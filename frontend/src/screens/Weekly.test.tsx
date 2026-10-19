// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return {
    ...real,
    weeklyImport: vi.fn().mockRejectedValue(new real.ApiError(422, 'invalide', ['lesson l1 sans titre', 'qcm q2 vide'])),
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
