// web/next/next.config.js
const path = require('path')

/** @type {import('next').NextConfig} */
module.exports = {
  // פרוקסי: כל /api/... עובר ל-FastAPI המקומי
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ]
  },

  // מסיר את אזהרת "inferred root"
  outputFileTracingRoot: path.join(__dirname),
}
