import { useCallback, useEffect, useRef, useState } from 'react'
import {
  answerQcm, audioUrl, checkTp, completeStep, getHint, getLesson, isForbidden,
  type Lesson as L, type QcmResult,
} from '../api'
import { renderLesson } from '../renderLesson'
import Terminal from './Terminal'

const RATES = [1, 1.5, 2]

function Audio({ id }: { id: string }) {
  const [rate, setRate] = useState(1)
  const el = useRef<HTMLAudioElement>(null)
  const pick = (r: number) => { setRate(r); if (el.current) el.current.playbackRate = r }
  return (
    <div className="card">
      <audio controls preload="none" src={audioUrl(id)} ref={el} />
      <div className="row">
        {RATES.map((r) => (
          <button key={r} className="chip" aria-pressed={rate === r} onClick={() => pick(r)}>{r}x</button>
        ))}
      </div>
    </div>
  )
}

function Qcm({ q, onOpen }: { q: L['qcm'][number]; onOpen: (id: string) => void }) {
  const [res, setRes] = useState<{ chosen: number; r: QcmResult } | null>(null)
  const [err, setErr] = useState('')
  const pick = (i: number) =>
    answerQcm(q.id, i).then((r) => setRes({ chosen: i, r })).catch((e: Error) => setErr(e.message))
  return (
    <div className="card">
      <p>{q.text}</p>
      {q.options.map((o, i) => (
        <button key={i} className={'opt' + (res && res.chosen === i ? (res.r.correct ? ' right' : ' wrong') : '')}
          disabled={!!res} onClick={() => pick(i)}>{o}</button>
      ))}
      {res && (
        <div className={'fb' + (res.r.correct ? ' ok' : '')} role="status">
          <p>{res.r.correct ? 'Correct.' : 'Raté.'} {res.r.explanation}</p>
          {res.r.remedial_lesson_id && (
            <button className="btn ghost" onClick={() => onOpen(res.r.remedial_lesson_id!)}>Ouvrir la mini-leçon</button>
          )}
        </div>
      )}
      {err && <p className="note">{err}</p>}
    </div>
  )
}

export default function Lesson({ id, onOpen }: { id: string | null; onOpen: (id: string) => void }) {
  const [les, setLes] = useState<L | null>(null)
  const [err, setErr] = useState('')
  const [local, setLocal] = useState(true) // false once the API/terminal answers 403 (phone/remote)
  const [hint, setHint] = useState('')
  const [level, setLevel] = useState(1)
  const [check, setCheck] = useState<{ passed: boolean; output: string } | null>(null)
  const [done, setDone] = useState<string[]>([])
  const denied = useCallback(() => setLocal(false), [])

  useEffect(() => {
    // state reset per lesson comes from the parent's key={id}
    if (id) getLesson(id).then(setLes).catch((e: Error) => setErr(e.message))
  }, [id])

  if (!id) return <section className="screen wrap"><p className="note">Choisis une étape dans la quête pour ouvrir une leçon.</p></section>
  if (err) return <section className="screen wrap"><p className="note" role="alert">{err}</p></section>
  if (!les) return <section className="screen wrap"><p className="note">Chargement…</p></section>

  const mark = (kind: 'lesson' | 'qcm' | 'tp') =>
    completeStep(kind, les.id).then(() => setDone((d) => [...d, kind])).catch((e: Error) => setErr(e.message))
  const guard = (e: unknown) => { if (isForbidden(e)) setLocal(false); else setErr((e as Error).message) }
  const tp = les.tp

  return (
    <section className="screen wrap">
      <h1>{les.title}</h1>
      <p className="time">{les.minutes} min</p>
      <Audio id={les.id} />
      {/* dangerouslySetInnerHTML only ever receives renderLesson output (escape-first) */}
      <div className="card course" dangerouslySetInnerHTML={{ __html: renderLesson(les.body_md) }} />
      <button className="btn" disabled={done.includes('lesson')} onClick={() => mark('lesson')}>
        {done.includes('lesson') ? 'Leçon terminée' : 'Terminer la leçon'}
      </button>
      {les.qcm.length > 0 && <h2>QCM</h2>}
      {les.qcm.map((q) => <Qcm key={q.id} q={q} onOpen={onOpen} />)}
      {les.qcm.length > 0 && (
        <button className="btn ghost" disabled={done.includes('qcm')} onClick={() => mark('qcm')}>Valider le QCM</button>
      )}
      {tp && (
        <>
          <h2>TP : {tp.title}</h2>
          <div className="card course" dangerouslySetInnerHTML={{ __html: renderLesson(tp.instructions_md) }} />
          {local ? (
            <>
              <Terminal onDenied={denied} />
              <div className="row wrapf">
                <button className="btn term" onClick={() =>
                  checkTp(tp.id).then((r) => { setCheck(r); if (r.passed) return mark('tp') }).catch(guard)}>Vérifier</button>
                <button className="btn ghost" onClick={() =>
                  getHint(tp.id, level).then((h) => { setHint(h.hint); setLevel(level + 1) }).catch(guard)}>Indice (-10 XP)</button>
              </div>
            </>
          ) : <p className="note">Le terminal et la vérification sont réservés à l'ordinateur.</p>}
          {hint && <p className="out" role="status">{hint}</p>}
          {check && <><p>{check.passed ? 'TP validé.' : 'TP non validé.'}</p><pre className="out">{check.output}</pre></>}
        </>
      )}
    </section>
  )
}
