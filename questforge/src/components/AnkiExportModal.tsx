import React, { useState, useEffect } from 'react';
import {
  Download,
  Copy,
  Check,
  FileSpreadsheet,
  FileText,
  Brain,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import { api, Question } from '../api';

interface AnkiExportProps {
  onClose: () => void;
}

export const AnkiExportModal: React.FC<AnkiExportProps> = ({ onClose }) => {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedType, setCopiedType] = useState<string | null>(null);

  useEffect(() => {
    loadQuestions();
  }, []);

  const loadQuestions = async () => {
    setLoading(true);
    try {
      const res = await api.getReviews();
      setQuestions(res.due || []);
    } finally {
      setLoading(false);
    }
  };

  const generateAnkiCsv = (): string => {
    const rows = questions.map((q) => {
      const front = `"${q.text.replace(/"/g, '""')}"`;
      const back = `"${q.explain.replace(/"/g, '""')}<br><br><b>Choix proposés:</b><br>${q.options
        .map((o) => `• ${o}`)
        .join('<br>')}"`;
      return `${front}\t${back}\t"QuestForge"`;
    });
    return rows.join('\n');
  };

  const generateMarkdownCheatSheet = (): string => {
    const header = `# QuestForge — Fiche Mémo des Notions à Consolider
Générée automatiquement le ${new Date().toLocaleDateString('fr-FR')} à partir des boîtes de répétition espacée Leitner.

---
`;
    const body = questions
      .map(
        (q, idx) => `### ${idx + 1}. ${q.text}
- **Explication & Clé de Résolution** : ${q.explain}
- **Boîte Leitner** : Palier ${q.box ?? 0}
- **Rappels techniques** :
${q.options.map((opt) => `  - ${opt}`).join('\n')}
`
      )
      .join('\n');

    return header + body;
  };

  const handleCopy = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  const handleDownload = (content: string, filename: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const ankiContent = generateAnkiCsv();
  const cheatSheetContent = generateMarkdownCheatSheet();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-950 border border-purple-500/30 rounded-3xl max-w-xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl text-slate-100 animate-scale-up">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-100">Export Anki & Fiches Mémo</h2>
              <p className="text-[10px] text-slate-400">Répétition espacée hors-ligne & fiches condensées</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-7 h-7 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-5 flex-1">
          <div className="p-3 bg-purple-950/30 border border-purple-500/30 rounded-2xl flex items-center justify-between text-xs">
            <span className="text-purple-200">
              <strong>{questions.length} cartes</strong> sélectionnées depuis vos boîtes de Leitner.
            </span>
            <span className="text-[10px] font-mono text-purple-400 bg-purple-900/50 px-2 py-0.5 rounded-full">
              Prêt à exporter
            </span>
          </div>

          {/* Option 1 : Anki CSV Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-slate-100">Paquet Anki (.csv / .txt)</h3>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleCopy(ankiContent, 'anki')}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] font-semibold text-slate-300 flex items-center gap-1 cursor-pointer"
                >
                  {copiedType === 'anki' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedType === 'anki' ? 'Copié' : 'Copier'}</span>
                </button>
                <button
                  onClick={() => handleDownload(ankiContent, 'questforge_anki_deck.txt', 'text/tab-separated-values')}
                  className="px-2.5 py-1 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-[11px] font-bold text-slate-950 flex items-center gap-1 cursor-pointer"
                >
                  <Download className="w-3 h-3" />
                  <span>Télécharger</span>
                </button>
              </div>
            </div>
            <p className="text-[11px] text-slate-400">
              Compatible Anki Desktop et AnkiMobile. Importez directement avec séparateur tabulation.
            </p>
          </div>

          {/* Option 2 : Markdown Cheat Sheet */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold text-slate-100">Cheat-Sheet Personnalisée (.md)</h3>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleCopy(cheatSheetContent, 'cheatsheet')}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] font-semibold text-slate-300 flex items-center gap-1 cursor-pointer"
                >
                  {copiedType === 'cheatsheet' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedType === 'cheatsheet' ? 'Copié' : 'Copier'}</span>
                </button>
                <button
                  onClick={() => handleDownload(cheatSheetContent, 'questforge_cheat_sheet.md', 'text/markdown')}
                  className="px-2.5 py-1 rounded-lg bg-amber-500 hover:bg-amber-400 text-[11px] font-bold text-slate-950 flex items-center gap-1 cursor-pointer"
                >
                  <Download className="w-3 h-3" />
                  <span>Télécharger</span>
                </button>
              </div>
            </div>
            <p className="text-[11px] text-slate-400">
              Fiche récapitulative condensée à conserver dans Obsidian, Notion ou imprimer pour vos révisions.
            </p>
            <pre className="p-3 bg-black/80 rounded-xl text-[10px] font-mono text-slate-300 max-h-32 overflow-y-auto">
              {cheatSheetContent}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
