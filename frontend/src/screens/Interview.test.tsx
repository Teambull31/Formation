// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getInterview: vi.fn(), answerInterview: vi.fn() }
})
import * as api from '../api'
import Interview from './Interview'

const one = { id: 'iv-01', role: 'DevOps', question: "C'est quoi l'idempotence ?", time_limit: 90, best: null }

beforeEach(() => { vi.mocked(api.getInterview).mockResolvedValue({ questions: [one] }) })
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.useRealTimers() })

const answer = 'Relancer plusieurs fois donne le même état final.'

test('bloque une réponse trop courte', async () => {
  render(<Interview />)
  await screen.findByText(/idempotence/)
  expect((screen.getByText('Faire noter') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.change(screen.getByLabelText('Ta réponse'), { target: { value: answer } })
  expect((screen.getByText('Faire noter') as HTMLButtonElement).disabled).toBe(false)
})

test('affiche score, mode, idées oubliées et réponse modèle', async () => {
  vi.mocked(api.answerInterview).mockResolvedValue({
    score: 50, xp: 15, best: 50, mode: 'mots-clés', feedback: 'Approximatif.', missing: ['un exemple'], model_answer: 'Réponse de référence.',
  })
  render(<Interview />)
  await screen.findByText(/idempotence/)
  fireEvent.change(screen.getByLabelText('Ta réponse'), { target: { value: answer } })
  fireEvent.click(screen.getByText('Faire noter'))
  expect(await screen.findByText(/50\/100/)).toBeTruthy()
  expect(screen.getByText(/\+15 XP/)).toBeTruthy()
  expect(screen.getByText(/notation : mots-clés/)).toBeTruthy()
  expect(screen.getByText('un exemple')).toBeTruthy()
  expect(screen.getByText('Réponse de référence.')).toBeTruthy()
  expect(api.answerInterview).toHaveBeenCalledWith('iv-01', answer)
})

test('le chrono décompte depuis la limite de la question', async () => {
  render(<Interview />)
  await screen.findByText(/idempotence/)
  expect(screen.getByRole('timer').textContent).toBe('1:30')
  vi.useFakeTimers()
  fireEvent.click(screen.getByText('Chrono'))
  act(() => { vi.advanceTimersByTime(3000) })
  expect(screen.getByRole('timer').textContent).toBe('1:27')
})

test('banque vide : message clair', async () => {
  vi.mocked(api.getInterview).mockResolvedValue({ questions: [] })
  render(<Interview />)
  expect(await screen.findByText(/Aucune question/)).toBeTruthy()
})
