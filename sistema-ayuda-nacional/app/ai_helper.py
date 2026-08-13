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
