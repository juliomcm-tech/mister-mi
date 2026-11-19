import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.js';

test('reading the public analysis performs only reads and preserves degraded source evidence',async()=>{
 const previous=globalThis.fetch,calls=[];
 const snapshot={date:'2026-11-19',updated_at:'2026-11-19T16:15:42Z',status:'partial',data:[],sources:[{id:'olbg',status:'ok',collected:169},{id:'forebet',status:'error',message:'HTTP 403'}]};
 globalThis.fetch=async(input,options={})=>{calls.push({url:String(input),method:options.method??'GET'});return new Response(JSON.stringify(snapshot),{status:200,headers:{'Content-Type':'application/json'}});};
 try{
  const response=await worker.fetch(new Request('https://mi.example/api/today'),{});
  assert.equal(response.status,200);
  assert.deepEqual(await response.json(),snapshot);
  assert.ok(calls.length>0);
  assert.ok(calls.every(call=>call.method==='GET'));
  assert.ok(calls.every(call=>!call.url.includes('/dispatches')));
  assert.match(response.headers.get('Cache-Control'),/no-store/);
 }finally{globalThis.fetch=previous;}
});

test('an unavailable public feed marks a bundled snapshot as fallback',async()=>{
 const previousFetch=globalThis.fetch,previousAssets=globalThis.STATIC_ASSETS;
 globalThis.fetch=async()=>{throw new TypeError('offline');};
 globalThis.STATIC_ASSETS={'/data/consenso_hoje.json':{body:JSON.stringify({date:'2026-11-18',updated_at:'2026-11-18T12:00:00Z',data:[],sources:[]})}};
 try{
  const response=await worker.fetch(new Request('https://mi.example/api/today'),{});
  const result=await response.json();
  assert.equal(result.snapshot_fallback,true);
  assert.equal(result.date,'2026-11-18');
  assert.match(response.headers.get('Cache-Control'),/no-store/);
 }finally{globalThis.fetch=previousFetch;if(previousAssets===undefined)delete globalThis.STATIC_ASSETS;else globalThis.STATIC_ASSETS=previousAssets;}
});
