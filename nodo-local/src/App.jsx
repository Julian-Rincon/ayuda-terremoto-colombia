import { useCallback, useEffect, useState } from 'react'
import * as db from './db.js'
import { sincronizarPendientes } from './sync.js'
import { asegurarSesionVigente } from './sesion.js'
import { useOnlineStatus } from './hooks/useOnlineStatus.js'
import NavPublica from './components/NavPublica.jsx'
import Inicio from './components/Inicio.jsx'
import MapaNacional from './components/MapaNacional.jsx'
import ReportarPublico from './components/ReportarPublico.jsx'
import RegistrarColectivo from './components/RegistrarColectivo.jsx'
import Login from './components/Login.jsx'
import Dashboard from './components/Dashboard.jsx'
import ActualizacionApp from './components/ActualizacionApp.jsx'
import './App.css'

const INTERVALO_RENOVACION_MS = 30 * 60 * 1000

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

  // Renovación automática del JWT: al recuperar conexión y cada 30 minutos
  // mientras la pestaña siga abierta. Un turno de coordinación dura más que el
  // token de acceso, y nadie debería quedar fuera a mitad de una entrega.
  const haySesion = Boolean(sesion)
  useEffect(() => {
    if (!haySesion || !enLinea) return undefined

    let cancelado = false
    async function renovar() {
      const vigente = await asegurarSesionVigente()
      if (cancelado) return
      // Conservar el objeto anterior cuando el token no cambió: así este
      // efecto no se reinicia a sí mismo en cada renovación.
      setSesion((anterior) =>
        vigente && anterior && vigente.token === anterior.token ? anterior : vigente,
      )
    }

    renovar()
    const intervalo = setInterval(renovar, INTERVALO_RENOVACION_MS)
    return () => {
      cancelado = true
      clearInterval(intervalo)
    }
  }, [haySesion, enLinea])

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
    return (
      <div className="cargando" role="status" aria-live="polite">
        Cargando…
      </div>
    )
  }

  return (
    <div className="app">
      <ActualizacionApp />
      <NavPublica vista={vista} onCambiarVista={setVista} />

      {vista === 'inicio' && <Inicio />}
      {vista === 'mapa' && <MapaNacional />}
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
