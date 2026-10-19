import { useCallback, useEffect, useState } from 'react'
import { announceRest, getQuest, getTeam, setTopic, type Quest as Q, type Step, type Team } from '../api'

const LABEL: Record<string, string> = { lesson: 'Leçon', qcm: 'QCM', tp: 'TP', bonus: 'Bonus' }

export default function Quest({ onStart }: { onStart: (lessonId: string) => void }) {
  const [quest, setQuest] = useState<Q | null>(null)
  const [team, setTeam] = useState<Team | null>(null)
  const [minutes, setMinutes] = useState<30 | 60>(30)
  const [topic, setTopicText] = useState('')
  const [msg, setMsg] = useState('')

  const load = useCallback(() => {
    Promise.all([getQuest(minutes), getTeam()])
      .then(([q, t]) => { setQuest(q); setTeam(t); setTopicText(q.imposed_topic ?? ''); setMsg('') })
      .catch((e: Error) => setMsg(e.message))
  }, [minutes])
  useEffect(load, [load])

  const act = (p: Promise<unknown>, ok = '') => p.then(() => { load(); setMsg(ok) }).catch((e: Error) => setMsg(e.message))
  const row = (s: Step) => (
    <div className="step" key={s.kind + s.lesson_id}>
      <span className={'dot' + (s.done ? ' done' : '')} aria-hidden>{s.done ? '✓' : ''}</span>
      <div className="grow">
        <div>{LABEL[s.kind]} · {s.lesson_id}</div>
        <div className="time">{s.minutes} min · +{s.xp} XP{s.done ? ' · fait' : ''}</div>
      </div>
      <button className="btn ghost" onClick={() => onStart(s.lesson_id)}>Commencer</button>
    </div>
  )

  return (
    <section className="screen wrap">
      <div className="card">
        <p className="tag">Rang actuel</p>
        <h2>{team ? team.rank : '…'}</h2>
        {team && <p className="stat">{team.xp} XP · niveau {team.level} · série {team.streak} j</p>}
      </div>
      <div className="card">
        <h3>Quête du jour</h3>
        {quest && quest.steps.length === 0 && <p>Module terminé, bravo !</p>}
        {quest?.steps.map(row)}
        {quest?.bonus && <><p className="tag">Bonus</p>{row(quest.bonus)}</>}
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
      <button className="btn ghost" onClick={() => act(announceRest(), 'Repos annoncé.')}>Repos aujourd'hui</button>
      {msg && <p className="note" role="status">{msg}</p>}
    </section>
  )
}
