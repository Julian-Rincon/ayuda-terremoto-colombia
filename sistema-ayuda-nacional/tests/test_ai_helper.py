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


def test_resumen_sismico_por_reglas_sin_eventos(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    resultado = ai_helper.generar_resumen_sismico([])
    assert "No hay sismos recientes" in resultado["resumen"]
    assert resultado["generado_por_ia"] is False


def test_resumen_sismico_por_reglas_con_eventos(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    eventos = [
        {"magnitud": 4.3, "lugar": "13 km WSW de San José del Palmar", "timestamp": "2026-08-13T14:42:32Z"},
        {"magnitud": 4.2, "lugar": "11 km WNW de San José del Palmar", "timestamp": "2026-08-11T15:43:41Z"},
    ]
    resultado = ai_helper.generar_resumen_sismico(eventos)
    assert "4.3" in resultado["resumen"]
    assert "2 sismos" in resultado["resumen"]
    assert resultado["generado_por_ia"] is False


def test_resumen_sismico_nunca_lanza_excepcion_si_groq_falla(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "llave-invalida")

    def _falla(*args, **kwargs):
        raise ConnectionError("sin red")

    monkeypatch.setattr(ai_helper.requests, "post", _falla)
    resultado = ai_helper.generar_resumen_sismico(
        [{"magnitud": 4.3, "lugar": "Chocó", "timestamp": "2026-08-13T14:42:32Z"}]
    )
    assert resultado["generado_por_ia"] is False
    assert "4.3" in resultado["resumen"]


def test_resumen_necesidades_por_reglas_sin_pendientes(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    resultado = ai_helper.generar_resumen_necesidades("Pereira / Risaralda", {})
    assert "no tiene necesidades pendientes" in resultado["resumen"]
    assert resultado["generado_por_ia"] is False


def test_resumen_necesidades_por_reglas_con_pendientes(monkeypatch):
    monkeypatch.setattr(ai_helper, "GROQ_API_KEY", "")
    resultado = ai_helper.generar_resumen_necesidades("Pereira / Risaralda", {"agua": 3, "alimentos": 2})
    assert "Pereira / Risaralda" in resultado["resumen"]
    assert "3 de agua" in resultado["resumen"]
    assert resultado["generado_por_ia"] is False
