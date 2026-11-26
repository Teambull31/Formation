import { useEffect, useState } from 'react'
import { correction, optClass } from '../qcm'
import { answerQcm, getRecall, type QcmResult, type RecallQ } from '../api'

// Entrelacement : une question d'une ancienne leçon glissée en fin de leçon, pour mélanger les sujets.
export default function Recall({ lessonId }: { lessonId: string }) {
  const [q, setQ] = useState<RecallQ | null>(null)
  const [res, setRes] = useState<{ chosen: number; r: QcmResult } | null>(null)
  useEffect(() => { getRecall(lessonId).then(setQ).catch(() => {}) }, [lessonId])
  if (!q) return null
  return (
    <div className="card">
      <p className="tag">Rappel · {q.title}</p>
      <h3>{q.text}</h3>
      {q.options.map((o, k) => (
        <button key={k} className={optClass(res, k, o)}
          disabled={!!res} onClick={() => answerQcm(q.id, k, null).then((r) => setRes({ chosen: k, r })).catch(() => {})}>{o}</button>
      ))}
      {res && <p className={'fb' + (res.r.correct ? ' ok' : '')} role="status">{res.r.correct ? 'Juste, toujours en tête ✓' : `À revoir : elle revient dans tes révisions.${correction(res.r)}`} {res.r.explanation}</p>}
    </div>
  )
}
