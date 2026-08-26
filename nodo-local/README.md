# Nodo Local — app offline-first

Tiene dos caras:

- **Portal público** (sin login): cualquiera puede ver el panorama nacional,
  reportar una necesidad, o registrarse como voluntario/colectivo.
- **Panel de coordinador** (con login, uno por centro territorial):
  registra reportes y entregas **incluso sin conexión**, y sincroniza todo
  con el [Nodo Central](../sistema-ayuda-nacional/) apenas vuelva la señal.
  Es la pieza que `planoidea.md` §8 marca como "la parte que más importa"
  en zonas como Chocó, donde la conectividad es intermitente. El backend
  ya siembra un centro por cada uno de los 33 departamentos del país —
  Pereira/Risaralda, Chocó, Caldas y Valle del Cauca arrancan **activos**
  con datos reales confirmados; los otros 29 quedan "dormidos" hasta que
  un sismo fuerte o un coordinador los activa (ver el README del Nodo
  Central, sección "Cobertura nacional"). El login no distingue entre
  centros activos y dormidos — cualquiera con el `id_territorio` y el
  secreto correcto puede entrar, esté o no ya activado.

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
`http://localhost:8000`) para poder iniciar sesión y sincronizar. El id de
territorio de login es el de cualquiera de los 33 centros sembrados (por
ejemplo `risaralda-pereira`, `choco`, `caldas` o `valle`, que son los que
hoy tienen datos reales) — el secreto es el valor de
`NODOS_SECRETO_INICIAL` que hayas configurado en el backend.

## Tests

```bash
npm test
```

39 tests con Vitest en 5 archivos:

- **Lógica offline** (18 tests, la base histórica de esta app): cola de
  salida (`db.test.js`, 11) y motor de sincronización con reintentos
  (`sync.test.js`, 7, incluye reportes, entregas y registro de colectivos),
  usando `fake-indexeddb` para simular IndexedDB en Node sin necesitar un
  navegador real.
- **Componentes React** (21 tests, con Testing Library): `Login.test.jsx`
  (6, login y manejo de credenciales inválidas), `NuevaSolicitudForm.test.jsx`
  (7, validación y envío del formulario reusado por reportar/coordinador) y
  `EstadoConexion.test.jsx` (8, indicador de conexión y estado del outbox).

**Nota honesta:** sigue sin haber verificación visual en un navegador real
más allá de lo que cubren estos tests — se validó manualmente que
`npm run build` compila limpio y que el servidor de desarrollo sirve la
app sin errores, pero no un click-through completo de principio a fin en
un navegador. La instalabilidad como PWA y la navegación por teclado del
mapa sí se verificaron con Playwright contra un build real (ver
[`docs/accesibilidad-pwa.md`](docs/accesibilidad-pwa.md)), fuera de esta
suite de Vitest.

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
    ├── AlertaSismica.jsx       # resumen de actividad sísmica reciente (IA + fallback)
    ├── MapaNacional.jsx        # mapa interactivo (Leaflet), sin login
    ├── ReportarPublico.jsx     # reportar una necesidad, sin login
    ├── RegistrarColectivo.jsx  # registrarse como voluntario/colectivo, sin login
    ├── Login.jsx               # login de coordinador (por centro)
    ├── Dashboard.jsx           # panel del coordinador, requiere sesión
    ├── EstadoConexion.jsx
    ├── ListaNecesidades.jsx
    ├── ListaMapaAccesible.jsx  # alternativa textual y navegable por teclado al mapa
    ├── EnviosEnCamino.jsx
    ├── NuevaSolicitudForm.jsx  # reusado por ReportarPublico y por el Dashboard
    └── ActualizacionApp.jsx    # aviso de nueva versión / app lista para usarse offline (PWA)
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
API, coherente con que el proyecto es 100% código abierto. Muestra los 33
centros territoriales del país (activos con un círculo más grande, los
"dormidos" más tenues, con su conteo de necesidades pendientes), los
reportes que tienen coordenadas (color por urgencia; los que aún no tiene
confirmación humana se ven más tenues), y todos los sismos detectados
recientemente por USGS (círculo más grande = mayor magnitud). A diferencia
del resto de la app, **el mapa necesita conexión** — las imágenes del mapa
no se pueden cachear para verlo offline en esta versión.

Los marcadores del mapa (`CircleMarker` de Leaflet) no reciben foco de
teclado. `ListaMapaAccesible.jsx` agrega, debajo del mapa, tres listas
navegables (centros, necesidades reportadas, sismos) con la misma
información que los popups, usando `<button>` reales — funciona igual de
bien para quien nunca ve el mapa. Detalle completo, incluida la
verificación con Playwright, en
[`docs/accesibilidad-pwa.md`](docs/accesibilidad-pwa.md).

## App instalable (PWA)

`nodo-local` se puede instalar como app (`vite-plugin-pwa`, estrategia
`generateSW`/Workbox): manifest con iconos propios, y un service worker
que precachea el shell de la app (HTML/JS/CSS/iconos) para que cargue sin
conexión después de la primera visita. Las llamadas a la API del Nodo
Central nunca pasan por ese precache — siguen yendo directo a la red.
`ActualizacionApp.jsx` avisa cuando hay versión nueva o cuando el offline
ya quedó listo, pero **nunca recarga la página sola** (para no perder un
reporte a medio llenar). Instalabilidad verificada con Playwright contra
un build real (`installabilityErrors: []`) — ver
[`docs/accesibilidad-pwa.md`](docs/accesibilidad-pwa.md) para el detalle y
cómo repetir la verificación.

## Alerta sísmica

`AlertaSismica.jsx` (en Inicio) consulta `GET /api/v1/eventos-sismicos/alerta`
del Nodo Central y muestra un resumen en español sencillo de la actividad
sísmica reciente, generado con Groq (gratis) cuando hay llave configurada,
o con una plantilla determinística si no — nunca inventa daños ni
instrucciones de seguridad, y siempre remite a fuentes oficiales (SGC, Cruz
Roja) para eso. Solo aparece si hay sismos registrados en los últimos 7
días; si no hay ninguno, no se muestra nada. El panel del coordinador
(`ListaNecesidades.jsx`) tiene el mismo patrón para un resumen de qué
atender primero.

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
- El service worker de la PWA (ver arriba) solo cachea el shell estático de
  la app — la primera carga sigue necesitando conexión, igual que antes.
