"""
Nodos territoriales iniciales.

IMPORTANTE: solo el contacto de Pereira/Risaralda está verificado — es el
mismo dato ya confirmado en pereira-ayuda-backend/app/seed_data.py (Alcaldía
de Pereira, línea de Gestión del Riesgo). Los demás nodos (Chocó, Caldas,
Valle) se crean SIN contacto: alguien debe confirmarlo directamente con la
entidad territorial antes de mostrarlo a nadie. No se inventan teléfonos.
"""
import os

from sqlalchemy.orm import Session

from . import auth
from .models import CentroLocal, NodoCredencial

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


def sembrar_datos_iniciales(db: Session) -> None:
    if db.query(CentroLocal).first():
        return

    secreto_inicial = os.getenv("NODOS_SECRETO_INICIAL", "cambia-esto-en-produccion")

    for item in CENTROS_SEED:
        centro = CentroLocal(**item)
        db.add(centro)
        db.commit()
        db.refresh(centro)

        credencial = NodoCredencial(
            centro_id=centro.id,
            secreto_hash=auth.hash_secreto(secreto_inicial),
        )
        db.add(credencial)
        db.commit()
