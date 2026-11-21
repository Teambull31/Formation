// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getPlan: vi.fn(), startPlan: vi.fn(), markPlanDay: vi.fn() }
})
import * as api from '../api'
import Plan from './Plan'

const days = [
  { day: 1, title: 'CI : premier workflow', lessons: ['ci1'], todo: [], done: true, manual: false },
  { day: 2, title: 'Repos actif', lessons: [], todo: ['Cartes du jour'], done: false, manual: false },
]
afterEach(() => { cleanup(); vi.clearAllMocks() })

test('propose de commencer, puis montre le jour courant et le retard', async () => {
  vi.mocked(api.getPlan).mockResolvedValueOnce({ started: false, start: null, today: null, days, late: 0 })
    .mockResolvedValue({ started: true, start: '2026-11-20', today: 2, days, late: 0 })
  vi.mocked(api.startPlan).mockResolvedValue({ ok: true })
  vi.mocked(api.markPlanDay).mockResolvedValue({ ok: true })
  render(<Plan onStart={() => {}} />)
  fireEvent.click(await screen.findByText("Commencer aujourd'hui"))
  expect(await screen.findByText('Jour 2 / 2 : Repos actif')).toBeTruthy()
  expect(screen.getByText('Cartes du jour')).toBeTruthy()
  fireEvent.click(screen.getByText('Marquer fait'))
  expect(api.markPlanDay).toHaveBeenCalledWith(2, true)
})

test('ouvre la leçon du jour', async () => {
  vi.mocked(api.getPlan).mockResolvedValue({ started: true, start: '2026-11-21', today: 1, days, late: 0 })
  const onStart = vi.fn()
  render(<Plan onStart={onStart} />)
  fireEvent.click(await screen.findByText('Ouvrir la leçon ci1'))
  expect(onStart).toHaveBeenCalledWith('ci1')
})
