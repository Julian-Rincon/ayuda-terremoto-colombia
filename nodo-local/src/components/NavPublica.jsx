const PESTANAS = [
  { valor: 'inicio', etiqueta: 'Inicio' },
  { valor: 'mapa', etiqueta: 'Mapa' },
  { valor: 'reportar', etiqueta: 'Reportar una necesidad' },
  { valor: 'registrarme', etiqueta: 'Registrarme para ayudar' },
  { valor: 'coordinador', etiqueta: 'Soy coordinador' },
]

export default function NavPublica({ vista, onCambiarVista }) {
  return (
    <nav className="nav-publica" aria-label="Navegación principal">
      {PESTANAS.map((p) => (
        <button
          key={p.valor}
          type="button"
          className={vista === p.valor ? 'activa' : ''}
          aria-current={vista === p.valor ? 'page' : undefined}
          onClick={() => onCambiarVista(p.valor)}
        >
          {p.etiqueta}
        </button>
      ))}
    </nav>
  )
}
