import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.orm import Session

from . import auth, dedup, models, pipeline, schemas, seed_data
from .ai_helper import clasificar_reporte, generar_resumen_necesidades, generar_resumen_sismico
from .config_checks import verificar_secretos_de_produccion
from .database import Base, engine, get_db
from .hxl_export import generar_sitrep_hxl
from .integrations import usgs, whatsapp
from .integrations.ushahidi import sincronizar_ushahidi
from .rate_limit import limiter
from .websocket_manager import manager

verificar_secretos_de_produccion()

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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

    envios_activos = (
        db.query(models.Envio)
        .filter(
            models.Envio.centro_id == centro_id,
            models.Envio.verificado.is_(True),
            models.Envio.estado.in_([models.EstadoEnvio.comprometido, models.EstadoEnvio.en_transito]),
        )
        .all()
    )
    conteo_envios: dict[str, int] = {}
    for e in envios_activos:
        conteo_envios[e.categoria.value] = conteo_envios.get(e.categoria.value, 0) + e.cantidad

    return schemas.NecesidadesCentro(
        centro_id=centro_id,
        pendientes_por_categoria=conteo,
        total_pendientes=len(pendientes),
        envios_verificados_por_categoria=conteo_envios,
    )


@app.get("/api/v1/centros/{centro_id}/necesidades/resumen-ia", response_model=schemas.ResumenNecesidadesIA)
def resumen_necesidades_ia(centro_id: int, db: Session = Depends(get_db)):
    """
    Resumen en lenguaje simple para que un coordinador priorice su día (Groq,
    con fallback por plantilla). Solo reformula los conteos ya calculados —
    nunca inventa solicitudes, personas ni ubicaciones nuevas.
    """
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

    resultado = generar_resumen_necesidades(centro.nombre, conteo)
    return schemas.ResumenNecesidadesIA(
        centro_id=centro_id,
        resumen=resultado["resumen"],
        generado_por_ia=resultado["generado_por_ia"],
    )


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
@limiter.limit("10/minute")
async def crear_reporte_manual(request: Request, payload: schemas.ReporteCiudadanoCreate, db: Session = Depends(get_db)):
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
    dedup.marcar_posible_duplicado(db, reporte)
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
    dedup.marcar_posible_duplicado(db, reporte)
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
    dedup.marcar_posible_duplicado(db, reporte)
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


@app.post("/api/v1/integraciones/ushahidi/sincronizar", response_model=List[schemas.ReporteCiudadanoOut])
async def sincronizar_ushahidi_endpoint(db: Session = Depends(get_db)):
    return await sincronizar_ushahidi(db)


# ---------------------------------------------------------------------------
# Envíos (recursos en especie en camino — NO dinero, ver spec de diseño)
# ---------------------------------------------------------------------------

@app.post("/api/v1/envios", response_model=schemas.EnvioOut)
async def crear_envio(payload: schemas.EnvioCreate, db: Session = Depends(get_db)):
    centro = db.query(models.CentroLocal).get(payload.centro_id)
    if not centro:
        raise HTTPException(404, "Centro no encontrado")

    envio = models.Envio(
        centro_id=payload.centro_id,
        categoria=payload.categoria,
        cantidad=payload.cantidad,
        origen=payload.origen,
        notas=payload.notas,
    )
    db.add(envio)
    db.commit()
    db.refresh(envio)
    await manager.broadcast("nuevo_envio", schemas.EnvioOut.model_validate(envio).model_dump())
    return envio


@app.get("/api/v1/envios", response_model=List[schemas.EnvioOut])
def listar_envios(
    centro_id: Optional[int] = None,
    categoria: Optional[models.CategoriaNecesidad] = None,
    estado: Optional[models.EstadoEnvio] = None,
    verificado: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Envio)
    if centro_id is not None:
        query = query.filter(models.Envio.centro_id == centro_id)
    if categoria:
        query = query.filter(models.Envio.categoria == categoria)
    if estado:
        query = query.filter(models.Envio.estado == estado)
    if verificado is not None:
        query = query.filter(models.Envio.verificado == verificado)
    return query.order_by(models.Envio.creado_en.desc()).all()


@app.patch("/api/v1/envios/{envio_id}/verificar", response_model=schemas.EnvioOut)
async def verificar_envio(envio_id: int, db: Session = Depends(get_db)):
    """
    Gate de confianza: un envío NUNCA cuenta como cobertura de una necesidad
    hasta que un humano coordinador lo confirme explícitamente por acá.
    """
    envio = db.query(models.Envio).get(envio_id)
    if not envio:
        raise HTTPException(404, "Envío no encontrado")
    envio.verificado = True
    db.commit()
    db.refresh(envio)
    await manager.broadcast("envio_verificado", schemas.EnvioOut.model_validate(envio).model_dump())
    return envio


@app.patch("/api/v1/envios/{envio_id}/estado", response_model=schemas.EnvioOut)
async def actualizar_estado_envio(envio_id: int, payload: schemas.EnvioEstadoUpdate, db: Session = Depends(get_db)):
    envio = db.query(models.Envio).get(envio_id)
    if not envio:
        raise HTTPException(404, "Envío no encontrado")
    envio.estado = payload.estado
    db.commit()
    db.refresh(envio)
    await manager.broadcast("envio_actualizado", schemas.EnvioOut.model_validate(envio).model_dump())
    return envio


# ---------------------------------------------------------------------------
# Colectivos y voluntarios ("quien puede darla") — registro público
# ---------------------------------------------------------------------------

@app.post("/api/v1/colectivos", response_model=schemas.ColectivoOut)
@limiter.limit("10/minute")
async def crear_colectivo(request: Request, payload: schemas.ColectivoCreate, db: Session = Depends(get_db)):
    """
    Registro público, sin autenticación: cualquier voluntario o colectivo
    puede anotarse. Nace sin verificar — nunca aparece como disponible ni
    se le puede asignar nada hasta que un humano coordinador lo confirme.
    """
    colectivo = models.Colectivo(**payload.model_dump())
    db.add(colectivo)
    db.commit()
    db.refresh(colectivo)
    await manager.broadcast("nuevo_colectivo", schemas.ColectivoOut.model_validate(colectivo).model_dump())
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
    colectivo = db.query(models.Colectivo).get(colectivo_id)
    if not colectivo:
        raise HTTPException(404, "Colectivo no encontrado")
    colectivo.verificado = True
    db.commit()
    db.refresh(colectivo)
    await manager.broadcast("colectivo_verificado", schemas.ColectivoOut.model_validate(colectivo).model_dump())
    return colectivo


# ---------------------------------------------------------------------------
# Panorama nacional — vista pública agregada, sin login
# ---------------------------------------------------------------------------

@app.get("/api/v1/resumen", response_model=schemas.ResumenNacional)
def resumen_nacional(db: Session = Depends(get_db)):
    solicitudes_pendientes = (
        db.query(models.Solicitud).filter(models.Solicitud.estado == models.EstadoSolicitud.pendiente).all()
    )
    por_categoria: dict[str, int] = {}
    for s in solicitudes_pendientes:
        por_categoria[s.categoria.value] = por_categoria.get(s.categoria.value, 0) + 1

    envios_verificados_en_camino = (
        db.query(models.Envio)
        .filter(
            models.Envio.verificado.is_(True),
            models.Envio.estado.in_([models.EstadoEnvio.comprometido, models.EstadoEnvio.en_transito]),
        )
        .count()
    )

    ultimo_evento = (
        db.query(models.EventoSismico).order_by(models.EventoSismico.timestamp.desc()).first()
    )

    return schemas.ResumenNacional(
        total_centros=db.query(models.CentroLocal).count(),
        total_reportes=db.query(models.ReporteCiudadano).count(),
        reportes_pendientes_verificacion=db.query(models.ReporteCiudadano)
        .filter(models.ReporteCiudadano.verificado.is_(False))
        .count(),
        total_solicitudes_pendientes=len(solicitudes_pendientes),
        solicitudes_pendientes_por_categoria=por_categoria,
        total_colectivos_verificados=db.query(models.Colectivo)
        .filter(models.Colectivo.verificado.is_(True))
        .count(),
        total_colectivos_pendientes_verificacion=db.query(models.Colectivo)
        .filter(models.Colectivo.verificado.is_(False))
        .count(),
        total_envios_verificados_en_camino=envios_verificados_en_camino,
        ultimo_evento_sismico=ultimo_evento,
    )


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


@app.get("/api/v1/eventos-sismicos", response_model=List[schemas.EventoSismicoOut])
def listar_eventos_sismicos(dias: int = 7, db: Session = Depends(get_db)):
    """Historial reciente — no solo el último, para ver la secuencia de réplicas."""
    desde = datetime.utcnow() - timedelta(days=dias)
    return (
        db.query(models.EventoSismico)
        .filter(models.EventoSismico.timestamp >= desde)
        .order_by(models.EventoSismico.timestamp.desc())
        .all()
    )


@app.get("/api/v1/eventos-sismicos/alerta", response_model=schemas.AlertaSismica)
def alerta_sismica(dias: int = 7, db: Session = Depends(get_db)):
    """
    Resumen en lenguaje simple de la actividad sísmica reciente (Groq, con
    fallback por plantilla). Nunca inventa datos de daños o seguridad — solo
    reformula los eventos reales que ya tenemos registrados.
    """
    desde = datetime.utcnow() - timedelta(days=dias)
    eventos = (
        db.query(models.EventoSismico)
        .filter(models.EventoSismico.timestamp >= desde)
        .order_by(models.EventoSismico.timestamp.desc())
        .all()
    )
    datos = [{"magnitud": e.magnitud, "lugar": e.lugar or "ubicación sin especificar", "timestamp": e.timestamp.isoformat()} for e in eventos]
    resultado = generar_resumen_sismico(datos)
    return schemas.AlertaSismica(
        resumen=resultado["resumen"],
        generado_por_ia=resultado["generado_por_ia"],
        eventos=eventos,
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
