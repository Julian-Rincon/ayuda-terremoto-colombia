import { useEffect, useRef, useState } from 'react'
import * as api from '../api.js'
import * as db from '../db.js'

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'

function normalizar(texto) {
  return texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

// Encuentra, entre los centros ya conocidos, cuál corresponde al
// departamento que devolvió Nominatim — nunca se inventa uno nuevo acá,
// solo se sugiere entre los que ya existen en el sistema.
function encontrarCentroPorDepartamento(centros, departamento) {
  if (!departamento) return null
  const buscado = normalizar(departamento)
  return centros.find((c) => normalizar(c.departamento) === buscado) ?? null
}

export default function Login({ onLogin }) {
  const [idTerritorio, setIdTerritorio] = useState('')
  const [secreto, setSecreto] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)
  const [centrosDisponibles, setCentrosDisponibles] = useState([])
  const [detectando, setDetectando] = useState(false)
  const [zonaDetectada, setZonaDetectada] = useState(null)
  const usuarioEscribio = useRef(false)

  useEffect(() => {
    let activo = true

    api
      .listarCentros()
      .then((lista) => {
        if (activo) setCentrosDisponibles(lista)
      })
      .catch(() => {
        // Sin conexión no hay lista para sugerir ni para autocompletar, pero
        // el campo sigue siendo un texto libre — no bloquea el login.
      })

    if (!navigator.geolocation) return

    setDetectando(true)
    navigator.geolocation.getCurrentPosition(
      async (posicion) => {
        try {
          const { latitude, longitude } = posicion.coords
          const resp = await fetch(
            `${NOMINATIM_URL}?lat=${latitude}&lon=${longitude}&format=json&zoom=6&accept-language=es`,
            { headers: { Accept: 'application/json' } },
          )
          const datos = await resp.json()
          const departamento = datos?.address?.state
          if (!activo) return

          api.listarCentros().then((lista) => {
            if (!activo) return
            const centro = encontrarCentroPorDepartamento(lista, departamento)
            if (centro) {
              setZonaDetectada(centro)
              if (!usuarioEscribio.current) setIdTerritorio(centro.id_territorio)
            }
          })
        } catch {
          // Geocodificación fallida: se sigue con selección manual, sin error visible.
        } finally {
          if (activo) setDetectando(false)
        }
      },
      () => {
        if (activo) setDetectando(false)
      },
      { timeout: 8000 },
    )

    return () => {
      activo = false
    }
  }, [])

  async function handleSubmit(evento) {
    evento.preventDefault()
    setCargando(true)
    setError(null)
    try {
      const { access_token: token } = await api.login(idTerritorio, secreto)
      const centros = await api.listarCentros()
      const centro = centros.find((c) => c.id_territorio === idTerritorio)
      if (!centro) {
        throw new Error('No se encontró el centro para este id de territorio')
      }

      const sesion = { centroId: centro.id, idTerritorio, token }
      await db.guardarSesion(sesion)
      onLogin(sesion)
    } catch {
      setError('No se pudo iniciar sesión. Verifica el id de territorio y el secreto, y que haya conexión.')
    } finally {
      setCargando(false)
    }
  }

  return (
    <form className="login" onSubmit={handleSubmit}>
      <h1>Nodo Local — Iniciar sesión</h1>
      <p className="ayuda">
        Elige tu zona de la lista, o escribe su id (ej: <code>risaralda-pereira</code>, <code>choco</code>). Si das
        permiso de ubicación, la sugerimos automáticamente.
      </p>
      {detectando && (
        <p className="ayuda" role="status">
          Detectando tu zona por ubicación…
        </p>
      )}
      {zonaDetectada && !detectando && (
        <p className="ayuda" role="status">
          Detectamos que estás cerca de <strong>{zonaDetectada.nombre}</strong>. Confírmalo abajo o elige otra zona.
        </p>
      )}
      <label>
        Id de territorio
        <input
          value={idTerritorio}
          onChange={(e) => {
            usuarioEscribio.current = true
            setIdTerritorio(e.target.value)
          }}
          required
          autoComplete="username"
          list="lista-territorios"
        />
        <datalist id="lista-territorios">
          {centrosDisponibles.map((c) => (
            <option key={c.id_territorio} value={c.id_territorio}>
              {c.nombre} — {c.departamento}
            </option>
          ))}
        </datalist>
      </label>
      <label>
        Secreto
        <input
          type="password"
          value={secreto}
          onChange={(e) => setSecreto(e.target.value)}
          required
          autoComplete="current-password"
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={cargando}>
        {cargando ? 'Ingresando…' : 'Ingresar'}
      </button>
      <p className="ayuda">Necesitas conexión la primera vez. Después, la sesión queda guardada localmente.</p>
    </form>
  )
}
