import { useEffect, useState } from 'react'
import { attemptBoss, getBoss, isForbidden, type BossInfo, type BossResult } from '../api'

export default function Boss({ onOpen }: { onOpen: (lessonId: string) => void }) {
  const [info, setInfo] = useState<BossInfo | null>(null)
  const [res, setRes] = useState<BossResult | null>(null)
  const [local, setLocal] = useState(true) // false once the API answers 403 (phone/remote)
  const [msg, setMsg] = useState('')
  useEffect(() => { getBoss().then(setInfo).catch((e: Error) => setMsg(e.message)) }, [])

  const fight = () =>
    attemptBoss()
      .then((r) => { setRes(r); setMsg(''); setInfo((i) => (i ? { ...i, attempts: r.attempts } : i)) })
      .catch((e: Error) => { if (isForbidden(e)) setLocal(false); else setMsg(e.message) })

  return (
    <section className="screen wrap">
      {info && (
        <div className="card">
          <p className="tag">Boss</p>
          <h2>{info.title}</h2>
          {info.phases.map((p, i) => <div key={i} className="step"><span className="grow">{p.label}</span></div>)}
          <p className="note">Conseillé avant de défier : avoir terminé les leçons du module. Ce n'est pas obligatoire.</p>
          <p className="stat">Tentatives : {info.attempts}</p>
          {local ? (
            <button className="btn" onClick={fight}>Défier</button>
          ) : (
            <p className="note" role="status">Le défi se lance uniquement depuis le PC.</p>
          )}
        </div>
      )}
      {res && (
        <div className={'fb' + (res.won ? ' ok' : '')} role="status">
          {res.won ? (
            <p>Victoire ! Boss vaincu en {res.attempts} tentative(s).</p>
          ) : (
            <>
              <p>Échec en phase {res.phase_reached}{res.failed_pattern ? ` : pattern « ${res.failed_pattern} »` : ''}.</p>
              {res.remedial_lesson_id && (
                <button className="btn ghost" onClick={() => onOpen(res.remedial_lesson_id!)}>Ouvrir la mini-leçon</button>
              )}
            </>
          )}
        </div>
      )}
      {msg && <p className="note" role="alert">{msg}</p>}
    </section>
  )
}
