import { useEffect, useRef, useState } from 'react'
import Oral from './Oral'
import { audioUrl, completeStep, ficheAudioUrl, getLessons, getPodcast, getRevision, podcastDone, podcastUrl, revisionDone, revisionUrl } from '../api'

interface Track { src: string; title: string; group: string; minutes: number | null; lessonId?: string; fresh?: boolean }
const ROUTE_EPISODES = 3 // épisodes pas encore écoutés gardés prêts sur le téléphone
const AUTO_KEY = 'route-auto'
const AUDIO_CACHE = 'formation-audio' // même nom que dans public/sw.js
const RATES = [1, 1.25, 1.5]
const RECALL_S = 30 // pause « qu'as-tu retenu ? » après un épisode
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
  const [recall, setRecall] = useState(0) // secondes restantes de la pause de rappel
  const el = useRef<HTMLAudioElement>(null)
  const mem = useRef(load())

  useEffect(() => {
    Promise.all([getPodcast(), getLessons(), getRevision().catch(() => ({ items: 0, key: null }))]).then(([eps, mods, rev]) => {
      const t: Track[] = [
        ...(rev.key ? [{ src: revisionUrl(rev.key), title: `Révision express (${rev.items} questions)`, group: 'Aujourd\'hui', minutes: null }] : []),
        ...eps.map((e) => ({ src: podcastUrl(e.file), title: e.title, group: 'Le livre du soir DevOps', minutes: e.minutes, fresh: !e.listened })),
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
    const t = track!
    const quiet = () => { /* hors ligne : tant pis */ }
    if (t.lessonId) completeStep('lesson', t.lessonId).catch(quiet)
    else if (t.src.startsWith('/api/podcast/')) {
      podcastDone(decodeURIComponent(t.src.slice('/api/podcast/'.length))).catch(quiet)
      // rappel libre : résumer de mémoire, à voix haute, avant de passer à la suite
      if (typeof speechSynthesis !== 'undefined') {
        const u = new SpeechSynthesisUtterance("Qu'as-tu retenu ? Résume l'épisode en trois phrases, à voix haute. Tu as trente secondes.")
        u.lang = 'fr-FR'
        speechSynthesis.speak(u)
      }
      setRecall(RECALL_S)
      return
    }
    else if (t.src.startsWith('/api/revision/')) revisionDone().catch(quiet) // révision express écoutée = révisions du jour
    play(cur! + 1)
  }
  const [saved, setSaved] = useState<Set<string>>(new Set())
  const [cacheRead, setCacheRead] = useState(false)
  const [auto, setAuto] = useState(() => { try { return localStorage.getItem(AUTO_KEY) !== '0' } catch { return true } })
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const offline = typeof caches !== 'undefined' // seulement en HTTPS (contexte sécurisé)
  useEffect(() => {
    if (!offline) return
    caches.open(AUDIO_CACHE).then((c) => c.keys()).then((ks) => setSaved(new Set(ks.map((k) => new URL(k.url).pathname))))
      .catch(() => {}).finally(() => setCacheRead(true))
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
  // « Préparer la route » : la révision du jour et les prochains épisodes pas encore écoutés
  const route = tracks.filter((t) => t.group === "Aujourd'hui").map((t) => t.src)
    .concat(tracks.filter((t) => t.fresh).slice(0, ROUTE_EPISODES).map((t) => t.src))
  const routeMissing = route.filter((s) => !saved.has(s))
  const prepared = useRef(false)
  useEffect(() => {
    if (!offline || !auto || !cacheRead || !tracks.length || prepared.current) return
    prepared.current = true // une fois par ouverture de l'onglet ; seuls les manquants sont téléchargés
    if (routeMissing.length) download(routeMissing)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offline, auto, cacheRead, tracks])
  const toggleAuto = () => { setAuto(!auto); try { localStorage.setItem(AUTO_KEY, auto ? '0' : '1') } catch { /* facultatif */ } }

  const forget = async (src: string) => {
    await (await caches.open(AUDIO_CACHE)).delete(src)
    setSaved((x) => { const n = new Set(x); n.delete(src); return n })
  }

  useEffect(() => {
    if (recall <= 0) return
    const id = setTimeout(() => { if (recall === 1) play(cur! + 1); setRecall(recall - 1) }, 1000)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recall])

  const pick = (r: number) => { setRate(r); if (el.current) el.current.playbackRate = r }

  let last = ''
  return (
    <div className="wrap">
      <h2>Écoute</h2>
      <p className="note">Pour la voiture : les pistes s'enchaînent, la position est retenue, et les boutons suivant/précédent du volant marchent. ⬇ garde la piste sur le téléphone pour les zones sans réseau ; une leçon écoutée jusqu'au bout est validée.
        Les audios des leçons sont créés à la première écoute (peut prendre une minute).</p>
      {err && <p className="fb">{err}</p>}
      <Oral />
      {recall > 0 && (
        <div className="card" role="status">
          <strong>Qu'as-tu retenu ? Résume l'épisode en 3 phrases, à voix haute.</strong>
          <p className="stat">Suite dans {recall} s</p>
          <button className="chip" onClick={() => { setRecall(0); play(cur! + 1) }}>Passer</button>
        </div>
      )}
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
      {offline && route.length > 0 && (
        <div className="card">
          <button className="btn" disabled={!routeMissing.length} onClick={() => download(routeMissing)}>
            {routeMissing.length ? `Préparer la route (${route.length - routeMissing.length} / ${route.length} prêts)` : `✓ Route prête : ${route.length} piste(s) sur le téléphone`}
          </button>
          <label className="row">
            <input type="checkbox" checked={auto} onChange={toggleAuto} />
            <span className="note">Préparer automatiquement à l'ouverture de l'onglet</span>
          </label>
        </div>
      )}
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
