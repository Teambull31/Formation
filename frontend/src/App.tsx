import { useState } from 'react'
import Quest from './screens/Quest'
import Lesson from './screens/Lesson'

const TABS = ['Quête', 'Leçon', 'Équipe', 'Boss', 'Semaine'] as const
type Tab = (typeof TABS)[number]

export default function App() {
  const [tab, setTab] = useState<Tab>('Quête')
  const [lessonId, setLessonId] = useState<string | null>(null)
  const open = (id: string) => { setLessonId(id); setTab('Leçon') }
  return (
    <>
      <main>
        {tab === 'Quête' && <Quest onStart={open} />}
        {tab === 'Leçon' && <Lesson key={lessonId} id={lessonId} onOpen={open} />}
        {(tab === 'Équipe' || tab === 'Boss' || tab === 'Semaine') && (
          <section className="screen wrap"><h1>{tab}</h1><p className="note">Bientôt disponible.</p></section>
        )}
      </main>
      <nav aria-label="Navigation principale"><div className="inner" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div></nav>
    </>
  )
}
