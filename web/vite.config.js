import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
// The proxy plays the bank's terminal network: it adds the service token, the browser never sees it.
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, '..', ''), ...process.env }
  const token = env.SERVICE_TOKEN || 'change-me'
  return {
    plugins: [react()],
    server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true,
      headers: { 'X-Service-Token': token }, rewrite: p => p.replace(/^\/api/, '') } } },
  }
})
