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

## Levantar el proyecto

Un comando, desde la raíz:

```bash
cp .env.docker.example .env
docker compose up --build
```

Nodo Local en <http://localhost:5173>, Nodo Central en
<http://localhost:8000/docs>. Para correr cada pieza sin Docker, el README
de cada subproyecto tiene las instrucciones.

## Guías

Lo que no cabe en un README:

| Guía | Para qué |
|---|---|
| [Conectar tu propio WhatsApp](sistema-ayuda-nacional/docs/whatsapp-meta.md) | Enchufar un número real de WhatsApp Business al despliegue |
| [GeoServer + PostGIS](sistema-ayuda-nacional/docs/geoserver-postgis.md) | Publicar las capas WMS/WFS para que otras entidades consuman los datos |
| [Monitoreo y alertas](sistema-ayuda-nacional/docs/monitoreo.md) | Enterarse de que se cayó sin estar mirando el dashboard |
| [Migración a Neon](sistema-ayuda-nacional/docs/migracion-neon.md) | Plan B de base de datos gratuita |
| [Pruebas de carga](sistema-ayuda-nacional/docs/pruebas-carga.md) | Cuánto aguanta el backend y dónde empieza a doler |
| [Accesibilidad y PWA](nodo-local/docs/accesibilidad-pwa.md) | Navegación por teclado, contraste, instalación offline |
| [Política de seguridad](SECURITY.md) | Reportar una vulnerabilidad y qué datos personales se manejan |

## Reglas del proyecto (no negociables)

- **Nada se asigna automáticamente sin verificación humana** — reportes,
  colectivos y envíos nacen con `verificado=false` y así se quedan hasta
  que alguien lo confirme. No cambies este patrón sin discutirlo primero.
- **No inventes contactos ni datos de entidades reales.** Si vas a sembrar
  un canal oficial nuevo, tiene que estar confirmado, no supuesto.
- **No se toca el alcance de "no maneja pagos ni donaciones".**

## Antes de abrir tu PR

Lo mismo que corre CI, en local:

```bash
# sistema-ayuda-nacional/
pytest -v

# nodo-local/
npm run lint
npm test
```

Si tocaste markdown:

```bash
npx markdownlint-cli2
```

Sin argumentos: qué se lintea sale de `.markdownlint-cli2.jsonc` y las
reglas de `.markdownlint.jsonc`, así que da el mismo resultado que CI.

Un PR que rompe tests existentes no se mergea hasta que se arregle.

### Qué esperamos de un cambio

- **Código nuevo viene con prueba.** No por cubrir una métrica: porque este
  sistema se usa cuando algo salió mal en el mundo real y nadie va a estar
  disponible para depurar en vivo.
- **El mensaje de commit explica por qué, no qué.** El diff ya dice qué
  cambió. Lo que no se puede reconstruir después es la razón.
- **Sin advertencias nuevas.** La suite corre con 3 advertencias, todas de
  dependencias externas. Si tu cambio agrega una, se ve.
- **Nada de datos reales en el PR.** Ni contenido de reportes, ni
  coordenadas sin verificar, ni teléfonos en capturas — ver
  [SECURITY.md](SECURITY.md).
- **Usá `Closes #N` en inglés** en la descripción del PR. GitHub no cierra
  issues con "Cierra #N", y ya nos pasó.

## Si encontrás una vulnerabilidad

No abras un issue público. Ver [SECURITY.md](SECURITY.md) — el repositorio
maneja datos de personas que pidieron ayuda, y un hueco documentado en un
issue abierto queda a disposición de cualquiera mientras se arregla.

## Contribuidores

Gracias a quienes ya sumaron trabajo real acá:

- [@LeonardSF](https://github.com/LeonardSF) — plantillas de issues y pull
  request en `.github/`.
- [@VedantMadane](https://github.com/VedantMadane) — `CODE_OF_CONDUCT.md`.

## Licencia

MIT — ver `LICENSE`.
