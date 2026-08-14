import { useEffect, useState } from 'react'
import * as api from '../api.js'
import * as db from '../db.js'

const ETIQUETA_ESTADO = {
  comprometido: 'Comprometido',
  en_transito: 'En tránsito',
  entregado: 'Entregado',
  cancelado: 'Cancelado',
}

export default function EnviosEnCamino({ sesion, enLinea }) {
  const [envios, setEnvios] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let activo = true

    async function cargar() {
      setCargando(true)
      if (enLinea) {
        try {
          const datos = await api.obtenerEnvios(sesion.centroId)
          if (activo) setEnvios(datos)
          await db.cachearEnvios(sesion.centroId, datos)
        } catch {
          const cache = await db.obtenerEnviosCache(sesion.centroId)
          if (activo) setEnvios(cache)
        }
      } else {
        const cache = await db.obtenerEnviosCache(sesion.centroId)
        if (activo) setEnvios(cache)
      }
      if (activo) setCargando(false)
    }

    cargar()
    return () => {
      activo = false
    }
  }, [sesion.centroId, enLinea])

  if (cargando) return null
  if (!envios || envios.length === 0) return null

  const activos = envios.filter((e) => e.estado !== 'entregado' && e.estado !== 'cancelado')
  if (activos.length === 0) return null

  return (
    <div className="envios-en-camino">
      <h2>En camino hacia este centro</h2>
      <ul>
        {activos.map((envio) => (
          <li key={envio.id}>
            <span>
              {envio.cantidad} de {envio.categoria} — desde {envio.origen}
            </span>
            <span className={`etiqueta-estado ${envio.verificado ? 'verificado' : 'sin-verificar'}`}>
              {ETIQUETA_ESTADO[envio.estado] ?? envio.estado}
              {!envio.verificado && ' (sin verificar)'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
