import { useCallback, useEffect, useRef, useState } from 'react'
import Plan from './Plan'
import Cert from './Cert'
import { announceRest, getPushKey, getQuest, getReviews, getTeam, setTopic, type Quest as Q, type Step, type StepKind, type Suggestion, type Team } from '../api'

export type Go = (tab: 'Révisions' | 'Écoute' | 'Équipe' | 'Boss', sub?: 'qcm' | 'cartes' | 'examen' | 'entretien') => void

const LABEL: Record<string, string> = { lesson: 'Leçon', qcm: 'QCM', tp: 'TP', bonus: 'Bonus' }

export default function Quest({ onStart, onGo }: { onStart: (lessonId: string, kind: StepKind, done: boolean) => void; onGo?: Go }) {
  const [quest, setQuest] = useState<Q | null>(null)
  const [team, setTeam] = useState<Team | null>(null)
  const [minutes, setMinutes] = useState<30 | 60>(30)
  const [topic, setTopicText] = useState('')
  const [msg, setMsg] = useState('')
  const [due, setDue] = useState(0)
  const [pushOff, setPushOff] = useState(false)
  useEffect(() => { getReviews().then((r) => setDue(r.questions.length)).catch(() => {}) }, [])
  useEffect(() => { getPushKey().then((k) => setPushOff(!k.subscribed)).catch(() => {}) }, [])

  const req = useRef(0) // request counter: stale responses are ignored
  const load = useCallback((ok = '') => {
    const n = ++req.current
    Promise.all([getQuest(minutes), getTeam()])
      .then(([q, t]) => {
        if (n !== req.current) return
        setQuest(q); setTeam(t); setTopicText(q.imposed_topic ?? ''); setMsg(ok)
      })
      .catch((e: Error) => { if (n === req.current) setMsg(e.message) })
  }, [minutes])
  useEffect(() => load(), [load])

  const act = (p: Promise<unknown>, ok = '') => p.then(() => load(ok)).catch((e: Error) => setMsg(e.message))
  const row = (s: Step) => (
    <div className="step" key={s.kind + s.lesson_id}>
      <span className={'dot' + (s.done ? ' done' : '')} aria-hidden>{s.done ? '✓' : ''}</span>
      <div className="grow">
        <div>{LABEL[s.kind]} · {s.lesson_id}</div>
        <div className="time">{s.minutes} min · +{s.xp} XP{s.done ? ' · fait' : ''}</div>
      </div>
      <button className="btn ghost" onClick={() => onStart(s.lesson_id, s.kind, s.done)}>Commencer</button>
    </div>
  )

  const go = (sg: Suggestion) => {
    if (sg.kind === 'feynman') onStart(sg.id, 'lesson', true)
    else if (sg.kind === 'episode') onGo?.('Écoute')
    else if (sg.kind === 'mission') onGo?.('Boss')
    else if (sg.kind === 'article') onGo?.('Équipe')
    else onGo?.('Révisions', sg.kind === 'exam' ? 'examen' : 'entretien')
  }

  // un seul bouton pour démarrer : ce qui vient ensuite (révisions d'abord, puis la première étape pas faite)
  const nextStep = quest?.steps.find((s) => !s.done)
  const reviewFirst = !!(quest?.review && quest.review.due > 0 && !quest.review.done)
  const startSession = () => {
    if (reviewFirst && onGo) onGo('Révisions', due > 0 ? 'qcm' : 'cartes')
    else if (nextStep) onStart(nextStep.lesson_id, nextStep.kind, false)
  }

  return (
    <section className="screen wrap">
      {quest && (reviewFirst || nextStep) && (
        <button className="btn term" style={{ fontSize: 18, minHeight: 56 }} onClick={startSession}>
          ▶ Ma séance du jour{reviewFirst ? ` · ${quest.review!.due} révisions puis ${nextStep ? nextStep.lesson_id : 'fin'}` : ` · ${LABEL[nextStep!.kind]} ${nextStep!.lesson_id}`}
        </button>
      )}
      {pushOff && onGo && (
        <button className="btn ghost" onClick={() => onGo('Équipe')}>🔔 Active le rappel quotidien : c'est la régularité qui fait retenir</button>
      )}
      <div className="card">
        <h3>Quête du jour</h3>
        {quest?.pace === 'consolidate' && (
          <p className="fb">Jour de consolidation conseillé : moins de 60 % de bonnes réponses en révision cette semaine.
            Fais les révisions et réécoute un épisode avant d'avancer.</p>
        )}
        {quest?.pace === 'fast' && <p className="fb ok">Plus de 85 % en révision : tu peux accélérer (format 60 min, leçon bonus).</p>}
        {quest?.review && (
          <div className="step">
            <span className={'dot' + (quest.review.done ? ' done' : '')} aria-hidden>{quest.review.done ? '✓' : ''}</span>
            <div className="grow">
              <div>Révisions du jour · {quest.review.due} à revoir</div>
              <div className="time">5 min · +15 XP{quest.review.done ? ' · fait' : ' · à faire en premier : c\'est ce qui fait retenir'}</div>
            </div>
            {onGo && quest.review.due > 0 && <button className="btn ghost" onClick={() => onGo('Révisions', due > 0 ? 'qcm' : 'cartes')}>Réviser</button>}
          </div>
        )}
        {quest && quest.steps.length === 0 && <p>Module terminé, bravo !</p>}
        {quest?.steps.map(row)}
        {quest?.bonus && <><p className="tag">Bonus</p>{row(quest.bonus)}</>}
      </div>
      {quest && quest.pending_tp.length > 0 && (
        <div className="card">
          <h3>TP à faire sur PC</h3>
          <p className="note">La suite avance sans eux ; garde-les pour une session au PC (le week-end par exemple).</p>
          {quest.pending_tp.map((lid) => (
            <div className="row between" key={lid}>
              <span>TP · {lid}</span>
              <button className="chip" onClick={() => onStart(lid, 'tp', false)}>Ouvrir</button>
            </div>
          ))}
        </div>
      )}
      {quest && quest.suggestions.length > 0 && (
        <div className="card">
          <h3>Pour aller plus loin</h3>
          {quest.suggestions.map((sg) => (
            <button key={sg.kind + sg.id} className="opt" onClick={() => go(sg)}>{sg.label}</button>
          ))}
        </div>
      )}
      {onGo && (
        <button className="btn ghost" onClick={() => onGo('Révisions', 'cartes')}>Fatigué ? Jour minimum : 2 minutes, 3 cartes, et le jour compte</button>
      )}
      <button className="btn ghost" onClick={() => act(announceRest(), 'Repos annoncé.')}>Repos aujourd'hui</button>
      <details className="card">
        <summary>Plan, objectif, profil et réglages{team ? ` · série ${team.streak} j · niveau ${team.level}` : ''}</summary>
        <Plan onStart={(id) => onStart(id, 'lesson', false)} />
        <Cert />
        <div className="card">
          <p className="tag">Rang actuel</p>
          <h2>{team ? team.rank : '…'}</h2>
          {team && <p className="stat">{team.xp} XP · niveau {team.level} · série {team.streak} j</p>}
        </div>
        <div className="card">
          <p className="tag">Format</p>
          <div className="row">
            {([30, 60] as const).map((m) => (
              <button key={m} className="chip" aria-pressed={minutes === m} onClick={() => setMinutes(m)}>{m} min</button>
            ))}
          </div>
          <label className="tag" htmlFor="topic">Sujet imposé</label>
          <div className="row">
            <input id="topic" type="text" className="grow" value={topic} onChange={(e) => setTopicText(e.target.value)} />
            <button className="btn" onClick={() => act(setTopic(topic.trim() || null))}>OK</button>
            <button className="btn ghost" aria-label="Effacer le sujet" onClick={() => { setTopicText(''); act(setTopic(null)) }}>✕</button>
          </div>
        </div>
      </details>
      {msg && <p className="note" role="status">{msg}</p>}
    </section>
  )
}
