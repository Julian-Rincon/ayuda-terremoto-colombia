"""
Pipeline de asignación (planoidea.md §5), adaptado para recursos en especie:
no reparte presupuesto (no hay donaciones en este sistema — ver spec §1),
ordena atención humana por urgencia y antigüedad.
"""
from sqlalchemy.orm import Session

from . import models

PESO_URGENCIA = {
    models.UrgenciaReporte.alta: 3,
    models.UrgenciaReporte.media: 2,
    models.UrgenciaReporte.baja: 1,
    models.UrgenciaReporte.sin_clasificar: 1,
}


def crear_solicitud_desde_reporte(db: Session, reporte: models.ReporteCiudadano) -> models.Solicitud:
    """
    Convierte un ReporteCiudadano YA VERIFICADO por un humano en una Solicitud
    formal asignada a su CentroLocal.
    """
    if not reporte.verificado:
        raise ValueError("No se puede crear una solicitud desde un reporte sin verificar")
    if not reporte.centro_id:
        raise ValueError("El reporte no tiene centro local asignado")

    solicitud = models.Solicitud(
        reporte_id=reporte.id,
        centro_id=reporte.centro_id,
        categoria=reporte.categoria,
        estado=models.EstadoSolicitud.pendiente,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


def priorizar_solicitudes_pendientes(db: Session) -> list[models.Solicitud]:
    """Ordena las solicitudes pendientes: mayor urgencia primero, luego más antiguas primero."""
    pendientes = (
        db.query(models.Solicitud)
        .filter(models.Solicitud.estado == models.EstadoSolicitud.pendiente)
        .all()
    )

    def clave_prioridad(s: models.Solicitud):
        urgencia = s.reporte.urgencia if s.reporte else models.UrgenciaReporte.sin_clasificar
        peso = PESO_URGENCIA.get(urgencia, 1)
        return (-peso, s.creado_en)

    return sorted(pendientes, key=clave_prioridad)
