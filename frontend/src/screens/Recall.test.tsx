// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => ({ ...(await orig<typeof import('../api')>()), getRecall: vi.fn(), answerQcm: vi.fn() }))
import * as api from '../api'
import Recall from './Recall'

afterEach(cleanup)

test('question de rappel d\'une ancienne leçon, réponse enregistrée', async () => {
  vi.mocked(api.getRecall).mockResolvedValue({ id: 'q9', text: 'Que fait cp ?', options: ['copie', 'supprime'], lesson_id: 'lx1', title: 'Fichiers' })
  vi.mocked(api.answerQcm).mockResolvedValue({ correct: false, explanation: 'cp copie.', remedial_lesson_id: null })
  render(<Recall lessonId="ci4" />)
  fireEvent.click(await screen.findByText('supprime'))
  expect(await screen.findByText(/elle revient dans tes révisions/)).toBeTruthy()
  expect(api.answerQcm).toHaveBeenCalledWith('q9', 1, null)
})
