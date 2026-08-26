const ETIQUETA_URGENCIA = {
  alta: 'urgencia alta',
  media: 'urgencia media',
  baja: 'urgencia baja',
  sin_clasificar: 'urgencia sin clasificar',
}

/**
 * Alternativa textual y navegable por teclado a los marcadores del mapa
 * Leaflet. Los `CircleMarker` del mapa son elementos SVG sin foco de
 * teclado ni texto accesible por defecto — esta lista repite exactamente
 * la misma información que sus popups (nombre, departamento, estado,
 * urgencia, verificación) usando botones reales, que sí reciben foco con
 * Tab y se activan con Enter o clic. Al activarlos, el mapa se centra en
 * ese punto y abre su popup — pero la lista funciona igual de bien aunque
 * el mapa no se mire nunca.
 */
export default function ListaMapaAccesible({ centros, reportes, sismos, onSeleccionar, onActivar, activandoId }) {
  return (
    <div className="lista-mapa-accesible">
      <h2 id="lista-centros-heading">Centros de coordinación ({centros.length})</h2>
      <ul role="list" aria-labelledby="lista-centros-heading">
        {centros.length === 0 && <li className="vacio">Ningún centro con ubicación registrada todavía.</li>}
        {centros.map((c) => (
          <li key={`li-centro-${c.id}`}>
            <button type="button" onClick={() => onSeleccionar(`centro-${c.id}`, [c.lat, c.lon])}>
              <strong>{c.nombre}</strong> — {c.departamento}. {c.activo ? 'Centro activo.' : 'Centro inactivo.'}{' '}
              {c.totalPendientes != null ? `${c.totalPendientes} necesidades pendientes.` : 'Sin datos de necesidades.'}{' '}
              {c.contacto_verificado && c.contacto ? `Contacto verificado: ${c.contacto}.` : 'Contacto sin verificar todavía.'}
            </button>
            {!c.activo && onActivar && (
              <button
                type="button"
                className="activar-zona"
                onClick={() => onActivar(c.id)}
                disabled={activandoId === c.id}
              >
                {activandoId === c.id ? 'Activando…' : `Activar ${c.nombre} a mano`}
              </button>
            )}
          </li>
        ))}
      </ul>

      <h2 id="lista-reportes-heading">Necesidades reportadas ({reportes.length})</h2>
      <ul role="list" aria-labelledby="lista-reportes-heading">
        {reportes.length === 0 && <li className="vacio">Ninguna necesidad con ubicación reportada todavía.</li>}
        {reportes.map((r) => (
          <li key={`li-reporte-${r.id}`}>
            <button type="button" onClick={() => onSeleccionar(`reporte-${r.id}`, [r.lat, r.lon])}>
              <strong>{r.categoria}</strong>, {ETIQUETA_URGENCIA[r.urgencia] ?? ETIQUETA_URGENCIA.sin_clasificar}.{' '}
              {r.resumen_ia || r.contenido_original}{' '}
              {r.verificado ? 'Confirmado por un coordinador.' : 'Todavía sin confirmar.'}
            </button>
          </li>
        ))}
      </ul>

      <h2 id="lista-sismos-heading">Sismos detectados ({sismos.length})</h2>
      <ul role="list" aria-labelledby="lista-sismos-heading">
        {sismos.length === 0 && <li className="vacio">Ningún sismo detectado recientemente.</li>}
        {sismos.map((s) => (
          <li key={`li-sismo-${s.id}`}>
            <button type="button" onClick={() => onSeleccionar(`sismo-${s.id}`, [s.lat, s.lon])}>
              Magnitud {s.magnitud} — {s.lugar} — {new Date(s.timestamp).toLocaleString('es-CO')}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
