import { useState } from 'react'
import { gradeFeynman, isForbidden, type FeynmanResult } from '../api'

const MIN = 40 // same floor as the API

export default function Feynman({ lessonId, title }: { lessonId: string; title: string }) {
  const [text, setText] = useState('')
  const [res, setRes] = useState<FeynmanResult | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const send = () => {
    setBusy(true)
    gradeFeynman(lessonId, text.trim())
      .then((r) => { setRes(r); setErr('') })
      .catch((e: Error) => setErr(isForbidden(e) ? "La notation est réservée à l'ordinateur (Ollama)." : e.message))
      .finally(() => setBusy(false))
  }

  return (
    <div className="card">
      <h2>Explique-le à un junior</h2>
      <p className="note">Avec tes mots, sans relire le cours : « {title} ». Ollama te note et te dit ce qui manque.</p>
      <textarea className="area" rows={6} value={text} maxLength={4000} aria-label="Ton explication"
        onChange={(e) => setText(e.target.value)} />
      <button className="btn" disabled={busy || text.trim().length < MIN} onClick={send}>
        {busy ? 'Notation en cours…' : 'Faire noter'}
      </button>
      {text.trim().length < MIN && <p className="note">Encore {MIN - text.trim().length} caractères au moins.</p>}
      {err && <p className="note" role="alert">{err}</p>}
      {res && (
        <div className={'fb' + (res.score >= 60 ? ' ok' : '')} role="status">
          <p><strong>{res.score}/100</strong>{res.xp > 0 ? ` · +${res.xp} XP` : ''} · meilleur score {res.best}</p>
          <p>{res.feedback}</p>
          {res.missing.length > 0 && (
            <>
              <p>À revoir :</p>
              <ul>{res.missing.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </>
          )}
        </div>
      )}
    </div>
  )
}
