import Navigation from '../components/navigation';

export default function PurchaseHistoryPage() {
  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Purchase History</h1>
          <p className="text-gray-600 mb-6">View your uploaded tickets and their latest statuses.</p>

          <div className="border border-gray-200 rounded-lg p-6 bg-gray-50">
            <p className="text-gray-700">No purchase history records to show yet.</p>
            <p className="text-sm text-gray-500 mt-2">
              Upload tickets from Home to start building your purchase history.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
