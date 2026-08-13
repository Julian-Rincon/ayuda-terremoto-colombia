import EstadoConexion from './EstadoConexion.jsx'
import ListaNecesidades from './ListaNecesidades.jsx'
import NuevaSolicitudForm from './NuevaSolicitudForm.jsx'

export default function Dashboard({ sesion, enLinea, pendientes, onAccionEncolada, onSincronizar, onLogout }) {
  return (
    <div className="dashboard">
      <header>
        <h1>Nodo Local — {sesion.idTerritorio}</h1>
        <button type="button" onClick={onLogout}>
          Cerrar sesión
        </button>
      </header>
      <EstadoConexion enLinea={enLinea} pendientes={pendientes} onSincronizar={onSincronizar} />
      <ListaNecesidades sesion={sesion} enLinea={enLinea} onAccionEncolada={onAccionEncolada} />
      <NuevaSolicitudForm onEncolada={onAccionEncolada} />
    </div>
  )
}
