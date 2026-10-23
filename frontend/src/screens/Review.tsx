import { useEffect, useState } from 'react'
import { answerQcm, getReviews, type QcmResult, type Reviews } from '../api'

// Leitner boxes: a wrong answer sends a question to box 1, right answers climb up to mastery.
export default function Review({ onOpen }: { onOpen: (lessonId: string) => void }) {
  const [data, setData] = useState<Reviews | null>(null)
  const [err, setErr] = useState('')
  const [i, setI] = useState(0)
  const [res, setRes] = useState<{ chosen: number; r: QcmResult } | null>(null)
  const [right, setRight] = useState(0)
  const [busy, setBusy] = useState(false)
  const [aerr, setAerr] = useState('')
  const [tries, setTries] = useState(0) // bump to reload

  useEffect(() => {
    setErr(''); setData(null)
    getReviews().then(setData).catch((e: Error) => setErr(e.message || 'Erreur'))
  }, [tries])

  if (err) {
    return (
      <section className="screen wrap">
        <p className="note" role="alert">Impossible de charger les révisions : {err}</p>
        <button className="btn ghost" onClick={() => setTries((n) => n + 1)}>Réessayer</button>
      </section>
    )
  }
  if (!data) return <section className="screen wrap"><p className="note">Chargement…</p></section>

  const qs = data.questions
  const q = qs[i]
  const boxes = (
    <div className="card">
      <p className="tag">Boîtes Leitner</p>
      <div className="row" role="list" aria-label="Boîtes de révision">
        {data.boxes.map((n, b) => (
          <div key={b} className="grow" role="listitem" aria-label={`Boîte ${b + 1} : ${n}`}
            style={{ textAlign: 'center', borderBottom: `2px solid ${q?.box === b ? 'var(--gold)' : 'var(--line)'}` }}>
            <div className="stat">{n}</div>
            <div className="time">B{b + 1} · {data.intervals[b]} j</div>
          </div>
        ))}
      </div>
    </div>
  )

  if (qs.length === 0) {
    return (
      <section className="screen wrap">
        <h1>Révisions</h1>
        <p className="card">Rien à réviser aujourd'hui</p>
        {boxes}
      </section>
    )
  }

  if (!q) {
    return (
      <section className="screen wrap">
        <h1>Séance terminée</h1>
        <div className="card" role="status">
          <h2>{right} / {qs.length} correctes</h2>
          <p className="note">{right === qs.length ? 'Sans faute, bravo !' : 'Les erreurs reviennent dans la boîte 1.'}</p>
        </div>
        <button className="btn" onClick={() => { setI(0); setRight(0); setRes(null); setTries((n) => n + 1) }}>Actualiser</button>
      </section>
    )
  }

  const pick = (c: number) => {
    setBusy(true)
    answerQcm(q.id, c)
      .then((r) => { setRes({ chosen: c, r }); setAerr(''); if (r.correct) setRight((n) => n + 1) })
      .catch((e: Error) => setAerr(e.message || 'Erreur'))
      .finally(() => setBusy(false))
  }

  return (
    <section className="screen wrap">
      <h1>Révisions</h1>
      <p className="stat">{qs.length} à réviser · question {i + 1} / {qs.length}</p>
      {boxes}
      <div className="card">
        <p>{q.text}</p>
        {q.options.map((o, c) => (
          <button key={c} className={'opt' + (res && res.chosen === c ? (res.r.correct ? ' right' : ' wrong') : '')}
            disabled={busy || !!res} onClick={() => pick(c)}>{o}</button>
        ))}
        {res && (
          <div className={'fb' + (res.r.correct ? ' ok' : '')} role="status">
            <p>{res.r.correct ? 'Correct.' : 'Raté.'} {res.r.explanation}</p>
            {res.r.remedial_lesson_id && (
              <button className="btn ghost" onClick={() => onOpen(res.r.remedial_lesson_id!)}>Ouvrir la mini-leçon</button>
            )}
          </div>
        )}
      </div>
      {aerr && <p className="note" role="alert">{aerr}</p>}
      {res && <button className="btn" onClick={() => { setI(i + 1); setRes(null) }}>{i + 1 < qs.length ? 'Question suivante' : 'Terminer'}</button>}
    </section>
  )
}
