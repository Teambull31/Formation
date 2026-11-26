import { getPushKey, pushSubscribe } from './api'

// Web Push needs a service worker, hence https (or localhost) and, on iPhone, the installed app.
export const pushSupported = () =>
  typeof window !== 'undefined' && window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

const toBytes = (b64url: string) => {
  const raw = atob(b64url.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(b64url.length / 4) * 4, '='))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

/** Permission, abonnement de ce navigateur, enregistrement côté serveur. Renvoie un message d'échec, ou null si c'est fait. */
export async function enablePush(): Promise<string | null> {
  if ((await Notification.requestPermission()) !== 'granted') return 'Notifications refusées dans le navigateur.'
  const reg = await navigator.serviceWorker.ready
  const { key } = await getPushKey()
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toBytes(key) })
  await pushSubscribe(sub.toJSON())
  return null
}
