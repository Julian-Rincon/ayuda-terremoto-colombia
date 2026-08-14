import { useEffect, useState } from 'react'
import * as api from '../api.js'
import * as db from '../db.js'
import { sincronizarPendientes } from '../sync.js'

export default function ListaNecesidades({ sesion, enLinea, onAccionEncolada }) {
  const [necesidades, setNecesidades] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [mensaje, setMensaje] = useState(null)
  const [resumenIA, setResumenIA] = useState(null)

  useEffect(() => {
    let activo = true

    async function cargar() {
      setCargando(true)
      if (enLinea) {
        try {
          const datos = await api.obtenerNecesidades(sesion.centroId)
          if (activo) setNecesidades(datos)
          await db.cachearNecesidades(sesion.centroId, datos)
        } catch {
          const cache = await db.obtenerNecesidadesCache(sesion.centroId)
          if (activo) setNecesidades(cache)
        }
        api
          .obtenerResumenNecesidadesIA(sesion.centroId)
          .then((datos) => activo && setResumenIA(datos))
          .catch(() => {})
      } else {
        const cache = await db.obtenerNecesidadesCache(sesion.centroId)
        if (activo) setNecesidades(cache)
      }
      if (activo) setCargando(false)
    }

    cargar()
    return () => {
      activo = false
    }
  }, [sesion.centroId, enLinea])

  async function marcarEntrega(categoria) {
    setMensaje(null)
    await db.encolarAccion('entrega', { centroId: sesion.centroId, categoria })
    onAccionEncolada()
    if (navigator.onLine) {
      await sincronizarPendientes()
      onAccionEncolada()
    }
    setMensaje(`Entrega de "${categoria}" registrada.`)
  }

  if (cargando) return <p>Cargando necesidades…</p>
  if (!necesidades) return <p>Sin datos de necesidades todavía (requiere conexión la primera vez).</p>

  const categorias = Object.entries(necesidades.pendientes_por_categoria || {})

  return (
    <div className="necesidades">
      <h2>Necesidades pendientes ({necesidades.total_pendientes})</h2>
      {resumenIA && (
        <p className="resumen-ia">
          {resumenIA.resumen}
          <span className="etiqueta-estado">{resumenIA.generado_por_ia ? 'resumen por IA' : 'resumen automático'}</span>
        </p>
      )}
      {categorias.length === 0 && <p>No hay solicitudes pendientes en este centro.</p>}
      <ul>
        {categorias.map(([categoria, cantidad]) => (
          <li key={categoria}>
            <span>
              {categoria}: {cantidad}
            </span>
            <button type="button" onClick={() => marcarEntrega(categoria)}>
              Marcar entrega
            </button>
          </li>
        ))}
      </ul>
      {mensaje && <p className="mensaje">{mensaje}</p>}
    </div>
  )
}
