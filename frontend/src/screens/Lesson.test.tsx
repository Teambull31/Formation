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
