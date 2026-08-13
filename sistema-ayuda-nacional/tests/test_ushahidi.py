import httpx
import pytest

from app import ai_helper, models
from app.integrations import ushahidi


@pytest.mark.asyncio
async def test_obtener_posts_usa_fixture_si_no_hay_instancia_configurada(monkeypatch):
    monkeypatch.setattr(ushahidi, "USHAHIDI_BASE_URL", "")
    posts = await ushahidi.obtener_posts_publicados()
    assert posts == ushahidi.POSTS_FIXTURE


@pytest.mark.asyncio
async def test_obtener_posts_llama_instancia_real_si_esta_configurada(monkeypatch):
    monkeypatch.setattr(ushahidi, "USHAHIDI_BASE_URL", "https://mi-instancia.ushahidi.io")

    async def _mock_get(self, url, **kwargs):
        assert url == "https://mi-instancia.ushahidi.io/api/v5/posts"
        return httpx.Response(200, json={"results": [{"id": "post-real-1"}]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)
    posts = await ushahidi.obtener_posts_publicados()
    assert posts == [{"id": "post-real-1"}]


@pytest.mark.asyncio
async def test_sincronizar_ushahidi_crea_reportes_nuevos_y_evita_duplicados(db_session, monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    monkeypatch.setattr(ushahidi, "USHAHIDI_BASE_URL", "")

    nuevos = await ushahidi.sincronizar_ushahidi(db_session)
    assert len(nuevos) == len(ushahidi.POSTS_FIXTURE)
    assert db_session.query(models.ReporteCiudadano).count() == len(ushahidi.POSTS_FIXTURE)

    nuevos_segunda_vez = await ushahidi.sincronizar_ushahidi(db_session)
    assert nuevos_segunda_vez == []
    assert db_session.query(models.ReporteCiudadano).count() == len(ushahidi.POSTS_FIXTURE)
