// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getPodcast: vi.fn(), getLessons: vi.fn() }
})
import * as api from '../api'
import Listen from './Listen'

afterEach(() => { cleanup(); vi.clearAllMocks() })

test('liste épisodes puis leçons, et charge la piste choisie', async () => {
  vi.mocked(api.getPodcast).mockResolvedValue([{ file: 'ep01.mp3', title: 'Épisode 1', minutes: 13 }])
  vi.mocked(api.getLessons).mockResolvedValue([{ id: 'ci', title: 'CI/CD', fiche: false, lessons: [{ id: 'ci1', title: 'Premier workflow', minutes: 15 }] }])
  const { container } = render(<Listen />)
  fireEvent.click(await screen.findByText('Premier workflow'))
  expect(container.querySelector('audio')!.getAttribute('src')).toBe('/api/audio/ci1.mp3')
  expect(screen.getByText('Le livre du soir DevOps')).toBeTruthy()
  expect(screen.getAllByText('Leçons — CI/CD')).toHaveLength(2) // en-tête de liste + lecteur
})
