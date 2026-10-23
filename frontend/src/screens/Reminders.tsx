import { useEffect, useState } from 'react'
import { getPushKey, pushSubscribe, pushTest, pushUnsubscribe } from '../api'

// Web Push needs a service worker, hence https (or localhost) and, on iPhone, the installed app.
export const pushSupported = () =>
  window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

const toBytes = (b64url: string) => {
  const raw = atob(b64url.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(b64url.length / 4) * 4, '='))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

export default function Reminders() {
  const [on, setOn] = useState(false)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const ok = pushSupported()

  useEffect(() => {
    if (ok) navigator.serviceWorker.ready.then((r) => r.pushManager.getSubscription()).then((s) => setOn(!!s)).catch(() => {})
  }, [ok])

  const run = (p: () => Promise<string | void>) => {
    setBusy(true)
    p().then((m) => setMsg(m ?? '')).catch((e: Error) => setMsg(e.message || 'Erreur')).finally(() => setBusy(false))
  }

  const enable = async () => {
    if ((await Notification.requestPermission()) !== 'granted') return 'Notifications refusées dans le navigateur.'
    const reg = await navigator.serviceWorker.ready
    const { key } = await getPushKey()
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toBytes(key) })
    await pushSubscribe(sub.toJSON())
    setOn(true)
    return 'Rappel activé.'
  }

  const disable = async () => {
    const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription()
    if (sub) { await pushUnsubscribe(sub.endpoint); await sub.unsubscribe() }
    setOn(false)
    return 'Rappel désactivé.'
  }

  return (
    <div className="card">
      <h3>Rappel quotidien</h3>
      {!ok ? (
        <p className="note">Indisponible ici : il faut l'appli ouverte en https (sur iPhone, installée sur l'écran d'accueil).</p>
      ) : (
        <>
          <p className="note">Une notification en fin de journée si tu n'as encore rien fait, jamais les jours de repos.</p>
          <div className="row wrapf">
            <button className="btn" disabled={busy} onClick={() => run(on ? disable : enable)}>
              {on ? 'Désactiver le rappel' : 'Activer le rappel'}
            </button>
            {on && <button className="btn ghost" disabled={busy} onClick={() => run(() => pushTest().then(() => 'Notification envoyée.'))}>Tester</button>}
          </div>
        </>
      )}
      {msg && <p className="note" role="status">{msg}</p>}
    </div>
  )
}
