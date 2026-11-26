import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  answerQcm, audioUrl, getGlossary, markUnclear, rephrase, type GlossEntry, checkTp, realTp, completeStep, getHint, getLesson, getFiche, getLessons, isForbidden, startTp,
  type Lesson as L, type LessonIndex, type QcmResult, type StepKind,
} from '../api'
import { renderLesson } from '../renderLesson'
import { bestPage, speakable, splitPages } from '../pages'
import { pause, say } from '../speech'
import { download, ficheHtml } from '../fiche'
import Feynman from './Feynman'
import Keys from './Keys'
import Confidence, { sureWrongNote } from './Confidence'
// xterm (~300 ko) chargé seulement quand un TP ouvre le terminal : l'appli démarre plus vite sur téléphone
const Terminal = lazy(() => import('./Terminal'))

const RATES = [1, 1.5, 2]
// repère d'une page : sa première ligne de texte (titre de section le plus souvent), retrouvée ensuite par bestPage
const excerpt = (md: string) => (md.split('\n').find((l) => l.trim()) ?? '').replace(/^#+\s*/, '').trim().slice(0, 200)
const THINK_MS = 6000 // temps de réflexion après une question lue

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
  const [sure, setSure] = useState<boolean | null>(null)
  const pick = (i: number) =>
    answerQcm(q.id, i, sure).then((r) => { setRes({ chosen: i, r }); setErr(''); onAnswered() }).catch((e: Error) => setErr(e.message))
  return (
    <div className="card">
      <p>{q.text}</p>
      {!res && <Confidence value={sure} onChange={setSure} />}
      {q.options.map((o, i) => (
        <button key={i} className={'opt' + (res && res.chosen === i ? (res.r.correct ? ' right' : ' wrong') : '')}
          disabled={!!res} onClick={() => pick(i)}>{o}</button>
      ))}
      {res && (
        <div className={'fb' + (res.r.correct ? ' ok' : '')} role="status">
          <p>{res.r.correct ? 'Correct.' : 'Raté.'} {res.r.explanation}</p>
          {res.r.sure_wrong && <p><strong>{sureWrongNote}</strong></p>}
          {res.r.remedial_lesson_id && (
            <button className="btn ghost" onClick={() => onOpen(res.r.remedial_lesson_id!)}>Ouvrir la mini-leçon</button>
          )}
        </div>
      )}
      {err && <p className="note" role="alert">{err}</p>}
    </div>
  )
}

// Questions avant la lecture : deviner, même faux, prépare le cerveau à repérer les réponses. Rien n'est noté.
function PreQuestions({ qs }: { qs: L['qcm'] }) {
  const [open, setOpen] = useState(true)
  const [picked, setPicked] = useState<Record<string, number>>({})
  if (!open) return null
  return (
    <div className="card">
      <p className="tag">Avant de lire · pas noté</p>
      <p className="note">Devine, même au hasard : chercher la réponse pendant la lecture fait mieux retenir.</p>
      {qs.slice(0, 3).map((q) => (
        <div key={q.id}>
          <p>{q.text}</p>
          {q.options.map((o, i) => (
            <button key={i} className="opt" aria-pressed={picked[q.id] === i} style={picked[q.id] === i ? { borderColor: 'var(--gold)' } : undefined}
              onClick={() => setPicked((p) => ({ ...p, [q.id]: i }))}>{o}</button>
          ))}
        </div>
      ))}
      <button className="btn ghost" onClick={() => setOpen(false)}>J'ai deviné, je lis la leçon</button>
    </div>
  )
}

function Catalog({ onOpen }: { onOpen: (id: string) => void }) {
  const [mods, setMods] = useState<LessonIndex[] | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => { getLessons().then(setMods).catch((e: Error) => setErr(e.message)) }, [])
  const saveFiches = (ids: string[], name: string) =>
    Promise.all(ids.map(getFiche))
      .then((fs) => download(name, ficheHtml('Fiches de révision', fs)))
      .catch((e: Error) => setErr(e.message))
  if (err) return <section className="screen wrap"><p className="note" role="alert">{err}</p></section>
  if (!mods) return <section className="screen wrap"><p className="note">Chargement…</p></section>
  return (
    <section className="screen wrap">
      <h1>Leçons</h1>
      {mods.some((m) => m.fiche) && (
        <button className="btn" onClick={() => saveFiches(mods.filter((m) => m.fiche).map((m) => m.id), 'fiches-revision.html')}>
          Télécharger toutes les fiches de révision
        </button>
      )}
      {mods.map((m) => (
        <div className="card" key={m.id}>
          <h2>{m.title}</h2>
          {m.fiche && (
            <button className="btn ghost" onClick={() => saveFiches([m.id], `fiche-${m.id}.html`)}>Fiche de révision ⬇</button>
          )}
          {m.lessons.map((l) => (
            <button key={l.id} className="btn ghost" onClick={() => onOpen(l.id)}>{l.title} · {l.minutes} min</button>
          ))}
        </div>
      ))}
    </section>
  )
}

interface Props {
  id: string | null
  kind?: StepKind | null // step kind the lesson was opened from
  done?: boolean // server-side done state of that step
  focus?: string // ouverte depuis une erreur : aller à la page qui explique ceci
  onOpen: (id: string) => void
}

export default function Lesson({ id, kind, done: initiallyDone, focus, onOpen }: Props) {
  const [les, setLes] = useState<L | null>(null)
  const [loadErr, setLoadErr] = useState('')
  const [banner, setBanner] = useState('') // action errors: shown above content, content stays
  const [local, setLocal] = useState(true) // false once the API/terminal answers 403 (phone/remote)
  const [hint, setHint] = useState('')
  const [level, setLevel] = useState(1)
  const [check, setCheck] = useState<{ passed: boolean; output: string } | null>(null)
  const [real, setReal] = useState<{ passed: boolean; output: string } | null>(null)
  const [done, setDone] = useState<string[]>(initiallyDone && kind ? [kind] : [])
  const [answered, setAnswered] = useState(0)
  const [busy, setBusy] = useState(false)
  const denied = useCallback(() => setLocal(false), [])
  const [dir, setDir] = useState('.') // TP sub-directory of the workspace, from /start
  const tpId = les?.tp?.id
  // lecture par pages courtes, une question du QCM entre deux pages ; « tout sur une page » reste possible
  const [page, setPage] = useState<number | null>(null) // null : page sauvegardée de cette leçon
  const [whole, setWhole] = useState(() => { try { return localStorage.getItem('lecture-entiere') === '1' } catch { return false } })
  const showPage = (n: number) => {
    setPage(n)
    window.scrollTo(0, 0)
    try { if (les) localStorage.setItem(`page:${les.id}`, String(n)) } catch { /* facultatif */ }
  }
  const goPage = (n: number) => {
    if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel()
    setReading(false)
    all.current = false
    setReadingAll(false)
    setPage(n)
    window.scrollTo(0, 0)
    try { if (les) localStorage.setItem(`page:${les.id}`, String(n)) } catch { /* facultatif */ }
  }
  const [reading, setReading] = useState(false)
  const [other, setOther] = useState<{ page: number; text: string } | null>(null) // « explique autrement »
  const [otherBusy, setOtherBusy] = useState(false)
  const [gloss, setGloss] = useState<Record<string, GlossEntry>>({})
  const [term, setTerm] = useState<{ page: number; e: GlossEntry } | null>(null) // terme en gras touché
  useEffect(() => { getGlossary().then(setGloss).catch(() => {}) }, [])
  const onTerm = (page: number, el: EventTarget) => {
    const t = (el as HTMLElement).closest?.('strong')?.textContent?.trim().toLowerCase()
    const e = t ? gloss[t] : undefined
    if (e) setTerm(term?.e === e ? null : { page, e })
  }
  const [flagged, setFlagged] = useState<Set<number>>(new Set()) // pages notées « pas claires »
  const [readingAll, setReadingAll] = useState(false)
  const all = useRef(false)
  const canSpeak = typeof speechSynthesis !== 'undefined'
  const readAloud = (md: string) => {
    speechSynthesis.cancel()
    if (reading) return setReading(false)
    const u = new SpeechSynthesisUtterance(speakable(md))
    u.lang = 'fr-FR'
    u.onend = () => setReading(false)
    u.onerror = () => setReading(false)
    setReading(true)
    speechSynthesis.speak(u)
  }
  // lecture continue : page, puis sa question (options lues, temps de réflexion), page suivante… mains libres
  const readAll = async (pages: string[], from: number) => {
    if (all.current) { all.current = false; setReadingAll(false); speechSynthesis.cancel(); return }
    all.current = true
    setReadingAll(true)
    for (let i = from; i < pages.length && all.current; i++) {
      showPage(i)
      await say(speakable(pages[i]))
      const q = les?.qcm[i]
      if (all.current && q && i < pages.length - 1) {
        await say(`Question : ${q.text} ${q.options.map((o, k) => `${'ABCDEF'[k]} : ${o}`).join('. ')}. Réfléchis.`)
        await pause(THINK_MS)
      }
    }
    if (all.current) await say('Fin de la leçon. Réponds au QCM pour la valider.')
    all.current = false
    setReadingAll(false)
  }
  const toggleWhole = () => { setWhole(!whole); try { localStorage.setItem('lecture-entiere', whole ? '0' : '1') } catch { /* facultatif */ } }
  useEffect(() => () => { all.current = false; if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel() }, []) // quitter la leçon coupe la lecture

  useEffect(() => {
    // once per TP; 403 means the terminal is hidden anyway
    if (tpId && local) startTp(tpId).then((r) => setDir(r.dir)).catch((e) => { if (isForbidden(e)) setLocal(false) })
  }, [tpId, local])

  useEffect(() => {
    // state reset per lesson comes from the parent's key
    if (id) getLesson(id).then(setLes).catch((e: Error) => setLoadErr(e.message))
  }, [id])

  useEffect(() => {
    // reprise de lecture : on revient à l'endroit où on s'était arrêté dans cette leçon
    if (!les) return
    const key = `scroll:${les.id}`
    try { const y = Number(localStorage.getItem(key)); if (y > 0) window.scrollTo(0, y) } catch { /* stockage indisponible */ }
    let t = 0
    const onScroll = () => {
      clearTimeout(t)
      t = window.setTimeout(() => { try { localStorage.setItem(key, String(Math.round(window.scrollY))) } catch { /* idem */ } }, 300)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => { clearTimeout(t); window.removeEventListener('scroll', onScroll) }
  }, [les])

  const [order, setOrder] = useState<{ id: string; title: string }[]>([]) // catalogue order, for prev/next
  useEffect(() => {
    if (id) getLessons().then((ms) => setOrder(ms.flatMap((m) => m.lessons))).catch(() => {}) // nav is optional
  }, [id])

  if (!id) return <Catalog onOpen={onOpen} />
  if (loadErr) return <section className="screen wrap"><p className="note" role="alert">{loadErr}</p></section>
  if (!les) return <section className="screen wrap"><p className="note">Chargement…</p></section>

  const mark = (k: StepKind) =>
    completeStep(k, les.id)
      .then(() => { setBanner(''); setDone((d) => (d.includes(k) ? d : [...d, k])) })
      .catch((e: Error) => setBanner(e.message))
  const guard = (e: unknown) => { if (isForbidden(e)) setLocal(false); else setBanner((e as Error).message) }
  const run = (p: () => Promise<unknown>) => { setBusy(true); p().finally(() => setBusy(false)) }
  const tp = les.tp
  const pages = splitPages(les.body_md)
  const last = pages.length - 1
  const saved = () => { try { return Number(localStorage.getItem(`page:${les.id}`)) || 0 } catch { return 0 } }
  const cur = Math.max(0, Math.min(page ?? (focus ? bestPage(pages, focus) : saved()), last))
  const at = order.findIndex((l) => l.id === les.id) // -1 for remedial lessons outside the catalogue
  const prev = at > 0 ? order[at - 1] : null
  const next = at >= 0 && at < order.length - 1 ? order[at + 1] : null

  return (
    <section className="screen wrap">
      {banner && <p className="fb" role="alert">{banner}</p>}
      <h1>{les.title}</h1>
      <p className="time">{les.minutes} min</p>
      {les.qcm.length > 0 && !done.includes('lesson') && (!kind || kind === 'lesson') && <PreQuestions qs={les.qcm} />}
      <Audio id={les.id} />
      {pages.length > 1 && (
        <div className="row between">
          <span className="stat">{whole ? `${pages.length} parties` : `Page ${cur + 1} / ${pages.length}`}</span>
          <span className="row">
            {canSpeak && !whole && !readingAll && (
              <button className="chip" aria-pressed={reading} onClick={() => readAloud(pages[cur])}>{reading ? '■ Stop' : '🔊 Écouter'}</button>
            )}
            {canSpeak && !whole && !reading && (
              <button className="chip" aria-pressed={readingAll} onClick={() => readAll(pages, cur)}>{readingAll ? '■ Stop' : '▶ Tout lire'}</button>
            )}
            <button className="chip" onClick={toggleWhole}>{whole ? 'Lire par pages' : 'Tout sur une page'}</button>
          </span>
        </div>
      )}
      {/* dangerouslySetInnerHTML only ever receives renderLesson output (escape-first) */}
      {pages.map((md, i) => (
        <div key={i} hidden={!whole && i !== cur}>
          {/* toucher un terme en gras : sa définition, même si elle vient d'une autre leçon */}
          <div className="card course" onClick={(e) => onTerm(i, e.target)} dangerouslySetInnerHTML={{ __html: renderLesson(md) }} />
          {term?.page === i && (
            <div className="fb ok" role="status">
              <p><b>{term.e.term}</b> : {term.e.sentence}</p>
              {term.e.lesson_id !== les.id
                ? <button className="chip" onClick={() => onOpen(term.e.lesson_id)}>Vu dans « {term.e.title} » →</button>
                : <p className="time">Défini dans cette leçon.</p>}
            </div>
          )}
          {!whole && i === cur && (
            other?.page === i ? <div className="fb ok" role="status"><p className="tag">Autrement dit</p><p>{other.text}</p></div> : (
              <button className="btn ghost" disabled={otherBusy} onClick={() => {
                setOtherBusy(true)
                rephrase(les.id, md).then((r) => setOther({ page: i, text: r.text }))
                  .catch((e: Error) => setBanner(e.message)).finally(() => setOtherBusy(false))
              }}>{otherBusy ? 'Reformulation…' : 'Pas clair ? Explique autrement'}</button>
            ))}
          {!whole && i === cur && (flagged.has(i) ? <p className="time">Notée : elle reviendra dans « Semaine ».</p> : (
            <button className="chip" onClick={() => markUnclear(les.id, excerpt(md))
              .then(() => setFlagged(new Set([...flagged, i]))).catch((e: Error) => setBanner(e.message))}>👎 Pas clair</button>
          ))}
          {!whole && i < last && les.qcm[i] && <p className="tag">Vérifie avant de continuer</p>}
        </div>
      ))}
      {/* toutes les questions restent montées (réponses conservées) ; en lecture par pages, la question i suit la page i */}
      {les.qcm.map((q, i) => (
        <div key={q.id} hidden={!whole && (i < last ? i !== cur : cur !== last)}>
          <Qcm q={q} onOpen={onOpen} onAnswered={() => setAnswered((n) => n + 1)} />
        </div>
      ))}
      {!whole && cur < last && (
        <div className="row">
          {cur > 0 && <button className="btn ghost" onClick={() => goPage(cur - 1)}>← Page précédente</button>}
          <button className="btn grow" onClick={() => goPage(cur + 1)}>Page suivante →</button>
        </div>
      )}
      {(whole || cur === last) && (
        <>
          <Keys lessonId={les.id} />
          {!whole && cur > 0 && <button className="btn ghost" onClick={() => goPage(cur - 1)}>← Page précédente</button>}
          <button className="btn" disabled={done.includes('lesson')} onClick={() => mark('lesson')}>
            {done.includes('lesson') ? 'Leçon terminée' : 'Terminer la leçon'}
          </button>
        </>
      )}
      {les.qcm.length > 0 && (whole || cur === last) && (
        <button className="btn ghost" disabled={done.includes('qcm') || answered < les.qcm.length} onClick={() => mark('qcm')}>
          {done.includes('qcm') ? 'QCM validé' : 'Valider le QCM'}
        </button>
      )}
      {tp && (whole || cur === last) && (
        <>
          <h2>TP : {tp.title}</h2>
          <div className="card course" dangerouslySetInnerHTML={{ __html: renderLesson(tp.instructions_md) }} />
          {local ? (
            <>
              {dir !== '.' && <p className="note">Dans le terminal : cd {dir}</p>}
              <Suspense fallback={<p className="note">Chargement du terminal…</p>}><Terminal onDenied={denied} /></Suspense>
              <div className="row wrapf">
                <button className="btn term" disabled={busy} onClick={() => run(() =>
                  checkTp(tp.id).then((r) => { setCheck(r); if (r.passed) return mark('tp') }).catch(guard))}>Vérifier</button>
                <button className="btn ghost" disabled={busy} onClick={() => run(() =>
                  getHint(tp.id, level).then((h) => { setHint(h.hint); setLevel(level + 1) }).catch(guard))}>Indice (-10 XP)</button>
                {tp.real && <button className="btn ghost" disabled={busy} onClick={() => run(() =>
                  realTp(tp.id).then(setReal).catch(guard))}>Vrais outils</button>}
              </div>
            </>
          ) : <p className="note">Le terminal et la vérification sont réservés à l'ordinateur.</p>}
          {hint && <p className="out" role="status">{hint}</p>}
          {check && <><p>{check.passed ? 'TP validé.' : 'TP non validé.'}</p><pre className="out">{check.output}</pre></>}
          {real && <><p>{real.passed ? 'Les vrais outils acceptent votre travail.' : 'Labo réel : à corriger (ou outil absent).'}</p><pre className="out">{real.output}</pre></>}
        </>
      )}
      {local && (whole || cur === last) && <Feynman lessonId={les.id} title={les.title} />}
      {kind === 'bonus' && (
        <button className="btn" disabled={done.includes('bonus')} onClick={() => mark('bonus')}>
          {done.includes('bonus') ? 'Bonus terminé' : 'Terminer le bonus'}
        </button>
      )}
      {(prev || next) && (
        <nav className="row wrapf" aria-label="Navigation entre leçons">
          {prev && <button className="btn ghost" onClick={() => onOpen(prev.id)}>← {prev.title}</button>}
          {next && <button className="btn" onClick={() => onOpen(next.id)}>Leçon suivante : {next.title} →</button>}
        </nav>
      )}
    </section>
  )
}
