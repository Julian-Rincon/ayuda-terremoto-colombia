// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ListaMapaAccesible from './ListaMapaAccesible.jsx'

afterEach(() => {
  cleanup()
})

const CENTRO_ACTIVO = {
  id: 1, nombre: 'Chocó', departamento: 'Chocó', activo: true,
  totalPendientes: 3, contacto_verificado: false, contacto: null, lat: 5.6, lon: -76.6,
}

const CENTRO_DORMIDO = {
  id: 2, nombre: 'Santander', departamento: 'Santander', activo: false,
  totalPendientes: null, contacto_verificado: false, contacto: null, lat: 7.1, lon: -73.1,
}

describe('ListaMapaAccesible', () => {
  it('no muestra botón de activar para un centro ya activo', () => {
    render(
      <ListaMapaAccesible
        centros={[CENTRO_ACTIVO]}
        reportes={[]}
        sismos={[]}
        onSeleccionar={vi.fn()}
        onActivar={vi.fn()}
        activandoId={null}
      />,
    )
    expect(screen.queryByRole('button', { name: /activar/i })).not.toBeInTheDocument()
  })

  it('muestra botón de activar para un centro dormido y lo llama con su id', async () => {
    const onActivar = vi.fn()
    const usuario = userEvent.setup()
    render(
      <ListaMapaAccesible
        centros={[CENTRO_DORMIDO]}
        reportes={[]}
        sismos={[]}
        onSeleccionar={vi.fn()}
        onActivar={onActivar}
        activandoId={null}
      />,
    )

    const boton = screen.getByRole('button', { name: /activar santander a mano/i })
    await usuario.click(boton)
    expect(onActivar).toHaveBeenCalledWith(2)
  })

  it('deshabilita el botón y muestra "Activando…" mientras esa zona está en curso', () => {
    render(
      <ListaMapaAccesible
        centros={[CENTRO_DORMIDO]}
        reportes={[]}
        sismos={[]}
        onSeleccionar={vi.fn()}
        onActivar={vi.fn()}
        activandoId={2}
      />,
    )
    const boton = screen.getByRole('button', { name: /activando/i })
    expect(boton).toBeDisabled()
  })

  it('el botón de seleccionar en el mapa sigue funcionando junto al de activar', async () => {
    const onSeleccionar = vi.fn()
    const usuario = userEvent.setup()
    render(
      <ListaMapaAccesible
        centros={[CENTRO_DORMIDO]}
        reportes={[]}
        sismos={[]}
        onSeleccionar={onSeleccionar}
        onActivar={vi.fn()}
        activandoId={null}
      />,
    )
    await usuario.click(screen.getByRole('button', { name: /Santander — Santander/i }))
    expect(onSeleccionar).toHaveBeenCalledWith('centro-2', [7.1, -73.1])
  })

  it('sin onActivar no revienta y no muestra el botón (uso defensivo)', () => {
    render(
      <ListaMapaAccesible centros={[CENTRO_DORMIDO]} reportes={[]} sismos={[]} onSeleccionar={vi.fn()} />,
    )
    expect(screen.queryByRole('button', { name: /activar/i })).not.toBeInTheDocument()
  })
})
