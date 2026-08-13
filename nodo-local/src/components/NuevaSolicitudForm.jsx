import { useState } from 'react'
import * as db from '../db.js'
import { sincronizarPendientes } from '../sync.js'

export default function NuevaSolicitudForm({ onEncolada }) {
  const [contenido, setContenido] = useState('')
  const [zona, setZona] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  async function handleSubmit(evento) {
    evento.preventDefault()
    setEnviando(true)
    setMensaje(null)
    try {
      await db.encolarAccion('reporte', { contenido, zona: zona || null, canal: 'manual' })
      setContenido('')
      setZona('')
      onEncolada()

      if (navigator.onLine) {
        const resultado = await sincronizarPendientes()
        onEncolada()
        setMensaje(resultado.sincronizados > 0 ? 'Reporte enviado.' : 'Reporte guardado localmente — se reintentará.')
      } else {
        setMensaje('Reporte guardado localmente — se enviará cuando vuelva la conexión.')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="nueva-solicitud" onSubmit={handleSubmit}>
      <h2>Registrar un reporte</h2>
      <label>
        Descripción
        <textarea value={contenido} onChange={(e) => setContenido(e.target.value)} required minLength={3} rows={3} />
      </label>
      <label>
        Zona / barrio (opcional)
        <input value={zona} onChange={(e) => setZona(e.target.value)} />
      </label>
      <button type="submit" disabled={enviando || contenido.trim().length < 3}>
        {enviando ? 'Guardando…' : 'Registrar'}
      </button>
      {mensaje && <p className="mensaje">{mensaje}</p>}
    </form>
  )
}
