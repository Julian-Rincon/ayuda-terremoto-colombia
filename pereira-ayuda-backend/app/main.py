"""
Backend del prototipo — Pereira, respuesta al terremoto del 10 de agosto de 2026.

Conecta solicitudes de ayuda ciudadanas con colectivos (desarrollo, diseño,
logística, salud, rescate, canales oficiales) verificados, con:
  - Clasificación asistida por IA gratuita (Groq/Llama, con fallback por reglas)
  - Actualizaciones en tiempo real por WebSocket
  - Verificación humana obligatoria antes de listar un colectivo o asignar recursos

Levantar:
    uvicorn app.main:app --reload
"""
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, ai_helper
from .database import engine, get_db, Base
from .websocket_manager import manager
from .seed_data import sembrar_datos_iniciales, ALERTA_SEGURIDAD

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Pereira Ayuda — Backend del prototipo",
    description="Conecta solicitudes de ayuda con colectivos verificados. Terremoto Colombia, agosto 2026.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustar a dominios reales antes de producción
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db = next(get_db())
    sembrar_datos_iniciales(db)


# ---------------------------------------------------------------------------
# Salud / info general
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "servicio": "Pereira Ayuda — backend del prototipo",
        "alcance": "Terremoto Colombia, 10 de agosto de 2026 — foco Pereira",
        "alerta_seguridad": ALERTA_SEGURIDAD,
    }


@app.get("/canales-oficiales", response_model=List[schemas.ColectivoOut])
def canales_oficiales(db: Session = Depends(get_db)):
    """Canales verificados (Alcaldía, Cruz Roja, Hospital) — punto de partida confiable."""
    return db.query(models.Colectivo).filter(models.Colectivo.es_oficial == True).all()  # noqa: E712


# ---------------------------------------------------------------------------
# Solicitudes
# ---------------------------------------------------------------------------

@app.post("/api/v1/solicitudes", response_model=schemas.SolicitudOut)
async def crear_solicitud(payload: schemas.SolicitudCreate, db: Session = Depends(get_db)):
    clasificacion = None
    if payload.categoria is None:
        clasificacion = ai_helper.clasificar_solicitud(payload.descripcion, payload.zona)

    solicitud = models.Solicitud(
        nombre_solicitante=payload.nombre_solicitante,
        telefono_contacto=payload.telefono_contacto,
        zona=payload.zona,
        descripcion=payload.descripcion,
        categoria=payload.categoria or clasificacion["categoria"],
        urgencia=(clasificacion["urgencia"] if clasificacion else models.UrgenciaSolicitud.sin_clasificar),
        resumen_ia=clasificacion["resumen"] if clasificacion else None,
        clasificado_por_ia=clasificacion is not None,
        lat=payload.lat,
        lon=payload.lon,
        fuente=payload.fuente,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    await manager.broadcast("nueva_solicitud", schemas.SolicitudOut.model_validate(solicitud).model_dump())
    return solicitud


@app.get("/api/v1/solicitudes", response_model=List[schemas.SolicitudOut])
def listar_solicitudes(
    estado: Optional[models.EstadoSolicitud] = None,
    categoria: Optional[models.CategoriaSolicitud] = None,
    zona: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Solicitud)
    if estado:
        query = query.filter(models.Solicitud.estado == estado)
    if categoria:
        query = query.filter(models.Solicitud.categoria == categoria)
    if zona:
        query = query.filter(models.Solicitud.zona.ilike(f"%{zona}%"))
    return query.order_by(models.Solicitud.creado_en.desc()).all()


@app.get("/api/v1/solicitudes/{solicitud_id}", response_model=schemas.SolicitudOut)
def obtener_solicitud(solicitud_id: int, db: Session = Depends(get_db)):
    solicitud = db.query(models.Solicitud).get(solicitud_id)
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")
    return solicitud


@app.get("/api/v1/solicitudes/{solicitud_id}/sugerencias", response_model=List[schemas.SugerenciaColectivo])
def sugerir_para_solicitud(solicitud_id: int, db: Session = Depends(get_db)):
    solicitud = db.query(models.Solicitud).get(solicitud_id)
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")

    colectivos = db.query(models.Colectivo).all()
    sugerencias = ai_helper.sugerir_colectivos(solicitud.categoria.value, solicitud.zona, colectivos)
    return [
        schemas.SugerenciaColectivo(
            colectivo=schemas.ColectivoOut.model_validate(s["colectivo"]),
            puntaje=s["puntaje"],
            razon=s["razon"],
        )
        for s in sugerencias
    ]


@app.patch("/api/v1/solicitudes/{solicitud_id}/estado", response_model=schemas.SolicitudOut)
async def actualizar_estado(solicitud_id: int, payload: schemas.SolicitudEstadoUpdate, db: Session = Depends(get_db)):
    solicitud = db.query(models.Solicitud).get(solicitud_id)
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")
    solicitud.estado = payload.estado
    db.commit()
    db.refresh(solicitud)
    await manager.broadcast("actualizacion_solicitud", schemas.SolicitudOut.model_validate(solicitud).model_dump())
    return solicitud


@app.post("/api/v1/solicitudes/{solicitud_id}/asignar", response_model=schemas.SolicitudOut)
async def asignar_colectivo(solicitud_id: int, payload: schemas.AsignarColectivo, db: Session = Depends(get_db)):
    solicitud = db.query(models.Solicitud).get(solicitud_id)
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")

    colectivo = db.query(models.Colectivo).get(payload.colectivo_id)
    if not colectivo:
        raise HTTPException(404, "Colectivo no encontrado")
    if not colectivo.verificado:
        raise HTTPException(400, "No se puede asignar a un colectivo sin verificar")

    solicitud.colectivo_id = colectivo.id
    solicitud.estado = models.EstadoSolicitud.asignada
    db.commit()
    db.refresh(solicitud)

    await manager.broadcast("asignacion", schemas.SolicitudOut.model_validate(solicitud).model_dump())
    return solicitud


# ---------------------------------------------------------------------------
# Colectivos
# ---------------------------------------------------------------------------

@app.post("/api/v1/colectivos", response_model=schemas.ColectivoOut)
async def registrar_colectivo(payload: schemas.ColectivoCreate, db: Session = Depends(get_db)):
    colectivo = models.Colectivo(**payload.model_dump(), verificado=False, es_oficial=False)
    db.add(colectivo)
    db.commit()
    db.refresh(colectivo)
    await manager.broadcast("nuevo_colectivo_pendiente", schemas.ColectivoOut.model_validate(colectivo).model_dump())
    return colectivo


@app.get("/api/v1/colectivos", response_model=List[schemas.ColectivoOut])
def listar_colectivos(
    verificado: Optional[bool] = None,
    tipo: Optional[models.TipoColectivo] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Colectivo)
    if verificado is not None:
        query = query.filter(models.Colectivo.verificado == verificado)
    if tipo:
        query = query.filter(models.Colectivo.tipo == tipo)
    return query.order_by(models.Colectivo.creado_en.desc()).all()


@app.patch("/api/v1/colectivos/{colectivo_id}/verificar", response_model=schemas.ColectivoOut)
async def verificar_colectivo(colectivo_id: int, db: Session = Depends(get_db)):
    """
    Gate de confianza: un colectivo NUNCA es sugerible ni asignable hasta que
    un humano coordinador lo apruebe explícitamente por acá.
    """
    colectivo = db.query(models.Colectivo).get(colectivo_id)
    if not colectivo:
        raise HTTPException(404, "Colectivo no encontrado")
    colectivo.verificado = True
    db.commit()
    db.refresh(colectivo)
    await manager.broadcast("colectivo_verificado", schemas.ColectivoOut.model_validate(colectivo).model_dump())
    return colectivo


@app.patch("/api/v1/colectivos/{colectivo_id}/disponibilidad", response_model=schemas.ColectivoOut)
def actualizar_disponibilidad(colectivo_id: int, disponible: bool, db: Session = Depends(get_db)):
    colectivo = db.query(models.Colectivo).get(colectivo_id)
    if not colectivo:
        raise HTTPException(404, "Colectivo no encontrado")
    colectivo.disponible = disponible
    db.commit()
    db.refresh(colectivo)
    return colectivo


# ---------------------------------------------------------------------------
# Stats + tiempo real
# ---------------------------------------------------------------------------

@app.get("/api/v1/stats", response_model=schemas.StatsOut)
def stats(db: Session = Depends(get_db)):
    total = db.query(models.Solicitud).count()
    pendientes = db.query(models.Solicitud).filter(
        models.Solicitud.estado == models.EstadoSolicitud.pendiente
    ).count()
    asignadas = db.query(models.Solicitud).filter(
        models.Solicitud.estado.in_([models.EstadoSolicitud.asignada, models.EstadoSolicitud.en_proceso])
    ).count()
    completadas = db.query(models.Solicitud).filter(
        models.Solicitud.estado == models.EstadoSolicitud.completada
    ).count()
    colectivos_verificados = db.query(models.Colectivo).filter(models.Colectivo.verificado == True).count()  # noqa: E712
    colectivos_pendientes = db.query(models.Colectivo).filter(models.Colectivo.verificado == False).count()  # noqa: E712

    return schemas.StatsOut(
        total_solicitudes=total,
        pendientes=pendientes,
        asignadas=asignadas,
        completadas=completadas,
        colectivos_verificados=colectivos_verificados,
        colectivos_pendientes_verificacion=colectivos_pendientes,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Conectar un dashboard o mapa en vivo acá para recibir eventos en tiempo real."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # no esperamos mensajes del cliente, solo mantener viva la conexión
    except WebSocketDisconnect:
        manager.disconnect(websocket)
