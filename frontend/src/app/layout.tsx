import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sports Prediction Dashboard",
  description: "Real-time sports predictions and analytics",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50">
        <nav className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <h1 className="text-xl font-bold text-gray-900">
                  Sports Prediction System
                </h1>
              </div>
              <div className="flex items-center space-x-4">
                <a href="/" className="text-gray-600 hover:text-gray-900">
                  Dashboard
                </a>
                <a href="/matches" className="text-gray-600 hover:text-gray-900">
                  Matches
                </a>
                <a href="/market" className="text-gray-600 hover:text-gray-900">
                  Market
                </a>
                <a href="/reports" className="text-gray-600 hover:text-gray-900">
                  Reports
                </a>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
