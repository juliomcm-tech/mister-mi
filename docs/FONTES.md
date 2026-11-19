# Fontes e ferramentas gratuitas — verificação em 19/11/2026

Software gratuito, dados gratuitos e uma API live completa são coisas diferentes. Não existe nesta versão uma promessa de cobertura completa de todos os desportos.

| Recurso | Papel | Estado no Mister Mi | Limite principal |
|---|---|---|---|
| [OLBG](https://www.olbg.com/betting-tips) | Apoio da comunidade | Adaptador ativo | Popularidade não é probabilidade; só métricas explícitas e jogos identificados |
| [Forebet](https://www.forebet.com/) | Previsão estatística | Adaptador ativo | Modelo proprietário não auditado; mudança de HTML ou horário exige revisão |
| [ProTipster](https://www.protipster.com/betting-tips/today) | Tip Score de tipsters | Adaptador ativo, condicionado à métrica pública | Algumas tips não publicam Tip Score; ficam excluídas |
| [PredictZ](https://www.predictz.com/predictions/) | Corroboração categórica | Adaptador ativo | Sem probabilidade/horário explícitos; não é âncora temporal |
| [OpenLigaDB](https://www.openligadb.de/en/license) | Resultados finais | Integrado para Bundesliga 1/2 | Comunitário, ODbL e política de cache; sem voto de prognóstico |
| [openfootball](https://github.com/openfootball/football.json) | Histórico CC0 | Referência para investigação | Conversão diária; dados a montante podem ter atrasos; não liquida automaticamente |
| [football-data.org](https://www.football-data.org/pricing) | Fixtures/resultados | Opção futura | Plano gratuito limitado a competições e com atraso; odds são extra pago |
| [API-Football](https://www.api-football.com/pricing) | Previsões e resultados | Integração opcional | Chave, quota e restrições de épocas no plano gratuito |
| [TheSportsDB](https://api.thesportsdb.com/documentation) | Metadados multidesporto | Não usado como feed completo | Plano gratuito devolve amostras pequenas em vários endpoints |
| [StatsBomb Open Data](https://github.com/hudl/open-data) | Pesquisa de modelos de futebol | Opção futura | Competições selecionadas e termos/atribuição próprios; não é feed de hoje |
| [nba_api](https://github.com/swar/nba_api) | Cliente NBA | Experimental, fora da base obrigatória | Código MIT não concede direitos sobre dados; bloqueios de cloud e endpoints instáveis |

## Ferramentas quantitativas

| Projeto | Uso | Decisão |
|---|---|---|
| [scikit-learn](https://scikit-learn.org/stable/modules/calibration.html) | Calibração e avaliação | Referência para fase com histórico suficiente; não há probabilidade calibrada ativa |
| [statsmodels / Wilson](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html) | Intervalo da taxa de acerto | Fórmula implementada diretamente em Python |
| [QuantStats](https://github.com/ranaroussi/quantstats) | Relatórios e drawdown | Referência; contabilidade leve implementada sem dependências pesadas |
| [Pandera](https://github.com/unionai-oss/pandera) | Validação tabular | Opção futura se forem adicionados CSV maiores; campos atuais já validados explicitamente |
| [Flumine](https://github.com/betcode-org/flumine) | Arquitetura de simulação | Referência de desenho; nenhuma execução de apostas integrada |

## Opções que não foram ativadas

- `football-data.co.uk`: a página atual restringe usos automatizados/comerciais/treino. Não é um feed de treino automático por defeito.
- `worldfootballR`: repositório arquivado; dependências a montante têm direitos próprios.
- Repositórios antigos de ténis ou endpoints ESPN/NHL não documentados: verificar disponibilidade e licença antes de depender deles.
- Betfair: cliente open source não significa odds live gratuitas nem sandbox; a chave Delayed opera na Exchange real. Não faz parte desta instalação.

## Atribuição

Data from OpenLigaDB (www.openligadb.de), licensed under ODbL 1.0. [Licença](https://www.openligadb.de/en/license) · [Acesso](https://www.openligadb.de/en/terms-of-use).

As páginas de prognósticos são consultadas com identificação da aplicação e verificação de robots, sem stealth ou contorno de bloqueios. A aplicação mostra apenas evidência normalizada para comparação; não replica as páginas nem treina modelos sobre elas.
