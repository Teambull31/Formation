import { expect, test } from 'vitest'
import { correction, optClass } from './qcm'

const wrong = { correct: false, explanation: '', remedial_lesson_id: null, answer: 'B' }
test('après une erreur : choix faux marqué, bonne option surlignée, correction en clair', () => {
  expect(optClass(null, 0, 'A')).toBe('opt')
  expect(optClass({ chosen: 0, r: wrong }, 0, 'A')).toBe('opt wrong')
  expect(optClass({ chosen: 0, r: wrong }, 1, 'B')).toBe('opt right')
  expect(optClass({ chosen: 1, r: { ...wrong, correct: true, answer: null } }, 1, 'B')).toBe('opt right')
  expect(correction(wrong)).toBe(' Bonne réponse : B.')
  expect(correction({ ...wrong, correct: true })).toBe('')
})
