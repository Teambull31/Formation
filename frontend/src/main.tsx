import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { flush } from './offline'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// installable app: service workers only exist on https or localhost
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('/sw.js').catch(() => {})
}

// réponses données hors réseau : envoyées au démarrage et dès que le réseau revient
flush().catch(() => {})
window.addEventListener('online', () => { flush().catch(() => {}) })
