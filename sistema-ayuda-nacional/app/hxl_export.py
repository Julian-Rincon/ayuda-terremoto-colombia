"""
Export HXL (Humanitarian Exchange Language) — planoidea.md §5/§3.5.
Solo formateo de datos ya en la base local; sin llamadas externas.
"""
import csv
import io

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

ENCABEZADOS_HXL = ["#loc+name", "#affected+num", "#need+category", "#date+reported"]


def _agregar_necesidades_por_municipio(db: Session) -> list[dict]:
    query = (
        db.query(
            models.CentroLocal.departamento,
            models.Solicitud.categoria,
            func.count(models.Solicitud.id),
            func.max(models.Solicitud.creado_en),
        )
        .join(models.CentroLocal, models.Solicitud.centro_id == models.CentroLocal.id)
        .group_by(models.CentroLocal.departamento, models.Solicitud.categoria)
    )
    filas = []
    for departamento, categoria, total, fecha in query.all():
        filas.append({
            "#loc+name": departamento,
            "#affected+num": total,
            "#need+category": categoria.value,
            "#date+reported": fecha.date().isoformat() if fecha else "",
        })
    return filas


def generar_sitrep_hxl(db: Session) -> str:
    filas = _agregar_necesidades_por_municipio(db)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=ENCABEZADOS_HXL, lineterminator="\n")
    writer.writeheader()
    for fila in filas:
        writer.writerow(fila)
    return buffer.getvalue()
