import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
  },
  server: {
    allowedHosts: true,
  },
  preview: {
    allowedHosts: ['yoga-song-showers-licensed.trycloudflare.com'],
  },
})
