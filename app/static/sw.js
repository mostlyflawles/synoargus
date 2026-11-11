/* SynoArgus service worker. Nothing is cached: the app always needs its server.
   Its only job is to show a short message instead of a blank page when the NAS cannot be reached. */
'use strict';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(() => new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<title>SynoArgus</title><body style="font-family:system-ui;margin:15vh auto;max-width:420px;padding:0 20px;text-align:center">' +
    '<h2>SynoArgus</h2><p>Cannot reach SynoArgus. Check that the NAS is on and that you are on the right network.</p>' +
    '<p>Kan inte nå SynoArgus. Kontrollera att NAS:en är igång och att du är på rätt nätverk.</p>' +
    '<p><button onclick="location.reload()" style="font:inherit;padding:8px 18px">↻</button></p></body>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } })));
});
