# Auditoria independente do Mister Mi

Auditor: agente `audit_mister_mi`, separado do autor da simulação histórica. Verificação inicial: **19 de novembro de 2026, 14:42 UTC / Lisboa**. Este documento descreve o estado observado nessa hora; alterações posteriores exigem nova verificação.

## O que existe em produção

Fontes primárias consultadas diretamente:

- [Análise publicada no ramo `data`](https://raw.githubusercontent.com/juliomcm-tech/mister-mi/7a14992879e45b5733fa72939fc2bc0452481260/consenso_hoje.json).
- [Histórico publicado no mesmo commit](https://raw.githubusercontent.com/juliomcm-tech/mister-mi/7a14992879e45b5733fa72939fc2bc0452481260/history.json).
- [Código `main` observado](https://github.com/juliomcm-tech/mister-mi/tree/73dbc73ef6a2cb66f34c6cc55b695a51270f848d).
- [Execução de recolha concluída](https://github.com/juliomcm-tech/mister-mi/actions/runs/44544477628) e [execução de publicação Pages](https://github.com/juliomcm-tech/mister-mi/actions/runs/44545143454).

| Medida | Valor verificado |
|---|---:|
| Dia da análise | 2026-11-19 |
| Última recolha | 14:30:41 UTC |
| Previsões normalizadas recolhidas | 87 |
| Previsões elegíveis após filtros | 1 |
| Opções selecionadas | 0 |
| Recomendações registadas no histórico | 0 |
| Resultados liquidados | 0 |
| Taxa real de acerto | Não disponível (`null`) |
| ROI real/simulado do histórico publicado | Não disponível (`null`) |
| Probabilidade calibrada disponível | Não |

**Não é válido afirmar uma taxa de sucesso do Mister Mi, o seu melhor desporto ou o seu pior país com esta amostra.** Uma amostra de zero não significa uma taxa de acerto de 0%. Significa que ainda não há observações para a estimar.

## Disponibilidade real das fontes

| Fonte | Observação na execução do GitHub |
|---|---|
| OLBG | 83 registos normalizados; recolha concluída |
| Forebet | HTTP 403 nas cinco páginas; nenhum registo recolhido |
| ProTipster | 4 registos sem Tip Score público; excluídos do consenso |
| PredictZ | HTTP 403; nenhum registo recolhido |
| API-Football | Chave não configurada |

O facto de um adaptador existir e passar testes não demonstra que a fonte esteja acessível a partir dos servidores do GitHub. O estado publicado preserva os erros. Não foi contornado qualquer bloqueio para fabricar cobertura.

Os endpoints da análise e do histórico responderam HTTP 200. O endpoint público do ramo `data` publicou `Access-Control-Allow-Origin: *`. A recolha e a seleção são processos distintos: a execução pode concluir com sucesso e selecionar zero opções.

## Verificação da publicação nessa hora

A raiz de GitHub Pages ainda apresentava a página README gerada por Jekyll. O painel estava acessível em `/mister-mi/web/`. O JavaScript publicado ainda utilizava a cópia inicial `./data/consenso_hoje.json` e uma chamada incondicional a `AbortSignal.timeout()`. O código local já estava a receber uma correção para ler o ramo persistente `data`; esta auditoria não trata uma alteração local como prova de publicação.

A cópia inicial tinha data de recolha **14:14:02 UTC**, diferente da recolha persistente **14:30:41 UTC**. Os diagnósticos das fontes também diferiam. Uma cópia inicial não deve substituir silenciosamente o estado real da execução.

## Verificação do código e das contas

Foram lidos `consensus/core.py`, `consensus/sources.py`, `consensus/cli.py`, `consensus/history.py`, `consensus/free_results.py`, `web/app.js`, `web/portfolio.js`, `scripts/save_data.py` e `.github/workflows/collect.yml`.

- O histórico regista a primeira recomendação e o primeiro preço observado; atualizações não melhoram retroativamente a odd.
- Sem odd observada, um resultado pode contar para a taxa de acerto, mas não deve entrar no ROI.
- A curva de drawdown implementada usa a ordem de publicação das recomendações, e não a hora real de liquidação. Essa definição está explicitada na arquitetura.
- Uma fonte de resultados, como OpenLigaDB, não é uma segunda previsão nem um voto adicional de consenso.
- Os limites de exposição da carteira são políticas de simulação. Não constituem probabilidades de perda nem proteção garantida.

Comandos executados nesta verificação:

```text
../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.mjs
```

Resultado: **29 testes Python e 20 testes Node aprovados**, sem falhas. Estes testes verificam regras e casos artificiais; não medem capacidade preditiva nem demonstram rentabilidade.

## Auditoria da simulação histórica

A implementação da experiência histórica foi feita por outro agente em `scripts/backtest.py`, `tests/test_backtest.py` e `docs/BACKTEST.md`. Esta auditoria leu o código, executou os testes e refez as contas independentemente. Não foram alterados o modelo, os parâmetros ou os dados pelo auditor.

### Protocolo verificado

- Treino inicial: épocas 2023/24 da Premier League e Bundesliga, 686 jogos completos.
- Teste cronológico: época 2024/25, entre 2024-07-01 e 2025-06-30, 686 jogos completos.
- Um dia inteiro é previsto antes de qualquer resultado desse dia atualizar o modelo. Foi verificado `trained_through < date` em todas as 662 previsões avaliadas.
- O método de previsão lê os participantes e o estado anterior, sem ler o placar do próprio jogo. As previsões ficam separadas das avaliações com resultados.
- Há um mínimo de 60 jogos da liga e cinco jogos de cada equipa; 24 jogos do teste ficaram fora por falta de histórico elegível.
- O limiar de seleção foi fixado em 0,65 antes da execução. O hash da configuração permaneceu `5f51eb509fc1a85d703c5a5ebee55ee557d71a7e4bad88f71303450690083851` entre a primeira execução observada e a versão final com registo completo. Isso não equivale a uma pré-registração externa.
- Os resultados são de um modelo Poisson experimental. Não existem aqui previsões pré-jogo arquivadas de OLBG, Forebet ou ProTipster nem uma reconstrução do consenso de produção.

### Reprodução independente

O auditor voltou a obter as quatro fontes, verificou os quatro hashes dos bytes e refez a execução. Depois verificou o ficheiro completo `docs/backtest-ledger.json`, que contém **662 previsões sem placares e 662 avaliações posteriores**. Foram comparados os identificadores, probabilidades, classes previstas, resultados e limiares linha a linha. As previsões não contêm os campos `actual`, `correct`, `final_score`, `home_goals` ou `away_goals`.

Os dados da versão final estão fixados no [commit openfootball `e6744429ee395bc86f247348c6184bb08d4eb361`](https://github.com/openfootball/football.json/tree/e6744429ee395bc86f247348c6184bb08d4eb361). Os hashes dos quatro ficheiros coincidem com os obtidos pelo auditor. O histórico original de publicação e possíveis correções posteriores dos resultados não foi reconstruído.

Verificações de integridade:

| Artefacto | SHA-256 verificado |
|---|---|
| Sequência de previsões anteriores à avaliação | `516fba1332a97920ea63e0cb2037ee6d91fc53c5a6836a5227d50c6aacc384b4` |
| Ficheiro completo de previsões e avaliações | `2c7f955f0d5966bd4bfcfe183ec5391323bcf87290089bb28b6b4e2cdc3e0f04` |
| Script da experiência | `a86d99632fde7b24c9c9e1d854126a054e3ec1565be602c362abdf2eb50978a9` |

### Resultados recalculados

| Medida do modelo experimental | Resultado |
|---|---:|
| Jogos avaliados | 662 |
| Jogos selecionados | 150 |
| Acertos nas seleções | 103 |
| Erros nas seleções | 47 |
| Taxa de acerto nas seleções | 68,67% |
| Intervalo de Wilson de 95% | 60,86%–75,55% |
| Cobertura das seleções sobre jogos avaliados | 22,66% |
| Acerto da classe mais provável em todos os jogos avaliados | 50,76% |
| Baseline «sempre vence a equipa da casa», nos mesmos jogos | 40,18% |
| Brier multiclasse, soma de três classes, escala 0 a 2 | 0,601315 |
| Brier do prior histórico nos mesmos jogos | 0,656884 |
| Log loss do modelo, logaritmo natural | 1,004583 |
| Log loss do prior histórico | 1,082928 |
| ROI, valor esperado e Kelly | Não calculados: sem odds históricas verificadas |

As contagens de acertos, Brier e log loss acima foram recalculadas a partir dos placares e probabilidades, sem confiar apenas no resumo produzido pelo autor. Os baselines usam exatamente os mesmos jogos elegíveis.

Nos 150 jogos selecionados, a média da maior probabilidade atribuída pelo modelo é **73,67%**, enquanto a frequência de acerto observada é **68,67%**. Essa diferença é descritiva desta amostra; não constitui, por si só, um teste conclusivo de calibração. A versão declara corretamente probabilidades **não calibradas**.

Oito testes adicionais passaram, incluindo alteração do resultado do próprio jogo, alteração de um resultado futuro, alteração de um resultado do mesmo dia, inversão da ordem de entrada, atualização válida no dia seguinte, mínimos de histórico e igualdade das coortes dos baselines. Estes testes de isolamento temporal não provam capacidade preditiva em novas épocas.

### Conclusão e limites

**A aritmética e o isolamento cronológico da experiência foram confirmados nas verificações descritas.** Não foi identificada inclusão de resultados do próprio dia no estado usado para prever esse dia. Esta conclusão é limitada ao código, dados e execução auditados.

É válido dizer que este modelo experimental acertou 103 de 150 seleções nesta amostra histórica. **Não é válido apresentar 68,67% como a taxa real de sucesso do Mister Mi em produção**, nem como uma probabilidade garantida para os jogos atuais. A experiência é retrospetiva e não uma prova prospetiva cega.

Os intervalos das duas ligas sobrepõem-se: as diferenças observadas entre Alemanha e Inglaterra não justificam uma conclusão segura de que um país será superior no futuro. O ensaio também não mede ténis, NBA, hóquei ou todas as competições de futebol.

Sem preços históricos pré-jogo, as seleções podem favorecer resultados prováveis com odds demasiado baixas para produzir lucro. Taxa de acerto e melhoria contra um baseline estatístico não demonstram vantagem sobre o mercado. Nenhum resultado experimental foi acrescentado ao livro real de recomendações como se tivesse sido publicado antes dos jogos.
