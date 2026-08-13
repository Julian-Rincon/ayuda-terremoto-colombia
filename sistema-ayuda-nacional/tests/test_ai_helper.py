from app import ai_helper


def test_clasificar_por_reglas_detecta_rescate_urgente(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")  # forzar fallback por reglas
    resultado = ai_helper.clasificar_reporte("Hay dos personas atrapadas bajo escombros, urgente")
    assert resultado["categoria"] == "rescate_escombros"
    assert resultado["urgencia"] == "alta"
    assert resultado["clasificado_por_ia"] is False


def test_clasificar_por_reglas_categoria_agua(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    resultado = ai_helper.clasificar_reporte("Llevamos tres días sin agua potable")
    assert resultado["categoria"] == "agua"


def test_clasificar_nunca_lanza_excepcion_si_groq_falla(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "llave-invalida")

    def _falla(*args, **kwargs):
        raise ConnectionError("sin red")

    monkeypatch.setattr(ai_helper.requests, "post", _falla)
    resultado = ai_helper.clasificar_reporte("Necesitamos carpas para dormir")
    assert resultado["categoria"] in ai_helper.CATEGORIAS_VALIDAS
    assert resultado["clasificado_por_ia"] is False
