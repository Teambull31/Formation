// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, gradeFeynman: vi.fn() }
})
import * as api from '../api'
import Feynman from './Feynman'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const long = 'Une image est un modèle figé et un conteneur est une instance.'

test('bouton bloqué tant que le texte est trop court', () => {
  render(<Feynman lessonId="dk1" title="Images" />)
  expect((screen.getByText('Faire noter') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.change(screen.getByLabelText('Ton explication'), { target: { value: long } })
  expect((screen.getByText('Faire noter') as HTMLButtonElement).disabled).toBe(false)
})

test('affiche score, XP et idées manquantes', async () => {
  vi.mocked(api.gradeFeynman).mockResolvedValue({ score: 72, xp: 43, best: 72, feedback: 'Bon début.', missing: ['le rôle des volumes'] })
  render(<Feynman lessonId="dk1" title="Images" />)
  fireEvent.change(screen.getByLabelText('Ton explication'), { target: { value: long } })
  fireEvent.click(screen.getByText('Faire noter'))
  expect(await screen.findByText(/72\/100/)).toBeTruthy()
  expect(screen.getByText(/\+43 XP/)).toBeTruthy()
  expect(screen.getByText('le rôle des volumes')).toBeTruthy()
  expect(api.gradeFeynman).toHaveBeenCalledWith('dk1', long)
})

test('erreur 503 affichée sans planter', async () => {
  vi.mocked(api.gradeFeynman).mockRejectedValue(new Error('Ollama indisponible'))
  render(<Feynman lessonId="dk1" title="Images" />)
  fireEvent.change(screen.getByLabelText('Ton explication'), { target: { value: long } })
  fireEvent.click(screen.getByText('Faire noter'))
  expect((await screen.findByRole('alert')).textContent).toContain('Ollama indisponible')
})
