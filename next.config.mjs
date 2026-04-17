/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",        // Smaller Docker image
  reactStrictMode: true,
  // Allow images from MinIO
  images: {
    remotePatterns: [
      { protocol: "http",  hostname: "localhost", port: "9000" },
      { protocol: "https", hostname: "**" },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
