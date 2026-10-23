# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El proyecto no publica versiones etiquetadas: lo que se mantiene es `main`.

## Sin publicar

### Agregado

- **WhatsApp conectable por quien despliegue.** Handshake de verificación que
  Meta exige (`GET /api/v1/webhooks/whatsapp`), acuse de recibo opcional
  hacia quien escribe, y aviso en el arranque si la configuración quedó a
  medias. Se conecta un número propio con cuatro variables de entorno, sin
  tocar código — [guía](sistema-ayuda-nacional/docs/whatsapp-meta.md).
- **`GET /api/v1/config/integraciones`** — qué corre en modo real y qué en
  sandbox en un despliegue, sin devolver ningún secreto.
- **Renovación automática de JWT.** El login entrega acceso (12 h) y refresco
  (30 días) con rotación en cada uso; el nodo local renueva solo al recuperar
  conexión, cada 30 minutos y antes de vaciar la cola offline.
- **`GET /salud`** — consulta la base y responde 503 si no contesta, para
  monitoreo externo. Con health check en Render y workflow de disponibilidad.
- **`docker compose up`** levanta PostGIS, backend y PWA juntos.
- **Capas WMS/WFS** sobre PostGIS servidas por GeoServer, como vistas de las
  tablas reales. Opcionales: sin `VITE_WMS_URL` el mapa queda igual.
- **`SECURITY.md`** — canal privado de reporte, alcance, datos personales
  campo por campo, y la política de no manejar dinero.
- **Guías**: monitoreo, GeoServer + PostGIS, conexión de WhatsApp.
- Diagramas de flujo en los tres READMEs.

### Corregido

- **`GET /api/v1/reportes` exponía el teléfono de quien reportó por
  WhatsApp.** El endpoint es público a propósito (la cola de verificación
  debe ser auditable), pero devolvía `id_externo`, que para ese canal es el
  número de quien escribió. El número se sigue guardando; ya no sale por la
  API ni por el WebSocket.

### Seguridad

- **PyJWT 2.13 → 2.15**: 15 vulnerabilidades conocidas en la librería que
  valida los tokens de autenticación. Con esto, `pip-audit` sobre el backend
  y `npm audit` sobre el frontend dan cero.
- **El guardia de producción ahora exige un `JWT_SECRET` de 32 bytes.**
  Antes solo verificaba que no fuera el valor de ejemplo, así que un
  `JWT_SECRET=clave123` pasaba — cambiado, pero rompible por fuerza bruta
  (RFC 7518 §3.2).
- Vitest 3 → 5 en desarrollo, por vulnerabilidades en `@vitest/mocker` y
  `tinypool`.

### Cambiado

- APIs deprecadas reemplazadas: `datetime.utcnow()` (con fecha de
  eliminación) por `app/tiempo.ahora_utc`, `@app.on_event` por `lifespan`,
  `Query.get()` por `Session.get()`, `class Config` por `ConfigDict`. La
  suite pasó de 3.985 advertencias a 3, todas de dependencias externas.

## Antes de este registro

El historial anterior está en los mensajes de commit, que explican el porqué
de cada cambio. Hitos: cobertura de los 33 departamentos con activación
automática por USGS, migración de SQLite a Postgres, PWA instalable y
accesible por teclado, pruebas de carga, CI con pytest y Vitest.
