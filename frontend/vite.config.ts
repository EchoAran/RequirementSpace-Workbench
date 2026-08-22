/// <reference types="vitest" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'DISABLE_HMR');
  return {
    // 生产环境与本地调试统一使用根路径 '/'
    base: '/',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      hmr: env.DISABLE_HMR !== 'true',
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          timeout: 600_000,
          proxyTimeout: 600_000,
        },
      },
    },
    test: {
      globals: true,
      environment: 'happy-dom',
      setupFiles: './src/tests/setup.ts',
    },
    build: {
      chunkSizeWarningLimit: 500,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('react') || id.includes('react-dom') || id.includes('react-router-dom')) {
                return 'vendor-react';
              }
              if (id.includes('lucide-react')) {
                return 'vendor-icons';
              }
              if (id.includes('zustand') || id.includes('i18next') || id.includes('react-i18next')) {
                return 'vendor-state';
              }
              if (id.includes('clsx') || id.includes('tailwind-merge') || id.includes('canvas-confetti') || id.includes('prismjs')) {
                return 'vendor-utils';
              }
            }
            if (id.includes('src/locales/')) {
              return 'locales';
            }
            if (id.includes('src/store/useWorkspaceStore')) {
              return 'store-workspace';
            }
          },
        },
      },
    },
  };
});
