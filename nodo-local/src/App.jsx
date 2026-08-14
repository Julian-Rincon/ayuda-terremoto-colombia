import { useCallback, useEffect, useState } from 'react'
import * as db from './db.js'
import { sincronizarPendientes } from './sync.js'
import { useOnlineStatus } from './hooks/useOnlineStatus.js'
import NavPublica from './components/NavPublica.jsx'
import Inicio from './components/Inicio.jsx'
import ReportarPublico from './components/ReportarPublico.jsx'
import RegistrarColectivo from './components/RegistrarColectivo.jsx'
import Login from './components/Login.jsx'
import Dashboard from './components/Dashboard.jsx'
import './App.css'

export default function App() {
  const [sesion, setSesion] = useState(undefined) // undefined = cargando, null = sin sesión
  const [pendientes, setPendientes] = useState(0)
  const [vista, setVista] = useState('inicio')
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
    setVista('inicio')
  }

  function handleLogin(nuevaSesion) {
    setSesion(nuevaSesion)
    setVista('coordinador')
  }

  if (sesion === undefined) {
    return <div className="cargando">Cargando…</div>
  }

  return (
    <div className="app">
      <NavPublica vista={vista} onCambiarVista={setVista} />

      {vista === 'inicio' && <Inicio />}
      {vista === 'reportar' && <ReportarPublico />}
      {vista === 'registrarme' && <RegistrarColectivo />}
      {vista === 'coordinador' &&
        (sesion ? (
          <Dashboard
            sesion={sesion}
            enLinea={enLinea}
            pendientes={pendientes}
            onAccionEncolada={actualizarPendientes}
            onSincronizar={sincronizar}
            onLogout={handleLogout}
          />
        ) : (
          <Login onLogin={handleLogin} />
        ))}
    </div>
  )
}
