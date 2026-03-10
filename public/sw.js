const CACHE_NAME = 'my-lottery-cache-v2'
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.webmanifest',
  '/web-app-manifest-192x192.png',
  '/web-app-manifest-512x512.png',
]

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS_TO_CACHE))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', function (event) {
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys()
      await Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      )

      await self.clients.claim()
    })(),
  )
})

self.addEventListener('fetch', function (event) {
  if (event.request.method !== 'GET') {
    return
  }

  const url = new URL(event.request.url)
  const isSameOrigin = url.origin === self.location.origin
  const isNavigation = event.request.mode === 'navigate'
  const isNextAsset = url.pathname.startsWith('/_next/')

  // Keep API and Next runtime chunks network-only to avoid stale SSR/JS hydration mismatches.
  if (!isSameOrigin || url.pathname.startsWith('/api/') || isNextAsset) {
    return
  }

  if (isNavigation) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/')),
    )
    return
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse
      }

      return fetch(event.request)
        .then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200) {
            return networkResponse
          }

          const responseClone = networkResponse.clone()
          void caches
            .open(CACHE_NAME)
            .then((cache) => cache.put(event.request, responseClone))

          return networkResponse
        })
        .catch(() => caches.match('/'))
    }),
  )
})

self.addEventListener('push', function (event) {
  const show = (async () => {
    let payload = {}

    if (event.data) {
      try {
        payload = event.data.json()
      } catch {
        try {
          payload = { body: event.data.text() }
        } catch {
          payload = {}
        }
      }
    }

    const title =
      typeof payload.title === 'string' && payload.title.trim().length > 0
        ? payload.title
        : 'New Notification'

    const options = {
      body:
        typeof payload.body === 'string' && payload.body.trim().length > 0
          ? payload.body
          : 'You have a new message.',
      icon:
        typeof payload.icon === 'string' && payload.icon.trim().length > 0
          ? payload.icon
          : '/web-app-manifest-192x192.png',
      badge: '/web-app-manifest-192x192.png',
      requireInteraction: true,
      data: {
        url: '/',
      },
    }

    await self.registration.showNotification(title, options)
  })()

  event.waitUntil(show)
})
 
self.addEventListener('notificationclick', function (event) {
  event.notification.close()
  const targetUrl = (event.notification && event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(clients.openWindow(targetUrl))
})