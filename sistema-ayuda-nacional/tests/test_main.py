import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import ai_helper
from app import seed_data as seed_data_module
from app.database import Base, get_db
from app.integrations import usgs
from app.main import app
from app.rate_limit import limiter
from tests.conftest import build_test_engine, reset_schema


async def _usgs_loop_noop():
    return


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # clasificación determinística en tests
    monkeypatch.setenv("NODOS_SECRETO_INICIAL", "cambia-esto-en-produccion")
    monkeypatch.setattr(usgs, "escuchar_usgs_loop", _usgs_loop_noop)  # nunca llamar a la red real en tests
    limiter.reset()  # cada test empieza con su propio cupo, sin arrastrar el de tests anteriores

    # Mismo motor que usa tests/conftest.py: SQLite en memoria por defecto,
    # o el Postgres real de DATABASE_URL si está exportada (ver ese archivo).
    engine = build_test_engine()
    reset_schema(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
        test_client.db_sessionmaker = TestingSessionLocal  # para sembrar datos sin endpoint (ej. EventoSismico)
        yield test_client
    app.dependency_overrides.clear()

    # Deja el esquema limpio: con SQLite en memoria es opcional (el engine se
    # descarta solo), pero con Postgres real (DATABASE_URL) es necesario para
    # que el siguiente test no vea datos sembrados por este.
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_raiz_responde_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "alcance" in resp.json()


def test_seed_cubre_los_33_departamentos(client):
    resp = client.get("/api/v1/centros")
    assert resp.status_code == 200
    centros = resp.json()
    assert len(centros) == 33
    assert sum(1 for c in centros if c["activo"]) == 4


def test_activar_centro_manualmente(client):
    centros = client.get("/api/v1/centros").json()
    dormido = next(c for c in centros if not c["activo"])

    resp = client.patch(f"/api/v1/centros/{dormido['id']}/activar")
    assert resp.status_code == 200
    assert resp.json()["activo"] is True

    releido = client.get("/api/v1/centros").json()
    actualizado = next(c for c in releido if c["id"] == dormido["id"])
    assert actualizado["activo"] is True


def test_activar_centro_manualmente_es_idempotente(client):
    centros = client.get("/api/v1/centros").json()
    dormido = next(c for c in centros if not c["activo"])

    client.patch(f"/api/v1/centros/{dormido['id']}/activar")
    segunda_vez = client.patch(f"/api/v1/centros/{dormido['id']}/activar")
    assert segunda_vez.status_code == 200
    assert segunda_vez.json()["activo"] is True


def test_activar_centro_inexistente_da_404(client):
    resp = client.patch("/api/v1/centros/999999/activar")
    assert resp.status_code == 404


def test_crear_reporte_manual_lo_clasifica(client):
    resp = client.post("/api/v1/reportes", json={
        "contenido": "Necesitamos carpas para dormir, se nos cayó la casa",
        "zona": "Centro",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["categoria"] == "refugio"
    assert data["verificado"] is False


def test_rate_limit_reportes_bloquea_tras_exceder_el_limite(client):
    for _ in range(10):
        resp = client.post("/api/v1/reportes", json={"contenido": "Reporte de prueba de límite"})
        assert resp.status_code == 200

    excedido = client.post("/api/v1/reportes", json={"contenido": "Este debería quedar bloqueado"})
    assert excedido.status_code == 429


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


def test_reporte_similar_queda_marcado_como_posible_duplicado(client):
    primero = client.post("/api/v1/reportes", json={
        "contenido": "Familia sin agua potable en el barrio Cuba hace tres días",
    }).json()

    segundo = client.post("/api/v1/reportes", json={
        "contenido": "Familia sin agua potable en el barrio Cuba hace 3 días",
    }).json()

    assert primero["posible_duplicado_de_id"] is None
    assert segundo["posible_duplicado_de_id"] == primero["id"]


def test_crear_envio_queda_sin_verificar_por_defecto(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    resp = client.post("/api/v1/envios", json={
        "centro_id": centro["id"], "categoria": "alimentos", "cantidad": 50, "origen": "Bogotá",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["verificado"] is False
    assert data["estado"] == "comprometido"
    assert data["cantidad"] == 50


def test_rate_limit_envios_bloquea_tras_exceder_el_limite(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    for _ in range(10):
        resp = client.post("/api/v1/envios", json={
            "centro_id": centro["id"], "categoria": "alimentos", "cantidad": 1, "origen": "Prueba de límite",
        })
        assert resp.status_code == 200

    excedido = client.post("/api/v1/envios", json={
        "centro_id": centro["id"], "categoria": "alimentos", "cantidad": 1, "origen": "Este debería quedar bloqueado",
    })
    assert excedido.status_code == 429


def test_envio_sin_verificar_no_cuenta_en_necesidades(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    client.post("/api/v1/envios", json={
        "centro_id": centro["id"], "categoria": "alimentos", "cantidad": 50, "origen": "Bogotá",
    })

    necesidades = client.get(f"/api/v1/centros/{centro['id']}/necesidades").json()
    assert necesidades["envios_verificados_por_categoria"] == {}


def test_envio_verificado_si_aparece_en_necesidades(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    envio = client.post("/api/v1/envios", json={
        "centro_id": centro["id"], "categoria": "alimentos", "cantidad": 50, "origen": "Bogotá",
    }).json()

    verificado = client.patch(f"/api/v1/envios/{envio['id']}/verificar")
    assert verificado.status_code == 200
    assert verificado.json()["verificado"] is True

    necesidades = client.get(f"/api/v1/centros/{centro['id']}/necesidades").json()
    assert necesidades["envios_verificados_por_categoria"] == {"alimentos": 50}


def test_envio_entregado_ya_no_cuenta_como_en_camino(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    envio = client.post("/api/v1/envios", json={
        "centro_id": centro["id"], "categoria": "medicamentos", "cantidad": 10, "origen": "Cruz Roja Nacional",
    }).json()
    client.patch(f"/api/v1/envios/{envio['id']}/verificar")

    actualizado = client.patch(f"/api/v1/envios/{envio['id']}/estado", json={"estado": "entregado"})
    assert actualizado.status_code == 200
    assert actualizado.json()["estado"] == "entregado"

    necesidades = client.get(f"/api/v1/centros/{centro['id']}/necesidades").json()
    assert necesidades["envios_verificados_por_categoria"] == {}


def test_listar_envios_filtra_por_centro_y_estado(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")
    otro_centro = next(c for c in centros if c["id_territorio"] == "choco")

    client.post("/api/v1/envios", json={
        "centro_id": centro["id"], "categoria": "agua", "cantidad": 20, "origen": "Bogotá",
    })
    client.post("/api/v1/envios", json={
        "centro_id": otro_centro["id"], "categoria": "agua", "cantidad": 5, "origen": "Cali",
    })

    resp = client.get(f"/api/v1/envios?centro_id={centro['id']}")
    envios = resp.json()
    assert len(envios) == 1
    assert envios[0]["origen"] == "Bogotá"


def test_registrar_colectivo_queda_sin_verificar_por_defecto(client):
    resp = client.post("/api/v1/colectivos", json={
        "nombre": "Voluntarios Cuba Pereira",
        "tipo": "logistica",
        "zona_cobertura": "Pereira - comuna Cuba",
        "contacto": "316 000 0000",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["verificado"] is False
    assert data["tipo"] == "logistica"


def test_rate_limit_colectivos_bloquea_tras_exceder_el_limite(client):
    for i in range(10):
        resp = client.post("/api/v1/colectivos", json={"nombre": f"Colectivo de prueba {i}"})
        assert resp.status_code == 200

    excedido = client.post("/api/v1/colectivos", json={"nombre": "Este debería quedar bloqueado"})
    assert excedido.status_code == 429


def test_verificar_colectivo(client):
    creado = client.post("/api/v1/colectivos", json={"nombre": "Cruz Roja seccional demo"}).json()
    resp = client.patch(f"/api/v1/colectivos/{creado['id']}/verificar")
    assert resp.status_code == 200
    assert resp.json()["verificado"] is True


def test_listar_colectivos_filtra_por_verificado(client):
    sin_verificar = client.post("/api/v1/colectivos", json={"nombre": "Colectivo A"}).json()
    verificado = client.post("/api/v1/colectivos", json={"nombre": "Colectivo B"}).json()
    client.patch(f"/api/v1/colectivos/{verificado['id']}/verificar")

    resp = client.get("/api/v1/colectivos?verificado=true")
    ids = [c["id"] for c in resp.json()]
    assert verificado["id"] in ids
    assert sin_verificar["id"] not in ids


def test_resumen_nacional_agrega_a_traves_de_todos_los_centros(client):
    centros = client.get("/api/v1/centros").json()
    pereira = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")
    choco = next(c for c in centros if c["id_territorio"] == "choco")

    resumen_antes = client.get("/api/v1/resumen").json()

    r1 = client.post("/api/v1/reportes", json={"contenido": "Sin agua potable"}).json()
    r2 = client.post("/api/v1/reportes", json={"contenido": "Sin comida hace dias"}).json()
    client.post(f"/api/v1/reportes/{r1['id']}/verificar", json={"centro_id": pereira["id"]})
    client.post(f"/api/v1/reportes/{r2['id']}/verificar", json={"centro_id": choco["id"]})

    envio = client.post("/api/v1/envios", json={
        "centro_id": pereira["id"], "categoria": "alimentos", "cantidad": 50, "origen": "Bogotá",
    }).json()
    client.patch(f"/api/v1/envios/{envio['id']}/verificar")

    colectivo = client.post("/api/v1/colectivos", json={"nombre": "Colectivo demo"}).json()
    client.patch(f"/api/v1/colectivos/{colectivo['id']}/verificar")

    resumen = client.get("/api/v1/resumen").json()

    assert resumen["total_centros"] == 4
    assert resumen["total_centros_registrados"] == 33
    assert resumen["total_reportes"] == 2
    assert resumen["total_solicitudes_pendientes"] == 2
    assert resumen["total_colectivos_verificados"] == resumen_antes["total_colectivos_verificados"] + 1
    assert resumen["total_envios_verificados_en_camino"] == 1


def test_resumen_nacional_sin_datos_no_falla(client):
    resp = client.get("/api/v1/resumen")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_centros"] == 4
    assert data["total_centros_registrados"] == 33
    assert data["total_reportes"] == 0
    assert data["ultimo_evento_sismico"] is None


def test_sitrep_hxl_responde_csv(client):
    resp = client.get("/api/v1/sitrep.csv?formato=hxl")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


def test_eventos_sismicos_ultimo_sin_eventos_responde_null(client):
    resp = client.get("/api/v1/eventos-sismicos/ultimo")
    assert resp.status_code == 200
    assert resp.json() is None


def _sembrar_evento_sismico(client, id_externo, magnitud, lugar, hace_horas=1):
    from datetime import datetime, timedelta

    from app import models

    db = client.db_sessionmaker()
    evento = models.EventoSismico(
        id_externo=id_externo,
        magnitud=magnitud,
        profundidad=100.0,
        lat=4.9,
        lon=-76.3,
        lugar=lugar,
        fuente="usgs",
        timestamp=datetime.utcnow() - timedelta(hours=hace_horas),
        activo_modo_emergencia=magnitud >= 6.0,
    )
    db.add(evento)
    db.commit()
    db.close()


def test_listar_eventos_sismicos_ordena_del_mas_reciente(client):
    _sembrar_evento_sismico(client, "us_test_1", 4.2, "San José del Palmar, Chocó", hace_horas=48)
    _sembrar_evento_sismico(client, "us_test_2", 4.3, "San José del Palmar, Chocó", hace_horas=1)

    resp = client.get("/api/v1/eventos-sismicos")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 2
    assert data[0]["id_externo"] == "us_test_2"


def test_listar_eventos_sismicos_respeta_ventana_de_dias(client):
    _sembrar_evento_sismico(client, "us_test_viejo", 4.0, "Chocó", hace_horas=24 * 30)

    resp = client.get("/api/v1/eventos-sismicos?dias=7")
    assert resp.json() == []


def test_alerta_sismica_sin_eventos(client):
    resp = client.get("/api/v1/eventos-sismicos/alerta")
    assert resp.status_code == 200
    data = resp.json()
    assert "No hay sismos recientes" in data["resumen"]
    assert data["generado_por_ia"] is False
    assert data["eventos"] == []


def test_alerta_sismica_con_eventos_usa_fallback_por_reglas(client):
    _sembrar_evento_sismico(client, "us_test_3", 4.3, "San José del Palmar, Chocó", hace_horas=2)

    resp = client.get("/api/v1/eventos-sismicos/alerta")
    data = resp.json()
    assert resp.status_code == 200
    assert "4.3" in data["resumen"]
    assert data["generado_por_ia"] is False
    assert len(data["eventos"]) == 1


def test_resumen_necesidades_ia_sin_pendientes(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    resp = client.get(f"/api/v1/centros/{centro['id']}/necesidades/resumen-ia")
    assert resp.status_code == 200
    data = resp.json()
    assert data["generado_por_ia"] is False
    assert "no tiene necesidades pendientes" in data["resumen"]


def test_resumen_necesidades_ia_con_pendientes(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    creado = client.post("/api/v1/reportes", json={"contenido": "Sin agua potable urgente"}).json()
    client.post(f"/api/v1/reportes/{creado['id']}/verificar", json={"centro_id": centro["id"]})

    resp = client.get(f"/api/v1/centros/{centro['id']}/necesidades/resumen-ia")
    data = resp.json()
    assert resp.status_code == 200
    assert "agua" in data["resumen"]
    assert data["generado_por_ia"] is False


def test_login_entrega_par_de_tokens_y_refrescar_renueva_el_acceso(client):
    login = client.post("/api/v1/auth/token", json={
        "id_territorio": "risaralda-pereira", "secreto": "cambia-esto-en-produccion",
    })
    assert login.status_code == 200
    datos = login.json()
    assert datos["refresh_token"]
    assert datos["expires_in"] > 0

    renovado = client.post("/api/v1/auth/refrescar", json={"refresh_token": datos["refresh_token"]})
    assert renovado.status_code == 200
    nuevo = renovado.json()

    # El acceso renovado sirve de verdad contra un endpoint protegido: se crea
    # una solicitud pendiente de agua y se marca entregada con el token nuevo.
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")
    reporte = client.post("/api/v1/reportes", json={"contenido": "Sin agua potable urgente"}).json()
    client.post(f"/api/v1/reportes/{reporte['id']}/verificar", json={"centro_id": centro["id"]})

    entrega = client.post(
        f"/api/v1/centros/{centro['id']}/entregas",
        json={"categoria": "agua"},
        headers={"Authorization": f"Bearer {nuevo['access_token']}"},
    )
    assert entrega.status_code == 200


def test_refrescar_con_token_invalido_responde_401(client):
    resp = client.post("/api/v1/auth/refrescar", json={"refresh_token": "no-es-un-jwt"})
    assert resp.status_code == 401


def test_refrescar_con_token_de_acceso_responde_401(client):
    login = client.post("/api/v1/auth/token", json={
        "id_territorio": "risaralda-pereira", "secreto": "cambia-esto-en-produccion",
    }).json()
    resp = client.post("/api/v1/auth/refrescar", json={"refresh_token": login["access_token"]})
    assert resp.status_code == 401


def test_salud_reporta_ok_con_base_viva(client):
    resp = client.get("/salud")
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["estado"] == "ok"
    assert datos["base_de_datos"] == "ok"
    assert datos["segundos_activo"] >= 0


def test_salud_responde_503_si_la_base_no_contesta(client, monkeypatch):
    """Un monitor externo necesita ver 503, no un 200 vacío, cuando la app
    está arriba pero no puede hablar con la base."""
    from app import main as main_module

    class SesionRota:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("conexión perdida con la base")

    main_module.app.dependency_overrides[get_db] = lambda: SesionRota()
    try:
        resp = client.get("/salud")
    finally:
        main_module.app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 503
    assert resp.json()["detail"]["estado"] == "degradado"


def test_listar_reportes_nunca_expone_el_telefono_de_whatsapp(client):
    """/api/v1/reportes es público: un reporte de WhatsApp no puede llevar el
    número de quien pidió ayuda."""
    from app import models

    db = client.db_sessionmaker()
    db.add(models.ReporteCiudadano(
        id_externo="573001234567",
        canal=models.CanalReporte.whatsapp,
        contenido_original="Necesitamos agua en el barrio",
    ))
    db.add(models.ReporteCiudadano(
        id_externo="4321",
        canal=models.CanalReporte.ushahidi,
        contenido_original="Reporte desde Ushahidi",
    ))
    db.commit()
    db.close()

    reportes = client.get("/api/v1/reportes").json()
    cuerpo = client.get("/api/v1/reportes").text

    por_canal = {r["canal"]: r for r in reportes}
    assert por_canal["whatsapp"]["id_externo"] is None
    # El id de un post de Ushahidi ya es público y sirve para rastrear: ese sí.
    assert por_canal["ushahidi"]["id_externo"] == "4321"
    assert "573001234567" not in cuerpo


def test_el_telefono_si_se_guarda_en_la_base(client):
    """Ocultarlo en la respuesta no significa perderlo: la coordinación tiene
    que poder rastrear un reporte hasta su origen."""
    from app import models

    respuesta = client.post("/sandbox/whatsapp/simular", json={
        "remitente": "573009998877", "texto": "Sin agua hace dos días",
    })
    assert respuesta.status_code == 200
    assert respuesta.json()["id_externo"] is None  # tampoco sale por acá

    db = client.db_sessionmaker()
    reporte = db.query(models.ReporteCiudadano).filter_by(canal=models.CanalReporte.whatsapp).first()
    assert reporte.id_externo == "573009998877"
    db.close()


def test_webhook_whatsapp_responde_el_challenge_de_meta(client, monkeypatch):
    """Sin esto, el panel de Meta se niega a guardar la URL del webhook y
    nadie puede conectar su número a este despliegue."""
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "token-de-este-despliegue")

    resp = client.get("/api/v1/webhooks/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "token-de-este-despliegue",
        "hub.challenge": "987654321",
    })

    assert resp.status_code == 200
    assert resp.text == "987654321"  # texto plano exacto, sin comillas JSON
    assert resp.headers["content-type"].startswith("text/plain")


def test_webhook_whatsapp_rechaza_un_token_ajeno(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "el-nuestro")
    resp = client.get("/api/v1/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "el-de-otro", "hub.challenge": "123",
    })
    assert resp.status_code == 403


def test_webhook_whatsapp_sin_configurar_responde_503(client, monkeypatch):
    """503 y no 403: el problema es de este despliegue, no de quien pregunta.
    El mensaje tiene que decirle a quien despliega qué le falta."""
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    resp = client.get("/api/v1/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "lo-que-sea", "hub.challenge": "123",
    })
    assert resp.status_code == 503
    assert "WHATSAPP_VERIFY_TOKEN" in resp.json()["detail"]


def test_estado_de_integraciones_distingue_real_de_sandbox(client, monkeypatch):
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    monkeypatch.delenv("USHAHIDI_BASE_URL", raising=False)

    datos = client.get("/api/v1/config/integraciones").json()
    assert datos["whatsapp"]["modo"] == "sandbox"
    assert datos["ushahidi"].startswith("sandbox")
    assert datos["usgs"] == "real"

    monkeypatch.setenv("WHATSAPP_APP_SECRET", "x")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "y")
    assert client.get("/api/v1/config/integraciones").json()["whatsapp"]["modo"] == "real"


def test_estado_de_integraciones_no_devuelve_ningun_secreto(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secreto-de-firma")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "secreto-de-verificacion")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-secreto")
    cuerpo = client.get("/api/v1/config/integraciones").text
    for secreto in ("secreto-de-firma", "secreto-de-verificacion", "gsk-secreto"):
        assert secreto not in cuerpo


def test_webhook_whatsapp_guarda_el_reporte_aunque_no_pueda_responder(client, monkeypatch):
    """El acuse es opcional y va en segundo plano: el reporte se guarda igual."""
    from app import models

    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)  # modo sandbox: no exige firma
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)       # sin credenciales de salida

    resp = client.post("/api/v1/webhooks/whatsapp", json={
        "entry": [{"changes": [{"value": {"messages": [
            {"from": "573005556677", "type": "text", "text": {"body": "Necesitamos carpas"}}
        ]}}]}]
    })

    assert resp.status_code == 200
    assert resp.json()["procesado"] is True

    db = client.db_sessionmaker()
    assert db.query(models.ReporteCiudadano).filter_by(id_externo="573005556677").count() == 1
    db.close()
