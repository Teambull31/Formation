import { useEffect, useState } from 'react'
import { enablePush, pushSupported } from '../push'

// Démarrage : ce qui rend l'appli sans friction (https, installée, rappel actif, une première séance).
// Disparaît quand tout est fait, ou sur demande.
interface InstallEvent extends Event { prompt(): Promise<void> }
const KEY = 'demarrage-masque'

export default function Onboarding({ pushOff, sessionDone, onReminders }: { pushOff: boolean; sessionDone: boolean; onReminders: () => void }) {
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(KEY) === '1' } catch { return false } })
  const [install, setInstall] = useState<InstallEvent | null>(null)
  const [pushOn, setPushOn] = useState(false)
  const [msg, setMsg] = useState('')
  // un toucher : permission + abonnement ici, plutôt qu'un détour par l'onglet Équipe
  const activate = () => enablePush()
    .then((err) => { if (err) setMsg(err); else { setPushOn(true); setMsg('Rappel activé (19 h par défaut).') } })
    .catch((e: Error) => setMsg(e.message || 'Activation impossible.'))
  const secure = typeof window !== 'undefined' && window.isSecureContext
  const installed = typeof window !== 'undefined' && !!window.matchMedia?.('(display-mode: standalone)').matches
  useEffect(() => {
    const on = (e: Event) => { e.preventDefault(); setInstall(e as InstallEvent) }
    window.addEventListener('beforeinstallprompt', on)
    return () => window.removeEventListener('beforeinstallprompt', on)
  }, [])
  const steps = [
    { ok: secure, label: "Ouvrir l'appli par son adresse https (ex. …ts.net:8443)", hint: 'indispensable pour le hors ligne, la voix et les rappels' },
    { ok: installed, label: "L'installer sur l'écran d'accueil", hint: "menu du navigateur → « Ajouter à l'écran d'accueil »" },
    { ok: !pushOff || pushOn, label: 'Activer le rappel quotidien', hint: 'un toucher, puis accepte les notifications' },
    { ok: sessionDone, label: 'Faire une première séance', hint: 'le gros bouton vert ci-dessus' },
  ]
  if (hidden || (steps.every((s) => s.ok) && !msg)) return null
  const hide = () => { setHidden(true); try { localStorage.setItem(KEY, '1') } catch { /* facultatif */ } }
  return (
    <div className="card" aria-label="Bien démarrer">
      <div className="row between"><h3>Bien démarrer</h3><button className="chip" onClick={hide} aria-label="Masquer">✕</button></div>
      {steps.map((s) => (
        <div className="step" key={s.label}>
          <span className={'dot' + (s.ok ? ' done' : '')} aria-hidden>{s.ok ? '✓' : ''}</span>
          <div className="grow"><div>{s.label}</div>{!s.ok && <div className="time">{s.hint}</div>}</div>
          {!s.ok && s.label.startsWith("L'installer") && install && (
            <button className="chip" onClick={() => install.prompt().then(() => setInstall(null))}>Installer</button>
          )}
          {!s.ok && s.label.startsWith('Activer') && secure && (
            <button className="chip" onClick={pushSupported() ? activate : onReminders}>Activer</button>
          )}
        </div>
      ))}
      {msg && (
        <p className="note" role="status">{msg}{pushOn && <> <button className="chip" onClick={onReminders}>Choisir l'heure et le déclencheur</button></>}</p>
      )}
    </div>
  )
}
