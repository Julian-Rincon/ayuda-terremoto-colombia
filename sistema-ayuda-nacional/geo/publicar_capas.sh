#!/usr/bin/env bash
# Publica las capas de geo/capas.sql en GeoServer vía su API REST (issue #7).
#
# Idempotente: se puede correr las veces que haga falta. Lo que ya existe se
# deja como está, lo que falta se crea.
#
#   docker compose --profile geo up -d
#   docker compose exec -T base-de-datos psql -U ayuda -d ayuda_terremoto \
#       -f - < sistema-ayuda-nacional/geo/capas.sql
#   ./sistema-ayuda-nacional/geo/publicar_capas.sh
#
# Variables (con los valores de docker-compose.yml por defecto):
#   GEOSERVER_URL, GEOSERVER_ADMIN_USER, GEOSERVER_ADMIN_PASSWORD
#   PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
set -euo pipefail

GEOSERVER_URL=${GEOSERVER_URL:-http://localhost:8080/geoserver}
GS_USER=${GEOSERVER_ADMIN_USER:-admin}
GS_PASS=${GEOSERVER_ADMIN_PASSWORD:-geoserver-local}

# Host visto DESDE el contenedor de GeoServer, no desde la máquina: por eso
# es el nombre del servicio de compose y el puerto interno 5432.
PG_HOST=${PG_HOST:-base-de-datos}
PG_PORT=${PG_PORT:-5432}
PG_DB=${PG_DB:-ayuda_terremoto}
PG_USER=${PG_USER:-ayuda}
PG_PASSWORD=${PG_PASSWORD:-ayuda-local}

ESPACIO=ayuda
ALMACEN=postgis-ayuda
CAPAS=(capa_centros capa_reportes_verificados capa_eventos_sismicos)

gs() { curl -sS -u "$GS_USER:$GS_PASS" -H 'Content-Type: application/json' "$@"; }
existe() { [ "$(curl -sS -o /dev/null -w '%{http_code}' -u "$GS_USER:$GS_PASS" "$1")" = "200" ]; }

echo "GeoServer: $GEOSERVER_URL"
if ! existe "$GEOSERVER_URL/rest/about/version.json"; then
  echo "ERROR: GeoServer no responde o las credenciales no sirven." >&2
  exit 1
fi

if existe "$GEOSERVER_URL/rest/workspaces/$ESPACIO.json"; then
  echo "· espacio de trabajo '$ESPACIO' ya existe"
else
  gs -X POST -d "{\"workspace\":{\"name\":\"$ESPACIO\"}}" "$GEOSERVER_URL/rest/workspaces" >/dev/null
  echo "+ espacio de trabajo '$ESPACIO' creado"
fi

if existe "$GEOSERVER_URL/rest/workspaces/$ESPACIO/datastores/$ALMACEN.json"; then
  echo "· almacén '$ALMACEN' ya existe"
else
  gs -X POST -d "{
    \"dataStore\": {
      \"name\": \"$ALMACEN\",
      \"connectionParameters\": { \"entry\": [
        {\"@key\":\"dbtype\",\"\$\":\"postgis\"},
        {\"@key\":\"host\",\"\$\":\"$PG_HOST\"},
        {\"@key\":\"port\",\"\$\":\"$PG_PORT\"},
        {\"@key\":\"database\",\"\$\":\"$PG_DB\"},
        {\"@key\":\"user\",\"\$\":\"$PG_USER\"},
        {\"@key\":\"passwd\",\"\$\":\"$PG_PASSWORD\"},
        {\"@key\":\"schema\",\"\$\":\"public\"},
        {\"@key\":\"Expose primary keys\",\"\$\":\"true\"}
      ]}
    }
  }" "$GEOSERVER_URL/rest/workspaces/$ESPACIO/datastores" >/dev/null
  echo "+ almacén '$ALMACEN' creado"
fi

for capa in "${CAPAS[@]}"; do
  if existe "$GEOSERVER_URL/rest/workspaces/$ESPACIO/datastores/$ALMACEN/featuretypes/$capa.json"; then
    echo "· capa '$capa' ya publicada"
    continue
  fi
  # Colombia continental + insular, en EPSG:4326.
  gs -X POST -d "{
    \"featureType\": {
      \"name\": \"$capa\",
      \"nativeName\": \"$capa\",
      \"srs\": \"EPSG:4326\",
      \"nativeBoundingBox\": {\"minx\":-82,\"maxx\":-66,\"miny\":-5,\"maxy\":14,\"crs\":\"EPSG:4326\"},
      \"latLonBoundingBox\": {\"minx\":-82,\"maxx\":-66,\"miny\":-5,\"maxy\":14,\"crs\":\"EPSG:4326\"},
      \"enabled\": true
    }
  }" "$GEOSERVER_URL/rest/workspaces/$ESPACIO/datastores/$ALMACEN/featuretypes" >/dev/null
  echo "+ capa '$capa' publicada"
done

echo
echo "Listo. Puntos de acceso:"
echo "  WMS  $GEOSERVER_URL/$ESPACIO/wms?service=WMS&version=1.3.0&request=GetCapabilities"
echo "  WFS  $GEOSERVER_URL/$ESPACIO/wfs?service=WFS&version=2.0.0&request=GetCapabilities"
echo "  GeoJSON de una capa:"
echo "       $GEOSERVER_URL/$ESPACIO/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=$ESPACIO:capa_centros&outputFormat=application/json"
