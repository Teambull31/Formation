export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function renderLesson(md: string): string {
  if (!md) return '';

  // 1. Échapper le HTML d'entrée
  const escaped = escapeHtml(md);

  // 2. Traiter les blocs de code d'abord pour éviter d'y remplacer les marqueurs
  const codeBlocks: string[] = [];
  const withPlaceholders = escaped.replace(/```([a-z0-9_-]*)\n([\s\S]*?)```/gi, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(
      `<div class="my-4 rounded-lg bg-slate-900 border border-slate-800 overflow-hidden font-mono text-sm"><div class="px-3 py-1 bg-slate-800/80 text-xs text-slate-400 font-semibold uppercase tracking-wider">${lang || 'code'}</div><pre class="p-3 overflow-x-auto text-emerald-400"><code>${code.trim()}</code></pre></div>`
    );
    return `__CODE_BLOCK_${idx}__`;
  });

  // 3. Remplacer les marqueurs gras **x** et rouge !!x!!
  let html = withPlaceholders
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/!!([^!]+)!!/g, '<span class="key">$1</span>')
    .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-800 text-amber-300 font-mono text-xs border border-slate-700/60">$1</code>');

  // 4. Traiter ligne par ligne pour les titres, listes et paragraphes
  const lines = html.split('\n');
  const result: string[] = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      if (inList) {
        result.push('</ul>');
        inList = false;
      }
      continue;
    }

    if (trimmed.startsWith('__CODE_BLOCK_')) {
      if (inList) {
        result.push('</ul>');
        inList = false;
      }
      result.push(trimmed);
      continue;
    }

    // Titres
    if (trimmed.startsWith('### ')) {
      if (inList) { result.push('</ul>'); inList = false; }
      result.push(`<h3 class="text-lg font-bold text-slate-100 mt-5 mb-2">${trimmed.slice(4)}</h3>`);
      continue;
    }
    if (trimmed.startsWith('## ')) {
      if (inList) { result.push('</ul>'); inList = false; }
      result.push(`<h2 class="text-xl font-extrabold text-amber-400 mt-6 mb-3 border-b border-slate-800 pb-1.5 flex items-center gap-2">${trimmed.slice(3)}</h2>`);
      continue;
    }
    if (trimmed.startsWith('# ')) {
      if (inList) { result.push('</ul>'); inList = false; }
      result.push(`<h1 class="text-2xl font-black text-slate-50 mt-2 mb-4 tracking-tight">${trimmed.slice(2)}</h1>`);
      continue;
    }

    // Listes à puces
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        result.push('<ul class="list-disc list-inside space-y-1.5 my-3 text-slate-300">');
        inList = true;
      }
      result.push(`<li class="leading-relaxed">${trimmed.slice(2)}</li>`);
      continue;
    }

    // Ligne standard (paragraphe)
    if (inList) {
      result.push('</ul>');
      inList = false;
    }
    result.push(`<p class="my-2.5 leading-relaxed text-slate-300">${trimmed}</p>`);
  }

  if (inList) {
    result.push('</ul>');
  }

  // 5. Réinsérer les blocs de code
  let finalHtml = result.join('\n');
  codeBlocks.forEach((block, idx) => {
    finalHtml = finalHtml.replace(`__CODE_BLOCK_${idx}__`, block);
  });

  return finalHtml;
}
