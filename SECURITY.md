# Política de seguridad

Este proyecto coordina ayuda humanitaria después del terremoto del 10 de
agosto de 2026. Lo que guarda no son filas de una base cualquiera: son
reportes de personas que están pidiendo auxilio y contactos de gente que está
ayudando. Un fallo de autorización acá no es solo un bug.

## Reportar una vulnerabilidad

**No abras un issue público.** Un issue con los pasos para reproducir deja el
hueco abierto y documentado para cualquiera mientras se arregla.

Usá uno de estos dos canales privados:

1. **GitHub Security Advisories** (preferido) — pestaña *Security* del
   repositorio → *Report a vulnerability*. Queda privado entre vos y quienes
   mantienen el proyecto hasta que haya arreglo.
2. **Correo** a <julianer2002@gmail.com> con el asunto
   `[SEGURIDAD] ayuda-terremoto-colombia`.

Qué ayuda incluir: qué encontraste, cómo reproducirlo, qué se puede hacer con
eso, y la versión o el commit donde lo viste. No hace falta un exploit
pulido — una descripción clara sirve.

### Tiempos

Este es un proyecto de código abierto sin equipo de guardia. Los plazos son
compromisos de buena fe, no un SLA contratado:

| Qué | Cuándo |
|---|---|
| Acuse de recibo | 72 horas |
| Evaluación inicial y severidad | 7 días |
| Arreglo de algo crítico (exposición de datos personales, acceso sin auth) | lo antes posible, con prioridad sobre cualquier feature |
| Divulgación pública | después del arreglo, acordando el momento con quien reportó |

Si en 7 días no hubo respuesta, insistí — no es desinterés, es que somos
pocos.

## Qué cuenta como vulnerabilidad acá

Sí, reportalo:

- Acceso a endpoints de coordinador sin token válido, o con el token de otro
  centro (`centro_id` cruzado).
- Cualquier cosa que exponga reportes ciudadanos sin verificar, coordenadas,
  o contactos que no sean públicos.
- Inyección (SQL, comandos, plantillas), XSS en el portal público, SSRF en
  las integraciones salientes (USGS, Ushahidi, WhatsApp).
- Falsificación de webhooks: hacer que el sistema acepte un mensaje como si
  viniera de Meta sin la firma correcta.
- Secretos filtrados en el repositorio o en los artefactos de build.
- Saltarse el rate limiting de forma que permita inundar la cola de reportes
  — en una emergencia, llenar el sistema de ruido es un ataque real.
- Poder inyectar un canal de donación o un contacto falso en algo que se le
  muestre a la gente como verificado.

No hace falta reportarlo (ya lo sabemos y es deliberado):

- Que los secretos de `.env.example` sean valores de ejemplo. La app **se
  niega a arrancar** con `ENVIRONMENT=production` si no se rotaron
  (`app/config_checks.py`).
- Que el despliegue de demo en Render tarde ~30-50 s en despertar: es el tier
  gratuito.
- Que el endpoint `/sandbox/whatsapp/simular` exista: es para desarrollo y no
  debe estar expuesto en un despliegue real.
- Que los datos sembrados (`seed_data.py`) sean de ejemplo y los contactos
  estén marcados como *sin verificar*.
- Reportes automáticos de escáneres sin un impacto demostrado.

## Datos personales

### Qué se almacena

| Dato | Dónde | Nota |
|---|---|---|
| Texto libre del reporte ciudadano | `reportes_ciudadanos.contenido_original` | Puede contener nombres, direcciones o teléfonos que la persona escribió |
| Coordenadas y zona del reporte | `reportes_ciudadanos.lat/lon/zona` | Opcional |
| Identificador del mensaje de origen | `reportes_ciudadanos.id_externo` | Para WhatsApp **es el número de quien escribió**. Se guarda para poder rastrear el reporte, pero la API pública nunca lo devuelve (`ReporteCiudadanoOut` lo anula para ese canal). Para Ushahidi es el id del post, que ya es público |
| Nombre, zona y contacto de un colectivo | `colectivos` | Se registra en público, pero sigue siendo un dato de contacto real |
| Contacto de un centro territorial | `centros_locales.contacto` | Se muestra solo si `contacto_verificado` |
| Hash del secreto de cada nodo | `nodo_credenciales.secreto_hash` | bcrypt; el secreto en claro no se guarda nunca |

**No se almacenan**: documentos de identidad, datos bancarios, ni información
de pagos. Ver la sección siguiente.

### Qué nunca debe salir del sistema

Al abrir un issue, pegar un log o adjuntar una captura en un PR:

- **Nunca** pegues el contenido real de un reporte ciudadano. Si necesitás un
  ejemplo, inventá uno o usá los de `seed_data.py`.
- **Nunca** incluyas coordenadas reales de un reporte sin verificar. Una
  ubicación con un pedido de auxilio identifica a una persona vulnerable.
- **Nunca** subas un volcado de la base, ni siquiera "para depurar".
- Censurá teléfonos y nombres en las capturas del panel de coordinador.
- No pegues tokens JWT, aunque creas que ya expiraron.

La capa `capa_reportes_verificados` de GeoServer existe justamente por esto:
publica solo lo verificado, y aun así exponerla hacia afuera es una decisión
de la coordinación, no una opción técnica por defecto
([guía geoespacial](sistema-ayuda-nacional/docs/geoserver-postgis.md)).

### Minimización

El sistema pide lo mínimo para coordinar: qué se necesita y dónde. No pide
cédula, no pide edad, no pide composición del hogar. Cualquier PR que agregue
un campo de dato personal nuevo tiene que justificar en la descripción por
qué la coordinación es imposible sin él.

## Este proyecto no maneja dinero — por diseño

No hay pasarela de pago, no hay recaudo, no hay cuentas, no hay llaves Bre-B
propias. Es una decisión de diseño, no una funcionalidad pendiente.

**Cualquier PR que introduzca un flujo de dinero se rechaza**, sin importar
qué tan bien esté implementado: pasarelas, recaudo de donaciones, criptomonedas,
enlaces de pago, códigos QR de transferencia, o un campo "cuenta para donar"
en cualquier formulario.

El motivo es la razón por la que el sistema existe. Durante esta emergencia
circularon campañas falsas de donación suplantando organizaciones reales
(`planoidea.md` §9). Un sistema de coordinación que además pide plata es
indistinguible de esas campañas, y le presta credibilidad a quien quiera
copiarlo. Para donar, los canales oficiales ya existentes: Cruz Roja
Colombiana, ABACO, Bancos de Alimentos, o la llave Bre-B que publique
directamente cada entidad.

Por la misma razón se tratan como vulnerabilidad, no como spam, los intentos
de inyectar contactos o canales de donación falsos en datos que el portal
muestre como verificados.

## Versiones con soporte

El proyecto no publica versiones etiquetadas todavía. Lo que se mantiene es la
rama `main`; los arreglos de seguridad entran ahí y se despliegan a la demo.
