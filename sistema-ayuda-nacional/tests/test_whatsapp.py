import pytest

from app import models
from app.integrations import whatsapp

PAYLOAD_TEXTO_META = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "573001234567",
                    "type": "text",
                    "text": {"body": "Necesitamos agua potable urgente en el barrio"},
                }]
            }
        }]
    }]
}

PAYLOAD_UBICACION_META = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "573001234567",
                    "type": "location",
                    "location": {"latitude": 4.8087, "longitude": -75.6906, "name": "Cuba, Pereira"},
                }]
            }
        }]
    }]
}

PAYLOAD_SIN_MENSAJES = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}


def test_parsear_mensaje_de_texto():
    mensaje = whatsapp.parsear_mensaje_entrante(PAYLOAD_TEXTO_META)
    assert mensaje["remitente"] == "573001234567"
    assert "agua potable" in mensaje["texto"]
    assert mensaje["ubicacion"] is None


def test_parsear_mensaje_de_ubicacion():
    mensaje = whatsapp.parsear_mensaje_entrante(PAYLOAD_UBICACION_META)
    assert mensaje["ubicacion"] == {"lat": 4.8087, "lon": -75.6906}


def test_parsear_payload_sin_mensajes_retorna_none():
    assert whatsapp.parsear_mensaje_entrante(PAYLOAD_SIN_MENSAJES) is None


def test_parsear_payload_malformado_retorna_none():
    assert whatsapp.parsear_mensaje_entrante({}) is None


def test_construir_reporte_desde_whatsapp_clasifica_y_arma_modelo(monkeypatch):
    from app import ai_helper
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # fallback por reglas, determinístico

    mensaje = {"remitente": "573001234567", "texto": "Familia atrapada bajo escombros", "ubicacion": None}
    reporte = whatsapp.construir_reporte_desde_whatsapp(mensaje)

    assert isinstance(reporte, models.ReporteCiudadano)
    assert reporte.canal == models.CanalReporte.whatsapp
    assert reporte.id_externo == "573001234567"
    assert reporte.categoria == models.CategoriaNecesidad.rescate_escombros
    assert reporte.urgencia == models.UrgenciaReporte.alta
    assert reporte.verificado is False


# ---------------------------------------------------------------------------
# Verificación del webhook: lo que Meta exige para conectar un número
# ---------------------------------------------------------------------------

def test_verificacion_devuelve_el_challenge_con_el_token_correcto(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "token-elegido-por-quien-despliega")
    assert whatsapp.resolver_verificacion(
        "subscribe", "token-elegido-por-quien-despliega", "1234567890"
    ) == "1234567890"


def test_verificacion_rechaza_un_token_que_no_coincide(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "el-correcto")
    with pytest.raises(whatsapp.VerificacionRechazada):
        whatsapp.resolver_verificacion("subscribe", "el-equivocado", "123")


def test_verificacion_sin_token_configurado_no_acepta_a_ciegas(monkeypatch):
    """Aceptar cualquier token dejaría que un tercero conecte su app de Meta
    a este despliegue y le inyecte reportes falsos a la cola."""
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    with pytest.raises(whatsapp.WebhookNoConfigurado):
        whatsapp.resolver_verificacion("subscribe", "cualquier-cosa", "123")


def test_verificacion_rechaza_un_hub_mode_inesperado(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "el-correcto")
    with pytest.raises(whatsapp.VerificacionRechazada):
        whatsapp.resolver_verificacion("unsubscribe", "el-correcto", "123")


# ---------------------------------------------------------------------------
# Acuse de recibo (opcional)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sin_credenciales_de_salida_no_se_intenta_responder(monkeypatch):
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    assert whatsapp.envio_configurado() is False
    assert await whatsapp.enviar_acuse_de_recibo("573001234567") is False


@pytest.mark.asyncio
async def test_un_fallo_al_responder_nunca_rompe_la_ingesta(monkeypatch):
    """El reporte ya quedó guardado; que la API de salida falle no puede
    convertirse en un error para quien pidió ayuda."""
    monkeypatch.setenv("WHATSAPP_TOKEN", "token-falso")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")

    class ClienteQueFalla:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, *_args, **_kwargs):
            raise RuntimeError("Meta no contesta")

    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", lambda **_: ClienteQueFalla())
    assert await whatsapp.enviar_acuse_de_recibo("573001234567") is False


@pytest.mark.asyncio
async def test_el_acuse_avisa_que_el_canal_no_maneja_dinero(monkeypatch):
    """Quien reporta recibe una respuesta de un número institucional: es el
    momento exacto en que una estafa suplantaría este canal."""
    monkeypatch.setenv("WHATSAPP_TOKEN", "token-falso")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    enviado = {}

    class ClienteOk:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, headers=None, json=None):
            enviado["url"] = url
            enviado["json"] = json

            class Resp:
                def raise_for_status(self):
                    return None

            return Resp()

    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", lambda **_: ClienteOk())

    assert await whatsapp.enviar_acuse_de_recibo("573001234567") is True
    assert enviado["json"]["to"] == "573001234567"
    assert "estafa" in enviado["json"]["text"]["body"]
    assert "123456/messages" in enviado["url"]


def test_estado_integracion_no_filtra_secretos(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secreto-real-que-no-debe-salir")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "otro-secreto")
    estado = whatsapp.estado_integracion()
    assert estado["modo"] == "real"
    assert "secreto-real-que-no-debe-salir" not in str(estado)
    assert "otro-secreto" not in str(estado)
