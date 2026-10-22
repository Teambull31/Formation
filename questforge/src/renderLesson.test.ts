import { describe, test, expect } from 'vitest';
import { renderLesson } from './renderLesson';

describe('renderLesson', () => {
  test('bold and red markers', () => {
    const output = renderLesson('a **b** !!c!!');
    expect(output).toContain('<strong>b</strong>');
    expect(output).toContain('<span class="key">c</span>');
  });

  test('html in lesson is escaped', () => {
    const output = renderLesson('<script>x</script>');
    expect(output).not.toContain('<script>');
    expect(output).toContain('&lt;script&gt;x&lt;/script&gt;');
  });

  test('headers and list parsing', () => {
    const output = renderLesson('# Super Titre\n- Item 1\n- Item 2');
    expect(output).toContain('Super Titre');
    expect(output).toContain('<ul');
    expect(output).toContain('<li');
  });
});
