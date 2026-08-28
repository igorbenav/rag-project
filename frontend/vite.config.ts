import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The bundle is served by FastAPI, which reads it from outside src/ — compose
// mounts ./src over the image for hot reload and would otherwise shadow it. In
// development Vite proxies /api to the backend, so the client uses one origin
// either way and never needs a base URL.
export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  build: {
    outDir: path.resolve(__dirname, 'dist'),
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: { '/api': { target: process.env.VITE_BACKEND_URL || 'http://localhost:8000', changeOrigin: true } },
  },
});
