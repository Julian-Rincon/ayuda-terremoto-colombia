// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NuevaSolicitudForm from './NuevaSolicitudForm.jsx'
import * as db from '../db.js'
import { sincronizarPendientes } from '../sync.js'

// Nunca red real ni IndexedDB real en estos tests: se mockean db.js y sync.js
// (que es quien internamente llamaría a api.js para sincronizar).
vi.mock('../db.js')
vi.mock('../sync.js')

function enLinea(valor) {
  vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(valor)
}

beforeEach(() => {
  db.encolarAccion.mockResolvedValue(1)
})

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

describe('NuevaSolicitudForm', () => {
  it('el botón de registrar está deshabilitado cuando el contenido está vacío', () => {
    render(<NuevaSolicitudForm onEncolada={vi.fn()} />)

    expect(screen.getByRole('button', { name: /registrar/i })).toBeDisabled()
  })

  it('el botón sigue deshabilitado con contenido muy corto (menos de 3 caracteres)', async () => {
    const user = userEvent.setup()
    render(<NuevaSolicitudForm onEncolada={vi.fn()} />)

    await user.type(screen.getByLabelText(/descripción/i), 'ab')

    expect(screen.getByRole('button', { name: /registrar/i })).toBeDisabled()
  })

  it('el botón se habilita con contenido de 3 caracteres o más', async () => {
    const user = userEvent.setup()
    render(<NuevaSolicitudForm onEncolada={vi.fn()} />)

    await user.type(screen.getByLabelText(/descripción/i), 'Sin agua potable')

    expect(screen.getByRole('button', { name: /registrar/i })).toBeEnabled()
  })

  it('el botón se deshabilita de nuevo si el contenido queda solo en espacios', async () => {
    const user = userEvent.setup()
    render(<NuevaSolicitudForm onEncolada={vi.fn()} />)

    await user.type(screen.getByLabelText(/descripción/i), '   ')

    expect(screen.getByRole('button', { name: /registrar/i })).toBeDisabled()
  })

  it('sin conexión: encola el reporte localmente, no intenta sincronizar y avisa que se enviará después', async () => {
    enLinea(false)
    const user = userEvent.setup()
    const onEncolada = vi.fn()
    render(<NuevaSolicitudForm onEncolada={onEncolada} />)

    await user.type(screen.getByLabelText(/descripción/i), 'Sin agua potable')
    await user.type(screen.getByLabelText(/zona/i), 'Barrio Centro')
    await user.click(screen.getByRole('button', { name: /registrar/i }))

    await waitFor(() => {
      expect(db.encolarAccion).toHaveBeenCalledWith('reporte', {
        contenido: 'Sin agua potable',
        zona: 'Barrio Centro',
        canal: 'manual',
      })
    })
    expect(sincronizarPendientes).not.toHaveBeenCalled()
    expect(onEncolada).toHaveBeenCalled()
    expect(
      await screen.findByText(/guardado localmente.*se enviará cuando vuelva la conexión/i),
    ).toBeInTheDocument()
    // El formulario se limpia tras encolar.
    expect(screen.getByLabelText(/descripción/i)).toHaveValue('')
  })

  it('en línea: sincroniza de inmediato y muestra "Reporte enviado." si la sincronización tuvo éxito', async () => {
    enLinea(true)
    sincronizarPendientes.mockResolvedValue({ sincronizados: 1, fallidos: 0 })
    const user = userEvent.setup()
    const onEncolada = vi.fn()
    render(<NuevaSolicitudForm onEncolada={onEncolada} />)

    await user.type(screen.getByLabelText(/descripción/i), 'Sin agua potable')
    await user.click(screen.getByRole('button', { name: /registrar/i }))

    await waitFor(() => {
      expect(sincronizarPendientes).toHaveBeenCalled()
    })
    expect(db.encolarAccion).toHaveBeenCalledWith('reporte', {
      contenido: 'Sin agua potable',
      zona: null,
      canal: 'manual',
    })
    expect(await screen.findByText('Reporte enviado.')).toBeInTheDocument()
    expect(onEncolada).toHaveBeenCalledTimes(2)
  })

  it('en línea pero la sincronización no logra enviar nada: avisa que se reintentará', async () => {
    enLinea(true)
    sincronizarPendientes.mockResolvedValue({ sincronizados: 0, fallidos: 1 })
    const user = userEvent.setup()
    render(<NuevaSolicitudForm onEncolada={vi.fn()} />)

    await user.type(screen.getByLabelText(/descripción/i), 'Sin agua potable')
    await user.click(screen.getByRole('button', { name: /registrar/i }))

    expect(await screen.findByText('Reporte guardado localmente — se reintentará.')).toBeInTheDocument()
  })
})
