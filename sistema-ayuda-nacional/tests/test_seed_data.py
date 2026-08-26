from app import models, seed_data
from app.colombia import DEPARTAMENTOS_COLOMBIA


def test_sembrar_datos_iniciales_crea_los_4_centros_reales(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    centros = db_session.query(models.CentroLocal).all()
    ids_territorio = {c.id_territorio for c in centros}
    assert {"risaralda-pereira", "choco", "caldas", "valle"} <= ids_territorio


def test_sembrar_datos_iniciales_cubre_los_33_departamentos(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    ids_territorio = {c.id_territorio for c in db_session.query(models.CentroLocal).all()}
    esperados = {d["id_territorio"] for d in DEPARTAMENTOS_COLOMBIA}
    assert ids_territorio == esperados
    assert len(ids_territorio) == 33


def test_sembrar_datos_iniciales_solo_4_centros_quedan_activos(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    activos = {c.id_territorio for c in db_session.query(models.CentroLocal).filter_by(activo=True).all()}
    assert activos == {"risaralda-pereira", "choco", "caldas", "valle"}


def test_departamentos_dormidos_no_tienen_contacto_ni_estan_activos(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    santander = db_session.query(models.CentroLocal).filter_by(id_territorio="santander").first()
    assert santander is not None
    assert santander.activo is False
    assert santander.contacto is None
    assert santander.contacto_verificado is False


def test_sembrar_datos_iniciales_es_idempotente(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.CentroLocal).count() == 33


def test_centros_no_verificados_no_tienen_contacto_inventado(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    choco = db_session.query(models.CentroLocal).filter_by(id_territorio="choco").first()
    assert choco.contacto is None
    assert choco.contacto_verificado is False


def test_cada_centro_tiene_credencial(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.NodoCredencial).count() == 33


def test_cada_centro_tiene_coordenadas_para_el_mapa(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    centros = db_session.query(models.CentroLocal).all()
    for centro in centros:
        assert centro.lat is not None
        assert centro.lon is not None


def test_siembra_colectivos_oficiales_ya_verificados(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    colectivos = db_session.query(models.Colectivo).all()
    nombres = {c.nombre for c in colectivos}
    assert "Cruz Roja Colombiana — Seccional Pereira" in nombres
    assert "Hospital Universitario San Jorge — Banco de Sangre" in nombres
    assert all(c.verificado for c in colectivos)


def test_sembrar_datos_iniciales_no_duplica_colectivos(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.Colectivo).count() == 2
