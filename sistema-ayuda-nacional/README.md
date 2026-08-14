# Sistema de Ayuda Nacional — Nodo Central

Backend del **Nodo Central** de la arquitectura híbrida descrita en
[`planoidea.md`](../planoidea.md): coordina reportes ciudadanos (WhatsApp,
Ushahidi, web/manual) y centros territoriales tras el terremoto de Colombia
del 10 de agosto de 2026, con auto-activación real cuando USGS detecta un
sismo fuerte en el país.

**Este sistema no maneja donaciones ni pagos.** Es una decisión de diseño
deliberada: un sistema que toca dinero real es el punto de mayor
riesgo reputacional si algo falla. El dinero sigue fluyendo por los canales
reales que ya existen — Cruz Roja, ABACO, Bancos de Alimentos, Bre-B directo
a las llaves institucionales que esas entidades ya publican. Este proyecto
se enfoca en lo que sí puede ser fuente primaria: reportes de necesidades,
coordinación entre centros, recursos en especie.

Este backend cubre Pereira (como el centro `risaralda-pereira`) además de
Chocó, Caldas y Valle del Cauca — es el único backend del proyecto. Hubo un
prototipo anterior acotado solo a Pereira; se retiró cuando este sistema
nacional lo superó en todo (verificación, envíos, colectivos, mapa, alertas)
sin perder nada — los 2 canales oficiales que tenía de más (Cruz Roja
Pereira, banco de sangre del Hospital San Jorge) ya están sembrados acá como
`Colectivo` verificados.

## Qué es real y qué es sandbox

| Integración | Estado | Detalle |
|---|---|---|
| USGS (alertas sísmicas) | **Real** | API pública gratuita, sin credenciales. Poll cada 60s a `earthquake.usgs.gov`. |
| Clasificación de reportes | **Real** (con fallback) | Groq/Llama gratis si hay `GROQ_API_KEY`; si no, clasificador por reglas — nunca falla. |
| Export HXL | **Real** | Solo formatea datos locales, sin dependencias externas. |
| WhatsApp Business Cloud API | **Sandbox** | El webhook usa el formato real de Meta y valida `X-Hub-Signature-256` — pero sin `WHATSAPP_APP_SECRET` configurado, no exige firma (modo desarrollo). Usa `POST /sandbox/whatsapp/simular` para probar sin cuenta Meta real. |
| Ushahidi Platform | **Sandbox** | Cliente REST v5 real; si no hay `USHAHIDI_BASE_URL` configurada, sirve una fixture con la misma forma. Dispara con `POST /api/v1/integraciones/ushahidi/sincronizar`. |

Para activar cualquiera de las dos integraciones sandbox, solo hay que
poner la variable de entorno correspondiente en `.env` — el código no
cambia, mismo patrón que ya usa `ai_helper.py` con Groq.

## Levantar en local (5 minutos)

```bash
python3 -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# opcional: pega tu GROQ_API_KEY en .env si quieres clasificación y
# resúmenes (alerta sísmica, resumen del coordinador) por LLM real

uvicorn app.main:app --reload
```

Abre `http://localhost:8000/docs` — Swagger UI interactivo, prueba todo desde ahí.

## Correr los tests

```bash
pytest -v
```

76 tests, cubren: modelos, clasificación IA con fallback, auth JWT y
validación de firma de webhooks, siembra de datos (sin contactos
inventados, incluyendo los colectivos oficiales verificados), pipeline de
priorización, export HXL, USGS (umbral de activación, dedup, resiliencia a
fallos de red), WhatsApp y Ushahidi (sandbox), detección de duplicados,
envíos en camino, colectivos/voluntarios, resumen nacional, alertas
sísmicas y resúmenes con IA, y la app FastAPI completa end-to-end.

## Endpoints principales

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/centros` | Listar centros territoriales |
| GET | `/api/v1/centros/{id}/necesidades` | Necesidades pendientes agregadas por categoría |
| POST | `/api/v1/centros/{id}/entregas` | Marcar una solicitud como entregada (requiere JWT del centro) |
| POST | `/api/v1/auth/token` | Login de un centro local (`id_territorio` + secreto → JWT) |
| POST | `/api/v1/reportes` | Crear reporte manual/web (clasificación automática) |
| GET | `/api/v1/reportes?verificado=false` | Cola de verificación |
| POST | `/api/v1/reportes/{id}/verificar` | Verificación humana → crea Solicitud formal |
| POST | `/api/v1/webhooks/whatsapp` | Webhook real de WhatsApp Cloud API (sandbox si no hay firma configurada) |
| POST | `/sandbox/whatsapp/simular` | Simular un mensaje de WhatsApp entrante |
| POST | `/api/v1/integraciones/ushahidi/sincronizar` | Sincronizar posts nuevos desde Ushahidi (o fixture) |
| GET | `/api/v1/eventos-sismicos/ultimo` | Último evento sísmico detectado por USGS |
| GET | `/api/v1/eventos-sismicos?dias=7` | Historial de sismos recientes (no solo el último) |
| GET | `/api/v1/eventos-sismicos/alerta` | Resumen en lenguaje simple de la actividad sísmica (IA + fallback) |
| GET | `/api/v1/centros/{id}/necesidades/resumen-ia` | Resumen para el coordinador de qué atender primero (IA + fallback) |
| GET | `/api/v1/sitrep.csv?formato=hxl` | Export HXL para HDX / ONG internacionales |
| POST | `/api/v1/envios` | Registrar un envío de recursos en especie hacia un centro (queda sin verificar) |
| GET | `/api/v1/envios?centro_id=&categoria=&estado=&verificado=` | Listar envíos, filtrable |
| PATCH | `/api/v1/envios/{id}/verificar` | Verificación humana — obligatoria antes de que cuente como cobertura |
| PATCH | `/api/v1/envios/{id}/estado` | Actualizar estado (`comprometido` → `en_transito` → `entregado`) |
| POST | `/api/v1/colectivos` | Registro público de un voluntario/colectivo (queda sin verificar) |
| GET | `/api/v1/colectivos?verificado=&tipo=` | Listar colectivos, filtrable |
| PATCH | `/api/v1/colectivos/{id}/verificar` | Verificación humana — obligatoria antes de aparecer disponible |
| GET | `/api/v1/resumen` | Panorama agregado nacional (sin login) — para la vista pública |
| WS | `/ws` | Feed de eventos en tiempo real |

## Colectivos: el otro lado de "conectar a quien necesita con quien puede darla"

Registro público y abierto para que cualquier persona o grupo se anote como
voluntario/colectivo (`POST /api/v1/colectivos`, sin autenticación). Igual
que reportes y envíos: nace con `verificado=false` y nunca aparece
disponible ni se le puede asignar nada hasta que un humano coordinador lo
confirme — así nadie puede hacerse pasar por ayuda legítima.

## Resumen nacional

`GET /api/v1/resumen` agrega en un solo lugar el estado de todo el sistema
(no de un centro en particular): cuántos centros hay, reportes totales y
pendientes de verificar, solicitudes activas por categoría, colectivos
confirmados, envíos verificados en camino, y el último sismo detectado. Es
el endpoint que alimenta la pantalla de inicio pública de `nodo-local/` —
pensado para que cualquiera vea el sistema funcionando sin necesitar
credenciales de coordinador.

## Envíos: evitar que dos sitios manden lo mismo sin saberlo

Cuando alguien se compromete a mandar recursos hacia un centro (ej. "desde
Bogotá vienen 50 kits de alimentos y 10 de medicamentos"), se registra como
`Envio` — **cantidad de unidades/kits, nunca dinero**. `GET
/api/v1/centros/{id}/necesidades` ahora también devuelve
`envios_verificados_por_categoria`, para que cualquiera vea de un vistazo si
una necesidad ya tiene cobertura en camino antes de duplicar el esfuerzo.

Mismo gate de confianza que el resto del sistema: un envío nace con
`verificado=false` y **no cuenta** en `necesidades` hasta que un humano lo
confirma — si no, cualquiera podría declarar falsamente "esto ya viene
cubierto" para bajarle prioridad a una necesidad real.

## Detección de posibles duplicados

Un mismo hecho puede llegar reportado dos veces por canales distintos
(alguien lo manda por WhatsApp, otra persona lo publica en Ushahidi). Cada
reporte nuevo se compara contra reportes recientes de la misma categoría con
`difflib` (fuzzy matching de texto, librería estándar de Python) — si la
similitud pasa un umbral, queda marcado con `posible_duplicado_de_id`
apuntando al original. **Deliberadamente no usa IA/LLM para esto**: es un
problema clásico de similitud de texto, no de razonamiento, y un modelo de
lenguaje acá sería más lento, más caro y menos auditable que un algoritmo
determinístico. Nunca se fusiona ni se descarta nada automáticamente — el
campo solo alimenta la cola de verificación humana (`app/dedup.py`).

## Alerta sísmica y resúmenes con IA

El feed de USGS pasó de `significant_hour` (solo sismos de relevancia
global) a `2.5_hour` (todo sismo M≥2.5 en el mundo, filtrado a Colombia
acá) — la réplica real de magnitud 4.2-4.3 en Chocó del 13 de agosto de
2026 nunca habría aparecido en el feed anterior. `GET
/api/v1/eventos-sismicos` guarda el historial completo, no solo el último
evento, para ver la secuencia de réplicas.

Dos lugares usan Groq para generar texto en español sencillo a partir de
datos que el sistema ya tiene (`app/ai_helper.py`):
- **Alerta sísmica** (`/eventos-sismicos/alerta`): resume la actividad
  sísmica reciente.
- **Resumen para el coordinador** (`/centros/{id}/necesidades/resumen-ia`):
  ayuda a decidir qué atender primero.

Ambos con reglas estrictas en el prompt — **nunca inventan daños,
víctimas ni instrucciones de seguridad**, solo reformulan los hechos que
ya están en la base de datos — y con el mismo fallback por plantilla que
`clasificar_reporte` si Groq falla o no hay llave configurada
(`generado_por_ia` en la respuesta indica cuál se usó). El resumen siempre
viene acompañado de los datos crudos en los que se basa, nunca reemplaza la
fuente.

## Seguridad y confianza

- Verificación humana obligatoria antes de que un reporte se convierta en
  una solicitud formal — nunca hay asignación automática sin un humano en
  el loop.
- Los centros territoriales sembrados fuera de Pereira (Chocó, Caldas,
  Valle) **no tienen contacto inventado** — quedan marcados como pendientes
  de verificación hasta que alguien lo confirme con la entidad real.
- Cambia `JWT_SECRET` y `NODOS_SECRETO_INICIAL` en `.env` antes de cualquier
  despliegue real — los valores de ejemplo son solo para desarrollo local.

## Próximos pasos honestos

- **Nodo Local offline-first** ya existe — ver [`nodo-local/`](../nodo-local/)
  (React/Vite + IndexedDB con sync). Este backend es su prerrequisito y ya
  está cubierto.
- **Capas WMS/WFS reales** (GeoServer + PostGIS vivo) para integrar con
  ICDE/SNIGRD — este build usa lat/lon simples, suficiente para el pipeline,
  el mapa y los exports, pero no un servidor geoespacial real.
- Migrar de SQLite a Postgres (`DATABASE_URL`) antes de cualquier volumen
  de producción real.
