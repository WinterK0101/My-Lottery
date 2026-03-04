'use client';

import Link from 'next/link';
import { useState, ChangeEvent } from 'react';
import imageCompression from 'browser-image-compression';

function Navigation() {
  return (
    <nav className="bg-gradient-to-r from-blue-600 to-blue-800 shadow-lg">
      <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
        <h1 className="text-white text-2xl font-bold">My Lottery</h1>
        <div className="flex gap-4">
          <Link href="/" className="text-white hover:text-blue-200 transition font-semibold">
            Home
          </Link>
          <Link href="/upload" className="text-white hover:text-blue-200 transition font-semibold">
            Upload
          </Link>
        </div>
      </div>
    </nav>
  );
}

export default function TicketUpload() {
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const getApiBaseUrl = () => {
    if (process.env.NEXT_PUBLIC_API_BASE_URL) return process.env.NEXT_PUBLIC_API_BASE_URL;
    if (typeof window !== 'undefined') return `${window.location.protocol}//${window.location.hostname}:8000`;
    return 'http://localhost:8000';
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setResult(null); // Clear previous results
    try {
      const options = { maxSizeMB: 1, maxWidthOrHeight: 1920, useWebWorker: true };
      const compressedFile = await imageCompression(file, options);
      
      setImage(compressedFile);
      setPreview(URL.createObjectURL(compressedFile));

      const formData = new FormData();
      formData.append('file', compressedFile);

      const response = await fetch(`${getApiBaseUrl()}/api/extract`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);
      const data = await response.json();
      setResult(data);
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