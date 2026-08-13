const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function solicitar(ruta, opciones = {}) {
  const resp = await fetch(`${API_BASE_URL}${ruta}`, {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      ...(opciones.headers || {}),
    },
  })
  if (!resp.ok) {
    const cuerpo = await resp.text().catch(() => '')
    throw new Error(`${resp.status} ${resp.statusText}: ${cuerpo}`)
  }
  return resp.json()
}

export function listarCentros() {
  return solicitar('/api/v1/centros')
}

export function login(idTerritorio, secreto) {
  return solicitar('/api/v1/auth/token', {
    method: 'POST',
    body: JSON.stringify({ id_territorio: idTerritorio, secreto }),
  })
}

export function obtenerNecesidades(centroId) {
  return solicitar(`/api/v1/centros/${centroId}/necesidades`)
}

export function crearReporte(payload) {
  return solicitar('/api/v1/reportes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function registrarEntrega(centroId, categoria, token) {
  return solicitar(`/api/v1/centros/${centroId}/entregas`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ categoria }),
  })
}
