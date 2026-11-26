// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getQuest: vi.fn(), getTeam: vi.fn(), getReviews: vi.fn(), getPushKey: vi.fn(), getPlan: vi.fn() }
})
import * as api from '../api'
import Quest from './Quest'

afterEach(() => { cleanup(); vi.clearAllMocks() })

test('révisions en tête, TP en attente, suggestions et bandeau de rappel', async () => {
  vi.mocked(api.getQuest).mockResolvedValue({
    day: '2026-11-25', imposed_topic: null, bonus: null,
    steps: [{ kind: 'lesson', lesson_id: 'ci4', minutes: 10, xp: 20, done: false }],
    pending_tp: ['ci3'], review: { due: 3, done: false },
    week: { days: 2, goal: 4, dots: [false, true, false, true, false, false, false], today: 3 },
    suggestions: [{ kind: 'episode', id: 'ep05.mp3', label: 'À écouter : Épisode 5' },
      { kind: 'feynman', id: 'ci1', label: 'Explique ci1 à un junior (Feynman)' }],
  })
  vi.mocked(api.getTeam).mockResolvedValue({ xp: 0, level: 1, rank: 'Recrue', rank_capped: false, skills: {}, skill_levels: {}, tokens: 0, streak: 0, inventory: [] } as never)
  vi.mocked(api.getReviews).mockResolvedValue({ due: ['q1'], questions: [{ id: 'q1', text: '?', options: [], box: 0 }], boxes: [], intervals: [] })
  vi.mocked(api.getPushKey).mockResolvedValue({ key: 'k', subscribed: false, hour: 19 })
  vi.mocked(api.getPlan).mockResolvedValue({ started: false, start: null, today: null, days: [], late: 0 })
  const onStart = vi.fn()
  const onGo = vi.fn()
  render(<Quest onStart={onStart} onGo={onGo} />)
  expect(await screen.findByText('Révisions du jour · 3 à revoir')).toBeTruthy()
  expect(screen.getByText('2 / 4 jours')).toBeTruthy()
  fireEvent.click(await screen.findByText('Réviser'))
  expect(onGo).toHaveBeenLastCalledWith('Révisions', 'qcm')
  fireEvent.click(screen.getByText('Ouvrir'))
  expect(onStart).toHaveBeenLastCalledWith('ci3', 'tp', false)
  fireEvent.click(screen.getByText('À écouter : Épisode 5'))
  expect(onGo).toHaveBeenLastCalledWith('Écoute')
  fireEvent.click(screen.getByText('Explique ci1 à un junior (Feynman)'))
  expect(onStart).toHaveBeenLastCalledWith('ci1', 'lesson', true)
  fireEvent.click(await screen.findByText(/Active le rappel quotidien/))
  expect(onGo).toHaveBeenLastCalledWith('Équipe')
})

test('« Ma séance du jour » commence par les révisions, puis la première étape', async () => {
  const base = { day: '2026-11-25', imposed_topic: null, bonus: null, pending_tp: [], suggestions: [],
    steps: [{ kind: 'lesson' as const, lesson_id: 'ci4', minutes: 10, xp: 20, done: true }, { kind: 'qcm' as const, lesson_id: 'ci4', minutes: 5, xp: 40, done: false }] }
  vi.mocked(api.getQuest).mockResolvedValueOnce({ ...base, review: { due: 2, done: false } }).mockResolvedValue({ ...base, review: null })
  vi.mocked(api.getTeam).mockResolvedValue({ xp: 0, level: 1, rank: 'R', rank_capped: false, skills: {}, skill_levels: {}, tokens: 0, streak: 0, inventory: [] } as never)
  vi.mocked(api.getReviews).mockResolvedValue({ due: [], questions: [], boxes: [], intervals: [] })
  vi.mocked(api.getPushKey).mockResolvedValue({ key: 'k', subscribed: true, hour: 19 })
  vi.mocked(api.getPlan).mockResolvedValue({ started: false, start: null, today: null, days: [], late: 0 })
  const onStart = vi.fn()
  const onGo = vi.fn()
  const { unmount } = render(<Quest onStart={onStart} onGo={onGo} />)
  fireEvent.click(await screen.findByText(/Ma séance du jour · 2 révisions/))
  expect(onGo).toHaveBeenCalledWith('Révisions', 'cartes')
  unmount()
  render(<Quest onStart={onStart} onGo={onGo} />)
  fireEvent.click(await screen.findByText(/Ma séance du jour · QCM ci4/))
  expect(onStart).toHaveBeenCalledWith('ci4', 'qcm', false)
})
