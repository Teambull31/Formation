import { renderToString } from 'react-dom/server'
import { expect, test } from 'vitest'
import App from './App'

test('app shell renders French tabs', () => {
  const h = renderToString(<App />)
  expect(h).toContain('Quête')
  expect(h).toContain('Semaine')
})
