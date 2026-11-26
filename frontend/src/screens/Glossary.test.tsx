// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => ({ ...(await orig<typeof import('../api')>()), getGlossary: vi.fn() }))
import * as api from '../api'
import Glossary from './Glossary'

afterEach(cleanup)

test('recherche dans le terme et la phrase, ouvre la leçon sur la définition', async () => {
  vi.mocked(api.getGlossary).mockResolvedValue({
    runner: { term: 'runner', sentence: 'Un runner exécute les jobs.', lesson_id: 'ci1', title: 'Premier workflow' },
    cache: { term: 'cache', sentence: 'Le cache garde les dépendances.', lesson_id: 'ci2', title: 'Cache' },
  })
  const onOpen = vi.fn()
  render(<Glossary onOpen={onOpen} />)
  fireEvent.change(await screen.findByLabelText('Chercher un terme'), { target: { value: 'jobs' } })
  expect(screen.getByText(/Un runner exécute les jobs/)).toBeTruthy()
  expect(screen.queryByText(/garde les dépendances/)).toBeNull()
  fireEvent.click(screen.getByText('Premier workflow →'))
  expect(onOpen).toHaveBeenCalledWith('ci1', 'Un runner exécute les jobs.')
})
