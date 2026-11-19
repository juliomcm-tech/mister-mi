# Auditoria da ligação da app — 19/11/2026

Verificação independente das ligações e do agendamento, às **17:05 UTC / Lisboa**,
antes das correções propostas nesta auditoria. Não foram lidos tokens, segredos,
sessões do navegador ou credenciais privadas. Não foram alterados o workflow,
o frontend, o Worker ou as definições de produção pelo auditor.

## Resultado principal

A leitura da publicação funciona. **O refresh da instalação pública não executa
uma recolha nova**, e não foi observada qualquer execução agendada. A cobertura
das fontes está degradada. Estes três estados precisam de ser apresentados
separadamente; um pedido HTTP bem sucedido não demonstra uma análise completa.

| Verificação pública | Observação às 17:05 |
| --- | --- |
| `web/config.js` no Pages | HTTP 200; `apiBase` vazio |
| JSON na branch `data`, leitura sem query | HTTP 200; recolha de 16:15:42 |
| Mesmo JSON, query de timestamp e `Cache-Control: no-cache` | Mesmo conteúdo e ETag |
| JSON obtido pelo conector GitHub | Mesma recolha de 16:15:42 |
| Política de cache do raw GitHub | `max-age=300`; CORS público |
| Idade dessa recolha às 17:05 | Aproximadamente 50 minutos; superior ao limite de 45 |
| Workflow de análise | `active`, ficheiro na branch predefinida `main` |
| Execuções registadas | 9 por `push`, 8 de publicação Pages |
| Execuções com evento `schedule` | 0 |
| Execuções com evento `workflow_dispatch` | 0 |

Portanto, neste instante, ocultar opções antigas é o comportamento esperado.
O upstream atual estava antigo; não foi demonstrada uma falha do service worker
nem uma versão mais recente disponível que o navegador estivesse a esconder.

O workflow ativo tem ID `423937058`, criado às 14:23:04. O repositório é público,
foi criado às 13:51:56 do mesmo dia, tem branch predefinida `main` e não está
arquivado ou desativado. O agendamento declarado era `7,37 * * * *`.

## O que o refresh faz

`refreshAnalysis()` só pede uma execução quando existem **ambos** `apiBase` e uma
chave de atualização da sessão. Sem esses valores, recarrega o JSON publicado.
O frontend já informa esta diferença depois do clique, mas o rótulo inicial
«Analisar o dia» e o estado temporário «Mister Mi a analisar» podem sugerir uma
recolha que não foi pedida.

O Worker opcional exige credenciais no servidor e uma chave da sessão para
escritas. A leitura pública não precisa dessas credenciais. Não foi inspecionada
a configuração privada de um serviço nem a ligação local guardada no telefone;
a constatação de `apiBase` vazio refere-se à configuração pública servida pelo Pages.

O service worker guarda apenas a interface e não interceta o raw GitHub
cross-origin. Os pedidos de dados do frontend usam `cache: no-store` e uma query
de timestamp. Dados e histórico não pertencem à cache offline. O Worker marca
explicitamente uma cópia inicial com `snapshot_fallback: true` quando o upstream
falha; o frontend não deve apresentar essa cópia como análise atual.

## Fontes realmente disponíveis na última execução

| Fonte | Registos normalizados | Estado observado |
| --- | ---: | --- |
| OLBG | 169 | Disponível; uma previsão apta para hoje |
| Forebet | 0 | HTTP 403 nas cinco páginas tentadas |
| ProTipster | 6 | Sem Tip Score público; não contribuem para o consenso |
| PredictZ | 0 | HTTP 403 |
| API-Football | 0 | Não configurada |

O JSON tinha `status: "ok"` porque o CLI só usa `error` quando todas as fontes
estão em erro ou não configuradas. Esse campo atualmente significa que houve
alguma recolha, não que existam fontes independentes suficientes. O painel
mostra cobertura parcial, mas recomenda-se um estado global explícito de
degradação separado do sucesso do transporte e da conclusão do job.

São configurados **cinco desportos**, não todos: futebol, ténis, basquetebol,
hóquei no gelo e futebol americano. O código tenta páginas Forebet para futebol,
ténis, basquetebol e hóquei; por isso a afirmação da imagem «Forebet só cobre
futebol» não descreve o comportamento deste código. Isto não prova que todas
essas páginas estejam disponíveis no GitHub: nesta execução devolveram 403.

## Agendamento: o que está provado e o que falta provar

A documentação oficial do GitHub indica que cron executa a versão da branch
predefinida e pode sofrer atrasos ou perder execuções em carga elevada. A
desativação após 60 dias de inatividade não explica um repositório criado nesse
dia. Um workflow `active` também não prova que o cron tenha disparado.

Não foi identificada a causa exata da ausência de eventos agendados. É
razoável rever ou voltar a registar o cron mantendo a frequência e acompanhar
um evento real `schedule`; não se deve declarar o problema resolvido apenas
porque o YAML é válido ou uma execução por `push` concluiu com sucesso.

A documentação também descreve paragem do cron associada à conta do ator e
re-registo ao editar a expressão, mas **não foi encontrada evidência de que
essa seja a causa neste repositório**. Não são necessárias alterações de
credenciais nem aumentos de permissões para concluir a auditoria de leitura.

## Correções recomendadas ao autor

1. Identificar o botão sem relay como «Recarregar dados publicados» e oferecer
   a ligação à execução manual no GitHub. Reservar «Executar nova recolha» para
   uma ligação ao servidor que realmente tenha capacidade de a pedir.
2. Mostrar idade da recolha, cobertura degradada e origem do último evento.
   Tornar visível que sucesso do job não implica consenso ou cobertura completa.
3. Registar `github.event_name` e o instante da execução no JSON. Confirmar
   pelo menos um evento `schedule` antes de anunciar atualização automática
   operacional. Não usar commits artificiais de manutenção como substituto.
4. Preservar o limite de frescura e as falhas das fontes; alargar acesso apenas
   através de fontes autorizadas e utilizáveis, sem contornar recusas.

## Referências e reprodução

- [Última execução observada](https://github.com/juliomcm-tech/mister-mi/actions/runs/44564013094).
- [Código auditado](https://github.com/juliomcm-tech/mister-mi/tree/1edc9aa0e3d0c58bac51063a7c740d5d3ca6fa06).
- [Eventos e agendamento — documentação oficial](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
- [Diagnóstico de workflows — documentação oficial](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows#scheduled-workflow-stopped-running).

Foram consultados `GET /actions/runs?per_page=100`,
`GET /actions/runs?event=schedule&per_page=10`, metadados públicos do repositório
e `GET /actions/workflows/423937058`. O conector rejeitou o último endpoint por
limitação de formatos de URL; os metadados foram então lidos na API pública
oficial, sem autenticação. A lista de ferramentas não expunha operações de
dispatch ou ativação; existe uma operação de reexecução de um job existente.
Não foi efetuada qualquer mutação externa pelo auditor.

Dois testes de contrato em `tests/test_connection_audit.mjs` verificam que ler
uma análise só efetua leituras e preserva os erros das fontes, e que uma cópia
inicial após falha é marcada como fallback. Estes testes não demonstram a
disponibilidade de fontes externas nem o funcionamento do agendamento.
