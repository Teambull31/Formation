import type { QcmResult } from './api'

export type Answered = { chosen: number; r: QcmResult } | null

/** Classe d'une option : choisie juste ou fausse ; après une erreur, la bonne réponse est surlignée aussi. */
export const optClass = (res: Answered, i: number, text: string) =>
  'opt' + (!res ? '' : res.chosen === i ? (res.r.correct ? ' right' : ' wrong') : !res.r.correct && res.r.answer === text ? ' right' : '')

/** « Raté. Bonne réponse : X. » : corriger tout de suite, en clair (le serveur ne la donne qu'après une erreur). */
export const correction = (r: QcmResult) => (r.correct || !r.answer ? '' : ` Bonne réponse : ${r.answer}.`)
