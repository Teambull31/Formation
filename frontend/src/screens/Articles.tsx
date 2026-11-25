import { useEffect, useState } from 'react'
import { getArticles, saveArticle, type Article } from '../api'

// Un article par module réussi : expliquer en public (Feynman) et nourrir le portfolio.
export default function Articles() {
  const [list, setList] = useState<Article[]>([])
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<Record<string, string>>({})
  useEffect(() => { getArticles().then((a) => { setList(a); setDraft(Object.fromEntries(a.map((x) => [x.id, x.text]))) }).catch(() => {}) }, [])
  if (!list.length) return null
  const words = (t: string) => t.trim().split(/\s+/).filter(Boolean).length
  return (
    <div className="card">
      <h3>Articles du portfolio</h3>
      <p className="note">« Comment j'ai fait X » en ~300 mots, après chaque examen réussi. Ils entrent dans le zip du portfolio.</p>
      {list.map((a) => (
        <div key={a.id}>
          <label className="tag" htmlFor={`art-${a.id}`}>{a.title} · {words(draft[a.id] ?? '')} mots</label>
          <textarea id={`art-${a.id}`} className="area" rows={8} value={draft[a.id] ?? ''}
            placeholder="Le problème, ce que j'ai fait, ce que j'ai appris, ce que je ferais autrement."
            onChange={(e) => setDraft({ ...draft, [a.id]: e.target.value })} />
          <button className="btn ghost" onClick={() => saveArticle(a.id, draft[a.id] ?? '')
            .then((r) => setMsg({ ...msg, [a.id]: `Enregistré (${r.words} mots)${r.xp ? `, +${r.xp} XP` : ''}.` }))
            .catch((e: Error) => setMsg({ ...msg, [a.id]: e.message }))}>Enregistrer</button>
          {msg[a.id] && <p className="note" role="status">{msg[a.id]}</p>}
        </div>
      ))}
    </div>
  )
}
