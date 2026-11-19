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
