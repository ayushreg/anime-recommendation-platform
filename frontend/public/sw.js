/* Kura service worker.
 *
 * Two caches with different rules. The app shell is cache-first so a cold boot
 * with no network still paints. API reads are network-first with a cached
 * fallback, so you get fresh data when the server is up and the last known
 * answer when it is not. Writes never touch the cache.
 */

const SHELL = "kura-shell-v2";
const DATA = "kura-data-v2";

const PRECACHE = [
  "/",
  "/index.html",
  "/logo.png",
  "/mascot.png",
  "/mascot-chibi.png",
  "/poster-fallback.png",
  "/hero-banner.png",
  "/favicon.svg",
];

const CACHEABLE_API = [
  "/api/anime/",
  "/api/stats",
  "/api/flags",
  "/api/discover/seasons",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== SHELL && k !== DATA).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) {
    if (!CACHEABLE_API.some((prefix) => url.pathname.startsWith(prefix))) return;
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(DATA).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Poster art from provider CDNs, cached opportunistically.
  if (url.origin !== self.location.origin) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request)
            .then((response) => {
              if (response.ok || response.type === "opaque") {
                const copy = response.clone();
                caches.open(DATA).then((cache) => cache.put(request, copy));
              }
              return response;
            })
            .catch(() => caches.match("/poster-fallback.png"))
      )
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request)
          .then((response) => {
            const copy = response.clone();
            caches.open(SHELL).then((cache) => cache.put(request, copy));
            return response;
          })
          .catch(() => caches.match("/index.html"))
    )
  );
});
