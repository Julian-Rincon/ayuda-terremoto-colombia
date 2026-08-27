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

Este backend es el único backend del proyecto y cubre **los 33
departamentos de Colombia** (32 departamentos + Bogotá D.C.), no solo las
zonas con afectación confirmada. Hubo un prototipo anterior acotado solo a
Pereira; se retiró cuando este sistema nacional lo superó en todo
(verificación, envíos, colectivos, mapa, alertas) sin perder nada — los 2
canales oficiales que tenía de más (Cruz Roja Pereira, banco de sangre del
Hospital San Jorge) ya están sembrados acá como `Colectivo` verificados.

## Cobertura nacional: 33 departamentos, activación automática y manual

Este es el diseño central del sistema, no un detalle secundario: desde el
arranque, los 33 departamentos del país (`app/colombia.py`) quedan
sembrados como centros de coordinación. Solo 4 arrancan **activos** con
datos reales confirmados en medios — Pereira/Risaralda (contacto
verificado), Chocó, Caldas y Valle del Cauca (afectación oficial, contacto
todavía por confirmar). Los otros **29 quedan "dormidos"** (`activo=False`,
sin contacto inventado) hasta que hacen falta:

- **Activación automática:** el poll de USGS (`app/integrations/usgs.py`,
  cada 60s) activa solo el centro de cualquier departamento donde caiga un
  sismo de magnitud ≥ 4.0 (`MAGNITUD_UMBRAL_AUTO_SOPORTE`) — más bajo que
  el umbral de "modo emergencia" nacional (≥ 6.0), pero alto para no abrir
  un centro por cada temblor apenas perceptible. Si la geocodificación
  devuelve un departamento fuera de la siembra inicial (variante de nombre
  no contemplada), se crea un centro nuevo igual de dormido en vez de
  perder el sismo.
- **Activación manual:** `PATCH /api/v1/centros/{id}/activar` — red de
  seguridad para falsos negativos (sismo real bajo el umbral, geocodificación
  fallida, o cualquier otro motivo para coordinar una zona). Abierto,
  cualquiera puede activar un centro.

Ninguna de las dos vías inventa ni verifica contacto — activar solo abre el
espacio para que un humano lo complete después. `GET /api/v1/resumen`
cuenta solo centros `activo=True` en `total_centros`, así que el panorama
público nunca exagera cuánta cobertura real hay.

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

## Base de datos: SQLite en local, Postgres en producción

`DATABASE_URL` decide el motor — mismo código, sin ramas por engine. Por
defecto (sin configurar nada) usa SQLite local, para que levantar el
proyecto no dependa de tener Postgres instalado. En producción (Render) se
usa Postgres real, gestionado por el blueprint (`render.yaml`, bloque
`databases:`), conectado al backend vía `fromDatabase`.

Esto no es una preferencia cosmética: en el free tier de Render el disco es
efímero — el proceso se duerme por inactividad y, al despertar, el disco se
reinicia desde cero. Con SQLite (un archivo en ese disco) eso significa
**perder todos los datos sembrados cada vez que el servicio despierta**,
confirmado en producción real. Postgres gestionado por Render no comparte
ese disco efímero, así que sobrevive a los ciclos de sueño/despertar.

Para probar contra Postgres real en local (recomendado antes de tocar
`app/models.py` o `app/database.py`):

```bash
docker run -d --name ayuda-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=ayuda_test -p 5433:5432 postgres:16
export DATABASE_URL=postgresql://postgres:test@localhost:5433/ayuda_test
uvicorn app.main:app --reload
```

## Correr los tests

```bash
pytest -v
```

Por defecto corre contra SQLite en memoria. Para correr la misma suite
contra Postgres real (ver arriba), exportá `DATABASE_URL` antes:

```bash
export DATABASE_URL=postgresql://postgres:test@localhost:5433/ayuda_test
pytest -v
```

`tests/conftest.py` arma el engine de pruebas según esa variable, y cada
test deja el esquema limpio al terminar (`drop_all`) — necesario contra
Postgres real, que persiste entre tests a diferencia del SQLite en memoria.

97 tests, cubren: modelos, clasificación IA con fallback, auth JWT y
validación de firma de webhooks, siembra de datos (sin contactos
inventados, incluyendo los colectivos oficiales verificados), cobertura de
los 33 departamentos con activación automática y manual, rate limiting en
todos los endpoints públicos de escritura, pipeline de priorización,
export HXL, USGS (umbral de activación, dedup, resiliencia a fallos de
red), WhatsApp y Ushahidi (sandbox), detección de duplicados, envíos en
camino, colectivos/voluntarios, resumen nacional, alertas sísmicas y
resúmenes con IA, y la app FastAPI completa end-to-end — toda la suite
pasa igual contra SQLite y contra Postgres 16 real.

## Endpoints principales

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/centros` | Listar centros territoriales (los 33 departamentos, activos y dormidos) |
| PATCH | `/api/v1/centros/{id}/activar` | Activar a mano un centro dormido (ver "Cobertura nacional" arriba) |
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
- Ningún centro territorial sembrado fuera de Pereira **tiene contacto
  inventado** — ni los 3 con afectación confirmada (Chocó, Caldas, Valle),
  ni los 29 "dormidos" del resto del país. Todos quedan marcados como
  pendientes de verificación hasta que alguien lo confirme con la entidad
  real.
- Cambia `JWT_SECRET` y `NODOS_SECRETO_INICIAL` en `.env` antes de cualquier
  despliegue real — los valores de ejemplo son solo para desarrollo local. Si
  se te olvida, no pasa nada: con `ENVIRONMENT=production`, la app **se
  niega a arrancar** mientras sigan con el valor de ejemplo
  (`app/config_checks.py`).
- `POST /api/v1/reportes`, `POST /api/v1/colectivos` y `POST /api/v1/envios`
  (los endpoints públicos sin autenticación que escriben en la base) tienen
  rate limiting — 10 solicitudes por minuto por IP (`slowapi`,
  `app/rate_limit.py`). Ver "Pruebas de carga y estrés" abajo para cómo se
  verificó.

## Pruebas de carga y estrés

Detalle completo en [`docs/pruebas-carga.md`](docs/pruebas-carga.md)
(Locust, corrido en local contra una instancia propia — nunca contra la
URL pública ni contra una base real). Resumen:

- El rate limit de 10/min por IP corta exacto en los tres endpoints
  públicos de escritura, en secuencia y bajo concurrencia real, sin `500`
  ni escritura parcial. **`POST /api/v1/envios` no tenía este límite** —
  se encontró durante la prueba y se corrigió (mismo decorador que ya
  protegía a `/reportes` y `/colectivos`).
- Tráfico de lectura normal (50 usuarios concurrentes): latencias de un
  dígito de milisegundos, cero errores.
- Bajo estrés sostenido sin pausas, el punto de quiebre real aparece entre
  100 y 150 usuarios virtuales: se agota el pool de conexiones de
  SQLAlchemy (5 + 10 de desborde = 15 conexiones concurrentes), con
  errores `500` y el servicio lento por varios minutos después del pico.
  No se corrigió en esa tarea por ser un cambio de infraestructura de
  mayor alcance — queda documentado con mitigaciones concretas (subir
  `pool_size`, modo WAL, o Postgres) en el doc completo.

## Próximos pasos honestos

- **Nodo Local offline-first** ya existe — ver [`nodo-local/`](../nodo-local/)
  (React/Vite + IndexedDB con sync). Este backend es su prerrequisito y ya
  está cubierto.
- **Capas WMS/WFS reales** (GeoServer + PostGIS vivo) para integrar con
  ICDE/SNIGRD — este build usa lat/lon simples, suficiente para el pipeline,
  el mapa y los exports, pero no un servidor geoespacial real.
- ~~Migrar de SQLite a Postgres antes de cualquier volumen de producción
  real~~ — resuelto y **ya desplegado en producción** (26 de agosto de
  2026): el blueprint de Render sincronizó solo, creó la base gestionada y
  el backend real ya corre sobre Postgres, confirmado en vivo contra
  `https://ayuda-terremoto-nacional.onrender.com`.
  - **Pendiente real, con fecha:** el plan `free` de Postgres en Render
    expira/se elimina a los 30 días de creado — se borra sola el **25 de
    septiembre de 2026** si no se hace nada antes. Plan B ya definido y
    documentado en [`docs/migracion-neon.md`](docs/migracion-neon.md):
    mover la base a Neon, que sí es gratis sin fecha de expiración.
