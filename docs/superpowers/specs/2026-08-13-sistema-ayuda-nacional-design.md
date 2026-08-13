# Sistema de Ayuda Nacional — Nodo Central (diseño)

**Fecha:** 2026-08-13
**Basado en:** `planoidea.md` (arquitectura híbrida completa, terremoto Colombia agosto 2026)
**Relación con `pereira-ayuda-backend/`:** proyecto independiente. No se modifica ni se depende del backend de Pereira; ese prototipo sigue siendo el MVP acotado a una ciudad y queda tal cual.

## 0. Verificación previa

Antes de construir, se confirmó que los fundamentos técnicos de `planoidea.md` siguen vigentes (agosto 2026):

- El terremoto (M7.4, San José del Palmar, Chocó, 10 ago 2026, ~130 fallecidos, desastre nacional declarado) es un evento real y ampliamente cubierto — Wikipedia, Infobae, Chequeado, Diario Libre coinciden en magnitud, epicentro y hora.
- El feed GeoJSON de USGS (`earthquake.usgs.gov/earthquakes/feed/v1.0/summary/...`) está en línea y responde en el formato esperado — se probó en vivo.
- Bre-B está operativo y con adopción real (218+ entidades participantes, >370M transacciones a enero 2026 según Banco de la República) — la arquitectura de conciliación vía banco aliado es el patrón correcto, no una API pública directa.
- Ushahidi Platform API v5 está documentada y activa (Postman/SwaggerHub oficiales) — confirma que integrar contra su REST API es viable tal como describe la sección 3.3.

Conclusión: el diseño de `planoidea.md` no está desactualizado ni es especulativo — es una base sólida para construir sobre ella hoy.

## 1. Alcance de este build

Del diagrama de `planoidea.md` §2, este proyecto construye el **Nodo Central**, con un recorte deliberado. Quedan fuera de este alcance (documentado explícitamente, no fingido):

- **Donaciones y pagos (Bre-B, PSE, conciliación bancaria)** — recortado a propósito, decisión explícita del 2026-08-13. Un sistema que toca dinero real (aunque sea "solo" conciliación) es el punto de mayor riesgo reputacional si algo falla: una asignación de contacto mal hecha es un error corregible, una donación mal conciliada o un webhook de pagos confundido con producción es el tipo de fallo que hace que la gente desconfíe de todo lo demás. El dinero sigue fluyendo por los canales reales que ya existen y funcionan (Cruz Roja, ABACO, Bancos de Alimentos, Bre-B directo a las llaves institucionales publicadas) — este sistema no se mete ahí. Se enfoca en lo que sí puede ser la fuente primaria: reportes ciudadanos, necesidades de terreno, recursos en especie, coordinación entre centros.
- **Nodos Locales offline-first** (React/Vite + SQLite/IndexedDB) — siguiente fase, el Nodo Central es su prerrequisito.
- **Servidor WMS/WFS real** (GeoServer + PostGIS vivo) — requiere infraestructura geoespacial dedicada; se documenta como paso futuro. Este build usa lat/lon simples, suficiente para el pipeline y los exports.
- **Credenciales reales de terceros** (verificación de negocio Meta, instancia Ushahidi hosteada) — no existen todavía. Las integraciones se implementan con la forma exacta que tendrían en producción, pero en **modo sandbox**: mismo payload, misma validación de firma donde aplica, alimentadas por datos simulados o un endpoint de simulación explícito. El README documenta qué credencial falta para activarlas de verdad. Mismo patrón que ya usa `ai_helper.py` de Pereira con Groq.

Lo que **sí** es real y funcional sin ninguna credencial:
- Poller de USGS (API pública gratuita).
- Todo el modelo de datos, pipeline de asignación de recursos en especie, export HXL.
- Clasificación de `ReporteCiudadano` (Groq gratis si hay `GROQ_API_KEY`, si no, reglas — igual que Pereira).

## 2. Estructura del proyecto

```
sistema-ayuda-nacional/
├── app/
│   ├── main.py                 # FastAPI app, rutas
│   ├── models.py                # SQLAlchemy: CentroLocal, Solicitud,
│   │                             #   ReporteCiudadano, EventoSismico, NodoCredencial
│   ├── schemas.py               # Pydantic
│   ├── database.py              # SQLite por defecto, DATABASE_URL para Postgres
│   ├── auth.py                  # JWT por CentroLocal, API key para webhooks
│   ├── ai_helper.py             # Clasificación Groq + fallback por reglas (mismo patrón que Pereira)
│   ├── pipeline.py              # ejecutarPipelineDeAsignacion (§5 planoidea.md)
│   ├── hxl_export.py            # generarSitrepHXL — CSV real, sin dependencias externas
│   ├── websocket_manager.py     # Broadcast en tiempo real (mismo patrón que Pereira)
│   ├── seed_data.py             # CentroLocal reales: Pereira/Risaralda, Chocó, Caldas, Valle
│   └── integrations/
│       ├── usgs.py              # REAL — poller cada 60s, activarModoEmergencia()
│       ├── whatsapp.py          # Sandbox — webhook + validación de firma + simulador
│       └── ushahidi.py          # Sandbox — cliente REST v5 + fixture si no hay instancia configurada
├── tests/
│   ├── test_pipeline.py
│   ├── test_hxl_export.py
│   ├── test_webhooks.py         # firmas válidas/inválidas
│   └── test_usgs_trigger.py     # umbral de auto-activación
├── .env.example
├── requirements.txt
└── README.md                    # qué es real, qué es sandbox, cómo activar cada integración real
```

## 3. Modelo de datos

Subconjunto del diagrama UML de `planoidea.md` §4, sin la rama de donaciones: `CentroLocal`, `Solicitud`, `ReporteCiudadano`, `EventoSismico`, más las relaciones de coordinación/recepción/escucha ya especificadas ahí (`GestorDistribucionCentral` coordina `CentroLocal`, recibe `ReporteCiudadano` de WhatsApp/Ushahidi, escucha `EventoSismico`). `Donacion` y `CanalDonacion` quedan fuera — ver §1. Se añade una tabla `NodoCredencial` (no está en el UML original) para las credenciales JWT de cada `CentroLocal` — necesaria para que el endpoint de autenticación funcione, y coherente con "Autenticación: JWT para nodos locales" de la §6.

## 4. Endpoints (subconjunto de §6 de planoidea.md — sin las rutas de donaciones/pagos)

```
POST   /api/v1/webhooks/whatsapp
GET    /api/v1/reportes?estado=pendiente
POST   /api/v1/reportes/{id}/verificar
GET    /api/v1/centros/{id}/necesidades
POST   /api/v1/centros/{id}/entregas
GET    /api/v1/sitrep.csv?formato=hxl
GET    /api/v1/eventos-sismicos/ultimo
```

Se añaden endpoints de sandbox, claramente namespaced aparte para que nunca se confundan con producción:
```
POST   /sandbox/whatsapp/simular
POST   /sandbox/ushahidi/simular
```

## 5. Resiliencia y confianza

- Verificación humana obligatoria antes de que un `ReporteCiudadano` derive en asignación de recursos (mismo gate que el prototipo de Pereira, mandado explícitamente por §8 de `planoidea.md`).
- Toda llamada externa (USGS, Ushahidi) en try/except — nunca tumba el proceso.
- El sistema no toca dinero: cero superficie de riesgo financiero, cero webhook que alguien pueda confundir con un canal de pago real. El README es explícito sobre esto y redirige a los canales oficiales de donación.
- Los datos sembrados de `CentroLocal` para Chocó/Caldas/Valle **no incluyen contactos inventados** — quedan marcados como pendientes de verificación humana, siguiendo la misma disciplina que ya usa `seed_data.py` de Pereira para sus canales oficiales.

## 6. Testing

pytest cubriendo: cálculo proporcional del pipeline de asignación, formato de export HXL, validación de firma de webhooks (caso válido e inválido), umbral de magnitud≥6.0 para auto-activación. Smoke test manual vía `uvicorn` + `/docs`.

## 7. Publicación

El resultado se publica como repositorio público en GitHub bajo licencia MIT, con README enfocado en que cualquier colectivo/ONG lo pueda levantar y adaptar. Sin atribución de herramienta de IA en commits, README ni ningún archivo — es un proyecto del usuario.
