# Mister Mi

O teu analista desportivo: recolhe prognósticos, compara o mesmo evento e mercado, aplica critérios explícitos e apresenta apenas opções atuais que os cumprem. O visual azul e translúcido inspira-se na referência fornecida; a personagem original Mister Mi é o rosto do painel.

**O Mister Mi pode concluir «nenhuma entrada». Consenso não é probabilidade de vitória nem garantia de retorno.**

## O que está implementado

- Futebol, ténis, basquetebol, hóquei e futebol americano nas fontes suportadas. A notação explícita visitante @ anfitrião é normalizada sem inverter a seleção.
- OLBG, Forebet, ProTipster e PredictZ; API-Football opcional, mediante chave e cobertura do plano.
- Data corrente em `Europe/Lisbon`, timestamps com fuso, apenas jogos ainda por começar e recolhas recentes.
- Identificação de participantes, segmento feminino/sub-idade, país conhecido e horários compatíveis. Abreviaturas de tenistas ambíguas são excluídas.
- Mesmo mercado e seleção em pelo menos duas fontes distintas; páginas duplicadas e vários tipsters não são votos adicionais.
- Leitura das previsões adicionais já incluídas nos dados públicos da página OLBG, além das primeiras linhas visíveis, com validação de datas, votos e domínio e sem executar JavaScript externo.
- Funil de cobertura: previsões recolhidas, previsões de hoje, jogos distintos identificados, evidências aptas e opções confirmadas, com motivos das exclusões.
- Candidatos **Em observação** quando uma previsão passa a regra da fonte mas falta confirmação independente. Não são recomendações e não entram no histórico de acerto nem na carteira simulada.
- ProTipster sem Tip Score público fica excluído. Uma odd nunca é interpretada como Tip Score.
- Estatísticas por desporto, país, mercado e desporto × país, com amostra e intervalo de Wilson de 95%.
- Livro imutável de primeiras recomendações, preços observados, resultados confirmados, ROI e drawdown em posições de simulação de uma unidade.
- Simulador de exposição com limites por jogo, dia, país, desporto e competição. Não executa apostas nem estima Kelly a partir do consenso.
- Exclusões locais e regras partilhadas no GitHub; a remoção de uma categoria não apaga resultados antigos.
- Resultados OpenLigaDB para Bundesliga 1/2 e API-Football opcional para futebol; outros resultados permanecem pendentes até confirmação manual verificável.
- GitHub Actions a cada 30 minutos, mais execução manual e por alteração da configuração.
- App instalável no smartphone, com ícone M.Mi., abertura standalone, atalhos e navegação inferior adaptada ao ecrã.
- Avatar com piscar de olhos e movimento ligeiro do cabelo; expressão preocupada apenas com resultados reais suficientes e negativos. O ensaio experimental não altera esse estado.

## Instalar no smartphone

Abrir [Mister Mi no GitHub Pages](https://juliomcm-tech.github.io/mister-mi/) e tocar em **Instalar app**. Em Android/Chrome compatível, o botão abre o pedido de instalação quando o navegador o disponibiliza. Em iPhone, abrir no Safari e usar **Partilhar → Adicionar ao ecrã principal**; a app mostra essas instruções quando não existe pedido nativo.

O manifest, os ícones PNG 192/512 e maskable, o ícone Apple e o service worker usam caminhos relativos, compatíveis com `main / (root)` e com publicação pelo Actions. O modo offline guarda apenas a interface: análises, odds, histórico e APIs nunca são servidos de uma cache antiga. A app continua a precisar de Internet para previsões atuais. Atualizações da interface são aplicadas pelo botão de atualização, sem recarregar formulários automaticamente.

As animações usam CSS e três imagens WebP, cerca de 120 KB no total, sem vídeo nem JavaScript por frame. Param quando o avatar sai do ecrã ou a página fica oculta; podem ser desligadas e respeitam a preferência do sistema por movimento reduzido. O lettering usa Dela Gothic One e a interface usa Manrope, em subconjuntos latinos WOFF2 alojados no próprio projeto, com as licenças OFL incluídas.

## Simulação histórica e auditoria

O separador **Histórico** inclui um laboratório experimental com previsão cronológica de jogos de 2024/25, usando apenas resultados de dias anteriores. O modelo Poisson de referência acertou **103 de 150 seleções (68,67%)**, com **47 erros** e intervalo de 95% **60,86%–75,55%**; foram avaliados 662 jogos. Não é a taxa de sucesso real do consenso Mister Mi, que ainda não tem resultados liquidados suficientes. Não há ROI sem odds históricas verificadas.

O método, os dados imutáveis e o registo completo estão em [BACKTEST.md](docs/BACKTEST.md); a reprodução e verificação por outro agente estão em [AUDIT.md](docs/AUDIT.md).

## Como funciona a atualização

| Modo | O que faz o refresh |
|---|---|
| GitHub Pages | Recarrega a última análise publicada, sem cache do navegador. O Python corre no Actions. |
| Pages + serviço protegido | Pede uma execução do Actions, acompanha a publicação e lê o novo resultado. Requer configurar o serviço e a chave de atualização. |
| Pré-visualização sem credenciais permanentes | Mostra a recolha inicial e o diagnóstico; execução imediata e escritas partilhadas ficam explicitamente indisponíveis. |

O GitHub Pages serve ficheiros estáticos e não executa Python quando o visitante atualiza a página. Nunca colocar um token GitHub em `web/config.js` ou no navegador.

## Arranque no GitHub

1. Em **Settings → Pages → Build and deployment**, escolher **main / (root)** ou **GitHub Actions**. Em modo main, a entrada abre `web/`; ambos os modos leem a análise mais recente na branch `data`.
2. Abrir **Actions → Mister Mi — analisar e publicar → Run workflow** para a primeira execução, caso ainda não tenha ocorrido automaticamente.
3. A branch `data` guarda `consenso_hoje.json` e `history.json`. Cada execução recupera o histórico anterior antes de acrescentar registos.
4. O agendamento corre aos minutos 07 e 37 de cada hora UTC. O GitHub pode atrasar execuções; a página rejeita dados antigos em vez de os chamar atuais.
5. A primeira recolha pode terminar sem seleções. Consultar **Fontes** para distinguir filtros exigentes, dados em falta e falhas dos fornecedores.

Uma fonte bloqueada, alterada ou sem métricas não é contornada. O adaptador regista a falha e o filtro continua com a evidência disponível.

**Verificação real em 19/11/2026:** a primeira execução no GitHub Actions passou os testes e guardou a branch `data`. Forebet e PredictZ devolveram HTTP 403 nesse ambiente, enquanto OLBG respondeu e as tips ProTipster disponíveis não publicaram Tip Score. Não houve consenso suficiente. Isto é uma limitação de cobertura atual, não demonstração de que os jogos desse dia são bons ou maus. Os adaptadores funcionaram na recolha de desenvolvimento, mas isso não prova disponibilidade permanente nos runners do GitHub.

O painel identifica esta cobertura como parcial. Os adaptadores não constituem um calendário global de jogos: podem publicar apenas algumas seleções, incluir vários mercados do mesmo evento ou listar eventos de outros dias. Os contadores distinguem essas situações. A auditoria da expansão OLBG encontra-se em [COVERAGE_AUDIT.md](docs/COVERAGE_AUDIT.md).

## Atualização imediata e configurações partilhadas

O Worker de `worker/index.js` é um relay opcional. É possível executá-lo num serviço compatível com Cloudflare Workers; esta versão também tem empacotamento para Sites. O backend usa o GitHub como origem e persistência, sem credenciais no frontend.

Variáveis **do servidor**:

| Nome | Conteúdo |
|---|---|
| `GITHUB_REPOSITORY` | `juliomcm-tech/mister-mi` |
| `GITHUB_TOKEN` | Token limitado a este repositório com Contents: read/write e Actions: read/write. Guardar como secret do servidor. |
| `REFRESH_TOKEN` | Chave aleatória, diferente do token GitHub; autoriza o relay. |
| `ALLOWED_ORIGINS` | Origens HTTPS permitidas, separadas por vírgulas. A origem do serviço e `https://juliomcm-tech.github.io` já são aceites. |

Na variável de repositório `REFRESH_API_URL`, indicar `https://teu-servico.example/api`. Na página **Definições**, guardar a URL e a chave de atualização e ativar «Pedir nova análise ao abrir». A chave de atualização só permanece em `sessionStorage`; quando a sessão termina, é necessário reintroduzi-la.

O relay valida a origem e a chave; só pode pedir o workflow fixo, editar `config/settings.json` e acrescentar confirmações a `config/results.json`. Não oferece um proxy GitHub arbitrário. O cooldown de cinco minutos é por instância de execução, uma proteção básica; uma instalação pública com muitos utilizadores deve acrescentar um limitador persistente.

O botão de refresh pode demorar alguns minutos, porque espera pelo GitHub Actions. Não é streaming de cotações.

## Fontes opcionais e quota

`API_FOOTBALL_KEY` é um secret opcional do GitHub Actions. O plano gratuito tem limites de chamadas e épocas; não presumir cobertura de 2026 sem a verificar na conta. Por defeito o workflow consulta previsões de **um** candidato por execução (`API_FOOTBALL_MAX_FIXTURES=1`), além de fixtures e resultados. Ajustar a frequência/orçamento antes de aumentar este limite. A chave nunca aparece no JSON.

OpenLigaDB não requer chave. A liquidação gratuita está limitada às ligas e identidades verificadas; não constitui cobertura de resultados para todos os desportos. Respeita cooldown persistente de seis horas por recurso e recua após falhas.

## Desenvolvimento

Requisitos: Python 3.12+ e Node 22+. Sem dependências npm para a aplicação.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m consensus.cli
node scripts/dev.mjs
```

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.mjs
node --check web/app.js
node scripts/build.mjs --pages
```

`node scripts/build.mjs` gera um Worker ESM; `--pages` gera HTML/CSS/JS estáticos em `dist/`. A pasta `.openai` só identifica a pré-visualização alojada e não é necessária para GitHub Pages. `wrangler.jsonc` é uma opção de implantação, não uma subscrição necessária para recolha no GitHub.

## Regras e evolução

Os limiares estão em `config/settings.json`. Para excluir, por exemplo, ténis no Japão:

```json
{"excluded_combinations": [{"sport": "tennis", "country": "Japan"}]}
```

Os nomes de países são os valores canónicos da fonte, não a nacionalidade dos jogadores. Se o país do evento não for verificável, fica `Desconhecido`.

A pontuação é um índice editorial de concordância. Ainda não existe um modelo de probabilidades treinado e validado fora da amostra; por isso EV, Kelly e promessas de «segurança» estão desativados. Ver [arquitetura](docs/ARQUITETURA.md) e [avaliação das fontes gratuitas](docs/FONTES.md).

## Proveniência e direitos

Data from OpenLigaDB (www.openligadb.de), licensed under ODbL 1.0. Ver [licença](https://www.openligadb.de/en/license) e [condições de acesso](https://www.openligadb.de/en/terms-of-use). Os registos derivados de resultados OpenLigaDB conservam a atribuição e a licença nos metadados; a redistribuição dessa base está sujeita à ODbL.

As outras fontes conservam os seus direitos e condições de utilização. O projeto não inclui páginas completas de terceiros, logótipos de clubes, software de contorno de bloqueios ou dados sintéticos apresentados como reais. O avatar Mister Mi é um asset original gerado para este projeto.
