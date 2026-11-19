import test from 'node:test';
import assert from 'node:assert/strict';
import {operationState,canStartCollection} from '../web/operation.js';
test('reloading a publication never claims to start a collection without a verified relay',()=>{
 assert.equal(canStartCollection({apiBase:'https://example.org/api'},'key',null),false);
 assert.equal(canStartCollection({apiBase:'https://example.org/api'},'key',{configured:false}),false);
 assert.equal(canStartCollection({apiBase:'https://example.org/api'},'key',{configured:true}),true);
 assert.equal(operationState(null).refreshLabel,'Recarregar dados');
});
test('successful data reads and cron declarations do not conceal degraded or expired sources',()=>{
 const now=Date.parse('2026-11-19T17:00:00Z');
 const p={updated_at:'2026-11-19T16:50:00Z',sources:[{status:'ok'},{status:'error'}],pipeline_health:{scheduler_status:'not_observed'}};
 const view=operationState(p,{now});assert.equal(view.level,'partial');assert.equal(view.scheduler,'not_observed');
 assert.equal(operationState({...p,updated_at:'2026-11-19T15:00:00Z'},{now}).level,'stale');
});
