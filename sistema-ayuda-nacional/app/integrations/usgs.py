"""
Escucha del feed público de USGS — planoidea.md §3.1/§5. Real, sin
credenciales: la API es pública y gratuita.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from .. import auth, models
from ..database import SessionLocal
from ..websocket_manager import manager
from . import geocoding

logger = logging.getLogger("integraciones.usgs")

# El feed "significant" de USGS solo trae sismos de relevancia global — una
# réplica regional de magnitud 4 (como la real del 13 de agosto de 2026 en
# Chocó) nunca aparece ahí. "2.5_hour" trae todo sismo M≥2.5 en el mundo;
# el filtro de Colombia en _esta_en_colombia() se encarga de quedarse solo
# con lo relevante para este sistema.
USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_hour.geojson"
MAGNITUD_UMBRAL_EMERGENCIA = 6.0
# Sismo lo bastante fuerte como para justificar abrir un centro de
# coordinación nuevo en una zona que hoy no tiene ninguno — más bajo que el
# umbral de "modo emergencia" nacional, pero no tan bajo como el mínimo del
# feed (2.5) para no crear un centro por cada temblor apenas perceptible.
MAGNITUD_UMBRAL_AUTO_SOPORTE = 4.0
INTERVALO_SEGUNDOS = 60

# Bounding box aproximado de Colombia continental
COLOMBIA_LAT_MIN, COLOMBIA_LAT_MAX = -4.3, 13.5
COLOMBIA_LON_MIN, COLOMBIA_LON_MAX = -82.0, -66.8


def _esta_en_colombia(lon: float, lat: float) -> bool:
    return COLOMBIA_LON_MIN <= lon <= COLOMBIA_LON_MAX and COLOMBIA_LAT_MIN <= lat <= COLOMBIA_LAT_MAX


async def _activar_centro_para_zona(db: Session, lat: float, lon: float) -> "models.CentroLocal | None":
    """
    Si un sismo lo bastante fuerte cae en un departamento, activa el centro
    de coordinación de esa zona. Los 33 departamentos ya están sembrados
    desde el arranque (ver seed_data.py) — la mayoría "dormidos"
    (activo=False, sin contacto) hasta que algo confirma que hace falta
    coordinar ahí. Activar nunca inventa contacto ni lo marca verificado:
    solo abre el espacio para que un humano lo complete.

    Si la geocodificación devuelve un departamento que por algún motivo no
    está en la siembra (variante de nombre no contemplada en los alias de
    geocoding.py), se crea uno nuevo igual de dormido en vez de descartar
    el sismo — nunca se pierde una zona real solo por un desajuste de texto.
    """
    import os

    ubicacion = await geocoding.departamento_desde_coordenadas(lat, lon)
    if ubicacion is None:
        return None

    centro = db.query(models.CentroLocal).filter_by(id_territorio=ubicacion["id_territorio"]).first()
    secreto_inicial = os.getenv("NODOS_SECRETO_INICIAL", "cambia-esto-en-produccion")

    if centro is not None:
        if centro.activo:
            return None
        centro.activo = True
        db.commit()
        db.refresh(centro)
        if not db.query(models.NodoCredencial).filter_by(centro_id=centro.id).first():
            db.add(models.NodoCredencial(centro_id=centro.id, secreto_hash=auth.hash_secreto(secreto_inicial)))
            db.commit()
        logger.warning(
            "Centro activado automáticamente por actividad sísmica: %s (%s)",
            centro.nombre, centro.id_territorio,
        )
        return centro

    centro = models.CentroLocal(
        id_territorio=ubicacion["id_territorio"],
        nombre=ubicacion["departamento"],
        departamento=ubicacion["departamento"],
        contacto=None,
        contacto_verificado=False,
        activo=True,
        lat=lat,
        lon=lon,
    )
    db.add(centro)
    db.commit()
    db.refresh(centro)
    db.add(models.NodoCredencial(centro_id=centro.id, secreto_hash=auth.hash_secreto(secreto_inicial)))
    db.commit()

    logger.warning(
        "Centro nuevo creado automáticamente por actividad sísmica (departamento fuera de la siembra nacional): %s (%s)",
        centro.nombre, centro.id_territorio,
    )
    return centro


async def _procesar_eventos(db: Session, features: list[dict]) -> list["models.EventoSismico"]:
    activados = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None, None])
        if len(coords) < 2 or coords[0] is None or coords[1] is None:
            continue

        lon, lat = coords[0], coords[1]
        profundidad = coords[2] if len(coords) > 2 else None
        id_externo = feature.get("id")
        magnitud = props.get("mag")

        if not id_externo or magnitud is None:
            continue
        if not _esta_en_colombia(lon, lat):
            continue
        if db.query(models.EventoSismico).filter_by(id_externo=id_externo).first():
            continue

        activar = magnitud >= MAGNITUD_UMBRAL_EMERGENCIA
        marca_tiempo = (
            datetime.fromtimestamp(props["time"] / 1000, tz=timezone.utc)
            if props.get("time") else datetime.now(timezone.utc)
        )

        evento = models.EventoSismico(
            id_externo=id_externo,
            magnitud=magnitud,
            profundidad=profundidad,
            lat=lat,
            lon=lon,
            lugar=props.get("place"),
            fuente="usgs",
            timestamp=marca_tiempo,
            activo_modo_emergencia=activar,
        )
        db.add(evento)
        db.commit()
        db.refresh(evento)

        if activar:
            await manager.broadcast("modo_emergencia_activado", {
                "id_externo": evento.id_externo,
                "magnitud": evento.magnitud,
                "lugar": evento.lugar,
            })

        if magnitud >= MAGNITUD_UMBRAL_AUTO_SOPORTE:
            centro_activado = await _activar_centro_para_zona(db, lat, lon)
            if centro_activado is not None:
                await manager.broadcast("centro_activado", {
                    "id_territorio": centro_activado.id_territorio,
                    "nombre": centro_activado.nombre,
                    "por_evento": evento.id_externo,
                })
        activados.append(evento)
    return activados


async def escuchar_usgs_una_vez(db: Session) -> list["models.EventoSismico"]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(USGS_FEED_URL)
            resp.raise_for_status()
            data = resp.json()
        return await _procesar_eventos(db, data.get("features", []))
    except Exception:
        logger.exception("Fallo consultando el feed de USGS, se reintenta en el próximo ciclo")
        return []


async def escuchar_usgs_loop():
    while True:
        db = SessionLocal()
        try:
            await escuchar_usgs_una_vez(db)
        finally:
            db.close()
        await asyncio.sleep(INTERVALO_SEGUNDOS)
