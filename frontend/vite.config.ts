import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Only /api is proxied. NEVER proxy /ws/terminal: it must stay same-origin (localhost guard).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
