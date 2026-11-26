// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import OfflineBanner from './OfflineBanner'

afterEach(cleanup)

test('bandeau hors ligne : apparaît à la coupure, disparaît au retour du réseau', () => {
  render(<OfflineBanner />)
  expect(screen.queryByRole('status')).toBeNull()
  act(() => { window.dispatchEvent(new Event('offline')) })
  expect(screen.getByRole('status').textContent).toMatch(/Hors ligne : cartes/)
  act(() => { window.dispatchEvent(new Event('online')) })
  expect(screen.queryByRole('status')).toBeNull()
})
