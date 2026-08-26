import httpx
import pytest

from app import models
from app.integrations import geocoding, usgs

FEATURE_SANTANDER_M49 = {
    "type": "Feature",
    "id": "us_test_santander",
    "properties": {"mag": 4.9, "place": "4 km E of Jordán, Colombia", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-73.0596, 6.737, 159.9]},
}

FEATURE_COLOMBIA_M74 = {
    "type": "Feature",
    "id": "us_test_74",
    "properties": {"mag": 7.4, "place": "San José del Palmar, Chocó", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-76.29, 4.99, 103.0]},
}

FEATURE_FUERA_DE_COLOMBIA = {
    "type": "Feature",
    "id": "us_test_otro_pais",
    "properties": {"mag": 7.8, "place": "Chile", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-70.6, -33.4, 50.0]},
}

FEATURE_COLOMBIA_LEVE = {
    "type": "Feature",
    "id": "us_test_leve",
    "properties": {"mag": 3.1, "place": "Bogotá", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-74.08, 4.71, 10.0]},
}


@pytest.mark.asyncio
async def test_escuchar_usgs_activa_modo_emergencia_para_sismo_colombiano_fuerte(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_M74]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)

    assert len(eventos) == 1
    assert eventos[0].activo_modo_emergencia is True
    assert db_session.query(models.EventoSismico).filter_by(id_externo="us_test_74").count() == 1


@pytest.mark.asyncio
async def test_escuchar_usgs_ignora_sismos_fuera_de_colombia(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_FUERA_DE_COLOMBIA]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)
    assert eventos == []


@pytest.mark.asyncio
async def test_escuchar_usgs_no_activa_emergencia_bajo_el_umbral(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_LEVE]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)
    assert len(eventos) == 1
    assert eventos[0].activo_modo_emergencia is False


@pytest.mark.asyncio
async def test_escuchar_usgs_no_duplica_eventos_ya_guardados(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_M74]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    await usgs.escuchar_usgs_una_vez(db_session)
    eventos_segunda_pasada = await usgs.escuchar_usgs_una_vez(db_session)

    assert eventos_segunda_pasada == []
    assert db_session.query(models.EventoSismico).count() == 1


@pytest.mark.asyncio
async def test_escuchar_usgs_nunca_lanza_si_la_red_falla(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)
    assert eventos == []


@pytest.mark.asyncio
async def test_sismo_fuerte_activa_centro_dormido_existente(db_session, monkeypatch):
    dormido = models.CentroLocal(
        id_territorio="santander", nombre="Santander", departamento="Santander",
        contacto=None, contacto_verificado=False, activo=False, lat=7.12, lon=-73.12,
    )
    db_session.add(dormido)
    db_session.commit()
    db_session.refresh(dormido)

    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_SANTANDER_M49]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    async def _geocode(lat, lon):
        return {"departamento": "Santander", "id_territorio": "santander"}

    monkeypatch.setattr(geocoding, "departamento_desde_coordenadas", _geocode)

    await usgs.escuchar_usgs_una_vez(db_session)

    db_session.refresh(dormido)
    assert dormido.activo is True
    assert dormido.contacto is None  # activar nunca inventa contacto
    assert db_session.query(models.CentroLocal).filter_by(id_territorio="santander").count() == 1
    assert db_session.query(models.NodoCredencial).filter_by(centro_id=dormido.id).count() == 1


@pytest.mark.asyncio
async def test_sismo_fuerte_en_zona_sin_cobertura_crea_centro_automatico(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_SANTANDER_M49]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    async def _geocode(lat, lon):
        return {"departamento": "Santander", "id_territorio": "santander"}

    monkeypatch.setattr(geocoding, "departamento_desde_coordenadas", _geocode)

    await usgs.escuchar_usgs_una_vez(db_session)

    centro = db_session.query(models.CentroLocal).filter_by(id_territorio="santander").first()
    assert centro is not None
    assert centro.contacto is None
    assert centro.contacto_verificado is False
    assert db_session.query(models.NodoCredencial).filter_by(centro_id=centro.id).count() == 1


@pytest.mark.asyncio
async def test_sismo_fuerte_no_duplica_centro_si_la_zona_ya_tiene_uno(db_session, monkeypatch):
    db_session.add(models.CentroLocal(id_territorio="santander", nombre="Santander", departamento="Santander"))
    db_session.commit()

    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_SANTANDER_M49]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    async def _geocode(lat, lon):
        return {"departamento": "Santander", "id_territorio": "santander"}

    monkeypatch.setattr(geocoding, "departamento_desde_coordenadas", _geocode)

    await usgs.escuchar_usgs_una_vez(db_session)

    assert db_session.query(models.CentroLocal).filter_by(id_territorio="santander").count() == 1


@pytest.mark.asyncio
async def test_sismo_debil_no_crea_centro_automatico(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_LEVE]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)
    llamado = {"veces": 0}

    async def _geocode_no_deberia_llamarse(lat, lon):
        llamado["veces"] += 1
        return {"departamento": "Cundinamarca", "id_territorio": "cundinamarca"}

    monkeypatch.setattr(geocoding, "departamento_desde_coordenadas", _geocode_no_deberia_llamarse)

    await usgs.escuchar_usgs_una_vez(db_session)

    assert llamado["veces"] == 0
    assert db_session.query(models.CentroLocal).count() == 0


@pytest.mark.asyncio
async def test_sismo_fuerte_si_falla_geocodificacion_no_crea_centro_ni_lanza(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_SANTANDER_M49]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    async def _geocode_falla(lat, lon):
        return None

    monkeypatch.setattr(geocoding, "departamento_desde_coordenadas", _geocode_falla)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)

    assert len(eventos) == 1  # el evento sí se guarda, solo no se abre centro
    assert db_session.query(models.CentroLocal).count() == 0
