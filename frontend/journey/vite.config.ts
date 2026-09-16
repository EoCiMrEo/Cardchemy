import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// Tests explicitly inject these public values. No root or component .env is read.
export default defineConfig({
  root: frontendRoot,
  cacheDir: process.env.JOURNEY_CACHE_DIR,
  envDir: false,
  define: { 'import.meta.env.VITE_API_URL': JSON.stringify('/api') },
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.join(frontendRoot, 'src') } },
  server: {
    proxy: {
      '/api': {
        target: process.env.JOURNEY_API_ORIGIN,
        changeOrigin: true,
        rewrite: (requestPath: string) => requestPath.replace(/^\/api(?=\/|$)/, ''),
        cookiePathRewrite: { '/auth': '/api/auth' },
      },
    },
  },
})
