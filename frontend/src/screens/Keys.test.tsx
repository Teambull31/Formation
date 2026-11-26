// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getLessonKeys: vi.fn() }
})
import * as api from '../api'
import Keys from './Keys'

afterEach(() => { cleanup(); vi.clearAllMocks() })

test('la réponse reste cachée tant qu\'on ne l\'a pas demandée', async () => {
  vi.mocked(api.getLessonKeys).mockResolvedValue([{ id: 'k1', kind: 'terme', front: 'Un ＿＿＿ exécute les jobs.', back: 'runner' }])
  render(<Keys lessonId="ci1" />)
  expect(await screen.findByText(/exécute les jobs/)).toBeTruthy()
  expect(screen.queryByText('runner')).toBeNull()
  fireEvent.click(screen.getByText('Voir'))
  expect(screen.getByText('runner')).toBeTruthy()
})
