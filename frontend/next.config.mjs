/** @type {import('next').NextConfig} */
const nextConfig = {
  // 'standalone' giúp tạo bản build tối giản, tối ưu cho Docker/Railway.
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
