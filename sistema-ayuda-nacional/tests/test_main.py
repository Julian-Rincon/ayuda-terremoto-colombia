import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ai_helper
from app import seed_data as seed_data_module
from app.database import Base, get_db
from app.integrations import usgs
from app.main import app


async def _usgs_loop_noop():
    return


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # clasificación determinística en tests
    monkeypatch.setenv("NODOS_SECRETO_INICIAL", "cambia-esto-en-produccion")
    monkeypatch.setattr(usgs, "escuchar_usgs_loop", _usgs_loop_noop)  # nunca llamar a la red real en tests

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    # El startup real llama get_db() directamente (no vía Depends), así que el
    # override de arriba no lo alcanza. Sembramos manualmente la misma base en
    # memoria antes de que arranque el lifespan, y anulamos la siembra real
    # para que no toque el sqlite de producción.
    real_sembrar = seed_data_module.sembrar_datos_iniciales
    monkeypatch.setattr(seed_data_module, "sembrar_datos_iniciales", lambda db: None)
    seed_session = TestingSessionLocal()
    real_sembrar(seed_session)
    seed_session.close()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_raiz_responde_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "alcance" in resp.json()


def test_seed_crea_cuatro_centros(client):
    resp = client.get("/api/v1/centros")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_crear_reporte_manual_lo_clasifica(client):
    resp = client.post("/api/v1/reportes", json={
        "contenido": "Necesitamos carpas para dormir, se nos cayó la casa",
        "zona": "Centro",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["categoria"] == "refugio"
    assert data["verificado"] is False


def test_sandbox_whatsapp_simular_crea_reporte(client):
    resp = client.post("/sandbox/whatsapp/simular", json={
        "remitente": "573009998877",
        "texto": "Familia atrapada bajo escombros, muy urgente",
    })
    assert resp.status_code == 200
    assert resp.json()["categoria"] == "rescate_escombros"
    assert resp.json()["urgencia"] == "alta"


def test_webhook_whatsapp_real_shape_sandbox_sin_firma(client):
    payload = {
        "entry": [{"changes": [{"value": {"messages": [{
            "from": "573001112233", "type": "text", "text": {"body": "Sin agua potable"},
        }]}}]}]
    }
    resp = client.post("/api/v1/webhooks/whatsapp", json=payload)
    assert resp.status_code == 200


def test_verificar_reporte_y_ver_necesidades_del_centro(client):
    centros = client.get("/api/v1/centros").json()
    centro_pereira = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    creado = client.post("/api/v1/reportes", json={"contenido": "Sin medicamentos para diabetes"}).json()

    resp = client.post(f"/api/v1/reportes/{creado['id']}/verificar", json={"centro_id": centro_pereira["id"]})
    assert resp.status_code == 200
    assert resp.json()["verificado"] is True

    necesidades = client.get(f"/api/v1/centros/{centro_pereira['id']}/necesidades")
    assert necesidades.status_code == 200
    assert necesidades.json()["total_pendientes"] == 1


def test_login_y_entrega_requiere_token(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    creado = client.post("/api/v1/reportes", json={"contenido": "Sin agua potable urgente"}).json()
    client.post(f"/api/v1/reportes/{creado['id']}/verificar", json={"centro_id": centro["id"]})

    login_resp = client.post("/api/v1/auth/token", json={
        "id_territorio": "risaralda-pereira", "secreto": "cambia-esto-en-produccion",
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    sin_token = client.post(f"/api/v1/centros/{centro['id']}/entregas", json={"categoria": "agua"})
    assert sin_token.status_code == 401

    con_token = client.post(
        f"/api/v1/centros/{centro['id']}/entregas",
        json={"categoria": "agua"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert con_token.status_code == 200


def test_sitrep_hxl_responde_csv(client):
    resp = client.get("/api/v1/sitrep.csv?formato=hxl")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


def test_eventos_sismicos_ultimo_sin_eventos_responde_null(client):
    resp = client.get("/api/v1/eventos-sismicos/ultimo")
    assert resp.status_code == 200
    assert resp.json() is None
