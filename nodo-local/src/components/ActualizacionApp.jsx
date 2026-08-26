import { useRegisterSW } from 'virtual:pwa-register/react'

/**
 * Aviso mínimo de service worker: no recarga la página sola en ningún caso
 * (registerType: 'prompt' en vite.config.js) para no perder un formulario a
 * medio llenar. Solo cachea el shell de la app (JS/CSS/HTML/iconos) — no
 * toca las llamadas a la API ni la cola offline de IndexedDB (src/db.js,
 * src/sync.js), que siguen funcionando exactamente igual con o sin este
 * service worker.
 */
export default function ActualizacionApp() {
  const {
    needRefresh: [needRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW()

  if (needRefresh) {
    return (
      <div className="actualizacion-app" role="status" aria-live="polite">
        <span>Hay una versión nueva de la app disponible.</span>
        <button type="button" onClick={() => updateServiceWorker(true)}>
          Actualizar ahora
        </button>
      </div>
    )
  }

  if (offlineReady) {
    return (
      <div className="actualizacion-app actualizacion-app--info" role="status" aria-live="polite">
        <span>Listo — esta app ya puede usarse sin conexión.</span>
        <button type="button" onClick={() => setOfflineReady(false)} aria-label="Cerrar aviso">
          ✕
        </button>
      </div>
    )
  }

  return null
}
