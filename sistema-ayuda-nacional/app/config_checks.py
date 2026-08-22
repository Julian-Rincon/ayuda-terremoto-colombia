"""
Guardia de arranque: si ENVIRONMENT=production y los secretos siguen con el
valor de ejemplo de .env.example, la app se niega a arrancar. Un checklist
de "acuérdate de rotar esto antes de desplegar" se olvida; un arranque que
falla con un mensaje claro, no.
"""
import os

VALOR_POR_DEFECTO = "cambia-esto-en-produccion"
SECRETOS_REQUERIDOS = ("JWT_SECRET", "NODOS_SECRETO_INICIAL")


def verificar_secretos_de_produccion() -> None:
    if os.getenv("ENVIRONMENT", "development") != "production":
        return

    sin_rotar = [s for s in SECRETOS_REQUERIDOS if os.getenv(s, VALOR_POR_DEFECTO) == VALOR_POR_DEFECTO]
    if sin_rotar:
        raise RuntimeError(
            f"ENVIRONMENT=production pero {', '.join(sin_rotar)} sigue con el valor de "
            "ejemplo de .env.example. Genera un valor real y único antes de desplegar "
            "(ver README, sección Seguridad y confianza)."
        )
