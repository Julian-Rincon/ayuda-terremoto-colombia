import pytest

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
