"""
Sincronización con Ushahidi Platform — planoidea.md §3.3/§5. Cliente REST
contra la API v5 real (docs.ushahidi.com); si USHAHIDI_BASE_URL no está
configurada, sirve una fixture con la misma forma para desarrollo/demo.
"""
import os

import httpx
from sqlalchemy.orm import Session

from .. import dedup, models
from ..ai_helper import clasificar_reporte

USHAHIDI_BASE_URL = os.getenv("USHAHIDI_BASE_URL", "").strip().rstrip("/")

POSTS_FIXTURE = [
    {
        "id": "fixture-1",
        "title": "Familia atrapada, necesitan rescate urgente",
        "content": "Familia atrapada, necesitan rescate urgente en zona del derrumbe",
        "status": "published",
        "location": {"lat": 4.8087, "lon": -75.6906},
    },
    {
        "id": "fixture-2",
        "title": "Sin agua potable hace tres días",
        "content": "Sin agua potable hace tres días en la vereda",
        "status": "published",
        "location": {"lat": 5.0387, "lon": -76.6644},
    },
]


async def obtener_posts_publicados() -> list[dict]:
    if not USHAHIDI_BASE_URL:
        return POSTS_FIXTURE
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{USHAHIDI_BASE_URL}/api/v5/posts", params={"status": "published"})
            resp.raise_for_status()
            data = resp.json()
        return data.get("results", data.get("data", []))
    except Exception:
        return []


def existe_en_sistema(db: Session, id_externo: str) -> bool:
    return db.query(models.ReporteCiudadano).filter_by(id_externo=id_externo).first() is not None


def _crear_reporte_desde_post(post: dict) -> models.ReporteCiudadano:
    contenido = post.get("content") or post.get("title") or ""
    clasificacion = clasificar_reporte(contenido)
    ubicacion = post.get("location") or {}
    return models.ReporteCiudadano(
        id_externo=str(post["id"]),
        canal=models.CanalReporte.ushahidi,
        contenido_original=contenido,
        categoria=clasificacion["categoria"],
        urgencia=clasificacion["urgencia"],
        resumen_ia=clasificacion["resumen"],
        clasificado_por_ia=clasificacion["clasificado_por_ia"],
        lat=ubicacion.get("lat"),
        lon=ubicacion.get("lon"),
        verificado=False,
    )


async def sincronizar_ushahidi(db: Session) -> list[models.ReporteCiudadano]:
    posts = await obtener_posts_publicados()
    nuevos = []
    for post in posts:
        if not post.get("id") or existe_en_sistema(db, str(post["id"])):
            continue
        reporte = _crear_reporte_desde_post(post)
        dedup.marcar_posible_duplicado(db, reporte)
        db.add(reporte)
        db.commit()
        db.refresh(reporte)
        nuevos.append(reporte)
    return nuevos
