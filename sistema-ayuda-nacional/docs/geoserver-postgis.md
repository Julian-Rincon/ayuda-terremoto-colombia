# Capas WMS/WFS reales con GeoServer + PostGIS

Hasta ahora el mapa del nodo local dibujaba los centros como marcadores sobre
OpenStreetMap: los datos viajan como JSON y los pinta el navegador. Eso alcanza
para 33 centros, pero no sirve para que **otra entidad** consuma la información
desde su propio visor (QGIS, ArcGIS, un portal de la UNGRD) ni para capas que
crezcan a miles de puntos.

Esta guía deja las mismas tablas publicadas como servicios OGC estándar —
**WMS** (imágenes del mapa) y **WFS** (los datos como GeoJSON o shapefile) —
sin duplicar la base ni cambiar cómo funciona la app.

> El nodo local **no depende** de esto. Sin `VITE_WMS_URL` el mapa queda
> exactamente igual que antes.

## Levantarlo

El perfil `geo` de `docker-compose.yml` agrega GeoServer junto a la base, que
ya es PostGIS:

```bash
cp .env.docker.example .env
docker compose --profile geo up --build -d

# 1. Crear las vistas geoespaciales sobre las tablas de la app
docker compose exec -T base-de-datos psql -U ayuda -d ayuda_terremoto \
    -f - < sistema-ayuda-nacional/geo/capas.sql

# 2. Publicarlas en GeoServer (idempotente: se puede repetir)
./sistema-ayuda-nacional/geo/publicar_capas.sh
```

GeoServer tarda ~1 minuto en responder la primera vez. Consola web:
<http://localhost:8080/geoserver> (usuario y clave en `.env`).

## Qué se publica

[`geo/capas.sql`](../geo/capas.sql) define tres **vistas**, no tablas. La
fuente de verdad sigue siendo lo que escribe la API: las capas reflejan el
estado real sin un proceso de sincronización que se pueda quedar atrás.

| Capa | Contenido | Nota |
|---|---|---|
| `capa_centros` | Centros territoriales, con `solicitudes_pendientes` | Permite tematizar por presión de demanda |
| `capa_reportes_verificados` | Reportes ciudadanos **ya verificados** | Los no verificados quedan fuera a propósito: una capa pública no difunde ubicaciones sin confirmar |
| `capa_eventos_sismicos` | Epicentros USGS de los últimos 30 días | |

## Consumirlas

```bash
# Catálogo de capas
curl "http://localhost:8080/geoserver/ayuda/wms?service=WMS&version=1.3.0&request=GetCapabilities"

# Los centros como GeoJSON (WFS)
curl "http://localhost:8080/geoserver/ayuda/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=ayuda:capa_centros&outputFormat=application/json"

# Una imagen del mapa (WMS)
curl -o centros.png "http://localhost:8080/geoserver/ayuda/wms?service=WMS&version=1.1.1&request=GetMap&layers=ayuda:capa_centros&bbox=-82,-5,-66,14&width=800&height=800&srs=EPSG:4326&format=image/png"
```

En **QGIS**: Capa → Añadir capa WMS/WMTS (o WFS) → Nueva conexión →
`http://localhost:8080/geoserver/ayuda/wms`.

## Verlas en el nodo local

Con GeoServer arriba, el mapa nacional ofrece las capas en un control arriba a
la derecha. Se configura en `nodo-local/.env`:

```
VITE_WMS_URL=http://localhost:8080/geoserver/ayuda/wms
VITE_WMS_CAPAS=ayuda:capa_centros:Centros (WMS),ayuda:capa_eventos_sismicos:Sismos 30 días
```

Las capas arrancan **apagadas**: nadie en terreno debería esperar a que
descarguen tiles que no pidió. Vite congela estas variables en tiempo de
build, así que hay que reconstruir (`npm run build`) para que tomen efecto.

## Para un despliegue real

- **Clave de admin.** `GEOSERVER_ADMIN_PASSWORD` por defecto es de desarrollo.
  Rotarla antes de exponer el puerto 8080.
- **Usuario de solo lectura.** El script conecta GeoServer a Postgres con el
  usuario de la app. En producción conviene un rol con `SELECT` únicamente
  sobre las tres vistas.
- **No exponer GeoServer directo a internet** sin un proxy delante que limite
  a `/ayuda/wms` y `/ayuda/wfs`. La consola web y la API REST no deberían ser
  públicas.
- **`capa_reportes_verificados` sigue siendo dato sensible** aunque esté
  verificado: son ubicaciones de personas pidiendo ayuda. Publicarla hacia
  afuera es una decisión de la coordinación, no una opción técnica por
  defecto — ver [SECURITY.md](../../SECURITY.md).
