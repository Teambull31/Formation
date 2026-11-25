import { useEffect, useState } from 'react'
import { getCert, setCert, type Cert as C } from '../api'

// Un cap daté : la certification visée, le compte à rebours, et son examen blanc (onglet Révisions → Examen).
export default function Cert() {
  const [c, setC] = useState<C | null>(null)
  const [edit, setEdit] = useState(false)
  const [key, setKey] = useState('')
  const [when, setWhen] = useState('')
  const load = () => getCert().then((x) => { setC(x); setKey(x.key ?? x.options[0]?.key ?? ''); setWhen(x.date ?? '') }).catch(() => {})
  useEffect(() => { load() }, [])
  if (!c) return null
  if (!edit) {
    return c.key ? (
      <div className="row between card">
        <span><span className="tag">Objectif</span><br />{c.title}{c.days_left !== null ? ` · J-${c.days_left}` : ''}</span>
        <button className="chip" onClick={() => setEdit(true)}>Changer</button>
      </div>
    ) : <button className="btn ghost" onClick={() => setEdit(true)}>🎯 Viser une certification (avec examen blanc)</button>
  }
  return (
    <div className="card">
      <label className="tag" htmlFor="cert-key">Certification visée</label>
      <select id="cert-key" value={key} onChange={(e) => setKey(e.target.value)}>
        {c.options.map((o) => <option key={o.key} value={o.key}>{o.title}</option>)}
      </select>
      <label className="tag" htmlFor="cert-date">Date de l'examen</label>
      <input id="cert-date" type="date" value={when} onChange={(e) => setWhen(e.target.value)} />
      <div className="row">
        <button className="btn" onClick={() => setCert(key, when || null).then(() => { setEdit(false); load() })}>Enregistrer</button>
        {c.key && <button className="btn ghost" onClick={() => setCert(null, null).then(() => { setEdit(false); load() })}>Retirer</button>}
      </div>
    </div>
  )
}
