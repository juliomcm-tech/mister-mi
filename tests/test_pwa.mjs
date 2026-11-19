import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFile } from "node:fs/promises";

const swCode = await readFile(new URL("../web/sw.js", import.meta.url), "utf8");
const pwaCode = (await readFile(new URL("../web/pwa.js", import.meta.url), "utf8"))
  .replace("export function initPWA", "function initPWA") + "\nglobalThis.initPWA = initPWA;";

function worker(scope = "https://example.org/mister-mi/") {
  const listeners = new Map(), stores = new Map(), calls = [], deleted = [];
  let offline = false, skips = 0;
  const cache = name => {
    if (!stores.has(name)) stores.set(name, new Map());
    const map = stores.get(name);
    return { put: async (key, response) => map.set(String(key.url || key), response.clone()),
      match: async key => map.get(String(key.url || key))?.clone() };
  };
  const self = { registration: { scope }, location: new URL(scope), clients: { claim: async () => {} },
    addEventListener: (type, handler) => listeners.set(type, handler), skipWaiting: () => { skips++; } };
  const fetch = async (request, options) => {
    const url = String(request.url || request);
    calls.push({ url, options });
    if (offline) throw new TypeError("Network unavailable");
    const path = new URL(url).pathname;
    const type = path.endsWith(".js") ? "text/javascript" : path.endsWith(".css") ? "text/css"
      : path.endsWith(".png") ? "image/png" : path.endsWith(".webp") ? "image/webp" : path.endsWith(".woff2") ? "font/woff2" : /\.json$|\/api\//.test(path) ? "application/json"
        : path.endsWith(".webmanifest") ? "application/manifest+json" : "text/html";
    return new Response(type === "application/json" ? '{"fresh":true}' : "app shell", { headers: { "content-type": type } });
  };
  const context = vm.createContext({ self, fetch, URL, Request, Response, caches: {
    open: async name => cache(name), keys: async () => [...stores.keys()], delete: async name => { deleted.push(name); return stores.delete(name); },
  } });
  vm.runInContext(swCode, context);
  return { stores, calls, deleted, skips: () => skips, offline: value => { offline = value; },
    async lifecycle(type) { let done; listeners.get(type)({ waitUntil: promise => { done = promise; } }); await done; },
    message(data) { listeners.get("message")({ data }); },
    request(path, options = {}) {
      let response;
      const request = { url: new URL(path, scope).href, method: "GET", headers: new Headers(), ...options };
      listeners.get("fetch")({ request, respondWith: promise => { response = promise; } });
      return response;
    },
  };
}

test("manifest and relative service worker work at repository root and /web/", async () => {
  const manifest = JSON.parse(await readFile(new URL("../web/manifest.webmanifest", import.meta.url), "utf8"));
  assert.equal(manifest.id, "./"); assert.equal(manifest.scope, "./");
  assert.equal(manifest.start_url, "./?source=installed#hoje");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.icons.length, 3);
  for (const scope of ["https://example.org/mister-mi/", "https://example.org/mister-mi/web/"]) {
    const w = worker(scope);
    await w.lifecycle("install");
    const name = [...w.stores.keys()][0];
    assert.ok(name.includes(encodeURIComponent(scope)));
    assert.ok([...w.stores.get(name).keys()].every(url => url.startsWith(scope)));
    w.offline(true);
    const response = await w.request("./?source=installed");
    assert.equal(await response.text(), "app shell");
    assert.equal((await w.request('./mood.js')).ok, true);
    assert.equal((await w.request('./pwa.js')).ok, true);
    assert.equal((await w.request('./assets/fonts/manrope-latin.woff2')).ok, true);
  }
});

test("predictions, history, config, API and authenticated documents never enter the offline cache", async () => {
  const w = worker(); await w.lifecycle("install");
  const before = [...w.stores.values()].reduce((n, map) => n + map.size, 0);
  for (const path of ["./data/consenso_hoje.json", "./data/history.json", "./config.js", "./api/today", "./auth/callback", "./?token=secret"]) {
    const response = await w.request(path); assert.equal(response.ok, true);
  }
  await w.request("./index.html", { headers: new Headers({ Authorization: "Bearer test" }) });
  assert.equal([...w.stores.values()].reduce((n, map) => n + map.size, 0), before);
  assert.ok([...w.stores.values()].every(map => [...map.keys()].every(key => !/history|consenso|api\/|auth\/|token=|config\.js/.test(key))));
  w.offline(true);
  await assert.rejects(w.request("./data/consenso_hoje.json"), /Network unavailable/);
  await assert.rejects(w.request("./data/history.json"), /Network unavailable/);
  await assert.rejects(w.request("./api/today"), /Network unavailable/);
  assert.equal((await w.request("./app.js")).ok, true);
});

test("cross-origin and mutations are not intercepted or cached", async () => {
  const w = worker(); await w.lifecycle("install");
  const before = w.calls.length;
  assert.equal(w.request("https://source.example/odds.json"), undefined);
  assert.equal(w.request("./api/refresh", { method: "POST" }), undefined);
  assert.equal(w.calls.length, before);
});

test("activation cleans only older Mister Mi caches for its exact registration scope", async () => {
  const w = worker(); await w.lifecycle("install");
  const active = [...w.stores.keys()][0];
  const old = active.replace(/:[^:]+$/, ":old-release");
  const other = `mister-mi-shell:${encodeURIComponent("https://example.org/another-repo/")}:v0`;
  w.stores.set(old, new Map()); w.stores.set(other, new Map()); w.stores.set("unrelated-app", new Map());
  await w.lifecycle("activate");
  assert.deepEqual(w.deleted, [old]);
  assert.equal(w.stores.has(active), true); assert.equal(w.stores.has(other), true); assert.equal(w.stores.has("unrelated-app"), true);
  assert.equal(w.skips(), 0); w.message({ type: "SKIP_WAITING" }); assert.equal(w.skips(), 1);
});

function target() {
  const listeners = new Map();
  return { addEventListener(type, fn) { const list = listeners.get(type) || []; list.push(fn); listeners.set(type, list); },
    removeEventListener(type, fn) { listeners.set(type, (listeners.get(type) || []).filter(x => x !== fn)); },
    async emit(type, event = {}) { for (const fn of [...(listeners.get(type) || [])]) await fn({ preventDefault() {}, ...event }); } };
}

function browser({ ios = false, standalone = false, waiting = false } = {}) {
  const names = ["install-app", "install-app-settings", "install-status", "install-dialog", "install-instructions", "app-update", "apply-update"];
  const elements = Object.fromEntries(names.map(id => [id, { ...target(), hidden: true, dataset: {}, textContent: "", open: false,
    showModal() { this.open = true; }, setAttribute() {} }]));
  let reloads = 0; const registrations = [], messages = [], statuses = [], offline = [];
  const registration = { ...target(), waiting: waiting ? { postMessage: message => messages.push(message) } : null };
  const navigator = { userAgent: ios ? "iPhone" : "Chrome", platform: "", maxTouchPoints: 0, onLine: true,
    serviceWorker: { ...target(), controller: {}, register: async (url, options) => { registrations.push({ url, options }); return registration; } } };
  const window = { ...target(), isSecureContext: true, matchMedia: () => ({ matches: standalone }),
    location: { reload: () => { reloads++; } }, requestIdleCallback: fn => { queueMicrotask(fn); return 1; }, cancelIdleCallback() {} };
  const context = vm.createContext({ window, navigator, document: { getElementById: id => elements[id] } });
  vm.runInContext(pwaCode, context);
  const app = context.initPWA({ onStatus: status => statuses.push(status), onOffline: value => offline.push(value) });
  return { app, elements, navigator, window, registrations, messages, statuses, offline, reloads: () => reloads };
}

test("native installation prompts only on explicit click and acceptance does not fake completion", async () => {
  const b = browser(); let prompts = 0;
  await b.window.emit("beforeinstallprompt", { prompt: async () => { prompts++; }, userChoice: Promise.resolve({ outcome: "accepted" }) });
  assert.equal(prompts, 0);
  await b.elements["install-app"].emit("click");
  assert.equal(prompts, 1); assert.equal(b.statuses.at(-1).state, "requested");
  assert.equal(b.elements["install-app"].hidden, false);
  await b.window.emit("appinstalled");
  assert.equal(b.statuses.at(-1).state, "installed"); assert.equal(b.elements["install-app"].hidden, true);
  b.app.dispose();
});

test("iOS gets manual instructions, standalone hides install buttons, registration stays relative", async () => {
  const b = browser({ ios: true }); await b.app.registration;
  assert.deepEqual(JSON.parse(JSON.stringify(b.registrations[0])), { url: "./sw.js", options: { scope: "./" } });
  await b.elements["install-app-settings"].emit("click");
  assert.equal(b.elements["install-dialog"].open, true);
  assert.match(b.elements["install-instructions"].textContent, /Safari.*Partilhar.*Adicionar ao ecrã principal/);
  assert.equal(b.statuses.at(-1).state, "manual");
  const installed = browser({ standalone: true });
  assert.equal(installed.elements["install-app"].hidden, true);
  assert.equal(installed.statuses.at(-1).state, "installed");
  b.app.dispose(); installed.app.dispose();
});

test("appinstalled confirmation wins a race with the native userChoice promise", async () => {
  const b = browser(); let choose;
  await b.window.emit("beforeinstallprompt", { prompt: async () => {}, userChoice: new Promise(resolve => { choose = resolve; }) });
  const clicked = b.elements["install-app"].emit("click");
  await b.window.emit("appinstalled");
  choose({ outcome: "accepted" }); await clicked;
  assert.equal(b.statuses.at(-1).state, "installed");
  assert.equal(b.elements["install-app"].hidden, true); b.app.dispose();
});

test("updates reload only after an explicit apply action; connectivity is reported", async () => {
  const b = browser({ waiting: true }); await b.app.registration;
  assert.equal(b.elements["app-update"].hidden, false);
  await b.navigator.serviceWorker.emit("controllerchange"); assert.equal(b.reloads(), 0);
  await b.elements["apply-update"].emit("click");
  assert.equal(b.messages[0].type, "SKIP_WAITING");
  await b.navigator.serviceWorker.emit("controllerchange"); assert.equal(b.reloads(), 1);
  b.navigator.onLine = false; await b.window.emit("offline");
  assert.deepEqual(b.offline, [false, true]); b.app.dispose();
});
