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
