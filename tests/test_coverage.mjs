import test from 'node:test';
import assert from 'node:assert/strict';
import {coverageView,visibleWatchlist} from '../web/coverage.js';
const now=Date.parse('2026-11-19T12:00:00Z');
const candidate={sport:'football',country:'Portugal',match:'Porto vs Benfica',kickoff:'2026-11-19T20:00:00Z',status:'awaiting_independent_source',is_recommendation:false};
test('coverage distinguishes forecasts, matches, eligible evidence and unavailable providers',()=>{
 const view=coverageView({total_collected:100,total_selected:0,sources:[{id:'olbg',status:'ok'},{id:'protipster',status:'partial'},{id:'forebet',status:'error'}],diagnostics:{today_forecasts:40,today_events:24,eligible_forecasts:3,by_source:[{id:'olbg',eligible:3},{id:'protipster',eligible:0}],threshold_reasons:{missing_metric:4}}});
 assert.deepEqual(view.metrics.map(([,n])=>n),[100,40,24,3,0]);assert.equal(view.usable,1);assert.equal(view.unavailable,1);assert.deepEqual(view.reasons,[['Métrica pública em falta',4]]);
 assert.equal(coverageView({}),null);
});
test('watchlist never displays another day, started games or recommendations mislabelled as candidates',()=>{
 const snapshot={date:'2026-11-19',watchlist:[candidate,{...candidate,kickoff:'2026-11-19T12:04:00Z'},
   {...candidate,kickoff:'2026-11-20T20:00:00Z'},{...candidate,kickoff:'2026-11-19T20:00:00'},
   {...candidate,is_recommendation:true}]};
 assert.deepEqual(visibleWatchlist(snapshot,{today:'2026-11-19',now}),[candidate]);
 assert.deepEqual(visibleWatchlist(snapshot,{today:'2026-11-20',now}),[]);
});
test('candidate list respects device exclusions and sport selection',()=>{
 const snapshot={date:'2026-11-19',watchlist:[candidate]};
 for(const preferences of [{excluded_sports:['football']},{excluded_countries:['Portugal']},{excluded_combinations:[{sport:'football',country:'Portugal'}]}])
   assert.deepEqual(visibleWatchlist(snapshot,{today:snapshot.date,now,preferences}),[]);
 assert.deepEqual(visibleWatchlist(snapshot,{today:snapshot.date,now,sport:'tennis'}),[]);
});
