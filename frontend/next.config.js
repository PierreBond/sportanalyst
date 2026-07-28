/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8005',
  },
  
  // Image optimization
  images: {
    unoptimized: true,
  },
  
  async rewrites() {
    return [
      {
        source: '/api/backend/:path*',
        destination: 'http://localhost:8005/:path*',
      },
    ];
  },

  turbopack: {},
};

module.exports = nextConfig;
