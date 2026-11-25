import { useEffect, useState } from 'react'
import { checkMission, getMissions, proveMission, type Mission } from '../api'

// Missions réelles : un module se termine par une tâche sur tes propres dépôts et serveurs.
export default function Missions() {
  const [ms, setMs] = useState<Mission[]>([])
  const [out, setOut] = useState<Record<string, string>>({})
  const [proof, setProof] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState('')
  const load = () => getMissions().then(setMs).catch(() => {})
  useEffect(() => { load() }, [])
  const note = (id: string, t: string) => setOut((o) => ({ ...o, [id]: t }))

  if (!ms.length) return null
  return (
    <div className="card">
      <h3>Missions réelles</h3>
      <p className="note">Appliquer sur tes vrais projets transforme le cours en compétence (et en ligne de CV). +200 XP chacune.</p>
      {ms.map((m) => (
        <details key={m.id} open={m.ready && !m.done}>
          <summary>{m.done ? '✓ ' : m.ready ? '▶ ' : ''}{m.title} <span className="time">· {m.module}</span></summary>
          <p>{m.goal}</p>
          <ol>{m.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          {m.done ? <p className="fb ok">Mission accomplie{m.proof ? ` : ${m.proof}` : ''}.</p> : (
            <>
              {m.checkable && (
                <button className="btn term" disabled={busy === m.id} onClick={() => {
                  setBusy(m.id)
                  checkMission(m.id).then((r) => { note(m.id, (r.passed ? `Réussie, +${r.xp} XP.\n` : 'Pas encore.\n') + r.output); load() })
                    .catch((e: Error) => note(m.id, e.message)).finally(() => setBusy(''))
                }}>Vérifier sur ce PC</button>
              )}
              <label className="tag" htmlFor={`proof-${m.id}`}>Ou un lien de preuve (commit, PR, run GitHub)</label>
              <div className="row">
                <input id={`proof-${m.id}`} className="grow" type="url" placeholder="https://github.com/…" value={proof[m.id] ?? ''}
                  onChange={(e) => setProof({ ...proof, [m.id]: e.target.value })} />
                <button className="btn ghost" onClick={() => proveMission(m.id, (proof[m.id] ?? '').trim())
                  .then((r) => { note(m.id, `Validée, +${r.xp} XP.`); load() }).catch((e: Error) => note(m.id, e.message))}>Valider</button>
              </div>
            </>
          )}
          {out[m.id] && <pre className="out">{out[m.id]}</pre>}
        </details>
      ))}
    </div>
  )
}
