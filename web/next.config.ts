import type { NextConfig } from 'next'

const isDemo = process.env.NEXT_PUBLIC_DEMO_MODE === '1'
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''

const config: NextConfig = {
  output: 'export',
  trailingSlash: true,
  basePath: isDemo ? basePath : '',
  assetPrefix: isDemo ? basePath : '',
  images: {
    unoptimized: true,
  },
  ...(isDemo
    ? {}
    : {
        async rewrites() {
          return [
            {
              source: '/api/:path*',
              destination: `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/:path*`,
            },
          ]
        },
      }),
}

export default config
