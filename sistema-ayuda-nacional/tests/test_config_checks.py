import pytest

from app import config_checks
from app.config_checks import verificar_secretos_de_produccion


def test_no_revisa_nada_en_desarrollo(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    verificar_secretos_de_produccion()  # no debe lanzar nada


def test_lanza_si_produccion_y_secretos_por_defecto(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("NODOS_SECRETO_INICIAL", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        verificar_secretos_de_produccion()


def test_no_lanza_si_produccion_y_secretos_rotados(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "un-secreto-real-generado-para-produccion")
    monkeypatch.setenv("NODOS_SECRETO_INICIAL", "otro-secreto-real-por-nodo")

    verificar_secretos_de_produccion()  # no debe lanzar nada


def test_verify_token_sin_app_secret_advierte(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "algo")
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)

    advertencias = config_checks.advertir_configuracion_parcial_whatsapp()

    assert len(advertencias) == 1
    assert "WHATSAPP_APP_SECRET" in advertencias[0]


def test_app_secret_sin_verify_token_advierte(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "algo")
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)

    advertencias = config_checks.advertir_configuracion_parcial_whatsapp()

    assert len(advertencias) == 1
    assert "no se podrá conectar el número" in advertencias[0]


def test_credenciales_de_salida_a_medias_advierten(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "a")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "b")
    monkeypatch.setenv("WHATSAPP_TOKEN", "c")
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)

    advertencias = config_checks.advertir_configuracion_parcial_whatsapp()

    assert len(advertencias) == 1
    assert "WHATSAPP_PHONE_NUMBER_ID" in advertencias[0]


def test_whatsapp_apagado_del_todo_no_advierte_nada(monkeypatch):
    """El canal es opcional: no tenerlo configurado es una decisión válida,
    no un error que haya que repetir en cada arranque."""
    for var in ("WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"):
        monkeypatch.delenv(var, raising=False)

    assert config_checks.advertir_configuracion_parcial_whatsapp() == []
