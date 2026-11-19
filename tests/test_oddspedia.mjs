import test from 'node:test';
import assert from 'node:assert/strict';
import {validateWidgetCode, widgetDocument, widgetHeight, createWidgetFrame, initOddspediaWidget, WIDGET_CSP} from '../web/oddspedia.js';

// Public demo URL, used only to exercise the embed boundary; no model data.
const code = '<iframe src="https://widgets.oddspedia.com/demo/standings"></iframe>';

test('accepts complete provider embeds, rejects keys and lookalike domains', () => {
 assert.equal(validateWidgetCode(`  ${code}\n`), code);
 assert.equal(validateWidgetCode('<div></div><script src="https://widgets.oddspedia.com/"></script>').includes('<script'), true);
 for (const value of ['', 'a-long-api-token', '<iframe src="javascript:alert(1)"></iframe>', '<iframe src="https://widgets.oddspedia.com.evil.example/"></iframe>', '<iframe src="https://widgets.oddspedia.com@evil.example/"></iframe>']) assert.throws(() => validateWidgetCode(value));
 assert.throws(() => validateWidgetCode(code + 'x'.repeat(256 * 1024)), /256 KB/);
});

test('isolates provider scripts and restricts network destinations', () => {
 const attributes = {};
 const frame = createWidgetFrame({createElement: tag => ({tag, style:{}, setAttribute:(k,v) => attributes[k] = v})}, code, 760);
 assert.equal(frame.tag, 'iframe');
 assert.equal(frame.style.height, '760px');
 assert.ok(attributes.sandbox.split(' ').includes('allow-scripts'));
 assert.ok(!attributes.sandbox.includes('allow-same-origin'));
 assert.ok(!attributes.sandbox.includes('allow-top-navigation'));
 assert.equal(attributes.referrerpolicy, 'strict-origin-when-cross-origin');
 assert.ok(frame.srcdoc.indexOf('Content-Security-Policy') < frame.srcdoc.indexOf(code));
 assert.ok(frame.srcdoc.includes(code));
 assert.match(WIDGET_CSP, /default-src 'none'/);
 assert.match(WIDGET_CSP, /object-src 'none'; base-uri 'none'; form-action 'none'/);
 assert.ok(!WIDGET_CSP.includes('unsafe-eval'));
 assert.throws(() => widgetDocument('secret-token'));
 assert.equal(widgetHeight(200),400);
 assert.equal(widgetHeight(9000),1600);
 assert.equal(widgetHeight('bad'),760);
});

function browser(initial = null) {
 const values = new Map(initial ? [['mister-mi.oddspedia-widget', JSON.stringify(initial)]] : []);
 let failWrite = false, opens = 0;
 const nodes = new Map();
 const element = () => ({value:'', hidden:false, disabled:false, style:{}, attributes:{}, children:[], textContent:'',
  setAttribute(k,v) {this.attributes[k]=v;}, getAttribute(k) {return this.attributes[k]??null;}, removeAttribute(k) {delete this.attributes[k];},
  set src(value) {this.attributes.src=value;}, replaceChildren(...children) {this.children=children;}});
 globalThis.document = {getElementById(id) {if(!nodes.has(id))nodes.set(id,element()); return nodes.get(id);}, createElement:element};
 globalThis.location = {hostname:'juliomcm-tech.github.io'};
 const storage = {getItem:k=>values.get(k)??null, setItem(k,v) {if(failWrite)throw new DOMException('Full','QuotaExceededError'); values.set(k,v);}, removeItem:k=>values.delete(k)};
 const controller = initOddspediaWidget({storage,onOpen:()=>{opens++;controller.show('fontes');},onToast:()=>{}});
 const $ = id => document.getElementById(id);
 return {controller,$,values,failWrite(value) {failWrite=value;},opens:()=>opens, submit() {$('oddspedia-form').onsubmit({preventDefault(){}});}};
}

test('saves locally, mounts only in Sources, reuses frame, restores and removes', () => {
 const b=browser();
 assert.equal(b.$('oddspedia-domain').textContent,'juliomcm-tech.github.io');
 b.$('oddspedia-code').value=code;
 b.submit();
 assert.equal(b.opens(),1);
 assert.equal(b.$('oddspedia-attribution').hidden,false);
 assert.equal(b.$('oddspedia-mount').children.length,1);
 const frame=b.$('oddspedia-mount').children[0];
 b.controller.show('fontes');
 assert.equal(b.$('oddspedia-mount').children[0],frame);
 b.controller.show('hoje');
 assert.equal(b.$('oddspedia-mount').children.length,0);
 assert.equal(b.$('oddspedia-attribution').hidden,false);
 const saved=JSON.parse(b.values.get('mister-mi.oddspedia-widget'));
 const restored=browser(saved);
 assert.equal(restored.$('oddspedia-code').value,code);
 assert.equal(restored.$('oddspedia-mount').children.length,0);
 restored.controller.show('fontes');
 assert.equal(restored.$('oddspedia-mount').children.length,1);
 restored.$('oddspedia-remove').onclick();
 assert.equal(restored.values.size,0);
 assert.equal(restored.$('oddspedia-mount').children.length,0);
 assert.equal(restored.$('oddspedia-attribution').hidden,true);
 assert.equal(restored.$('oddspedia-code').value,'');
});

test('invalid input or blocked storage does not replace an existing widget', () => {
 const b=browser({code,height:760});
 b.controller.show('fontes');
 const saved=b.values.get('mister-mi.oddspedia-widget');
 b.$('oddspedia-code').value='not-a-widget';b.submit();
 assert.equal(b.opens(),0);
 assert.equal(b.values.get('mister-mi.oddspedia-widget'),saved);
 b.$('oddspedia-code').value=code;b.failWrite(true);b.submit();
 assert.equal(b.opens(),0);
 assert.match(b.$('oddspedia-status').textContent,/não permitiu guardar/);
 assert.equal(b.$('oddspedia-mount').children.length,1);
 assert.equal(b.values.get('mister-mi.oddspedia-widget'),saved);
});
