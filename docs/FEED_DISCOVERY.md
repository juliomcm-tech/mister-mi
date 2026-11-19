# Auditoria independente de calendários e APIs — 19/11/2026

## Resultado prático

Foi implementado um **catálogo de calendário OpenLigaDB** em
`consensus/fixture_catalog.py`, separado do motor de prognósticos. Não altera
limiares, não cria odds, não treina um modelo e nunca conta como uma segunda
previsão. Os campos `counts_as_prediction: false` e
`complete_global_coverage: false` tornam essa separação explícita.

O âmbito atual é limitado a **futebol masculino, Alemanha, Bundesliga 1 e 2**.
Os números não são o total de jogos de todos os desportos ou de todas as ligas.

### Verificação ao vivo

As duas respostas documentadas da API tinham 306 jogos por época. Às
**17:10 UTC / Lisboa** de 19/11/2026, o catálogo normalizado encontrou:

| Dia em Lisboa | Bundesliga 1 | Bundesliga 2 | Total agendado nestas duas ligas |
|---|---:|---:|---:|
| 19/11/2026 | 0 | 0 | 0 |
| 20/11/2026 | 1 | 2 | 3 |
| 21/11/2026 | 6 | 4 | 10 |

O candidato OLBG **Bayern Munich vs Cologne**, em 20/11 às **19:30 UTC / Lisboa**,
corresponde ao jogo OpenLigaDB **83237**, FC Bayern München vs 1. FC Köln. O
[calendário publicado pela Bundesliga](https://products.bundesliga.com/fixtures/export/pdf?league%5B0%5D=1d570dd9-b10b-44de-9f64-8c91e56bf168&matchday%5B0%5D=10&season=b2f90c16-d6ef-40b1-a974-e6b1bf102c2a)
também confirma esse encontro e horário. Esta confirmação do calendário não
valida a seleção Bayern vence nem a torna um consenso de dois prognósticos.

### Interface para integração

```python
from consensus.fixture_catalog import collect_fixture_catalog, verify_fixture

catalog = collect_fixture_catalog(previous_catalog, now)
event_check = verify_fixture(tip, catalog)
```

É necessário persistir o objeto retornado, especialmente `resources`, entre
execuções. Cada recurso tem cache de seis horas e recuo persistente em erros,
de 30 minutos até seis horas. São feitos no máximo dois pedidos por recolha
efetiva. O cache conserva uma semana de eventos para permitir mudar de dia sem
repetir pedidos idênticos. `checked_at` conserva a hora real da consulta.

O catálogo valida liga, época, identificador, horário UTC explícito e os dois
participantes; descarta cancelamentos/adiamentos explícitos e identificadores
conflituantes. O verificador exige país conhecido, liga suportada e segmento
masculino principal. Os aliases são explícitos e conservadores, incluindo
Bayern Munich/FC Bayern München e Cologne/1. FC Köln.

Os estados possíveis são `verified`, `conflict`, `not_found`, `out_of_scope` e
`unverified`. Um jogo não encontrado nesta base comunitária não é prova de que
o jogo não existe. Em falhas completas, as contagens são `null`, em vez de um
zero que pudesse ser confundido com ausência de jogos. Estes dados requerem a
atribuição **Data from OpenLigaDB (www.openligadb.de), licensed under ODbL 1.0**.

Testes: sete regressões aprovadas para limites de pedidos, cache persistente,
passagem da meia-noite, recuo após erros, calendários vazios, cancelamentos,
identidades/datas/países/ligas e jogos cujo início passou durante o cache.

## Fontes comparadas

| Fonte | Uso possível | Condições verificadas | Decisão nesta versão |
|---|---|---|---|
| OpenLigaDB | Calendário e resultados comunitários | API documentada, sem chave; ODbL; solicita cache e poucos pedidos fora de jogos | Novo catálogo restrito às duas ligas verificadas |
| football-data.org | Calendários/resultados de futebol | Plano grátis: 12 competições, dados atrasados, 10 pedidos/minuto; acesso a jogos exige token registado | Boa opção de expansão após configurar chave; não ativa agora |
| API-Football / API-Sports | Calendários, resultados e previsões, conforme cobertura | Grátis: 100 pedidos/dia, 10/minuto; épocas disponíveis limitadas | Adaptador opcional existente; confirmar época/conta antes de prometer cobertura |
| TheSportsDB | Metadados e amostras multidesporto | Endpoint diário grátis limitado a três eventos; busca de equipas grátis limitada a Arsenal | Não serve como denominador global de jogos |
| openfootball/football.json | Calendários/histórico de futebol em JSON | CC0, sem chave; repositório anuncia atualização diária às 05:00 UTC | Referência possível para expansão, não incluída neste novo adaptador |
| ESPN | Páginas de calendários para consulta humana | Não foi estabelecida API pública suportada/licenciada; termos Disney/ESPN restringem extração automatizada | Não integrar os endpoints internos como se fossem um serviço gratuito autorizado |

Um calendário, um resultado final, uma previsão estatística e uma cotação têm
papéis diferentes. Acrescentar dez APIs de calendário não acrescenta dez votos
independentes ao consenso. Também não transforma popularidade em probabilidade
calibrada ou demonstra retorno positivo.

O agendamento de 48 execuções diárias deve respeitar quotas de cada fornecedor.
Por exemplo, três chamadas por execução já excedem 100 chamadas/dia, antes de
consultar previsões e resultados. Os dados estáveis precisam de cache central.

## Verificação dos encontros da imagem fornecida

Foi possível confirmar a existência de três encontros nas fontes organizadoras,
sem obter as métricas de prognóstico mostradas na imagem:

- A [UEFA](https://www.uefa.com/womenschampionsleague/news/02ab-220ff9af21a9-748c51d8b995-1000--women-s-champions-league-matchday-5-preview-chelsea-vs-pa/)
  publica Benfica vs Roma e Arsenal vs OL Lyonnes em 19/11/2026, às 21:00 CET
  (**20:00 em Lisboa**). Os jogos da imagem não devem ser descartados como
  fictícios apenas por não aparecerem no coletor atual.
- O [organizador ATP Finals](https://www.nittoatpfinals.com/en/news/shelton-jodar-nitto-atp-finals-2026-thursday)
  confirma Shelton vs Jodar e já publica o resultado final em 19/11. À hora
  desta auditoria esse jogo já não poderia ser uma opção futura do dia.
- O confronto Celtics vs Lakers da imagem não foi confirmado para essa data
  nas fontes primárias inspecionadas. O
  [calendário dos Lakers](https://www.nba.com/lakers/schedule?SeasonType=002&seasontype=002)
  apresenta Kings em 20/11 e Celtics em janeiro. Não se usa esta observação
  isolada para reconstruir toda a origem da imagem.

Nada nestas verificações comprova os valores 82,4%, 8,7/10, 71% ou Smart Score
96,1/97,5 apresentados na captura. Para os validar seriam necessários os dados
originais de cada fonte e a hora da recolha. O resultado posterior de Shelton
também não prova que uma previsão arquivada existia antes do jogo.

## Referências primárias

- [OpenLigaDB: documentação da API](https://api.openligadb.de/index.html),
  [condições de acesso](https://www.openligadb.de/en/terms-of-use) e
  [licença](https://www.openligadb.de/en/license).
- [football-data.org: preços](https://www.football-data.org/pricing),
  [cobertura](https://www.football-data.org/coverage) e
  [políticas da API](https://docs.football-data.org/general/v4/policies.html).
- [API-Football: preços](https://www.api-football.com/pricing),
  [limites](https://www.api-football.com/news/post/how-ratelimit-works) e
  [orçamento de chamadas](https://www.api-football.com/news/post/how-to-optimize-api-sports-calls-and-quota-usage).
- [TheSportsDB: documentação](https://api.thesportsdb.com/documentation) e
  [termos](https://www.thesportsdb.com/docs_terms_of_use.php).
- [openfootball: repositório e frequência de atualização](https://github.com/openfootball/football.json).
- [Disney/ESPN: termos de uso, secção 2](https://disneytermsofuse.com/english/).

Não houve repetição de fontes recusadas por outra rede, alteração de identidade
do cliente ou contorno de autenticação. A implementação adicionada não inclui
imagens, logótipos ou conteúdo integral dos fornecedores.
