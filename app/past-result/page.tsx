import Navigation from '../components/navigation';

export default function PastResultPage() {
  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Past Result</h1>
          <p className="text-gray-600 mb-6">Browse previous draw outcomes for 4D and TOTO.</p>

          <div className="border border-gray-200 rounded-lg p-6 bg-gray-50">
            <p className="text-gray-700">Past result listing is ready for integration.</p>
            <p className="text-sm text-gray-500 mt-2">
              You can connect this page to `/api/results/past/{'{game_type}'}` next.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
