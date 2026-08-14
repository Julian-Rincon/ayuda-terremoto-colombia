import NuevaSolicitudForm from './NuevaSolicitudForm.jsx'

export default function ReportarPublico() {
  return (
    <div className="reportar-publico">
      <h1>Reportar una necesidad</h1>
      <p className="ayuda">
        Cuéntanos qué hace falta y dónde — agua, comida, refugio, medicamentos, lo que sea. Un coordinador de la
        zona lo va a revisar antes de que se convierta en una solicitud activa. Puedes reportar aunque no tengas
        conexión: se guarda en tu dispositivo y se envía apenas vuelva la señal.
      </p>
      <NuevaSolicitudForm onEncolada={() => {}} />
    </div>
  )
}
