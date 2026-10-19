import { useEffect, useRef } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { terminalUrl } from '../api'

// Connects straight to the page origin (never proxied). Server closes with 1008 when not local.
export default function Terminal({ onDenied }: { onDenied: () => void }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const term = new XTerm({ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 13, cursorBlink: true })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(box.current!)
    const ws = new WebSocket(terminalUrl())
    ws.binaryType = 'arraybuffer'
    const sendSize = () => {
      fit.fit()
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ resize: [term.rows, term.cols] }))
    }
    let opened = false
    ws.onopen = () => { opened = true; sendSize() }
    ws.onclose = (e) => { if (!opened || e.code === 1008) onDenied() }
    ws.onmessage = (e) => term.write(new Uint8Array(e.data as ArrayBuffer))
    const sub = term.onData((d) => { if (ws.readyState === WebSocket.OPEN) ws.send(d) })
    window.addEventListener('resize', sendSize)
    fit.fit()
    return () => {
      window.removeEventListener('resize', sendSize)
      sub.dispose(); ws.onclose = null; ws.close(); term.dispose()
    }
  }, [onDenied])
  return <div className="term-box" ref={box} aria-label="Terminal" />
}
