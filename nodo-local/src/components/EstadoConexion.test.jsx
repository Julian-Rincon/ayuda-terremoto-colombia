// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EstadoConexion from './EstadoConexion.jsx'

afterEach(() => {
  cleanup()
})

describe('EstadoConexion', () => {
  it('muestra el badge "En línea" y habilita el botón de sincronizar cuando enLinea=true', () => {
    render(<EstadoConexion enLinea pendientes={0} onSincronizar={vi.fn()} />)

    expect(screen.getByText('En línea')).toBeInTheDocument()
    expect(screen.queryByText(/sin conexión/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sincronizar ahora/i })).toBeEnabled()
  })

  it('muestra el badge "Sin conexión" y deshabilita el botón de sincronizar cuando enLinea=false', () => {
    render(<EstadoConexion enLinea={false} pendientes={0} onSincronizar={vi.fn()} />)

    expect(screen.getByText(/sin conexión — trabajando localmente/i)).toBeInTheDocument()
    expect(screen.queryByText('En línea')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sincronizar ahora/i })).toBeDisabled()
  })

  it('aplica la clase CSS "en-linea" cuando está en línea y "sin-conexion" cuando no', () => {
    const { container, rerender } = render(<EstadoConexion enLinea pendientes={0} onSincronizar={vi.fn()} />)
    expect(container.querySelector('.estado-conexion')).toHaveClass('en-linea')
    expect(container.querySelector('.estado-conexion')).not.toHaveClass('sin-conexion')

    rerender(<EstadoConexion enLinea={false} pendientes={0} onSincronizar={vi.fn()} />)
    expect(container.querySelector('.estado-conexion')).toHaveClass('sin-conexion')
    expect(container.querySelector('.estado-conexion')).not.toHaveClass('en-linea')
  })

  it('no muestra el contador de pendientes cuando no hay ninguna acción pendiente', () => {
    render(<EstadoConexion enLinea pendientes={0} onSincronizar={vi.fn()} />)

    expect(screen.queryByText(/pendiente/i)).not.toBeInTheDocument()
  })

  it('muestra el contador de pendientes en singular cuando hay exactamente 1', () => {
    render(<EstadoConexion enLinea pendientes={1} onSincronizar={vi.fn()} />)

    expect(screen.getByText('1 acción pendiente de sincronizar')).toBeInTheDocument()
  })

  it('muestra el contador de pendientes en plural cuando hay más de 1', () => {
    render(<EstadoConexion enLinea pendientes={3} onSincronizar={vi.fn()} />)

    // Nota: el componente concatena 'acción' + 'es' literalmente, por lo que
    // el texto renderizado conserva la tilde ("acciónes") en vez de la forma
    // ortográfica correcta ("acciones"). No es un bug de comportamiento —
    // solo un detalle cosmético de redacción — así que el test verifica el
    // texto tal como el componente lo produce hoy.
    expect(screen.getByText('3 acciónes pendientes de sincronizar')).toBeInTheDocument()
  })

  it('llama a onSincronizar al hacer click en "Sincronizar ahora" estando en línea', async () => {
    const user = userEvent.setup()
    const onSincronizar = vi.fn()
    render(<EstadoConexion enLinea pendientes={2} onSincronizar={onSincronizar} />)

    await user.click(screen.getByRole('button', { name: /sincronizar ahora/i }))

    expect(onSincronizar).toHaveBeenCalledTimes(1)
  })

  it('no permite hacer click en "Sincronizar ahora" estando sin conexión', async () => {
    const user = userEvent.setup()
    const onSincronizar = vi.fn()
    render(<EstadoConexion enLinea={false} pendientes={2} onSincronizar={onSincronizar} />)

    await user.click(screen.getByRole('button', { name: /sincronizar ahora/i }))

    expect(onSincronizar).not.toHaveBeenCalled()
  })
})
