/** @type {import('next').NextConfig} */
const backendTarget = process.env.API_PROXY_TARGET || "http://10.10.43.20:8001";

const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ["10.243.28.225", "vinnie-unlaborious-unimaginably.ngrok-free.dev"],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendTarget}/:path*`
      }
    ]
  }
};

export default nextConfig;
