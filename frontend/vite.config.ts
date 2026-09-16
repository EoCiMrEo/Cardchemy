import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { publicEnvironment } from './config/environment.mjs'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(frontendDir, '..')

export default defineConfig(() => {
  const { apiPort, apiUrl } = publicEnvironment(path.join(rootDir, '.env'))

  return {
    envDir: false as const,
    define: { 'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl) },
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(frontendDir, 'src'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${apiPort}`,
          changeOrigin: true,
          rewrite: (requestPath: string) => requestPath.replace(/^\/api(?=\/|$)/, ''),
          cookiePathRewrite: { '/auth': '/api/auth' },
        },
      },
    },
  }
})
