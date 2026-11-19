# Próximos dois dias e comparação das primeiras recolhas

## Pré-visualização

Cada execução recolhe as fontes uma só vez. `upcoming_previews()` analisa as
previsões com data de amanhã e depois de amanhã em `Europe/Lisbon`, usando as
mesmas regras de identidade, mercados, votos, métricas, conflitos e exclusões.
A frescura continua a ser calculada com o relógio real da recolha; o código
nunca adianta o relógio para tornar dados antigos válidos.

As vistas mostram o que as fontes publicam agora para jogos futuros. Não
mostram resultados futuros conhecidos nem simulam dados ainda não publicados.
As datas são recalculadas diariamente e respeitam a passagem de ano e o horário
de verão de Lisboa. Não há pedidos adicionais às fontes para gerar estas vistas.

O JSON principal contém `previews` com duas entradas. Nestas, `data` é sempre
vazio, `total_selected` é zero, `is_preview` é verdadeiro e
`analysis_mode` é `future_preview`. Os candidatos com consenso prévio ficam
em `candidates`, com `is_recommendation: false`; sinais qualificados sem outra
fonte ficam em `watchlist`. `total_consensus_candidates` distingue consenso
preliminar de recomendações do dia. `history.record()` recusa uma pré-visualização.
O simulador da carteira continua a receber apenas `data` do dia corrente.

O navegador exige uma recolha recente do dia corrente e a data exata de cada
pré-visualização. Uma entrada ausente ou malformada é apresentada como dados
indisponíveis, e não como zero candidatos. Os filtros locais de países,
desportos, combinações e odds aplicam-se também aos candidatos futuros.

## Verificação direta em 19/11/2026, 16:10 UTC / Lisboa

Uma recolha de auditoria apenas das cinco páginas públicas OLBG permitidas
encontrou os valores abaixo. Forebet e PredictZ não foram repetidos por outra
via após a recusa observada no GitHub. Estes números datados não garantem o
estado das recolhas posteriores nem constituem recomendações.

| Data dos jogos | Previsões dessa data | Aptas na fonte | Com duas fontes independentes |
| --- | ---: | ---: | ---: |
| 20/11/2026 | 62 | 1 | 0 |
| 21/11/2026 | 49 | 3 | 0 |

O candidato de 20/11 era Bayern Munich vs Cologne, às 19:30 de Lisboa,
13/15 votos para Bayern Munich. Os de 21/11 eram Man City vs Fulham,
Tottenham vs Ipswich e Newcastle vs Arsenal. Estes são sinais de uma comunidade,
não probabilidades calibradas, confirmações independentes ou apostas executadas.

## A simulação histórica alterou as regras?

Não. O agente de auditoria comparou os commits e o autor voltou a verificar o
ficheiro `consensus/core.py` antes e depois da introdução da simulação: os bytes
eram idênticos. O commit experimental não alterou esse ficheiro, os adaptadores,
o CLI ou `config/settings.json`. O script da experiência escreve apenas o
relatório de backtest e o respetivo registo; não otimiza definições de produção.
As definições da primeira implementação e as atuais mantêm 15 votos, 75% OLBG,
65% no modelo publicado da fonte, duas fontes distintas e consenso mínimo 70.

| Registo preservado em 19/11/2026 | Recolhidas | Aptas numa fonte | Confirmadas entre fontes |
| --- | ---: | ---: | ---: |
| Desenvolvimento, 14:14 | 275 | 69 | 0 |
| Primeira execução GitHub, 14:23 | 27 | 1 | 0 |
| GitHub, 14:30 | 87 | 1 | 0 |
| GitHub, 15:55 | 174 | 1 | 0 |

A recolha de desenvolvimento acedia a 236 previsões Forebet e 12 PredictZ.
Ambas as fontes já devolviam HTTP 403 na primeira execução GitHub, antes do
backtest. Os registos preservados não comprovam seleções finais anteriores;
também não permitem afirmar o que apareceu numa execução não preservada.

Referências imutáveis:

- [Primeiro snapshot de desenvolvimento](https://github.com/juliomcm-tech/mister-mi/blob/6805ebc048374053387dbf6ecc44abf8b80f8035/web/data/consenso_hoje.json).
- [Primeira análise guardada no GitHub](https://github.com/juliomcm-tech/mister-mi/blob/783cd4caa1e6378d3118fc0bbdf0cbf5556be40d/consenso_hoje.json).
- [Versão anterior à simulação](https://github.com/juliomcm-tech/mister-mi/tree/73dbc73ef6a2cb66f34c6cc55b695a51270f848d).
- [Commit que introduziu a experiência histórica](https://github.com/juliomcm-tech/mister-mi/commit/ee21fdcbe4376e1ba8d114817859f46df62e0b03).
- [Análise das 15:55](https://github.com/juliomcm-tech/mister-mi/blob/2ed00894342363f373c046c95455b6f2cc670242/consenso_hoje.json).

Validação desta versão: 62 testes Python e 39 testes Node aprovados, incluindo
datas futuras, relógio real de frescura, viragem do ano, meia-noite no verão,
conflitos e exclusões, dados ausentes e a separação entre previews e contabilidade.
