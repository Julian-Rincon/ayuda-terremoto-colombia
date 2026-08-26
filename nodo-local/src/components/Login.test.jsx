// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Login from './Login.jsx'
import * as api from '../api.js'
import * as db from '../db.js'

// Nunca red real ni IndexedDB real en estos tests: se mockean api.js y db.js.
vi.mock('../api.js')
vi.mock('../db.js')

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

describe('Login', () => {
  it('muestra los campos de id de territorio y secreto, ambos requeridos', () => {
    render(<Login onLogin={vi.fn()} />)

    expect(screen.getByLabelText(/id de territorio/i)).toBeRequired()
    expect(screen.getByLabelText(/secreto/i)).toBeRequired()
    expect(screen.getByLabelText(/secreto/i)).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: /ingresar/i })).toBeEnabled()
  })

  it('no llama a api.login si se intenta enviar el formulario con campos vacíos (validación required)', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    render(<Login onLogin={onLogin} />)

    await user.click(screen.getByRole('button', { name: /ingresar/i }))

    expect(api.login).not.toHaveBeenCalled()
    expect(onLogin).not.toHaveBeenCalled()
    expect(screen.queryByText(/no se pudo iniciar sesión/i)).not.toBeInTheDocument()
  })

  it('inicia sesión correctamente: guarda la sesión localmente y notifica onLogin', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    api.login.mockResolvedValue({ access_token: 'jwt-abc' })
    api.listarCentros.mockResolvedValue([
      { id: 7, id_territorio: 'choco' },
      { id: 1, id_territorio: 'valle' },
    ])
    db.guardarSesion.mockResolvedValue(undefined)

    render(<Login onLogin={onLogin} />)
    await user.type(screen.getByLabelText(/id de territorio/i), 'choco')
    await user.type(screen.getByLabelText(/secreto/i), 'clave-secreta')
    await user.click(screen.getByRole('button', { name: /ingresar/i }))

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith({ centroId: 7, idTerritorio: 'choco', token: 'jwt-abc' })
    })
    expect(api.login).toHaveBeenCalledWith('choco', 'clave-secreta')
    expect(db.guardarSesion).toHaveBeenCalledWith({ centroId: 7, idTerritorio: 'choco', token: 'jwt-abc' })
    expect(screen.queryByText(/no se pudo iniciar sesión/i)).not.toBeInTheDocument()
  })

  it('muestra un mensaje de error y no notifica onLogin si el login falla (credenciales/conexión)', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    api.login.mockRejectedValue(new Error('401 Unauthorized'))

    render(<Login onLogin={onLogin} />)
    await user.type(screen.getByLabelText(/id de territorio/i), 'choco')
    await user.type(screen.getByLabelText(/secreto/i), 'clave-mala')
    await user.click(screen.getByRole('button', { name: /ingresar/i }))

    expect(
      await screen.findByText(/no se pudo iniciar sesión.*verifica el id de territorio y el secreto/i),
    ).toBeInTheDocument()
    expect(onLogin).not.toHaveBeenCalled()
    expect(db.guardarSesion).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /ingresar/i })).toBeEnabled()
  })

  it('muestra error si el login es válido pero no existe un centro para ese id de territorio', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    api.login.mockResolvedValue({ access_token: 'jwt-abc' })
    api.listarCentros.mockResolvedValue([{ id: 1, id_territorio: 'valle' }])

    render(<Login onLogin={onLogin} />)
    await user.type(screen.getByLabelText(/id de territorio/i), 'choco')
    await user.type(screen.getByLabelText(/secreto/i), 'clave-secreta')
    await user.click(screen.getByRole('button', { name: /ingresar/i }))

    expect(await screen.findByText(/no se pudo iniciar sesión/i)).toBeInTheDocument()
    expect(onLogin).not.toHaveBeenCalled()
    expect(db.guardarSesion).not.toHaveBeenCalled()
  })

  it('deshabilita el botón y muestra el estado de carga mientras se autentica, y lo restaura al finalizar', async () => {
    let resolveLogin
    api.login.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = resolve
      }),
    )

    render(<Login onLogin={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/id de territorio/i), { target: { value: 'choco' } })
    fireEvent.change(screen.getByLabelText(/secreto/i), { target: { value: 'clave' } })
    fireEvent.click(screen.getByRole('button', { name: /ingresar/i }))

    const botonCargando = await screen.findByRole('button', { name: /ingresando/i })
    expect(botonCargando).toBeDisabled()

    resolveLogin({ access_token: 'jwt-abc' })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /ingresar/i })).toBeEnabled()
    })
  })
})
