# Ayuda Terremoto Colombia

Sistema de coordinación de ayuda humanitaria construido tras el terremoto de
magnitud 7.4 que sacudió el occidente de Colombia el 10 de agosto de 2026
(epicentro en San José del Palmar, Chocó, con Pereira como la ciudad más
golpeada). Es un evento real, declarado desastre nacional por el gobierno
colombiano — ver [Terremoto de Colombia de 2026 en Wikipedia](https://es.wikipedia.org/wiki/Terremoto_de_Colombia_de_2026).

El problema que ataca no es falta de organizaciones ni de dinero para
donar — es **fragmentación de canales**. Cruz Roja, ABACO, Bancos de
Alimentos, la Alcaldía y UNGRD ya operan, pero sin interoperar entre sí. Este
proyecto es una capa de agregación: ingiere reportes ciudadanos y necesidades
de terreno, y los expone en formatos que las instituciones grandes sí pueden
consumir.

**Este proyecto no maneja donaciones ni pagos**, por decisión deliberada de
diseño. Para donar dinero, usa únicamente los canales oficiales ya
establecidos: Cruz Roja Colombiana, ABACO (corredor humanitario), Banco de
Alimentos de Bogotá, o la llave Bre-B publicada directamente por esas
entidades. Ninguna entidad legítima cobra por registrar a alguien como
voluntario, damnificado o para un subsidio — ver la nota de seguridad en
`planoidea.md` §9 sobre estafas activas confirmadas durante esta emergencia.

## Contenido de este repositorio

- **[`planoidea.md`](planoidea.md)** — el documento de arquitectura completo:
  contexto real de la emergencia, ecosistema de actores existentes, diagrama
  UML, especificación de API, stack recomendado y notas de resiliencia y
  confianza.
- **[`pereira-ayuda-backend/`](pereira-ayuda-backend/)** — MVP funcional
  acotado a una sola ciudad (Pereira): conecta solicitudes ciudadanas con
  colectivos verificados, con clasificación por IA gratuita y actualizaciones
  en tiempo real.
- **[`sistema-ayuda-nacional/`](sistema-ayuda-nacional/)** — el Nodo Central
  de la arquitectura nacional multi-departamento: reportes vía WhatsApp y
  Ushahidi, auto-activación real por sismos (USGS), export HXL para la
  comunidad humanitaria internacional. Ver su README para el detalle de qué
  integraciones son reales y cuáles corren en modo sandbox.
- **[`nodo-local/`](nodo-local/)** — app offline-first (React/Vite +
  IndexedDB) para que un centro territorial registre reportes y entregas sin
  conexión y sincronice todo apenas vuelva la señal. Habla con
  `sistema-ayuda-nacional/`.
- **`docs/superpowers/`** — specs de diseño y planes de implementación, para
  quien quiera entender las decisiones de alcance (por ejemplo, por qué no
  hay manejo de pagos, o qué queda fuera de esta versión).

## Qué falta (honesto)

Capas geoespaciales WMS/WFS reales compatibles con ICDE/SNIGRD — requieren un
GeoServer y una instancia PostGIS en vivo conectada a datos oficiales, que es
infraestructura de despliegue, no solo código. `sistema-ayuda-nacional/` usa
lat/lon simples mientras tanto, suficiente para el pipeline y los exports.

## Cómo contribuir

Cada subproyecto tiene su propio README con instrucciones para levantarlo en
local y correr sus tests. Si vas a desplegar cualquiera de los dos backends
para una emergencia real, revisa primero las notas de "próximos pasos
honestos" en su README — hay datos (contactos, canales) que deben
reverificarse antes de mostrarse a nadie más.

## Licencia

MIT — ver [`LICENSE`](LICENSE). Úsalo, adáptalo, despliégalo donde haga
falta.
