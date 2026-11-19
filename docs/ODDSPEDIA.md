# Oddspedia: verificação da opção gratuita

Verificado na documentação pública oficial em 19/11/2026.

A [página para publishers](https://widgets.oddspedia.com/) anuncia widgets e
API de dados gratuitos, incluindo calendários, resultados e comparação de odds.
A FAQ exige registo para aceder ao painel e às opções de integração.

O [acordo de utilização](https://widgets.oddspedia.com/terms) estabelece que cada
widget tem de ser criado na conta do webmaster e associado ao domínio onde é
utilizado. As [obrigações de atribuição](https://widgets.oddspedia.com/obligations)
exigem logótipo, texto visível “Data powered by Oddspedia” e ligação nofollow
no rodapé. Os detalhes de API e o código da conta devem ser obtidos no painel;
não foram inventadas chaves, widgets ou endpoints privados nesta integração.

## Configurar o widget na app

1. Na conta Oddspedia, criar o widget e configurar o domínio de utilização.
   No GitHub Pages: `juliomcm-tech.github.io`. A app mostra o domínio real em
   Ajustes, incluindo quando é aberta na publicação privada alternativa.
2. Na app, abrir **Ajustes → Oddspedia**, colar o código completo de incorporação
   (HTML / JavaScript) e escolher **Guardar e abrir widget**.
3. Consultar o painel no separador **Fontes**. A altura é ajustável para mostrar
   o widget completo. A própria Oddspedia determina a disponibilidade e valida
   a configuração da conta/domínio. A mensagem de código guardado não certifica
   que o fornecedor carregou o conteúdo ou aprovou esse domínio.

O código é guardado apenas no armazenamento local deste dispositivo e origem.
Não é publicado no GitHub nem sincronizado entre dispositivos. Não precisa de
GitHub Secret. Chaves reais de API não devem ser coladas neste campo; pertencem
à recolha no servidor/GitHub Actions, com a documentação de acesso do fornecedor.
Não houve criação de conta ou aceitação de contrato em nome do utilizador.

O código original é executado num iframe isolado, sem `allow-same-origin` ou
navegação da janela principal. Uma CSP permite scripts e recursos apenas nos
domínios Oddspedia, além de estilos locais e imagens/fontes data. Assim, código
colado não recebe acesso ao DOM ou ao armazenamento do Mister Mi. O iframe só
existe quando Fontes está aberto e é removido ao sair, reduzindo atividade em
segundo plano. A atribuição oficial fica visível no rodapé de todos os
separadores enquanto houver um widget configurado. Remover o widget elimina a
configuração local e desmonta o conteúdo.

O formato real da conta ainda precisa de ser colado pelo proprietário e
verificado. Se depender de acesso ao DOM do site principal, domínios adicionais
ou requisitos de autenticação, será necessário adaptar a incorporação com base
na documentação/código oficial, sem enfraquecer o isolamento da app.

Odds e calendários têm funções diferentes das previsões: não entram como uma
fonte adicional de consenso apenas por serem provenientes de outra API.
O widget é exclusivamente de consulta e não alimenta o motor Python; esse
passo requer um feed/API autorizado, com formato e condições confirmados.
