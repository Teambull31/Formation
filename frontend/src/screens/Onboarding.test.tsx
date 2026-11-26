// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../push', () => ({ pushSupported: vi.fn(() => false), enablePush: vi.fn() }))
import * as push from '../push'
import Onboarding from './Onboarding'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); vi.mocked(push.pushSupported).mockReturnValue(false) })

test('liste ce qui manque, bouton Activer en https, masquable et retenu', () => {
  vi.stubGlobal('isSecureContext', true)
  const onReminders = vi.fn()
  const { unmount } = render(<Onboarding pushOff sessionDone={false} onReminders={onReminders} />)
  fireEvent.click(screen.getByText('Activer'))
  expect(onReminders).toHaveBeenCalled()
  fireEvent.click(screen.getByLabelText('Masquer'))
  expect(screen.queryByText('Bien démarrer')).toBeNull()
  unmount()
  render(<Onboarding pushOff sessionDone={false} onReminders={onReminders} />)
  expect(screen.queryByText('Bien démarrer')).toBeNull()
})

test('tout fait : rien à afficher', () => {
  vi.stubGlobal('isSecureContext', true)
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  render(<Onboarding pushOff={false} sessionDone onReminders={() => {}} />)
  expect(screen.queryByText('Bien démarrer')).toBeNull()
})

test('rappel activé en un toucher, sans détour par Équipe ; réglages proposés ensuite', async () => {
  vi.stubGlobal('isSecureContext', true)
  vi.stubGlobal('matchMedia', () => ({ matches: true })) // déjà installée
  vi.mocked(push.pushSupported).mockReturnValue(true)
  vi.mocked(push.enablePush).mockResolvedValue(null)
  const onReminders = vi.fn()
  render(<Onboarding pushOff sessionDone onReminders={onReminders} />)
  fireEvent.click(screen.getByText('Activer'))
  expect(await screen.findByText(/Rappel activé/)).toBeTruthy()
  expect(push.enablePush).toHaveBeenCalled()
  expect(onReminders).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText("Choisir l'heure et le déclencheur"))
  expect(onReminders).toHaveBeenCalled()
})

test('notifications refusées : le message le dit, l\'étape reste à faire', async () => {
  vi.stubGlobal('isSecureContext', true)
  vi.mocked(push.pushSupported).mockReturnValue(true)
  vi.mocked(push.enablePush).mockResolvedValue('Notifications refusées dans le navigateur.')
  render(<Onboarding pushOff sessionDone={false} onReminders={() => {}} />)
  fireEvent.click(screen.getByText('Activer'))
  expect(await screen.findByText('Notifications refusées dans le navigateur.')).toBeTruthy()
  expect(screen.getByText('Activer')).toBeTruthy()
})
