/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXTAUTH_URL: 'http://localhost:3000',
    NEXTAUTH_SECRET: 'devsecret_please_change_me',
    AUTH_USERNAME: 'admin',
    AUTH_PASSWORD: 'admin',
    NEXT_PUBLIC_OPERATOR_API_KEY: 'opkey',
    NEXT_PUBLIC_BACKEND_HTTP: 'http://localhost:5001',
    NEXT_PUBLIC_BACKEND_WS: 'ws://localhost:5001/ops',
  },
  // Ensure no experimental mismatches and opt into stable defaults
  poweredByHeader: false,
  trailingSlash: false,
  compress: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  headers: async () => {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
        ],
      },
    ];
  },
};

module.exports = nextConfig; 