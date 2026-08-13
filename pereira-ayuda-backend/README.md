# Pereira Ayuda — Backend del prototipo

Backend funcional (probado end-to-end) para conectar **solicitudes de ayuda**
en Pereira con **colectivos** (desarrollo, diseño, logística, salud, rescate,
canales oficiales) tras el terremoto del 10 de agosto de 2026.

Alcance deliberado: **solo Pereira, por ahora.** Nada de arquitectura nacional
multi-nodo todavía — eso es la versión 2 si esto funciona.

## Qué resuelve

- La comunidad reporta necesidades (vía web, y con estructura lista para
  conectar WhatsApp) → el sistema las clasifica automáticamente (categoría +
  urgencia) con IA **gratuita**.
- Colectivos y voluntarios se registran, pero **no aparecen como asignables
  hasta que un humano los verifica** — esto es intencional: ya hay estafas
  reales circulando haciéndose pasar por plataformas de ayuda para el
  terremoto (ver `app/seed_data.py::ALERTA_SEGURIDAD`).
- Todo cambio (nueva solicitud, nueva asignación, nuevo colectivo pendiente
  de verificar) se transmite en tiempo real por WebSocket — listo para
  alimentar un mapa o dashboard en vivo.

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

## La parte de "IA gratuita"

`app/ai_helper.py` intenta clasificar cada solicitud con **Groq** (API
gratuita, modelo Llama 3.3 70B — el mismo que ya usaste en tu proyecto
Victor). Si no configuras `GROQ_API_KEY`, o si la llamada falla por
cualquier razón, cae automáticamente a un clasificador por palabras clave
que **nunca falla y no depende de internet**. El sistema jamás se cae por
esto — en el peor caso, clasifica un poco menos fino.

Conseguir la llave gratis: [console.groq.com](https://console.groq.com) →
crear cuenta → API Keys → copiar a `.env`.

El matching de "qué colectivo debería atender esta solicitud" (`sugerir_colectivos`)
es **puramente basado en reglas** a propósito — en medio de una emergencia real,
preferí que la lógica de asignación sea 100% auditable y depurable por un humano,
en vez de una caja negra de LLM. Es fácil añadir un paso de re-ranking con IA
encima después, si el volumen de solicitudes lo justifica.

## Endpoints principales

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/api/v1/solicitudes` | Crear solicitud (clasificación automática si no envías `categoria`) |
| GET | `/api/v1/solicitudes` | Listar/filtrar por estado, categoría, zona |
| GET | `/api/v1/solicitudes/{id}/sugerencias` | Colectivos recomendados para esa solicitud |
| PATCH | `/api/v1/solicitudes/{id}/estado` | Actualizar estado |
| POST | `/api/v1/solicitudes/{id}/asignar` | Asignar un colectivo verificado |
| POST | `/api/v1/colectivos` | Registrar colectivo (queda pendiente de verificar) |
| PATCH | `/api/v1/colectivos/{id}/verificar` | Aprobar humano — obligatorio antes de poder asignar |
| GET | `/canales-oficiales` | Alcaldía, Cruz Roja Pereira, Hospital San Jorge (precargados) |
| GET | `/api/v1/stats` | Contadores en vivo |
| WS | `/ws` | Feed de eventos en tiempo real |

## Desplegarlo gratis (para que exista en una URL real, no solo en tu máquina)

**Render** es la opción con free tier permanente real en este momento (2026).
Contras a tener presentes: el servicio se "duerme" tras 15 min sin tráfico y
tarda 30-60s en despertar — molesto si alguien entra en medio de una emergencia
y el primer request tarda. Si esto empieza a moverse en serio, vale la pena
pasar al plan pago más barato (~$7/mes) para que no se duerma.

Pasos:
1. Sube este repo a GitHub.
2. En Render: "New Web Service" → conecta el repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Variables de entorno: agrega `GROQ_API_KEY` si la tienes.

Railway y Fly.io ya no tienen free tier permanente en 2026 (solo trial de
días/horas) — verifica precios actuales antes de decidir, cambian seguido.

## Próximos pasos honestos

- **Falta un frontend.** Esto es solo backend, tal como pediste. El WebSocket
  y los endpoints ya están listos para que alguien de diseño/frontend del
  colectivo construya un mapa/dashboard encima.
- **Falta conectar WhatsApp de verdad** (el modelo de datos y el campo `fuente`
  ya están listos para eso — falta el webhook de Meta Cloud API).
- **Los canales oficiales sembrados en `seed_data.py` deben re-verificarse**
  antes de mostrarlos a nadie más — son de medios de comunicación del 12-13
  de agosto, y los números/horarios de una emergencia activa cambian rápido.
- Considera agregar autenticación real antes de exponerlo públicamente —
  ahora mismo cualquiera puede pegarle a la API sin restricción.
