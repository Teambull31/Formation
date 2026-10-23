import { useState } from 'react'
import Quest from './screens/Quest'
import Lesson from './screens/Lesson'
import Team from './screens/Team'
import Boss from './screens/Boss'
import Weekly from './screens/Weekly'
import Review from './screens/Review'
import Interview from './screens/Interview'
import type { StepKind } from './api'

const TABS = ['Quête', 'Leçon', 'Équipe', 'Boss', 'Révisions', 'Semaine'] as const
type Tab = (typeof TABS)[number]
interface Opened { id: string; kind: StepKind | null; done: boolean; n: number }

export default function App() {
  const [tab, setTab] = useState<Tab>('Quête')
  const [lesson, setLesson] = useState<Opened | null>(null)
  const [sub, setSub] = useState<'qcm' | 'entretien'>('qcm')
  const open = (id: string, kind: StepKind | null = null, done = false) => {
    setLesson((l) => ({ id, kind, done, n: (l?.n ?? 0) + 1 }))
    setTab('Leçon')
  }
  return (
    <>
      <main>
        {tab === 'Quête' && <Quest onStart={open} onReview={() => setTab('Révisions')} />}
        {tab === 'Leçon' && (
          <Lesson key={lesson?.n} id={lesson?.id ?? null} kind={lesson?.kind} done={lesson?.done} onOpen={(id) => open(id)} />
        )}
        {tab === 'Équipe' && <Team />}
        {tab === 'Boss' && <Boss onOpen={(id) => open(id)} />}
        {tab === 'Révisions' && (
          <>
            <div className="wrap row" role="group" aria-label="Type de révision">
              <button className="chip" aria-pressed={sub === 'qcm'} onClick={() => setSub('qcm')}>Questions</button>
              <button className="chip" aria-pressed={sub === 'entretien'} onClick={() => setSub('entretien')}>Entretien</button>
            </div>
            {sub === 'qcm' ? <Review onOpen={(id) => open(id)} /> : <Interview />}
          </>
        )}
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
