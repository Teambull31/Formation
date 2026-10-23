// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getReviews: vi.fn(), answerQcm: vi.fn() }
})
import * as api from '../api'
import Review from './Review'

const data = {
  due: ['q1', 'q2'],
  questions: [
    { id: 'q1', text: 'Quelle commande ?', options: ['ls', 'touch'], box: 0 },
    { id: 'q2', text: 'Autre question ?', options: ['a', 'b'], box: 2 },
  ],
  boxes: [1, 0, 1, 0, 0],
  intervals: [1, 2, 4, 7, 14],
}

beforeEach(() => {
  vi.mocked(api.getReviews).mockResolvedValue(data)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

test('liste les questions dues et les 5 boîtes', async () => {
  render(<Review onOpen={() => {}} />)
  expect(await screen.findByText('Quelle commande ?')).toBeTruthy()
  expect(screen.getByText(/2 à réviser/)).toBeTruthy()
  expect(screen.getAllByRole('listitem')).toHaveLength(5)
})

test('bonne réponse puis fin de séance avec score', async () => {
  vi.mocked(api.answerQcm).mockResolvedValue({ correct: true, explanation: 'Bien vu', remedial_lesson_id: null })
  render(<Review onOpen={() => {}} />)
  fireEvent.click(await screen.findByText('touch'))
  expect(await screen.findByText(/Correct\. Bien vu/)).toBeTruthy()
  expect(screen.queryByText('Ouvrir la mini-leçon')).toBeNull()
  fireEvent.click(screen.getByText('Question suivante'))
  vi.mocked(api.answerQcm).mockResolvedValue({ correct: false, explanation: 'Non', remedial_lesson_id: 'l9' })
  fireEvent.click(await screen.findByText('a'))
  await screen.findByText(/Raté\. Non/)
  fireEvent.click(screen.getByText('Terminer'))
  expect(await screen.findByText('1 / 2 correctes')).toBeTruthy()
  expect(api.answerQcm).toHaveBeenCalledWith('q1', 1)
})

test('mauvaise réponse : lien vers la leçon corrective', async () => {
  vi.mocked(api.answerQcm).mockResolvedValue({ correct: false, explanation: 'Faux', remedial_lesson_id: 'l7' })
  const onOpen = vi.fn()
  render(<Review onOpen={onOpen} />)
  fireEvent.click(await screen.findByText('ls'))
  fireEvent.click(await screen.findByText('Ouvrir la mini-leçon'))
  expect(onOpen).toHaveBeenCalledWith('l7')
})

test('rien à réviser', async () => {
  vi.mocked(api.getReviews).mockResolvedValue({ due: [], questions: [], boxes: [0, 0, 0, 0, 0], intervals: [1, 2, 4, 7, 14] })
  render(<Review onOpen={() => {}} />)
  expect(await screen.findByText("Rien à réviser aujourd'hui")).toBeTruthy()
})

test('erreur API : message et réessai', async () => {
  vi.mocked(api.getReviews).mockRejectedValueOnce(new Error('boom'))
  render(<Review onOpen={() => {}} />)
  expect((await screen.findByRole('alert')).textContent).toContain('boom')
  fireEvent.click(screen.getByText('Réessayer'))
  expect(await screen.findByText('Quelle commande ?')).toBeTruthy()
})
