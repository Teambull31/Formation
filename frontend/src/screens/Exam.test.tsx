// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getExams: vi.fn(), getExam: vi.fn(), submitExam: vi.fn() }
})
import * as api from '../api'
import Exam from './Exam'

const exam = { id: 'k8s', title: 'Kubernetes', duration_s: 2, pass_pct: 80, best: null,
  questions: [{ id: 'q1', text: 'Combien de réplicas ?', options: ['1', '2'] }, { id: 'q2', text: 'Quel tag ?', options: ['latest', '1.27'] }] }
const result = { score: 50, passed: false, pass_pct: 80, best: 50, xp: 50,
  detail: [{ id: 'q2', text: 'Quel tag ?', chosen: -1, answer: 1, correct: false, explain: 'Jamais latest.', remedial_lesson_id: 'k1' }] }
afterEach(() => { cleanup(); vi.clearAllMocks() })

test('rend la copie avec -1 pour les questions sans réponse et montre les erreurs', async () => {
  vi.mocked(api.getExams).mockResolvedValue([{ id: 'k8s', title: 'Kubernetes', questions: 2, best: null }])
  vi.mocked(api.getExam).mockResolvedValue(exam)
  vi.mocked(api.submitExam).mockResolvedValue(result)
  const onOpen = vi.fn()
  render(<Exam onOpen={onOpen} />)
  fireEvent.click(await screen.findByText('Commencer'))
  fireEvent.click(await screen.findByText('2'))
  fireEvent.click(screen.getByText('Rendre la copie'))
  expect(await screen.findByText(/pas encore/)).toBeTruthy()
  expect(api.submitExam).toHaveBeenCalledWith('k8s', { q1: 1, q2: -1 })
  expect(screen.getByText(/Sans réponse\. Jamais latest\./)).toBeTruthy()
  fireEvent.click(screen.getByText('Revoir la leçon'))
  expect(onOpen).toHaveBeenCalledWith('k1')
})

test('le temps écoulé rend la copie automatiquement, une seule fois', async () => {
  vi.mocked(api.getExams).mockResolvedValue([{ id: 'k8s', title: 'Kubernetes', questions: 2, best: null }])
  vi.mocked(api.getExam).mockResolvedValue(exam)
  vi.mocked(api.submitExam).mockResolvedValue(result)
  render(<Exam onOpen={() => {}} />)
  fireEvent.click(await screen.findByText('Commencer'))
  await screen.findByText(/Combien de réplicas/)
  expect(await screen.findByText(/pas encore/, {}, { timeout: 4000 })).toBeTruthy()  // durée de 2 s, vraie horloge
  expect(api.submitExam).toHaveBeenCalledTimes(1)
})

test('après l\'examen : bonne réponse en clair et erreurs regroupées par leçon avec Revoir', async () => {
  vi.mocked(api.getExams).mockResolvedValue([{ id: 'k8s', title: 'Kubernetes', questions: 2, best: null }])
  vi.mocked(api.getExam).mockResolvedValue(exam)
  vi.mocked(api.submitExam).mockResolvedValue({ ...result,
    detail: [{ ...result.detail[0], answer_text: '1.27' }],
    to_review: [{ lesson_id: 'k3', title: 'Images et tags', count: 1, focus: 'Quel tag ?' }] })
  const onOpen = vi.fn()
  render(<Exam onOpen={onOpen} />)
  fireEvent.click(await screen.findByText('Commencer'))
  fireEvent.click(await screen.findByText('Rendre la copie'))
  expect(await screen.findByText('À revoir en priorité')).toBeTruthy()
  expect(screen.getByText(/Bonne réponse : 1\.27\./)).toBeTruthy()
  fireEvent.click(screen.getByText('Revoir'))
  expect(onOpen).toHaveBeenCalledWith('k3', 'Quel tag ?')
})
