// Security: output goes to dangerouslySetInnerHTML (XSS == RCE via the terminal).
// Everything is HTML-escaped FIRST; only then are our own tags produced.
const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')

function inline(escaped: string): string {
  // split on code spans (odd indexes) so markers inside them stay literal
  return escaped
    .split(/(`[^`]*`)/)
    .map((part, i) => {
      if (i % 2) return `<code>${part.slice(1, -1)}</code>`
      return part
        .replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
        .replace(/!!(.+?)!!/g, '<span class="key">$1</span>')
    })
    .join('')
}

export function renderLesson(md: string): string {
  const out: string[] = []
  let list = false
  let code: string[] | null = null
  const closeList = () => {
    if (list) out.push('</ul>')
    list = false
  }
  for (const raw of md.split('\n')) {
    if (raw.startsWith('```')) {
      if (code) {
        out.push(`<pre><code>${code.join('')}</code></pre>`)
        code = null
      } else {
        closeList()
        code = []
      }
      continue
    }
    if (code) {
      code.push(esc(raw) + '\n')
      continue
    }
    const line = esc(raw)
    const h = /^(#{1,3}) (.*)$/.exec(line)
    const li = /^- (.*)$/.exec(line)
    if (li) {
      if (!list) out.push('<ul>')
      list = true
      out.push(`<li>${inline(li[1])}</li>`)
      continue
    }
    closeList()
    if (h) out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`)
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`)
  }
  closeList()
  if (code) out.push(`<pre><code>${(code as string[]).join('')}</code></pre>`) // unclosed fence
  return out.join('')
}
