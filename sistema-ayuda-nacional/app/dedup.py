"""
Detección de reportes posiblemente duplicados entre canales (WhatsApp,
Ushahidi, manual) — el mismo hecho puede llegar reportado dos veces por
vías distintas.

Deliberadamente NO usa IA/LLM: comparar similitud de texto es un problema
clásico de fuzzy matching, no de razonamiento — un modelo de lenguaje acá
sería más lento, más caro y menos auditable que un algoritmo determinístico
de la librería estándar. Mismo principio que ya aplica `sugerir_colectivos`
en el prototipo de Pereira: donde la lógica es auditable por un humano, no
hace falta una caja negra.

Nunca descarta ni fusiona nada automáticamente — solo deja marcado el
reporte para que un humano decida en la cola de verificación.
"""
import difflib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models

VENTANA_HORAS_DEFECTO = 48
UMBRAL_SIMILITUD_DEFECTO = 0.6
REFUERZO_MISMA_ZONA = 0.1


def encontrar_posible_duplicado(
    db: Session,
    categoria: models.CategoriaNecesidad,
    contenido: str,
    zona: Optional[str] = None,
    ventana_horas: int = VENTANA_HORAS_DEFECTO,
    umbral_similitud: float = UMBRAL_SIMILITUD_DEFECTO,
) -> Optional[models.ReporteCiudadano]:
    desde = datetime.utcnow() - timedelta(hours=ventana_horas)
    candidatos = (
        db.query(models.ReporteCiudadano)
        .filter(
            models.ReporteCiudadano.categoria == categoria,
            models.ReporteCiudadano.creado_en >= desde,
        )
        .all()
    )

    texto_nuevo = (contenido or "").lower().strip()
    zona_nueva = (zona or "").lower().strip()

    mejor = None
    mejor_puntaje = 0.0

    for candidato in candidatos:
        texto_candidato = (candidato.contenido_original or "").lower().strip()
        puntaje = difflib.SequenceMatcher(None, texto_nuevo, texto_candidato).ratio()

        zona_candidato = (candidato.zona or "").lower().strip()
        if zona_nueva and zona_candidato and zona_nueva == zona_candidato:
            puntaje += REFUERZO_MISMA_ZONA

        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = candidato

    if mejor is not None and mejor_puntaje >= umbral_similitud:
        return mejor
    return None


def marcar_posible_duplicado(db: Session, reporte: models.ReporteCiudadano) -> models.ReporteCiudadano:
    """Muta `reporte.posible_duplicado_de_id` in-place. Llamar antes de db.add()/commit()."""
    duplicado = encontrar_posible_duplicado(db, reporte.categoria, reporte.contenido_original, reporte.zona)
    reporte.posible_duplicado_de_id = duplicado.id if duplicado else None
    return reporte
