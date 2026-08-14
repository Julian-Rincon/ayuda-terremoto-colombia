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


class EstadoEnvio(str, enum.Enum):
    comprometido = "comprometido"  # alguien se comprometió a mandarlo, aún no salió
    en_transito = "en_transito"  # ya salió, viene en camino
    entregado = "entregado"  # ya llegó al centro
    cancelado = "cancelado"


class TipoColectivo(str, enum.Enum):
    voluntariado = "voluntariado"
    logistica = "logistica"
    salud = "salud"
    alimentos = "alimentos"
    refugio = "refugio"
    rescate = "rescate"
    construccion = "construccion"
    general = "general"


class CentroLocal(Base):
    __tablename__ = "centros_locales"

    id = Column(Integer, primary_key=True, index=True)
    id_territorio = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    departamento = Column(String(100), nullable=False, index=True)
    contacto = Column(String(200), nullable=True)
    contacto_verificado = Column(Boolean, default=False)
    activo = Column(Boolean, default=True)

    # Coordenadas de referencia del nodo (capital departamental) — para el
    # mapa nacional. No representan un punto exacto de atención, son la
    # ubicación aproximada de la zona que coordina este centro.
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

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

    # Detección de duplicados entre canales (dedup.py) — nunca se fusiona ni
    # descarta automáticamente, solo se deja marcado para revisión humana.
    posible_duplicado_de_id = Column(Integer, ForeignKey("reportes_ciudadanos.id"), nullable=True)

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


class Envio(Base):
    """
    Recursos en especie (comida, medicamentos, etc.) que alguien se
    compromete a mandar hacia un CentroLocal — NUNCA dinero (eso queda
    fuera de este sistema, ver spec de diseño). `cantidad` es un conteo de
    unidades/kits, no un monto.

    `verificado` sigue el mismo patrón que ReporteCiudadano: por defecto
    False, para que nadie pueda inflar falsamente "esto ya viene cubierto"
    y bajarle prioridad a una necesidad real sin que un humano lo confirme.
    """
    __tablename__ = "envios"

    id = Column(Integer, primary_key=True, index=True)

    centro_id = Column(Integer, ForeignKey("centros_locales.id"), nullable=False)
    centro = relationship("CentroLocal")

    categoria = Column(Enum(CategoriaNecesidad), nullable=False, index=True)
    cantidad = Column(Integer, nullable=False)
    origen = Column(String(200), nullable=False)  # ej. "Bogotá", "Cruz Roja Nacional"
    notas = Column(Text, nullable=True)

    estado = Column(Enum(EstadoEnvio), default=EstadoEnvio.comprometido, index=True)
    verificado = Column(Boolean, default=False)

    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Colectivo(Base):
    """
    Voluntario u organización que se ofrece a ayudar — el lado de "quien
    puede darla" en "conectar a quien necesita con quien puede darla".
    Registro público, abierto a cualquiera; NUNCA aparece disponible ni se
    le puede asignar nada hasta que un humano coordinador lo verifique
    (mismo gate que reportes y envíos — evita que alguien se haga pasar por
    ayuda legítima).
    """
    __tablename__ = "colectivos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    tipo = Column(Enum(TipoColectivo), default=TipoColectivo.general, index=True)
    descripcion = Column(Text, nullable=True)
    zona_cobertura = Column(String(300), nullable=True)
    contacto = Column(String(200), nullable=True)

    verificado = Column(Boolean, default=False)

    creado_en = Column(DateTime, default=datetime.utcnow)


class NodoCredencial(Base):
    __tablename__ = "nodo_credenciales"

    id = Column(Integer, primary_key=True, index=True)
    centro_id = Column(Integer, ForeignKey("centros_locales.id"), nullable=False, unique=True)
    centro = relationship("CentroLocal")
    secreto_hash = Column(String(200), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)
