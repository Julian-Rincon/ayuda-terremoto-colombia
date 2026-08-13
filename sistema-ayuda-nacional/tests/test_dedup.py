from datetime import datetime, timedelta

from app import dedup, models


def _crear_reporte(db, contenido, categoria=models.CategoriaNecesidad.agua, zona=None, creado_en=None):
    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.web,
        contenido_original=contenido,
        categoria=categoria,
        zona=zona,
        creado_en=creado_en or datetime.utcnow(),
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


def test_encuentra_duplicado_con_texto_muy_similar_misma_categoria(db_session):
    original = _crear_reporte(db_session, "Familia sin agua potable en el barrio Cuba hace tres días")

    duplicado = dedup.encontrar_posible_duplicado(
        db_session, models.CategoriaNecesidad.agua, "Familia sin agua potable en el barrio Cuba hace 3 días"
    )

    assert duplicado is not None
    assert duplicado.id == original.id


def test_no_marca_duplicado_si_texto_es_muy_distinto(db_session):
    _crear_reporte(db_session, "Familia sin agua potable en el barrio Cuba hace tres días")

    duplicado = dedup.encontrar_posible_duplicado(
        db_session, models.CategoriaNecesidad.agua, "Se rompió una tubería en la avenida 30 de agosto"
    )

    assert duplicado is None


def test_no_marca_duplicado_si_la_categoria_es_distinta(db_session):
    _crear_reporte(db_session, "Familia sin agua potable en el barrio Cuba", categoria=models.CategoriaNecesidad.agua)

    duplicado = dedup.encontrar_posible_duplicado(
        db_session, models.CategoriaNecesidad.alimentos, "Familia sin agua potable en el barrio Cuba"
    )

    assert duplicado is None


def test_no_marca_duplicado_si_esta_fuera_de_la_ventana_de_tiempo(db_session):
    hace_tres_dias = datetime.utcnow() - timedelta(hours=72)
    _crear_reporte(db_session, "Familia sin agua potable en el barrio Cuba", creado_en=hace_tres_dias)

    duplicado = dedup.encontrar_posible_duplicado(
        db_session, models.CategoriaNecesidad.agua, "Familia sin agua potable en el barrio Cuba", ventana_horas=48
    )

    assert duplicado is None


def test_misma_zona_refuerza_pero_no_es_obligatoria(db_session):
    original = _crear_reporte(db_session, "Necesitamos agua potable urgente", zona="Cuba")

    duplicado = dedup.encontrar_posible_duplicado(
        db_session, models.CategoriaNecesidad.agua, "Necesitamos agua potable urgente", zona="Cuba"
    )

    assert duplicado is not None
    assert duplicado.id == original.id


def test_marcar_posible_duplicado_asigna_el_id_del_original(db_session):
    original = _crear_reporte(db_session, "Familia atrapada bajo escombros, urgente", categoria=models.CategoriaNecesidad.rescate_escombros)

    nuevo = models.ReporteCiudadano(
        canal=models.CanalReporte.whatsapp,
        contenido_original="Familia atrapada bajo escombros, muy urgente",
        categoria=models.CategoriaNecesidad.rescate_escombros,
    )
    dedup.marcar_posible_duplicado(db_session, nuevo)

    assert nuevo.posible_duplicado_de_id == original.id


def test_marcar_posible_duplicado_deja_none_si_no_hay_coincidencia(db_session):
    nuevo = models.ReporteCiudadano(
        canal=models.CanalReporte.whatsapp,
        contenido_original="Reporte completamente distinto sin precedentes",
        categoria=models.CategoriaNecesidad.otro,
    )
    dedup.marcar_posible_duplicado(db_session, nuevo)

    assert nuevo.posible_duplicado_de_id is None
