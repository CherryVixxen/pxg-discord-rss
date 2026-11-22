#!/usr/bin/env python3
"""Read announcement-channel messages using the Discord bot API and build a static RSS feed."""
import datetime as dt
import html
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "1574194274701017238"
BASE_URL = "https://cherryvixxen.github.io/pxg-discord-rss"
STORE = Path("data/items.json")
OUTPUT = Path("docs/feed.xml")
MEDIA_DIR = Path("docs/media")
MAX_MEDIA_BYTES = 12 * 1024 * 1024
MAX_ITEMS = 2000
MAX_MEDIA_PER_RUN = 40 * 1024 * 1024
api = "https://discord.com/api/v10"
token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
MEDIA_BUDGET = MAX_MEDIA_PER_RUN


def fetch_json(url):
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN nao foi configurado.")
    req = urllib.request.Request(url, headers={
        "Authorization": "Bot " + token,
        "User-Agent": "PxGDiscordRSS/1.0 (personal announcement archiver)",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace")
        raise RuntimeError("Discord HTTP %s: %s" % (exc.code, detail)) from exc


def download_attachment(url, dest):
    global MEDIA_BUDGET
    if MEDIA_BUDGET <= 0:
        return False
    if not url.startswith("https://"):
        return False
    req = urllib.request.Request(url, headers={"User-Agent": "PxGDiscordRSS/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            reported = int(res.headers.get("Content-Length", "0"))
            if reported > MAX_MEDIA_BYTES or reported > MEDIA_BUDGET:
                return False
            buffer = bytearray()
            while True:
                chunk = res.read(65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_MEDIA_BYTES or len(buffer) > MEDIA_BUDGET:
                    return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(buffer)
        MEDIA_BUDGET -= len(buffer)
        return True
    except (OSError, urllib.error.URLError):
        return False


def load_records():
    if STORE.exists():
        result = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(result, list):
            return result
    return []


def get_new_messages(after):
    # API returns newest first. Page forward from last known snowflake to avoid missing a burst.
    messages = []
    cursor = after
    while True:
        params = {"limit": 100}
        if cursor:
            params["after"] = cursor
        url = api + "/channels/" + CHANNEL_ID + "/messages?" + urllib.parse.urlencode(params)
        page = fetch_json(url)
        if not isinstance(page, list):
            raise RuntimeError("Unexpected Discord response")
        if not page:
            break
        page.sort(key=lambda x: int(x["id"]))
        messages.extend(page)
        cursor = page[-1]["id"]
        if len(page) < 100:
            break
        if len(messages) > 10000:
            raise RuntimeError("Mais de 10000 mensagens pendentes. Interrompendo para evitar perdas.")
    messages.sort(key=lambda x: int(x["id"]))
    return messages


def localize_attachment(message_id, number, item):
    original = item.get("url") or item.get("proxy_url") or ""
    name = item.get("filename") or ("attachment-%s" % number)
    ext = Path(name).suffix.lower()[:12]
    if not ext or len(ext) < 2:
        ext = mimetypes.guess_extension(item.get("content_type") or "") or ".bin"
    path = MEDIA_DIR / ("%s-%s%s" % (message_id, number, ext))
    size = int(item.get("size") or 0)
    status = "original_link"
    url = original
    if size <= MAX_MEDIA_BYTES and download_attachment(original, path):
        url = BASE_URL + "/media/" + urllib.parse.quote(path.name)
        status = "saved"
    return {"name": name, "url": url, "status": status,
            "original_url": original, "size": size, "content_type": item.get("content_type") or ""}


def parse_message(msg, guild_id):
    # Webhook-authored followed announcements arrive in this destination channel.
    mid = msg["id"]
    files = [localize_attachment(mid, i, item) for i, item in enumerate(msg.get("attachments", []))]
    embeds = []
    for embed in msg.get("embeds", []):
        if not isinstance(embed, dict):
            continue
        embeds.append({
            "title": embed.get("title") or "",
            "description": embed.get("description") or "",
            "url": embed.get("url") or "",
            "fields": [{"name": f.get("name") or "", "value": f.get("value") or ""}
                       for f in embed.get("fields", [])],
            "image": (embed.get("image") or {}).get("url") or "",
            "thumbnail": (embed.get("thumbnail") or {}).get("url") or "",
            "video": (embed.get("video") or {}).get("url") or "",
        })
    author = msg.get("author") or {}
    return {
        "id": mid,
        "timestamp": msg.get("timestamp") or dt.datetime.now(dt.timezone.utc).isoformat(),
        "author": author.get("global_name") or author.get("username") or "Anúncio",
        "content": msg.get("content") or "",
        "attachments": files,
        "embeds": embeds,
        "message_url": "https://discord.com/channels/" + guild_id + "/" + CHANNEL_ID + "/" + mid,
        "type": msg.get("type"),
    }


def build_feed(records):
    rss = ET.Element("rss", {"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")
    def field(parent, name, value):
        ET.SubElement(parent, name).text = str(value or "")
    field(channel, "title", "PxG News — anuncios oficiais encaminhados do Discord")
    field(channel, "link", BASE_URL + "/")
    field(channel, "description", "Espelho de anuncios encaminhados para o canal #news do servidor projetos.")
    field(channel, "language", "pt-br")
    ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link",
                  {"href": BASE_URL + "/feed.xml", "rel": "self", "type": "application/rss+xml"})
    for record in reversed(records[-MAX_ITEMS:]):
        item = ET.SubElement(channel, "item")
        text = record.get("content", "")
        title = text.splitlines()[0][:150] if text.strip() else ""
        title = title or next((x.get("title") for x in record.get("embeds", []) if x.get("title")), "")
        title = title or "Anúncio com anexos"
        field(item, "title", title)
        field(item, "guid", "discord-" + record["id"])
        field(item, "link", record["message_url"])
        try:
            stamp = dt.datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            field(item, "pubDate", stamp.strftime("%a, %d %b %Y %H:%M:%S %z"))
        except ValueError:
            pass
        chunks = ["<pre style='white-space:pre-wrap'>%s</pre>" % html.escape(text)]
        for em in record.get("embeds", []):
            if em.get("title"):
                chunks.append("<h3>%s</h3>" % html.escape(em["title"]))
            if em.get("description"):
                chunks.append("<pre style='white-space:pre-wrap'>%s</pre>" % html.escape(em["description"]))
            if em.get("url"):
                safe = html.escape(em["url"], quote=True)
                chunks.append('<p><a href="%s">%s</a></p>' % (safe, safe))
            for f in em.get("fields", []):
                chunks.append("<p><b>%s</b>: %s</p>" % (html.escape(f["name"]), html.escape(f["value"])))
            for key in ("image", "thumbnail", "video"):
                if em.get(key):
                    safe = html.escape(em[key], quote=True)
                    chunks.append('<p><a href="%s">Mídia incorporada (%s)</a></p>' % (safe, key))
        for attachment in record.get("attachments", []):
            url = html.escape(attachment["url"], quote=True)
            label = html.escape(attachment["name"])
            if attachment["status"] == "saved" and (attachment["content_type"] or "").startswith("image/"):
                chunks.append('<p><img src="%s" alt="%s" style="max-width:100%%"></p>' % (url, label))
            else:
                chunks.append('<p><a href="%s">Anexo: %s</a>%s</p>' % (
                    url, label, " (link externo sujeito a expiração)" if attachment["status"] != "saved" else ""))
        field(item, "description", "\n".join(chunks))
        for attachment in record.get("attachments", []):
            if attachment["status"] == "saved":
                ET.SubElement(item, "enclosure", {
                    "url": attachment["url"],
                    "length": str(attachment["size"]),
                    "type": attachment["content_type"] or "application/octet-stream",
                })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(rss, space="  ")
    ET.ElementTree(rss).write(OUTPUT, encoding="utf-8", xml_declaration=True)


def main():
    records = load_records()
    latest = str(max((int(x["id"]) for x in records), default=0)) if records else ""
    channel_info = fetch_json(api + "/channels/" + CHANNEL_ID)
    guild_id = str(channel_info.get("guild_id") or "@me")
    messages = get_new_messages(latest)
    ids = {x["id"] for x in records}
    for message in messages:
        if message["id"] not in ids:
            records.append(parse_message(message, guild_id))
            ids.add(message["id"])
    records.sort(key=lambda x: int(x["id"]))
    records = records[-MAX_ITEMS:]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    build_feed(records)
    print("New messages:", len(messages), "total stored:", len(records))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
