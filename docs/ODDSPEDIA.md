# Oddspedia API no Mister Mi

## Configuração

No repositório GitHub, abrir **Settings → Secrets and variables → Actions**.
Criar ou atualizar o Secret **ODDSPEDIA_FEED_URL** com o URL completo da primeira
linha do gerador API da conta, junto de OPEN. O valor inclui `api_token` e `lang`.
Não deve conter HTML, JSON, uma ligação Markdown ou uma chave de exemplo.
O valor não pode ser lido novamente pelo conector: o teste é feito no runner.

## Documentação fornecida pelo proprietário

Lida em 19/11/2026, secção **Oddspedia data feeds → Configuration** do ficheiro
fornecido na conversa. A secção documenta:

- `/api/sports`: catálogo de desportos; `lang` opcional.
- `/api/search`: eventos de uma equipa/jogador; `q` obrigatório, em minúsculas,
  uma equipa por pesquisa.
- `/api/categories`: `sport_id` opcional.
- `/api/tournaments`: `sport_id` e `category_id` opcionais.
- `/api/teams`: `sport_id` obrigatório; categoria/torneio opcionais.

O ficheiro não inclui a lista de parâmetros de `/api/matches` nem documenta um
endpoint de odds com os respetivos mercados e intervalos temporais. As regras
`domain`, seleção de operadores e afiliados aparecem na secção de widgets;
não se inventa um parâmetro de domínio para corrigir uma recusa na API.

## Recolha e estado

O Secret existente continua a funcionar como origem da credencial. A recolha
extrai a chave e o idioma no runner e constrói os pedidos documentados:

1. Um pedido a `/api/sports` para verificar o acesso e o formato do catálogo.
2. Se o catálogo for reconhecido, até seis pesquisas `/api/search?q=...`, uma
   equipa por chamada, usando equipas das seleções atuais e próximas datas.

Uma recusa no catálogo termina a tentativa. Uma falha de pesquisa interrompe as
pesquisas restantes. Não há retries, sondagem de rotas ou tentativa de contornar
403. O coletor deixou de depender do `/api/matches` sem filtros que devolvia
«Empty data» no navegador do proprietário. Não são acrescentados parâmetros de
data não documentados. As pesquisas são reconstruídas a partir da análise de
cada execução; o URL do Secret não fixa o dia do calendário.

Texto simples `Empty data`, a mesma mensagem em JSON e listas JSON vazias são
identificados como resposta vazia. Essa situação é distinta de HTTP 403, JSON
malformado ou uma mensagem de erro da API.

O cliente bloqueia redirecionamentos para outro host, limita tempo e tamanho da
resposta e não expõe URLs ou corpos de erro. A chave extraída é mascarada nos
logs do GitHub Actions. A publicação inclui apenas estado, instante, contagens,
nomes/tipos de campos e os nomes públicos de equipas pesquisadas. A soma de
registos de pesquisas pode repetir eventos e não é contada como jogos únicos.

Em **Fontes → Oddspedia API**, a app distingue catálogo recebido, resposta vazia,
pesquisa por confirmar e recusa de acesso. Estados antigos não aparecem como
verificações recentes. O editor de widgets continua removido.

Uma resposta JSON confirma a leitura do feed, mas não valida automaticamente
identidades, datas, mercados, odds ou previsões. O estado inclui explicitamente
`counts_as_prediction: false` e `used_in_analysis: false`. O catálogo de desportos
é identificado como tal e a soma de `match_count` não é inventada como uma lista
de jogos analisados. O mapeamento dos jogos e mercados depende do esquema real
recebido e será validado antes de usar o feed na seleção.

A configuração da API é feita no GitHub. Atribuição visível no rodapé quando a
API respondeu: logótipo e texto “Data powered by Oddspedia”, com ligação nofollow.

## Referências oficiais

- https://widgets.oddspedia.com/
- https://widgets.oddspedia.com/terms
- https://widgets.oddspedia.com/obligations

Não são publicadas nem transcritas neste documento as credenciais da conta.
