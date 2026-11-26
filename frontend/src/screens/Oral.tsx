import { useRef, useState } from 'react'
import { say } from '../speech'
import { answerInterview, answerOral, getInterview, getOral, type OralItem, type OralResult } from '../api'

// Révision orale mains libres : la question est lue, tu réponds à voix haute, le serveur note et range la réponse.
// Synthèse et reconnaissance vocales du navigateur (https obligatoire, micro autorisé).
interface Rec { lang: string; interimResults: boolean; continuous?: boolean; onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null; onerror: (() => void) | null; start(): void; stop(): void }
type RecCtor = new () => Rec
const RecClass = (): RecCtor | undefined => {
  const w = window as unknown as { SpeechRecognition?: RecCtor; webkitSpeechRecognition?: RecCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}
const LISTEN_MS = 9000
const INTERVIEW_MS = 75000 // réponse d'entretien : jusqu'à 75 s de parole
const INTERVIEW_N = 2

function listen(R: RecCtor, ms = LISTEN_MS, continuous = false): Promise<string> {
  return new Promise((done) => {
    const r = new R()
    let text = ''
    r.lang = 'fr-FR'
    r.interimResults = false
    r.continuous = continuous
    r.onresult = (e) => { text = Array.from(e.results, (x) => x[0].transcript).join(' ') }
    r.onend = () => done(text)
    r.onerror = () => done(text)
    r.start()
    setTimeout(() => { try { r.stop() } catch { /* déjà arrêtée */ } }, ms)
  })
}

export default function Oral() {
  const R = RecClass()
  const ok = typeof speechSynthesis !== 'undefined' && !!R
  const on = useRef(false)
  const [running, setRunning] = useState(false)
  const [item, setItem] = useState<OralItem | null>(null)
  const [heard, setHeard] = useState('')
  const [res, setRes] = useState<OralResult | null>(null)
  const [score, setScore] = useState({ right: 0, total: 0 })
  const [msg, setMsg] = useState('')

  const stop = () => { on.current = false; setRunning(false); speechSynthesis.cancel() }
  const start = async () => {
    on.current = true
    setRunning(true); setMsg(''); setScore({ right: 0, total: 0 })
    try {
      const { items } = await getOral()
      if (!items.length) { await say("Rien à réviser aujourd'hui. Bravo."); return stop() }
      await say(`Révision orale : ${items.length} questions. Réponds après la question, à voix haute. Dis « je ne sais pas » pour passer.`)
      let right = 0
      for (const [n, it] of items.entries()) {
        if (!on.current) return
        setItem(it); setHeard(''); setRes(null)
        await say(`Question ${n + 1}. ${it.prompt}`)
        if (!on.current) return
        const t = await listen(R!)
        setHeard(t)
        const r = await answerOral(it.kind, it.id, t)
        setRes(r)
        if (r.correct) right++
        setScore({ right, total: n + 1 })
        await say(r.correct ? 'Juste.' : `Non. La réponse : ${r.answer}. ${r.explain}`)
      }
      await say(`Terminé : ${right} sur ${items.length}.`)
    } catch (e) {
      setMsg((e as Error).message)
    }
    stop()
  }

  // entretien oral : les questions les moins réussies, réponse longue, note et idées manquantes lues
  const interview = async () => {
    on.current = true
    setRunning(true); setMsg(''); setScore({ right: 0, total: 0 })
    try {
      const qs = (await getInterview()).questions.slice().sort((a, b) => (a.best ?? -1) - (b.best ?? -1)).slice(0, INTERVIEW_N)
      await say(`Entretien : ${qs.length} questions. Réponds comme face à un recruteur, tu as environ une minute.`)
      for (const [n, q] of qs.entries()) {
        if (!on.current) return
        setItem({ kind: 'qcm', id: q.id, prompt: q.question }); setHeard(''); setRes(null)
        await say(`Question ${n + 1}. ${q.question}`)
        if (!on.current) return
        const t = await listen(R!, INTERVIEW_MS, true)
        setHeard(t)
        if (t.trim().length < 20) { await say('Réponse trop courte, on passe.'); continue }
        const g = await answerInterview(q.id, t)
        setRes({ correct: g.score >= 70, answer: g.model_answer, explain: '' })
        const missing = g.missing.length ? `Il manquait : ${g.missing.join(', ')}.` : 'Toutes les idées clés y sont.'
        await say(`${g.score} sur 100. ${missing} Réponse type : ${g.model_answer.split('. ').slice(0, 2).join('. ')}.`)
      }
      await say("Fin de l'entretien.")
    } catch (e) {
      setMsg((e as Error).message)
    }
    stop()
  }

  return (
    <div className="card">
      <h3>Révision orale (mains libres)</h3>
      {!ok ? (
        <p className="note">Reconnaissance vocale indisponible ici (il faut Chrome ou Safari, en https). Utilise la révision express audio ci-dessous.</p>
      ) : (
        <>
          <p className="note">Lance-la avant de démarrer, puis ne touche plus l'écran : tout se fait à la voix.</p>
          <button className={'btn' + (running ? ' ghost' : ' term')} onClick={running ? stop : start}>{running ? 'Arrêter' : 'Commencer la révision orale'}</button>
          {!running && <button className="btn ghost" onClick={interview}>Entretien oral ({INTERVIEW_N} questions)</button>}
          {item && <p>{item.prompt}</p>}
          {heard && <p className="note">Entendu : « {heard} »</p>}
          {res && <p className={'fb' + (res.correct ? ' ok' : '')}>{res.correct ? 'Juste.' : `Réponse : ${res.answer}`}</p>}
          {score.total > 0 && <p className="stat">{score.right} / {score.total}</p>}
        </>
      )}
      {msg && <p className="note" role="alert">{msg}</p>}
    </div>
  )
}
