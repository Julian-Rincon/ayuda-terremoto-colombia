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
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
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


def test_token_de_refresco_no_sirve_como_token_de_acceso():
    """El refresco solo abre /auth/refrescar; si alguien lo manda en el header
    Authorization de un endpoint protegido debe rebotar con 401."""
    refresco = auth.generar_token_refresco(centro_id=1, id_territorio="risaralda-pereira")
    with pytest.raises(HTTPException) as exc_info:
        auth.requerir_centro_autenticado(authorization=f"Bearer {refresco}")
    assert exc_info.value.status_code == 401


def test_token_de_acceso_no_sirve_para_refrescar():
    acceso = auth.generar_token(centro_id=1, id_territorio="risaralda-pereira")
    with pytest.raises(HTTPException) as exc_info:
        auth.decodificar_token(acceso, tipo_esperado=auth.TIPO_REFRESCO)
    assert exc_info.value.status_code == 401


def test_token_de_refresco_vive_mas_que_el_de_acceso():
    datos_acceso = auth.decodificar_token(auth.generar_token(1, "risaralda-pereira"))
    datos_refresco = auth.decodificar_token(
        auth.generar_token_refresco(1, "risaralda-pereira"), tipo_esperado=auth.TIPO_REFRESCO
    )
    assert datos_refresco["exp"] > datos_acceso["exp"]


def test_token_viejo_sin_claim_tipo_se_sigue_aceptando_como_acceso():
    """Sesiones emitidas antes del refresco no traen 'tipo' y no deben cerrarse
    al desplegar esta versión."""
    import jwt as pyjwt
    token_viejo = pyjwt.encode(
        {"centro_id": 1, "id_territorio": "risaralda-pereira", "exp": 4102444800},
        auth.JWT_SECRET,
        algorithm=auth.JWT_ALGORITHM,
    )
    assert auth.decodificar_token(token_viejo)["centro_id"] == 1
