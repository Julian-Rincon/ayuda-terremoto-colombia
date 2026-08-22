# Cómo contribuir

Gracias por sumarte. Este proyecto conecta reportes de necesidades tras el
terremoto del 10 de agosto de 2026 con los colectivos que responden en
terreno. **No maneja donaciones ni pagos** — es una decisión de diseño
deliberada, no un descuido.

## Antes de empezar

1. Lee el README del subproyecto donde vas a trabajar
   (`sistema-ayuda-nacional/` o `nodo-local/`).
2. Únete al grupo de coordinación de contribuidores (pídelo por acá o al
   correo de contacto) — ahí se coordina quién está en qué.
3. Comenta en el issue que quieras tomar antes de empezar, para que no dos
   personas trabajen en lo mismo sin saberlo.

## Reglas del proyecto (no negociables)

- **Nada se asigna automáticamente sin verificación humana** — reportes,
  colectivos y envíos nacen con `verificado=false` y así se quedan hasta
  que alguien lo confirme. No cambies este patrón sin discutirlo primero.
- **No inventes contactos ni datos de entidades reales.** Si vas a sembrar
  un canal oficial nuevo, tiene que estar confirmado, no supuesto.
- **No se toca el alcance de "no maneja pagos ni donaciones".**

## Correr los tests antes de tu PR

```bash
# sistema-ayuda-nacional/
pytest -v

# nodo-local/
npm test
```

Un PR que rompe tests existentes no se mergea hasta que se arregle.

## Licencia

MIT — ver `LICENSE`.
