# PxG Discord RSS

Feed RSS gratuito dos anúncios oficiais encaminhados ao canal `#news` do servidor Discord **projetos**.

- **Canal de origem:** `1574194274701017238`
- **Feed planejado:** https://cherryvixxen.github.io/pxg-discord-rss/feed.xml
- **Atualização:** GitHub Actions a cada 15 minutos (pode atrasar)
- **Destino:** leitores RSS como Feeder (Android); a publicação no WhatsApp é manual.

## Configuração para ativar

1. No Discord Developer Portal, confira que **Message Content Intent** está habilitado. O bot já foi instalado no servidor `projetos`; ele precisa de **View Channels** e **Read Message History** em `#news`.
2. Abra [Settings → Secrets and variables → Actions](https://github.com/CherryVixxen/pxg-discord-rss/settings/secrets/actions), clique **New repository secret** e configure o nome **`DISCORD_BOT_TOKEN`** com o token do bot (NUNCA coloque em arquivos ou mensagens).
3. Abra [Settings → Pages](https://github.com/CherryVixxen/pxg-discord-rss/settings/pages) e, em **Build and deployment → Source**, selecione **GitHub Actions**.
4. Abra [Actions](https://github.com/CherryVixxen/pxg-discord-rss/actions), selecione **Sincronizar Discord e publicar RSS** e clique **Run workflow** para iniciar um teste.
5. Após a execução e publicação com sucesso, abra https://cherryvixxen.github.io/pxg-discord-rss/feed.xml e cadastre a URL no Feeder no celular.

## Conteúdo e limitações

O código armazena textos integrais, metadados das mensagens, imagens e anexos pequenos (até 12 MiB por arquivo), além de títulos, descrições e campos dos embeds. Referências a mídias grandes ou externas continuam como links; URLs temporárias do CDN do Discord podem expirar. RSS e WhatsApp não reproduzem necessariamente exatamente a mesma formatação do Discord. Conteúdo que não pôde ser baixado é sinalizado no feed, nunca omitido sem aviso.

A primeira execução captura as mensagens recentes disponíveis do canal. As seguintes processam apenas mensagens posteriores ao último ID salvo; preservam os registros antigos e os IDs para não duplicar publicações. Alterações ou exclusões de anúncios antigos não são sincronizadas automaticamente.

O GitHub Pages é público: **tudo o que o bot copiar de `#news` para o RSS ficará visível publicamente.** Use somente os anúncios que você tem permissão para redistribuir.

O GitHub pode atrasar ou suspender agendamentos após períodos prolongados de inatividade. Se o feed não atualizar, veja a aba Actions.

## Arquivos

- `sync.py`: leitura da API oficial do Discord, arquivo local de mídias pequenas, geração do feed
- `.github/workflows/rss.yml`: execução agendada e publicação do Pages
- `data/items.json`: histórico dos anúncios já capturados
- `docs/feed.xml`: RSS público
- `docs/media/`: arquivos de mídia baixados

**Segurança:** não compartilhe tokens. A execução usa o segredo `DISCORD_BOT_TOKEN` definido na configuração privada do GitHub.
