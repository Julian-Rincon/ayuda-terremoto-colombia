"""
Guardia de arranque: si ENVIRONMENT=production y los secretos siguen con el
valor de ejemplo de .env.example, la app se niega a arrancar. Un checklist
de "acuérdate de rotar esto antes de desplegar" se olvida; un arranque que
falla con un mensaje claro, no.
"""
import logging
import os

logger = logging.getLogger(__name__)

VALOR_POR_DEFECTO = "cambia-esto-en-produccion"
SECRETOS_REQUERIDOS = ("JWT_SECRET", "NODOS_SECRETO_INICIAL")

# RFC 7518 §3.2: para HS256 la clave debe tener al menos el tamaño del hash,
# 32 bytes. Una clave más corta se puede atacar por fuerza bruta aunque no
# sea el valor de ejemplo — y "lo cambié" no implica "es fuerte".
LONGITUD_MINIMA_JWT_SECRET = 32


def verificar_secretos_de_produccion() -> None:
    if os.getenv("ENVIRONMENT", "development") != "production":
        return

    sin_rotar = [s for s in SECRETOS_REQUERIDOS if os.getenv(s, VALOR_POR_DEFECTO) == VALOR_POR_DEFECTO]
    if sin_rotar:
        raise RuntimeError(
            f"ENVIRONMENT=production pero {', '.join(sin_rotar)} sigue con el valor de "
            "ejemplo de .env.example. Genera un valor real y único antes de desplegar "
            "(ver README, sección Seguridad y confianza)."
        )

    jwt_secret = os.getenv("JWT_SECRET", "")
    if len(jwt_secret.encode()) < LONGITUD_MINIMA_JWT_SECRET:
        raise RuntimeError(
            f"ENVIRONMENT=production pero JWT_SECRET tiene {len(jwt_secret.encode())} bytes "
            f"y HS256 necesita al menos {LONGITUD_MINIMA_JWT_SECRET} (RFC 7518 §3.2). "
            "Una clave corta se puede romper por fuerza bruta aunque la hayas cambiado. "
            "Genera una con: openssl rand -hex 32"
        )


def advertir_configuracion_parcial_whatsapp() -> list[str]:
    """
    Una integración de WhatsApp a medias es peor que una apagada: quien
    despliega cree que el canal funciona y la gente escribe a un número que
    no ingesta nada. Esto no tumba el arranque (el canal es opcional) pero
    deja dicho en el log exactamente qué falta.

    Devuelve las advertencias emitidas, para poder probarlas.
    """
    firma = bool(os.getenv("WHATSAPP_APP_SECRET", "").strip())
    verificacion = bool(os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip())
    token_salida = bool(os.getenv("WHATSAPP_TOKEN", "").strip())
    phone_id = bool(os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip())

    advertencias = []

    if verificacion and not firma:
        advertencias.append(
            "WhatsApp: WHATSAPP_VERIFY_TOKEN está puesto pero WHATSAPP_APP_SECRET no. "
            "El webhook se puede conectar, pero aceptará cualquier payload sin validar "
            "que venga de Meta. Completá WHATSAPP_APP_SECRET antes de recibir mensajes reales."
        )
    if firma and not verificacion:
        advertencias.append(
            "WhatsApp: WHATSAPP_APP_SECRET está puesto pero WHATSAPP_VERIFY_TOKEN no. "
            "Meta no va a poder verificar la URL del webhook y no se podrá conectar el número."
        )
    if token_salida != phone_id:
        falta = "WHATSAPP_PHONE_NUMBER_ID" if token_salida else "WHATSAPP_TOKEN"
        advertencias.append(
            f"WhatsApp: para responder el acuse de recibo hacen falta WHATSAPP_TOKEN y "
            f"WHATSAPP_PHONE_NUMBER_ID; falta {falta}. El canal va a recibir mensajes "
            "pero no va a confirmar nada a quien escribe."
        )

    for advertencia in advertencias:
        logger.warning(advertencia)
    return advertencias
