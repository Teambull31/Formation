import { useEffect, useRef, useState } from 'react'
import { audioUrl, getLessons, getPodcast, podcastUrl } from '../api'

interface Track { src: string; title: string; group: string; minutes: number }
const RATES = [1, 1.25, 1.5]
const KEY = 'ecoute'

// Position mémorisée par piste : on reprend là où la voiture s'est arrêtée. Stockage optionnel (navigation privée).
function load(): { src?: string; pos: Record<string, number> } {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '') } catch { return { pos: {} } }
}
function save(s: { src?: string; pos: Record<string, number> }) {
  try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* ignore */ }
}

export default function Listen() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [cur, setCur] = useState<number | null>(null)
  const [rate, setRate] = useState(1)
  const [err, setErr] = useState('')
  const el = useRef<HTMLAudioElement>(null)
  const mem = useRef(load())

  useEffect(() => {
    Promise.all([getPodcast(), getLessons()]).then(([eps, mods]) => {
      const t: Track[] = [
        ...eps.map((e) => ({ src: podcastUrl(e.file), title: e.title, group: 'Le livre du soir DevOps', minutes: e.minutes })),
        ...mods.flatMap((m) => m.lessons.map((l) => ({ src: audioUrl(l.id), title: l.title, group: `Leçons — ${m.title}`, minutes: l.minutes }))),
      ]
      setTracks(t)
      const i = t.findIndex((x) => x.src === mem.current.src)
      if (i >= 0) setCur(i)
    }).catch((e: Error) => setErr(e.message))
  }, [])

  const play = (i: number) => {
    if (i < 0 || i >= tracks.length) return
    if (i === cur) { el.current?.play(); return }
    setCur(i)
  }
  const track = cur === null ? null : tracks[cur]

  useEffect(() => {
    const a = el.current
    if (!a || !track) return
    mem.current.src = track.src
    save(mem.current)
    a.playbackRate = rate
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({ title: track.title, album: track.group, artist: 'Formation' })
      navigator.mediaSession.setActionHandler('nexttrack', () => play(cur! + 1))
      navigator.mediaSession.setActionHandler('previoustrack', () => play(cur! - 1))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track])

  const onLoaded = () => {
    const a = el.current!
    a.playbackRate = rate
    a.currentTime = mem.current.pos[track!.src] ?? 0
    a.play().catch(() => { /* lecture auto refusée : l'utilisateur appuie sur play */ })
  }
  const onTime = () => {
    const a = el.current!
    if (Math.floor(a.currentTime) % 5 === 0) { mem.current.pos[track!.src] = a.currentTime; save(mem.current) }
  }
  const onEnded = () => { mem.current.pos[track!.src] = 0; save(mem.current); play(cur! + 1) }
  const pick = (r: number) => { setRate(r); if (el.current) el.current.playbackRate = r }

  let last = ''
  return (
    <div className="wrap">
      <h2>Écoute</h2>
      <p className="note">Pour la voiture : les pistes s'enchaînent, la position est retenue, et les boutons suivant/précédent du volant marchent.
        Les audios des leçons sont créés à la première écoute (peut prendre une minute).</p>
      {err && <p className="fb">{err}</p>}
      <div className="card" style={{ position: 'sticky', top: 0, zIndex: 2 }}>
        <div className="tag">{track ? track.group : 'Choisissez une piste'}</div>
        <strong>{track?.title ?? '—'}</strong>
        <audio controls preload="none" ref={el} src={track?.src}
          onLoadedMetadata={onLoaded} onTimeUpdate={onTime} onEnded={onEnded} onPause={onTime} style={{ width: '100%' }} />
        <div className="row wrapf">
          <button className="chip" disabled={!cur} onClick={() => play(cur! - 1)} aria-label="Piste précédente">⏮</button>
          <button className="chip" disabled={cur === null || cur >= tracks.length - 1} onClick={() => play(cur! + 1)} aria-label="Piste suivante">⏭</button>
          {RATES.map((r) => (
            <button key={r} className="chip" aria-pressed={rate === r} onClick={() => pick(r)}>{r}x</button>
          ))}
        </div>
      </div>
      {tracks.map((t, i) => {
        const head = t.group !== last ? <div className="tag" style={{ marginTop: 8 }}>{t.group}</div> : null
        last = t.group
        return (
          <div key={t.src}>
            {head}
            <button className={'opt' + (i === cur ? ' right' : '')} aria-current={i === cur} onClick={() => play(i)}>
              <span className="row between"><span className="grow">{t.title}</span><span className="time">{t.minutes} min</span></span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
