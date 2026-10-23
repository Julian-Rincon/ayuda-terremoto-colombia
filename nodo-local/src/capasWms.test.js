import { describe, expect, it } from 'vitest'
import { parsearCapasWms } from './capasWms.js'

describe('parsearCapasWms', () => {
  it('sin URL de WMS no ofrece ninguna capa — el mapa funciona solo con OSM', () => {
    expect(parsearCapasWms('', 'ayuda:capa_centros:Centros')).toEqual([])
    expect(parsearCapasWms(undefined, undefined)).toEqual([])
  })

  it('usa la capa de centros por defecto cuando hay URL pero no lista', () => {
    const capas = parsearCapasWms('http://localhost:8080/geoserver/ayuda/wms', '')
    expect(capas).toHaveLength(1)
    expect(capas[0].nombre).toBe('ayuda:capa_centros')
  })

  it('separa espacio:capa de la etiqueta visible', () => {
    const [capa] = parsearCapasWms('http://geo', 'ayuda:capa_eventos_sismicos:Sismos 30 días')
    expect(capa.nombre).toBe('ayuda:capa_eventos_sismicos')
    expect(capa.etiqueta).toBe('Sismos 30 días')
  })

  it('cae al nombre técnico si no se dio etiqueta', () => {
    const [capa] = parsearCapasWms('http://geo', 'ayuda:capa_centros')
    expect(capa.etiqueta).toBe('ayuda:capa_centros')
  })

  it('admite varias capas e ignora entradas vacías', () => {
    const capas = parsearCapasWms('http://geo', 'ayuda:capa_centros:Centros, ,ayuda:capa_reportes_verificados:Reportes')
    expect(capas.map((c) => c.nombre)).toEqual(['ayuda:capa_centros', 'ayuda:capa_reportes_verificados'])
  })

  it('ninguna capa arranca encendida', () => {
    const capas = parsearCapasWms('http://geo', 'ayuda:capa_centros:Centros,ayuda:capa_eventos_sismicos:Sismos')
    expect(capas.every((c) => c.visible === false)).toBe(true)
  })
})
