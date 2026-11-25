import { useEffect, useRef, useState } from 'react'
import { audioUrl, completeStep, ficheAudioUrl, getLessons, getPodcast, getRevision, podcastUrl, revisionUrl } from '../api'

interface Track { src: string; title: string; group: string; minutes: number | null; lessonId?: string }
const AUDIO_CACHE = 'formation-audio' // même nom que dans public/sw.js
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
    Promise.all([getPodcast(), getLessons(), getRevision().catch(() => ({ items: 0, key: null }))]).then(([eps, mods, rev]) => {
      const t: Track[] = [
        ...(rev.key ? [{ src: revisionUrl(rev.key), title: `Révision express (${rev.items} questions)`, group: 'Aujourd\'hui', minutes: null }] : []),
        ...eps.map((e) => ({ src: podcastUrl(e.file), title: e.title, group: 'Le livre du soir DevOps', minutes: e.minutes })),
        ...mods.filter((m) => m.fiche).map((m) => ({ src: ficheAudioUrl(m.id), title: m.title, group: 'Fiches de révision', minutes: null })),
        ...mods.flatMap((m) => m.lessons.map((l) => ({ src: audioUrl(l.id), title: l.title, group: `Leçons — ${m.title}`, minutes: l.minutes, lessonId: l.id }))),
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
  const onEnded = () => {
    mem.current.pos[track!.src] = 0
    save(mem.current)
    // leçon écoutée jusqu'au bout = étape « leçon » validée (mêmes règles que le bouton de l'onglet Leçon)
    if (track!.lessonId) completeStep('lesson', track!.lessonId).catch(() => { /* hors ligne : tant pis */ })
    play(cur! + 1)
  }
  const [saved, setSaved] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const offline = typeof caches !== 'undefined' // seulement en HTTPS (contexte sécurisé)
  useEffect(() => {
    if (!offline) return
    caches.open(AUDIO_CACHE).then((c) => c.keys()).then((ks) => setSaved(new Set(ks.map((k) => new URL(k.url).pathname))))
      .catch(() => {})
  }, [offline])
  const download = async (srcs: string[]) => {
    const todo = srcs.filter((s) => !saved.has(s) && !busy.has(s))
    setBusy((b) => new Set([...b, ...todo]))
    const c = await caches.open(AUDIO_CACHE)
    for (const s of todo) {
      try {
        await c.add(s) // un audio de leçon pas encore créé peut prendre une minute
        setSaved((x) => new Set([...x, s]))
      } catch (e) {
        setErr(`Téléchargement impossible : ${(e as Error).message}`)
      }
      setBusy((b) => { const n = new Set(b); n.delete(s); return n })
    }
  }
  const forget = async (src: string) => {
    await (await caches.open(AUDIO_CACHE)).delete(src)
    setSaved((x) => { const n = new Set(x); n.delete(src); return n })
  }

  const pick = (r: number) => { setRate(r); if (el.current) el.current.playbackRate = r }

  let last = ''
  return (
    <div className="wrap">
      <h2>Écoute</h2>
      <p className="note">Pour la voiture : les pistes s'enchaînent, la position est retenue, et les boutons suivant/précédent du volant marchent. ⬇ garde la piste sur le téléphone pour les zones sans réseau ; une leçon écoutée jusqu'au bout est validée.
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
      {offline && (
        <button className="btn ghost" onClick={() => download(tracks.filter((t) => t.group === 'Le livre du soir DevOps').map((t) => t.src))}>
          Télécharger les épisodes du livre pour la route ({[...saved].filter((s) => s.startsWith('/api/podcast/')).length} / {tracks.filter((t) => t.group === 'Le livre du soir DevOps').length})
        </button>
      )}
      {tracks.map((t, i) => {
        const head = t.group !== last ? <div className="tag" style={{ marginTop: 8 }}>{t.group}</div> : null
        last = t.group
        return (
          <div key={t.src}>
            {head}
            <div className="row">
              <button className={'opt grow' + (i === cur ? ' right' : '')} aria-current={i === cur} onClick={() => play(i)}>
                <span className="row between"><span className="grow">{t.title}</span>{t.minutes !== null && <span className="time">{t.minutes} min</span>}</span>
              </button>
              {offline && (saved.has(t.src)
                ? <button className="chip" onClick={() => forget(t.src)} aria-label={`Retirer du téléphone : ${t.title}`}>✓</button>
                : <button className="chip" disabled={busy.has(t.src)} onClick={() => download([t.src])} aria-label={`Télécharger : ${t.title}`}>{busy.has(t.src) ? '…' : '⬇'}</button>)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
