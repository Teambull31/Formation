import { useCallback, useEffect, useState } from 'react'
import { getPlan, markPlanDay, startPlan, type Plan as P } from '../api'

// Parcours de 30 jours : le jour courant en tête de la quête, le détail sur demande.
export default function Plan({ onStart }: { onStart: (lessonId: string) => void }) {
  const [plan, setPlan] = useState<P | null>(null)
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState('')
  const load = useCallback(() => { getPlan().then(setPlan).catch((e: Error) => setMsg(e.message)) }, [])
  useEffect(load, [load])
  const act = (p: Promise<unknown>) => p.then(load).catch((e: Error) => setMsg(e.message))

  if (!plan || plan.days.length === 0) return msg ? <p className="note" role="alert">{msg}</p> : null
  const total = plan.days.length
  const doneCount = plan.days.filter((d) => d.done).length

  if (!plan.started) {
    return (
      <div className="card">
        <p className="tag">Parcours DevOps en {total} jours</p>
        <p>CI/CD, Docker, Kubernetes, Terraform, Ansible et un projet fil rouge, avec un objectif clair chaque jour.</p>
        <button className="btn" onClick={() => act(startPlan())}>Commencer aujourd'hui</button>
      </div>
    )
  }
  const n = Math.min(Math.max(plan.today ?? 1, 1), total)
  const day = plan.days[n - 1]
  const finished = (plan.today ?? 0) > total
  const row = (d: P['days'][number]) => (
    <div className="step" key={d.day}>
      <span className={'dot' + (d.done ? ' done' : '')} aria-hidden>{d.done ? '✓' : ''}</span>
      <div className="grow">
        <div>J{d.day} · {d.title}</div>
        <div className="time">{[...d.lessons, ...d.todo].join(' · ')}</div>
      </div>
      {d.lessons.length === 0 && (
        <button className="chip" aria-pressed={d.manual} onClick={() => act(markPlanDay(d.day, !d.manual))}>{d.manual ? 'Fait' : 'Marquer fait'}</button>
      )}
    </div>
  )
  return (
    <div className="card">
      <p className="tag">Parcours · {doneCount} / {total} jours faits{plan.late ? ` · ${plan.late} jour(s) en retard` : ''}</p>
      <h3>{finished ? 'Parcours terminé : place aux examens finaux et au portfolio' : `Jour ${n} / ${total} : ${day.title}`}</h3>
      {!finished && (
        <>
          {day.lessons.map((lid) => (
            <button key={lid} className="btn ghost" onClick={() => onStart(lid)}>Ouvrir la leçon {lid}</button>
          ))}
          {day.lessons.length > 0 ? day.todo.map((t) => <p key={t} className="note">{t}</p>) : row(day)}
        </>
      )}
      <div className="row">
        <button className="chip" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Masquer le plan' : 'Voir les 30 jours'}</button>
        <button className="chip" onClick={() => { if (window.confirm('Recommencer le parcours au jour 1 ?')) act(startPlan()) }}>Recommencer</button>
      </div>
      {open && plan.days.map(row)}
      {msg && <p className="note" role="status">{msg}</p>}
    </div>
  )
}
