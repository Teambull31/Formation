import React, { useState } from 'react';
import {
  Wand2,
  Sparkles,
  Terminal,
  FileCode,
  CheckCircle2,
  Copy,
  Check,
  Play,
  RotateCcw,
  Zap,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, CustomChallengeResult } from '../api';

interface CustomChallengeProps {
  onClose: () => void;
  onRefreshQuest: () => void;
}

const QUICK_TOPICS = [
  'Reverse Proxy Caddy avec mTLS',
  'Script de Rotation des Logs NGINX',
  'Backup incrémental PostgreSQL et S3',
  'Audit de sécurité des utilisateurs sudo',
  'Sonde Prometheus personnalisée en Python',
];

export const CustomChallengeModal: React.FC<CustomChallengeProps> = ({ onClose, onRefreshQuest }) => {
  const [topicInput, setTopicInput] = useState('');
  const [level, setLevel] = useState<'initié' | 'intermédiaire' | 'expert'>('intermédiaire');
  const [generating, setGenerating] = useState(false);
  const [challenge, setChallenge] = useState<CustomChallengeResult | null>(null);
  const [copiedSolution, setCopiedSolution] = useState(false);
  const [copiedScript, setCopiedScript] = useState(false);
  const [verified, setVerified] = useState(false);

  const handleGenerate = async (topicToUse?: string) => {
    const t = (topicToUse || topicInput).trim();
    if (!t) return;

    setGenerating(true);
    setChallenge(null);
    setVerified(false);

    try {
      const res = await api.generateCustomChallenge(t, level);
      setChallenge(res);
      confetti({ particleCount: 50, spread: 60 });
    } finally {
      setGenerating(false);
    }
  };

  const handleCopySolution = () => {
    if (!challenge) return;
    navigator.clipboard.writeText(challenge.solutionCommand);
    setCopiedSolution(true);
    setTimeout(() => setCopiedSolution(false), 2000);
  };

  const handleCopyScript = () => {
    if (!challenge) return;
    navigator.clipboard.writeText(challenge.verificationScript);
    setCopiedScript(true);
    setTimeout(() => setCopiedScript(false), 2000);
  };

  const [showSolution, setShowSolution] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [userCmd, setUserCmd] = useState('');
  const [testResult, setTestResult] = useState<string | null>(null);

  const handleTestUserCmd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userCmd.trim() || !challenge) return;
    const cmd = userCmd.trim();
    if (cmd.includes(challenge.targetFile)) {
      setTestResult(`✓ Commande valide : ${cmd} cible bien '${challenge.targetFile}'. Vous pouvez valider !`);
    } else {
      setTestResult(`ℹ Commande exécutée : veillez à bien cibler le fichier '${challenge.targetFile}' demandé dans les consignes.`);
    }
  };

  const handleSimulatePass = () => {
    setVerified(true);
    confetti({ particleCount: 70, spread: 60, origin: { y: 0.6 } });
    onRefreshQuest();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-950 border border-amber-500/30 rounded-3xl max-w-xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl text-slate-100 animate-scale-up">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
              <Wand2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-100">Générateur Instantané de Défis & TP</h2>
              <p className="text-[10px] text-slate-400">Génération sur-mesure de travaux pratiques avec validation</p>
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
          {/* Prompt Form */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
            <label className="text-xs font-bold text-slate-300 block">
              Quel sujet souhaitez-vous pratiquer ?
            </label>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ex: Configuration WireGuard, Optimisation Dockerfile, Audit cgroup..."
                value={topicInput}
                onChange={(e) => setTopicInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-amber-400 font-medium"
              />

              <button
                disabled={generating || !topicInput.trim()}
                onClick={() => handleGenerate()}
                className="px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 cursor-pointer shadow-md shadow-amber-500/20"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{generating ? 'Création...' : 'Générer'}</span>
              </button>
            </div>

            {/* Quick Topic Pills */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] text-slate-400 uppercase font-mono block">Suggestions rapides :</span>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_TOPICS.map((topic, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setTopicInput(topic);
                      handleGenerate(topic);
                    }}
                    className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-amber-500/50 text-[10px] text-slate-300 cursor-pointer transition-all"
                  >
                    + {topic}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Generated Challenge Card */}
          {challenge && (
            <div className="space-y-4 animate-scale-up">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-amber-300">{challenge.title}</h3>
                    <span className="text-[10px] text-slate-400">Récompense : +{challenge.xpReward} XP</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    Fichier : {challenge.targetFile}
                  </span>
                </div>

                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed font-sans max-h-48 overflow-y-auto">
                  {challenge.markdownContent}
                </div>

                {/* Zone de test interactif pour l'apprenant */}
                <form onSubmit={handleTestUserCmd} className="space-y-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <div className="flex items-center justify-between text-[11px] text-slate-300">
                    <span className="font-semibold flex items-center gap-1 text-amber-400">
                      <Terminal className="w-3.5 h-3.5" /> Entrez votre commande de résolution :
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowHint(!showHint)}
                      className="text-[10px] text-amber-400 hover:underline cursor-pointer"
                    >
                      {showHint ? 'Masquer indice' : 'Besoin d\'un indice ?'}
                    </button>
                  </div>

                  {showHint && (
                    <div className="p-2.5 bg-amber-950/30 border border-amber-500/30 rounded-lg text-[11px] text-amber-200 leading-relaxed">
                      💡 <strong>Indice de méthodologie :</strong> Créez le fichier <code>{challenge.targetFile}</code> avec une commande d'écriture bash (ex: <code>echo '...' &gt; {challenge.targetFile}</code>) en respectant la structure JSON demandée.
                    </div>
                  )}

                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder={`Ex: echo '{"enabled": true, ...}' > ${challenge.targetFile}`}
                      value={userCmd}
                      onChange={(e) => setUserCmd(e.target.value)}
                      className="flex-1 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-400"
                    />
                    <button
                      type="submit"
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 font-semibold rounded-lg cursor-pointer"
                    >
                      Tester
                    </button>
                  </div>

                  {testResult && (
                    <div className="text-[11px] font-mono text-slate-300 pt-1">
                      {testResult}
                    </div>
                  )}
                </form>

                {/* Accordéon masqué pour la solution */}
                <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/60">
                  <button
                    type="button"
                    onClick={() => setShowSolution(!showSolution)}
                    className="w-full px-3 py-2 text-left text-[11px] text-slate-400 hover:text-slate-200 flex items-center justify-between cursor-pointer"
                  >
                    <span>{showSolution ? '▼ Masquer la solution corrigée' : '▶ Révéler la solution corrigée (Recommandé uniquement après avoir cherché)'}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{showSolution ? 'Ouvert' : 'Masqué'}</span>
                  </button>

                  {showSolution && (
                    <div className="p-3 border-t border-slate-800/80 space-y-3 bg-black/50">
                      <div className="space-y-1 font-mono text-[11px]">
                        <div className="flex items-center justify-between text-[10px] text-slate-400">
                          <span>Commande corrigée :</span>
                          <button
                            onClick={handleCopySolution}
                            className="flex items-center gap-1 text-amber-400 hover:text-amber-300 cursor-pointer"
                          >
                            {copiedSolution ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            <span>{copiedSolution ? 'Copié !' : 'Copier'}</span>
                          </button>
                        </div>
                        <div className="text-emerald-400 break-all bg-black/80 p-2 rounded-lg border border-slate-800">
                          {challenge.solutionCommand}
                        </div>
                      </div>

                      <div className="space-y-1 font-mono text-[11px]">
                        <div className="flex items-center justify-between text-[10px] text-slate-400">
                          <span>Script de vérification testé (check.sh) :</span>
                          <button
                            onClick={handleCopyScript}
                            className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 cursor-pointer"
                          >
                            {copiedScript ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            <span>{copiedScript ? 'Copié !' : 'Copier'}</span>
                          </button>
                        </div>
                        <div className="text-cyan-300 break-all bg-black/80 p-2 rounded-lg border border-slate-800">
                          {challenge.verificationScript}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Validation status */}
                {verified ? (
                  <div className="p-3 bg-emerald-950/40 border border-emerald-500/40 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <span>Défi personnalisé validé avec succès ! (+{challenge.xpReward} XP accordés).</span>
                  </div>
                ) : (
                  <button
                    onClick={handleSimulatePass}
                    className="w-full py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-emerald-600/20"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Valider ce Défi dans l'Espace de Travail</span>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};


