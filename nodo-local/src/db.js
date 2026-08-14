import { openDB } from 'idb'

const DB_NAME = 'nodo-local-db'
const DB_VERSION = 2

let dbPromise = null

function getDb() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db, oldVersion) {
        if (oldVersion < 1) {
          db.createObjectStore('auth')
          db.createObjectStore('necesidades_cache')
          db.createObjectStore('outbox', { keyPath: 'id', autoIncrement: true })
        }
        if (oldVersion < 2) {
          db.createObjectStore('envios_cache')
        }
      },
    })
  }
  return dbPromise
}

// ---------- Sesión (JWT del centro autenticado) ----------

export async function guardarSesion({ centroId, idTerritorio, token }) {
  const db = await getDb()
  await db.put('auth', { centroId, idTerritorio, token }, 'sesion')
}

export async function obtenerSesion() {
  const db = await getDb()
  return (await db.get('auth', 'sesion')) ?? null
}

export async function borrarSesion() {
  const db = await getDb()
  await db.delete('auth', 'sesion')
}

// ---------- Cache de necesidades por centro (para funcionar sin conexión) ----------

export async function cachearNecesidades(centroId, data) {
  const db = await getDb()
  await db.put('necesidades_cache', data, centroId)
}

export async function obtenerNecesidadesCache(centroId) {
  const db = await getDb()
  return (await db.get('necesidades_cache', centroId)) ?? null
}

// ---------- Cache de envíos en camino por centro (para funcionar sin conexión) ----------

export async function cachearEnvios(centroId, data) {
  const db = await getDb()
  await db.put('envios_cache', data, centroId)
}

export async function obtenerEnviosCache(centroId) {
  const db = await getDb()
  return (await db.get('envios_cache', centroId)) ?? null
}

// ---------- Cola de salida (outbox) — acciones pendientes de sincronizar ----------

export async function encolarAccion(tipo, payload) {
  const db = await getDb()
  const id = await db.add('outbox', {
    tipo,
    payload,
    estado: 'pendiente',
    error: null,
    creadoEn: new Date().toISOString(),
  })
  return id
}

export async function listarPendientes() {
  const db = await getDb()
  const todas = await db.getAll('outbox')
  return todas.filter((accion) => accion.estado === 'pendiente' || accion.estado === 'error')
}

export async function marcarSincronizado(id) {
  const db = await getDb()
  const accion = await db.get('outbox', id)
  if (!accion) return
  accion.estado = 'sincronizado'
  accion.error = null
  await db.put('outbox', accion)
}

export async function marcarError(id, mensaje) {
  const db = await getDb()
  const accion = await db.get('outbox', id)
  if (!accion) return
  accion.estado = 'error'
  accion.error = mensaje
  await db.put('outbox', accion)
}

export async function contarPendientes() {
  const pendientes = await listarPendientes()
  return pendientes.length
}

// Solo para tests: fuerza un DB fresco entre casos.
export function _resetDbParaTests() {
  dbPromise = null
}
