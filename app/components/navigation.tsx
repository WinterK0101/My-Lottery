'use client';

import Link from 'next/link';

export default function Navigation() {
  return (
    <nav className="bg-gradient-to-r from-blue-600 to-blue-800 shadow-lg">
      <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center gap-4">
        <h1 className="text-white text-2xl font-bold">My Lottery</h1>
        <div className="flex flex-wrap gap-4 justify-end text-sm md:text-base">
          <Link href="/" className="text-white hover:text-blue-200 transition font-semibold">
            Home
          </Link>
          <Link href="/purchase-history" className="text-white hover:text-blue-200 transition font-semibold">
            Purchase History
          </Link>
          <Link href="/past-result" className="text-white hover:text-blue-200 transition font-semibold">
            Past Result
          </Link>
          <Link href="/prediction" className="text-white hover:text-blue-200 transition font-semibold">
            Prediction
          </Link>
        </div>
      </div>
    </nav>
  );
}
