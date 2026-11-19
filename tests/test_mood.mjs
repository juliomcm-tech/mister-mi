import test from 'node:test';
import assert from 'node:assert/strict';
import {getAnalystMood} from '../web/mood.js';
test('unmeasured or insufficient performance never invents a bad mood',()=>{
 assert.equal(getAnalystMood(null).state,'neutral');
 assert.equal(getAnalystMood({overall:{settled:29,priced_settled:29,odds_coverage:100,paper_roi_pct:-90}}).state,'neutral');
 assert.equal(getAnalystMood({overall:{settled:100,priced_settled:30,odds_coverage:30,paper_roi_pct:-90}}).state,'neutral');
});
test('only supported negative production ROI triggers review',()=>{
 const overall={settled:40,priced_settled:40,odds_coverage:100,paper_roi_pct:-15};
 assert.equal(getAnalystMood({overall}).state,'review');
 assert.equal(getAnalystMood({overall:{...overall,paper_roi_pct:5}}).state,'neutral');
 assert.equal(getAnalystMood({overall:{...overall,paper_roi_pct:NaN}}).state,'neutral');
});
test('experimental benchmark results are never treated as production history',()=>{
 assert.equal(getAnalystMood({experimental_backtest:{settled:300,priced_settled:300,odds_coverage:100,paper_roi_pct:-50}}).state,'neutral');
});
