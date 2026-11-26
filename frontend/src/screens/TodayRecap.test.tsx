// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => ({ ...(await orig<typeof import('../api')>()), getToday: vi.fn() }))
import * as api from '../api'
import TodayRecap from './TodayRecap'

afterEach(cleanup)

test('bilan : leçons, révisions et ce qui attend demain', async () => {
  vi.mocked(api.getToday).mockResolvedValue({ lessons: ['Cache'], reviewed: 4, correct: 3, tomorrow: 2 })
  render(<TodayRecap />)
  expect(await screen.findByText('Appris : Cache')).toBeTruthy()
  expect(screen.getByText('Révisé : 4 question(s), 3 juste(s)')).toBeTruthy()
  expect(screen.getByText("Demain : 2 révision(s) t'attendent.")).toBeTruthy()
})
