import test from 'node:test';
import assert from 'node:assert/strict';
import {oddspediaView} from '../web/oddspedia.js';
const now=Date.parse('2026-11-19T20:00:00Z');
const feed={configured:true,status:'ok',checked_at:'2026-11-19T19:50:00Z',records_received:12,message:'Formato recebido em validação.'};
test('missing configuration and API errors never appear as a verified connection',()=>{
 assert.equal(oddspediaView(null,now).level,'pending');
 assert.equal(oddspediaView({...feed,configured:false},now).attribution,false);
 const failure=oddspediaView({...feed,status:'error',reason:'invalid_configuration',message:'URL inválido.'},now);
 assert.equal(failure.level,'error');assert.equal(failure.label,'Rever o Secret no GitHub');assert.equal(failure.message,'URL inválido.');assert.equal(failure.attribution,false);
});
test('only a recent successful response is shown as received, without claiming an analysis',()=>{
 const view=oddspediaView(feed,now);assert.equal(view.level,'ok');assert.equal(view.attribution,true);assert.match(view.message,/12 registos/);assert.match(view.message,/validação/);
 for(const date of ['bad','2026-11-19T18:00:00Z','2026-11-20T20:00:00Z'])assert.equal(oddspediaView({...feed,checked_at:date},now).level,'pending');
 assert.ok(!oddspediaView({...feed,records_received:-1},now).message.includes('-1'));
});
test('empty responses and catalogue-only access stay distinct from a refusal',()=>{
 const empty=oddspediaView({...feed,status:'empty',message:'Empty data',catalogue:{status:'ok'}},now);
 assert.equal(empty.label,'Sem registos no pedido');assert.equal(empty.level,'pending');assert.equal(empty.attribution,true);
 const catalogue=oddspediaView({...feed,status:'partial',reason:'catalogue_only',catalogue:{status:'ok'}},now);
 assert.equal(catalogue.label,'Catálogo recebido');assert.equal(catalogue.level,'pending');
 const refused=oddspediaView({...feed,status:'error',http_status:403,message:'HTTP 403'},now);
 assert.equal(refused.level,'error');assert.equal(refused.attribution,false);
});
test('provider challenge is explicit and a deferred retry never claims a fresh success',()=>{
 const challenged={...feed,status:'error',reason:'provider_challenge',message:'É exigida uma verificação de navegador.'};
 assert.equal(oddspediaView(challenged,now).label,'Verificação exigida');
 const deferred=oddspediaView({...challenged,deferred:true,next_check_at:'2026-11-20T01:50:00Z'},now);
 assert.equal(deferred.label,'Nova tentativa em pausa');assert.equal(deferred.level,'pending');assert.equal(deferred.attribution,false);
 assert.match(deferred.message,/Lisboa/);
});
