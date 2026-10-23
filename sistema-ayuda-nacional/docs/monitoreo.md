# Monitoreo y alertas

El sistema solo sirve si está arriba cuando alguien lo necesita, y nadie se va
a dar cuenta de que se cayó mirando el dashboard — hay que enterarse sin
mirar.

## El endpoint: `GET /salud`

```bash
curl https://ayuda-terremoto-nacional.onrender.com/salud
```

```json
{"estado": "ok", "base_de_datos": "ok", "version": "0.1.0", "segundos_activo": 1842}
```

Consulta la base antes de responder. Si la base no contesta devuelve **503**
con `{"detail": {"estado": "degradado", "base_de_datos": "sin conexión", ...}}`
(el cuerpo va dentro de `detail`, como todos los errores de FastAPI). Esa
diferencia entre 200 y 503 es la razón de
que exista: un monitor apuntado a `/` vería 200 aunque la base esté muerta y
la app no pueda hacer absolutamente nada útil.

`segundos_activo` delata los reinicios: si baja a cero entre dos chequeos, el
proceso se reinició — en el tier gratuito de Render eso es normal (duerme por
inactividad), en un plan pago no lo es.

## Capas de monitoreo

### 1. Render (ya configurado)

`render.yaml` declara `healthCheckPath: /salud`. Render consulta ese endpoint
al desplegar y no da por bueno un despliegue que no responda 200 — así una
migración que rompe la conexión a la base no llega a reemplazar la versión que
estaba funcionando.

### 2. GitHub Actions (ya configurado, gratis)

[`.github/workflows/monitoreo.yml`](../../.github/workflows/monitoreo.yml)
consulta `/salud` cada 6 horas. Si falla, el workflow falla y GitHub manda
correo a quien mantiene el repositorio.

Es el piso, no el techo: cada 6 horas significa que una caída puede pasar
desapercibida casi un día. Sirve para "el despliegue murió en silencio la
semana pasada", no para una emergencia en curso.

Para apuntarlo a otro despliegue, definir la variable de repositorio `API_URL`
(Settings → Secrets and variables → Actions → Variables).

### 3. Monitor externo (recomendado para una emergencia activa)

Cualquiera de estos tiene plan gratuito suficiente:

| Servicio | Plan gratis | Alerta a |
|---|---|---|
| [UptimeRobot](https://uptimerobot.com) | 50 monitores, cada 5 min | correo, Telegram, webhook |
| [Better Stack](https://betterstack.com/uptime) | 10 monitores, cada 3 min | correo, SMS, Slack |
| [Healthchecks.io](https://healthchecks.io) | 20 chequeos | correo, Telegram, webhook |

Configuración recomendada:

- **URL:** `https://<tu-despliegue>/salud`
- **Intervalo:** 5 minutos
- **Espera:** código 200 **y** que el cuerpo contenga `"estado": "ok"`.
  Verificar solo el código deja pasar el caso degradado.
- **Timeout:** 60 s si está en el tier gratuito de Render (el primer request
  despierta el proceso dormido); 10 s en un plan pago.
- **Confirmación:** alertar al segundo fallo seguido, no al primero. Con el
  despertar del tier gratuito, alertar al primero genera falsas alarmas y en
  dos días nadie mira las notificaciones.

### Qué más vale la pena vigilar

Más allá de "responde o no responde":

- **`/api/v1/eventos-sismicos/ultimo` sin datos nuevos en 24 h.** El loop de
  USGS corre en segundo plano; si muere, la app sigue respondiendo 200 y el
  sistema deja de enterarse de las réplicas sin que nadie lo note.
- **`segundos_activo` reiniciándose seguido** en un plan pago: señal de que el
  proceso se está cayendo y levantando.
- **`/api/v1/resumen` con `reportes_pendientes_verificacion` creciendo sin
  parar:** no es una caída técnica, es que no hay nadie verificando. Importa
  igual.

## Verificarlo en local

```bash
docker compose up -d
curl -s localhost:8000/salud

# Simular la base caída: el endpoint debe responder 503
docker compose stop base-de-datos
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/salud
docker compose start base-de-datos
```
