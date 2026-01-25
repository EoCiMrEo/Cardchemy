import path from "path"
import { fileURLToPath } from "url"
import { defineConfig } from 'vite'

const __filepath = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filepath)
import react from '@vitejs/plugin-react'

import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
