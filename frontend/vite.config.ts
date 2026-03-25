import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const sessionManagerTarget = env.VITE_SESSION_MANAGER_URL?.trim() || 'http://localhost:8080';

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: sessionManagerTarget,
          changeOrigin: true,
        },
        '/health': {
          target: sessionManagerTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
