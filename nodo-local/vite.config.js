import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  esbuild: {
    // @vitejs/plugin-react v6 solo aplica su transform de JSX al entorno
    // "client" (Environment API de Vite). El runner de Vitest ejecuta los
    // tests como consumidor "ssr", así que sin esto esbuild cae al runtime
    // JSX clásico (exige `React` en scope) para los archivos .jsx de test.
    jsx: 'automatic',
  },
  test: {
    environment: 'node',
    setupFiles: ['./src/test-setup.js'],
  },
})
