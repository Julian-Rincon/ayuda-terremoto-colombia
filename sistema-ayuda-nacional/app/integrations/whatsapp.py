"""
Ingesta vía WhatsApp Business Cloud API — planoidea.md §3.2/§5.

Modo sandbox por defecto: sin WHATSAPP_APP_SECRET configurado, el webhook
en main.py acepta cualquier payload (ver auth.validar_firma_whatsapp). El
parseo de abajo usa exactamente el formato real de Meta Graph API — cuando
haya credenciales reales, esto no cambia.
"""
from typing import Optional

from .. import models
from ..ai_helper import clasificar_reporte


def parsear_mensaje_entrante(payload: dict) -> Optional[dict]:
    try:
        entry = payload["entry"][0]
        valor = entry["changes"][0]["value"]
        mensajes = valor.get("messages")
        if not mensajes:
            return None
        mensaje = mensajes[0]
    except (KeyError, IndexError, TypeError):
        return None

    remitente = mensaje.get("from")
    texto = None
    ubicacion = None

    if mensaje.get("type") == "text":
        texto = mensaje.get("text", {}).get("body")
    elif mensaje.get("type") == "location":
        loc = mensaje.get("location", {})
        if loc.get("latitude") is not None and loc.get("longitude") is not None:
            ubicacion = {"lat": loc["latitude"], "lon": loc["longitude"]}
        texto = loc.get("name") or loc.get("address") or ""

    if not remitente or texto is None:
        return None

    return {"remitente": remitente, "texto": texto, "ubicacion": ubicacion}


def construir_reporte_desde_whatsapp(mensaje: dict) -> models.ReporteCiudadano:
    clasificacion = clasificar_reporte(mensaje["texto"])
    ubicacion = mensaje.get("ubicacion") or {}
    return models.ReporteCiudadano(
        id_externo=mensaje["remitente"],
        canal=models.CanalReporte.whatsapp,
        contenido_original=mensaje["texto"],
        categoria=clasificacion["categoria"],
        urgencia=clasificacion["urgencia"],
        resumen_ia=clasificacion["resumen"],
        clasificado_por_ia=clasificacion["clasificado_por_ia"],
        lat=ubicacion.get("lat"),
        lon=ubicacion.get("lon"),
        verificado=False,
    )
