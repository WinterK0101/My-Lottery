'use server'

type SerializedPushSubscription = {
  endpoint: string
  expirationTime: number | null
  keys: {
    p256dh: string
    auth: string
  }
}

const FASTAPI_URL =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'
 
export async function subscribeUser(sub: SerializedPushSubscription) {
  try {
    const response = await fetch(`${FASTAPI_URL}/api/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sub),
    });

    if (!response.ok) {
      throw new Error('Failed to subscribe on backend');
    }

    return { success: true }
  } catch (error) {
    console.error('Subscribe error:', error)
    return { success: false, error: String(error) }
  }
}
 
export async function unsubscribeUser() {
  try {
    const response = await fetch(`${FASTAPI_URL}/api/unsubscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error('Failed to unsubscribe on backend');
    }

    return { success: true }
  } catch (error) {
    console.error('Unsubscribe error:', error)
    return { success: false, error: String(error) }
  }
}
 
export async function sendNotification(message: string) {
  try {
    const response = await fetch(`${FASTAPI_URL}/api/send-notification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || data.detail || 'Failed to send notification');
    }

    return { success: true }
  } catch (error) {
    console.error('Error sending push notification:', error)
    return { success: false, error: String(error) }
  }
}