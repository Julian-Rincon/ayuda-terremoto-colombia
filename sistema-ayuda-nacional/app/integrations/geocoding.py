"""
Geocodificación inversa vía Nominatim (OpenStreetMap) — gratis, sin llave,
mismo ecosistema que ya usa el mapa (Leaflet + OSM). Se usa SOLO para saber
en qué departamento cayó un sismo detectado, para poder abrir un centro de
coordinación ahí — NUNCA para inventar datos de contacto de una entidad.
"""
import logging
import re
import unicodedata
from typing import Optional

import httpx

from ..colombia import DEPARTAMENTOS_COLOMBIA

logger = logging.getLogger("integraciones.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "ayuda-terremoto-colombia (github.com/Julian-Rincon/ayuda-terremoto-colombia)"


def slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto


_NOMBRE_POR_SLUG = {d["id_territorio"]: d["nombre"] for d in DEPARTAMENTOS_COLOMBIA}

# Nominatim no siempre devuelve el nombre exacto que usamos como slug (ej.
# Risaralda ya está sembrado como "risaralda-pereira" por el centro real de
# Pereira, o el archipiélago tiene nombre oficial largo) — estos alias
# conocidos evitan crear un centro duplicado por un desajuste de texto.
_ALIAS_SLUG = {
    "risaralda": "risaralda-pereira",
    "valle-del-cauca": "valle",
    "bogota": "bogota-dc",
    "bogota-d-c": "bogota-dc",
    "distrito-capital-de-bogota": "bogota-dc",
    "archipielago-de-san-andres-providencia-y-santa-catalina": "san-andres-y-providencia",
    "san-andres-providencia-y-santa-catalina": "san-andres-y-providencia",
}


async def departamento_desde_coordenadas(lat: float, lon: float) -> Optional[dict]:
    """Retorna {"departamento": str, "id_territorio": str} o None si falla o no hay dato."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"lat": lat, "lon": lon, "format": "json", "zoom": 6, "accept-language": "es"},
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
        departamento = data.get("address", {}).get("state")
        if not departamento:
            return None
        slug_crudo = slug(departamento)
        id_territorio = _ALIAS_SLUG.get(slug_crudo, slug_crudo)
        nombre = _NOMBRE_POR_SLUG.get(id_territorio, departamento)
        return {"departamento": nombre, "id_territorio": id_territorio}
    except Exception:
        logger.exception("Fallo geocodificando el epicentro, no se crea centro automático")
        return None
