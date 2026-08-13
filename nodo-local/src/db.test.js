import { beforeEach, describe, expect, it } from 'vitest'
import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import * as db from './db.js'

beforeEach(() => {
  // Base de datos limpia en cada test.
  globalThis.indexedDB = new IDBFactory()
  db._resetDbParaTests()
})

describe('sesión', () => {
  it('guarda y recupera la sesión del centro autenticado', async () => {
    await db.guardarSesion({ centroId: 1, idTerritorio: 'risaralda-pereira', token: 'jwt-de-prueba' })
    const sesion = await db.obtenerSesion()
    expect(sesion).toEqual({ centroId: 1, idTerritorio: 'risaralda-pereira', token: 'jwt-de-prueba' })
  })

  it('retorna null si no hay sesión guardada', async () => {
    const sesion = await db.obtenerSesion()
    expect(sesion).toBeNull()
  })

  it('borra la sesión', async () => {
    await db.guardarSesion({ centroId: 1, idTerritorio: 'choco', token: 'x' })
    await db.borrarSesion()
    expect(await db.obtenerSesion()).toBeNull()
  })
})

describe('cache de necesidades', () => {
  it('guarda y recupera el cache de necesidades por centro', async () => {
    await db.cachearNecesidades(1, { total_pendientes: 3, pendientes_por_categoria: { agua: 3 } })
    const cache = await db.obtenerNecesidadesCache(1)
    expect(cache.total_pendientes).toBe(3)
  })

  it('retorna null si no hay cache para ese centro', async () => {
    expect(await db.obtenerNecesidadesCache(99)).toBeNull()
  })
})

describe('outbox', () => {
  it('encola una acción como pendiente', async () => {
    const id = await db.encolarAccion('reporte', { contenido: 'Sin agua' })
    const pendientes = await db.listarPendientes()
    expect(pendientes).toHaveLength(1)
    expect(pendientes[0].id).toBe(id)
    expect(pendientes[0].tipo).toBe('reporte')
    expect(pendientes[0].estado).toBe('pendiente')
  })

  it('marcar como sincronizado la saca de la lista de pendientes', async () => {
    const id = await db.encolarAccion('entrega', { categoria: 'agua' })
    await db.marcarSincronizado(id)
    expect(await db.listarPendientes()).toHaveLength(0)
  })

  it('marcar error mantiene la acción visible para reintentar', async () => {
    const id = await db.encolarAccion('reporte', { contenido: 'test' })
    await db.marcarError(id, 'sin conexión')
    const pendientes = await db.listarPendientes()
    expect(pendientes).toHaveLength(1)
    expect(pendientes[0].estado).toBe('error')
    expect(pendientes[0].error).toBe('sin conexión')
  })

  it('contarPendientes cuenta pendientes y en error, no los sincronizados', async () => {
    const id1 = await db.encolarAccion('reporte', {})
    const id2 = await db.encolarAccion('reporte', {})
    await db.encolarAccion('reporte', {})
    await db.marcarSincronizado(id1)
    await db.marcarError(id2, 'boom')
    expect(await db.contarPendientes()).toBe(2)
  })
})
