/// <reference types="vitest" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => {
  return {
    // 生产环境编译时使用子路径，本地开发调试时使用根路径 '/'
    base: mode === 'production' ? '/requirement_space_workbench/' : '/',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
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
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            react: ['react', 'react-dom', 'react-router-dom'],
            ui: ['lucide-react', 'motion'],
            state: ['zustand'],
          },
        },
      },
    },
  };
});
