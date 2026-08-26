"""
Nodos territoriales y colectivos oficiales iniciales.

IMPORTANTE: solo el contacto de Pereira/Risaralda y los colectivos oficiales
de abajo están verificados — son datos reales confirmados en medios al
12-13 de agosto de 2026 (ver README). Los demás centros (Chocó, Caldas,
Valle) se crean SIN contacto: alguien debe confirmarlo directamente con la
entidad territorial antes de mostrarlo a nadie. No se inventan teléfonos.

Además de esos 4, se siembran los otros 29 departamentos del país como
centros "dormidos" (activo=False, sin contacto) — así todo Colombia queda
representado en el sistema desde el arranque, no solo donde ya hay
actividad confirmada. Un centro dormido se activa solo, sin intervención
humana, cuando USGS detecta un sismo suficientemente fuerte ahí (ver
integrations/usgs.py), o lo activa a mano un coordinador vía
PATCH /api/v1/centros/{id}/activar — nunca automáticamente por otra razón,
y nunca con contacto inventado.
"""
import os

from sqlalchemy.orm import Session

from . import auth
from .colombia import DEPARTAMENTOS_COLOMBIA
from .models import CentroLocal, Colectivo, NodoCredencial, TipoColectivo

CENTROS_SEED = [
    {
        "id_territorio": "risaralda-pereira",
        "nombre": "Pereira / Risaralda",
        "departamento": "Risaralda",
        "contacto": "(+57) 606 324 8000 — Alcaldía de Pereira, Gestión del Riesgo",
        "contacto_verificado": True,
        "lat": 4.8133,
        "lon": -75.6961,
    },
    {
        "id_territorio": "choco",
        "nombre": "Chocó",
        "departamento": "Chocó",
        "contacto": None,
        "contacto_verificado": False,
        "lat": 5.6947,  # Quibdó, capital departamental — referencia del nodo, no el epicentro
        "lon": -76.6611,
    },
    {
        "id_territorio": "caldas",
        "nombre": "Caldas",
        "departamento": "Caldas",
        "contacto": None,
        "contacto_verificado": False,
        "lat": 5.0703,  # Manizales, capital departamental
        "lon": -75.5138,
    },
    {
        "id_territorio": "valle",
        "nombre": "Valle del Cauca",
        "departamento": "Valle del Cauca",
        "contacto": None,
        "contacto_verificado": False,
        "lat": 3.4516,  # Cali, capital departamental
        "lon": -76.5320,
    },
]

COLECTIVOS_OFICIALES_SEED = [
    {
        "nombre": "Cruz Roja Colombiana — Seccional Pereira",
        "tipo": TipoColectivo.general,
        "descripcion": "Atención de emergencia, voluntariado, reporte de desaparecidos.",
        "zona_cobertura": "Pereira - todas las comunas",
        "contacto": "316 478 1821",
        "verificado": True,
    },
    {
        "nombre": "Hospital Universitario San Jorge — Banco de Sangre",
        "tipo": TipoColectivo.salud,
        "descripcion": (
            "Banco de sangre con escasez confirmada tras el terremoto. "
            "Recibe donantes de todos los tipos de sangre, lunes a sábado 8am-5pm."
        ),
        "zona_cobertura": "Carrera 4 #24-88, Pereira",
        "contacto": "(+57) 606 316 9024",
        "verificado": True,
    },
]


def _crear_centro_con_credencial(db: Session, secreto_hash: str, **kwargs) -> CentroLocal:
    centro = CentroLocal(**kwargs)
    db.add(centro)
    db.commit()
    db.refresh(centro)

    credencial = NodoCredencial(centro_id=centro.id, secreto_hash=secreto_hash)
    db.add(credencial)
    db.commit()
    return centro


def sembrar_datos_iniciales(db: Session) -> None:
    if db.query(CentroLocal).first():
        return

    secreto_inicial = os.getenv("NODOS_SECRETO_INICIAL", "cambia-esto-en-produccion")
    # El mismo secreto se usa para los 33 centros — se hashea una sola vez
    # (bcrypt es deliberadamente lento) en vez de una vez por centro.
    secreto_hash = auth.hash_secreto(secreto_inicial)

    ids_ya_sembrados = set()
    for item in CENTROS_SEED:
        _crear_centro_con_credencial(db, secreto_hash, **item)
        ids_ya_sembrados.add(item["id_territorio"])

    for depto in DEPARTAMENTOS_COLOMBIA:
        if depto["id_territorio"] in ids_ya_sembrados:
            continue
        _crear_centro_con_credencial(
            db, secreto_hash,
            id_territorio=depto["id_territorio"],
            nombre=depto["nombre"],
            departamento=depto["nombre"],
            contacto=None,
            contacto_verificado=False,
            activo=False,
            lat=depto["lat"],
            lon=depto["lon"],
        )

    for item in COLECTIVOS_OFICIALES_SEED:
        db.add(Colectivo(**item))
    db.commit()
