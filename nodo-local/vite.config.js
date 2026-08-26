import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // 'prompt': nunca recarga la página sola. Alguien puede estar a mitad de
      // llenar un reporte offline — forzar un reload perdería lo escrito. En
      // vez de eso, App.jsx muestra un aviso y la persona decide cuándo actualizar.
      registerType: 'prompt',
      injectRegister: false,
      manifestFilename: 'manifest.json',
      includeAssets: ['icons/favicon-16.png', 'icons/favicon-32.png', 'icons/apple-touch-icon.png'],
      manifest: {
        id: '/',
        name: 'Nodo Local — Ayuda Terremoto Colombia',
        short_name: 'Nodo Local',
        description:
          'Coordinación de ayuda humanitaria tras el terremoto del 10 de agosto de 2026 en Chocó, Colombia: mapa en vivo, reportes de necesidades y panel de coordinador offline-first.',
        lang: 'es-CO',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait-primary',
        background_color: '#fafafa',
        theme_color: '#7a3bff',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Solo cachea el shell de la app (HTML/JS/CSS/iconos/tiles que ya
        // pasaron por el build). Las llamadas a la API del Nodo Central
        // (VITE_API_BASE_URL) NUNCA se interceptan acá: ese tráfico sigue
        // yendo directo a la red y la cola offline sigue viviendo en
        // IndexedDB (src/db.js, src/sync.js), no en el service worker.
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
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
