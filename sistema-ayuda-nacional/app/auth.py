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
JWT_REFRESCO_EXPIRA_SEGUNDOS = 60 * 60 * 24 * 30  # 30 días

TIPO_ACCESO = "acceso"
TIPO_REFRESCO = "refresco"


def hash_secreto(secreto: str) -> str:
    return bcrypt.hashpw(secreto.encode(), bcrypt.gensalt()).decode()


def verificar_secreto(secreto: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(secreto.encode(), hash_guardado.encode())


def _generar(centro_id: int, id_territorio: str, tipo: str, vida_segundos: int) -> str:
    payload = {
        "centro_id": centro_id,
        "id_territorio": id_territorio,
        "tipo": tipo,
        "exp": int(time.time()) + vida_segundos,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def generar_token(centro_id: int, id_territorio: str) -> str:
    """Token de acceso de vida corta: el que viaja en cada request."""
    return _generar(centro_id, id_territorio, TIPO_ACCESO, JWT_EXPIRA_SEGUNDOS)


def generar_token_refresco(centro_id: int, id_territorio: str) -> str:
    """
    Token de refresco de vida larga. Solo sirve para pedir un token de acceso
    nuevo en /api/v1/auth/refrescar; no autentica ningún otro endpoint.
    """
    return _generar(centro_id, id_territorio, TIPO_REFRESCO, JWT_REFRESCO_EXPIRA_SEGUNDOS)


def decodificar_token(token: str, tipo_esperado: str = TIPO_ACCESO) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o expirado")

    # Los tokens emitidos antes de que existiera el refresco no traen 'tipo';
    # se siguen aceptando como tokens de acceso para no cerrar sesiones vivas.
    tipo = payload.get("tipo", TIPO_ACCESO)
    if tipo != tipo_esperado:
        raise HTTPException(401, "Token del tipo incorrecto para esta operación")
    return payload


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
