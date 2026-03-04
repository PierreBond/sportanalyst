export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Dashboard</h2>
        <p className="mt-2 text-gray-600">
          Real-time sports predictions and analytics
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Active Predictions
          </h3>
          <p className="text-4xl font-bold text-blue-600">24</p>
          <p className="text-sm text-gray-500 mt-1">Matches in progress</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Model Accuracy
          </h3>
          <p className="text-4xl font-bold text-green-600">65%</p>
          <p className="text-sm text-gray-500 mt-1">Last 30 days</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Value Bets
          </h3>
          <p className="text-4xl font-bold text-purple-600">8</p>
          <p className="text-sm text-gray-500 mt-1">Positive EV opportunities</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            Upcoming Matches
          </h3>
        </div>
        <div className="divide-y divide-gray-200">
          <div className="px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <span className="font-medium">Manchester City</span>
                <span className="text-gray-400">vs</span>
                <span className="font-medium">Arsenal</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-500">Today, 8:00 PM</span>
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  45% / 25% / 30%
                </span>
              </div>
            </div>
          </div>

          <div className="px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <span className="font-medium">Liverpool</span>
                <span className="text-gray-400">vs</span>
                <span className="font-medium">Chelsea</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-500">Tomorrow, 3:00 PM</span>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                  52% / 23% / 25%
                </span>
              </div>
            </div>
          </div>

          <div className="px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <span className="font-medium">Barcelona</span>
                <span className="text-gray-400">vs</span>
                <span className="font-medium">Real Madrid</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-500">Sat, 7:00 PM</span>
                <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                  38% / 28% / 34%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
