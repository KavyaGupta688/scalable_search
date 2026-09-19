import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/search': 'http://localhost:8000',
      '/ingestion': 'http://localhost:8000',
      '/ai': 'http://localhost:8000',
      '/downloads': 'http://localhost:8000',
      '/auth': 'http://localhost:8000'
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});
