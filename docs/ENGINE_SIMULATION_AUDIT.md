# Auditoria do motor, cobertura e simulações de regras

Auditoria independente do autor das alterações visuais. Data: **19/11/2026**,
com replay de um snapshot às **16:10:18 UTC/Lisboa** e uma nova recolha pública
OLBG às **17:07:50 UTC/Lisboa**. Não foram alterados o motor de produção,
as definições ou os adaptadores nesta auditoria.

## Conclusão verificável

O motor processa as previsões recebidas nos cinco desportos configurados:
futebol, ténis, basquetebol, hóquei no gelo e futebol americano. Isto não
constitui cobertura de todos os desportos nem de todos os jogos desses cinco
desportos. A unidade recolhida é uma previsão publicada por uma fonte; não é
um calendário global de eventos.

A única comunidade OLBG, mesmo com mais páginas ou mais previsões, continua
a contar como uma fonte. Uma seleção exige duas fontes independentes com
identidade, mercado e escolha compatíveis. Assim, uma falha de acesso à outra
fonte impede o consenso mesmo quando há candidatos que passam os limiares.

## Nova recolha permitida: 17:07:50

Foram consultadas apenas as cinco páginas públicas OLBG já configuradas,
respeitando o cliente e o robots.txt do projeto. Não se tentou ler Forebet ou
PredictZ por outra rede, proxy, rota ou identidade após a recusa observada no
GitHub.

| Página OLBG | Linhas públicas | Inativas | Mercado sem suporte | Normalizadas |
| --- | ---: | ---: | ---: | ---: |
| Futebol | 100 | 0 | 1 | 99 |
| Ténis | 11 | 5 | 3 | 3 |
| Basquetebol | 32 | 14 | 0 | 18 |
| Hóquei no gelo | 38 | 4 | 9 | 25 |
| Futebol americano | 21 | 0 | 0 | 21 |
| **Total** | **202** | **23** | **13** | **166** |

As linhas inativas e os mercados sem suporte são excluídos antes da análise de
votos. A normalização não converte uma previsão de outro dia numa oportunidade
para hoje. A classificação acima usa os dados públicos da própria resposta;
não estima quantos jogos ou mercados não foram publicados nessa página.

| Data dos jogos | Previsões normalizadas dessa data | Aptas na fonte | Com consenso independente |
| --- | ---: | ---: | ---: |
| 19/11 | 23 | 2 | 0 |
| 20/11 | 63 | 1 | 0 |
| 21/11 | 49 | 3 | 0 |

Nesta nova recolha, os dois sinais aptos de hoje repartem-se entre ténis e
basquetebol. Isso difere do snapshot anterior, que tinha apenas um sinal apto
em ténis. Os dados, votos e estados dos jogos mudam entre recolhas.

### Amanhã por desporto

| Desporto | Previsões de 20/11 | Menos de 15 votos | Apoio abaixo de 75% | Aptas |
| --- | ---: | ---: | ---: | ---: |
| Futebol | 37 | 36 | 0 | 1 |
| Basquetebol | 8 | 8 | 0 | 0 |
| Hóquei no gelo | 15 | 15 | 0 | 0 |
| Ténis | 2 | 2 | 0 | 0 |
| Futebol americano | 1 | 0 | 1 | 0 |
| **Total** | **63** | **61** | **1** | **1** |

Portanto, a única opção de amanhã não resulta de o motor ter ignorado os
outros quatro desportos: existem previsões nesses desportos no input, mas
nenhuma passa o filtro OLBG nesse instante. Isto não demonstra que sejam más
apostas nem que uma política diferente seja rentável. Mostra falta de volume
de votos e de confirmações nas fontes atualmente utilizáveis.

## Replay e sensibilidade, sem afinação automática

O script `scripts/audit_coverage.py` aceita um snapshot de previsões com o seu
relógio original ou uma nova leitura pública OLBG. O replay preserva
`fetched_at` e avalia no `observed_at` guardado. Não modifica timestamps para
tornar dados antigos recentes, nem escreve definições de produção.

O snapshot de 16:10 tinha 169 previsões normalizadas, 27 para hoje, 62 para
amanhã e 49 para sábado. Os sinais aptos eram 1, 1 e 3, respetivamente. O
novo snapshot teve mais uma previsão de hóquei de amanhã e menos eventos
ativos de hoje, explicando as diferenças acima.

Foram executados 12 cenários de diagnóstico: mínimos de 5, 10, 15 e 20 votos,
com apoio mínimo de 65%, 75% e 85%. O mínimo de duas fontes permaneceu em vigor.
Estes cenários não usam resultados dos jogos e não estimam taxa de sucesso.

| Regras comparadas na recolha das 17:07 | Aptas hoje | Aptas amanhã | Aptas sábado | Consensos nos três dias |
| --- | ---: | ---: | ---: | ---: |
| Produção: 15 votos, 75% | 2 | 1 | 3 | 0 |
| Diagnóstico: 5 votos, 65% | 17 | 15 | 18 | 0 |

Reduzir o limiar aumenta a quantidade de sinais da mesma comunidade; não cria
uma fonte independente. Os cenários mais permissivos não foram aplicados à
app nem demonstram melhoria do modelo.

As simulações artificiais, identificadas no JSON como `synthetic_rule_checks`,
confirmam que duas fontes concordantes podem produzir uma seleção, que a perda
da segunda fonte elimina a seleção e que cinco páginas da mesma fonte não
contam como cinco confirmações. Conflitos, datas diferentes e recolhas antigas
também mantêm a seleção a zero. São verificações de regras, não jogos reais.

## Conferência da imagem fornecida

A imagem foi tratada como uma afirmação a verificar, sem lhe atribuir uma
proveniência que não está preservada. Os valores das fontes e os jogos da
imagem não ficam verificados apenas por recalcular a fórmula.

A função `score_tips` da primeira implementação guardada no commit
[`6805ebc`](https://github.com/juliomcm-tech/mister-mi/blob/6805ebc048374053387dbf6ecc44abf8b80f8035/consensus/core.py)
usa a mesma fórmula observada na versão atual: 50 + 12 por fonte adicional,
mais 0,12 vezes a média das métricas, mais até 8 por volume OLBG, com teto 98.
Com métricas válidas, o máximo com duas fontes é **82**, e com três é **94**.
O teto 98 não transforma qualquer par ou trio de fontes num score de 98.

| Linha da imagem | Score na imagem | Recalculado com as métricas apresentadas |
| --- | ---: | ---: |
| Benfica Women vs AS Roma Women | 96,1 | 89,1 |
| Arsenal Women vs OL Lyonnes | 95,5 | 89,4 |
| Ben Shelton vs Rafael Jodar | 97,5 | 77,2 |
| Boston Celtics vs LA Lakers | 97,0 | 79,0 |

Logo, esses quatro scores não são saídas da fórmula documentada nos commits
verificados. A auditoria não permite estabelecer de onde vieram esses valores
nem afirmar o que ocorreu numa execução não preservada. Também não confirma
os Tip Scores, percentagens ou jogos da imagem sem evidência primária datada.
O rodapé da imagem dizendo que Forebet só cobre futebol não descreve os
adaptadores atuais, que incluem também ténis, basquetebol e hóquei.

## Reprodução e limites

```bash
../.venv/bin/python scripts/audit_coverage.py --snapshot ../research/mi-future-live-audit.json
../.venv/bin/python scripts/audit_coverage.py --live-olbg
../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

O snapshot indicado é um ficheiro interno da sessão, não uma dependência
incluída no repositório. Qualquer snapshot com `observed_at`, `tips` compatíveis
com `Tip` e metadados opcionais `sources` pode ser reproduzido. Sem snapshot,
`--live-olbg` consulta apenas as páginas públicas permitidas. `--settings`
permite indicar outra cópia das definições; por defeito lê `config/settings.json`.

A verificação integrada mais recente aprovou **72 testes Python e 41 testes
Node**, incluindo três novos testes desta auditoria sobre perda de fontes,
incompatibilidade dos scores e separação das simulações das definições de
produção. Os totais incluem também verificações acrescentadas pelos outros
agentes em paralelo. Não foram avaliados
resultados históricos adicionais nem calculados ROI, probabilidades calibradas
ou promessas de segurança financeira.
