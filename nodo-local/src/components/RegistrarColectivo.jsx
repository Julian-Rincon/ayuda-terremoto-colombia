import { useState } from 'react'
import * as db from '../db.js'
import { sincronizarPendientes } from '../sync.js'

const TIPOS = [
  { valor: 'voluntariado', etiqueta: 'Voluntariado general' },
  { valor: 'logistica', etiqueta: 'Logística / transporte' },
  { valor: 'salud', etiqueta: 'Salud' },
  { valor: 'alimentos', etiqueta: 'Alimentos' },
  { valor: 'refugio', etiqueta: 'Refugio / alojamiento' },
  { valor: 'rescate', etiqueta: 'Rescate' },
  { valor: 'construccion', etiqueta: 'Construcción / reparación' },
  { valor: 'general', etiqueta: 'Otro' },
]

export default function RegistrarColectivo() {
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState('general')
  const [zonaCobertura, setZonaCobertura] = useState('')
  const [contacto, setContacto] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  async function handleSubmit(evento) {
    evento.preventDefault()
    setEnviando(true)
    setMensaje(null)
    try {
      await db.encolarAccion('colectivo', {
        nombre,
        tipo,
        zona_cobertura: zonaCobertura || null,
        contacto: contacto || null,
        descripcion: descripcion || null,
      })
      setNombre('')
      setZonaCobertura('')
      setContacto('')
      setDescripcion('')

      if (navigator.onLine) {
        await sincronizarPendientes()
      }
      setMensaje(
        'Gracias por registrarte. Un coordinador va a confirmar tus datos antes de que aparezcas disponible — así nos aseguramos de que nadie se haga pasar por ayuda legítima.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="registrar-colectivo" onSubmit={handleSubmit}>
      <h1>Registrarme para ayudar</h1>
      <p className="ayuda">
        Eres una persona, un grupo de voluntarios o una organización que quiere ayudar. Regístrate acá y un
        coordinador va a confirmar tus datos antes de conectarte con una necesidad real.
      </p>
      <label>
        Nombre (tuyo o del grupo)
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} required minLength={2} />
      </label>
      <label>
        ¿Con qué puedes ayudar?
        <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {TIPOS.map((t) => (
            <option key={t.valor} value={t.valor}>
              {t.etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label>
        Zona donde puedes ayudar (opcional)
        <input value={zonaCobertura} onChange={(e) => setZonaCobertura(e.target.value)} placeholder="Ej. Pereira, Cuba" />
      </label>
      <label>
        Contacto (teléfono o WhatsApp)
        <input value={contacto} onChange={(e) => setContacto(e.target.value)} />
      </label>
      <label>
        Cuéntanos más (opcional)
        <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={3} />
      </label>
      <button type="submit" disabled={enviando || nombre.trim().length < 2}>
        {enviando ? 'Enviando…' : 'Registrarme'}
      </button>
      {mensaje && <p className="mensaje">{mensaje}</p>}
    </form>
  )
}
