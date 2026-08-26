# PWA instalable y accesibilidad del mapa

Este documento resume dos mejoras hechas sobre `nodo-local`, pensadas para
el contexto real de uso: alguien en Chocó con conexión intermitente que
necesita poder abrir la app sin señal, y alguien que depende de teclado o
lector de pantalla para reportar una necesidad o encontrar un centro.
Ninguna de las dos toca el modelo de datos, la lógica de sincronización ni
las reglas de verificación humana — son cambios de presentación y de
capa de red estática.

## 1. App instalable (PWA)

### Qué se agregó

- **`vite-plugin-pwa`** (`nodo-local/vite.config.js`), estrategia
  `generateSW` (Workbox), que genera en el build:
  - `dist/manifest.json` — nombre, iconos, colores de marca
    (`background_color`/`theme_color` = paleta de `index.css`),
    `display: standalone`, `start_url`/`scope: "/"`.
  - `dist/sw.js` — precachea el shell de la app (HTML, JS, CSS e iconos
    del build) para que cargue sin conexión después de la primera visita.
- **Iconos** en `public/icons/`: `icon-192.png`, `icon-512.png` (purpose
  `any`), `icon-maskable-512.png` (con margen de seguridad para Android),
  `apple-touch-icon.png` y favicons. Son un marcador de mapa simple sobre
  el morado de marca (`--accent`), generados localmente, sin dependencias
  externas.
- **`src/components/ActualizacionApp.jsx`**: aviso mínimo que aparece
  cuando hay una versión nueva del service worker o cuando el offline ya
  quedó listo. Usa `registerType: 'prompt'` a propósito — **nunca recarga
  la página sola**. Si recargara automáticamente, alguien llenando un
  reporte offline podría perder lo escrito.

### Qué NO toca

El service worker solo cachea archivos estáticos del build
(`globPatterns` en `vite.config.js` + `navigateFallbackDenylist` excluye
`/api/`). Las llamadas a la API del Nodo Central (`VITE_API_BASE_URL`,
normalmente otro origen) nunca pasan por el precache de Workbox — siguen
yendo directo a la red exactamente igual que antes. La cola offline
(`src/db.js`, IndexedDB) y el motor de sincronización (`src/sync.js`) no
se modificaron y sus 18 tests (`npm test`) siguen pasando sin cambios.

### Cómo se verificó

Lighthouse quitó la categoría `pwa` de sus versiones recientes (ya no
existe `--only-categories=pwa`), así que la instalabilidad se comprobó
con el mismo mecanismo que usa Chrome internamente: el comando de
DevTools Protocol `Page.getInstallabilityErrors`, vía un script de
Playwright contra `npm run build && npm run preview`. Resultado:
`installabilityErrors: []` (cero errores) — manifest válido, íconos
correctos, service worker activo y controlando la página. Una segunda
carga con la red completamente desconectada (`context.setOffline(true)`)
sirvió el shell completo desde caché, con la navegación y el contenido de
Inicio renderizados con normalidad.

Para repetir la verificación manualmente:

```bash
npm run build
npm run preview
# abrir http://localhost:4173, y en Chrome DevTools:
# Application → Manifest (debe verse sin errores)
# Application → Service Workers (debe verse "activated and is running")
```

## 2. Accesibilidad del mapa y los formularios públicos

### El problema de los marcadores de Leaflet

Los centros, reportes y sismos del mapa nacional (`MapaNacional.jsx`) se
dibujan con `CircleMarker` de `react-leaflet`, que renderiza capas
vectoriales SVG. A diferencia de un `Marker` de ícono normal, un
`CircleMarker` **no recibe foco de teclado ni tiene texto accesible** —
solo responde a clic de mouse o toque. Se confirmó con Playwright:
recorriendo el mapa con Tab real, el foco pasa del control de zoom de
Leaflet directo a los enlaces de atribución, saltándose por completo
los marcadores.

### La solución: lista paralela navegable

`src/components/ListaMapaAccesible.jsx` agrega, debajo del mapa, tres
listas (`<ul role="list">`, con `role="list"` explícito porque Safari le
quita la semántica de lista a un `<ul>` con `list-style: none`) —
Centros de coordinación, Necesidades reportadas y Sismos detectados —
con la misma información que los popups del mapa: nombre del centro,
departamento, **estado activo/inactivo** (campo `activo` que ya existía
en la API pero no se mostraba en ningún lado), pendientes, verificación
de contacto, urgencia y magnitud.

Cada fila es un `<button>` real (foco de Tab + activación con Enter o
clic, gratis por ser HTML nativo). Al activarlo, el mapa hace `flyTo`
hacia ese punto y abre su popup — un plus para quien sí ve el mapa — pero
la lista funciona igual de bien para quien nunca lo mira: toda la
información ya está en el texto del botón, no depende de ver el mapa.

Se verificó con Playwright (Tab real, sin `.focus()` programático) que el
recorrido completo de teclado es: barra de navegación → contenedor de
Leaflet → controles de zoom (`+`/`-`) → atribución → lista accesible,
con anillo de foco visible en cada parada.

### Foco visible

Se agregó una regla global en `src/index.css`:

```css
:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}
```

Solo se activa con navegación por teclado (no con clic de mouse), y el
`outline-offset` hace que el anillo caiga sobre el fondo de la página en
vez del propio color del elemento, así que se ve igual de bien sobre un
botón morado que sobre una tarjeta blanca, en modo claro y oscuro.

### Formularios públicos

- **Labels**: ya estaban bien asociados (el patrón `<label>Texto<input
  /></label>` del proyecto es válido para lectores de pantalla sin
  necesitar `id`/`htmlFor`). Se sumó `autocomplete` donde correspondía
  (`name`, `tel`, `username`, `current-password`) y `type="tel"` al
  campo de contacto de "Registrarme para ayudar", que antes era un
  `text` genérico.
- **Mensajes anunciados**: los mensajes de error y de confirmación
  (`ReportarPublico`, `RegistrarColectivo`, `Login`, `MapaNacional`,
  `Inicio`, `ListaNecesidades`) no estaban en una región `aria-live`, así
  que un lector de pantalla no los anunciaba a menos que el foco
  estuviera justo ahí. Ahora los mensajes de éxito usan
  `role="status" aria-live="polite"` y los de error `role="alert"`
  (asertivo por definición del rol).
- **Estado de conexión** (`EstadoConexion.jsx`) y la alerta sísmica
  (`AlertaSismica.jsx`) también quedaron como regiones vivas, y el botón
  de "ver detalle" de la alerta sísmica ahora expone
  `aria-expanded`/`aria-controls`.
- **Navegación**: el tab activo de `NavPublica` ahora lleva
  `aria-current="page"`.

### Contraste de color

Se midió el contraste real (fórmula de luminancia relativa de WCAG 2.1)
de cada color semántico de `index.css` contra los fondos donde se usa.
Tres no llegaban al mínimo de 4.5:1 para texto normal:

| Token | Uso | Antes | Ahora |
|---|---|---|---|
| `--warning` (claro) | botón/ícono de alerta sísmica | 2.8:1 | 4.9:1 |
| `--ok` (claro) | mensajes de confirmación | 3.9:1 | 4.8:1 |
| `--error` (oscuro) | mensajes de error | 3.0:1 | 4.6:1 |

Se ajustó solo la luminosidad de cada color (mismo tono, mismo
significado) lo mínimo necesario para pasar 4.5:1 contra `--bg` y
`--surface` en su tema correspondiente.

## Verificación final

```bash
npm run lint   # oxlint, sin errores
npm test       # 18 tests (vitest), todos verdes — cola offline y sync intactos
npm run build && npm run preview   # build de producción + smoke test manual
```
