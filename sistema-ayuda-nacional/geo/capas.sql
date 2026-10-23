-- Capas geoespaciales publicables por GeoServer (issue #7).
--
-- Son VISTAS, no tablas: la fuente de verdad sigue siendo lo que escribe la
-- API, y las capas WMS/WFS reflejan el estado real sin un proceso de ETL que
-- se pueda quedar atrás. Idempotente: se puede correr en cada despliegue.
--
--   psql "$DATABASE_URL" -f geo/capas.sql

CREATE EXTENSION IF NOT EXISTS postgis;

-- Centros de coordinación territorial, con el conteo de necesidades
-- pendientes para poder tematizar el mapa por presión de demanda.
CREATE OR REPLACE VIEW capa_centros AS
SELECT
    c.id,
    c.id_territorio,
    c.nombre,
    c.departamento,
    c.activo,
    c.contacto_verificado,
    COALESCE(p.pendientes, 0)::int AS solicitudes_pendientes,
    ST_SetSRID(ST_MakePoint(c.lon, c.lat), 4326)::geometry(Point, 4326) AS geom
FROM centros_locales c
LEFT JOIN (
    SELECT centro_id, COUNT(*) AS pendientes
    FROM solicitudes
    WHERE estado = 'pendiente'
    GROUP BY centro_id
) p ON p.centro_id = c.id
WHERE c.lat IS NOT NULL AND c.lon IS NOT NULL;

-- Reportes ciudadanos ya verificados. Los no verificados quedan fuera a
-- propósito: una capa pública no debe difundir ubicaciones sin confirmar.
CREATE OR REPLACE VIEW capa_reportes_verificados AS
SELECT
    r.id,
    r.categoria,
    r.urgencia,
    r.canal,
    r.centro_id,
    r.creado_en,
    ST_SetSRID(ST_MakePoint(r.lon, r.lat), 4326)::geometry(Point, 4326) AS geom
FROM reportes_ciudadanos r
WHERE r.verificado IS TRUE
  AND r.lat IS NOT NULL AND r.lon IS NOT NULL;

-- Epicentros sísmicos de los últimos 30 días (USGS).
CREATE OR REPLACE VIEW capa_eventos_sismicos AS
SELECT
    e.id,
    e.id_externo,
    e.magnitud,
    e.profundidad,
    e.lugar,
    e.fuente,
    e.timestamp,
    ST_SetSRID(ST_MakePoint(e.lon, e.lat), 4326)::geometry(Point, 4326) AS geom
FROM eventos_sismicos e
WHERE e.timestamp > NOW() - INTERVAL '30 days';

-- GeoServer descubre el SRID y el tipo de geometría de una vista leyendo
-- geometry_columns, que en PostGIS 3 es a su vez una vista derivada de las
-- tablas reales — no registra vistas. Se declara a mano para que las capas
-- se publiquen sin tener que elegir SRID en la interfaz.
CREATE TABLE IF NOT EXISTS geo_metadata_capas (
    nombre_capa text PRIMARY KEY,
    srid int NOT NULL DEFAULT 4326,
    tipo_geometria text NOT NULL DEFAULT 'Point'
);

INSERT INTO geo_metadata_capas (nombre_capa) VALUES
    ('capa_centros'),
    ('capa_reportes_verificados'),
    ('capa_eventos_sismicos')
ON CONFLICT (nombre_capa) DO NOTHING;
