import { useEffect, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import * as api from '../api.js'
import ListaMapaAccesible from './ListaMapaAccesible.jsx'

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
  const [sismos, setSismos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const mapaRef = useRef(null)
  const marcadoresRef = useRef(new Map())

  useEffect(() => {
    let activo = true

    async function cargar() {
      setCargando(true)
      setError(null)
      try {
        const [listaCentros, listaReportes, listaSismos] = await Promise.all([
          api.listarCentros(),
          api.obtenerReportes(),
          api.obtenerEventosSismicos(),
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
        setSismos(listaSismos)
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

  // Registra la instancia de Leaflet de cada marcador para poder abrir su
  // popup desde la lista accesible (ver ListaMapaAccesible.jsx).
  function registrarMarcador(id) {
    return (instancia) => {
      if (instancia) marcadoresRef.current.set(id, instancia)
      else marcadoresRef.current.delete(id)
    }
  }

  // Puente entre la lista textual y el mapa: centra el mapa en el punto
  // elegido y abre su popup. Es un plus para quien sí ve el mapa — la lista
  // en sí ya contiene toda la información sin necesitar esto.
  function seleccionarEnMapa(id, posicion) {
    const [lat, lon] = posicion
    if (mapaRef.current && lat != null && lon != null) {
      mapaRef.current.flyTo([lat, lon], Math.max(mapaRef.current.getZoom(), 9), { duration: 0.75 })
    }
    marcadoresRef.current.get(id)?.openPopup()
  }

  return (
    <div className="mapa-nacional">
      <h1>Mapa del sistema</h1>
      <p className="ayuda">
        Los círculos morados son los centros de coordinación con actividad confirmada; los círculos grises son
        departamentos que ya están en el sistema pero todavía sin actividad — se activan solos si hay un sismo fuerte
        ahí, o cualquier coordinador los puede activar a mano. Los puntos de colores son necesidades reportadas — rojo
        es urgente, naranja es media. Los círculos rojos grandes son sismos detectados en los últimos días (entre
        más grande, mayor la magnitud). Toca cualquier punto para ver el detalle antes de mandar o mirar ayuda. Si
        usas teclado o lector de pantalla, la misma información está en la lista debajo del mapa.
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!cargando && (
        <>
          <div className="mapa-contenedor">
            <MapContainer
              ref={mapaRef}
              center={CENTRO_COLOMBIA}
              zoom={6}
              scrollWheelZoom
              style={{ height: '420px', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {centros.map((c) => (
                <CircleMarker
                  key={`centro-${c.id}`}
                  ref={registrarMarcador(`centro-${c.id}`)}
                  center={[c.lat, c.lon]}
                  radius={c.activo ? 12 : 7}
                  pathOptions={
                    c.activo
                      ? { color: '#7a3bff', fillColor: '#7a3bff', fillOpacity: 0.5 }
                      : { color: '#9ca3af', fillColor: '#9ca3af', fillOpacity: 0.25 }
                  }
                >
                  <Popup>
                    <strong>{c.nombre}</strong>
                    <br />
                    {c.departamento}
                    <br />
                    {c.activo ? 'Centro activo' : 'Centro inactivo'}
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
                  ref={registrarMarcador(`reporte-${r.id}`)}
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

              {sismos.map((s) => (
                <CircleMarker
                  key={`sismo-${s.id}`}
                  ref={registrarMarcador(`sismo-${s.id}`)}
                  center={[s.lat, s.lon]}
                  radius={8 + s.magnitud * 2}
                  pathOptions={{ color: '#c0392b', fillColor: '#c0392b', fillOpacity: 0.15, weight: 2 }}
                >
                  <Popup>
                    <strong>Sismo — magnitud {s.magnitud}</strong>
                    <br />
                    {s.lugar}
                    <br />
                    {new Date(s.timestamp).toLocaleString('es-CO')}
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>

          <ListaMapaAccesible centros={centros} reportes={reportes} sismos={sismos} onSeleccionar={seleccionarEnMapa} />
        </>
      )}
    </div>
  )
}
