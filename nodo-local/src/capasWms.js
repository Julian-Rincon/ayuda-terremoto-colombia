/**
 * Capas WMS opcionales (GeoServer + PostGIS, ver
 * sistema-ayuda-nacional/docs/geoserver-postgis.md).
 *
 * Sin VITE_WMS_URL no hay capas y el mapa queda exactamente como estaba: el
 * nodo local nunca depende de que exista un GeoServer detrás.
 */

export const CAPAS_WMS_POR_DEFECTO = 'ayuda:capa_centros:Centros (WMS)'

/**
 * Convierte la configuración "espacio:capa:Etiqueta visible", separada por
 * comas, en la lista que consume el control de capas de Leaflet.
 */
export function parsearCapasWms(url, capas) {
  if (!url) return []
  return (capas || CAPAS_WMS_POR_DEFECTO)
    .split(',')
    .map((entrada) => entrada.trim())
    .filter(Boolean)
    .map((entrada) => {
      const partes = entrada.split(':')
      const nombre = partes.slice(0, 2).join(':')
      // Sin etiqueta explícita se muestra el nombre técnico de la capa.
      const etiqueta = partes.length > 2 ? partes.slice(2).join(':').trim() : nombre
      return {
        nombre,
        etiqueta,
        visible: false, // se prenden a mano: nadie debería esperar tiles sin pedirlas
      }
    })
}

export const WMS_URL = import.meta.env.VITE_WMS_URL || ''
export const CAPAS_WMS = parsearCapasWms(WMS_URL, import.meta.env.VITE_WMS_CAPAS)
