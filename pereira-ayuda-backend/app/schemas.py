from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import CategoriaSolicitud, UrgenciaSolicitud, EstadoSolicitud, TipoColectivo


# ---------- Solicitudes ----------

class SolicitudCreate(BaseModel):
    nombre_solicitante: Optional[str] = None
    telefono_contacto: Optional[str] = None
    zona: str = Field(..., description="Barrio o comuna de Pereira, ej. 'Cuba', 'Centro', 'Los Álamos'")
    descripcion: str = Field(..., min_length=5)
    categoria: Optional[CategoriaSolicitud] = None  # si no se envía, la IA la infiere
    lat: Optional[float] = None
    lon: Optional[float] = None
    fuente: str = "web"


class SolicitudOut(BaseModel):
    id: int
    nombre_solicitante: Optional[str]
    telefono_contacto: Optional[str]
    zona: str
    descripcion: str
    categoria: CategoriaSolicitud
    urgencia: UrgenciaSolicitud
    estado: EstadoSolicitud
    resumen_ia: Optional[str]
    clasificado_por_ia: bool
    verificado: bool
    colectivo_id: Optional[int]
    creado_en: datetime

    class Config:
        from_attributes = True


class SolicitudEstadoUpdate(BaseModel):
    estado: EstadoSolicitud


class AsignarColectivo(BaseModel):
    colectivo_id: int


# ---------- Colectivos ----------

class ColectivoCreate(BaseModel):
    nombre: str
    tipo: TipoColectivo = TipoColectivo.general
    descripcion_capacidad: Optional[str] = None
    zona_cobertura: Optional[str] = None
    contacto: Optional[str] = None


class ColectivoOut(BaseModel):
    id: int
    nombre: str
    tipo: TipoColectivo
    descripcion_capacidad: Optional[str]
    zona_cobertura: Optional[str]
    contacto: Optional[str]
    es_oficial: bool
    verificado: bool
    disponible: bool
    creado_en: datetime

    class Config:
        from_attributes = True


class SugerenciaColectivo(BaseModel):
    colectivo: ColectivoOut
    puntaje: float
    razon: str


# ---------- Stats ----------

class StatsOut(BaseModel):
    total_solicitudes: int
    pendientes: int
    asignadas: int
    completadas: int
    colectivos_verificados: int
    colectivos_pendientes_verificacion: int
