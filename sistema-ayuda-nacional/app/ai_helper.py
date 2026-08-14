"""
Clasificación de reportes ciudadanos — gratuita por defecto.

Usa Groq (https://console.groq.com) si hay GROQ_API_KEY configurada. Si no,
o si la llamada falla por cualquier razón, cae a un clasificador por
palabras clave que nunca falla y no depende de internet.
"""
import json
import os
from typing import Optional

import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

CATEGORIAS_VALIDAS = [
    "alimentos", "agua", "refugio", "salud", "medicamentos",
    "aseo", "ropa", "rescate_escombros", "mascotas", "reconstruccion", "otro",
]

_PALABRAS_CLAVE = {
    "rescate_escombros": ["atrapad", "escombro", "colapsó", "colapso", "derrumb", "sepultad"],
    "salud": ["herid", "sangre", "médic", "medico", "hospital", "fractura"],
    "medicamentos": ["medicamento", "insulina", "pastilla", "tratamiento"],
    "agua": ["agua potable", "sed", "sin agua"],
    "alimentos": ["comida", "alimento", "hambre", "leche", "víveres", "viveres"],
    "refugio": ["carpa", "colchoneta", "dormir", "sin techo", "alberg"],
    "aseo": ["jabón", "jabon", "pañal", "panal", "aseo"],
    "ropa": ["ropa", "cobija", "manta", "abrigo"],
    "mascotas": ["perro", "gato", "mascota"],
    "reconstruccion": ["reconstruir", "reparar vivienda", "material de construcción"],
}

_URGENCIA_ALTA = ["atrapad", "sepultad", "sangrando", "no respira", "urgente", "muriendo"]


def _clasificar_por_reglas(descripcion: str) -> dict:
    texto = descripcion.lower()
    categoria = "otro"
    for cat, palabras in _PALABRAS_CLAVE.items():
        if any(p in texto for p in palabras):
            categoria = cat
            break
    urgencia = "alta" if any(p in texto for p in _URGENCIA_ALTA) else "media"
    return {
        "categoria": categoria,
        "urgencia": urgencia,
        "resumen": descripcion[:180],
        "clasificado_por_ia": False,
    }


def _clasificar_con_groq(descripcion: str) -> Optional[dict]:
    if not GROQ_API_KEY:
        return None

    prompt = (
        "Eres un asistente de triage para ayuda humanitaria tras el terremoto en "
        "Colombia (10 ago 2026). Clasifica este reporte ciudadano. Responde SOLO "
        "con JSON válido, sin texto adicional, con este formato exacto:\n"
        f'{{"categoria": "<una de: {", ".join(CATEGORIAS_VALIDAS)}>", '
        '"urgencia": "<alta|media|baja>", "resumen": "<máximo 25 palabras>"}\n\n'
        f'Reporte: "{descripcion}"'
    )
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 200,
            },
            timeout=10,
        )
        resp.raise_for_status()
        contenido = resp.json()["choices"][0]["message"]["content"].strip()
        contenido = contenido.replace("```json", "").replace("```", "").strip()
        data = json.loads(contenido)

        if data.get("categoria") not in CATEGORIAS_VALIDAS:
            data["categoria"] = "otro"
        if data.get("urgencia") not in ("alta", "media", "baja"):
            data["urgencia"] = "media"
        data["clasificado_por_ia"] = True
        return data
    except Exception:
        return None


def clasificar_reporte(descripcion: str) -> dict:
    resultado = _clasificar_con_groq(descripcion)
    if resultado is None:
        resultado = _clasificar_por_reglas(descripcion)
    return resultado


# ---------------------------------------------------------------------------
# Resumen de actividad sísmica en lenguaje simple
#
# Reformula HECHOS que ya tenemos (magnitud, lugar, fecha) — nunca inventa
# datos de daños, víctimas ni instrucciones de seguridad. Eso sigue siendo
# responsabilidad de las fuentes oficiales (SGC, Cruz Roja).
# ---------------------------------------------------------------------------

def _resumen_sismico_por_reglas(eventos: list[dict]) -> str:
    if not eventos:
        return "No hay sismos recientes registrados en la zona."
    reciente = eventos[0]
    extra = f" Van {len(eventos)} sismos detectados en los últimos días." if len(eventos) > 1 else ""
    return f"Sismo de magnitud {reciente['magnitud']} cerca de {reciente['lugar']}.{extra}"


def _resumen_sismico_con_groq(eventos: list[dict]) -> Optional[str]:
    if not GROQ_API_KEY or not eventos:
        return None

    lista = "\n".join(f"- Magnitud {e['magnitud']}, {e['lugar']}, {e['timestamp']}" for e in eventos)
    prompt = (
        "Eres un generador de alertas informativas para un sistema de ayuda humanitaria "
        "en Colombia, tras el terremoto de agosto 2026. Se te dan datos reales de sismos "
        "detectados recientemente. Tu única tarea es resumirlos en español sencillo, en "
        "máximo 40 palabras, para que cualquier persona los entienda.\n\n"
        "REGLAS ESTRICTAS — nunca las rompas:\n"
        "- Usa SOLO los datos que se te dan (magnitud, lugar, fecha).\n"
        "- NUNCA inventes ni menciones daños, víctimas, heridos, ni si es seguro o no.\n"
        "- NUNCA des instrucciones de seguridad ni recomendaciones de qué hacer.\n"
        "- Responde SOLO el texto del resumen, sin comillas ni explicaciones.\n\n"
        f"Datos:\n{lista}"
    )
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 150,
            },
            timeout=10,
        )
        resp.raise_for_status()
        texto = resp.json()["choices"][0]["message"]["content"].strip()
        return texto or None
    except Exception:
        return None


def generar_resumen_sismico(eventos: list[dict]) -> dict:
    """`eventos`: lista de {"magnitud", "lugar", "timestamp"}, más reciente primero."""
    resumen = _resumen_sismico_con_groq(eventos)
    if resumen is not None:
        return {"resumen": resumen, "generado_por_ia": True}
    return {"resumen": _resumen_sismico_por_reglas(eventos), "generado_por_ia": False}


# ---------------------------------------------------------------------------
# Resumen de necesidades pendientes para un coordinador
#
# Igual que arriba: solo reformula los conteos que ya calculó el pipeline,
# nunca inventa solicitudes, personas ni ubicaciones nuevas.
# ---------------------------------------------------------------------------

def _resumen_necesidades_por_reglas(centro_nombre: str, pendientes_por_categoria: dict) -> str:
    if not pendientes_por_categoria:
        return f"{centro_nombre} no tiene necesidades pendientes registradas ahora mismo."
    partes = ", ".join(f"{cantidad} de {categoria}" for categoria, cantidad in pendientes_por_categoria.items())
    return f"{centro_nombre} tiene necesidades pendientes: {partes}."


def _resumen_necesidades_con_groq(centro_nombre: str, pendientes_por_categoria: dict) -> Optional[str]:
    if not GROQ_API_KEY or not pendientes_por_categoria:
        return None

    lista = ", ".join(f"{cantidad} solicitudes de {categoria}" for categoria, cantidad in pendientes_por_categoria.items())
    prompt = (
        "Eres un asistente que ayuda a un coordinador de ayuda humanitaria en Colombia a "
        f"priorizar su día en el centro '{centro_nombre}'. Se te da el conteo de "
        "solicitudes pendientes por categoría. Escribe un resumen breve (máximo 35 "
        "palabras) en español sencillo que le ayude a decidir qué atender primero.\n\n"
        "REGLAS ESTRICTAS — nunca las rompas:\n"
        "- Usa SOLO los números que se te dan.\n"
        "- NUNCA inventes solicitudes, nombres de personas, ni ubicaciones que no se dieron.\n"
        "- Responde SOLO el texto del resumen, sin comillas ni explicaciones.\n\n"
        f"Datos: {lista}"
    )
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 150,
            },
            timeout=10,
        )
        resp.raise_for_status()
        texto = resp.json()["choices"][0]["message"]["content"].strip()
        return texto or None
    except Exception:
        return None


def generar_resumen_necesidades(centro_nombre: str, pendientes_por_categoria: dict) -> dict:
    resumen = _resumen_necesidades_con_groq(centro_nombre, pendientes_por_categoria)
    if resumen is not None:
        return {"resumen": resumen, "generado_por_ia": True}
    return {"resumen": _resumen_necesidades_por_reglas(centro_nombre, pendientes_por_categoria), "generado_por_ia": False}
