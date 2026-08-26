# Pruebas de carga y estrés — Nodo Central

Pruebas ejecutadas **en local** contra una instancia propia del backend
(`uvicorn app.main:app --host 127.0.0.1 --port 8001`), con una base SQLite
de un solo uso creada para la ocasión — nunca contra la URL pública de
Render ni contra ninguna base de datos real. Herramienta usada: **Locust**
(más un par de scripts en Python con `requests`/`httpx` para verificar
comportamientos puntuales del rate limit con precisión de solicitud por
solicitud).

Objetivo: entender cómo se comporta el backend bajo tráfico concurrente
antes de que llegue tráfico público real, dado que un colegio anunció
apoyo institucional al proyecto.

## Resumen ejecutivo

- Los endpoints públicos de escritura (`/api/v1/reportes`,
  `/api/v1/colectivos`) respetan el límite de **10 solicitudes/minuto por
  IP** con precisión exacta: la solicitud 11 en adelante recibe `429`, sin
  ningún `500` y sin corrupción de datos (el conteo en `/api/v1/resumen`
  coincide exactamente con las solicitudes aceptadas).
- Se encontró que **`POST /api/v1/envios`** — también público, también sin
  autenticación, mismo perfil de riesgo que los dos anteriores — **no tenía
  rate limiting**. Se corrigió (ver sección "Corrección aplicada").
- Para tráfico de lectura normal (concurrencia humana realista, 50 usuarios
  concurrentes) el backend responde con latencias de un dígito de
  milisegundos y cero errores.
- Bajo estrés agresivo y sostenido (~120–150 usuarios virtuales golpeando
  sin pausa), el backend **sí tiene un punto de quiebre real**: se agota el
  pool de conexiones de SQLAlchemy (por defecto 5 + 10 de desborde = 15
  conexiones concurrentes a SQLite) y empiezan a aparecer errores `500`,
  con el servicio quedando lento/no responde por un buen rato después del
  pico. Esto **no se corrigió** en esta tarea por ser un cambio de mayor
  alcance (ver sección de hallazgos grandes) — queda documentado con
  números concretos para que se revise y priorice.

## Metodología

Tres escenarios, tal como pedía la tarea:

**(a) Tráfico normal concurrente en lectura** — `GET /api/v1/resumen`,
`GET /api/v1/centros`, `GET /api/v1/centros/{id}/necesidades`,
`GET /api/v1/sitrep.csv`, `GET /api/v1/eventos-sismicos`, con 50 usuarios
virtuales y tiempos de espera humanos (1–3s entre solicitudes) durante 60s.

**(b) Ráfagas contra los endpoints públicos de escritura** — para confirmar
que el rate limit de 10/min por IP corta exactamente donde debe, tanto en
secuencia como en concurrencia real (30 solicitudes simultáneas al mismo
endpoint, no una detrás de otra), y que nunca produce un `500` ni deja
datos a medio escribir.

**(c) Estrés progresivo** — la misma carga de lectura pero sin tiempos de
espera humanos, subiendo la concurrencia por pasos (30 → 60 → 100 → 120 →
150 usuarios virtuales) para encontrar dónde empieza a degradarse la
latencia y dónde aparece el primer error real.

Nota sobre el entorno: la máquina donde se corrieron las pruebas tenía
otros procesos en ejecución simultánea (otras sesiones de trabajo sobre
este mismo repo, en otros directorios). Eso puede introducir algo de ruido
en los números absolutos de latencia/throughput, pero **no afecta la causa
raíz del punto de quiebre encontrado** (el límite de 15 conexiones
concurrentes del pool de SQLAlchemy es una constante de configuración, no
un efecto del ruido de CPU) — si acaso, en un servidor dedicado el límite
se alcanzaría con una concurrencia igual o mayor, nunca menor.

## (a) Tráfico normal de lectura — resultado

50 usuarios virtuales, 60s, tiempos de espera humanos (1-3s):

| Endpoint | Solicitudes | Errores | p50 | p95 | p99 | máx |
|---|---:|---:|---:|---:|---:|---:|
| `GET /api/v1/resumen` | 517 | 0 | 4ms | 6ms | 22ms | 28ms |
| `GET /api/v1/centros` | 422 | 0 | 2ms | 4ms | 18ms | 21ms |
| `GET /api/v1/centros/{id}/necesidades` | 272 | 0 | 3ms | 4ms | 18ms | 19ms |
| `GET /api/v1/sitrep.csv` | 123 | 0 | 2ms | 3ms | 16ms | 19ms |
| `GET /api/v1/eventos-sismicos` | 124 | 0 | 2ms | 4ms | 11ms | 21ms |
| **Agregado** | **1458** | **0 (0%)** | **3ms** | **5ms** | **19ms** | **28ms** |

Cero errores, latencias triviales. El throughput agregado (~25 req/s) está
limitado por los tiempos de espera simulados del usuario (1-3s entre
clics), no por la capacidad del servidor — con 50 usuarios reales
navegando la vista pública, esto no es ni remotamente un problema.

## (b) Ráfagas contra endpoints con rate limit — resultado

**Ráfaga secuencial de 20 solicitudes contra `/api/v1/reportes`:**
solicitudes 1–10 → `200`, solicitudes 11–20 → `429`. Corte exacto en 10,
sin excepciones.

**Lo mismo contra `/api/v1/colectivos`:** idéntico resultado, 10 `200` y 10
`429`.

**Verificación de integridad:** tras la ráfaga, `GET /api/v1/resumen`
reportó exactamente 10 reportes y 10 colectivos pendientes — ni uno más ni
uno menos. El rate limit corta la solicitud *antes* de tocar la base de
datos, así que no hay escritura parcial ni fila corrupta.

**Ráfaga concurrente real (no secuencial)** — 30 solicitudes disparadas
*simultáneamente* (no una tras otra) contra un endpoint con rate limit
(`/api/v1/envios`, ya con la corrección aplicada, ver más abajo): 10
aceptadas (`200`), 20 rechazadas (`429`), 0 errores `500`. El límite se
sostiene también bajo concurrencia real, no solo en secuencia — no hay
condición de carrera visible que deje pasar de más (esperable: con un solo
proceso worker, la comprobación del límite corre en el mismo hilo de
evento antes de cualquier `await` a la base de datos).

**Forma de la respuesta `429`:** JSON limpio, sin información interna —
`{"error":"Rate limit exceeded: 10 per 1 minute"}` — con
`content-type: application/json`. No trae header `Retry-After`; no es un
problema funcional (el mensaje ya dice la ventana), pero sería una mejora
menor de cara a integraciones automatizadas.

## (c) Estrés progresivo — dónde está el punto de quiebre

Mismos tres endpoints de lectura, sin tiempos de espera, escalando la
concurrencia:

| Usuarios virtuales | Throughput | Errores | p50 | p95 | p99 | máx |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | ~194 req/s | 0% | 3ms | 9ms | 25ms | 70ms |
| 60 | ~380 req/s | 0% | 5ms | 21ms | 48ms | 150ms |
| 100 | ~490 req/s | 0% | 45ms | 98ms | 140ms | 270ms |
| 150 | — | **1.2%+ (crece)** | — | — | 30000ms | 30000ms |

Hasta 100 usuarios virtuales continuos (sin pausa entre solicitudes, un
patrón bastante más agresivo que cualquier tráfico humano real) el backend
no arroja ni un solo error — aunque la latencia ya empieza a subir
notoriamente entre 60 y 100 (p95 pasa de 21ms a 98ms), señal de que el
sistema se está acercando a su límite.

Entre 100 y 150 aparece el quiebre real. El log del servidor lo deja claro:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached,
connection timed out, timeout 30.00
```

**Causa raíz:** el motor de SQLAlchemy usa su configuración por defecto
para SQLite basado en archivo — un pool de 5 conexiones más 10 de
desborde, es decir **máximo 15 conexiones concurrentes a la base**. Cuando
hay más de ~15 solicitudes que necesitan tocar la base de datos al mismo
tiempo, las siguientes se quedan esperando un cupo libre; si no consiguen
uno en 30 segundos, la solicitud entera falla con `500` — sin ningún
manejo especial de este caso en el código, así que el cliente solo ve un
error genérico de servidor.

**Efecto posterior al pico, más preocupante que el pico mismo:** una vez
saturado el pool, el sistema no se recupera al instante aunque el tráfico
baje. Cada solicitud atascada puede tardar hasta 30 segundos en resolverse
(ya sea consiguiendo conexión o fallando por timeout), y mientras eso pasa
sigue sin poder atender solicitudes nuevas — durante las pruebas, el
servidor quedó sin responder *a nada, incluyendo endpoints simples como
`/api/v1/resumen`*, durante varios minutos después de un pico de ~150
usuarios concurrentes, antes de recuperarse por sí solo (sin necesidad de
reiniciar el proceso — no hubo caída ni cuelgue permanente, solo una cola
muy larga por drenar).

Este es el hallazgo más importante de toda la prueba, y el escenario más
realista dado el contexto del proyecto: no es un ataque, es lo que pasaría
si un colegio (o cualquier medio) comparte el enlace y **muchas personas
entran a la vez a ver el mapa/resumen público** — todos pegándole a
endpoints de *lectura*, que deliberadamente no tienen rate limit porque no
deberían necesitarlo. El cuello de botella no está en la lógica de la
aplicación sino en cuántas conexiones simultáneas puede sostener SQLite con
la configuración por defecto.

### Por qué no se corrigió esto en esta tarea

Es un hallazgo real pero de alcance mayor, con varias formas posibles de
abordarlo (subir `pool_size`/`max_overflow` como mitigación barata pero
parcial; mover a modo WAL de SQLite; o directamente migrar a Postgres, que
el propio `README.md` del proyecto ya señala como pendiente antes de
cualquier volumen de producción real). Cualquiera de esas opciones cambia
comportamiento de infraestructura bajo carga real, y probarla bien
requiere más que esta sesión de pruebas — así que, siguiendo el criterio de
"si el hallazgo es grande o riesgoso, no lo arregles, documéntalo", queda
acá para que se revise con calma.

**Recomendación concreta para quien lo revise:**
1. Mitigación rápida y de bajo riesgo: subir `pool_size` y `max_overflow`
   en `create_engine` (`app/database.py`) a un número más generoso (p.ej.
   20/20) — no resuelve el límite físico de SQLite para escrituras
   concurrentes, pero sí para lecturas, que es el escenario más probable de
   pico real (mucha gente mirando el mapa a la vez).
2. Mitigación estructural: activar modo WAL en SQLite
   (`PRAGMA journal_mode=WAL`), que permite lectores concurrentes sin
   bloquear sobre un único escritor.
3. Solución de fondo, ya anotada en el README: migrar a Postgres
   (`DATABASE_URL`) antes de cualquier volumen de tráfico real sostenido.
4. Si alguna vez se despliega con más de un worker/proceso (hoy
   `render.yaml` corre `uvicorn` sin `--workers`, así que es un solo
   proceso): el rate limiter de `slowapi` usa almacenamiento en memoria por
   proceso — con varios workers, cada uno llevaría su propio contador de
   10/min, multiplicando el límite real por la cantidad de workers. Hoy no
   aplica (un solo proceso), pero es una trampa a tener en cuenta si se
   cambia el `startCommand` de Render más adelante.

## Corrección aplicada: `POST /api/v1/envios` sin rate limit

Al revisar todos los endpoints públicos de escritura del sistema (los que
no requieren token JWT de un centro), se encontró que
`POST /api/v1/envios` — igual que `/reportes` y `/colectivos`, abierto a
cualquiera, sin autenticación — no tenía el decorador de límite de tasa.
Una prueba con 30 solicitudes simultáneas confirmó el problema: las 30 se
aceptaban sin ningún corte.

Se agregó el mismo límite que ya protege a los otros dos endpoints
públicos (`@limiter.limit("10/minute")`, `app/rate_limit.py`), y se sumó un
test (`test_rate_limit_envios_bloquea_tras_exceder_el_limite` en
`tests/test_main.py`) que reproduce exactamente el mismo patrón que ya
existía para `/reportes` y `/colectivos`. Se repitió la prueba de ráfaga
concurrente tras el cambio: de 30 solicitudes simultáneas, 10 aceptadas y
20 rechazadas con `429`, cero errores `500`.

Este endpoint es de menor riesgo que los otros dos porque requiere un
`centro_id` válido (falla con `404` si no existe), pero sigue siendo una
tabla que cualquiera en internet puede llenar de filas basura sin límite
— exactamente el mismo riesgo que ya se había identificado y mitigado para
reportes y colectivos, solo que faltó aplicarlo acá también.

## Suite de tests existente

Se corrió `pytest -q` completo después de todos los cambios: **82 tests
pasan**, 0 fallos (81 preexistentes + el nuevo test del rate limit de
envíos).

## Conclusión

Para el tráfico esperado en el corto plazo (visitantes curiosos viendo el
panorama público, algunos reportes y registros de colectivos genuinos), el
sistema responde bien: rate limiting correcto y sin fugas en los
endpoints de escritura pública, latencias de un dígito de milisegundos en
lectura normal, y capacidad holgada hasta unos 100 usuarios concurrentes
sostenidos sin pausa (mucho más agresivo que navegación humana real). El
riesgo real no es abuso malicioso — eso ya está cubierto — sino un pico
genuino de visitas simultáneas (por ejemplo, si el anuncio del colegio se
viraliza) saturando las ~15 conexiones que SQLite permite por defecto. Vale
la pena resolver esto (aunque sea con la mitigación rápida del punto 1)
antes de que ese pico llegue de verdad.
