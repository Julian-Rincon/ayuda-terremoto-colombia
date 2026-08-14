import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import * as api from '../api.js'

const CENTRO_COLOMBIA = [4.5, -74.3]

const COLOR_URGENCIA = {
  alta: '#c0392b',
  media: '#d9822b',
  baja: '#6b6375',
  sin_clasificar: '#9ca3af',
}

export default function MapaNacional() {
  const [centros, setCentros] = useState([])
  const [reportes, setReportes] = useState([])
  const [ultimoSismo, setUltimoSismo] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let activo = true

    async function cargar() {
      setCargando(true)
      setError(null)
      try {
        const [listaCentros, listaReportes, sismo] = await Promise.all([
          api.listarCentros(),
          api.obtenerReportes(),
          api.obtenerUltimoEventoSismico(),
        ])

        const centrosConNecesidades = await Promise.all(
          listaCentros
            .filter((c) => c.lat != null && c.lon != null)
            .map(async (c) => {
              try {
                const necesidades = await api.obtenerNecesidades(c.id)
                return { ...c, totalPendientes: necesidades.total_pendientes }
              } catch {
                return { ...c, totalPendientes: null }
              }
            }),
        )

        if (!activo) return
        setCentros(centrosConNecesidades)
        setReportes(listaReportes.filter((r) => r.lat != null && r.lon != null))
        setUltimoSismo(sismo)
      } catch {
        if (activo) setError('No se pudo cargar el mapa. ¿Hay conexión?')
      } finally {
        if (activo) setCargando(false)
      }
    }

    cargar()
    return () => {
      activo = false
    }
  }, [])

  return (
    <div className="mapa-nacional">
      <h1>Mapa del sistema</h1>
      <p className="ayuda">
        Los círculos azules son los centros de coordinación. Los puntos de colores son necesidades reportadas — rojo
        es urgente, naranja es media. Si hay un sismo detectado, aparece marcado como el epicentro. Toca cualquier
        punto para ver el detalle antes de mandar o mirar ayuda.
      </p>

      {error && <p className="error">{error}</p>}

      {!cargando && (
        <div className="mapa-contenedor">
          <MapContainer center={CENTRO_COLOMBIA} zoom={6} scrollWheelZoom style={{ height: '420px', width: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {centros.map((c) => (
              <CircleMarker
                key={`centro-${c.id}`}
                center={[c.lat, c.lon]}
                radius={12}
                pathOptions={{ color: '#7a3bff', fillColor: '#7a3bff', fillOpacity: 0.5 }}
              >
                <Popup>
                  <strong>{c.nombre}</strong>
                  <br />
                  {c.departamento}
                  <br />
                  {c.totalPendientes != null ? `${c.totalPendientes} necesidades pendientes` : 'Sin datos'}
                  <br />
                  {c.contacto_verificado && c.contacto ? `Contacto: ${c.contacto}` : 'Contacto sin verificar todavía'}
                </Popup>
              </CircleMarker>
            ))}

            {reportes.map((r) => (
              <CircleMarker
                key={`reporte-${r.id}`}
                center={[r.lat, r.lon]}
                radius={6}
                pathOptions={{
                  color: COLOR_URGENCIA[r.urgencia] ?? COLOR_URGENCIA.sin_clasificar,
                  fillColor: COLOR_URGENCIA[r.urgencia] ?? COLOR_URGENCIA.sin_clasificar,
                  fillOpacity: r.verificado ? 0.8 : 0.35,
                }}
              >
                <Popup>
                  <strong>{r.categoria}</strong> ({r.urgencia})
                  <br />
                  {r.resumen_ia || r.contenido_original}
                  <br />
                  {r.verificado ? 'Confirmado por un coordinador' : 'Todavía sin confirmar'}
                </Popup>
              </CircleMarker>
            ))}

            {ultimoSismo && (
              <CircleMarker
                center={[ultimoSismo.lat, ultimoSismo.lon]}
                radius={14}
                pathOptions={{ color: '#c0392b', fillColor: '#c0392b', fillOpacity: 0.2, weight: 2 }}
              >
                <Popup>
                  <strong>Sismo detectado</strong>
                  <br />
                  Magnitud {ultimoSismo.magnitud} — {ultimoSismo.lugar}
                </Popup>
              </CircleMarker>
            )}
          </MapContainer>
        </div>
      )}
    </div>
  )
}
