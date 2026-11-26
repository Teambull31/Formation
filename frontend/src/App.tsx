import { useEffect, useState } from 'react'
import Quest from './screens/Quest'
import Lesson from './screens/Lesson'
import Team from './screens/Team'
import Boss from './screens/Boss'
import Weekly from './screens/Weekly'
import Review from './screens/Review'
import Glossary from './screens/Glossary'
import Interview from './screens/Interview'
import Cards from './screens/Cards'
import Exam from './screens/Exam'
import Listen from './screens/Listen'
import OfflineBanner from './screens/OfflineBanner'
import { getQuest, type StepKind } from './api'

import { TABS, saveLast, startAt, type Sub, type Tab } from './deeplink'
const MINI_CARDS = 3 // « J'ai 2 min » : trois cartes, et la journée compte
interface Opened { id: string; kind: StepKind | null; done: boolean; n: number; focus?: string }

export default function App() {
  const [start] = useState(() => startAt())
  const [tab, setTab] = useState<Tab>(start.tab)
  const [lesson, setLesson] = useState<Opened | null>(start.lessonId ? { id: start.lessonId, kind: null, done: false, n: 1 } : null)
  const [sub, setSub] = useState<Sub>(start.sub)
  useEffect(() => { saveLast({ tab, sub, lessonId: lesson?.id ?? null }) }, [tab, sub, lesson?.id])
  const open = (id: string, kind: StepKind | null = null, done = false, focus?: string) => {
    setLesson((l) => ({ id, kind, done, n: (l?.n ?? 0) + 1, focus }))
    setTab('Leçon')
  }
  // séance guidée : révisions QCM → cartes → première étape pas faite de la quête
  const toLesson = () => getQuest().then((q) => {
    const s = q.steps.find((x) => !x.done)
    if (s) open(s.lesson_id, s.kind, false)
    else setTab('Quête')
  }).catch(() => setTab('Quête'))
  return (
    <>
      <main>
        <OfflineBanner />
        {tab === 'Quête' && <Quest onStart={open} onGo={(t, sb) => { if (sb) setSub(sb); setTab(t) }} />}
        {tab === 'Leçon' && (
          <Lesson key={lesson?.n} id={lesson?.id ?? null} kind={lesson?.kind} done={lesson?.done} focus={lesson?.focus} onOpen={(id) => open(id)} />
        )}
        {tab === 'Équipe' && <Team />}
        {tab === 'Boss' && <Boss onOpen={(id) => open(id)} />}
        {tab === 'Révisions' && (
          <>
            <div className="wrap row" role="group" aria-label="Type de révision">
              {([['qcm', 'Questions'], ['cartes', 'Cartes'], ['examen', 'Examen'], ['entretien', 'Entretien'], ['glossaire', 'Glossaire']] as const).map(([k, label]) => (
                <button key={k} className="chip" aria-pressed={sub === k} onClick={() => setSub(k)}>{label}</button>
              ))}
            </div>
            {sub === 'qcm' && <Review onOpen={(id, focus) => open(id, null, false, focus)} onContinue={() => setSub('cartes')} />}
            {sub === 'cartes' && <Cards onOpen={(id) => open(id)} onContinue={toLesson} limit={start.mini ? MINI_CARDS : undefined} />}
            {sub === 'examen' && <Exam onOpen={(id, focus) => open(id, null, false, focus)} />}
            {sub === 'entretien' && <Interview />}
            {sub === 'glossaire' && <Glossary onOpen={(id, focus) => open(id, null, false, focus)} />}
          </>
        )}
        {tab === 'Écoute' && <Listen />}
        {tab === 'Semaine' && <Weekly onOpen={(id, focus) => open(id, null, false, focus)} />}
      </main>
      <nav aria-label="Navigation principale"><div className="inner" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div></nav>
    </>
  )
}
