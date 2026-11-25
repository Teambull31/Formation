// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getPodcast: vi.fn(), getLessons: vi.fn(), getRevision: vi.fn(), completeStep: vi.fn() }
})
import * as api from '../api'
import Listen from './Listen'

afterEach(() => { cleanup(); vi.clearAllMocks() })

test('liste épisodes puis leçons, et charge la piste choisie', async () => {
  vi.mocked(api.getRevision).mockResolvedValue({ items: 0, key: null })
  vi.mocked(api.getPodcast).mockResolvedValue([{ file: 'ep01.mp3', title: 'Épisode 1', minutes: 13 }])
  vi.mocked(api.getLessons).mockResolvedValue([{ id: 'ci', title: 'CI/CD', fiche: false, lessons: [{ id: 'ci1', title: 'Premier workflow', minutes: 15 }] }])
  const { container } = render(<Listen />)
  fireEvent.click(await screen.findByText('Premier workflow'))
  expect(container.querySelector('audio')!.getAttribute('src')).toBe('/api/audio/ci1.mp3')
  expect(screen.getByText('Le livre du soir DevOps')).toBeTruthy()
  expect(screen.getAllByText('Leçons — CI/CD')).toHaveLength(2) // en-tête de liste + lecteur
})

test('révision du jour et fiches en tête ; une leçon finie est validée', async () => {
  vi.mocked(api.getPodcast).mockResolvedValue([])
  vi.mocked(api.getRevision).mockResolvedValue({ items: 4, key: 'abc123' })
  vi.mocked(api.completeStep).mockResolvedValue({ ok: true })
  vi.mocked(api.getLessons).mockResolvedValue([{ id: 'ci', title: 'CI/CD', fiche: true, lessons: [{ id: 'ci1', title: 'Premier workflow', minutes: 15 }] }])
  const { container } = render(<Listen />)
  expect(await screen.findByText('Révision express (4 questions)')).toBeTruthy()
  fireEvent.click(screen.getByText('CI/CD'))
  expect(container.querySelector('audio')!.getAttribute('src')).toBe('/api/fiche-audio/ci.mp3')
  fireEvent.click(screen.getByText('Premier workflow'))
  fireEvent.ended(container.querySelector('audio')!)
  expect(api.completeStep).toHaveBeenCalledWith('lesson', 'ci1')
})

test('préparer la route : révision du jour + épisodes pas écoutés, téléchargés seuls à l\'ouverture', async () => {
  const add = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('caches', { open: vi.fn().mockResolvedValue({ keys: vi.fn().mockResolvedValue([]), add, delete: vi.fn() }) })
  vi.mocked(api.getRevision).mockResolvedValue({ items: 3, key: 'k1' })
  vi.mocked(api.getPodcast).mockResolvedValue([
    { file: 'ep01.mp3', title: 'Un', minutes: 10, listened: 1 }, { file: 'ep02.mp3', title: 'Deux', minutes: 10, listened: 0 }])
  vi.mocked(api.getLessons).mockResolvedValue([])
  render(<Listen />)
  expect(await screen.findByText(/Route prête : 2 piste/)).toBeTruthy()
  expect(add.mock.calls.map((c) => c[0])).toEqual(['/api/revision/k1.mp3', '/api/podcast/ep02.mp3'])
  vi.unstubAllGlobals()
})
