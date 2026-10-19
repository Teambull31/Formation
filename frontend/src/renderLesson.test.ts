import { describe, expect, test } from 'vitest'
import { renderLesson } from './renderLesson'

describe('renderLesson', () => {
  test('bold and red markers', () => {
    const h = renderLesson('a **b** !!c!!')
    expect(h).toContain('<strong>b</strong>')
    expect(h).toContain('<span class="key">c</span>')
  })
  test('html in lesson is escaped', () => {
    expect(renderLesson('<script>x</script>')).not.toContain('<script>')
  })
  test('img onerror is neutralised', () => {
    const h = renderLesson('<img src=x onerror=alert(1)>')
    expect(h).not.toContain('<img')
    expect(h).toContain('&lt;img')
  })
  test('markers inside code spans stay literal and escaped', () => {
    const h = renderLesson('`**x** <b>`')
    expect(h).toContain('<code>**x** &lt;b&gt;</code>')
    expect(h).not.toContain('<strong>')
  })
  test('unclosed or nested markers do not throw', () => {
    expect(() => renderLesson('**a **b** c')).not.toThrow()
    expect(() => renderLesson('**!!a**!!')).not.toThrow()
    expect(renderLesson('**open')).toContain('**open')
  })
  test('headings and lists', () => {
    const h = renderLesson('# T\n## U\n### V\n- a\n- **b**')
    expect(h).toContain('<h1>T</h1>')
    expect(h).toContain('<h2>U</h2>')
    expect(h).toContain('<h3>V</h3>')
    expect(h).toContain('<ul><li>a</li><li><strong>b</strong></li></ul>')
  })
  test('fenced code block is pre/code, escaped, no markers', () => {
    const h = renderLesson('```sh\necho "<a>" **x**\n```')
    expect(h).toContain('<pre><code>echo &quot;&lt;a&gt;&quot; **x**\n</code></pre>')
  })
})
