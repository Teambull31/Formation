// One typed function per backend route. Same-origin relative URLs only.
export class ApiError extends Error {
  status: number
  errors: string[] // 422 import validation errors
  constructor(status: number, message: string, errors: string[] = []) {
    super(message)
    this.status = status
    this.errors = errors
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
    let errors: string[] = []
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
      if (Array.isArray(j.errors)) errors = j.errors.map(String)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(r.status, msg, errors)
  }
  return r.json() as Promise<T>
}

export type StepKind = 'lesson' | 'qcm' | 'tp' | 'bonus'
export interface Step { kind: StepKind; lesson_id: string; minutes: number; xp: number; done: boolean }
export interface Suggestion { kind: 'episode' | 'exam' | 'interview' | 'feynman' | 'mission' | 'article'; id: string; label: string }
export interface Quest {
  day: string; steps: Step[]; bonus: Step | null; imposed_topic: string | null
  pending_tp: string[]; review: { due: number; done: boolean } | null; suggestions: Suggestion[]
  pace?: 'normal' | 'fast' | 'consolidate'
}
export interface Lesson {
  id: string; title: string; minutes: number; body_md: string
  qcm: { id: string; text: string; options: string[] }[]
  tp: { id: string; title: string; instructions_md: string; timeout_s: number; real?: boolean } | null
}
export interface QcmResult { correct: boolean; explanation: string; remedial_lesson_id: string | null; sure_wrong?: boolean; lesson_id?: string | null; answer?: string | null }
export interface Team {
  xp: number; level: number; rank: string; rank_capped?: boolean; skills: Record<string, number>; skill_levels: Record<string, number>; tokens: number; streak: number
  inventory: { item_id: string; name: string; type: string; rarity: string; obtained_at: string }[]
}
export interface BossInfo { id: string; bosses: { id: string; title: string }[]; title: string; phases: { label: string }[]; attempts: number }
export interface BossResult {
  won: boolean; phase_reached: number; failed_pattern: string | null; remedial_lesson_id: string | null; attempts: number; output: string
}
export interface Ok { ok: boolean }

export const getQuest = (minutes: 30 | 60 = 30) => call<Quest>('GET', `/api/quest?minutes=${minutes}`)
export const completeStep = (kind: StepKind, lesson_id: string) => call<Ok>('POST', '/api/quest/step', { kind, lesson_id })
export const announceRest = () => call<Ok>('POST', '/api/rest')
export const setTopic = (topic: string | null) => call<Ok>('POST', '/api/topic', { topic })
export interface LessonIndex { id: string; title: string; fiche: boolean; lessons: { id: string; title: string; minutes: number }[] }
export const getLessons = () => call<LessonIndex[]>('GET', '/api/lessons')
export interface Fiche { id: string; title: string; body_md: string }
export const getFiche = (id: string) => call<Fiche>('GET', `/api/fiche/${encodeURIComponent(id)}`)
export const getLesson =(id: string) => call<Lesson>('GET', `/api/lesson/${encodeURIComponent(id)}`)
export const audioUrl = (id: string) => `/api/audio/${encodeURIComponent(id)}.mp3`
export const answerQcm = (question_id: string, chosen: number, confident: boolean | null = null) =>
  call<QcmResult>('POST', '/api/qcm/answer', { question_id, chosen, confident })
export interface ReviewQuestion { id: string; text: string; options: string[]; box: number }
export interface Reviews { due: string[]; questions: ReviewQuestion[]; boxes: number[]; intervals: number[] }
export const getReviews = () => call<Reviews>('GET', '/api/reviews')
export const getHint = (tpId: string, level = 1) =>
  call<{ hint: string; cost: number }>('POST', `/api/tp/${encodeURIComponent(tpId)}/hint`, { level })
export const getPushKey = () => call<{ key: string; subscribed: boolean; hour: number; cue?: string }>('GET', '/api/push/key')
export const setPushCue = (cue: string) => call<Ok>('POST', '/api/push/cue', { cue })
export const setPushHour = (hour: number) => call<Ok>('POST', '/api/push/hour', { hour })
export const pushSubscribe = (sub: PushSubscriptionJSON) => call<Ok>('POST', '/api/push/subscribe', sub)
export const pushUnsubscribe = (endpoint: string) => call<Ok>('POST', '/api/push/unsubscribe', { endpoint })
export const pushTest = () => call<{ sent: number }>('POST', '/api/push/test')
export interface InterviewQuestion { id: string; role: string; question: string; time_limit: number; best: number | null }
export interface InterviewResult {
  score: number; xp: number; best: number; mode: string; feedback: string; missing: string[]; model_answer: string
}
export const getInterview = () => call<{ questions: InterviewQuestion[] }>('GET', '/api/interview')
export const answerInterview = (id: string, answer: string) =>
  call<InterviewResult>('POST', `/api/interview/${encodeURIComponent(id)}`, { answer })
export interface FeynmanResult { score: number; xp: number; best: number; feedback: string; missing: string[] }
export const gradeFeynman = (lessonId: string, explanation: string) =>
  call<FeynmanResult>('POST', `/api/feynman/${encodeURIComponent(lessonId)}`, { explanation })
export const startTp = (tpId: string) =>
  call<{ dir: string }>('POST', `/api/tp/${encodeURIComponent(tpId)}/start`)
export const checkTp =(tpId: string) =>
  call<{ passed: boolean; output: string }>('POST', `/api/tp/${encodeURIComponent(tpId)}/check`)
export const realTp = (tpId: string) =>
  call<{ passed: boolean; output: string }>('POST', `/api/tp/${encodeURIComponent(tpId)}/real`)
export interface Card { id: string; lesson_id: string; kind: 'piege' | 'terme'; front: string; back: string; box: number | null }
export interface Cards { cards: Card[]; boxes: number[]; total: number; unseen: number }
export const getCards = () => call<Cards>('GET', '/api/cards')
export const answerCard = (id: string, known: boolean) =>
  call<{ box: number; due: string; mastered: boolean }>('POST', `/api/cards/${encodeURIComponent(id)}`, { known })
export interface PlanDay { day: number; title: string; lessons: string[]; todo: string[]; done: boolean; manual: boolean }
export interface Plan { started: boolean; start: string | null; today: number | null; days: PlanDay[]; late: number }
export const getPlan = () => call<Plan>('GET', '/api/plan')
export const rebasePlan = () => call<Ok>('POST', '/api/plan/rebase')
export const startPlan = () => call<Ok>('POST', '/api/plan/start')
export const markPlanDay = (day: number, done: boolean) => call<Ok>('POST', `/api/plan/day/${day}`, { done })
export interface ExamSummary { id: string; title: string; questions: number; best: number | null }
export interface Exam {
  id: string; title: string; duration_s: number; pass_pct: number; best: number | null
  questions: { id: string; text: string; options: string[] }[]
}
export interface ExamResult {
  score: number; passed: boolean; pass_pct: number; best: number; xp: number
  detail: { id: string; text: string; chosen: number; answer: number; correct: boolean; explain: string; remedial_lesson_id: string | null }[]
}
export const getExams = () => call<ExamSummary[]>('GET', '/api/exams')
export const getExam = (id: string) => call<Exam>('GET', `/api/exam/${encodeURIComponent(id)}`)
export const submitExam = (id: string, answers: Record<string, number>) =>
  call<ExamResult>('POST', `/api/exam/${encodeURIComponent(id)}`, { answers })
export const getTeam = () => call<Team>('GET', '/api/team')
export const pullGacha = () => call<Record<string, unknown>>('POST', '/api/gacha/pull')
const bossQ = (id?: string) => (id ? `?id=${encodeURIComponent(id)}` : '')
export const getBoss = (id?: string) => call<BossInfo>('GET', `/api/boss${bossQ(id)}`)
export const attemptBoss = (id?: string) => call<BossResult>('POST', `/api/boss/attempt${bossQ(id)}`)
export const weeklyBrief = (topic: string, format: string) =>
  call<{ brief: string }>('POST', '/api/weekly/brief', { topic, format })
export const weeklyImport = (path: string) => call<{ module_id: string }>('POST', '/api/weekly/import', { path })

export const terminalUrl = () => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/terminal`
export interface Episode { file: string; title: string; minutes: number; listened?: number; module?: string }
export const getPodcast = () => call<Episode[]>('GET', '/api/podcast')
export const podcastUrl = (file: string) => `/api/podcast/${encodeURIComponent(file)}`
export const ficheAudioUrl = (moduleId: string) => `/api/fiche-audio/${encodeURIComponent(moduleId)}.mp3`
export interface Revision { items: number; key: string | null }
export const getRevision = () => call<Revision>('GET', '/api/revision')
export const revisionUrl = (key: string) => `/api/revision/${encodeURIComponent(key)}.mp3`
export const podcastDone = (file: string) => call<Ok>('POST', `/api/podcast/${encodeURIComponent(file)}/done`)
export const revisionDone = () => call<{ xp: number }>('POST', '/api/revision/done')
export interface Retention { answered7: number; rate7: number | null; solid: number; weak: number; summary?: string }
export const getRetention = () => call<Retention>('GET', '/api/retention')
export interface OralItem { kind: 'card' | 'qcm'; id: string; prompt: string }
export const getOral = () => call<{ items: OralItem[] }>('GET', '/api/oral')
export interface OralResult { correct: boolean; answer: string; explain: string }
export const answerOral = (kind: OralItem['kind'], id: string, transcript: string) =>
  call<OralResult>('POST', '/api/oral/answer', { kind, id, transcript })
export const addPanne = (symptom: string, cause: string, fix: string) => call<{ id: string }>('POST', '/api/cards/panne', { symptom, cause, fix })
export interface Mission { id: string; module: string; title: string; goal: string; steps: string[]; checkable: boolean; done: boolean; proof: string | null; ready: boolean }
export const getMissions = () => call<Mission[]>('GET', '/api/missions')
export const checkMission = (id: string) => call<{ passed: boolean; output: string; xp: number }>('POST', `/api/missions/${encodeURIComponent(id)}/check`)
export const proveMission = (id: string, proof: string) => call<{ xp: number }>('POST', `/api/missions/${encodeURIComponent(id)}/done`, { proof })
export interface Article { id: string; title: string; text: string; unlocked: boolean }
export const getArticles = () => call<Article[]>('GET', '/api/articles')
export const saveArticle = (id: string, text: string) => call<{ xp: number; words: number }>('PUT', `/api/articles/${encodeURIComponent(id)}`, { text })
export interface Cert { key: string | null; date: string | null; title: string | null; days_left: number | null; options: { key: string; title: string }[] }
export const getCert = () => call<Cert>('GET', '/api/cert')
export const setCert = (key: string | null, date: string | null) => call<Ok>('POST', '/api/cert', { key, date })
