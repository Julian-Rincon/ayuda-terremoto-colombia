# Conectar tu propio número de WhatsApp

WhatsApp es el canal que más importa en una emergencia: es lo que la gente ya
tiene instalado y sabe usar sin que nadie le explique.

Este despliegue **no trae un número conectado y no lo va a traer**. La cuenta
de WhatsApp Business queda a nombre de una organización concreta, y quien
levante este sistema tiene que conectar el suyo. Esta guía es para eso: todo
el código del lado del servidor ya está, y la conexión se hace con variables
de entorno, sin tocar una línea.

Mientras no conectes nada, el canal corre en **modo sandbox** y se prueba
entero con `POST /sandbox/whatsapp/simular`. El sistema funciona completo sin
WhatsApp — por web, por Ushahidi y por carga manual.

## Lo que ya está del lado del servidor

| Pieza | Dónde |
|---|---|
| Handshake de verificación que Meta exige (`GET` con `hub.challenge`) | `GET /api/v1/webhooks/whatsapp` |
| Recepción de mensajes, con validación de firma `X-Hub-Signature-256` | `POST /api/v1/webhooks/whatsapp` |
| Parseo del formato real de la Graph API: texto y ubicación | `app/integrations/whatsapp.py` |
| Clasificación, detección de duplicados y entrada a la cola de verificación | `ai_helper.py`, `dedup.py` |
| Acuse de recibo a quien escribe (opcional) | `whatsapp.enviar_acuse_de_recibo` |
| El teléfono de quien reporta nunca sale por la API pública | `schemas.ReporteCiudadanoOut` |
| Aviso en el log si la configuración quedó a medias | `config_checks.py` |

## Las cuatro variables

```bash
WHATSAPP_VERIFY_TOKEN=      # 1. la elegís vos — sin esto no se conecta nada
WHATSAPP_APP_SECRET=        # 2. de tu app en Meta — sin esto no se valida la firma
WHATSAPP_TOKEN=             # 3. opcional: para responder
WHATSAPP_PHONE_NUMBER_ID=   # 4. opcional: para responder
```

Comprobá en cualquier momento cómo quedó, sin leer logs ni exponer secretos:

```bash
curl -s https://<tu-despliegue>/api/v1/config/integraciones
```

```json
{
  "whatsapp": {
    "modo": "real",
    "verificacion_de_webhook": true,
    "validacion_de_firma": true,
    "responde_acuse_de_recibo": false
  },
  "ushahidi": "sandbox (fixture)",
  "clasificacion_ia": "reglas locales",
  "usgs": "real",
  "entorno": "production"
}
```

## Paso a paso

### 1. Cuenta de Meta y verificación de negocio

En <https://business.facebook.com>, creá un Business Manager (o usá el de tu
organización) y pasá la **verificación de negocio**: Meta pide documentación
legal de la entidad — certificado de existencia, NIT, dirección verificable.

Es el paso largo: tarda entre días y semanas, y Meta puede pedir
correcciones. Es también el único que no depende de vos ni de este código.
Si tu organización ya tiene Business Manager verificado, ya lo pasaste.

### 2. App y número

1. En <https://developers.facebook.com>, creá una app de tipo **Business** y
   agregale el producto **WhatsApp**.
2. Registrá un número de teléfono. **Tiene que ser un número que no esté ya
   registrado en WhatsApp ni en WhatsApp Business** — si lo está, hay que
   darlo de baja primero. Lo más simple es conseguir uno nuevo para esto.

### 3. Elegí tu token de verificación

Es una cadena que inventás vos; no viene de Meta. Sirve para que el servidor
sepa que quien está conectando el webhook sos vos:

```bash
openssl rand -hex 32
```

Ponela en `WHATSAPP_VERIFY_TOKEN` en tu despliegue y **reiniciá el servicio**
antes de seguir. Si no está configurada, el endpoint de verificación responde
`503` diciendo exactamente eso — no acepta a ciegas, a propósito: un webhook
que acepta cualquier token deja que un tercero conecte su app de Meta a tu
despliegue y le inyecte reportes falsos a la cola de verificación.

Probá que responde antes de ir al panel de Meta:

```bash
curl "https://<tu-despliegue>/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=<tu-token>&hub.challenge=prueba123"
# debe imprimir exactamente: prueba123
```

Si imprime `prueba123`, el panel de Meta va a poder guardar la URL. Si
responde 403, el token que mandaste no coincide con el del entorno.

### 4. Configurá el webhook en Meta

En la app → WhatsApp → Configuration:

- **Callback URL:** `https://<tu-despliegue>/api/v1/webhooks/whatsapp`
- **Verify token:** la misma cadena del paso 3
- **Webhook fields:** suscribite a `messages`

Meta hace el GET de verificación al guardar. Si el paso 3 funcionó, pasa.

> La URL tiene que ser **HTTPS y pública**. Para probar desde tu máquina,
> `ngrok http 8000` o similar, y usá la URL que te dé.

### 5. Activá la validación de firma

Copiá el **App Secret** (Settings → Basic de tu app) a `WHATSAPP_APP_SECRET`
y reiniciá. Desde ese momento el webhook rechaza con 401 cualquier payload
que no venga firmado por Meta.

**Hacé este paso.** Sin él el webhook acepta lo que sea de quien sea: con la
URL a la vista, cualquiera puede llenar la cola de verificación de basura
justo cuando el equipo necesita leerla. El sistema te lo advierte en el log
al arrancar si dejaste el verify token puesto y este no.

### 6. Opcional: que conteste un acuse de recibo

Con `WHATSAPP_TOKEN` (el token de acceso de la app) y
`WHATSAPP_PHONE_NUMBER_ID` (el id del número, no el número), el sistema
responde a quien escribe:

> Recibimos tu reporte y queda en la cola de verificación. Este canal NO
> gestiona dinero ni donaciones: si alguien te pide un pago a nombre de esta
> ayuda, es una estafa.

Ese segundo renglón no es relleno. Recibir una respuesta desde un número
institucional es exactamente el momento en que una estafa suplantaría este
canal; decirlo ahí es lo más barato que se puede hacer al respecto.

El acuse va en segundo plano y **nunca** rompe la ingesta: si Meta no
contesta, el reporte ya quedó guardado igual.

## Probarlo de punta a punta

```bash
# 1. ¿Cómo quedó la configuración?
curl -s https://<tu-despliegue>/api/v1/config/integraciones

# 2. Escribile al número desde tu propio WhatsApp:
#    "Necesitamos agua en el barrio tal"

# 3. El reporte tiene que aparecer en la cola de verificación,
#    sin tu número de teléfono
curl -s "https://<tu-despliegue>/api/v1/reportes?canal=whatsapp&verificado=false"
```

Si el mensaje no aparece: revisá en Meta → WhatsApp → Configuration que la
suscripción a `messages` esté activa, y los logs del servicio (un 401 ahí
significa firma inválida; un payload que llega pero no se procesa suele ser
un tipo de mensaje no soportado — hoy se ingesta texto y ubicación).

## Antes de encenderlo de verdad

- **Tiene que haber alguien atendiendo la cola de verificación.** Un número
  publicado al que la gente le escribe pidiendo ayuda y nadie lee es peor que
  no tener el canal: genera una expectativa que no se cumple.
- **Ventana de 24 horas.** Meta solo deja responder libremente dentro de las
  24 h del último mensaje de la persona. Fuera de eso hacen falta plantillas
  aprobadas por Meta, que hay que registrar antes.
- **Los mensajes traen datos personales.** Antes de pegar un payload real en
  un issue, un log o una captura, leé [SECURITY.md](../../SECURITY.md).
- **Este canal no maneja dinero**, igual que el resto del sistema. Si alguien
  pide una transferencia a nombre de esta ayuda, es una estafa — y el acuse
  de recibo lo dice.
