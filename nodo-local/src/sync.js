import * as api from './api.js'
import * as db from './db.js'

/**
 * Intenta sincronizar todas las acciones pendientes en la cola (reportes y
 * entregas registrados offline). Cada acción se marca 'sincronizado' o
 * 'error' individualmente — una falla no bloquea el resto de la cola, y
 * las que quedan en error se reintentan en la próxima llamada.
 */
export async function sincronizarPendientes() {
  const pendientes = await db.listarPendientes()
  let sincronizados = 0
  let fallidos = 0

  if (pendientes.length === 0) {
    return { sincronizados, fallidos }
  }

  const sesion = await db.obtenerSesion()

  for (const accion of pendientes) {
    try {
      if (accion.tipo === 'reporte') {
        await api.crearReporte(accion.payload)
      } else if (accion.tipo === 'colectivo') {
        await api.crearColectivo(accion.payload)
      } else if (accion.tipo === 'entrega') {
        if (!sesion) {
          throw new Error('No hay sesión activa para sincronizar esta entrega')
        }
        await api.registrarEntrega(accion.payload.centroId, accion.payload.categoria, sesion.token)
      } else {
        throw new Error(`Tipo de acción desconocido: ${accion.tipo}`)
      }
      await db.marcarSincronizado(accion.id)
      sincronizados += 1
    } catch (error) {
      await db.marcarError(accion.id, error.message)
      fallidos += 1
    }
  }

  return { sincronizados, fallidos }
}
