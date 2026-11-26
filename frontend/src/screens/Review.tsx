import { useEffect, useState } from 'react'
import { answerQcm, getReviews, type QcmResult, type Reviews } from '../api'
import { correction, optClass } from '../qcm'
import Confidence, { sureWrongNote } from './Confidence'

// Leitner boxes: a wrong answer sends a question to box 1, right answers climb up to mastery.
export default function Review({ onOpen, onContinue }: { onOpen: (lessonId: string, focus?: string) => void; onContinue?: () => void }) {
  const [data, setData] = useState<Reviews | null>(null)
  const [err, setErr] = useState('')
  const [i, setI] = useState(0)
  const [res, setRes] = useState<{ chosen: number; r: QcmResult } | null>(null)
  const [right, setRight] = useState(0)
  const [busy, setBusy] = useState(false)
  const [aerr, setAerr] = useState('')
  const [tries, setTries] = useState(0) // bump to reload
  const [sure, setSure] = useState<boolean | null>(null)
  const [early, setEarly] = useState(false) // « questions d'avance » choisies quand rien n'est dû
  const qs = data ? (data.questions.length ? data.questions : early ? data.ahead ?? [] : []) : []
  const q = qs[i]
  const pick = (c: number) => {
    setBusy(true)
    answerQcm(q.id, c, sure)
      .then((r) => { setRes({ chosen: c, r }); setAerr(''); if (r.correct) setRight((n) => n + 1) })
      .catch((e: Error) => setAerr(e.message || 'Erreur'))
      .finally(() => setBusy(false))
  }
  const next = () => { setI(i + 1); setRes(null); setSure(null) }
  useEffect(() => {
    // clavier : 1 à 6 répond, Entrée passe à la suivante
    const onKey = (e: KeyboardEvent) => {
      if (!q || busy || (e.target as HTMLElement)?.closest?.('input, textarea, select')) return
      const n = Number(e.key)
      if (!res && n >= 1 && n <= q.options.length) pick(n - 1)
      else if (res && e.key === 'Enter') next()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

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

  const boxes = (
    <div className="card">
      <p className="tag">Boîtes Leitner</p>
      <div className="row" role="list" aria-label="Boîtes de révision">
        {data.boxes.map((n, b) => (
          <div key={b} className="grow" role="listitem" aria-label={`Boîte ${b + 1} : ${n}`}
            style={{ textAlign: 'center', borderBottom: `2px solid ${q?.box === b ? 'var(--gold)' : 'var(--line)'}` }}>
            <div className="stat">{n}</div>
            <div className="time">{data.intervals[b]} j</div>
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
        {!!data.ahead?.length && (
          <button className="btn term" onClick={() => setEarly(true)}>Réviser {data.ahead.length} question{data.ahead.length > 1 ? 's' : ''} d'avance</button>
        )}
        {onContinue && <button className="btn" onClick={onContinue}>Continuer la séance : cartes →</button>}
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
        {onContinue && <button className="btn" onClick={onContinue}>Continuer la séance : cartes →</button>}
        <button className="btn ghost" onClick={() => { setI(0); setRight(0); setRes(null); setTries((n) => n + 1) }}>Actualiser</button>
      </section>
    )
  }

  return (
    <section className="screen wrap">
      <h1>Révisions</h1>
      <p className="stat">{qs.length} à réviser · question {i + 1} / {qs.length}</p>
      {boxes}
      <div className="card">
        <p>{q.text}</p>
        {!res && <Confidence value={sure} onChange={setSure} />}
        {q.options.map((o, c) => (
          <button key={c} className={optClass(res, c, o)} disabled={busy || !!res} onClick={() => pick(c)}>{o}</button>
        ))}
        {res && (
          <div className={'fb' + (res.r.correct ? ' ok' : '')} role="status">
            <p>{res.r.correct ? 'Correct.' : 'Raté.'}{correction(res.r)} {res.r.explanation}</p>
            {res.r.sure_wrong && <p><strong>{sureWrongNote}</strong></p>}
            {res.r.lesson_id && (
              <button className="btn ghost" onClick={() => onOpen(res.r.lesson_id!, `${q.text} ${res.r.answer ?? ''}`)}>
                Revoir le passage dans la leçon {res.r.lesson_id}
              </button>
            )}
            {res.r.remedial_lesson_id && (
              <button className="btn ghost" onClick={() => onOpen(res.r.remedial_lesson_id!)}>Ouvrir la mini-leçon</button>
            )}
          </div>
        )}
      </div>
      {aerr && <p className="note" role="alert">{aerr}</p>}
      {res && <button className="btn" onClick={next}>{i + 1 < qs.length ? 'Question suivante' : 'Terminer'}</button>}
    </section>
  )
}
