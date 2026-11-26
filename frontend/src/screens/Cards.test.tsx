// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

test('« J\'ai 2 min » : trois cartes au plus, puis la journée compte', async () => {
  const cs = ['a', 'b', 'c', 'd'].map((x) => card(x, `Question ${x}`, `Réponse ${x}`))
  vi.mocked(api.getCards).mockResolvedValue({ cards: cs, boxes: [0, 0, 0, 0, 0, 0], total: 4, unseen: 4 })
  vi.mocked(api.answerCard).mockResolvedValue({ box: 1, due: '2026-11-28', mastered: false })
  render(<Cards onOpen={() => {}} limit={3} />)
  for (const x of ['a', 'b', 'c']) {
    expect(await screen.findByText(`Question ${x}`)).toBeTruthy()
    fireEvent.click(screen.getByText('Voir la réponse'))
    fireEvent.click(await screen.findByText('Je savais'))
  }
  expect(await screen.findByText(/la journée compte/)).toBeTruthy()
  expect(api.answerCard).toHaveBeenCalledTimes(3)
})

test('gestes : toucher montre la réponse, glisser à droite = je savais, flèche gauche = à revoir', async () => {
  vi.mocked(api.getCards).mockResolvedValue({ cards: [card('a', 'Question A', 'Réponse A'), card('b', 'Question B', 'Réponse B')], boxes: [0, 0, 0, 0, 0, 0], total: 2, unseen: 2 })
  vi.mocked(api.answerCard).mockResolvedValue({ box: 1, due: '2026-11-28', mastered: false })
  render(<Cards onOpen={() => {}} />)
  const front = await screen.findByText('Question A')
  const cardEl = front.closest('.card')!
  fireEvent.touchStart(cardEl, { touches: [{ clientX: 100 }] })
  fireEvent.touchEnd(cardEl, { changedTouches: [{ clientX: 102 }] })
  expect(await screen.findByText('Réponse A')).toBeTruthy()
  fireEvent.touchStart(cardEl, { touches: [{ clientX: 100 }] })
  fireEvent.touchEnd(cardEl, { changedTouches: [{ clientX: 200 }] })
  expect(await screen.findByText('Question B')).toBeTruthy()
  expect(api.answerCard).toHaveBeenLastCalledWith('a', true)
  fireEvent.keyDown(window, { key: ' ' })
  expect(await screen.findByText('Réponse B')).toBeTruthy()
  fireEvent.keyDown(window, { key: 'ArrowLeft' })
  await waitFor(() => expect(api.answerCard).toHaveBeenLastCalledWith('b', false))
  expect(await screen.findByText('Question B')).toBeTruthy() // ratée et seule restante : elle revient
})

test('nouvelles cartes par jour réglables', async () => {
  vi.mocked(api.getCards).mockResolvedValue({ cards: [card('a', 'Q', 'R')], boxes: [0, 0, 0, 0, 0, 0], total: 1, unseen: 1, per_day: 10 })
  const set = vi.spyOn(api, 'setCardsPerDay').mockResolvedValue({ ok: true })
  render(<Cards onOpen={() => {}} />)
  fireEvent.change(await screen.findByDisplayValue('10'), { target: { value: '5' } })
  expect(set).toHaveBeenCalledWith(5)
})

test('carte à trou : 3 propositions, la réponse choisie décide « su » ou « à revoir »', async () => {
  vi.mocked(api.getCards).mockResolvedValue({ cards: [{ ...card('a', 'Un ＿＿＿ garde les pods', 'Deployment'), choices: ['Service', 'Deployment', 'Pod'] }], boxes: [0, 0, 0, 0, 0, 0], total: 1, unseen: 1 })
  vi.mocked(api.answerCard).mockResolvedValue({ box: 0, due: '2026-11-22', mastered: false })
  render(<Cards onOpen={() => {}} />)
  fireEvent.click(await screen.findByText('Pod'))
  expect(screen.getByRole('status').textContent).toContain('Bonne réponse : Deployment')
  expect(screen.getByText('Service').hasAttribute('disabled')).toBe(true)
  fireEvent.click(screen.getByText('Suivant →'))
  await waitFor(() => expect(api.answerCard).toHaveBeenCalledWith('a', false))
})
