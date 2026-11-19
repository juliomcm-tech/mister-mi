# BetClan: uma nova fonte de previsões, com limites explícitos

Foi consultada a [FAQ oficial](https://www.betclan.com/faq/), que declara o
serviço gratuito e permite a partilha das previsões. A recolha respeita o
robots.txt e não acede a `/viewbetclan/`, não requer autenticação, não executa
JavaScript e não repete as fontes recusadas através de outras redes.

## O que é analisado

O adaptador lê cinco índices públicos de hoje e os índices futuros publicados
na navegação desses índices: futebol, ténis, basquetebol, hóquei e futebol
americano. Só segue URLs HTTPS do domínio exato `www.betclan.com`. O ano, a
data completa, os participantes e os horários explícitos vêm dos eventos
publicados. As ligações com caracteres Unicode são codificadas como URLs.

Um índice de eventos não contém as previsões do modelo. Por isso o adaptador
publica separadamente o número de eventos indexados e o número de detalhes
efetivamente consultados. Por execução, consulta no máximo 24 detalhes para
jogos já encontrados nas outras fontes, com prioridade para sinais que já
passam os limiares e com horário e participantes compatíveis. A lista do índice
não é apresentada como se todos os seus jogos tivessem sido analisados.

Só o bloco `.partone` do modelo é lido; o bloco Users Average não contribui.
A métrica é a percentagem publicada para a seleção escolhida, nunca o maior
número de uma distribuição nem uma odd. Distribuições devem ter dois ou três
resultados, valores entre 0 e 100 e soma próxima de 100. Mercados de vencedor,
totais de futebol 2.5 e ambas marcam são normalizados apenas quando explícitos.
Hóquei com dois resultados e âmbito de prolongamento ambíguo fica excluído.

Há páginas cujo índice e detalhe usam offsets UTC contraditórios. Quando a
data local coincide mas os instantes diferem mais de 20 minutos, o prognóstico
fica sem `kickoff`: pode corroborar uma fonte com início verificado, mas não é
uma âncora temporal independente. Datas locais contraditórias, cancelamentos,
participantes divergentes e URLs fora do âmbito são recusados.

O mínimo de 65% é o mesmo critério já aplicado aos outros modelos publicados.
Não demonstra calibração ou rentabilidade. A seleção continua a exigir duas
fontes distintas, mesmo mercado, mesma seleção e os restantes filtros.

## Resultado da primeira verificação ao vivo

Uma execução de desenvolvimento de 19/11/2026 leu 1267 eventos nos índices e
24 detalhes, obtendo 20 previsões normalizadas. O conjunto OLBG + BetClan
produziu três consensos do dia: Alexander Zverev vs Arthur Fils, Milano vs
Fenerbahce e Bayern Munich vs Baskonia. Para 20/11, Bayern Munich vs Cologne
passou; para 21/11, Man City vs Fulham passou. Estes valores são um snapshot,
não um total fixo nem promessa de execução no GitHub. A publicação e o estado
dos fornecedores devem ser verificados na execução real do runner.

As definições 15 votos, 75% OLBG, 65% dos modelos e duas fontes não foram
reduzidas para produzir estes resultados. Um calendário OpenLigaDB separado
acrescenta verificação do evento apenas no seu âmbito; não acrescenta um voto.

## Atualização

O workflow mantém duas execuções previstas por hora, agora aos minutos 13 e 43.
Os relatórios incluem `pipeline_health`, que distingue configuração ativa de
execuções agendadas realmente observadas. Não se afirma que um agendamento
funciona apenas porque uma execução por alteração de código terminou.

Sem relay verificado, a interface diz **Recarregar dados** e oferece a ligação
ao workflow para executar o motor. Um token permanente não é colocado no
navegador. A ausência dessa ligação é uma limitação funcional explícita.
