'use client';

import Image from "next/image";
import { useState, useEffect } from "react";
import { subscribeUser, unsubscribeUser, sendNotification } from './actions'; 

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
 
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)
 
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

function PushNotificationManager() {
  const [isSupported, setIsSupported] = useState(false)
  const [subscription, setSubscription] = useState<PushSubscription | null>(
    null
  )
  const [message, setMessage] = useState('')
  const [pushError, setPushError] = useState<string | null>(null)
 
  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true)
      registerServiceWorker()
    }
  }, [])
 
  async function registerServiceWorker() {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      })
      const sub = await registration.pushManager.getSubscription()
      setSubscription(sub)
    } catch (error) {
      console.error('Service Worker registration failed:', error)
      setPushError('Failed to register service worker.')
    }
  }

  async function ensureNotificationPermission() {
    if (Notification.permission === 'default') {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        throw new Error('Notification permission denied')
      }
      return
    }

    if (Notification.permission === 'denied') {
      throw new Error('Notification permission is denied')
    }
  }

  async function createPushSubscription(forceRefresh: boolean) {
    if (forceRefresh) {
      const registrations = await navigator.serviceWorker.getRegistrations()
      await Promise.all(registrations.map((reg) => reg.unregister()))
      await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      })
    }

    const registration = await navigator.serviceWorker.ready
    if (!registration.active) {
      throw new Error('No active service worker')
    }

    const key = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY
    if (!key) {
      throw new Error('NEXT_PUBLIC_VAPID_PUBLIC_KEY is not set')
    }

    if (key.length < 50) {
      throw new Error('VAPID public key appears invalid')
    }

    const existing = await registration.pushManager.getSubscription()
    if (existing) {
      await existing.unsubscribe()
    }

    return registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    })
  }
 
  async function subscribeToPush() {
    setPushError(null)
    try {
      await ensureNotificationPermission()
      const sub = await createPushSubscription(false)
      setSubscription(sub)
      const serializedSub = JSON.parse(JSON.stringify(sub))
      await subscribeUser(serializedSub)
    } catch (error) {
      const isAbortError =
        error instanceof DOMException && error.name === 'AbortError'

      if (isAbortError) {
        try {
          const sub = await createPushSubscription(true)
          setSubscription(sub)
          const serializedSub = JSON.parse(JSON.stringify(sub))
          await subscribeUser(serializedSub)
          return
        } catch (retryError) {
          console.error('Push subscription retry failed:', retryError)
        }
      }

      console.error('Push subscription failed:', error)
      setPushError(
        'Push service is unreachable from this browser/network. Try disabling VPN/ad blocker, allow browser background networking, or test in Chrome/Edge with a clean profile.'
      )
    }
  }
 
  async function unsubscribeFromPush() {
    await subscription?.unsubscribe()
    setSubscription(null)
    await unsubscribeUser()
  }
 
  async function sendTestNotification() {
    if (subscription) {
      const result = await sendNotification(message)
      if (result.success) {
        setMessage('')
        setPushError(null)
      } else {
        setPushError(result.error || 'Failed to send notification')
      }
    }
  }
 
  if (!isSupported) {
    return <p>Push notifications are not supported in this browser.</p>
  }
 
  return (
    <div>
      <h3>Push Notifications</h3>
      {subscription ? (
        <>
          <p>You are subscribed to push notifications.</p>
          <button onClick={unsubscribeFromPush}>Unsubscribe</button>
          <input
            type="text"
            placeholder="Enter notification message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          <button onClick={sendTestNotification}>Send Test</button>
        </>
      ) : (
        <>
          <p>You are not subscribed to push notifications.</p>
          {pushError ? <p>{pushError}</p> : null}
          <button onClick={subscribeToPush}>Subscribe</button>
        </>
      )}
    </div>
  )
}

function InstallPrompt() {
  const [isIOS, setIsIOS] = useState(false)
  const [isStandalone, setIsStandalone] = useState(false)
 
  useEffect(() => {
    setIsIOS(
      /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream
    )
 
    setIsStandalone(window.matchMedia('(display-mode: standalone)').matches)
  }, [])
 
  if (isStandalone) {
    return null // Don't show install button if already installed
  }
 
  return (
    <div>
      <h3>Install App</h3>
      <button>Add to Home Screen</button>
      {isIOS && (
        <p>
          To install this app on your iOS device, tap the share button
          <span role="img" aria-label="share icon">
            {' '}
            ⎋{' '}
          </span>
          and then "Add to Home Screen"
          <span role="img" aria-label="plus icon">
            {' '}
            ➕{' '}
          </span>
          .
        </p>
      )}
    </div>
  )
}
 
export default function Page() {
  return (
    <div>
      <PushNotificationManager />
      <InstallPrompt />
    </div>
  )
}