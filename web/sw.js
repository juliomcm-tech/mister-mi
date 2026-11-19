/* Bump VERSION with app-shell releases. Only static presentation files are cached. */
const VERSION = "v5";
const SCOPE = new URL(self.registration.scope);
const PREFIX = `mister-mi-shell:${encodeURIComponent(SCOPE.href)}:`;
const CACHE = PREFIX + VERSION;
const APP_FILES = new Set(["", "index.html", "style.css", "app.js", "portfolio.js", "pwa.js", "mood.js", "coverage.js", "outlook.js", "manifest.webmanifest",
  "assets/mister-mi.webp", "assets/mister-mi-blink.webp", "assets/mister-mi-upset.webp", "assets/logo-mmi.webp",
  "assets/fonts/manrope-latin.woff2", "assets/fonts/dela-gothic-latin.woff2", "assets/apple-touch-icon.png",
  "assets/icon-192.png", "assets/icon-512.png", "assets/icon-maskable-512.png"]);
const rootKey = SCOPE.href;
const appPath = url => url.origin === SCOPE.origin && url.pathname.startsWith(SCOPE.pathname)
  ? url.pathname.slice(SCOPE.pathname.length) : null;
const sensitive = request => request.headers.get("authorization") || request.headers.get("x-api-key")
  || [...new URL(request.url).searchParams.keys()].some(key => /token|secret|key|session|code|state|auth|login/i.test(key));
const cacheKey = path => new URL(path, SCOPE).href;

function storable(response, path) {
  if (!response?.ok || response.type === "opaque" || response.redirected
      || /no-store/i.test(response.headers.get("cache-control") || "")) return false;
  if (response.url && new URL(response.url).origin !== SCOPE.origin) return false;
  const type = response.headers.get("content-type") || "";
  if (!path || path === "index.html") return /text\/html/i.test(type);
  if (path.endsWith(".js")) return /(?:javascript|ecmascript)/i.test(type);
  if (path.endsWith(".css")) return /text\/css/i.test(type);
  if (path.endsWith(".png")) return /image\/png/i.test(type);
  if (path.endsWith(".webp")) return /image\/webp/i.test(type);
  if (path.endsWith(".woff2")) return /(?:font\/woff2|application\/octet-stream)/i.test(type);
  return path === "manifest.webmanifest" && /(?:application\/manifest\+json|application\/json)/i.test(type);
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.all([...APP_FILES].filter(path => path !== "index.html").map(async path => {
      try {
        const response = await fetch(new Request(cacheKey(path), { cache: "reload", credentials: "same-origin" }));
        if (storable(response, path)) await cache.put(cacheKey(path), response.clone());
      } catch { /* An unavailable asset must not turn data into a cached fallback. */ }
    }));
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys())
      if (name.startsWith(PREFIX) && name !== CACHE) await caches.delete(name);
    await self.clients.claim();
  })());
});

self.addEventListener("message", event => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

async function networkFirst(request, path) {
  const cache = await caches.open(CACHE);
  const key = !path || path === "index.html" ? rootKey : cacheKey(path);
  try {
    const response = await fetch(request, { cache: "no-store" });
    if (storable(response, path)) await cache.put(key, response.clone());
    if (!response.ok) {
      const fallback = await cache.match(key);
      if (fallback) return fallback;
    }
    return response;
  } catch (error) {
    const fallback = await cache.match(key);
    if (fallback) return fallback;
    throw error;
  }
}

self.addEventListener("fetch", event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== SCOPE.origin) return;
  const path = appPath(url);
  if (path !== null && APP_FILES.has(path) && !sensitive(request)) {
    event.respondWith(networkFirst(request, path));
    return;
  }
  // Includes predictions, history, config, auth and APIs. Network failure remains a failure.
  event.respondWith(fetch(request, { cache: "no-store" }));
});
