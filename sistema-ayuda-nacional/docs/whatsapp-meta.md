# WhatsApp Business Cloud API: qué falta y qué ya está

El canal de WhatsApp es el que más importa en esta emergencia — es lo que la
gente ya tiene instalado y lo que sabe usar sin que nadie le explique. Hoy
corre en **modo sandbox**: el código para recibir mensajes reales está
completo, lo que falta es un trámite con Meta que este proyecto no puede
hacer solo.

Este documento existe para que quien pueda hacerlo no tenga que averiguar
qué hace falta.

## Lo que ya está hecho (no requiere cambios)

| Pieza | Dónde | Estado |
|---|---|---|
| Parseo del formato real de Meta Graph API | `app/integrations/whatsapp.py` | Listo — mensajes de texto y de ubicación |
| Validación de firma `X-Hub-Signature-256` | `auth.validar_firma_whatsapp` | Listo — HMAC-SHA256 con comparación en tiempo constante |
| Webhook | `POST /api/v1/webhooks/whatsapp` | Listo |
| Clasificación y detección de duplicados del mensaje entrante | `ai_helper.py`, `dedup.py` | Listo |
| Protección del número de quien escribe | `schemas.ReporteCiudadanoOut` | El teléfono se guarda pero la API pública nunca lo devuelve |
| Pruebas sin cuenta Meta | `POST /sandbox/whatsapp/simular` | Listo |

Mientras no exista `WHATSAPP_APP_SECRET` en el entorno, el webhook **no
exige firma**: es modo desarrollo. Poner esa variable activa la validación
real, y ese es el único cambio de código necesario — no hay ninguno.

## Lo que falta: el trámite

Meta exige una **entidad legal registrada** con documentación verificable.
Este es un proyecto de código abierto sin una organización detrás, y por eso
el issue [#8](https://github.com/Julian-Rincon/ayuda-terremoto-colombia/issues/8)
queda abierto: lo natural es que lo complete una organización humanitaria que
ya tenga cuenta de Business Manager verificada.

Los pasos, en orden:

1. **Business Manager.** Crear (o usar uno existente) en
   <https://business.facebook.com>.
2. **Verificación de negocio.** Subir documentación legal de la organización:
   certificado de existencia, NIT, dirección verificable. Meta tarda entre
   días y semanas, y puede pedir correcciones. Es el paso largo.
3. **App de tipo Business** en <https://developers.facebook.com> y agregarle
   el producto *WhatsApp*.
4. **Número de teléfono.** Uno que no esté registrado en WhatsApp normal ni
   en WhatsApp Business. Si el número ya se usa, hay que darlo de baja antes
   — conviene conseguir uno nuevo para esto.
5. **Configurar el webhook** en la app: URL
   `https://<tu-despliegue>/api/v1/webhooks/whatsapp`, y suscribirse al campo
   `messages`. Meta hace un `GET` de verificación con `hub.challenge`.
6. **Copiar el App Secret** de la app a la variable `WHATSAPP_APP_SECRET` del
   despliegue. Desde ese momento el webhook exige firma válida.

## Verificarlo

```bash
# Sin WHATSAPP_APP_SECRET: cualquier payload entra (modo sandbox)
curl -X POST localhost:8000/sandbox/whatsapp/simular \
  -H 'Content-Type: application/json' \
  -d '{"remitente": "573001112233", "texto": "Necesitamos agua en el barrio"}'

# El reporte aparece en la cola de verificación, sin el teléfono
curl -s "localhost:8000/api/v1/reportes?canal=whatsapp"
```

Con `WHATSAPP_APP_SECRET` puesto, un POST al webhook sin la cabecera
`X-Hub-Signature-256` correcta debe ser rechazado. Eso lo cubren las pruebas
en `tests/test_whatsapp.py` y `tests/test_auth.py`.

## Antes de encenderlo de verdad

- El número queda asociado a una organización real y la gente le va a
  escribir esperando respuesta. Encenderlo sin alguien atendiendo la cola de
  verificación es peor que no tenerlo.
- Meta impone ventanas de 24 horas para responder fuera de plantillas
  aprobadas. Si se piensa responder automáticamente, las plantillas hay que
  aprobarlas antes.
- Los mensajes entrantes traen datos personales. Ver
  [SECURITY.md](../../SECURITY.md) antes de pegar cualquier payload real en
  un issue o un log.
