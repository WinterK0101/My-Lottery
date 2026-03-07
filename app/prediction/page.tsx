import Navigation from '../components/navigation';

export default function PredictionPage() {
  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Prediction</h1>
          <p className="text-gray-600 mb-6">Generate and review number predictions.</p>

          <div className="border border-gray-200 rounded-lg p-6 bg-gray-50">
            <p className="text-gray-700">Prediction module route is ready.</p>
            <p className="text-sm text-gray-500 mt-2">
              You can add your prediction algorithm and UI controls on this page next.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
