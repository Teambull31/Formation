// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getPushKey: vi.fn(), pushSubscribe: vi.fn(), pushUnsubscribe: vi.fn(), pushTest: vi.fn() }
})
import * as api from '../api'
import Reminders from './Reminders'

afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

test('navigateur sans Web Push : message explicatif, aucun bouton', () => {
  render(<Reminders />)
  expect(screen.getByText(/Indisponible ici/)).toBeTruthy()
  expect(screen.queryByText('Activer le rappel')).toBeNull()
})

function stubPush(permission: NotificationPermission, subscribe = vi.fn().mockResolvedValue({ toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/x' }), endpoint: 'https://fcm.googleapis.com/x' })) {
  const pm = { getSubscription: vi.fn().mockResolvedValue(null), subscribe }
  vi.stubGlobal('isSecureContext', true)
  vi.stubGlobal('PushManager', class {})
  vi.stubGlobal('Notification', { requestPermission: vi.fn().mockResolvedValue(permission) })
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve({ pushManager: pm }) } })
  return subscribe
}

test('permission refusée : on n\'abonne rien', async () => {
  const subscribe = stubPush('denied')
  render(<Reminders />)
  fireEvent.click(await screen.findByText('Activer le rappel'))
  expect(await screen.findByText(/refusées/)).toBeTruthy()
  expect(subscribe).not.toHaveBeenCalled()
  expect(api.pushSubscribe).not.toHaveBeenCalled()
})

test('permission accordée : abonnement envoyé au serveur', async () => {
  vi.mocked(api.getPushKey).mockResolvedValue({ key: 'BAQ', subscribed: false })
  vi.mocked(api.pushSubscribe).mockResolvedValue({ ok: true })
  const subscribe = stubPush('granted')
  render(<Reminders />)
  fireEvent.click(await screen.findByText('Activer le rappel'))
  expect(await screen.findByText('Rappel activé.')).toBeTruthy()
  expect(subscribe.mock.calls[0][0].userVisibleOnly).toBe(true)
  expect(api.pushSubscribe).toHaveBeenCalledWith({ endpoint: 'https://fcm.googleapis.com/x' })
  expect(screen.getByText('Désactiver le rappel')).toBeTruthy()
})
