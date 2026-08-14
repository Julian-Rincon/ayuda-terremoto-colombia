import { useEffect, useState } from 'react'
import * as api from '../api.js'
import AlertaSismica from './AlertaSismica.jsx'

export default function Inicio() {
  const [resumen, setResumen] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let activo = true
    api
      .obtenerResumenNacional()
      .then((datos) => activo && setResumen(datos))
      .catch(() => activo && setError('No se pudo cargar el panorama nacional. ¿Hay conexión?'))
    return () => {
      activo = false
    }
  }, [])

  return (
    <div className="inicio">
      <h1>Ayuda Terremoto Colombia</h1>
      <p className="ayuda">
        Conectamos a quien necesita ayuda con quien puede darla, tras el terremoto del 10 de agosto de 2026. Este
        panorama se actualiza con lo que reportan las comunidades y confirman los coordinadores en cada zona — no
        maneja donaciones ni dinero.
      </p>

      <AlertaSismica />

      {error && <p className="error">{error}</p>}

      {resumen && (
        <div className="resumen-nacional">
          <div className="tarjeta">
            <span className="numero">{resumen.total_centros}</span>
            <span className="etiqueta">zonas trabajando en el sistema</span>
          </div>
          <div className="tarjeta">
            <span className="numero">{resumen.total_reportes}</span>
            <span className="etiqueta">necesidades reportadas</span>
          </div>
          <div className="tarjeta">
            <span className="numero">{resumen.total_solicitudes_pendientes}</span>
            <span className="etiqueta">confirmadas y esperando ayuda</span>
          </div>
          <div className="tarjeta">
            <span className="numero">{resumen.total_colectivos_verificados}</span>
            <span className="etiqueta">grupos de ayuda confirmados</span>
          </div>
          <div className="tarjeta">
            <span className="numero">{resumen.total_envios_verificados_en_camino}</span>
            <span className="etiqueta">envíos ya en camino</span>
          </div>
        </div>
      )}

      {resumen && Object.keys(resumen.solicitudes_pendientes_por_categoria).length > 0 && (
        <div className="necesidades-nacionales">
          <h2>Qué se está necesitando ahora mismo</h2>
          <ul>
            {Object.entries(resumen.solicitudes_pendientes_por_categoria).map(([categoria, cantidad]) => (
              <li key={categoria}>
                <span>{categoria}</span>
                <span className="cantidad">{cantidad}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="ayuda pie">
        ¿Quieres ayudar? Usa "Registrarme para ayudar" arriba. ¿Necesitas ayuda o conoces a alguien que la necesita?
        Usa "Reportar una necesidad".
      </p>
    </div>
  )
}
