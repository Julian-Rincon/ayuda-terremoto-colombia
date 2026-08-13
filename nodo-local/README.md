# Nodo Local — app offline-first

App para que un centro territorial (Pereira/Risaralda, Chocó, Caldas, Valle)
registre reportes y entregas **incluso sin conexión**, y sincronice todo con
el [Nodo Central](../sistema-ayuda-nacional/) apenas vuelva la señal. Es la
pieza que `planoidea.md` §8 marca como "la parte que más importa" en zonas
como Chocó, donde la conectividad es intermitente.

## Cómo funciona el offline-first

Todo lo que el usuario hace (registrar un reporte, marcar una entrega) se
escribe primero en **IndexedDB local** (`src/db.js`, cola `outbox`), nunca
directo a la red. Después, si hay conexión, se intenta sincronizar de
inmediato (`src/sync.js`); si falla o no hay red, la acción queda marcada
`pendiente` (o `error`, con el motivo) y se reintenta:

- automáticamente cuando el navegador dispara el evento `online`,
- o manualmente con el botón "Sincronizar ahora".

Ninguna acción se pierde por quedarse sin señal a mitad de una entrega.

La sesión (JWT del centro, obtenido de `POST /api/v1/auth/token` en el Nodo
Central) también se guarda en IndexedDB — se necesita conexión para el login
inicial, pero después el centro puede seguir trabajando offline durante toda
su sesión.

## Levantar en local

```bash
npm install
cp .env.example .env
# VITE_API_BASE_URL debe apuntar al Nodo Central (ver sistema-ayuda-nacional/)
npm run dev
```

Necesitas el backend de `sistema-ayuda-nacional/` corriendo (por defecto en
`http://localhost:8000`) para poder iniciar sesión y sincronizar. El
id de territorio de login es uno de: `risaralda-pereira`, `choco`, `caldas`,
`valle` — el secreto es el valor de `NODOS_SECRETO_INICIAL` que hayas
configurado en el backend.

## Tests

```bash
npm test
```

15 tests con Vitest, sobre la lógica que garantiza que nada se pierde
offline: cola de salida (`db.test.js`) y motor de sincronización con
reintentos (`sync.test.js`), usando `fake-indexeddb` para simular IndexedDB
en Node sin necesitar un navegador real.

**Nota honesta:** estos tests cubren la lógica de persistencia y
sincronización, que es donde vive el riesgo real de un sistema offline-first
(perder datos, duplicar envíos, quedarse colgado sin red). No hay tests de
componentes React ni verificación visual en un navegador real — se validó
manualmente que `npm run build` compila limpio y que el servidor de
desarrollo sirve la app sin errores, pero no un click-through completo en
un navegador.

## Estructura

```
src/
├── db.js              # IndexedDB: sesión, cache de necesidades, outbox
├── api.js              # cliente HTTP al Nodo Central
├── sync.js              # motor de sincronización (flush del outbox)
├── hooks/useOnlineStatus.js
└── components/
    ├── Login.jsx
    ├── Dashboard.jsx
    ├── EstadoConexion.jsx
    ├── ListaNecesidades.jsx
    └── NuevaSolicitudForm.jsx
```

## Limitaciones conocidas

- Si el JWT expira mientras el centro está offline, las entregas encoladas
  quedarán en estado `error` hasta volver a iniciar sesión con conexión —
  no hay renovación automática de token todavía.
- No hay Service Worker / manifest de PWA instalable — corre como web app
  normal en el navegador, que ya cachea localmente vía IndexedDB, pero no
  funciona sin haber cargado la página al menos una vez con conexión.
