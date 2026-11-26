// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return {
    ...real,
    weeklyImport: vi.fn().mockRejectedValue(new real.ApiError(422, 'invalide', ['lesson l1 sans titre', 'qcm q2 vide'])),
    getUnclear: vi.fn().mockResolvedValue([{ id: 7, lesson_id: 'ci2', title: 'Cache', excerpt: 'Partie 2', at: '2026-11-26' }]),
    clearUnclear: vi.fn().mockResolvedValue({ ok: true }),
    getWeak: vi.fn().mockResolvedValue([{ lesson_id: 'ci3', title: 'Secrets', module: 'CI/CD', count: 2 }]),
    getRetention: vi.fn().mockResolvedValue({ answered7: 0, rate7: null, solid: 0, weak: 2, summary: '1 jour(s) actif(s) sur 7.' }),
  }
})
import Weekly from './Weekly'

afterEach(cleanup)

test('import refusé 422 : erreurs listées, aucun succès', async () => {
  render(<Weekly />)
  fireEvent.change(screen.getByLabelText('Chemin du module'), { target: { value: '/tmp/m' } })
  fireEvent.click(screen.getByText('Importer'))
  expect(await screen.findByText('lesson l1 sans titre')).toBeTruthy()
  expect(screen.getByText('qcm q2 vide')).toBeTruthy()
  expect(screen.queryByText(/importé/i)).toBeNull()
})

test('points faibles : la leçon la plus touchée, avec Revoir', async () => {
  const onOpen = vi.fn()
  render(<Weekly onOpen={onOpen} />)
  const row = (await screen.findByText(/2 erreur\(s\)/)).closest('.row') as HTMLElement
  fireEvent.click(within(row).getByText('Revoir'))
  expect(onOpen).toHaveBeenCalledWith('ci3')
  expect(screen.getByText('1 jour(s) actif(s) sur 7.')).toBeTruthy()
})

test('pages pas claires : Revoir ouvre la page, Compris la retire', async () => {
  const onOpen = vi.fn()
  render(<Weekly onOpen={onOpen} />)
  const row = (await screen.findByText(/Partie 2/)).closest('.row') as HTMLElement
  fireEvent.click(within(row).getByText('Revoir'))
  expect(onOpen).toHaveBeenCalledWith('ci2', 'Partie 2')
  fireEvent.click(screen.getByText('Compris ✓'))
  await waitFor(() => expect(screen.queryByText(/Partie 2/)).toBeNull())
})
