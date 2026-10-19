// One typed function per backend route. Same-origin relative URLs only.
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
  get forbidden() {
    return this.status === 403
  }
}
export const isForbidden = (e: unknown) => e instanceof ApiError && e.status === 403

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) {
    let msg = r.statusText
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(r.status, msg)
  }
  return r.json() as Promise<T>
}

export type StepKind = 'lesson' | 'qcm' | 'tp' | 'bonus'
export interface Step { kind: StepKind; lesson_id: string; minutes: number; xp: number; done: boolean }
export interface Quest { day: string; steps: Step[]; bonus: Step | null; imposed_topic: string | null }
export interface Lesson {
  id: string; title: string; minutes: number; body_md: string
  qcm: { id: string; text: string; options: string[] }[]
  tp: { id: string; title: string; instructions_md: string; timeout_s: number } | null
}
export interface QcmResult { correct: boolean; explanation: string; remedial_lesson_id: string | null }
export interface Team {
  xp: number; level: number; rank: string; skills: Record<string, number>; tokens: number; streak: number
  inventory: { item_id: string; name: string; type: string; rarity: string; obtained_at: string }[]
}
export interface BossInfo { title: string; phases: { label: string }[]; attempts: number }
export interface BossResult {
  won: boolean; phase_reached: number; failed_pattern: string | null; remedial_lesson_id: string | null; attempts: number
}
export interface Ok { ok: boolean }

export const getQuest = (minutes: 30 | 60 = 30) => call<Quest>('GET', `/api/quest?minutes=${minutes}`)
export const completeStep = (kind: StepKind, lesson_id: string) => call<Ok>('POST', '/api/quest/step', { kind, lesson_id })
export const announceRest = () => call<Ok>('POST', '/api/rest')
export const setTopic = (topic: string | null) => call<Ok>('POST', '/api/topic', { topic })
export const getLesson = (id: string) => call<Lesson>('GET', `/api/lesson/${encodeURIComponent(id)}`)
export const audioUrl = (id: string) => `/api/audio/${encodeURIComponent(id)}.wav`
export const answerQcm = (question_id: string, chosen: number) =>
  call<QcmResult>('POST', '/api/qcm/answer', { question_id, chosen })
export const getReviews = () => call<{ due: unknown[] }>('GET', '/api/reviews')
export const getHint = (tpId: string, level = 1) =>
  call<{ hint: string; cost: number }>('GET', `/api/tp/${encodeURIComponent(tpId)}/hint?level=${level}`)
export const checkTp = (tpId: string) =>
  call<{ passed: boolean; output: string }>('POST', `/api/tp/${encodeURIComponent(tpId)}/check`)
export const getTeam = () => call<Team>('GET', '/api/team')
export const pullGacha = () => call<Record<string, unknown>>('POST', '/api/gacha/pull')
export const getBoss = () => call<BossInfo>('GET', '/api/boss')
export const attemptBoss = () => call<BossResult>('POST', '/api/boss/attempt')
export const weeklyBrief = (topic: string, format: string) =>
  call<{ brief: string }>('POST', '/api/weekly/brief', { topic, format })
export const weeklyImport = (path: string) => call<{ module_id: string }>('POST', '/api/weekly/import', { path })

export const terminalUrl = () => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/terminal`
