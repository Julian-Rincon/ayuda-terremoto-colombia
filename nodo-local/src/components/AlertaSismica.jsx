import { useEffect, useState } from 'react'
import * as api from '../api.js'

function tiempoRelativo(timestampISO) {
  const minutos = Math.round((Date.now() - new Date(timestampISO).getTime()) / 60000)
  if (minutos < 60) return `hace ${minutos} min`
  const horas = Math.round(minutos / 60)
  if (horas < 24) return `hace ${horas} h`
  const dias = Math.round(horas / 24)
  return `hace ${dias} día${dias === 1 ? '' : 's'}`
}

export default function AlertaSismica() {
  const [alerta, setAlerta] = useState(null)
  const [expandido, setExpandido] = useState(false)

  useEffect(() => {
    let activo = true
    api
      .obtenerAlertaSismica()
      .then((datos) => activo && setAlerta(datos))
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  if (!alerta || alerta.eventos.length === 0) return null

  return (
    <div className="alerta-sismica">
      <div className="alerta-sismica-encabezado">
        <span className="alerta-sismica-icono">⚠</span>
        <p>{alerta.resumen}</p>
      </div>
      <button type="button" onClick={() => setExpandido((v) => !v)}>
        {expandido ? 'Ocultar detalle' : `Ver los ${alerta.eventos.length} sismos detectados`}
      </button>
      {expandido && (
        <ul>
          {alerta.eventos.map((e) => (
            <li key={e.id}>
              Magnitud {e.magnitud} — {e.lugar} — {tiempoRelativo(e.timestamp)}
            </li>
          ))}
        </ul>
      )}
      <p className="alerta-sismica-fuente">
        Fuente: USGS (datos sísmicos en tiempo real).
        {alerta.generado_por_ia ? ' Resumen generado por IA a partir de estos datos.' : ''} Para información oficial
        verificada, consulta el Servicio Geológico Colombiano o Cruz Roja.
      </p>
    </div>
  )
}
