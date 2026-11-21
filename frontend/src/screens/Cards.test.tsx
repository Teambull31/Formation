// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getCards: vi.fn(), answerCard: vi.fn() }
})
import * as api from '../api'
import Cards from './Cards'

const card = (id: string, front: string, back: string) => ({ id, lesson_id: 'k1', kind: 'terme' as const, front, back, box: null })
afterEach(() => { cleanup(); vi.clearAllMocks() })

test('cache la réponse, puis une carte ratée revient en fin de séance', async () => {
  vi.mocked(api.getCards).mockResolvedValue({ cards: [card('a', 'Un ＿＿＿ garde les pods', 'Deployment'), card('b', 'Question B', 'Réponse B')], boxes: [0, 0, 0, 0, 0, 0], total: 2, unseen: 2 })
  vi.mocked(api.answerCard).mockResolvedValue({ box: 0, due: '2026-11-22', mastered: false })
  render(<Cards onOpen={() => {}} />)
  expect(await screen.findByText(/garde les pods/)).toBeTruthy()
  expect(screen.queryByText('Deployment')).toBeNull()
  fireEvent.click(screen.getByText('Voir la réponse'))
  fireEvent.click(await screen.findByText('À revoir'))
  expect(await screen.findByText('Question B')).toBeTruthy()
  expect(api.answerCard).toHaveBeenCalledWith('a', false)
  fireEvent.click(screen.getByText('Voir la réponse'))
  fireEvent.click(await screen.findByText('Je savais'))
  expect(await screen.findByText(/garde les pods/)).toBeTruthy()  // la carte ratée revient
})

test('invite à terminer une leçon quand il n\'y a aucune carte', async () => {
  vi.mocked(api.getCards).mockResolvedValue({ cards: [], boxes: [0, 0, 0, 0, 0, 0], total: 0, unseen: 0 })
  render(<Cards onOpen={() => {}} />)
  expect(await screen.findByText(/Terminez une leçon/)).toBeTruthy()
})
