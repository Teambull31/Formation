import { useRef, useState } from 'react'
import { ApiError, isForbidden, weeklyBrief, weeklyImport } from '../api'

const FORMATS = ['30 min', '60 min', 'mixte']

export default function Weekly() {
  const [topic, setTopic] = useState('')
  const [format, setFormat] = useState(FORMATS[0])
  const [brief, setBrief] = useState('')
  const [path, setPath] = useState('')
  const [moduleId, setModuleId] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [msg, setMsg] = useState('')
  const pre = useRef<HTMLPreElement>(null)

  const gen = () =>
    weeklyBrief(topic.trim(), format).then((r) => { setBrief(r.brief); setMsg('') }).catch((e: Error) => setMsg(e.message))

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(brief)
      setMsg('Brief copié.')
    } catch {
      const sel = window.getSelection()
      if (pre.current && sel) {
        const range = document.createRange()
        range.selectNodeContents(pre.current)
        sel.removeAllRanges()
        sel.addRange(range)
      }
      setMsg('Copie auto impossible : texte sélectionné, copie-le à la main.')
    }
  }

  const imp = () => {
    setModuleId(''); setErrors([]); setMsg('')
    weeklyImport(path.trim())
      .then((r) => setModuleId(r.module_id))
      .catch((e: Error) => {
        if (isForbidden(e)) setMsg("L'import n'est disponible que sur le PC.")
        else if (e instanceof ApiError && e.status === 422) setErrors(e.errors)
        else setMsg(e.message)
      })
  }

  return (
    <section className="screen wrap">
      <div className="card">
        <h3>Préparer la semaine</h3>
        <label className="tag" htmlFor="wk-topic">Sujet</label>
        <input id="wk-topic" type="text" value={topic} onChange={(e) => setTopic(e.target.value)} />
        <label className="tag" htmlFor="wk-format">Format</label>
        <select id="wk-format" value={format} onChange={(e) => setFormat(e.target.value)}>
          {FORMATS.map((f) => <option key={f}>{f}</option>)}
        </select>
        <button className="btn" onClick={gen}>Générer le brief</button>
        {brief && (
          <>
            <pre className="out" ref={pre}>{brief}</pre>
            <button className="btn ghost" onClick={copy}>Copier le brief</button>
          </>
        )}
      </div>
      <div className="card">
        <h3>Importer un module</h3>
        <label className="tag" htmlFor="wk-path">Chemin du module</label>
        <input id="wk-path" type="text" value={path} onChange={(e) => setPath(e.target.value)} />
        <button className="btn" onClick={imp}>Importer</button>
        {moduleId && <p className="fb ok" role="status">Module importé : {moduleId}</p>}
        {errors.length > 0 && (
          <div className="fb" role="alert">
            <p>Import refusé :</p>
            <ul>{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
          </div>
        )}
      </div>
      {msg && <p className="note" role="status">{msg}</p>}
    </section>
  )
}
