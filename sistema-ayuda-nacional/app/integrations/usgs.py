"""
Escucha del feed público de USGS — planoidea.md §3.1/§5. Real, sin
credenciales: la API es pública y gratuita.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from ..websocket_manager import manager

logger = logging.getLogger("integraciones.usgs")

USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.geojson"
MAGNITUD_UMBRAL_EMERGENCIA = 6.0
INTERVALO_SEGUNDOS = 60

# Bounding box aproximado de Colombia continental
COLOMBIA_LAT_MIN, COLOMBIA_LAT_MAX = -4.3, 13.5
COLOMBIA_LON_MIN, COLOMBIA_LON_MAX = -82.0, -66.8


def _esta_en_colombia(lon: float, lat: float) -> bool:
    return COLOMBIA_LON_MIN <= lon <= COLOMBIA_LON_MAX and COLOMBIA_LAT_MIN <= lat <= COLOMBIA_LAT_MAX


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
