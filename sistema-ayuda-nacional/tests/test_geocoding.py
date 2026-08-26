import httpx
import pytest

from app.integrations import geocoding


def test_slug_quita_tildes_y_espacios():
    assert geocoding.slug("Valle del Cauca") == "valle-del-cauca"
    assert geocoding.slug("Chocó") == "choco"
    assert geocoding.slug("Bogotá D.C.") == "bogota-d-c"


@pytest.mark.asyncio
async def test_departamento_desde_coordenadas_devuelve_departamento_y_slug(monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(
            200,
            json={"address": {"state": "Santander", "town": "Aratoca"}},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    resultado = await geocoding.departamento_desde_coordenadas(6.737, -73.0596)
    assert resultado == {"departamento": "Santander", "id_territorio": "santander"}


@pytest.mark.asyncio
async def test_departamento_desde_coordenadas_sin_state_retorna_none(monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"address": {}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    resultado = await geocoding.departamento_desde_coordenadas(0.0, 0.0)
    assert resultado is None


@pytest.mark.asyncio
async def test_departamento_desde_coordenadas_nunca_lanza_si_la_red_falla(monkeypatch):
    async def _mock_get(self, url, **kwargs):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    resultado = await geocoding.departamento_desde_coordenadas(6.737, -73.0596)
    assert resultado is None
