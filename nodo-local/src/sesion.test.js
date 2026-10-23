import { beforeEach, describe, expect, it, vi } from 'vitest'
import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import * as db from './db.js'
import * as api from './api.js'
import { asegurarSesionVigente, tokenPorVencer, vencimientoDeToken } from './sesion.js'

vi.mock('./api.js')

/** JWT de mentira: solo el payload importa, la firma nunca se valida aquí. */
function tokenFalso(segundosRestantes) {
  const payload = { exp: Math.floor(Date.now() / 1000) + segundosRestantes }
  const base64 = btoa(JSON.stringify(payload)).replace(/\+/g, '-').replace(/\//g, '_')
  return `encabezado.${base64}.firma`
}

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory()
  db._resetDbParaTests()
  vi.resetAllMocks()
})

describe('vencimientoDeToken', () => {
  it('lee el exp de un JWT', () => {
    expect(vencimientoDeToken(tokenFalso(3600))).toBeGreaterThan(Date.now())
  })

  it('devuelve null si el token no tiene forma de JWT', () => {
    expect(vencimientoDeToken('no-es-un-jwt')).toBeNull()
    expect(vencimientoDeToken(undefined)).toBeNull()
  })
})

describe('tokenPorVencer', () => {
  it('es falso para un token con horas por delante', () => {
    expect(tokenPorVencer(tokenFalso(6 * 3600))).toBe(false)
  })

  it('es verdadero dentro del margen de renovación', () => {
    expect(tokenPorVencer(tokenFalso(60))).toBe(true)
  })

  it('es verdadero para un token ya vencido', () => {
    expect(tokenPorVencer(tokenFalso(-10))).toBe(true)
  })
})

describe('asegurarSesionVigente', () => {
  it('devuelve null si no hay sesión guardada', async () => {
    expect(await asegurarSesionVigente()).toBeNull()
    expect(api.refrescarToken).not.toHaveBeenCalled()
  })

  it('no toca la red si el token todavía está lejos de vencer', async () => {
    const sesion = { centroId: 1, idTerritorio: 'risaralda-pereira', token: tokenFalso(6 * 3600), refreshToken: 'r1' }
    await db.guardarSesion(sesion)

    const resultado = await asegurarSesionVigente()

    expect(resultado.token).toBe(sesion.token)
    expect(api.refrescarToken).not.toHaveBeenCalled()
  })

  it('renueva y guarda el par nuevo cuando el token está por vencer', async () => {
    const nuevoAcceso = tokenFalso(12 * 3600)
    api.refrescarToken.mockResolvedValue({ access_token: nuevoAcceso, refresh_token: 'r2' })
    await db.guardarSesion({ centroId: 1, idTerritorio: 'risaralda-pereira', token: tokenFalso(60), refreshToken: 'r1' })

    const resultado = await asegurarSesionVigente()

    expect(api.refrescarToken).toHaveBeenCalledWith('r1')
    expect(resultado.token).toBe(nuevoAcceso)
    expect(resultado.refreshToken).toBe('r2')
    expect((await db.obtenerSesion()).refreshToken).toBe('r2')
  })

  it('cierra la sesión solo si el backend rechaza el refresco (401)', async () => {
    const error = new Error('401 Unauthorized')
    error.status = 401
    api.refrescarToken.mockRejectedValue(error)
    await db.guardarSesion({ centroId: 1, idTerritorio: 'risaralda-pereira', token: tokenFalso(60), refreshToken: 'r1' })

    expect(await asegurarSesionVigente()).toBeNull()
    expect(await db.obtenerSesion()).toBeNull()
  })

  it('conserva la sesión si el refresco falla por red', async () => {
    api.refrescarToken.mockRejectedValue(new Error('Failed to fetch'))
    const token = tokenFalso(60)
    await db.guardarSesion({ centroId: 1, idTerritorio: 'risaralda-pereira', token, refreshToken: 'r1' })

    const resultado = await asegurarSesionVigente()

    expect(resultado.token).toBe(token)
    expect(await db.obtenerSesion()).not.toBeNull()
  })

  it('respeta sesiones viejas sin token de refresco', async () => {
    await db.guardarSesion({ centroId: 1, idTerritorio: 'risaralda-pereira', token: tokenFalso(60) })

    const resultado = await asegurarSesionVigente()

    expect(resultado.centroId).toBe(1)
    expect(api.refrescarToken).not.toHaveBeenCalled()
  })
})
