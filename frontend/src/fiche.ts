import type { Fiche } from './api'
import { renderLesson } from './renderLesson'

// Fichier HTML autonome : lisible hors ligne sur téléphone, imprimable en PDF depuis le navigateur.
const CSS = `body{font:16px/1.55 system-ui,sans-serif;max-width:46rem;margin:0 auto;padding:16px;color:#1b1b1f;background:#fff}
h1{font-size:1.6rem;border-bottom:3px solid #3b5bdb;padding-bottom:.3rem}h2{font-size:1.25rem;margin-top:1.6rem;color:#3b5bdb}
h3{font-size:1.05rem}code{background:#f1f3f5;padding:.1rem .3rem;border-radius:4px;font-size:.9em}
pre{background:#f1f3f5;padding:.7rem;border-radius:6px;overflow-x:auto}pre code{padding:0}
.key{color:#c92a2a;font-weight:600}.page{break-after:page}
@media (prefers-color-scheme:dark){body{background:#141517;color:#e9ecef}code,pre{background:#25262b}h2{color:#748ffc}.key{color:#ff8787}}
@media print{body{max-width:none}pre{white-space:pre-wrap}}`

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export function ficheHtml(title: string, fiches: Fiche[]): string {
  const body = fiches.map((f) => `<section class="page">${renderLesson(f.body_md)}</section>`).join('')
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">`
    + `<title>${esc(title)}</title><style>${CSS}</style></head><body>${body}</body></html>`
}

export function download(name: string, html: string): void {
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
