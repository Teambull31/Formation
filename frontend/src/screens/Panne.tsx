import { useState } from 'react'
import { addPanne } from '../api'

// Une vraie panne résolue devient une carte écrite par toi : symptôme, cause, correction.
export default function Panne({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ symptom: '', cause: '', fix: '' })
  const [msg, setMsg] = useState('')
  const field = (k: keyof typeof f, label: string, ph: string) => (
    <>
      <label className="tag" htmlFor={`panne-${k}`}>{label}</label>
      <textarea id={`panne-${k}`} className="area" rows={2} placeholder={ph} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </>
  )
  if (!open) return <button className="btn ghost" onClick={() => setOpen(true)}>J'ai résolu une panne → en faire une carte</button>
  return (
    <div className="card">
      <h3>Panne résolue</h3>
      {field('symptom', 'Symptôme', 'ex. le checkout échoue sur le runner du VPS : Permission denied')}
      {field('cause', 'Cause', 'ex. un job précédent a laissé des fichiers appartenant à root')}
      {field('fix', 'Correction', 'ex. vider le workspace et lancer le job dans un conteneur')}
      <div className="row">
        <button className="btn" onClick={() => addPanne(f.symptom, f.cause, f.fix)
          .then(() => { setF({ symptom: '', cause: '', fix: '' }); setMsg('Carte ajoutée : elle arrive dans tes révisions.'); onAdded() })
          .catch((e: Error) => setMsg(e.message))}>Créer la carte</button>
        <button className="btn ghost" onClick={() => setOpen(false)}>Fermer</button>
      </div>
      {msg && <p className="note" role="status">{msg}</p>}
    </div>
  )
}
