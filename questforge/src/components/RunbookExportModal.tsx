import React, { useState, useEffect } from 'react';
import {
  FileText,
  Copy,
  Check,
  Download,
  X,
  Sparkles,
  BookOpen,
  Terminal,
  ShieldAlert,
} from 'lucide-react';
import { api, RunbookDocument } from '../api';

interface RunbookExportModalProps {
  lessonId?: string;
  title?: string;
  onClose: () => void;
}

export const RunbookExportModal: React.FC<RunbookExportModalProps> = ({
  lessonId = 'l1',
  title = 'Procédure Opérationnelle Standard (SOP)',
  onClose,
}) => {
  const [runbook, setRunbook] = useState<RunbookDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [activeView, setActiveView] = useState<'preview' | 'raw'>('preview');

  useEffect(() => {
    api
      .generateRunbook(lessonId, title)
      .then((data) => setRunbook(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [lessonId, title]);

  const handleCopy = () => {
    if (!runbook) return;
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(runbook.markdown);
      }
    } catch {}
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!runbook) return;
    const blob = new Blob([runbook.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `runbook_${runbook.lessonId}_${Date.now()}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-100">
                  Générateur de Runbook SRE (Markdown & Notion)
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  Export Documenté
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Transformez cet exercice pratique en procédure opérationnelle standard prête pour votre équipe.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 cursor-pointer transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Toolbar */}
        <div className="px-4 py-2.5 bg-slate-950/50 border-b border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setActiveView('preview')}
              className={`px-3 py-1 rounded-xl font-medium cursor-pointer transition-all ${
                activeView === 'preview'
                  ? 'bg-amber-500 text-slate-950 font-bold'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Aperçu Rendu
            </button>
            <button
              onClick={() => setActiveView('raw')}
              className={`px-3 py-1 rounded-xl font-medium cursor-pointer transition-all ${
                activeView === 'raw'
                  ? 'bg-amber-500 text-slate-950 font-bold'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Markdown Brut
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className={`px-3 py-1 rounded-xl font-bold text-xs flex items-center gap-1.5 cursor-pointer transition-all ${
                copied
                  ? 'bg-emerald-500 text-slate-950'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
              }`}
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copié !' : 'Copier Markdown'}</span>
            </button>

            <button
              onClick={handleDownload}
              className="px-3 py-1 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 cursor-pointer shadow-md shadow-amber-500/20 transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Télécharger (.md)</span>
            </button>
          </div>
        </div>

        {/* Document Content */}
        <div className="flex-1 overflow-y-auto p-4 bg-slate-950/60 font-mono text-xs text-slate-300">
          {runbook ? (
            activeView === 'preview' ? (
              <div className="space-y-4 max-w-2xl mx-auto font-sans">
                <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                  <span className="text-[10px] font-mono text-amber-400 font-bold uppercase">
                    Procédure Opérationnelle Standard (SOP)
                  </span>
                  <h3 className="text-base font-extrabold text-slate-100">{runbook.title}</h3>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {runbook.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3 leading-relaxed text-slate-300">
                  <h4 className="font-bold text-slate-100 border-b border-slate-800 pb-1 text-sm">
                    1. Déclencheur & Alerte P1/P2
                  </h4>
                  <p className="text-xs">
                    Défaillance de configuration ou refus de démarrage du pod/service. Les métriques RED indiquent une augmentation brutale des erreurs 5xx.
                  </p>

                  <h4 className="font-bold text-slate-100 border-b border-slate-800 pb-1 text-sm pt-2">
                    2. Commandes de Diagnostic Rapide (Triage)
                  </h4>
                  <pre className="p-2.5 bg-slate-950 rounded-lg text-emerald-400 font-mono text-[11px] overflow-x-auto">
                    {`ls -la config.json\npython3 -m json.tool config.json\nps aux | grep -i node`}
                  </pre>

                  <h4 className="font-bold text-slate-100 border-b border-slate-800 pb-1 text-sm pt-2">
                    3. Procédure de Rétablissement (Mitigation)
                  </h4>
                  <p className="text-xs">
                    Rétablir le fichier de configuration avec les droits appropriés (chmod 644) puis valider l'exécution avec le script de contrôle.
                  </p>
                  <pre className="p-2.5 bg-slate-950 rounded-lg text-emerald-400 font-mono text-[11px] overflow-x-auto">
                    {`echo '{"provider": "demo", "active": true}' > config.json\nbash check.sh`}
                  </pre>

                  <h4 className="font-bold text-slate-100 border-b border-slate-800 pb-1 text-sm pt-2">
                    4. Analyse de Cause Racine (RCA) & Checklist
                  </h4>
                  <ul className="list-disc list-inside text-xs space-y-1 text-slate-300">
                    <li>Isoler le pod avant redémarrage via ReadinessProbe.</li>
                    <li>Vérifier l'absence de secrets sensibles dans les variables d'environnement.</li>
                    <li>Documenter l'incident dans le canal Slack/Teams d'astreinte SRE.</li>
                  </ul>
                </div>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap select-all leading-relaxed max-w-2xl mx-auto">
                {runbook.markdown}
              </pre>
            )
          ) : (
            <div className="text-center py-10 text-slate-500">Génération du runbook...</div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
          <span>Compatible avec Obsidian, Notion, Confluence et GitHub Wiki.</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 cursor-pointer font-medium"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
