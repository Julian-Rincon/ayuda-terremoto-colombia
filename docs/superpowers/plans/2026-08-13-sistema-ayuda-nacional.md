# Sistema de Ayuda Nacional — Nodo Central Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Nodo Central backend of the national aid-distribution system described in `planoidea.md` — ingesting citizen reports (WhatsApp, Ushahidi, manual), tracking territorial `CentroLocal` nodes, auto-activating on real earthquakes via USGS, and exporting HXL/SITREP data — with zero payment/donation handling.

**Architecture:** FastAPI + SQLAlchemy (SQLite by default, Postgres via `DATABASE_URL`), same shape as `pereira-ayuda-backend/` but multi-node. Three external integrations (WhatsApp Cloud API, Ushahidi, and — not here, see below) run in **sandbox mode** by default (same payload/signature shape as production, backed by fixtures/simulators) except the USGS poller, which is real and requires no credentials. Payments/donations are explicitly out of scope (see design doc `docs/superpowers/specs/2026-08-13-sistema-ayuda-nacional-design.md` §1).

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx (async HTTP client), PyJWT, bcrypt, pytest, pytest-asyncio.

## Global Constraints

- New code lives entirely under `sistema-ayuda-nacional/`. Never modify `pereira-ayuda-backend/`.
- No `Donacion`, `CanalDonacion`, or any payment/webhook-de-banco code, anywhere.
- Every external integration (WhatsApp, Ushahidi) must work with zero credentials configured (sandbox/fixture mode) and upgrade automatically to real mode when the relevant env var is set — never two code paths, one `if` branch per integration.
- No fabricated contact info (phone numbers, addresses) for any new `CentroLocal` beyond what already exists verified in `pereira-ayuda-backend/app/seed_data.py`.
- Every module with logic gets a pytest file. `pytest` must pass before any commit that touches `app/`.
- No `Co-Authored-By` / AI-tool attribution in any commit message or file.

---

## Task 1: Project scaffolding

**Files:**
- Create: `sistema-ayuda-nacional/requirements.txt`
- Create: `sistema-ayuda-nacional/.env.example`
- Create: `sistema-ayuda-nacional/app/__init__.py`
- Create: `sistema-ayuda-nacional/app/database.py`
- Create: `sistema-ayuda-nacional/tests/__init__.py`
- Create: `sistema-ayuda-nacional/tests/conftest.py`

**Interfaces:**
- Produces: `database.Base` (declarative base), `database.engine`, `database.get_db()` (FastAPI dependency), `database.SessionLocal`.

- [ ] **Step 1: Write requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
pydantic==2.9.2
requests==2.32.3
httpx==0.27.2
python-dotenv==1.0.1
websockets==13.1
PyJWT==2.9.0
bcrypt==4.2.0
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Write .env.example**

```
# Opcional. Sin esto, clasificación por reglas (gratis, sin red).
GROQ_API_KEY=

# Opcional. Por defecto SQLite local.
DATABASE_URL=sqlite:///./sistema_ayuda_nacional.db

# Firma real de webhooks de WhatsApp Cloud API (Meta). Sin esto, el
# webhook de WhatsApp corre en modo sandbox (no valida firma).
WHATSAPP_APP_SECRET=

# URL base de una instancia Ushahidi real, ej. https://mi-instancia.ushahidi.io
# Sin esto, la sincronización usa datos de ejemplo (fixture).
USHAHIDI_BASE_URL=

# Firma usada para emitir/validar JWT de nodos locales. CAMBIAR antes de
# cualquier despliegue real.
JWT_SECRET=cambia-esto-en-produccion

# Secreto inicial compartido para los CentroLocal sembrados. CAMBIAR antes
# de cualquier despliegue real (o rotar credenciales por nodo).
NODOS_SECRETO_INICIAL=cambia-esto-en-produccion
```

- [ ] **Step 3: Write app/database.py**

```python
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sistema_ayuda_nacional.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Write tests/conftest.py — shared in-memory DB fixture for all tests**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 5: Create empty `app/__init__.py` and `tests/__init__.py`, verify imports work**

Run: `cd sistema-ayuda-nacional && python3 -c "from app.database import Base, get_db; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add sistema-ayuda-nacional/requirements.txt sistema-ayuda-nacional/.env.example \
        sistema-ayuda-nacional/app/__init__.py sistema-ayuda-nacional/app/database.py \
        sistema-ayuda-nacional/tests/__init__.py sistema-ayuda-nacional/tests/conftest.py
git commit -m "Nodo Central: scaffolding y conexión a base de datos"
```

---

## Task 2: Data models

**Files:**
- Create: `sistema-ayuda-nacional/app/models.py`
- Test: `sistema-ayuda-nacional/tests/test_models.py`

**Interfaces:**
- Consumes: `database.Base` (Task 1).
- Produces: `models.CategoriaNecesidad`, `models.UrgenciaReporte`, `models.EstadoSolicitud`, `models.CanalReporte` (str Enums); `models.CentroLocal`, `models.ReporteCiudadano`, `models.Solicitud`, `models.EventoSismico`, `models.NodoCredencial` (SQLAlchemy models).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from app import models


def test_crear_centro_local_y_reporte_y_solicitud(db_session):
    centro = models.CentroLocal(
        id_territorio="choco",
        nombre="Chocó",
        departamento="Chocó",
        contacto=None,
        contacto_verificado=False,
    )
    db_session.add(centro)
    db_session.commit()
    db_session.refresh(centro)

    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.whatsapp,
        contenido_original="Familia sin agua potable en zona rural",
        categoria=models.CategoriaNecesidad.agua,
        urgencia=models.UrgenciaReporte.media,
        centro_id=centro.id,
    )
    db_session.add(reporte)
    db_session.commit()
    db_session.refresh(reporte)

    solicitud = models.Solicitud(
        reporte_id=reporte.id,
        centro_id=centro.id,
        categoria=models.CategoriaNecesidad.agua,
        estado=models.EstadoSolicitud.pendiente,
    )
    db_session.add(solicitud)
    db_session.commit()
    db_session.refresh(solicitud)

    assert solicitud.centro.id_territorio == "choco"
    assert solicitud.reporte.contenido_original.startswith("Familia sin agua")
    assert centro.reportes[0].id == reporte.id


def test_evento_sismico_requiere_id_externo_unico(db_session):
    from datetime import datetime, timezone

    evento = models.EventoSismico(
        id_externo="us1234",
        magnitud=7.4,
        profundidad=103.0,
        lat=4.99,
        lon=-76.29,
        lugar="San José del Palmar, Chocó",
        timestamp=datetime.now(timezone.utc),
        activo_modo_emergencia=True,
    )
    db_session.add(evento)
    db_session.commit()
    db_session.refresh(evento)
    assert evento.activo_modo_emergencia is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write app/models.py**

```python
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class CategoriaNecesidad(str, enum.Enum):
    alimentos = "alimentos"
    agua = "agua"
    refugio = "refugio"
    salud = "salud"
    medicamentos = "medicamentos"
    aseo = "aseo"
    ropa = "ropa"
    rescate_escombros = "rescate_escombros"
    mascotas = "mascotas"
    reconstruccion = "reconstruccion"
    otro = "otro"


class UrgenciaReporte(str, enum.Enum):
    alta = "alta"
    media = "media"
    baja = "baja"
    sin_clasificar = "sin_clasificar"


class EstadoSolicitud(str, enum.Enum):
    pendiente = "pendiente"
    asignada = "asignada"
    en_proceso = "en_proceso"
    completada = "completada"
    descartada = "descartada"


class CanalReporte(str, enum.Enum):
    whatsapp = "whatsapp"
    ushahidi = "ushahidi"
    web = "web"
    sms = "sms"
    manual = "manual"


class CentroLocal(Base):
    __tablename__ = "centros_locales"

    id = Column(Integer, primary_key=True, index=True)
    id_territorio = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    departamento = Column(String(100), nullable=False, index=True)
    contacto = Column(String(200), nullable=True)
    contacto_verificado = Column(Boolean, default=False)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    solicitudes = relationship("Solicitud", back_populates="centro")
    reportes = relationship("ReporteCiudadano", back_populates="centro")


class ReporteCiudadano(Base):
    __tablename__ = "reportes_ciudadanos"

    id = Column(Integer, primary_key=True, index=True)
    id_externo = Column(String(120), nullable=True, index=True)
    canal = Column(Enum(CanalReporte), nullable=False)
    contenido_original = Column(Text, nullable=False)

    categoria = Column(Enum(CategoriaNecesidad), default=CategoriaNecesidad.otro, index=True)
    urgencia = Column(Enum(UrgenciaReporte), default=UrgenciaReporte.sin_clasificar, index=True)
    resumen_ia = Column(Text, nullable=True)
    clasificado_por_ia = Column(Boolean, default=False)

    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    zona = Column(String(120), nullable=True)

    verificado = Column(Boolean, default=False)

    centro_id = Column(Integer, ForeignKey("centros_locales.id"), nullable=True)
    centro = relationship("CentroLocal", back_populates="reportes")

    creado_en = Column(DateTime, default=datetime.utcnow)


class Solicitud(Base):
    __tablename__ = "solicitudes"

    id = Column(Integer, primary_key=True, index=True)

    reporte_id = Column(Integer, ForeignKey("reportes_ciudadanos.id"), nullable=True)
    reporte = relationship("ReporteCiudadano")

    centro_id = Column(Integer, ForeignKey("centros_locales.id"), nullable=False)
    centro = relationship("CentroLocal", back_populates="solicitudes")

    categoria = Column(Enum(CategoriaNecesidad), nullable=False, index=True)
    estado = Column(Enum(EstadoSolicitud), default=EstadoSolicitud.pendiente, index=True)

    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EventoSismico(Base):
    __tablename__ = "eventos_sismicos"

    id = Column(Integer, primary_key=True, index=True)
    id_externo = Column(String(120), unique=True, nullable=False)
    magnitud = Column(Float, nullable=False)
    profundidad = Column(Float, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    lugar = Column(String(300), nullable=True)
    fuente = Column(String(30), default="usgs")
    timestamp = Column(DateTime, nullable=False)
    activo_modo_emergencia = Column(Boolean, default=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class NodoCredencial(Base):
    __tablename__ = "nodo_credenciales"

    id = Column(Integer, primary_key=True, index=True)
    centro_id = Column(Integer, ForeignKey("centros_locales.id"), nullable=False, unique=True)
    centro = relationship("CentroLocal")
    secreto_hash = Column(String(200), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_models.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/models.py sistema-ayuda-nacional/tests/test_models.py
git commit -m "Nodo Central: modelos de datos (CentroLocal, ReporteCiudadano, Solicitud, EventoSismico)"
```

---

## Task 3: Pydantic schemas

**Files:**
- Create: `sistema-ayuda-nacional/app/schemas.py`

**Interfaces:**
- Consumes: `models.*` enums and models (Task 2).
- Produces: `schemas.CentroLocalOut`, `schemas.ReporteCiudadanoCreate`, `schemas.ReporteCiudadanoOut`, `schemas.SolicitudOut`, `schemas.EventoSismicoOut`, `schemas.TokenOut`.

No dedicated test file — schemas are validated indirectly through the endpoint tests in Task 8 (FastAPI raises at import time if a schema is malformed, and every endpoint test exercises `response_model` serialization).

- [ ] **Step 1: Write app/schemas.py**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import CanalReporte, CategoriaNecesidad, EstadoSolicitud, UrgenciaReporte


class CentroLocalOut(BaseModel):
    id: int
    id_territorio: str
    nombre: str
    departamento: str
    contacto: Optional[str]
    contacto_verificado: bool
    activo: bool

    class Config:
        from_attributes = True


class ReporteCiudadanoCreate(BaseModel):
    contenido: str = Field(..., min_length=3)
    zona: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    canal: CanalReporte = CanalReporte.manual


class ReporteCiudadanoOut(BaseModel):
    id: int
    id_externo: Optional[str]
    canal: CanalReporte
    contenido_original: str
    categoria: CategoriaNecesidad
    urgencia: UrgenciaReporte
    resumen_ia: Optional[str]
    clasificado_por_ia: bool
    lat: Optional[float]
    lon: Optional[float]
    zona: Optional[str]
    verificado: bool
    centro_id: Optional[int]
    creado_en: datetime

    class Config:
        from_attributes = True


class ReporteVerificar(BaseModel):
    centro_id: int


class SolicitudOut(BaseModel):
    id: int
    reporte_id: Optional[int]
    centro_id: int
    categoria: CategoriaNecesidad
    estado: EstadoSolicitud
    creado_en: datetime

    class Config:
        from_attributes = True


class NecesidadesCentro(BaseModel):
    centro_id: int
    pendientes_por_categoria: dict[str, int]
    total_pendientes: int


class EventoSismicoOut(BaseModel):
    id: int
    id_externo: str
    magnitud: float
    profundidad: Optional[float]
    lat: float
    lon: float
    lugar: Optional[str]
    fuente: str
    timestamp: datetime
    activo_modo_emergencia: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    id_territorio: str
    secreto: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd sistema-ayuda-nacional && python3 -c "from app import schemas; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add sistema-ayuda-nacional/app/schemas.py
git commit -m "Nodo Central: schemas Pydantic"
```

---

## Task 4: AI classification helper

**Files:**
- Create: `sistema-ayuda-nacional/app/ai_helper.py`
- Test: `sistema-ayuda-nacional/tests/test_ai_helper.py`

**Interfaces:**
- Produces: `ai_helper.clasificar_reporte(descripcion: str) -> dict` with keys `categoria` (str matching a `CategoriaNecesidad` value), `urgencia` (str matching `UrgenciaReporte` value), `resumen` (str), `clasificado_por_ia` (bool). Never raises; always returns a usable dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai_helper.py
from app import ai_helper


def test_clasificar_por_reglas_detecta_rescate_urgente(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # forzar fallback por reglas
    resultado = ai_helper.clasificar_reporte("Hay dos personas atrapadas bajo escombros, urgente")
    assert resultado["categoria"] == "rescate_escombros"
    assert resultado["urgencia"] == "alta"
    assert resultado["clasificado_por_ia"] is False


def test_clasificar_por_reglas_categoria_agua(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    resultado = ai_helper.clasificar_reporte("Llevamos tres días sin agua potable")
    assert resultado["categoria"] == "agua"


def test_clasificar_nunca_lanza_excepcion_si_groq_falla(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "llave-invalida")

    def _falla(*args, **kwargs):
        raise ConnectionError("sin red")

    monkeypatch.setattr(ai_helper.requests, "post", _falla)
    resultado = ai_helper.clasificar_reporte("Necesitamos carpas para dormir")
    assert resultado["categoria"] in ai_helper.CATEGORIAS_VALIDAS
    assert resultado["clasificado_por_ia"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_ai_helper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai_helper'`

- [ ] **Step 3: Write app/ai_helper.py**

```python
"""
Clasificación de reportes ciudadanos — gratuita por defecto.

Usa Groq (https://console.groq.com) si hay GROQ_API_KEY configurada. Si no,
o si la llamada falla por cualquier razón, cae a un clasificador por
palabras clave que nunca falla y no depende de internet.
"""
import json
import os
from typing import Optional

import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

CATEGORIAS_VALIDAS = [
    "alimentos", "agua", "refugio", "salud", "medicamentos",
    "aseo", "ropa", "rescate_escombros", "mascotas", "reconstruccion", "otro",
]

_PALABRAS_CLAVE = {
    "rescate_escombros": ["atrapad", "escombro", "colapsó", "colapso", "derrumb", "sepultad"],
    "salud": ["herid", "sangre", "médic", "medico", "hospital", "fractura"],
    "medicamentos": ["medicamento", "insulina", "pastilla", "tratamiento"],
    "agua": ["agua potable", "sed", "sin agua"],
    "alimentos": ["comida", "alimento", "hambre", "leche", "víveres", "viveres"],
    "refugio": ["carpa", "colchoneta", "dormir", "sin techo", "alberg"],
    "aseo": ["jabón", "jabon", "pañal", "panal", "aseo"],
    "ropa": ["ropa", "cobija", "manta", "abrigo"],
    "mascotas": ["perro", "gato", "mascota"],
    "reconstruccion": ["reconstruir", "reparar vivienda", "material de construcción"],
}

_URGENCIA_ALTA = ["atrapad", "sepultad", "sangrando", "no respira", "urgente", "muriendo"]


def _clasificar_por_reglas(descripcion: str) -> dict:
    texto = descripcion.lower()
    categoria = "otro"
    for cat, palabras in _PALABRAS_CLAVE.items():
        if any(p in texto for p in palabras):
            categoria = cat
            break
    urgencia = "alta" if any(p in texto for p in _URGENCIA_ALTA) else "media"
    return {
        "categoria": categoria,
        "urgencia": urgencia,
        "resumen": descripcion[:180],
        "clasificado_por_ia": False,
    }


def _clasificar_con_groq(descripcion: str) -> Optional[dict]:
    if not GROQ_API_KEY:
        return None

    prompt = (
        "Eres un asistente de triage para ayuda humanitaria tras el terremoto en "
        "Colombia (10 ago 2026). Clasifica este reporte ciudadano. Responde SOLO "
        "con JSON válido, sin texto adicional, con este formato exacto:\n"
        f'{{"categoria": "<una de: {", ".join(CATEGORIAS_VALIDAS)}>", '
        '"urgencia": "<alta|media|baja>", "resumen": "<máximo 25 palabras>"}\n\n'
        f'Reporte: "{descripcion}"'
    )
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 200,
            },
            timeout=10,
        )
        resp.raise_for_status()
        contenido = resp.json()["choices"][0]["message"]["content"].strip()
        contenido = contenido.replace("```json", "").replace("```", "").strip()
        data = json.loads(contenido)

        if data.get("categoria") not in CATEGORIAS_VALIDAS:
            data["categoria"] = "otro"
        if data.get("urgencia") not in ("alta", "media", "baja"):
            data["urgencia"] = "media"
        data["clasificado_por_ia"] = True
        return data
    except Exception:
        return None


def clasificar_reporte(descripcion: str) -> dict:
    resultado = _clasificar_con_groq(descripcion)
    if resultado is None:
        resultado = _clasificar_por_reglas(descripcion)
    return resultado
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_ai_helper.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/ai_helper.py sistema-ayuda-nacional/tests/test_ai_helper.py
git commit -m "Nodo Central: clasificación de reportes (Groq gratis + fallback por reglas)"
```

---

## Task 5: Auth (JWT for nodes, webhook signature validation)

**Files:**
- Create: `sistema-ayuda-nacional/app/auth.py`
- Test: `sistema-ayuda-nacional/tests/test_auth.py`

**Interfaces:**
- Produces: `auth.hash_secreto(secreto) -> str`, `auth.verificar_secreto(secreto, hash_guardado) -> bool`, `auth.generar_token(centro_id, id_territorio) -> str`, `auth.decodificar_token(token) -> dict` (raises `fastapi.HTTPException(401)` on invalid/expired), `auth.requerir_centro_autenticado(authorization: str | None) -> dict` (FastAPI dependency), `auth.validar_firma_whatsapp(payload_bytes, firma_header) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth.py
import time

import pytest
from fastapi import HTTPException

from app import auth


def test_hash_y_verificar_secreto_roundtrip():
    hash_guardado = auth.hash_secreto("clave-super-secreta")
    assert auth.verificar_secreto("clave-super-secreta", hash_guardado) is True
    assert auth.verificar_secreto("clave-incorrecta", hash_guardado) is False


def test_generar_y_decodificar_token_roundtrip():
    token = auth.generar_token(centro_id=1, id_territorio="risaralda-pereira")
    payload = auth.decodificar_token(token)
    assert payload["centro_id"] == 1
    assert payload["id_territorio"] == "risaralda-pereira"


def test_decodificar_token_invalido_lanza_401():
    with pytest.raises(HTTPException) as exc_info:
        auth.decodificar_token("esto-no-es-un-jwt-valido")
    assert exc_info.value.status_code == 401


def test_requerir_centro_autenticado_sin_header_lanza_401():
    with pytest.raises(HTTPException) as exc_info:
        auth.requerir_centro_autenticado(authorization=None)
    assert exc_info.value.status_code == 401


def test_validar_firma_whatsapp_modo_sandbox_sin_secreto(monkeypatch):
    monkeypatch.setattr(auth.os, "getenv", lambda k, d="": "" if k == "WHATSAPP_APP_SECRET" else d)
    assert auth.validar_firma_whatsapp(b"cualquier payload", None) is True


def test_validar_firma_whatsapp_con_secreto_real(monkeypatch):
    import hashlib
    import hmac

    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secreto-de-meta")
    payload = b'{"campo": "valor"}'
    firma_correcta = "sha256=" + hmac.new(b"secreto-de-meta", payload, hashlib.sha256).hexdigest()

    assert auth.validar_firma_whatsapp(payload, firma_correcta) is True
    assert auth.validar_firma_whatsapp(payload, "sha256=firmaincorrecta") is False
    assert auth.validar_firma_whatsapp(payload, None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`

- [ ] **Step 3: Write app/auth.py**

```python
import hashlib
import hmac
import os
import time
from typing import Optional

import bcrypt
import jwt
from fastapi import Header, HTTPException

JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esto-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXPIRA_SEGUNDOS = 60 * 60 * 12  # 12 horas


def hash_secreto(secreto: str) -> str:
    return bcrypt.hashpw(secreto.encode(), bcrypt.gensalt()).decode()


def verificar_secreto(secreto: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(secreto.encode(), hash_guardado.encode())


def generar_token(centro_id: int, id_territorio: str) -> str:
    payload = {
        "centro_id": centro_id,
        "id_territorio": id_territorio,
        "exp": int(time.time()) + JWT_EXPIRA_SEGUNDOS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o expirado")


def requerir_centro_autenticado(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta el header Authorization: Bearer <token>")
    token = authorization[len("Bearer "):].strip()
    return decodificar_token(token)


def validar_firma_whatsapp(payload_bytes: bytes, firma_header: Optional[str]) -> bool:
    """
    Valida X-Hub-Signature-256 de Meta. En modo sandbox (sin WHATSAPP_APP_SECRET
    configurado) siempre retorna True para permitir pruebas locales.
    """
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    if not app_secret:
        return True
    if not firma_header or not firma_header.startswith("sha256="):
        return False
    firma_esperada = hmac.new(app_secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    firma_recibida = firma_header[len("sha256="):]
    return hmac.compare_digest(firma_esperada, firma_recibida)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_auth.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/auth.py sistema-ayuda-nacional/tests/test_auth.py
git commit -m "Nodo Central: autenticación JWT por centro y validación de firma de webhooks"
```

---

## Task 6: Seed data

**Files:**
- Create: `sistema-ayuda-nacional/app/seed_data.py`
- Test: `sistema-ayuda-nacional/tests/test_seed_data.py`

**Interfaces:**
- Consumes: `models.CentroLocal`, `models.NodoCredencial` (Task 2), `auth.hash_secreto` (Task 5).
- Produces: `seed_data.sembrar_datos_iniciales(db: Session) -> None` (idempotent).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_data.py
from app import models, seed_data


def test_sembrar_datos_iniciales_crea_cuatro_centros(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    centros = db_session.query(models.CentroLocal).all()
    ids_territorio = {c.id_territorio for c in centros}
    assert ids_territorio == {"risaralda-pereira", "choco", "caldas", "valle"}


def test_sembrar_datos_iniciales_es_idempotente(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.CentroLocal).count() == 4


def test_centros_no_verificados_no_tienen_contacto_inventado(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    choco = db_session.query(models.CentroLocal).filter_by(id_territorio="choco").first()
    assert choco.contacto is None
    assert choco.contacto_verificado is False


def test_cada_centro_tiene_credencial(db_session):
    seed_data.sembrar_datos_iniciales(db_session)
    assert db_session.query(models.NodoCredencial).count() == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_seed_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed_data'`

- [ ] **Step 3: Write app/seed_data.py**

```python
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
    },
    {
        "id_territorio": "choco",
        "nombre": "Chocó",
        "departamento": "Chocó",
        "contacto": None,
        "contacto_verificado": False,
    },
    {
        "id_territorio": "caldas",
        "nombre": "Caldas",
        "departamento": "Caldas",
        "contacto": None,
        "contacto_verificado": False,
    },
    {
        "id_territorio": "valle",
        "nombre": "Valle del Cauca",
        "departamento": "Valle del Cauca",
        "contacto": None,
        "contacto_verificado": False,
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_seed_data.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/seed_data.py sistema-ayuda-nacional/tests/test_seed_data.py
git commit -m "Nodo Central: siembra de centros territoriales, sin contactos inventados"
```

---

## Task 7: Assignment pipeline

**Files:**
- Create: `sistema-ayuda-nacional/app/pipeline.py`
- Test: `sistema-ayuda-nacional/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `models.*` (Task 2).
- Produces: `pipeline.crear_solicitud_desde_reporte(db, reporte) -> models.Solicitud` (raises `ValueError` if reporte not verified or has no centro), `pipeline.priorizar_solicitudes_pendientes(db) -> list[models.Solicitud]` (sorted highest urgency + oldest first).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from datetime import datetime, timedelta

import pytest

from app import models, pipeline


def _crear_centro(db):
    centro = models.CentroLocal(id_territorio="choco", nombre="Chocó", departamento="Chocó")
    db.add(centro)
    db.commit()
    db.refresh(centro)
    return centro


def test_crear_solicitud_desde_reporte_no_verificado_lanza_error(db_session):
    centro = _crear_centro(db_session)
    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.web,
        contenido_original="test",
        categoria=models.CategoriaNecesidad.agua,
        centro_id=centro.id,
        verificado=False,
    )
    db_session.add(reporte)
    db_session.commit()
    db_session.refresh(reporte)

    with pytest.raises(ValueError):
        pipeline.crear_solicitud_desde_reporte(db_session, reporte)


def test_crear_solicitud_desde_reporte_verificado(db_session):
    centro = _crear_centro(db_session)
    reporte = models.ReporteCiudadano(
        canal=models.CanalReporte.web,
        contenido_original="test",
        categoria=models.CategoriaNecesidad.agua,
        centro_id=centro.id,
        verificado=True,
    )
    db_session.add(reporte)
    db_session.commit()
    db_session.refresh(reporte)

    solicitud = pipeline.crear_solicitud_desde_reporte(db_session, reporte)
    assert solicitud.centro_id == centro.id
    assert solicitud.categoria == models.CategoriaNecesidad.agua
    assert solicitud.estado == models.EstadoSolicitud.pendiente


def test_priorizar_solicitudes_urgencia_alta_primero(db_session):
    centro = _crear_centro(db_session)

    reporte_media = models.ReporteCiudadano(
        canal=models.CanalReporte.web, contenido_original="a",
        categoria=models.CategoriaNecesidad.agua, urgencia=models.UrgenciaReporte.media,
        centro_id=centro.id, verificado=True,
    )
    reporte_alta = models.ReporteCiudadano(
        canal=models.CanalReporte.web, contenido_original="b",
        categoria=models.CategoriaNecesidad.rescate_escombros, urgencia=models.UrgenciaReporte.alta,
        centro_id=centro.id, verificado=True,
    )
    db_session.add_all([reporte_media, reporte_alta])
    db_session.commit()
    db_session.refresh(reporte_media)
    db_session.refresh(reporte_alta)

    solicitud_media = pipeline.crear_solicitud_desde_reporte(db_session, reporte_media)
    solicitud_alta = pipeline.crear_solicitud_desde_reporte(db_session, reporte_alta)

    priorizadas = pipeline.priorizar_solicitudes_pendientes(db_session)

    assert priorizadas[0].id == solicitud_alta.id
    assert priorizadas[1].id == solicitud_media.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline'`

- [ ] **Step 3: Write app/pipeline.py**

```python
"""
Pipeline de asignación (planoidea.md §5), adaptado para recursos en especie:
no reparte presupuesto (no hay donaciones en este sistema — ver spec §1),
ordena atención humana por urgencia y antigüedad.
"""
from sqlalchemy.orm import Session

from . import models

PESO_URGENCIA = {
    models.UrgenciaReporte.alta: 3,
    models.UrgenciaReporte.media: 2,
    models.UrgenciaReporte.baja: 1,
    models.UrgenciaReporte.sin_clasificar: 1,
}


def crear_solicitud_desde_reporte(db: Session, reporte: models.ReporteCiudadano) -> models.Solicitud:
    """
    Convierte un ReporteCiudadano YA VERIFICADO por un humano en una Solicitud
    formal asignada a su CentroLocal.
    """
    if not reporte.verificado:
        raise ValueError("No se puede crear una solicitud desde un reporte sin verificar")
    if not reporte.centro_id:
        raise ValueError("El reporte no tiene centro local asignado")

    solicitud = models.Solicitud(
        reporte_id=reporte.id,
        centro_id=reporte.centro_id,
        categoria=reporte.categoria,
        estado=models.EstadoSolicitud.pendiente,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


def priorizar_solicitudes_pendientes(db: Session) -> list[models.Solicitud]:
    """Ordena las solicitudes pendientes: mayor urgencia primero, luego más antiguas primero."""
    pendientes = (
        db.query(models.Solicitud)
        .filter(models.Solicitud.estado == models.EstadoSolicitud.pendiente)
        .all()
    )

    def clave_prioridad(s: models.Solicitud):
        urgencia = s.reporte.urgencia if s.reporte else models.UrgenciaReporte.sin_clasificar
        peso = PESO_URGENCIA.get(urgencia, 1)
        return (-peso, s.creado_en)

    return sorted(pendientes, key=clave_prioridad)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_pipeline.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/pipeline.py sistema-ayuda-nacional/tests/test_pipeline.py
git commit -m "Nodo Central: pipeline de asignación (priorización, no monetario)"
```

---

## Task 8: HXL export

**Files:**
- Create: `sistema-ayuda-nacional/app/hxl_export.py`
- Test: `sistema-ayuda-nacional/tests/test_hxl_export.py`

**Interfaces:**
- Produces: `hxl_export.generar_sitrep_hxl(db: Session) -> str` (CSV text with HXL header tags).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hxl_export.py
from app import hxl_export, models


def test_generar_sitrep_hxl_incluye_encabezados_hxl(db_session):
    csv_texto = hxl_export.generar_sitrep_hxl(db_session)
    primera_linea = csv_texto.splitlines()[0]
    assert primera_linea == "#loc+name,#affected+num,#need+category,#date+reported"


def test_generar_sitrep_hxl_agrega_por_departamento_y_categoria(db_session):
    centro = models.CentroLocal(id_territorio="choco", nombre="Chocó", departamento="Chocó")
    db_session.add(centro)
    db_session.commit()
    db_session.refresh(centro)

    for _ in range(3):
        db_session.add(models.Solicitud(centro_id=centro.id, categoria=models.CategoriaNecesidad.agua))
    db_session.commit()

    csv_texto = hxl_export.generar_sitrep_hxl(db_session)
    lineas = csv_texto.splitlines()
    assert len(lineas) == 2  # encabezado + 1 fila agregada
    assert "Chocó" in lineas[1]
    assert "3" in lineas[1]
    assert "agua" in lineas[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_hxl_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.hxl_export'`

- [ ] **Step 3: Write app/hxl_export.py**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_hxl_export.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/hxl_export.py sistema-ayuda-nacional/tests/test_hxl_export.py
git commit -m "Nodo Central: export HXL para HDX/ONG internacionales"
```

---

## Task 9: WebSocket manager

**Files:**
- Create: `sistema-ayuda-nacional/app/websocket_manager.py`

No dedicated test — exercised through the `/ws` integration test in Task 13.

- [ ] **Step 1: Write app/websocket_manager.py**

```python
import json

from fastapi import WebSocket


class ConnectionManager:
    """Broadcast simple para dashboards en tiempo real."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, tipo: str, data: dict):
        mensaje = json.dumps({"tipo": tipo, "data": data}, default=str)
        vivos = []
        for connection in self.active_connections:
            try:
                await connection.send_text(mensaje)
                vivos.append(connection)
            except Exception:
                pass
        self.active_connections = vivos


manager = ConnectionManager()
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd sistema-ayuda-nacional && python3 -c "from app.websocket_manager import manager; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add sistema-ayuda-nacional/app/websocket_manager.py
git commit -m "Nodo Central: broadcast en tiempo real por WebSocket"
```

---

## Task 10: USGS integration (real, no credentials needed)

**Files:**
- Create: `sistema-ayuda-nacional/app/integrations/__init__.py`
- Create: `sistema-ayuda-nacional/app/integrations/usgs.py`
- Test: `sistema-ayuda-nacional/tests/test_usgs.py`

**Interfaces:**
- Produces: `usgs.escuchar_usgs_una_vez(db: Session) -> list[models.EventoSismico]` (fetches the real USGS feed, dedupes, filters to Colombia bounding box, flags `activo_modo_emergencia` when `magnitud >= 6.0`), `usgs.escuchar_usgs_loop()` (infinite poller for `main.py` startup, not unit-tested directly), `usgs.MAGNITUD_UMBRAL_EMERGENCIA`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_usgs.py
import httpx
import pytest

from app import models
from app.integrations import usgs

FEATURE_COLOMBIA_M74 = {
    "type": "Feature",
    "id": "us_test_74",
    "properties": {"mag": 7.4, "place": "San José del Palmar, Chocó", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-76.29, 4.99, 103.0]},
}

FEATURE_FUERA_DE_COLOMBIA = {
    "type": "Feature",
    "id": "us_test_otro_pais",
    "properties": {"mag": 7.8, "place": "Chile", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-70.6, -33.4, 50.0]},
}

FEATURE_COLOMBIA_LEVE = {
    "type": "Feature",
    "id": "us_test_leve",
    "properties": {"mag": 3.1, "place": "Bogotá", "time": 1786452867000},
    "geometry": {"type": "Point", "coordinates": [-74.08, 4.71, 10.0]},
}


@pytest.mark.asyncio
async def test_escuchar_usgs_activa_modo_emergencia_para_sismo_colombiano_fuerte(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_M74]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)

    assert len(eventos) == 1
    assert eventos[0].activo_modo_emergencia is True
    assert db_session.query(models.EventoSismico).filter_by(id_externo="us_test_74").count() == 1


@pytest.mark.asyncio
async def test_escuchar_usgs_ignora_sismos_fuera_de_colombia(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_FUERA_DE_COLOMBIA]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)
    assert eventos == []


@pytest.mark.asyncio
async def test_escuchar_usgs_no_activa_emergencia_bajo_el_umbral(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_LEVE]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)
    assert len(eventos) == 1
    assert eventos[0].activo_modo_emergencia is False


@pytest.mark.asyncio
async def test_escuchar_usgs_no_duplica_eventos_ya_guardados(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"features": [FEATURE_COLOMBIA_M74]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    await usgs.escuchar_usgs_una_vez(db_session)
    eventos_segunda_pasada = await usgs.escuchar_usgs_una_vez(db_session)

    assert eventos_segunda_pasada == []
    assert db_session.query(models.EventoSismico).count() == 1


@pytest.mark.asyncio
async def test_escuchar_usgs_nunca_lanza_si_la_red_falla(db_session, monkeypatch):
    async def _mock_get(self, url, **kwargs):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    eventos = await usgs.escuchar_usgs_una_vez(db_session)
    assert eventos == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_usgs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.integrations'`

- [ ] **Step 3: Write app/integrations/__init__.py (empty) and app/integrations/usgs.py**

```python
# app/integrations/usgs.py
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
```

- [ ] **Step 4: Add pytest-asyncio config and run tests**

Add to `sistema-ayuda-nacional/` a `pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

Run: `cd sistema-ayuda-nacional && pytest tests/test_usgs.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/integrations/__init__.py sistema-ayuda-nacional/app/integrations/usgs.py \
        sistema-ayuda-nacional/tests/test_usgs.py sistema-ayuda-nacional/pytest.ini
git commit -m "Nodo Central: auto-activación real vía feed público de USGS"
```

---

## Task 11: WhatsApp integration (sandbox)

**Files:**
- Create: `sistema-ayuda-nacional/app/integrations/whatsapp.py`
- Test: `sistema-ayuda-nacional/tests/test_whatsapp.py`

**Interfaces:**
- Consumes: `ai_helper.clasificar_reporte` (Task 4).
- Produces: `whatsapp.parsear_mensaje_entrante(payload: dict) -> dict | None`, `whatsapp.construir_reporte_desde_whatsapp(mensaje: dict) -> models.ReporteCiudadano` (not yet added to session).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_whatsapp.py
from app import models
from app.integrations import whatsapp

PAYLOAD_TEXTO_META = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "573001234567",
                    "type": "text",
                    "text": {"body": "Necesitamos agua potable urgente en el barrio"},
                }]
            }
        }]
    }]
}

PAYLOAD_UBICACION_META = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "573001234567",
                    "type": "location",
                    "location": {"latitude": 4.8087, "longitude": -75.6906, "name": "Cuba, Pereira"},
                }]
            }
        }]
    }]
}

PAYLOAD_SIN_MENSAJES = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}


def test_parsear_mensaje_de_texto():
    mensaje = whatsapp.parsear_mensaje_entrante(PAYLOAD_TEXTO_META)
    assert mensaje["remitente"] == "573001234567"
    assert "agua potable" in mensaje["texto"]
    assert mensaje["ubicacion"] is None


def test_parsear_mensaje_de_ubicacion():
    mensaje = whatsapp.parsear_mensaje_entrante(PAYLOAD_UBICACION_META)
    assert mensaje["ubicacion"] == {"lat": 4.8087, "lon": -75.6906}


def test_parsear_payload_sin_mensajes_retorna_none():
    assert whatsapp.parsear_mensaje_entrante(PAYLOAD_SIN_MENSAJES) is None


def test_parsear_payload_malformado_retorna_none():
    assert whatsapp.parsear_mensaje_entrante({}) is None


def test_construir_reporte_desde_whatsapp_clasifica_y_arma_modelo(monkeypatch):
    from app import ai_helper
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # fallback por reglas, determinístico

    mensaje = {"remitente": "573001234567", "texto": "Familia atrapada bajo escombros", "ubicacion": None}
    reporte = whatsapp.construir_reporte_desde_whatsapp(mensaje)

    assert isinstance(reporte, models.ReporteCiudadano)
    assert reporte.canal == models.CanalReporte.whatsapp
    assert reporte.id_externo == "573001234567"
    assert reporte.categoria == models.CategoriaNecesidad.rescate_escombros
    assert reporte.urgencia == models.UrgenciaReporte.alta
    assert reporte.verificado is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_whatsapp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.integrations.whatsapp'`

- [ ] **Step 3: Write app/integrations/whatsapp.py**

```python
"""
Ingesta vía WhatsApp Business Cloud API — planoidea.md §3.2/§5.

Modo sandbox por defecto: sin WHATSAPP_APP_SECRET configurado, el webhook
en main.py acepta cualquier payload (ver auth.validar_firma_whatsapp). El
parseo de abajo usa exactamente el formato real de Meta Graph API — cuando
haya credenciales reales, esto no cambia.
"""
from typing import Optional

from .. import models
from ..ai_helper import clasificar_reporte


def parsear_mensaje_entrante(payload: dict) -> Optional[dict]:
    try:
        entry = payload["entry"][0]
        valor = entry["changes"][0]["value"]
        mensajes = valor.get("messages")
        if not mensajes:
            return None
        mensaje = mensajes[0]
    except (KeyError, IndexError, TypeError):
        return None

    remitente = mensaje.get("from")
    texto = None
    ubicacion = None

    if mensaje.get("type") == "text":
        texto = mensaje.get("text", {}).get("body")
    elif mensaje.get("type") == "location":
        loc = mensaje.get("location", {})
        if loc.get("latitude") is not None and loc.get("longitude") is not None:
            ubicacion = {"lat": loc["latitude"], "lon": loc["longitude"]}
        texto = loc.get("name") or loc.get("address") or ""

    if not remitente or texto is None:
        return None

    return {"remitente": remitente, "texto": texto, "ubicacion": ubicacion}


def construir_reporte_desde_whatsapp(mensaje: dict) -> models.ReporteCiudadano:
    clasificacion = clasificar_reporte(mensaje["texto"])
    ubicacion = mensaje.get("ubicacion") or {}
    return models.ReporteCiudadano(
        id_externo=mensaje["remitente"],
        canal=models.CanalReporte.whatsapp,
        contenido_original=mensaje["texto"],
        categoria=clasificacion["categoria"],
        urgencia=clasificacion["urgencia"],
        resumen_ia=clasificacion["resumen"],
        clasificado_por_ia=clasificacion["clasificado_por_ia"],
        lat=ubicacion.get("lat"),
        lon=ubicacion.get("lon"),
        verificado=False,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_whatsapp.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/integrations/whatsapp.py sistema-ayuda-nacional/tests/test_whatsapp.py
git commit -m "Nodo Central: ingesta WhatsApp Business Cloud API (sandbox por defecto)"
```

---

## Task 12: Ushahidi integration (sandbox with realistic fixture)

**Files:**
- Create: `sistema-ayuda-nacional/app/integrations/ushahidi.py`
- Test: `sistema-ayuda-nacional/tests/test_ushahidi.py`

**Interfaces:**
- Consumes: `ai_helper.clasificar_reporte` (Task 4).
- Produces: `ushahidi.obtener_posts_publicados() -> list[dict]`, `ushahidi.existe_en_sistema(db, id_externo) -> bool`, `ushahidi.sincronizar_ushahidi(db) -> list[models.ReporteCiudadano]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ushahidi.py
import httpx
import pytest

from app import ai_helper, models
from app.integrations import ushahidi


@pytest.mark.asyncio
async def test_obtener_posts_usa_fixture_si_no_hay_instancia_configurada(monkeypatch):
    monkeypatch.setattr(ushahidi, "USHAHIDI_BASE_URL", "")
    posts = await ushahidi.obtener_posts_publicados()
    assert posts == ushahidi.POSTS_FIXTURE


@pytest.mark.asyncio
async def test_obtener_posts_llama_instancia_real_si_esta_configurada(monkeypatch):
    monkeypatch.setattr(ushahidi, "USHAHIDI_BASE_URL", "https://mi-instancia.ushahidi.io")

    async def _mock_get(self, url, **kwargs):
        assert url == "https://mi-instancia.ushahidi.io/api/v5/posts"
        return httpx.Response(200, json={"results": [{"id": "post-real-1"}]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)
    posts = await ushahidi.obtener_posts_publicados()
    assert posts == [{"id": "post-real-1"}]


@pytest.mark.asyncio
async def test_sincronizar_ushahidi_crea_reportes_nuevos_y_evita_duplicados(db_session, monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    monkeypatch.setattr(ushahidi, "USHAHIDI_BASE_URL", "")

    nuevos = await ushahidi.sincronizar_ushahidi(db_session)
    assert len(nuevos) == len(ushahidi.POSTS_FIXTURE)
    assert db_session.query(models.ReporteCiudadano).count() == len(ushahidi.POSTS_FIXTURE)

    nuevos_segunda_vez = await ushahidi.sincronizar_ushahidi(db_session)
    assert nuevos_segunda_vez == []
    assert db_session.query(models.ReporteCiudadano).count() == len(ushahidi.POSTS_FIXTURE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_ushahidi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.integrations.ushahidi'`

- [ ] **Step 3: Write app/integrations/ushahidi.py**

```python
"""
Sincronización con Ushahidi Platform — planoidea.md §3.3/§5. Cliente REST
contra la API v5 real (docs.ushahidi.com); si USHAHIDI_BASE_URL no está
configurada, sirve una fixture con la misma forma para desarrollo/demo.
"""
import os

import httpx
from sqlalchemy.orm import Session

from .. import models
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
        db.add(reporte)
        db.commit()
        db.refresh(reporte)
        nuevos.append(reporte)
    return nuevos
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_ushahidi.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add sistema-ayuda-nacional/app/integrations/ushahidi.py sistema-ayuda-nacional/tests/test_ushahidi.py
git commit -m "Nodo Central: sincronización Ushahidi Platform (sandbox con fixture realista)"
```

---

## Task 13: FastAPI app — wire everything together

**Files:**
- Create: `sistema-ayuda-nacional/app/main.py`
- Test: `sistema-ayuda-nacional/tests/test_main.py`

**Interfaces:**
- Consumes: every module from Tasks 2–12.
- Produces: `main.app` (FastAPI instance).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import ai_helper
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # clasificación determinística en tests

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_raiz_responde_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "alcance" in resp.json()


def test_seed_crea_cuatro_centros(client):
    resp = client.get("/api/v1/centros")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_crear_reporte_manual_lo_clasifica(client):
    resp = client.post("/api/v1/reportes", json={
        "contenido": "Necesitamos carpas para dormir, se nos cayó la casa",
        "zona": "Centro",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["categoria"] == "refugio"
    assert data["verificado"] is False


def test_sandbox_whatsapp_simular_crea_reporte(client):
    resp = client.post("/sandbox/whatsapp/simular", json={
        "remitente": "573009998877",
        "texto": "Familia atrapada bajo escombros, muy urgente",
    })
    assert resp.status_code == 200
    assert resp.json()["categoria"] == "rescate_escombros"
    assert resp.json()["urgencia"] == "alta"


def test_webhook_whatsapp_real_shape_sandbox_sin_firma(client):
    payload = {
        "entry": [{"changes": [{"value": {"messages": [{
            "from": "573001112233", "type": "text", "text": {"body": "Sin agua potable"},
        }]}}]}]
    }
    resp = client.post("/api/v1/webhooks/whatsapp", json=payload)
    assert resp.status_code == 200


def test_verificar_reporte_y_ver_necesidades_del_centro(client):
    centros = client.get("/api/v1/centros").json()
    centro_pereira = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    creado = client.post("/api/v1/reportes", json={"contenido": "Sin medicamentos para diabetes"}).json()

    resp = client.post(f"/api/v1/reportes/{creado['id']}/verificar", json={"centro_id": centro_pereira["id"]})
    assert resp.status_code == 200
    assert resp.json()["verificado"] is True

    necesidades = client.get(f"/api/v1/centros/{centro_pereira['id']}/necesidades")
    assert necesidades.status_code == 200
    assert necesidades.json()["total_pendientes"] == 1


def test_login_y_entrega_requiere_token(client):
    centros = client.get("/api/v1/centros").json()
    centro = next(c for c in centros if c["id_territorio"] == "risaralda-pereira")

    creado = client.post("/api/v1/reportes", json={"contenido": "Sin agua potable urgente"}).json()
    client.post(f"/api/v1/reportes/{creado['id']}/verificar", json={"centro_id": centro["id"]})
    solicitud_id = client.get(f"/api/v1/centros/{centro['id']}/necesidades").json()

    login_resp = client.post("/api/v1/auth/token", json={
        "id_territorio": "risaralda-pereira", "secreto": "cambia-esto-en-produccion",
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    sin_token = client.post(f"/api/v1/centros/{centro['id']}/entregas", json={"categoria": "agua"})
    assert sin_token.status_code == 401

    con_token = client.post(
        f"/api/v1/centros/{centro['id']}/entregas",
        json={"categoria": "agua"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert con_token.status_code == 200


def test_sitrep_hxl_responde_csv(client):
    resp = client.get("/api/v1/sitrep.csv?formato=hxl")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


def test_eventos_sismicos_ultimo_sin_eventos_responde_null(client):
    resp = client.get("/api/v1/eventos-sismicos/ultimo")
    assert resp.status_code == 200
    assert resp.json() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sistema-ayuda-nacional && pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write app/main.py**

```python
import asyncio
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from . import auth, models, pipeline, schemas, seed_data
from .ai_helper import clasificar_reporte
from .database import Base, engine, get_db
from .hxl_export import generar_sitrep_hxl
from .integrations import usgs, whatsapp
from .integrations.ushahidi import sincronizar_ushahidi
from .websocket_manager import manager

Base.metadata.create_all(bind=engine)

ALERTA_SEGURIDAD = (
    "Este sistema NO maneja donaciones ni pagos. Para donar dinero, use "
    "únicamente los canales oficiales ya establecidos (Cruz Roja, ABACO, "
    "Bancos de Alimentos, o la llave Bre-B publicada directamente por esas "
    "entidades). Ninguna entidad legítima cobra por registrar a alguien como "
    "voluntario, damnificado o para un subsidio."
)

app = FastAPI(
    title="Sistema de Ayuda Nacional — Nodo Central",
    description="Coordinación de reportes ciudadanos y centros territoriales. Terremoto Colombia, agosto 2026. No maneja pagos.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_tarea_usgs: Optional[asyncio.Task] = None


@app.on_event("startup")
def startup():
    db = next(get_db())
    seed_data.sembrar_datos_iniciales(db)
    global _tarea_usgs
    _tarea_usgs = asyncio.create_task(usgs.escuchar_usgs_loop())


@app.on_event("shutdown")
async def shutdown():
    if _tarea_usgs:
        _tarea_usgs.cancel()


@app.get("/")
def root():
    return {
        "servicio": "Sistema de Ayuda Nacional — Nodo Central",
        "alcance": "Terremoto Colombia, 10 de agosto de 2026 — coordinación nacional",
        "alerta_seguridad": ALERTA_SEGURIDAD,
    }


# ---------------------------------------------------------------------------
# Centros locales
# ---------------------------------------------------------------------------

@app.get("/api/v1/centros", response_model=List[schemas.CentroLocalOut])
def listar_centros(db: Session = Depends(get_db)):
    return db.query(models.CentroLocal).all()


@app.get("/api/v1/centros/{centro_id}/necesidades", response_model=schemas.NecesidadesCentro)
def necesidades_centro(centro_id: int, db: Session = Depends(get_db)):
    centro = db.query(models.CentroLocal).get(centro_id)
    if not centro:
        raise HTTPException(404, "Centro no encontrado")

    pendientes = (
        db.query(models.Solicitud)
        .filter(models.Solicitud.centro_id == centro_id, models.Solicitud.estado == models.EstadoSolicitud.pendiente)
        .all()
    )
    conteo: dict[str, int] = {}
    for s in pendientes:
        conteo[s.categoria.value] = conteo.get(s.categoria.value, 0) + 1

    return schemas.NecesidadesCentro(centro_id=centro_id, pendientes_por_categoria=conteo, total_pendientes=len(pendientes))


@app.post("/api/v1/centros/{centro_id}/entregas", response_model=schemas.SolicitudOut)
def registrar_entrega(
    centro_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    identidad: dict = Depends(auth.requerir_centro_autenticado),
):
    if identidad["centro_id"] != centro_id:
        raise HTTPException(403, "El token no corresponde a este centro")

    solicitud = (
        db.query(models.Solicitud)
        .filter(
            models.Solicitud.centro_id == centro_id,
            models.Solicitud.categoria == payload["categoria"],
            models.Solicitud.estado == models.EstadoSolicitud.pendiente,
        )
        .first()
    )
    if not solicitud:
        raise HTTPException(404, "No hay una solicitud pendiente de esa categoría para este centro")

    solicitud.estado = models.EstadoSolicitud.completada
    db.commit()
    db.refresh(solicitud)
    return solicitud


# ---------------------------------------------------------------------------
# Autenticación de nodos
# ---------------------------------------------------------------------------

@app.post("/api/v1/auth/token", response_model=schemas.TokenOut)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    centro = db.query(models.CentroLocal).filter_by(id_territorio=payload.id_territorio).first()
    if not centro:
        raise HTTPException(401, "Credenciales inválidas")

    credencial = db.query(models.NodoCredencial).filter_by(centro_id=centro.id).first()
    if not credencial or not auth.verificar_secreto(payload.secreto, credencial.secreto_hash):
        raise HTTPException(401, "Credenciales inválidas")

    token = auth.generar_token(centro.id, centro.id_territorio)
    return schemas.TokenOut(access_token=token)


# ---------------------------------------------------------------------------
# Reportes ciudadanos
# ---------------------------------------------------------------------------

@app.post("/api/v1/reportes", response_model=schemas.ReporteCiudadanoOut)
async def crear_reporte_manual(payload: schemas.ReporteCiudadanoCreate, db: Session = Depends(get_db)):
    clasificacion = clasificar_reporte(payload.contenido)
    reporte = models.ReporteCiudadano(
        canal=payload.canal,
        contenido_original=payload.contenido,
        categoria=clasificacion["categoria"],
        urgencia=clasificacion["urgencia"],
        resumen_ia=clasificacion["resumen"],
        clasificado_por_ia=clasificacion["clasificado_por_ia"],
        lat=payload.lat,
        lon=payload.lon,
        zona=payload.zona,
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    await manager.broadcast("nuevo_reporte", schemas.ReporteCiudadanoOut.model_validate(reporte).model_dump())
    return reporte


@app.get("/api/v1/reportes", response_model=List[schemas.ReporteCiudadanoOut])
def listar_reportes(
    verificado: Optional[bool] = None,
    categoria: Optional[models.CategoriaNecesidad] = None,
    canal: Optional[models.CanalReporte] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.ReporteCiudadano)
    if verificado is not None:
        query = query.filter(models.ReporteCiudadano.verificado == verificado)
    if categoria:
        query = query.filter(models.ReporteCiudadano.categoria == categoria)
    if canal:
        query = query.filter(models.ReporteCiudadano.canal == canal)
    return query.order_by(models.ReporteCiudadano.creado_en.desc()).all()


@app.post("/api/v1/reportes/{reporte_id}/verificar", response_model=schemas.ReporteCiudadanoOut)
async def verificar_reporte(reporte_id: int, payload: schemas.ReporteVerificar, db: Session = Depends(get_db)):
    reporte = db.query(models.ReporteCiudadano).get(reporte_id)
    if not reporte:
        raise HTTPException(404, "Reporte no encontrado")

    centro = db.query(models.CentroLocal).get(payload.centro_id)
    if not centro:
        raise HTTPException(404, "Centro no encontrado")

    reporte.verificado = True
    reporte.centro_id = centro.id
    db.commit()
    db.refresh(reporte)

    pipeline.crear_solicitud_desde_reporte(db, reporte)

    await manager.broadcast("reporte_verificado", schemas.ReporteCiudadanoOut.model_validate(reporte).model_dump())
    return reporte


# ---------------------------------------------------------------------------
# Webhooks e integraciones (sandbox salvo USGS)
# ---------------------------------------------------------------------------

@app.post("/api/v1/webhooks/whatsapp")
async def webhook_whatsapp(request: Request, db: Session = Depends(get_db)):
    cuerpo = await request.body()
    firma = request.headers.get("X-Hub-Signature-256")
    if not auth.validar_firma_whatsapp(cuerpo, firma):
        raise HTTPException(401, "Firma de webhook inválida")

    payload = await request.json()
    mensaje = whatsapp.parsear_mensaje_entrante(payload)
    if mensaje is None:
        return {"recibido": True, "procesado": False}

    reporte = whatsapp.construir_reporte_desde_whatsapp(mensaje)
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    await manager.broadcast("nuevo_reporte", schemas.ReporteCiudadanoOut.model_validate(reporte).model_dump())
    return {"recibido": True, "procesado": True, "reporte_id": reporte.id}


@app.post("/sandbox/whatsapp/simular", response_model=schemas.ReporteCiudadanoOut)
async def simular_whatsapp(payload: dict, db: Session = Depends(get_db)):
    """Endpoint de desarrollo: simula un mensaje entrante sin necesitar cuenta Meta real."""
    mensaje = {"remitente": payload["remitente"], "texto": payload["texto"], "ubicacion": payload.get("ubicacion")}
    reporte = whatsapp.construir_reporte_desde_whatsapp(mensaje)
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


@app.post("/api/v1/integraciones/ushahidi/sincronizar", response_model=List[schemas.ReporteCiudadanoOut])
async def sincronizar_ushahidi_endpoint(db: Session = Depends(get_db)):
    return await sincronizar_ushahidi(db)


# ---------------------------------------------------------------------------
# Eventos sísmicos
# ---------------------------------------------------------------------------

@app.get("/api/v1/eventos-sismicos/ultimo", response_model=Optional[schemas.EventoSismicoOut])
def ultimo_evento_sismico(db: Session = Depends(get_db)):
    return (
        db.query(models.EventoSismico)
        .order_by(models.EventoSismico.timestamp.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Interoperabilidad / export
# ---------------------------------------------------------------------------

@app.get("/api/v1/sitrep.csv")
def sitrep_csv(formato: str = "hxl", db: Session = Depends(get_db)):
    if formato != "hxl":
        raise HTTPException(400, "Solo se soporta formato=hxl por ahora")
    return PlainTextResponse(generar_sitrep_hxl(db), media_type="text/csv")


# ---------------------------------------------------------------------------
# Tiempo real
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sistema-ayuda-nacional && pytest tests/test_main.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the full test suite**

Run: `cd sistema-ayuda-nacional && pytest -v`
Expected: all tests across every task pass (≈35 tests)

- [ ] **Step 6: Commit**

```bash
git add sistema-ayuda-nacional/app/main.py sistema-ayuda-nacional/tests/test_main.py
git commit -m "Nodo Central: FastAPI app completa — endpoints, auth, webhooks, export"
```

---

## Task 14: README and manual smoke test

**Files:**
- Create: `sistema-ayuda-nacional/README.md`

- [ ] **Step 1: Write README.md**

Cover: what this is, explicit "no maneja pagos" callout, how each integration is real vs sandbox and exactly which env var flips it to real, how to run locally (`uvicorn app.main:app --reload`), the endpoint table, how to run tests, honest next steps (Nodos Locales offline-first, WMS/WFS real). Follow the tone and structure already established in `pereira-ayuda-backend/README.md`.

- [ ] **Step 2: Manual smoke test**

Run:
```bash
cd sistema-ayuda-nacional
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload &
sleep 2
curl -s localhost:8000/ | python3 -m json.tool
curl -s localhost:8000/api/v1/centros | python3 -m json.tool
curl -s -X POST localhost:8000/sandbox/whatsapp/simular -H "Content-Type: application/json" \
  -d '{"remitente": "573001112233", "texto": "Familia atrapada bajo escombros"}' | python3 -m json.tool
kill %1
```
Expected: root responds with `alerta_seguridad` mentioning no payments; 4 centros returned; sandbox WhatsApp call returns a `rescate_escombros`/`alta` classified report.

- [ ] **Step 3: Commit**

```bash
git add sistema-ayuda-nacional/README.md
git commit -m "Nodo Central: README (qué es real, qué es sandbox, cómo correrlo)"
```

---

## Task 15: Publish as public open-source repository

**Files:**
- Create: `LICENSE` (repo root)
- Create/modify: `README.md` (repo root — overview linking to both `pereira-ayuda-backend/` and `sistema-ayuda-nacional/`)
- Create: `.gitignore` (repo root)

- [ ] **Step 1: Write root .gitignore**

```
__pycache__/
*.pyc
.venv/
*.db
.env
node_modules/
```

- [ ] **Step 2: Write MIT LICENSE with the current year and no tool attribution**

- [ ] **Step 3: Write root README.md**

Short overview: what the project is, the earthquake context (one paragraph, cite that it's a real documented event), links to `planoidea.md` (architecture doc), `pereira-ayuda-backend/` (city-scoped MVP), `sistema-ayuda-nacional/` (national Nodo Central) — each with a one-line description and a link to its own README. Explicit callout: this project does not handle money; state the safety notice from §9 of `planoidea.md` in short form.

- [ ] **Step 4: Commit everything**

```bash
git add LICENSE README.md .gitignore
git commit -m "Publicación: LICENSE MIT, README general, gitignore"
```

- [ ] **Step 5: Create the GitHub repository and push**

Run (repo name to confirm with user before running — see plan notes below):
```bash
gh repo create <nombre-repo> --public --source=. --description "Sistema de coordinación de ayuda humanitaria — terremoto Colombia, agosto 2026" --push
```
Expected: repo created under the authenticated GitHub account, `main` pushed, remote `origin` set.

- [ ] **Step 6: Verify**

Run: `gh repo view --web` (or `gh repo view` for a text summary) to confirm the repo is live and public.
