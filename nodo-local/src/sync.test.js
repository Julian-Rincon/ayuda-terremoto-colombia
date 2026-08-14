import { beforeEach, describe, expect, it, vi } from 'vitest'
import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import * as db from './db.js'
import * as api from './api.js'
import { sincronizarPendientes } from './sync.js'

vi.mock('./api.js')

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory()
  db._resetDbParaTests()
  vi.resetAllMocks()
})

describe('sincronizarPendientes', () => {
  it('no hace nada si no hay pendientes', async () => {
    const resultado = await sincronizarPendientes()
    expect(resultado).toEqual({ sincronizados: 0, fallidos: 0 })
  })

  it('sincroniza un reporte pendiente y lo marca como sincronizado', async () => {
    api.crearReporte.mockResolvedValue({ id: 1 })
    await db.encolarAccion('reporte', { contenido: 'Sin agua potable' })

    const resultado = await sincronizarPendientes()

    expect(resultado).toEqual({ sincronizados: 1, fallidos: 0 })
    expect(api.crearReporte).toHaveBeenCalledWith({ contenido: 'Sin agua potable' })
    expect(await db.listarPendientes()).toHaveLength(0)
  })

  it('deja el reporte en estado error si la sincronización falla', async () => {
    api.crearReporte.mockRejectedValue(new Error('500 Internal Server Error'))
    await db.encolarAccion('reporte', { contenido: 'test' })

    const resultado = await sincronizarPendientes()

    expect(resultado).toEqual({ sincronizados: 0, fallidos: 1 })
    const pendientes = await db.listarPendientes()
    expect(pendientes[0].estado).toBe('error')
    expect(pendientes[0].error).toContain('500')
  })

  it('sincroniza una entrega usando el token de la sesión guardada', async () => {
    await db.guardarSesion({ centroId: 1, idTerritorio: 'risaralda-pereira', token: 'jwt-123' })
    api.registrarEntrega.mockResolvedValue({ id: 5 })
    await db.encolarAccion('entrega', { centroId: 1, categoria: 'agua' })

    const resultado = await sincronizarPendientes()

    expect(resultado).toEqual({ sincronizados: 1, fallidos: 0 })
    expect(api.registrarEntrega).toHaveBeenCalledWith(1, 'agua', 'jwt-123')
  })

  it('sincroniza un registro de colectivo pendiente', async () => {
    api.crearColectivo.mockResolvedValue({ id: 9 })
    await db.encolarAccion('colectivo', { nombre: 'Voluntarios Cuba' })

    const resultado = await sincronizarPendientes()

    expect(resultado).toEqual({ sincronizados: 1, fallidos: 0 })
    expect(api.crearColectivo).toHaveBeenCalledWith({ nombre: 'Voluntarios Cuba' })
  })

  it('marca error en una entrega si no hay sesión activa', async () => {
    await db.encolarAccion('entrega', { centroId: 1, categoria: 'agua' })

    const resultado = await sincronizarPendientes()

    expect(resultado).toEqual({ sincronizados: 0, fallidos: 1 })
    expect(api.registrarEntrega).not.toHaveBeenCalled()
  })

  it('reintenta acciones que quedaron en estado error', async () => {
    api.crearReporte.mockRejectedValueOnce(new Error('sin red'))
    await db.encolarAccion('reporte', { contenido: 'test' })
    await sincronizarPendientes()

    api.crearReporte.mockResolvedValueOnce({ id: 1 })
    const segundoIntento = await sincronizarPendientes()

    expect(segundoIntento).toEqual({ sincronizados: 1, fallidos: 0 })
    expect(await db.listarPendientes()).toHaveLength(0)
  })
})
