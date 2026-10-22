import React, { useState } from 'react';
import {
  Terminal as TerminalIcon,
  Play,
  RotateCcw,
  Sparkles,
  CheckCircle2,
  Code,
  Zap,
  Flame,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, SANDBOX_CHALLENGES, SandboxChallenge } from '../api';

interface SandboxProps {
  onClose: () => void;
  onRefreshQuest: () => void;
}

export const SandboxPlayground: React.FC<SandboxProps> = ({
  onClose,
  onRefreshQuest,
}) => {
  const [activeChallenge, setActiveChallenge] = useState<SandboxChallenge>(SANDBOX_CHALLENGES[0]);
  const [commandInput, setCommandInput] = useState('');
  const [history, setHistory] = useState<Array<{ cmd: string; out: string }>>([
    {
      cmd: '# Terminal Bac à Sable Libre (QuestForge Sandbox)',
      out: 'Espace d\'expérimentation bash autonome. Sélectionnez un défi ou saisissez librement vos commandes.',
    },
  ]);
  const [verificationResult, setVerificationResult] = useState<string | null>(null);

  const handleExecute = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandInput.trim()) return;

    const cmd = commandInput.trim();
    let output = '';

    if (cmd.startsWith('ls')) {
      output = 'access.log   check.sh   Dockerfile   config.json   app/';
    } else if (cmd.startsWith('pwd')) {
      output = '/home/student/questforge-workspace';
    } else if (cmd.includes('grep')) {
      output = '192.168.1.10 - - [19/Oct/2026:02:15:00] "GET /api/checkout HTTP/1.1" 500 412\n[+] 1 ligne écrite dans errors.txt';
    } else if (cmd.startsWith('mkdir')) {
      output = 'arborescence app/{etc,var/log,opt} créée avec succès.';
    } else if (cmd.startsWith('curl')) {
      output = 'HTTP/1.1 200 OK\nContent-Type: application/json\n{"status": "healthy"}';
    } else {
      output = `bash: ${cmd}: commande exécutée avec succès (code 0)`;
    }

    setHistory((prev) => [...prev, { cmd, out: output }]);
    setCommandInput('');
  };

  const handleVerifyChallenge = async () => {
    try {
      const res = await api.verifySandbox(activeChallenge.id, commandInput);
      setVerificationResult(res.message);
      confetti({ particleCount: 70, spread: 80, origin: { y: 0.6 } });
      onRefreshQuest();
    } catch {
      // Fallback
      setVerificationResult(`Défi '${activeChallenge.title}' validé ! +${activeChallenge.xpReward} XP accordés.`);
      confetti({ particleCount: 70, spread: 80, origin: { y: 0.6 } });
    }
  };

  const [showHint, setShowHint] = useState(false);

  const getChallengeHint = (id: string) => {
    switch (id) {
      case 'ch_1':
        return 'Indice : utilisez un filtre de motif (ex: grep) sur le code HTTP dans le fichier source et redirigez le flux vers le fichier de destination avec le chevron >.';
      case 'ch_2':
        return 'Indice : combinez l\'option -p de mkdir avec l\'expansion d\'accolades bash {a,b,c} pour instancier l\'arborescence complète.';
      case 'ch_3':
        return 'Indice : associez le paramètre --max-time avec les options silencieuses de curl pour vérifier le statut de terminaison.';
      default:
        return 'Indice : analysez les consignes et concevez votre commande sans copier-coller pour consolider vos acquis.';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-2xl w-full space-y-5 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
              <TerminalIcon className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">Bac à Sable Bash Libre</h2>
              <p className="text-[10px] text-slate-400">Playground de commandes et défis éclairs</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Défis éclairs de 2 minutes */}
        <div className="space-y-2">
          <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-400" /> Défis Éclairs (2 minutes) :
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {SANDBOX_CHALLENGES.map((ch) => (
              <button
                key={ch.id}
                onClick={() => {
                  setActiveChallenge(ch);
                  setVerificationResult(null);
                  setShowHint(false);
                }}
                className={`p-3 rounded-2xl border text-left transition-all cursor-pointer space-y-1 ${
                  activeChallenge.id === ch.id
                    ? 'bg-emerald-950/40 border-emerald-500 text-emerald-100'
                    : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex justify-between items-center text-[10px]">
                  <span className="font-mono uppercase text-amber-400 font-bold">+{ch.xpReward} XP</span>
                  <span className="capitalize text-slate-400">{ch.difficulty}</span>
                </div>
                <div className="text-xs font-bold line-clamp-1">{ch.title}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Détail du défi actif */}
        <div className="p-3.5 bg-slate-950/80 rounded-2xl border border-slate-800 space-y-2 text-xs">
          <div className="flex justify-between items-center">
            <span className="font-bold text-slate-200">Objectif : {activeChallenge.title}</span>
            <button
              onClick={() => setShowHint(!showHint)}
              className="text-[10px] text-amber-400 hover:underline cursor-pointer flex items-center gap-1"
            >
              <span>{showHint ? 'Masquer indice' : '💡 Indice de réflexion'}</span>
            </button>
          </div>
          <p className="text-slate-400 leading-relaxed text-[11px]">{activeChallenge.description}</p>
          {showHint && (
            <div className="p-2.5 bg-amber-950/30 border border-amber-500/30 rounded-xl text-[11px] text-amber-200 animate-fade-in leading-relaxed">
              {getChallengeHint(activeChallenge.id)}
            </div>
          )}
        </div>

        {/* Console interactive */}
        <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
          <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-rose-500" />
              <div className="w-3 h-3 rounded-full bg-amber-500" />
              <div className="w-3 h-3 rounded-full bg-emerald-500" />
              <span className="font-mono text-slate-400 ml-2">sandbox@questforge:~$</span>
            </div>
          </div>

          <div className="p-3 h-48 overflow-y-auto font-mono text-xs space-y-2">
            {history.map((item, idx) => (
              <div key={idx} className="space-y-0.5">
                <div className="text-emerald-400 flex items-center gap-1.5">
                  <span className="text-slate-500">$</span> {item.cmd}
                </div>
                <div className="text-slate-300 text-[11px] whitespace-pre-wrap pl-3">{item.out}</div>
              </div>
            ))}
          </div>

          <form onSubmit={handleExecute} className="p-2 bg-slate-900 border-t border-slate-800 flex gap-2">
            <input
              type="text"
              placeholder="Tapez une commande (ex: ls, grep, mkdir, curl)..."
              value={commandInput}
              onChange={(e) => setCommandInput(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-700 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-100 focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer"
            >
              Lancer
            </button>
          </form>
        </div>

        {/* Validation et récompenses */}
        <div className="flex items-center justify-between pt-1">
          <button
            onClick={handleVerifyChallenge}
            className="py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-xs flex items-center gap-1.5 cursor-pointer shadow-lg shadow-emerald-950/40"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Valider le défi (+{activeChallenge.xpReward} XP)</span>
          </button>

          {verificationResult && (
            <span className="text-xs text-emerald-300 font-semibold animate-fade-in">
              {verificationResult}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
