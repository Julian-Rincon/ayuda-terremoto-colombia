# Plan B de base de datos: migrar de Render Postgres a Neon

## Por qué

La base de datos actual en producción (`ayuda-terremoto-db`, creada por el
blueprint de Render el 26 de agosto de 2026) está en el plan gratis de
Render, que **expira 30 días después de creada** — se borra sola el **25 de
septiembre de 2026** si no se hace nada antes.

[Neon](https://neon.tech) ofrece Postgres real (100% compatible, mismo
motor) con un plan gratis que **no expira nunca**: no es una prueba con
fecha límite. Si el proyecto queda sin uso, Neon solo apaga el cómputo
(se reactiva solo en un par de cientos de milisegundos cuando alguien
vuelve a usarlo) — nunca borra el proyecto ni los datos. No pide tarjeta.
Límite: 0.5 GB de almacenamiento por proyecto, de sobra para este sistema
(todo el contenido es texto — reportes, centros, colectivos — sin archivos
ni imágenes).

Fuente verificada directamente en la documentación oficial de Neon el 26 de
agosto de 2026 (no en blogs de terceros), justo para no repetir la sorpresa
que tuvimos con el límite de Render.

## Pasos

### 1. Crear la cuenta y el proyecto en Neon (~2 minutos, sin tarjeta)

1. Entra a [neon.tech](https://neon.tech) y regístrate con GitHub o Google.
2. Al crear el primer proyecto, ponle un nombre (ej. `ayuda-terremoto`) y
   elegí una región cercana (`us-east` o similar — no es crítico, la
   latencia extra es mínima para este uso).
3. Neon te muestra una **connection string** que empieza con
   `postgresql://...` — cópiala completa. Esa es la única credencial que
   necesitas.

### 2. Pasarme la connection string

Cuando la tengas, compartímela (en el chat está bien, o si preferís más
cuidado, guardala en un archivo y decime la ruta). Con eso yo hago:

- Actualizar `render.yaml`: cambiar `DATABASE_URL` de `fromDatabase`
  (apuntando a la base de Render) a `sync: false` (secreto manual, mismo
  patrón que ya usa `GROQ_API_KEY`), y quitar el bloque `databases:` que
  ya no hace falta.
- Configurar `DATABASE_URL` en el servicio backend de Render (vía la API,
  con la connection string de Neon) para que apunte a la base nueva.
- Disparar un redeploy y confirmar en vivo que el backend arranca bien,
  siembra los 33 departamentos, y responde correctamente — igual que se
  verificó hoy con la base de Render.
- Actualizar este documento y el README del backend para reflejar el
  cambio.

### 3. Qué pasa con la base vieja de Render

No hace falta borrarla a mano — se va a borrar sola el 25 de septiembre de
2026 por su propia política de expiración. Una vez migrado a Neon, esa
fecha deja de importar.

## Nota sobre respaldo (más allá de "cuál base uso")

Migrar a Neon resuelve "que no se caiga por expirar", pero no reemplaza un
respaldo real de los datos (reportes, centros verificados, etc.) si algo
sale mal en cualquiera de los dos proveedores. Si en el futuro hay tiempo,
vale la pena automatizar un `pg_dump` periódico (ej. una GitHub Action
semanal) que guarde una copia — no es urgente mientras el sistema tenga
poco tráfico, pero si empieza a haber coordinadores reales dependiendo de
los datos, conviene no dejarlo para después.
