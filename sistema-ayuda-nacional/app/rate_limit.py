"""
Límite de tasa para endpoints públicos de escritura (sin autenticación) —
protege /reportes y /colectivos de scripts de spam el mismo día en que el
repo se vuelve público. Límites generosos para uso humano real.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
