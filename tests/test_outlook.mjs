import test from 'node:test';
import assert from 'node:assert/strict';
import {futureDate,outlookState,outlookCandidates} from '../web/outlook.js';
const now=Date.parse('2026-11-19T12:00:00Z');
const preview={date:'2026-11-20',day_offset:1,is_preview:true,analysis_mode:'future_preview',updated_at:new Date(now).toISOString(),diagnostics:{today_forecasts:0,today_events:0},total_eligible:0,total_consensus_candidates:0,candidates:[],watchlist:[]};
const payload={date:'2026-11-19',updated_at:preview.updated_at,previews:[preview]};
test('future dates use the current Lisbon calendar across DST and year boundaries',()=>{
 assert.equal(futureDate(1,now),'2026-11-20');assert.equal(futureDate(2,now),'2026-11-21');
 assert.equal(futureDate(1,Date.parse('2026-07-01T23:05:00Z')),'2026-07-03');
 assert.equal(futureDate(2,Date.parse('2026-12-31T22:00:00Z')),'2027-01-02');
 assert.equal(futureDate(3,now),'');
});
test('absence of published future data is distinguished from a valid zero-candidate snapshot',()=>{
 assert.equal(outlookState(payload,1,{now}).valid,true);
 assert.equal(outlookState({...payload,previews:[]},1,{now}).valid,false);
 assert.equal(outlookState(payload,2,{now}).valid,false);
 assert.equal(outlookState({...payload,previews:[{...preview,is_preview:false}]},1,{now}).valid,false);
 assert.equal(outlookState({...payload,previews:[{...preview,diagnostics:{}}]},1,{now}).valid,false);
 assert.equal(outlookState({...payload,previews:{}},1,{now}).valid,false);
});
test('previews cannot survive the collection age limit or midnight with yesterday data',()=>{
 assert.equal(outlookState(payload,1,{now:now+46*60000}).valid,false);
 assert.equal(outlookState(payload,1,{now:now+86400000}).valid,false);
 assert.equal(outlookState({...payload,updated_at:'2026-11-20T12:00:00Z'},1,{now}).valid,false);
 assert.equal(outlookState({...payload,previews:[{...preview,updated_at:'2026-11-18T12:00:00Z'}]},1,{now}).valid,false);
});
test('candidate display respects exact target date, explicit preview status and device filters',()=>{
 const pick={status:'preliminary_consensus',is_recommendation:false,kickoff:'2026-11-20T20:00:00Z',sport:'football',country:'Portugal',odds:1.8};
 const snapshot={...preview,candidates:[pick,{...pick,kickoff:'2026-11-21T20:00:00Z'},{...pick,is_recommendation:true}]};
 assert.deepEqual(outlookCandidates(snapshot,{now}).confirmed,[pick]);
 for(const preferences of [{excluded_sports:['football']},{excluded_combinations:[{sport:'football',country:'Portugal'}]},{min_odds:2}])
   assert.deepEqual(outlookCandidates(snapshot,{now,preferences}).confirmed,[]);
});
