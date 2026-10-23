import { useEffect, useRef, useState } from 'react'
import { answerInterview, getInterview, type InterviewQuestion, type InterviewResult } from '../api'

const MIN = 20 // same floor as the API

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

export default function Interview() {
  const [qs, setQs] = useState<InterviewQuestion[] | null>(null)
  const [err, setErr] = useState('')
  const [i, setI] = useState(0)
  const [text, setText] = useState('')
  const [res, setRes] = useState<InterviewResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [left, setLeft] = useState(0)
  const [running, setRunning] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval>>(undefined)

  useEffect(() => {
    getInterview()
      .then((r) => {
        setQs(r.questions)
        // start somewhere random so the same first question does not come back every time
        const start = r.questions.length ? Math.floor(Math.random() * r.questions.length) : 0
        setI(start)
        setLeft(r.questions[start]?.time_limit ?? 0)
      })
      .catch((e: Error) => setErr(e.message || 'Erreur'))
  }, [])

  useEffect(() => {
    if (!running) return
    timer.current = setInterval(() => setLeft((s) => {
      if (s <= 1) { setRunning(false); return 0 }
      return s - 1
    }), 1000)
    return () => clearInterval(timer.current)
  }, [running])

  if (err) return <section className="screen wrap"><p className="note" role="alert">{err}</p></section>
  if (!qs) return <section className="screen wrap"><p className="note">Chargement…</p></section>
  if (qs.length === 0) return <section className="screen wrap"><p className="card">Aucune question d'entretien installée.</p></section>

  const q = qs[i]
  const speak = () => {
    const synth = window.speechSynthesis
    if (!synth) return
    synth.cancel()
    const u = new SpeechSynthesisUtterance(q.question)
    u.lang = 'fr-FR'
    synth.speak(u)
  }
  const go = (n: number) => {
    setI(n); setText(''); setRes(null); setErr(''); setRunning(false); setLeft(qs[n].time_limit)
  }
  const send = () => {
    setBusy(true); setRunning(false)
    answerInterview(q.id, text.trim())
      .then((r) => {
        setRes(r); setErr('')
        setQs((all) => all && all.map((x, k) => (k === i ? { ...x, best: r.best } : x)))
      })
      .catch((e: Error) => setErr(e.message || 'Erreur'))
      .finally(() => setBusy(false))
  }

  return (
    <section className="screen wrap">
      <h1>Entretien</h1>
      <p className="stat">{q.role} · question {i + 1} / {qs.length}{q.best != null ? ` · meilleur score ${q.best}` : ''}</p>
      <div className="card">
        <p>« {q.question} »</p>
        <div className="row wrapf">
          <span className="stat" role="timer" aria-label="Temps restant">{clock(left)}</span>
          <button className="btn ghost" onClick={() => setRunning((r) => !r)}>{running ? 'Pause' : 'Chrono'}</button>
          <button className="btn ghost" onClick={() => { setRunning(false); setLeft(q.time_limit) }}>Remettre</button>
          {'speechSynthesis' in window && <button className="btn ghost" onClick={speak}>Écouter</button>}
        </div>
        <p className="note">Réponds comme à l'oral, en structurant : contexte, idées clés, exemple.</p>
        <textarea className="area" rows={7} value={text} maxLength={4000} aria-label="Ta réponse"
          onChange={(e) => setText(e.target.value)} disabled={!!res} />
        {!res && (
          <button className="btn" disabled={busy || text.trim().length < MIN} onClick={send}>
            {busy ? 'Notation en cours…' : 'Faire noter'}
          </button>
        )}
      </div>
      {err && <p className="note" role="alert">{err}</p>}
      {res && (
        <div className={'fb' + (res.score >= 60 ? ' ok' : '')} role="status">
          <p><strong>{res.score}/100</strong>{res.xp > 0 ? ` · +${res.xp} XP` : ''} · notation : {res.mode}</p>
          <p>{res.feedback}</p>
          {res.missing.length > 0 && (
            <>
              <p>Idées oubliées :</p>
              <ul>{res.missing.map((m, k) => <li key={k}>{m}</li>)}</ul>
            </>
          )}
          <p><strong>Réponse modèle</strong></p>
          <p>{res.model_answer}</p>
        </div>
      )}
      {res && <button className="btn" onClick={() => go((i + 1) % qs.length)}>Question suivante</button>}
    </section>
  )
}
