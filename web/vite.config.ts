import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['e2e/**', 'node_modules/**'],
  },
  server: {
    // Both overridable so a launcher can move off a port that is already
    // taken. The API port matters more than it looks: client.ts calls a
    // relative '/api', so this proxy is the ONLY thing pointing the UI at a
    // backend — hardcoding 8000 meant a busy 8000 broke the whole web UI
    // with no way to redirect it short of editing this file.
    port: Number(process.env.SAGE_UI_PORT ?? 5173),
    proxy: {
      '/api': {
        target: `http://localhost:${process.env.SAGE_API_PORT ?? 8000}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
