'use client';

import { useState, ChangeEvent, useEffect } from 'react';
import imageCompression from 'browser-image-compression';
import Navigation from './components/navigation';

type AutoSubscribeResult = {
  attempted: boolean;
  subscribed: boolean;
  reason?: string;
};

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }

  return outputArray;
}

// Get fixed user ID from environment variable
const getUserId = (): string => {
  return process.env.NEXT_PUBLIC_USER_ID || 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d';
};

export default function TicketUpload() {
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const userId = getUserId(); // Fixed user ID from environment

  // Auto-subscribe to notifications on mount
  useEffect(() => {
    void syncExistingSubscription(userId);
  }, []);

  const formatCurrency = (value: number | undefined) => {
    const amount = typeof value === 'number' ? value : 0;
    return `SGD $${amount.toLocaleString()}`;
  };

  const getApiBaseUrl = () => {
    if (process.env.NEXT_PUBLIC_API_BASE_URL) return process.env.NEXT_PUBLIC_API_BASE_URL;
    if (typeof window !== 'undefined') return `${window.location.protocol}//${window.location.hostname}:8000`;
    return 'http://localhost:8000';
  };

  const autoSubscribeNotifications = async (activeUserId: string): Promise<AutoSubscribeResult> => {
    if (!activeUserId) {
      return { attempted: false, subscribed: false, reason: 'missing_user_id' };
    }

    if (
      typeof window === 'undefined' ||
      !("serviceWorker" in navigator) ||
      !("PushManager" in window) ||
      !("Notification" in window)
    ) {
      return { attempted: false, subscribed: false, reason: 'unsupported_browser' };
    }

    const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
    if (!vapidPublicKey) {
      return { attempted: false, subscribed: false, reason: 'missing_vapid_public_key' };
    }

    try {
      await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      });

      let permission = Notification.permission;
      if (permission === 'default') {
        permission = await Notification.requestPermission();
      }

      if (permission !== 'granted') {
        return { attempted: true, subscribed: false, reason: 'permission_not_granted' };
      }

      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();

      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
        });
      }

      const response = await fetch(`${getApiBaseUrl()}/api/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: activeUserId,
          subscription: JSON.parse(JSON.stringify(subscription)),
        }),
      });

      if (!response.ok) {
        return { attempted: true, subscribed: false, reason: 'backend_subscribe_failed' };
      }

      return { attempted: true, subscribed: true };
    } catch (error) {
      console.error('Automatic push subscription failed:', error);
      return { attempted: true, subscribed: false, reason: 'subscription_error' };
    }
  };

  const syncExistingSubscription = async (activeUserId: string): Promise<void> => {
    if (!activeUserId) return;

    if (
      typeof window === 'undefined' ||
      !("serviceWorker" in navigator) ||
      !("PushManager" in window)
    ) {
      return;
    }

    try {
      await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      });

      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (!subscription) return;

      await fetch(`${getApiBaseUrl()}/api/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: activeUserId,
          subscription: JSON.parse(JSON.stringify(subscription)),
        }),
      });
    } catch (error) {
      console.error('Subscription resync failed:', error);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const autoSubscribePromise = autoSubscribeNotifications(userId);

    setLoading(true);
    setResult(null); // Clear previous results
    try {
      const options = { maxSizeMB: 1, maxWidthOrHeight: 1920, useWebWorker: true };
      const compressedFile = await imageCompression(file, options);
      
      setImage(compressedFile);
      setPreview(URL.createObjectURL(compressedFile));

      const formData = new FormData();
      formData.append('file', compressedFile);
      formData.append('user_id', userId);

      const response = await fetch(`${getApiBaseUrl()}/api/extract`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);
      const data = await response.json();

      let combinedResult = data;
      const ticketId = data?.database?.ticket_id;

      if (data?.status === 'success' && ticketId) {
        try {
          const processResponse = await fetch(`${getApiBaseUrl()}/api/results/process-ticket`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket_id: ticketId }),
          });

          const processData = await processResponse.json();

          combinedResult = {
            ...data,
            ticket_processing: processResponse.ok
              ? processData
              : {
                  status: 'error',
                  message: processData?.detail || 'Failed to process ticket',
                },
          };
        } catch {
          combinedResult = {
            ...data,
            ticket_processing: {
              status: 'error',
              message: 'Ticket was uploaded but post-upload processing failed',
            },
          };
        }
      }

      const autoSubscribeResult = await autoSubscribePromise;
      combinedResult = {
        ...combinedResult,
        notification_setup: autoSubscribeResult,
      };

      setResult(combinedResult);
    } catch {
      setResult({ status: 'error', message: 'Upload failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-8 space-y-6">
            <div className="text-center">
              <h1 className="text-3xl font-bold text-gray-800 mb-2">Upload 4D/TOTO Ticket</h1>
              <p className="text-gray-600">Take a photo or upload an image of your lottery ticket</p>
            </div>
            
            <div className="flex justify-center">
              <label className="cursor-pointer bg-gradient-to-r from-blue-600 to-blue-700 text-white px-8 py-4 rounded-lg shadow-md hover:shadow-lg transition font-semibold text-lg">
                {loading ? "⌛ Processing..." : "📷 Take Photo / Upload"}
                <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFileChange} disabled={loading} />
              </label>
            </div>

            {/* Ticket Preview */}
            {preview && (
              <div className="relative w-full border-4 border-dashed border-blue-300 rounded-xl overflow-hidden bg-gray-100 shadow-inner">
                <img 
                  src={preview} 
                  alt="Ticket Preview" 
                  className="w-full h-auto block"
                />

                {loading && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <div className="text-white text-center">
                      <div className="mb-3 text-2xl animate-bounce">🔍</div>
                      <p className="font-semibold">Scanning Numbers...</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Results UI (Keep as is) */}
            {result && result.status === 'success' && (
              <div className="w-full p-6 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border-2 border-green-300">
                <h2 className="font-bold text-green-800 text-lg mb-4">✓ Extraction Complete</h2>
                <div className="space-y-2">
                  <p className="text-gray-900"><span className="font-semibold text-gray-950">Game:</span> {result.extracted_data?.game_type || 'N/A'}</p>
                  <p className="text-gray-900"><span className="font-semibold text-gray-950">Draw Date:</span> {result.extracted_data?.draw_date || 'N/A'}</p>
                  {result.extracted_data?.draw_id && (
                    <p className="text-gray-900"><span className="font-semibold text-gray-950">Draw ID:</span> {result.extracted_data.draw_id}</p>
                  )}
                  {result.extracted_data?.ticket_serial_number && (
                    <p className="text-gray-900"><span className="font-semibold text-gray-950">Ticket Serial:</span> {result.extracted_data.ticket_serial_number}</p>
                  )}
                  {result.database?.status === 'duplicate' && (
                    <div className="mt-2 p-3 bg-blue-50 border border-blue-300 rounded">
                      <p className="text-blue-800 font-semibold text-sm">This ticket was previously uploaded</p>
                      <p className="text-blue-700 text-sm mt-1">{result.database.message}</p>
                    </div>
                  )}
                  <div className="mt-4 p-3 bg-white rounded border border-green-200">
                    <span className="font-semibold text-gray-950 block mb-2">Detected Numbers:</span>
                    <div className="flex flex-wrap gap-2">
                      {result.extracted_data?.numbers?.map((num: number | string, idx: number) => (
                        <span key={idx} className="px-3 py-1 bg-blue-100 text-blue-900 rounded-full font-mono font-bold">
                          {num}
                        </span>
                      ))}
                    </div>
                  </div>

                  {result.ticket_processing && (
                    <div className="mt-4 p-3 bg-white rounded border border-blue-200">
                      <span className="font-semibold text-gray-950 block mb-2">Result Check:</span>

                      {/* Show notification status message */}
                      <div className={`mt-3 rounded-lg border p-4 ${
                        result.ticket_processing.notification_sent 
                          ? 'bg-blue-50 border-blue-300' 
                          : 'bg-amber-50 border-amber-300'
                      }`}>
                        <p className="text-gray-800 font-semibold mb-2">
                          {result.ticket_processing.notification_sent ? '📱 Notification Sent' : 'ℹ️ Status'}
                        </p>
                        <p className="text-gray-700">
                          {result.ticket_processing.message}
                        </p>

                        {result.notification_setup?.subscribed && (
                          <div className="mt-3 p-3 bg-white rounded border border-blue-200">
                            <p className="text-sm text-blue-800">
                              Push notifications are enabled automatically for this device.
                            </p>
                          </div>
                        )}
                        
                        {/* Show subscribe prompt if notification wasn't sent */}
                        {!result.ticket_processing.notification_sent && 
                         result.ticket_processing.status === 'success' && (
                          <div className="mt-3 p-3 bg-white rounded border border-amber-200">
                            <p className="text-sm text-gray-700">
                              <span className="font-semibold">Notification setup needed:</span> Automatic setup was not completed. Allow notifications in your browser settings, then upload again to subscribe.
                            </p>
                          </div>
                        )}
                        
                        {/* Show draw date for pending/no_results status */}
                        {result.ticket_processing.draw_date && 
                         (result.ticket_processing.status === 'pending' || 
                          result.ticket_processing.status === 'no_results') && (
                          <p className="text-gray-600 text-sm mt-2">
                            Draw Date: {result.ticket_processing.draw_date}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Warning UI */}
            {result && result.status === 'warning' && (
              <div className="w-full p-6 bg-gradient-to-r from-yellow-50 to-amber-50 rounded-lg border-2 border-yellow-400">
                <h2 className="font-bold text-yellow-800 text-lg mb-4">⚠️ {result.message || 'No numbers detected'}</h2>
                <p className="text-gray-700 mb-2">Try taking a clearer photo with better lighting.</p>
              </div>
            )}

            {/* Duplicate Ticket UI */}
            {result && result.database?.status === 'duplicate' && result.status === 'success' && (
              <div className="w-full p-6 bg-gradient-to-r from-blue-50 to-cyan-50 rounded-lg border-2 border-blue-300">
                <h2 className="font-bold text-blue-800 text-lg mb-4">Duplicate Ticket Detected</h2>
                <p className="text-gray-800 mb-2">{result.database.message}</p>
                <p className="text-gray-700 text-sm mt-3">
                  Ticket Serial: <span className="font-mono font-semibold">{result.extracted_data?.ticket_serial_number}</span>
                </p>
                {result.database.existing_ticket?.status && (
                  <div className="mt-3 p-3 bg-white rounded border border-blue-200">
                    <p className="text-sm text-gray-800">
                      <span className="font-semibold">Previous Status:</span>{' '}
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        result.database.existing_ticket.status === 'won'
                          ? 'bg-green-100 text-green-800'
                          : result.database.existing_ticket.status === 'lost'
                          ? 'bg-gray-100 text-gray-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {result.database.existing_ticket.status}
                      </span>
                    </p>
                    {result.database.existing_ticket.prize_tier && (
                      <p className="text-sm text-gray-800 mt-1">
                        <span className="font-semibold">Prize Tier:</span> {result.database.existing_ticket.prize_tier}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Error UI */}
            {result && result.status === 'error' && (
              <div className="w-full p-6 bg-gradient-to-r from-red-50 to-orange-50 rounded-lg border-2 border-red-300">
                <p className="text-red-800 font-semibold">❌ Error: {result.message || 'Could not extract data. Please try again with a clearer image.'}</p>
              </div>
            )}

            {/* Info Box */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <h3 className="font-semibold text-blue-800 mb-2">💡 Tip for taking picture:</h3>
              <p className="text-sm text-gray-700">
                Turn on your phone flashlight when lighting is dim, keep the ticket flat, and avoid shadows or glare for more accurate results.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}