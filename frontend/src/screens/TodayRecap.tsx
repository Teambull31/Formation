import { useEffect, useState } from 'react'
import { getToday, type Today } from '../api'

// Séance finie : un bilan court, pour clore nettement et savoir ce qui attend demain.
export default function TodayRecap() {
  const [t, setT] = useState<Today | null>(null)
  useEffect(() => { getToday().then(setT).catch(() => {}) }, [])
  if (!t || (!t.lessons.length && !t.reviewed)) return null
  return (
    <div className="card" role="status">
      <h2>Séance du jour faite ✓</h2>
      {t.lessons.length > 0 && <p>Appris : {t.lessons.join(', ')}</p>}
      {t.reviewed > 0 && <p>Révisé : {t.reviewed} question(s), {t.correct} juste(s)</p>}
      <p className="note">{t.tomorrow ? `Demain : ${t.tomorrow} révision(s) t'attendent.` : 'Demain : rien en retard, place à la suite.'}</p>
    </div>
  )
}
