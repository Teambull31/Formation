import { useEffect, useRef, useState } from 'react'

const SWIPE_PX = 60
const PER_DAY = [3, 5, 10, 15, 20] // peu les jours chargés, plus quand on a le temps
import { answerCard, getCards, setCardsPerDay, type Card, type Cards as C } from '../api'
import { renderLesson } from '../renderLesson'
import Panne from './Panne'

// Cartes mémoire des leçons terminées : on se répond de tête, puis on dit honnêtement si on savait.
export default function Cards({ onOpen, onContinue, limit }: { onOpen: (lessonId: string) => void; onContinue?: () => void; limit?: number }) {
  const [data, setData] = useState<C | null>(null)
  const [queue, setQueue] = useState<Card[]>([])
  const [shown, setShown] = useState(false)
  const [picked, setPicked] = useState<string | null>(null) // carte à trou : proposition touchée
  const [known, setKnown] = useState(0)
  const [err, setErr] = useState('')
  const [tries, setTries] = useState(0)

  useEffect(() => {
    setErr(''); setData(null)
    getCards().then((d) => { setData(d); setQueue(limit ? d.cards.slice(0, limit) : d.cards); setKnown(0); setShown(false); setPicked(null) }).catch((e: Error) => setErr(e.message || 'Erreur'))
  }, [tries, limit])

  const c = queue[0]
  const pick = (o: string) => { setPicked(o); setShown(true) }
  const answer = (ok: boolean) => {
    answerCard(c.id, ok)
      .then(() => {
        if (ok) setKnown((n) => n + 1)
        // une carte ratée revient en fin de séance : on ne la quitte pas sans l'avoir sue une fois
        setQueue((q) => (ok ? q.slice(1) : [...q.slice(1), c]))
        setShown(false); setPicked(null)
      })
      .catch((e: Error) => setErr(e.message || 'Erreur'))
  }

  // geste et clavier : toucher = voir la réponse ; glisser → je savais, ← à revoir (flèches, Espace au clavier)
  const touchX = useRef<number | null>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!c || (e.target as HTMLElement)?.closest?.('input, textarea, select')) return
      if (!shown && c.choices && '123'.includes(e.key) && c.choices[Number(e.key) - 1]) pick(c.choices[Number(e.key) - 1])
      else if (shown && picked && (e.key === 'Enter' || e.key === 'ArrowRight')) answer(picked === c.back)
      else if (!shown && !c.choices && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); setShown(true) }
      else if (shown && e.key === 'ArrowRight') answer(true)
      else if (shown && e.key === 'ArrowLeft') answer(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
  const onTouchEnd = (x: number) => {
    const dx = touchX.current === null ? 0 : x - touchX.current
    touchX.current = null
    if (c?.choices) return // propositions : on choisit en touchant un bouton, pas la carte
    if (!shown && Math.abs(dx) < 10) setShown(true)
    else if (shown && dx > SWIPE_PX) answer(true)
    else if (shown && dx < -SWIPE_PX) answer(false)
  }

  if (err) {
    return (
      <section className="screen wrap">
        <p className="note" role="alert">Impossible de charger les cartes : {err}</p>
        <button className="btn ghost" onClick={() => setTries((n) => n + 1)}>Réessayer</button>
      </section>
    )
  }
  if (!data) return <section className="screen wrap"><p className="note">Chargement…</p></section>

  return (
    <section className="screen wrap">
      <h1>Cartes mémoire</h1>
      <Panne onAdded={() => setTries((n) => n + 1)} />
      <label className="row">
        <span className="tag">Nouvelles cartes par jour</span>
        <select value={data.per_day ?? 10} onChange={(e) => setCardsPerDay(Number(e.target.value)).then(() => setTries((n) => n + 1))}>
          {PER_DAY.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <p className="stat">{data.total} cartes dans les leçons terminées · {data.unseen} jamais vues · {data.boxes[data.boxes.length - 1] ?? 0} maîtrisées</p>
      {data.total === 0 && <p className="card">Terminez une leçon : ses pièges et ses termes clés deviennent des cartes.</p>}
      {data.total > 0 && !c && (
        <div className="card" role="status">
          {limit && data.cards.length > 0 && <p className="fb ok">2 minutes faites : la journée compte ✓</p>}
          <h2>{data.cards.length ? `Séance terminée : ${known} carte(s) sue(s) du premier coup ou après reprise` : 'Rien à revoir aujourd\'hui'}</h2>
          <p className="note">Les cartes reviennent après 1, 2, 4, 7, 14, 30 puis 60 jours.</p>
          {onContinue && <button className="btn" onClick={onContinue}>Continuer la séance : leçon du jour →</button>}
          <button className="btn ghost" onClick={() => setTries((n) => n + 1)}>Actualiser</button>
        </div>
      )}
      {c && (
        <div className="card" onTouchStart={(e) => { touchX.current = e.touches[0].clientX }}
          onTouchEnd={(e) => onTouchEnd(e.changedTouches[0].clientX)}>
          <p className="tag">{c.kind === 'piege' ? 'Piège' : c.kind === 'panne' ? 'Panne vécue' : 'Terme clé'}{c.lesson_id ? ` · ${c.lesson_id}` : ''} · {queue.length} restante(s)</p>
          {/* renderLesson échappe tout avant de produire ses balises */}
          <div className="course" dangerouslySetInnerHTML={{ __html: renderLesson(c.front) }} />
          {c.choices && (
            c.choices.map((o) => (
              <button key={o} className={'opt' + (!picked ? '' : o === c.back ? ' right' : o === picked ? ' wrong' : '')}
                disabled={!!picked} onClick={() => pick(o)}>{o}</button>
            ))
          )}
          {picked ? (
            <>
              <p className={'fb' + (picked === c.back ? ' ok' : '')} role="status">{picked === c.back ? 'Juste ✓' : `Raté. Bonne réponse : ${c.back}.`}</p>
              <button className="btn" onClick={() => answer(picked === c.back)}>Suivant →</button>
              {c.lesson_id && picked !== c.back && <button className="btn ghost" onClick={() => onOpen(c.lesson_id)}>Relire la leçon</button>}
            </>
          ) : c.choices ? null : !shown ? (
            <>
              <button className="btn" onClick={() => setShown(true)}>Voir la réponse</button>
              <p className="time">Astuce : touche la carte, puis glisse → si tu savais, ← sinon.</p>
            </>
          ) : (
            <>
              <div className="fb ok" role="status"><div className="course" dangerouslySetInnerHTML={{ __html: renderLesson(c.back) }} /></div>
              <div className="row">
                <button className="btn term grow" onClick={() => answer(true)}>Je savais</button>
                <button className="btn ghost grow" onClick={() => answer(false)}>À revoir</button>
              </div>
              {c.lesson_id && <button className="btn ghost" onClick={() => onOpen(c.lesson_id)}>Relire la leçon</button>}
            </>
          )}
        </div>
      )}
    </section>
  )
}
