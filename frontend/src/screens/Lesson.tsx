import { useCallback, useEffect, useRef, useState } from 'react'
import {
  answerQcm, audioUrl, checkTp, completeStep, getHint, getLesson, isForbidden, startTp,
  type Lesson as L, type QcmResult, type StepKind,
} from '../api'
import { renderLesson } from '../renderLesson'
import Feynman from './Feynman'
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

function Qcm({ q, onOpen, onAnswered }: { q: L['qcm'][number]; onOpen: (id: string) => void; onAnswered: () => void }) {
  const [res, setRes] = useState<{ chosen: number; r: QcmResult } | null>(null)
  const [err, setErr] = useState('')
  const pick = (i: number) =>
    answerQcm(q.id, i).then((r) => { setRes({ chosen: i, r }); setErr(''); onAnswered() }).catch((e: Error) => setErr(e.message))
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
      {err && <p className="note" role="alert">{err}</p>}
    </div>
  )
}

interface Props {
  id: string | null
  kind?: StepKind | null // step kind the lesson was opened from
  done?: boolean // server-side done state of that step
  onOpen: (id: string) => void
}

export default function Lesson({ id, kind, done: initiallyDone, onOpen }: Props) {
  const [les, setLes] = useState<L | null>(null)
  const [loadErr, setLoadErr] = useState('')
  const [banner, setBanner] = useState('') // action errors: shown above content, content stays
  const [local, setLocal] = useState(true) // false once the API/terminal answers 403 (phone/remote)
  const [hint, setHint] = useState('')
  const [level, setLevel] = useState(1)
  const [check, setCheck] = useState<{ passed: boolean; output: string } | null>(null)
  const [done, setDone] = useState<string[]>(initiallyDone && kind ? [kind] : [])
  const [answered, setAnswered] = useState(0)
  const [busy, setBusy] = useState(false)
  const denied = useCallback(() => setLocal(false), [])
  const [dir, setDir] = useState('.') // TP sub-directory of the workspace, from /start
  const tpId = les?.tp?.id

  useEffect(() => {
    // once per TP; 403 means the terminal is hidden anyway
    if (tpId && local) startTp(tpId).then((r) => setDir(r.dir)).catch((e) => { if (isForbidden(e)) setLocal(false) })
  }, [tpId, local])

  useEffect(() => {
    // state reset per lesson comes from the parent's key
    if (id) getLesson(id).then(setLes).catch((e: Error) => setLoadErr(e.message))
  }, [id])

  if (!id) return <section className="screen wrap"><p className="note">Choisis une étape dans la quête pour ouvrir une leçon.</p></section>
  if (loadErr) return <section className="screen wrap"><p className="note" role="alert">{loadErr}</p></section>
  if (!les) return <section className="screen wrap"><p className="note">Chargement…</p></section>

  const mark = (k: StepKind) =>
    completeStep(k, les.id)
      .then(() => { setBanner(''); setDone((d) => (d.includes(k) ? d : [...d, k])) })
      .catch((e: Error) => setBanner(e.message))
  const guard = (e: unknown) => { if (isForbidden(e)) setLocal(false); else setBanner((e as Error).message) }
  const run = (p: () => Promise<unknown>) => { setBusy(true); p().finally(() => setBusy(false)) }
  const tp = les.tp

  return (
    <section className="screen wrap">
      {banner && <p className="fb" role="alert">{banner}</p>}
      <h1>{les.title}</h1>
      <p className="time">{les.minutes} min</p>
      <Audio id={les.id} />
      {/* dangerouslySetInnerHTML only ever receives renderLesson output (escape-first) */}
      <div className="card course" dangerouslySetInnerHTML={{ __html: renderLesson(les.body_md) }} />
      <button className="btn" disabled={done.includes('lesson')} onClick={() => mark('lesson')}>
        {done.includes('lesson') ? 'Leçon terminée' : 'Terminer la leçon'}
      </button>
      {les.qcm.length > 0 && <h2>QCM</h2>}
      {les.qcm.map((q) => <Qcm key={q.id} q={q} onOpen={onOpen} onAnswered={() => setAnswered((n) => n + 1)} />)}
      {les.qcm.length > 0 && (
        <button className="btn ghost" disabled={done.includes('qcm') || answered < les.qcm.length} onClick={() => mark('qcm')}>
          {done.includes('qcm') ? 'QCM validé' : 'Valider le QCM'}
        </button>
      )}
      {tp && (
        <>
          <h2>TP : {tp.title}</h2>
          <div className="card course" dangerouslySetInnerHTML={{ __html: renderLesson(tp.instructions_md) }} />
          {local ? (
            <>
              {dir !== '.' && <p className="note">Dans le terminal : cd {dir}</p>}
              <Terminal onDenied={denied} />
              <div className="row wrapf">
                <button className="btn term" disabled={busy} onClick={() => run(() =>
                  checkTp(tp.id).then((r) => { setCheck(r); if (r.passed) return mark('tp') }).catch(guard))}>Vérifier</button>
                <button className="btn ghost" disabled={busy} onClick={() => run(() =>
                  getHint(tp.id, level).then((h) => { setHint(h.hint); setLevel(level + 1) }).catch(guard))}>Indice (-10 XP)</button>
              </div>
            </>
          ) : <p className="note">Le terminal et la vérification sont réservés à l'ordinateur.</p>}
          {hint && <p className="out" role="status">{hint}</p>}
          {check && <><p>{check.passed ? 'TP validé.' : 'TP non validé.'}</p><pre className="out">{check.output}</pre></>}
        </>
      )}
      {local && <Feynman lessonId={les.id} title={les.title} />}
      {kind === 'bonus' && (
        <button className="btn" disabled={done.includes('bonus')} onClick={() => mark('bonus')}>
          {done.includes('bonus') ? 'Bonus terminé' : 'Terminer le bonus'}
        </button>
      )}
    </section>
  )
}
