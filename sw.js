/* EDDY service worker — offline shell + fresh data */

const CACHE = "eddy-v1";
const SHELL = [
  "./",
  "./index.html",
  "./event.html",
  "./portfolio.html",
  "./style.css",
  "./app.js",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  // Live data: network-first, fall back to last cached copy when offline
  if (url.pathname.endsWith(".json") && !url.pathname.endsWith("manifest.webmanifest")) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(stripQuery(e.request), clone));
          return res;
        })
        .catch(() => caches.match(stripQuery(e.request)))
    );
    return;
  }

  // App shell: cache-first
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request))
  );
});

function stripQuery(request) {
  const url = new URL(request.url);
  url.search = "";
  return new Request(url.toString());
}
