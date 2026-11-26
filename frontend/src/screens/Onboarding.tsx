import { useEffect, useState } from 'react'

// Démarrage : ce qui rend l'appli sans friction (https, installée, rappel actif, une première séance).
// Disparaît quand tout est fait, ou sur demande.
interface InstallEvent extends Event { prompt(): Promise<void> }
const KEY = 'demarrage-masque'

export default function Onboarding({ pushOff, sessionDone, onReminders }: { pushOff: boolean; sessionDone: boolean; onReminders: () => void }) {
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(KEY) === '1' } catch { return false } })
  const [install, setInstall] = useState<InstallEvent | null>(null)
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
    { ok: !pushOff, label: 'Activer le rappel quotidien', hint: "choisis l'heure et ton déclencheur" },
    { ok: sessionDone, label: 'Faire une première séance', hint: 'le gros bouton vert ci-dessus' },
  ]
  if (hidden || steps.every((s) => s.ok)) return null
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
          {!s.ok && s.label.startsWith('Activer') && secure && <button className="chip" onClick={onReminders}>Activer</button>}
        </div>
      ))}
    </div>
  )
}
