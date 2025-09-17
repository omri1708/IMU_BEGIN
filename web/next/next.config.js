/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' },
      { source: '/grounded/:path*', destination: 'http://localhost:8000/grounded/:path*' },
    ];
  },
};
module.exports = nextConfig;
