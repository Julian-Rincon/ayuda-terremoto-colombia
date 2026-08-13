"""
Canales oficiales verificados para Pereira, tal como se reportaban en medios
verificados al 12-13 de agosto de 2026 (ver README para fuentes).

IMPORTANTE: estos datos son un punto de partida, no una fuente de verdad viva.
Antes de desplegar en producción, alguien debe volver a confirmar cada
teléfono/dirección directamente con la entidad. Los números y horarios de
una emergencia activa cambian de un día para otro.
"""
from sqlalchemy.orm import Session

from .models import Colectivo, TipoColectivo


CANALES_OFICIALES_SEED = [
    {
        "nombre": "Alcaldía de Pereira — Gestión del Riesgo",
        "tipo": TipoColectivo.oficial_verificado,
        "descripcion_capacidad": (
            "Línea administrativa (no de emergencias) para horarios de puntos de "
            "acopio, voluntariado e información institucional."
        ),
        "zona_cobertura": "Pereira - todas las comunas",
        "contacto": "(+57) 606 324 8000 / 606 324 8179",
        "es_oficial": True,
        "verificado": True,
    },
    {
        "nombre": "Cruz Roja Colombiana — Seccional Pereira",
        "tipo": TipoColectivo.oficial_verificado,
        "descripcion_capacidad": "Atención de emergencia, voluntariado, reporte de desaparecidos.",
        "zona_cobertura": "Pereira - todas las comunas",
        "contacto": "316 478 1821",
        "es_oficial": True,
        "verificado": True,
    },
    {
        "nombre": "Hospital Universitario San Jorge — Banco de Sangre",
        "tipo": TipoColectivo.salud,
        "descripcion_capacidad": (
            "Banco de sangre con escasez confirmada tras el terremoto. "
            "Recibe donantes de todos los tipos de sangre, lunes a sábado 8am-5pm."
        ),
        "zona_cobertura": "Carrera 4 #24-88, Pereira",
        "contacto": "(+57) 606 316 9024",
        "es_oficial": True,
        "verificado": True,
    },
]

ALERTA_SEGURIDAD = (
    "Se han confirmado estafas activas tras el terremoto: (1) el sitio "
    "'terremotocolombia.com' redirige a un mapa de un sismo distinto en Venezuela "
    "y recolecta datos de contacto — NO es oficial; (2) ninguna entidad legítima cobra "
    "por registrar voluntarios, damnificados o subsidios; (3) las transferencias por "
    "Nequi/Daviplata/Bre-B son inmediatas e irreversibles, ningún recaudador legítimo "
    "presiona para transferir en minutos; (4) han aparecido falsos evaluadores de daños "
    "estructurales — un evaluador legítimo no exige entrar de inmediato ni cobra en la puerta. "
    "Verifique siempre con la Alcaldía o Cruz Roja Pereira antes de confiar en un canal nuevo."
)


def sembrar_datos_iniciales(db: Session):
    ya_existe = db.query(Colectivo).filter(Colectivo.es_oficial == True).first()  # noqa: E712
    if ya_existe:
        return
    for item in CANALES_OFICIALES_SEED:
        db.add(Colectivo(**item))
    db.commit()
