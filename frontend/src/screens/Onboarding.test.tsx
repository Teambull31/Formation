// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Onboarding from './Onboarding'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear() })

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
