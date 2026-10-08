import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend port is configurable so it can coexist with other local services on 8000.
const backendPort = process.env.BACKEND_PORT || '8000'
const backend = `http://127.0.0.1:${backendPort}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      ignored: ['**/dist_app/**', '**/dist_installer/**', '**/build/**', '**/venv/**']
    },
    proxy: {
      '/api': {
        target: backend,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (_err, _req, res: any) => {
            if (res && !res.headersSent && typeof res.writeHead === 'function') {
              res.writeHead(503, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                error: `Backend API server on port ${backendPort} is not running. Start it with \`npm run dev\`.`,
                status: 503
              }));
            }
          });
        }
      },
      '/docs': {
        target: backend,
        changeOrigin: true,
      },
      '/redoc': {
        target: backend,
        changeOrigin: true,
      },
      '/openapi.json': {
        target: backend,
        changeOrigin: true,
      },
    }
  }
})

