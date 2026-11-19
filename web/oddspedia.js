// Only public connection metadata reaches the browser. Credentials stay in Actions.
export function oddspediaView(feed, now = Date.now()) {
 if (!feed || feed.configured !== true) return {label:'A aguardar configuração',level:'pending',message:'A próxima recolha verifica o Secret ODDSPEDIA_FEED_URL no GitHub.',attribution:false};
 const checked = Date.parse(feed.checked_at), age = now - checked;
 if (!Number.isFinite(checked) || age < -60000 || age > 60 * 60000) return {label:'É necessária nova verificação',level:'pending',message:'O estado da API ainda não foi confirmado numa recolha recente.',attribution:feed.status==='ok'};
 if (feed.status === 'empty') return {label:'Sem registos no pedido',level:'pending',message:feed.message || 'O pedido não devolveu dados.',attribution:feed.catalogue?.status==='ok'};
 if (feed.status === 'partial') return {label:feed.reason==='catalogue_only'?'Catálogo recebido':'Pesquisa por confirmar',level:'pending',message:feed.message || 'A leitura dos jogos ainda não foi confirmada.',attribution:feed.catalogue?.status==='ok'};
 if (feed.status !== 'ok') return {label:feed.reason==='invalid_configuration'?'Rever o Secret no GitHub':'Ligação por confirmar',level:'error',message:feed.message || 'A API não respondeu com dados válidos nesta recolha.',attribution:false};
 const count = Number.isSafeInteger(feed.records_received) && feed.records_received >= 0 ? `${feed.records_received} registos recebidos. ` : '';
 return {label:'A API respondeu',level:'ok',message:count+(feed.message || 'O formato recebido ainda está em validação.'),attribution:true};
}
