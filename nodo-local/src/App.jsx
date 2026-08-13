import { useCallback, useEffect, useState } from 'react'
import * as db from './db.js'
import { sincronizarPendientes } from './sync.js'
import { useOnlineStatus } from './hooks/useOnlineStatus.js'
import Login from './components/Login.jsx'
import Dashboard from './components/Dashboard.jsx'
import './App.css'

export default function App() {
  const [sesion, setSesion] = useState(undefined) // undefined = cargando, null = sin sesión
  const [pendientes, setPendientes] = useState(0)
  const enLinea = useOnlineStatus()

  const actualizarPendientes = useCallback(async () => {
    setPendientes(await db.contarPendientes())
  }, [])

  const sincronizar = useCallback(async () => {
    if (!navigator.onLine) return
    await sincronizarPendientes()
    await actualizarPendientes()
  }, [actualizarPendientes])

  useEffect(() => {
    db.obtenerSesion().then(setSesion)
    actualizarPendientes()
  }, [actualizarPendientes])

  useEffect(() => {
    if (enLinea) sincronizar()
  }, [enLinea, sincronizar])

  async function handleLogout() {
    await db.borrarSesion()
    setSesion(null)
  }

  if (sesion === undefined) {
    return <div className="cargando">Cargando…</div>
  }

  return (
    <div className="app">
      {sesion ? (
        <Dashboard
          sesion={sesion}
          enLinea={enLinea}
          pendientes={pendientes}
          onAccionEncolada={actualizarPendientes}
          onSincronizar={sincronizar}
          onLogout={handleLogout}
        />
      ) : (
        <Login onLogin={setSesion} />
      )}
    </div>
  )
}
