import { useEffect, useState } from 'react'
import { ApiError, getTeam, pullGacha, type Team as T } from '../api'

export default function Team() {
  const [team, setTeam] = useState<T | null>(null)
  const [pulled, setPulled] = useState<{ name: string; rarity: string } | null>(null)
  const [msg, setMsg] = useState('')
  const load = () => getTeam().then(setTeam).catch((e: Error) => setMsg(e.message))
  useEffect(() => { load() }, [])

  const pull = () =>
    pullGacha()
      .then((r) => { setPulled({ name: String(r.name), rarity: String(r.rarity) }); setMsg(''); return load() })
      .catch((e: Error) => {
        setPulled(null)
        setMsg(e instanceof ApiError && e.status === 409 ? 'Plus de jetons : termine des étapes pour en gagner.' : e.message)
      })

  return (
    <section className="screen wrap">
      <div className="card">
        <p className="tag">Profil</p>
        <h2>{team ? team.rank : '…'}</h2>
        {team?.rank_capped && <p className="note">Rang plafonné : bats un boss pour monter.</p>}
        {team && <p className="stat">niveau {team.level} · {team.xp} XP · série {team.streak} j</p>}
      </div>
      {team && (
        <>
          <div className="card">
            <h3>Compétences</h3>
            {Object.keys(team.skills).length === 0 && <p className="note">Aucune compétence pour l'instant.</p>}
            {Object.entries(team.skills).map(([k, v]) => (
              <div key={k} className="row between"><span>{k}</span><span className="stat">niveau {team.skill_levels[k]} · {v} XP</span></div>
            ))}
          </div>
          <div className="card">
            <h3>Inventaire</h3>
            {team.inventory.length === 0 && <p className="note">Inventaire vide.</p>}
            {team.inventory.map((it, i) => (
              <div key={i} className="row between"><span>{it.name}</span><span className="time">{it.type} · {it.rarity}</span></div>
            ))}
          </div>
          <div className="card">
            <p className="stat">Jetons : {team.tokens}</p>
            <button className="btn" onClick={pull}>Invoquer</button>
            {pulled && <p className="fb ok" role="status">Obtenu : {pulled.name} ({pulled.rarity})</p>}
          </div>
        </>
      )}
      {msg && <p className="note" role="alert">{msg}</p>}
    </section>
  )
}
