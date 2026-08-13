"""
Capa de IA para gestión — pensada para ser GRATUITA por defecto.

Usa la API de Groq (https://console.groq.com) si hay GROQ_API_KEY configurada:
  - Tiene un tier gratuito generoso, corre modelos abiertos (Llama 3.3 70B) muy
    rápido, y es compatible con el endpoint estilo OpenAI — el mismo patrón
    que ya usaste en tu proyecto Victor (ingeniero de carreras con Whisper +
    LLaMA 3.3 70B).

Si NO hay GROQ_API_KEY, el sistema sigue funcionando con un clasificador
basado en reglas/palabras clave. Nunca se cae, nunca requiere pago.
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

# --- Fallback basado en reglas (siempre disponible, cero costo, cero dependencias externas) ---

_PALABRAS_CLAVE = {
    "rescate_escombros": ["atrapad", "escombro", "colapsó", "colapso", "derrumb", "atrapada", "sepultad"],
    "salud": ["herid", "sangre", "médic", "medico", "hospital", "fractura", "urgencia médica"],
    "medicamentos": ["medicamento", "insulina", "pastilla", "droga formulada", "tratamiento"],
    "agua": ["agua potable", "sed", "sin agua"],
    "alimentos": ["comida", "alimento", "hambre", "leche", "víveres", "viveres"],
    "refugio": ["carpa", "colchoneta", "dormir", "sin techo", "vivienda colapsada", "alberg"],
    "aseo": ["jabón", "jabon", "pañal", "panal", "toalla higiénica", "aseo"],
    "ropa": ["ropa", "cobija", "manta", "abrigo"],
    "mascotas": ["perro", "gato", "mascota", "concentrado para animales"],
    "reconstruccion": ["reconstruir", "reparar vivienda", "material de construcción"],
}

_URGENCIA_ALTA = ["atrapad", "sepultad", "sangrando", "no respira", "urgente", "muriendo", "colapsó ahora"]


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
        "fuente_clasificacion": "reglas",
    }


def _clasificar_con_groq(descripcion: str, zona: str) -> Optional[dict]:
    if not GROQ_API_KEY:
        return None

    prompt = f"""Eres un asistente de triage para ayuda humanitaria tras el terremoto en Pereira, Colombia (10 ago 2026).
Clasifica esta solicitud ciudadana. Responde SOLO con JSON válido, sin texto adicional, con este formato exacto:
{{"categoria": "<una de: {', '.join(CATEGORIAS_VALIDAS)}>", "urgencia": "<alta|media|baja>", "resumen": "<resumen de máximo 25 palabras>"}}

Zona: {zona}
Solicitud: "{descripcion}"
"""
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
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
        # El modelo a veces envuelve el JSON en ```json ... ``` — limpiar por seguridad
        contenido = contenido.replace("```json", "").replace("```", "").strip()
        data = json.loads(contenido)

        if data.get("categoria") not in CATEGORIAS_VALIDAS:
            data["categoria"] = "otro"
        if data.get("urgencia") not in ("alta", "media", "baja"):
            data["urgencia"] = "media"

        data["fuente_clasificacion"] = "groq_llama_3.3_70b"
        return data
    except Exception:
        # Cualquier fallo de red/parseo/cuota -> nunca tumbar el sistema, usar fallback
        return None


def clasificar_solicitud(descripcion: str, zona: str = "") -> dict:
    """Punto de entrada único: intenta IA gratuita, si falla usa reglas."""
    resultado = _clasificar_con_groq(descripcion, zona)
    if resultado is None:
        resultado = _clasificar_por_reglas(descripcion)
    return resultado


def sugerir_colectivos(solicitud_categoria: str, solicitud_zona: str, colectivos: list) -> list:
    """
    Rankea colectivos candidatos para una solicitud.
    Puramente basado en reglas — determinístico, auditable y gratis.
    (Se puede añadir un paso de re-ranking con Groq después si el volumen lo justifica;
    para el MVP de Pereira, esto es suficiente y más fácil de confiar/depurar.)
    """
    sugerencias = []
    zona_lower = (solicitud_zona or "").lower()

    for c in colectivos:
        if not c.verificado or not c.disponible:
            continue

        puntaje = 0.0
        razones = []

        tipo_relevante = {
            "rescate_escombros": ["rescate"],
            "salud": ["salud"],
            "medicamentos": ["salud"],
            "alimentos": ["alimentos", "logistica"],
            "agua": ["alimentos", "logistica"],
            "refugio": ["logistica", "construccion"],
            "aseo": ["logistica", "alimentos"],
            "ropa": ["logistica"],
            "reconstruccion": ["construccion"],
        }.get(solicitud_categoria, [])

        if c.tipo.value in tipo_relevante or c.tipo.value == "oficial_verificado":
            puntaje += 2.0
            razones.append(f"tipo de colectivo ({c.tipo.value}) coincide con la categoría")

        cobertura = (c.zona_cobertura or "").lower()
        if zona_lower and zona_lower in cobertura:
            puntaje += 3.0
            razones.append(f"cubre explícitamente la zona '{solicitud_zona}'")
        elif not cobertura:
            puntaje += 0.5
            razones.append("sin restricción de zona declarada")

        if puntaje > 0:
            sugerencias.append({
                "colectivo": c,
                "puntaje": puntaje,
                "razon": "; ".join(razones) if razones else "coincidencia parcial",
            })

    sugerencias.sort(key=lambda s: s["puntaje"], reverse=True)
    return sugerencias[:5]
