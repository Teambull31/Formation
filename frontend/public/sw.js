// Network-first shell cache. Never touches /api or /ws (course data and terminal stay live),
// sauf les audios que l'onglet Écoute a téléchargés pour la route (cache AUDIO, rempli par la page).
const CACHE = 'formation-shell-v1'
const AUDIO = 'formation-audio'
const AUDIO_PATHS = ['/api/podcast/', '/api/audio/', '/api/fiche-audio/', '/api/revision/']

// Le lecteur audio demande des morceaux (Range) ; Safari exige une réponse 206 pour lire un média.
async function fromCache(req, hit) {
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.get('range') || '')
  if (!range) return hit
  const buf = await hit.arrayBuffer()
  const start = range[1] ? Number(range[1]) : Math.max(0, buf.byteLength - Number(range[2]))
  const end = range[1] && range[2] ? Math.min(Number(range[2]), buf.byteLength - 1) : buf.byteLength - 1
  if (start >= buf.byteLength || start > end) {
    return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${buf.byteLength}` } })
  }
  return new Response(buf.slice(start, end + 1), {
    status: 206,
    headers: {
      'Content-Type': hit.headers.get('Content-Type') || 'audio/mpeg',
      'Content-Range': `bytes ${start}-${end}/${buf.byteLength}`,
      'Content-Length': String(end - start + 1),
      'Accept-Ranges': 'bytes',
    },
  })
}

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k !== AUDIO).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  const url = new URL(req.url)
  if (req.method !== 'GET' || url.origin !== self.location.origin) return
  if (AUDIO_PATHS.some((p) => url.pathname.startsWith(p))) {
    // téléchargé : lu depuis le téléphone ; sinon réseau normal (jamais mis en cache automatiquement)
    event.respondWith(caches.open(AUDIO).then((c) => c.match(url.pathname)).then((hit) => hit ? fromCache(req, hit) : fetch(req)))
    return
  }
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/ws')) return
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(req, copy))
        }
        return res
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match('/'))),
  )
})

// Rappel quotidien (Web Push) : le serveur envoie {title, body} chiffré.
self.addEventListener('push', (event) => {
  let d = {}
  try { d = event.data.json() } catch { /* message vide ou en texte brut */ }
  event.waitUntil(self.registration.showNotification(d.title || 'Formation', {
    body: d.body || '', icon: '/icon-192.png', badge: '/icon-192.png', tag: 'daily',
    data: { url: d.url || '/?tab=quete' },
    actions: Array.isArray(d.actions) ? d.actions.slice(0, 2) : [], // Android : boutons ; ailleurs ignorés
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    .then((cs) => (cs.length ? cs[0].focus() : self.clients.openWindow('/'))))
})

// Toucher la notification ouvre l'appli (ou la ramène au premier plan) sur la quête du jour.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const byAction = { ecoute: '/?tab=ecoute', revisions: '/?tab=revisions' }
  const url = byAction[event.action] || (event.notification.data && event.notification.data.url) || '/?tab=quete'
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
    const w = wins.find((c) => new URL(c.url).origin === self.location.origin)
    return w ? w.focus().then((c) => c.navigate ? c.navigate(url) : c) : self.clients.openWindow(url)
  }))
})
