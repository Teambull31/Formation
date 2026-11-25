// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getLesson: vi.fn(), getLessons: vi.fn() }
})
import * as api from '../api'
import Lesson from './Lesson'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const lesson = (id: string) => ({ id, title: `Leçon ${id}`, minutes: 5, body_md: 'Texte', qcm: [], tp: null })
const index = [
  { id: 'm1', title: 'M1', fiche: false, lessons: [{ id: 'a', title: 'A', minutes: 5 }, { id: 'b', title: 'B', minutes: 5 }] },
  { id: 'm2', title: 'M2', fiche: false, lessons: [{ id: 'c', title: 'C', minutes: 5 }] },
]

test('boutons précédente et suivante, y compris vers le module suivant', async () => {
  vi.mocked(api.getLesson).mockImplementation((id) => Promise.resolve(lesson(id)))
  vi.mocked(api.getLessons).mockResolvedValue(index)
  const onOpen = vi.fn()
  render(<Lesson id="b" onOpen={onOpen} />)
  fireEvent.click(await screen.findByText('Leçon suivante : C →'))
  expect(onOpen).toHaveBeenCalledWith('c')
  fireEvent.click(screen.getByText('← A'))
  expect(onOpen).toHaveBeenCalledWith('a')
})

test('pas de suivante sur la dernière leçon, rien hors catalogue', async () => {
  vi.mocked(api.getLesson).mockImplementation((id) => Promise.resolve(lesson(id)))
  vi.mocked(api.getLessons).mockResolvedValue(index)
  render(<Lesson id="c" onOpen={() => {}} />)
  expect(await screen.findByText('← B')).toBeTruthy()
  expect(screen.queryByText(/Leçon suivante/)).toBeNull()
  cleanup()
  render(<Lesson id="remediation" onOpen={() => {}} />)
  expect(await screen.findByText('Leçon remediation')).toBeTruthy()
  expect(screen.queryByRole('navigation')).toBeNull()
})

test('questions avant lecture puis QCM avec la confiance envoyée', async () => {
  const qcm = [{ id: 'q1', text: 'Où vit un workflow ?', options: ['.github/workflows', '/etc'] }]
  vi.mocked(api.getLesson).mockResolvedValue({ ...lesson('a'), qcm })
  vi.mocked(api.getLessons).mockResolvedValue(index)
  const ans = vi.spyOn(api, 'answerQcm').mockResolvedValue({ correct: false, explanation: 'Dans .github/workflows.', remedial_lesson_id: null, sure_wrong: true })
  render(<Lesson id="a" onOpen={() => {}} />)
  expect(await screen.findByText(/Avant de lire/)).toBeTruthy()
  fireEvent.click(screen.getByText("J'ai deviné, je lis la leçon"))
  expect(screen.queryByText(/Avant de lire/)).toBeNull()
  fireEvent.click(screen.getByText('Sûr'))
  fireEvent.click(screen.getByText('/etc'))
  expect(await screen.findByText(/en étant sûr de toi/)).toBeTruthy()
  expect(ans).toHaveBeenCalledWith('q1', 1, true)
})

test('lecture par pages : une question entre deux pages, la fin sur la dernière', async () => {
  localStorage.clear()
  const long = 'mot '.repeat(250)
  const qcm = [{ id: 'q1', text: 'Question un ?', options: ['a', 'b'] }, { id: 'q2', text: 'Question deux ?', options: ['a', 'b'] }]
  vi.mocked(api.getLesson).mockResolvedValue({ ...lesson('a'), body_md: `## Partie 1\n${long}\n## Partie 2\n${long}`, qcm })
  vi.mocked(api.getLessons).mockResolvedValue(index)
  render(<Lesson id="a" kind="qcm" onOpen={() => {}} />)
  expect(await screen.findByText('Page 1 / 2')).toBeTruthy()
  expect(screen.getByText('Question un ?').closest('[hidden]')).toBeNull()
  expect(screen.getByText('Question deux ?').closest('[hidden]')).not.toBeNull()
  expect(screen.queryByText('Terminer la leçon')).toBeNull()
  fireEvent.click(screen.getByText('Page suivante →'))
  expect(screen.getByText('Page 2 / 2')).toBeTruthy()
  expect(screen.getByText('Question deux ?').closest('[hidden]')).toBeNull()
  expect(screen.getByText('Terminer la leçon')).toBeTruthy()
  fireEvent.click(screen.getByText('Tout sur une page'))
  expect(screen.getByText('Question un ?').closest('[hidden]')).toBeNull()
})
