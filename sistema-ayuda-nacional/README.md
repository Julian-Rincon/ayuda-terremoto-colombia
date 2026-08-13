# Sistema de Ayuda Nacional — Nodo Central

Backend del **Nodo Central** de la arquitectura híbrida descrita en
[`planoidea.md`](../planoidea.md): coordina reportes ciudadanos (WhatsApp,
Ushahidi, web/manual) y centros territoriales tras el terremoto de Colombia
del 10 de agosto de 2026, con auto-activación real cuando USGS detecta un
sismo fuerte en el país.

**Este sistema no maneja donaciones ni pagos.** Es una decisión de diseño
deliberada (ver `docs/superpowers/specs/2026-08-13-sistema-ayuda-nacional-design.md`
en la raíz del repo): un sistema que toca dinero real es el punto de mayor
riesgo reputacional si algo falla. El dinero sigue fluyendo por los canales
reales que ya existen — Cruz Roja, ABACO, Bancos de Alimentos, Bre-B directo
a las llaves institucionales que esas entidades ya publican. Este proyecto
se enfoca en lo que sí puede ser fuente primaria: reportes de necesidades,
coordinación entre centros, recursos en especie.

Es independiente de [`pereira-ayuda-backend/`](../pereira-ayuda-backend/)
(el MVP acotado a una sola ciudad) — no lo reemplaza ni depende de él.

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
# opcional: pega tu GROQ_API_KEY en .env si quieres clasificación por LLM real

uvicorn app.main:app --reload
```

Abre `http://localhost:8000/docs` — Swagger UI interactivo, prueba todo desde ahí.

## Correr los tests

```bash
pytest -v
```

42 tests, cubren: modelos, clasificación IA con fallback, auth JWT y
validación de firma de webhooks, siembra de datos (sin contactos
inventados), pipeline de priorización, export HXL, USGS (umbral de
activación, dedup, resiliencia a fallos de red), WhatsApp y Ushahidi
(sandbox), y la app FastAPI completa end-to-end.

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
| GET | `/api/v1/sitrep.csv?formato=hxl` | Export HXL para HDX / ONG internacionales |
| WS | `/ws` | Feed de eventos en tiempo real |

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

- **Nodos Locales offline-first** (React/Vite + SQLite/IndexedDB con sync)
  — siguiente fase, este Nodo Central es su prerrequisito.
- **Capas WMS/WFS reales** (GeoServer + PostGIS vivo) para integrar con
  ICDE/SNIGRD — este build usa lat/lon simples, suficiente para el pipeline
  y los exports, pero no un servidor geoespacial real.
- Migrar de SQLite a Postgres (`DATABASE_URL`) antes de cualquier volumen
  de producción real.
