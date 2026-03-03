self.addEventListener('install', function (event) {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim())
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