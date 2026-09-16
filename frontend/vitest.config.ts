import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  envDir: false,
  define: { 'import.meta.env.VITE_API_URL': JSON.stringify('/api') },
  test: {
    environment: 'jsdom',
    include: ['tests/components/**/*.test.tsx'],
    setupFiles: ['tests/components/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/context/AuthContext.tsx', 'src/components/auth/RouteGuards.tsx', 'src/pages/JoinCourse.tsx', 'src/pages/student/StudyMode.tsx'],
      reporter: ['text', 'json-summary', 'lcov', 'html'],
      thresholds: { statements: 90, branches: 80, functions: 90, lines: 90 },
    },
  },
})
