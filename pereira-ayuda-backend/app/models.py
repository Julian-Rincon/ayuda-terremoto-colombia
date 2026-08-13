"""
Modelos de base de datos.
Diseñado para arrancar en SQLite (cero configuración) y migrar a Postgres
solo cambiando DATABASE_URL — mismo patrón que ya usas en Chinook/ShopStream.
"""
from datetime import datetime
import enum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
)
from sqlalchemy.orm import relationship

from .database import Base


class CategoriaSolicitud(str, enum.Enum):
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


class UrgenciaSolicitud(str, enum.Enum):
    alta = "alta"
    media = "media"
    baja = "baja"
    sin_clasificar = "sin_clasificar"


class EstadoSolicitud(str, enum.Enum):
    pendiente = "pendiente"
    verificando = "verificando"
    asignada = "asignada"
    en_proceso = "en_proceso"
    completada = "completada"
    descartada = "descartada"


class TipoColectivo(str, enum.Enum):
    desarrollo = "desarrollo"
    diseno = "diseno"
    logistica = "logistica"
    salud = "salud"
    alimentos = "alimentos"
    rescate = "rescate"
    construccion = "construccion"
    oficial_verificado = "oficial_verificado"  # Alcaldía, Cruz Roja, Hospital, etc.
    general = "general"


class Solicitud(Base):
    __tablename__ = "solicitudes"

    id = Column(Integer, primary_key=True, index=True)
    nombre_solicitante = Column(String(200), nullable=True)
    telefono_contacto = Column(String(30), nullable=True)
    zona = Column(String(120), nullable=False, index=True)  # barrio / comuna de Pereira
    descripcion = Column(Text, nullable=False)

    categoria = Column(Enum(CategoriaSolicitud), default=CategoriaSolicitud.otro, index=True)
    urgencia = Column(Enum(UrgenciaSolicitud), default=UrgenciaSolicitud.sin_clasificar, index=True)
    estado = Column(Enum(EstadoSolicitud), default=EstadoSolicitud.pendiente, index=True)

    resumen_ia = Column(Text, nullable=True)  # resumen generado por el clasificador IA
    clasificado_por_ia = Column(Boolean, default=False)

    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    fuente = Column(String(30), default="web")  # web, whatsapp, manual
    verificado = Column(Boolean, default=False)  # confirmación humana antes de asignar

    colectivo_id = Column(Integer, ForeignKey("colectivos.id"), nullable=True)
    colectivo = relationship("Colectivo", back_populates="solicitudes")

    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Colectivo(Base):
    __tablename__ = "colectivos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    tipo = Column(Enum(TipoColectivo), default=TipoColectivo.general, index=True)
    descripcion_capacidad = Column(Text, nullable=True)  # qué puede ofrecer / capacidad real
    zona_cobertura = Column(String(300), nullable=True)  # barrios/comunas que cubre

    contacto = Column(String(200), nullable=True)  # teléfono, WhatsApp, email

    es_oficial = Column(Boolean, default=False)  # Alcaldía, Cruz Roja, Hospital, etc.
    verificado = Column(Boolean, default=False)  # SIEMPRE False hasta que un humano lo apruebe
    disponible = Column(Boolean, default=True)

    creado_en = Column(DateTime, default=datetime.utcnow)

    solicitudes = relationship("Solicitud", back_populates="colectivo")
