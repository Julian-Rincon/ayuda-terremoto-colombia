import pytest

from app import models, pipeline


def _crear_centro(db):
    centro = models.CentroLocal(id_territorio="choco", nombre="Chocó", departamento="Chocó")
    db.add(centro)
    db.commit()
    db.refresh(centro)
    return centro


def test_crear_solicitud_desde_reporte_no_verificado_lanza_error(db_session):
    centro = _crear_centro(db_session)
    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.web,
        contenido_original="test",
        categoria=models.CategoriaNecesidad.agua,
        centro_id=centro.id,
        verificado=False,
    )
    db_session.add(reporte)
    db_session.commit()
    db_session.refresh(reporte)

    with pytest.raises(ValueError):
        pipeline.crear_solicitud_desde_reporte(db_session, reporte)


def test_crear_solicitud_desde_reporte_verificado(db_session):
    centro = _crear_centro(db_session)
    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.web,
        contenido_original="test",
        categoria=models.CategoriaNecesidad.agua,
        centro_id=centro.id,
        verificado=True,
    )
    db_session.add(reporte)
    db_session.commit()
    db_session.refresh(reporte)

    solicitud = pipeline.crear_solicitud_desde_reporte(db_session, reporte)
    assert solicitud.centro_id == centro.id
    assert solicitud.categoria == models.CategoriaNecesidad.agua
    assert solicitud.estado == models.EstadoSolicitud.pendiente


def test_priorizar_solicitudes_urgencia_alta_primero(db_session):
    centro = _crear_centro(db_session)

    reporte_media = models.ReporteCiudadano(
        canal=models.CanalReporte.web, contenido_original="a",
        categoria=models.CategoriaNecesidad.agua, urgencia=models.UrgenciaReporte.media,
        centro_id=centro.id, verificado=True,
    )
    reporte_alta = models.ReporteCiudadano(
        canal=models.CanalReporte.web, contenido_original="b",
        categoria=models.CategoriaNecesidad.rescate_escombros, urgencia=models.UrgenciaReporte.alta,
        centro_id=centro.id, verificado=True,
    )
    db_session.add_all([reporte_media, reporte_alta])
    db_session.commit()
    db_session.refresh(reporte_media)
    db_session.refresh(reporte_alta)

    solicitud_media = pipeline.crear_solicitud_desde_reporte(db_session, reporte_media)
    solicitud_alta = pipeline.crear_solicitud_desde_reporte(db_session, reporte_alta)

    priorizadas = pipeline.priorizar_solicitudes_pendientes(db_session)

    assert priorizadas[0].id == solicitud_alta.id
    assert priorizadas[1].id == solicitud_media.id
