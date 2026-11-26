import { useEffect, useRef, useState } from 'react'
import { getExam, getExams, submitExam, type Exam as E, type ExamResult, type ExamSummary } from '../api'

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

// Examen final : questions mélangées de tout le module, chronométrées, réponses montrées à la fin seulement.
export default function Exam({ onOpen }: { onOpen: (lessonId: string, focus?: string) => void }) {
  const [list, setList] = useState<ExamSummary[] | null>(null)
  const [exam, setExam] = useState<E | null>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [left, setLeft] = useState(0)
  const [res, setRes] = useState<ExamResult | null>(null)
  const [err, setErr] = useState('')
  const sent = useRef(false)

  useEffect(() => { if (!exam) getExams().then(setList).catch((e: Error) => setErr(e.message || 'Erreur')) }, [exam])

  const submit = () => {
    if (!exam || sent.current) return
    sent.current = true
    const all = Object.fromEntries(exam.questions.map((q) => [q.id, answers[q.id] ?? -1]))
    submitExam(exam.id, all).then(setRes).catch((e: Error) => { sent.current = false; setErr(e.message || 'Erreur') })
  }
  const submitRef = useRef(submit)
  submitRef.current = submit

  useEffect(() => {
    if (!exam || res) return
    const t = setInterval(() => setLeft((s) => {
      if (s <= 1) { clearInterval(t); submitRef.current(); return 0 }
      return s - 1
    }), 1000)
    return () => clearInterval(t)
  }, [exam, res])

  const start = (id: string) => {
    setErr('')
    getExam(id).then((e) => { sent.current = false; setAnswers({}); setRes(null); setLeft(e.duration_s); setExam(e) })
      .catch((e: Error) => setErr(e.message || 'Erreur'))
  }

  if (err) return <section className="screen wrap"><p className="note" role="alert">{err}</p></section>

  if (!exam) {
    return (
      <section className="screen wrap">
        <h1>Examens finaux</h1>
        <p className="note">Questions tirées de tout le module, chronométrées. Réussite à 80 %. Les erreurs rejoignent vos révisions.</p>
        {!list && <p className="note">Chargement…</p>}
        {list?.map((m) => (
          <div className="step" key={m.id}>
            <div className="grow">
              <div>{m.title}</div>
              <div className="time">{m.questions} questions{m.best !== null ? ` · meilleur score ${m.best} %` : ''}</div>
            </div>
            <button className="btn ghost" onClick={() => start(m.id)}>Commencer</button>
          </div>
        ))}
      </section>
    )
  }

  if (res) {
    return (
      <section className="screen wrap">
        <h1>{exam.title}</h1>
        <div className={'fb' + (res.passed ? ' ok' : '')} role="status">
          <h2>{res.score} % : {res.passed ? 'examen réussi' : `pas encore (${res.pass_pct} % requis)`}</h2>
          <p className="stat">Meilleur score {res.best} %{res.xp ? ` · +${res.xp} XP` : ''}</p>
        </div>
        {!!res.to_review?.length && (
          <div className="card">
            <h3>À revoir en priorité</h3>
            <p className="note">Tes erreurs, leçon par leçon. Elles reviennent aussi dans tes révisions.</p>
            {res.to_review.map((t) => (
              <div className="row between" key={t.lesson_id}>
                <span className="grow">{t.title} <span className="time">· {t.count} erreur(s)</span></span>
                <button className="chip" onClick={() => onOpen(t.lesson_id, t.focus)}>Revoir</button>
              </div>
            ))}
          </div>
        )}
        {res.detail.filter((d) => !d.correct).map((d) => (
          <div className="card" key={d.id}>
            <p>{d.text}</p>
            <p className="note">{d.chosen < 0 ? 'Sans réponse.' : 'Raté.'}{d.answer_text ? ` Bonne réponse : ${d.answer_text}.` : ''} {d.explain}</p>
            {d.remedial_lesson_id && <button className="btn ghost" onClick={() => onOpen(d.remedial_lesson_id!)}>Revoir la leçon</button>}
          </div>
        ))}
        <button className="btn" onClick={() => setExam(null)}>Retour aux examens</button>
      </section>
    )
  }

  const n = Object.keys(answers).length
  return (
    <section className="screen wrap">
      <h1>{exam.title}</h1>
      <p className="stat" role="timer" aria-live="off">Temps restant {clock(left)} · {n} / {exam.questions.length} répondues</p>
      {exam.questions.map((q, i) => (
        <div className="card" key={q.id}>
          <p>{i + 1}. {q.text}</p>
          {q.options.map((o, c) => (
            <button key={c} className={'opt' + (answers[q.id] === c ? ' right' : '')} aria-pressed={answers[q.id] === c}
              onClick={() => setAnswers((a) => ({ ...a, [q.id]: c }))}>{o}</button>
          ))}
        </div>
      ))}
      <button className="btn" onClick={submit}>Rendre la copie</button>
    </section>
  )
}
