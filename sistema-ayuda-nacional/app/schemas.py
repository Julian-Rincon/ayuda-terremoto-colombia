from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .models import CanalReporte, CategoriaNecesidad, EstadoEnvio, EstadoSolicitud, TipoColectivo, UrgenciaReporte


class CentroLocalOut(BaseModel):
    id: int
    id_territorio: str
    nombre: str
    departamento: str
    contacto: Optional[str]
    contacto_verificado: bool
    activo: bool
    lat: Optional[float]
    lon: Optional[float]

    class Config:
        from_attributes = True


class ReporteCiudadanoCreate(BaseModel):
    contenido: str = Field(..., min_length=3)
    zona: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    canal: CanalReporte = CanalReporte.manual


class ReporteCiudadanoOut(BaseModel):
    """
    Forma pública de un reporte. `GET /api/v1/reportes` no pide autenticación
    a propósito (la cola de verificación tiene que ser auditable por
    cualquiera), así que todo lo que salga por acá es público.
    """

    id: int
    # Para Ushahidi es el id del post, que ya es público. Para WhatsApp es el
    # número de quien escribió: eso NUNCA sale (ver _ocultar_remitente abajo).
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
    posible_duplicado_de_id: Optional[int]
    creado_en: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def _ocultar_remitente(self):
        """
        El número de teléfono de quien pidió ayuda por WhatsApp se guarda para
        poder rastrear el reporte hasta su origen, pero no puede salir por una
        API pública: sería una lista de personas vulnerables y cómo
        contactarlas, justo durante la emergencia en que circulan estafas
        suplantando a las organizaciones de ayuda.
        """
        if self.canal == CanalReporte.whatsapp:
            self.id_externo = None
        return self


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
    envios_verificados_por_categoria: dict[str, int]


class EnvioCreate(BaseModel):
    centro_id: int
    categoria: CategoriaNecesidad
    cantidad: int = Field(..., gt=0)
    origen: str = Field(..., min_length=2)
    notas: Optional[str] = None


class EnvioOut(BaseModel):
    id: int
    centro_id: int
    categoria: CategoriaNecesidad
    cantidad: int
    origen: str
    notas: Optional[str]
    estado: EstadoEnvio
    verificado: bool
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        from_attributes = True


class EnvioEstadoUpdate(BaseModel):
    estado: EstadoEnvio


class ColectivoCreate(BaseModel):
    nombre: str = Field(..., min_length=2)
    tipo: TipoColectivo = TipoColectivo.general
    descripcion: Optional[str] = None
    zona_cobertura: Optional[str] = None
    contacto: Optional[str] = None


class ColectivoOut(BaseModel):
    id: int
    nombre: str
    tipo: TipoColectivo
    descripcion: Optional[str]
    zona_cobertura: Optional[str]
    contacto: Optional[str]
    verificado: bool
    creado_en: datetime

    class Config:
        from_attributes = True


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


class AlertaSismica(BaseModel):
    resumen: str
    generado_por_ia: bool
    eventos: list[EventoSismicoOut]


class ResumenNecesidadesIA(BaseModel):
    centro_id: int
    resumen: str
    generado_por_ia: bool


class ResumenNacional(BaseModel):
    total_centros: int
    total_centros_registrados: int
    total_reportes: int
    reportes_pendientes_verificacion: int
    total_solicitudes_pendientes: int
    solicitudes_pendientes_por_categoria: dict[str, int]
    total_colectivos_verificados: int
    total_colectivos_pendientes_verificacion: int
    total_envios_verificados_en_camino: int
    ultimo_evento_sismico: Optional[EventoSismicoOut]


class LoginRequest(BaseModel):
    id_territorio: str
    secreto: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefrescoRequest(BaseModel):
    refresh_token: str


class EstadoSalud(BaseModel):
    estado: str
    base_de_datos: str
    version: str
    segundos_activo: int
