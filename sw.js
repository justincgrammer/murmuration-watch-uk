const CACHE_NAME = 'murmuration-watch-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Network-first strategy so nightly roost & sightings JSON stay fresh
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});