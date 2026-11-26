import { useEffect, useState } from 'react'

// Hors réseau : dire une fois ce qui marche quand même, plutôt qu'une erreur par écran.
export default function OfflineBanner() {
  const [offline, setOffline] = useState(() => typeof navigator !== 'undefined' && navigator.onLine === false)
  useEffect(() => {
    const on = () => setOffline(false)
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])
  if (!offline) return null
  return (
    <p className="fb wrap" role="status">
      Hors ligne : cartes, leçons déjà ouvertes, glossaire et audio téléchargé marchent.
      Tes réponses aux cartes partent dès que le réseau revient.
    </p>
  )
}
