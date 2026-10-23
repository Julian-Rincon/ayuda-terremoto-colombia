"""
Ingesta vía WhatsApp Business Cloud API — planoidea.md §3.2/§5.

Modo sandbox por defecto: sin WHATSAPP_APP_SECRET configurado, el webhook
en main.py acepta cualquier payload (ver auth.validar_firma_whatsapp). El
parseo de abajo usa exactamente el formato real de Meta Graph API — cuando
haya credenciales reales, esto no cambia.
"""
import hmac
import logging
import os
from typing import Optional

import httpx

from .. import models
from ..ai_helper import clasificar_reporte

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Conectar un número propio: verificación del webhook
# ---------------------------------------------------------------------------
#
# Antes de mandar un solo mensaje, Meta hace un GET a la URL del webhook con
# un token que uno mismo eligió y un `hub.challenge`. Si la respuesta no es
# exactamente ese challenge en texto plano, el panel de Meta se niega a
# guardar la URL. Sin esto no se puede conectar ningún número — ni el nuestro
# ni el de quien despliegue esto mañana.


class WebhookNoConfigurado(Exception):
    """Falta WHATSAPP_VERIFY_TOKEN: no hay con qué comparar."""


class VerificacionRechazada(Exception):
    """El token que mandó Meta no coincide con el configurado."""


def resolver_verificacion(modo: Optional[str], token: Optional[str], challenge: Optional[str]) -> str:
    """
    Devuelve el `hub.challenge` si la suscripción es legítima.

    Si no hay token configurado se rechaza en vez de aceptar cualquier cosa:
    un webhook que acepta a ciegas deja que un tercero conecte SU app de Meta
    a ESTE despliegue y le inyecte reportes falsos a la cola de verificación.
    """
    esperado = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    if not esperado:
        raise WebhookNoConfigurado(
            "WHATSAPP_VERIFY_TOKEN no está configurado en este despliegue. "
            "Elegí una cadena larga al azar, ponela en la variable de entorno "
            "y la misma en el panel de Meta (ver docs/whatsapp-meta.md)."
        )

    if modo != "subscribe" or not challenge:
        raise VerificacionRechazada("Petición de verificación incompleta o con hub.mode inesperado")

    # Comparación en tiempo constante: el token es un secreto compartido.
    if not token or not hmac.compare_digest(token, esperado):
        raise VerificacionRechazada("El hub.verify_token no coincide con el configurado")

    return challenge


# ---------------------------------------------------------------------------
# Acuse de recibo hacia quien escribió (opcional)
# ---------------------------------------------------------------------------

GRAPH_API_VERSION = "v21.0"

TEXTO_ACUSE = (
    "Recibimos tu reporte y queda en la cola de verificación. "
    "Este canal NO gestiona dinero ni donaciones: si alguien te pide un pago "
    "a nombre de esta ayuda, es una estafa."
)


def envio_configurado() -> bool:
    """Responder es opt-in: sin credenciales de salida, el canal solo escucha."""
    return bool(os.getenv("WHATSAPP_TOKEN", "").strip() and os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip())


async def enviar_acuse_de_recibo(destinatario: str) -> bool:
    """
    Confirma a quien reportó que su mensaje llegó. Devuelve True si se envió.

    Nunca propaga errores: que falle el acuse no puede tumbar la ingesta del
    reporte, que es lo único que de verdad importa guardar.
    """
    if not envio_configurado():
        return False

    token = os.getenv("WHATSAPP_TOKEN", "").strip()
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": destinatario,
                    "type": "text",
                    "text": {"body": TEXTO_ACUSE},
                },
            )
            resp.raise_for_status()
        return True
    except Exception as error:  # red caída, token vencido, ventana de 24h cerrada
        logger.warning("No se pudo enviar el acuse de recibo por WhatsApp: %s", error)
        return False


def estado_integracion() -> dict:
    """
    Qué partes del canal están configuradas en este despliegue. No devuelve
    ningún secreto, solo si está puesto o no — sirve para que quien despliega
    confirme que su configuración tomó efecto sin leer logs.
    """
    firma = bool(os.getenv("WHATSAPP_APP_SECRET", "").strip())
    verificacion = bool(os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip())
    return {
        "modo": "real" if (firma and verificacion) else "sandbox",
        "verificacion_de_webhook": verificacion,
        "validacion_de_firma": firma,
        "responde_acuse_de_recibo": envio_configurado(),
    }
