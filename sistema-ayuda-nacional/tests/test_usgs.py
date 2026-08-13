import httpx
import pytest

from app import models
from app.integrations import usgs

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
