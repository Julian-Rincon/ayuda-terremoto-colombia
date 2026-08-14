from app import models, seed_data


def test_sembrar_datos_iniciales_crea_cuatro_centros(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    centros = db_session.query(models.CentroLocal).all()
    ids_territorio = {c.id_territorio for c in centros}
    assert ids_territorio == {"risaralda-pereira", "choco", "caldas", "valle"}


def test_sembrar_datos_iniciales_es_idempotente(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.CentroLocal).count() == 4


def test_centros_no_verificados_no_tienen_contacto_inventado(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    choco = db_session.query(models.CentroLocal).filter_by(id_territorio="choco").first()
    assert choco.contacto is None
    assert choco.contacto_verificado is False


def test_cada_centro_tiene_credencial(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.NodoCredencial).count() == 4


def test_cada_centro_tiene_coordenadas_para_el_mapa(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    centros = db_session.query(models.CentroLocal).all()
    for centro in centros:
        assert centro.lat is not None
        assert centro.lon is not None
