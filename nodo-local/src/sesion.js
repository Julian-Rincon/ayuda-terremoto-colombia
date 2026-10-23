import * as api from './api.js'
import * as db from './db.js'

/** Margen antes del `exp` del JWT: se renueva antes de que caduque, no después. */
export const MARGEN_RENOVACION_MS = 5 * 60 * 1000

/**
 * Lee el `exp` de un JWT sin verificar la firma — eso lo hace el backend. Aquí
 * solo sirve para saber cuándo conviene pedir uno nuevo.
 * Devuelve null si el token no tiene forma de JWT o no trae `exp`.
 */
export function vencimientoDeToken(token) {
  if (typeof token !== 'string') return null
  const partes = token.split('.')
  if (partes.length !== 3) return null
  try {
    const payload = JSON.parse(atob(partes[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

export function tokenPorVencer(token, ahora = Date.now()) {
  const vence = vencimientoDeToken(token)
  if (vence === null) return false // sin `exp` legible no forzamos un refresco a ciegas
  return vence - ahora <= MARGEN_RENOVACION_MS
}

/**
 * Devuelve la sesión con un token de acceso utilizable, renovándolo con el
 * token de refresco si está por vencer.
 *
 * Nunca tumba la sesión por un fallo de red: sin conexión devuelve la sesión
 * tal cual y el trabajo sigue encolado offline. Solo borra la sesión cuando el
 * backend rechaza el refresco (401), que es la señal real de "hay que volver a
 * entrar".
 */
export async function asegurarSesionVigente(sesion) {
  const actual = sesion ?? (await db.obtenerSesion())
  if (!actual) return null
  if (!actual.refreshToken) return actual // sesión anterior al refresco: sigue valiendo hasta que expire
  if (!tokenPorVencer(actual.token)) return actual

  try {
    const datos = await api.refrescarToken(actual.refreshToken)
    const renovada = {
      ...actual,
      token: datos.access_token,
      refreshToken: datos.refresh_token,
    }
    await db.guardarSesion(renovada)
    return renovada
  } catch (error) {
    if (error.status === 401) {
      await db.borrarSesion()
      return null
    }
    return actual // caída de red: se reintenta en la próxima oportunidad
  }
}
