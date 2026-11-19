# Oddspedia API no Mister Mi

## Configuração

No repositório GitHub, abrir **Settings → Secrets and variables → Actions**.
Criar ou atualizar o Secret **ODDSPEDIA_FEED_URL** com o URL completo da primeira
linha do gerador API da conta, junto de OPEN. O valor inclui `api_token` e `lang`.
Não deve conter HTML, JSON, uma ligação Markdown ou uma chave de exemplo.
O valor não pode ser lido novamente pelo conector: o teste é feito no runner.

O endpoint de jogos `/api/matches` e o catálogo `/api/sports` foram identificados
no ecrã da conta fornecido pelo proprietário. A recolha aceita apenas HTTPS no
host `widgets.oddspedia.com` e esses caminhos, com uma única chave não vazia.
Caracteres HTML escapados no separador `&amp;` são normalizados.

## Recolha e estado

O workflow passa o Secret apenas ao passo Python de recolha. Há um pedido de
leitura autenticado por execução, sem robots de páginas públicas nem tentativas
de contornar recusas. O cliente bloqueia redirecionamentos para outro host,
limita tempo e tamanho da resposta e não expõe URLs ou corpos de erro.
A chave extraída é também mascarada nos logs do GitHub Actions.

A publicação inclui apenas estado, instante, contagem de registos e uma descrição
de nomes/tipos de campos. URLs, chaves e valores da resposta não são publicados.
Em **Fontes → Oddspedia API**, a app apresenta essa verificação. Um estado antigo
não aparece como uma ligação verificada recentemente.

Uma resposta JSON confirma a leitura do feed, mas não valida automaticamente
identidades, datas, mercados, odds ou previsões. O estado inclui explicitamente
`counts_as_prediction: false` e `used_in_analysis: false`. O catálogo de desportos
é identificado como tal e a soma de `match_count` não é inventada como uma lista
de jogos analisados. O mapeamento dos jogos e mercados depende do esquema real
recebido e será validado antes de usar o feed na seleção.

O editor e a execução de widgets foram retirados da app a pedido do proprietário.
A configuração da API é feita no GitHub. Atribuição visível no rodapé quando a
API respondeu: logótipo e texto “Data powered by Oddspedia”, com ligação nofollow.

## Referências oficiais

- https://widgets.oddspedia.com/
- https://widgets.oddspedia.com/terms
- https://widgets.oddspedia.com/obligations

Não são publicadas nem transcritas neste documento as credenciais da conta.
