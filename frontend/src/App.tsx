import { useState } from 'react'
import Quest from './screens/Quest'
import Lesson from './screens/Lesson'
import Team from './screens/Team'
import Boss from './screens/Boss'
import Weekly from './screens/Weekly'
import Review from './screens/Review'
import Interview from './screens/Interview'
import Cards from './screens/Cards'
import Exam from './screens/Exam'
import Listen from './screens/Listen'
import type { StepKind } from './api'

const TABS = ['Quête', 'Leçon', 'Équipe', 'Boss', 'Révisions', 'Écoute', 'Semaine'] as const
type Tab = (typeof TABS)[number]
interface Opened { id: string; kind: StepKind | null; done: boolean; n: number }

export default function App() {
  const [tab, setTab] = useState<Tab>('Quête')
  const [lesson, setLesson] = useState<Opened | null>(null)
  const [sub, setSub] = useState<'qcm' | 'cartes' | 'examen' | 'entretien'>('qcm')
  const open = (id: string, kind: StepKind | null = null, done = false) => {
    setLesson((l) => ({ id, kind, done, n: (l?.n ?? 0) + 1 }))
    setTab('Leçon')
  }
  return (
    <>
      <main>
        {tab === 'Quête' && <Quest onStart={open} onGo={(t, sb) => { if (sb) setSub(sb); setTab(t) }} />}
        {tab === 'Leçon' && (
          <Lesson key={lesson?.n} id={lesson?.id ?? null} kind={lesson?.kind} done={lesson?.done} onOpen={(id) => open(id)} />
        )}
        {tab === 'Équipe' && <Team />}
        {tab === 'Boss' && <Boss onOpen={(id) => open(id)} />}
        {tab === 'Révisions' && (
          <>
            <div className="wrap row" role="group" aria-label="Type de révision">
              {([['qcm', 'Questions'], ['cartes', 'Cartes'], ['examen', 'Examen'], ['entretien', 'Entretien']] as const).map(([k, label]) => (
                <button key={k} className="chip" aria-pressed={sub === k} onClick={() => setSub(k)}>{label}</button>
              ))}
            </div>
            {sub === 'qcm' && <Review onOpen={(id) => open(id)} />}
            {sub === 'cartes' && <Cards onOpen={(id) => open(id)} />}
            {sub === 'examen' && <Exam onOpen={(id) => open(id)} />}
            {sub === 'entretien' && <Interview />}
          </>
        )}
        {tab === 'Écoute' && <Listen />}
        {tab === 'Semaine' && <Weekly />}
      </main>
      <nav aria-label="Navigation principale"><div className="inner" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div></nav>
    </>
  )
}
