export default {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }],
    ['@babel/preset-react', { runtime: 'automatic' }],
  ],
  plugins: [
    ['babel-plugin-transform-vite-meta-env', {
      VITE_API_BASE_URL: '/api',
      VITE_SSE_URL: '/sse',
    }],
  ],
}