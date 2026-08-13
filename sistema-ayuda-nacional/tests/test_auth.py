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
