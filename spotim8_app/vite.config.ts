import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/spotim8/', // For GitHub Pages deployment (matches repo name)
  server: {
    host: '127.0.0.1',
    port: 5173,  // Use default port to avoid conflict with Python OAuth on 8888
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})
