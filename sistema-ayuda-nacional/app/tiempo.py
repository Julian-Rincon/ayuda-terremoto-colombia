"""
Una sola forma de preguntar qué hora es.

`datetime.utcnow()` quedó deprecada y tiene fecha de eliminación, pero su
reemplazo directo (`datetime.now(timezone.utc)`) devuelve un datetime *con*
zona horaria, y las columnas de este modelo son `DateTime` sin zona. Mezclar
los dos tipos revienta en cuanto se comparan ("can't compare offset-naive and
offset-aware datetimes"), y esa comparación ocurre en la detección de
duplicados y en las consultas de sismos recientes.

Así que se conserva la semántica anterior —UTC sin zona— de forma explícita
en un solo lugar, en vez de repetir la conversión en doce archivos. Si alguna
vez se migran las columnas a `DateTime(timezone=True)`, este es el único
punto que hay que tocar.
"""
from datetime import datetime, timezone


def ahora_utc() -> datetime:
    """Hora actual en UTC, sin zona horaria adjunta (como la guarda la base)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
