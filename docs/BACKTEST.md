# Mister Mi — ensaio histórico experimental

Este ensaio avalia **um modelo Poisson de referência**. Não é a taxa de acerto do Mister Mi em produção: não há neste ensaio recomendações reais do consenso OLBG/Forebet/ProTipster liquidadas, nem arquivos pré-jogo completos dessas fontes. Não se reconstruíram previsões antigas a partir do resultado final.

## Resultado executado

| Medida | Resultado |
| --- | ---: |
| Jogos concluídos de treino, época 2023/24 | 686 |
| Jogos concluídos da época de teste 2024/25 | 686 |
| Jogos avaliados após aquecimento das equipas | 662 |
| Jogos excluídos por falta de histórico | 24 |
| Seleções com probabilidade modelada mínima de 65% | 150 |
| Seleções certas / erradas | 103 / 47 |
| Taxa de acerto nas seleções | 68,67% |
| Intervalo de Wilson de 95% | 60,86%–75,55% |
| Cobertura entre os jogos avaliados | 22,66% |
| Acerto da escolha mais provável em todos os jogos avaliados | 50,76% |
| Brier multiclasse, soma das três classes; menor é melhor | 0,601315 |
| Log loss, logaritmo natural; menor é melhor | 1,004583 |
| Brier da referência com frequências históricas | 0,656884 |
| Log loss da referência com frequências históricas | 1,082928 |
| Referência «sempre equipa da casa», mesmos 662 jogos | 40,18% |
| Referência «sempre equipa da casa», mesmas 150 seleções | 49,33% |

| Liga de teste | Avaliados | Selecionados | Certos / errados | Acerto | Wilson 95% |
| --- | ---: | ---: | ---: | ---: | --- |
| Premier League inglesa | 366 | 77 | 51 / 26 | 66,23% | 55,12%–75,80% |
| Bundesliga alemã | 296 | 73 | 52 / 21 | 71,23% | 59,99%–80,35% |

Os intervalos sobrepõem-se. Este resultado não demonstra que o sistema deva evitar a Inglaterra ou preferir a Alemanha em geral; representa apenas duas ligas, um modelo e uma época de teste.

**Sem odds históricas pré-jogo verificadas, não há ROI, valor esperado nem Kelly neste ensaio.** Uma taxa de acerto superior à referência não demonstra rentabilidade. As probabilidades não foram calibradas.

## Protocolo fixado

1. Usar apenas resultados `score.ft` explícitos do projeto CC0 `openfootball/football.json`: primeira divisão inglesa e alemã.
2. Treino inicial: época 2023/24, jogos anteriores a 01/07/2024. Teste: época 2024/25, intervalo declarado 01/07/2024–30/06/2025; jogos avaliados efetivos de 16/08/2024 a 25/05/2025.
3. Ordenar por dia. Prever **todos os jogos de um dia antes de aprender qualquer resultado desse dia**. Os horários dos ficheiros não têm fuso inequívoco, pelo que não se simula aprendizagem dentro do próprio dia.
4. Exigir pelo menos 60 jogos anteriores da liga e cinco de cada equipa. Equipas promovidas ou sem histórico permanecem fora até cumprir esse mínimo.
5. Estimar a média de golos da casa e de fora da liga. O ataque e a defesa de cada equipa são estimados pelos seus golos marcados/sofridos anteriores, com retração equivalente a cinco jogos para a média anterior da liga.
6. Modelar golos com Poisson independente, intensidades limitadas ao intervalo 0,15–5,0 e resultados de 0 a 20 golos. Normalizar a distribuição das três classes: casa, empate, fora.
7. Escolher a classe mais provável apenas quando a sua probabilidade modelada é pelo menos 0,65. O limiar e os restantes parâmetros não foram ajustados aos resultados do teste.
8. Depois das previsões do dia, avaliar as escolhas e só então incorporar esses resultados no treino dos dias seguintes. Este é um teste com janela crescente, não um modelo congelado durante toda a época.
9. Comparar sempre na mesma amostra elegível. A referência probabilística usa frequências anteriores de casa/empate/fora com suavização de Laplace; «sempre casa» compara apenas o acerto, sem probabilidades artificiais.

A primeira execução já produziu os valores acima. As alterações posteriores acrescentaram o ficheiro completo para auditoria e URLs fixos num commit; não alteraram os parâmetros ou os resultados.

## Proveniência e reprodução

Commit imutável a montante: `e6744429ee395bc86f247348c6184bb08d4eb361`.

| Ficheiro no commit acima | Jogos | SHA-256 dos bytes |
| --- | ---: | --- |
| `2023-24/en.1.json` | 380 | `03e13eafbf78dfe00d7e89dd3bf6643986eb6e8fd86c7664aeb8c5bc0bed88d0` |
| `2024-25/en.1.json` | 380 | `c3d18f552d83382cd4b6b21127adbbfe38e7f8618ddc979fb5404f2df07d0a75` |
| `2023-24/de.1.json` | 306 | `d104edde48a5e254545eac3d3ed379a09801e1ebcef5c6480e28bc36fcfa202d` |
| `2024-25/de.1.json` | 306 | `f473d6595e6c29ebedc08b09177aed6a6b2ff0fa8378b82f51dea469139f44c3` |

Base dos URLs: `https://raw.githubusercontent.com/openfootball/football.json/e6744429ee395bc86f247348c6184bb08d4eb361/`.

Os URLs completos, horários de recolha, tamanhos, ETags e hashes constam de [backtest.json](../web/data/backtest.json). A licença dos dados é [CC0 1.0](https://github.com/openfootball/football.json/blob/master/LICENSE.md).

O registo completo está em [backtest-ledger.json](backtest-ledger.json): 662 previsões antes do resultado e 662 avaliações correspondentes. O painel recebe apenas o resumo, sem carregar este ficheiro de auditoria.

Hash canónico das previsões anteriores aos resultados: `516fba1332a97920ea63e0cb2037ee6d91fc53c5a6836a5227d50c6aacc384b4`.

Hash SHA-256 do ficheiro de auditoria desta execução: `2c7f955f0d5966bd4bfcfe183ec5391323bcf87290089bb28b6b4e2cdc3e0f04`.

```bash
python scripts/backtest.py --source-ref e6744429ee395bc86f247348c6184bb08d4eb361
python -m unittest discover -s tests -p 'test_backtest.py' -v
```

Os horários de execução e recolha mudam numa reprodução, pelo que o hash do ficheiro completo também muda. Com os mesmos dados e código, o hash canónico das previsões e as métricas devem permanecer iguais.

## Limites da interpretação

- É uma simulação cronológica retrospetiva, não uma experiência prospetiva cega com clientes.
- Conhecer hoje os resultados históricos não prova quando esses dados estavam disponíveis nem reconstrói correções feitas posteriormente pelos contribuidores.
- O modelo não inclui lesões, convocatórias, alinhamentos, forma recente ponderada, calendário ou preços de mercado.
- Não se extrapola este resultado para ténis, NBA, hóquei, outros países ou mercados de golos.
- Não se usa o resultado deste laboratório para alterar automaticamente os filtros da produção.
- O desempenho real do Mister Mi será medido pelo histórico imutável das recomendações publicadas antes do início e pelos resultados confirmados posteriormente.
