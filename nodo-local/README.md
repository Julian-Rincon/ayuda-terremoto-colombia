# Nodo Local — app offline-first

Tiene dos caras:

- **Portal público** (sin login): cualquiera puede ver el panorama nacional,
  reportar una necesidad, o registrarse como voluntario/colectivo.
- **Panel de coordinador** (con login, uno por centro territorial —
  Pereira/Risaralda, Chocó, Caldas, Valle): registra reportes y entregas
  **incluso sin conexión**, y sincroniza todo con el
  [Nodo Central](../sistema-ayuda-nacional/) apenas vuelva la señal. Es la
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

18 tests con Vitest, sobre la lógica que garantiza que nada se pierde
offline: cola de salida (`db.test.js`) y motor de sincronización con
reintentos (`sync.test.js`, incluye reportes, entregas y registro de
colectivos), usando `fake-indexeddb` para simular IndexedDB en Node sin
necesitar un navegador real.

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
├── db.js              # IndexedDB: sesión, cache de necesidades/envíos, outbox
├── api.js              # cliente HTTP al Nodo Central
├── sync.js              # motor de sincronización (flush del outbox)
├── hooks/useOnlineStatus.js
└── components/
    ├── NavPublica.jsx          # pestañas: Inicio / Mapa / Reportar / Registrarme / Coordinador
    ├── Inicio.jsx              # panorama nacional público, sin login
    ├── MapaNacional.jsx        # mapa interactivo (Leaflet), sin login
    ├── ReportarPublico.jsx     # reportar una necesidad, sin login
    ├── RegistrarColectivo.jsx  # registrarse como voluntario/colectivo, sin login
    ├── Login.jsx               # login de coordinador (por centro)
    ├── Dashboard.jsx           # panel del coordinador, requiere sesión
    ├── EstadoConexion.jsx
    ├── ListaNecesidades.jsx
    ├── EnviosEnCamino.jsx
    └── NuevaSolicitudForm.jsx  # reusado por ReportarPublico y por el Dashboard
```

## Portal público

`Inicio.jsx` consulta `GET /api/v1/resumen` del Nodo Central y muestra, sin
pedir login a nadie, cuántas zonas están activas, cuántas necesidades hay
reportadas/confirmadas, cuántos colectivos están confirmados y cuántos
envíos vienen en camino — el objetivo es que cualquier persona interesada
entienda el sistema de un vistazo.

`ReportarPublico.jsx` y `RegistrarColectivo.jsx` reutilizan el mismo patrón
offline-first que el resto de la app: la acción se guarda primero en el
`outbox` local y se sincroniza apenas hay conexión, así que reportar o
registrarse como voluntario funciona incluso sin señal.

## Mapa nacional

`MapaNacional.jsx` usa **Leaflet + OpenStreetMap** — gratis, sin llave de
API, coherente con que el proyecto es 100% código abierto. Muestra los 4
centros territoriales (con su conteo de necesidades pendientes), los
reportes que tienen coordenadas (color por urgencia; los que aún no tiene
confirmación humana se ven más tenues), y el último sismo detectado por
USGS si hay uno. A diferencia del resto de la app, **el mapa necesita
conexión** — las imágenes del mapa no se pueden cachear para verlo offline
en esta versión.

## Envíos en camino

`EnviosEnCamino.jsx` muestra, de solo lectura, qué recursos en especie están
comprometidos/en tránsito hacia el centro (ej. "50 de alimentos desde
Bogotá") — consulta `GET /api/v1/envios?centro_id=` del Nodo Central y
cachea la respuesta en IndexedDB para poder mostrarla offline. Cada envío
indica si ya fue verificado por un humano o no; registrar/verificar un envío
nuevo se hace desde el Nodo Central (Swagger o integración de quien
despacha), no desde esta app — el Nodo Local es la vista del centro que
recibe, no del que despacha.

## Limitaciones conocidas

- Si el JWT expira mientras el centro está offline, las entregas encoladas
  quedarán en estado `error` hasta volver a iniciar sesión con conexión —
  no hay renovación automática de token todavía.
- No hay Service Worker / manifest de PWA instalable — corre como web app
  normal en el navegador, que ya cachea localmente vía IndexedDB, pero no
  funciona sin haber cargado la página al menos una vez con conexión.
