export default function EstadoConexion({ enLinea, pendientes, onSincronizar }) {
  return (
    <div className={`estado-conexion ${enLinea ? 'en-linea' : 'sin-conexion'}`}>
      <span className="punto" />
      <span>{enLinea ? 'En línea' : 'Sin conexión — trabajando localmente'}</span>
      {pendientes > 0 && (
        <span className="pendientes">
          {pendientes} acción{pendientes === 1 ? '' : 'es'} pendiente{pendientes === 1 ? '' : 's'} de sincronizar
        </span>
      )}
      <button type="button" onClick={onSincronizar} disabled={!enLinea}>
        Sincronizar ahora
      </button>
    </div>
  )
}
