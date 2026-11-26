// Synthèse vocale du navigateur, en promesse : la suite attend la fin de la phrase.
export const canSpeak = () => typeof speechSynthesis !== 'undefined'

export function say(text: string): Promise<void> {
  return new Promise((done) => {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'fr-FR'
    u.rate = 0.95
    u.onend = () => done()
    u.onerror = () => done()
    speechSynthesis.speak(u)
  })
}

export const pause = (ms: number) => new Promise((r) => setTimeout(r, ms))
