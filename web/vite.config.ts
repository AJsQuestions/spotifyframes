import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/spotiframes/', // For GitHub Pages deployment (matches repo name)
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})
