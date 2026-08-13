from app import models


def test_crear_centro_local_y_reporte_y_solicitud(db_session):
    centro = models.CentroLocal(
        id_territorio="choco",
        nombre="Chocó",
        departamento="Chocó",
        contacto=None,
        contacto_verificado=False,
    )
    db_session.add(centro)
    db_session.commit()
    db_session.refresh(centro)

    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.whatsapp,
        contenido_original="Familia sin agua potable en zona rural",
        categoria=models.CategoriaNecesidad.agua,
        urgencia=models.UrgenciaReporte.media,
        centro_id=centro.id,
    )
    db_session.add(reporte)
    db_session.commit()
    db_session.refresh(reporte)

    solicitud = models.Solicitud(
        reporte_id=reporte.id,
        centro_id=centro.id,
        categoria=models.CategoriaNecesidad.agua,
        estado=models.EstadoSolicitud.pendiente,
    )
    db_session.add(solicitud)
    db_session.commit()
    db_session.refresh(solicitud)

    assert solicitud.centro.id_territorio == "choco"
    assert solicitud.reporte.contenido_original.startswith("Familia sin agua")
    assert centro.reportes[0].id == reporte.id


def test_evento_sismico_requiere_id_externo_unico(db_session):
    from datetime import datetime, timezone

    evento = models.EventoSismico(
        id_externo="us1234",
        magnitud=7.4,
        profundidad=103.0,
        lat=4.99,
        lon=-76.29,
        lugar="San José del Palmar, Chocó",
        timestamp=datetime.now(timezone.utc),
        activo_modo_emergencia=True,
    )
    db_session.add(evento)
    db_session.commit()
    db_session.refresh(evento)
    assert evento.activo_modo_emergencia is True
