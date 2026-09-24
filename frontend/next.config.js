/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8005',
  },
  
  images: {
    unoptimized: true,
  },
  
  async rewrites() {
    return [];
  },

  turbopack: {},
};

module.exports = nextConfig;
