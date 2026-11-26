import { useEffect, useState } from 'react'
import { getLessonKeys, type LessonKey } from '../api'
import { renderLesson } from '../renderLesson'

// Fin de leçon : se rappeler les pièges et termes clés AVANT de voir la réponse (rappel actif, pas relecture).
export default function Keys({ lessonId }: { lessonId: string }) {
  const [keys, setKeys] = useState<LessonKey[]>([])
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [picked, setPicked] = useState<Record<string, string>>({}) // carte à trou : proposition touchée
  useEffect(() => { getLessonKeys(lessonId).then(setKeys).catch(() => {}) }, [lessonId])
  if (!keys.length) return null
  return (
    <div className="card">
      <h3>À retenir</h3>
      <p className="note">Réponds de tête, puis vérifie. Ces notions reviendront en cartes.</p>
      {keys.map((k) => (
        <div key={k.id} className="step">
          {/* renderLesson échappe tout avant de produire ses balises */}
          <div className="grow">
            <div className="course" dangerouslySetInnerHTML={{ __html: renderLesson(k.front) }} />
            {k.choices && k.choices.map((o) => {
              const p = picked[k.id]
              return <button key={o} className={'opt' + (!p ? '' : o === k.back ? ' right' : o === p ? ' wrong' : '')} disabled={!!p}
                onClick={() => setPicked({ ...picked, [k.id]: o })}>{o}</button>
            })}
            {open.has(k.id) && !k.choices && <div className="fb ok course" dangerouslySetInnerHTML={{ __html: renderLesson(k.back) }} />}
          </div>
          {!open.has(k.id) && !k.choices && <button className="chip" onClick={() => setOpen(new Set([...open, k.id]))}>Voir</button>}
        </div>
      ))}
    </div>
  )
}
