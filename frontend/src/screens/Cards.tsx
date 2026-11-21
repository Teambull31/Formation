import { useEffect, useState } from 'react'
import { answerCard, getCards, type Card, type Cards as C } from '../api'
import { renderLesson } from '../renderLesson'

// Cartes mémoire des leçons terminées : on se répond de tête, puis on dit honnêtement si on savait.
export default function Cards({ onOpen }: { onOpen: (lessonId: string) => void }) {
  const [data, setData] = useState<C | null>(null)
  const [queue, setQueue] = useState<Card[]>([])
  const [shown, setShown] = useState(false)
  const [known, setKnown] = useState(0)
  const [err, setErr] = useState('')
  const [tries, setTries] = useState(0)

  useEffect(() => {
    setErr(''); setData(null)
    getCards().then((d) => { setData(d); setQueue(d.cards); setKnown(0); setShown(false) }).catch((e: Error) => setErr(e.message || 'Erreur'))
  }, [tries])

  if (err) {
    return (
      <section className="screen wrap">
        <p className="note" role="alert">Impossible de charger les cartes : {err}</p>
        <button className="btn ghost" onClick={() => setTries((n) => n + 1)}>Réessayer</button>
      </section>
    )
  }
  if (!data) return <section className="screen wrap"><p className="note">Chargement…</p></section>

  const c = queue[0]
  const answer = (ok: boolean) => {
    answerCard(c.id, ok)
      .then(() => {
        if (ok) setKnown((n) => n + 1)
        // une carte ratée revient en fin de séance : on ne la quitte pas sans l'avoir sue une fois
        setQueue((q) => (ok ? q.slice(1) : [...q.slice(1), c]))
        setShown(false)
      })
      .catch((e: Error) => setErr(e.message || 'Erreur'))
  }

  return (
    <section className="screen wrap">
      <h1>Cartes mémoire</h1>
      <p className="stat">{data.total} cartes dans les leçons terminées · {data.unseen} jamais vues · {data.boxes[data.boxes.length - 1] ?? 0} maîtrisées</p>
      {data.total === 0 && <p className="card">Terminez une leçon : ses pièges et ses termes clés deviennent des cartes.</p>}
      {data.total > 0 && !c && (
        <div className="card" role="status">
          <h2>{data.cards.length ? `Séance terminée : ${known} carte(s) sue(s) du premier coup ou après reprise` : 'Rien à revoir aujourd\'hui'}</h2>
          <p className="note">Les cartes reviennent après 1, 2, 4, 7 puis 14 jours.</p>
          <button className="btn ghost" onClick={() => setTries((n) => n + 1)}>Actualiser</button>
        </div>
      )}
      {c && (
        <div className="card">
          <p className="tag">{c.kind === 'piege' ? 'Piège' : 'Terme clé'} · {c.lesson_id} · {queue.length} restante(s)</p>
          {/* renderLesson échappe tout avant de produire ses balises */}
          <div className="course" dangerouslySetInnerHTML={{ __html: renderLesson(c.front) }} />
          {!shown ? (
            <button className="btn" onClick={() => setShown(true)}>Voir la réponse</button>
          ) : (
            <>
              <div className="fb ok" role="status"><div className="course" dangerouslySetInnerHTML={{ __html: renderLesson(c.back) }} /></div>
              <div className="row">
                <button className="btn term grow" onClick={() => answer(true)}>Je savais</button>
                <button className="btn ghost grow" onClick={() => answer(false)}>À revoir</button>
              </div>
              <button className="btn ghost" onClick={() => onOpen(c.lesson_id)}>Relire la leçon</button>
            </>
          )}
        </div>
      )}
    </section>
  )
}
