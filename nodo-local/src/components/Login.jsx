import { useState } from 'react'
import * as api from '../api.js'
import * as db from '../db.js'

export default function Login({ onLogin }) {
  const [idTerritorio, setIdTerritorio] = useState('')
  const [secreto, setSecreto] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)

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
        El id de territorio es, por ejemplo: <code>risaralda-pereira</code>, <code>choco</code>,{' '}
        <code>caldas</code> o <code>valle</code>.
      </p>
      <label>
        Id de territorio
        <input value={idTerritorio} onChange={(e) => setIdTerritorio(e.target.value)} required />
      </label>
      <label>
        Secreto
        <input type="password" value={secreto} onChange={(e) => setSecreto(e.target.value)} required />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={cargando}>
        {cargando ? 'Ingresando…' : 'Ingresar'}
      </button>
      <p className="ayuda">Necesitas conexión la primera vez. Después, la sesión queda guardada localmente.</p>
    </form>
  )
}
