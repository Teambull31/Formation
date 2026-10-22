import React, { useState } from 'react';
import {
  Brain,
  X,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  BookOpen,
  Award,
  HelpCircle,
  Lightbulb,
  ArrowRight,
} from 'lucide-react';

interface FeynmanChallengeModalProps {
  onClose: () => void;
  onRewardExp?: (xp: number) => void;
}

interface ConceptTopic {
  id: string;
  title: string;
  category: string;
  juniorQuestion: string;
  forbiddenJargon: string[];
  analogyHints: string[];
  modelExplanation: string;
}

const CONCEPTS: ConceptTopic[] = [
  {
    id: 'cgroups_v2',
    title: 'cgroups v2 (Control Groups Linux)',
    category: 'Noyau Linux & Conteneurs',
    juniorQuestion: '« Pourquoi mon conteneur Docker/K8s se fait tuer s\'il consomme trop de RAM au lieu de ralentir ? »',
    forbiddenJargon: ['CFS bandwidth', 'OOM Killer bitwise', 'hierarchical unified tree'],
    analogyHints: ['Budget familial strict', 'Bocal à poissons', 'Compteur électrique qui disjoncte'],
    modelExplanation:
      'Imagine un compteur électrique avec un disjoncteur. cgroups v2 est le disjoncteur du noyau Linux : on donne à chaque conteneur une limite stricte de mémoire (ex: 512 Mo). Si l\'application essaie de tirer plus d\'énergie que le contrat alloué, le système coupe net le courant (SIGKILL) plutôt que de faire sauter l\'électricité de tout l\'immeuble (le serveur hôte).',
  },
  {
    id: 'ebpf',
    title: 'eBPF (Extended Berkeley Packet Filter)',
    category: 'Kernel & Observabilité',
    juniorQuestion: '« C\'est quoi eBPF et pourquoi tout le monde en parle pour remplacer les agents de monitoring ? »',
    forbiddenJargon: ['JIT compiler bytecode in-kernel verifier', 'ringbuffer perf map'],
    analogyHints: ['Agent de sécurité avec des lunettes à rayons X', 'Plugin JavaScript dans le navigateur', 'Douanier'],
    modelExplanation:
      'Habituellement, pour ajouter du code dans le noyau Linux, il fallait modifier le moteur de la voiture en marche ou installer un pilote risqué. eBPF fonctionne comme une mini machine virtuelle ultra sécurisée : c\'est comme installer un plugin dans un navigateur web, mais directement au cœur de l\'OS. On peut écouter chaque paquet réseau ou appel système à la volée à la vitesse de la lumière sans jamais faire crasher le serveur.',
  },
  {
    id: 'zombie_process',
    title: 'Processus Zombie & init PID 1',
    category: 'Processus UNIX',
    juniorQuestion: '« Un processus zombie consomme-t-il de la mémoire ? Pourquoi on ne peut pas le tuer avec kill -9 ? »',
    forbiddenJargon: ['wait4 syscall', 'task_struct pointer reaping', 'SIGCHLD signal handling'],
    analogyHints: ['Certificat de décès non signé', 'Fantôme administratif', 'Colis livré en attente de signature'],
    modelExplanation:
      'Un zombie est déjà mort : il ne consomme ni CPU ni mémoire RAM ! C\'est simplement une ligne restante dans le grand carnet d\'état civil du noyau. Il attend juste que son processus parent vienne signer son certificat de décès (avec l\'appel wait). On ne peut pas le tuer avec un revolver (kill -9) parce qu\'on ne peut pas tuer ce qui est déjà mort ! Seul le parent ou le processus orphelin recueilli par PID 1 peut effacer sa ligne.',
  },
  {
    id: 'raft_quorum',
    title: 'Quorum Raft & Consensus (Etcd / K8s)',
    category: 'Systèmes Distribués',
    juniorQuestion: '« Pourquoi un cluster Kubernetes a toujours 3 ou 5 nœuds de contrôle et jamais 4 ou 6 ? »',
    forbiddenJargon: ['split-brain partition vector clock', 'leader election epoch term'],
    analogyHints: ['Vote à la majorité absolue', 'Jury d\'assises impair', 'Démocratie sans égalité possible'],
    modelExplanation:
      'Pour se mettre d\'accord sur la vérité sans risque d\'égalité ou de schisme, une démocratie distribuée exige la majorité stricte : (N/2) + 1. Avec 3 membres, la majorité est 2 (on tolère 1 panne). Avec 4 membres, la majorité requise est 3 (on ne tolère toujours qu\'une seule panne !). Avoir un nombre pair augmente le risque de coupure en deux moitiés égales sans apporter aucune tolérance aux pannes supplémentaire.',
  },
];

export const FeynmanChallengeModal: React.FC<FeynmanChallengeModalProps> = ({ onClose, onRewardExp }) => {
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [userText, setUserText] = useState<string>('');
  const [evaluated, setEvaluated] = useState<boolean>(false);
  const [showModel, setShowModel] = useState<boolean>(false);

  const concept = CONCEPTS[selectedIdx];

  const wordCount = userText.trim().split(/\s+/).filter(Boolean).length;
  const hasAnalogyWord = /comme|imagine|façon|ressemble|exemple|métaphore|analogie/i.test(userText);
  const hasGoodLength = wordCount >= 25 && wordCount <= 120;

  const handleSelectConcept = (idx: number) => {
    setSelectedIdx(idx);
    setUserText('');
    setEvaluated(false);
    setShowModel(false);
  };

  const handleEvaluate = () => {
    setEvaluated(true);
    if (onRewardExp && hasGoodLength) {
      onRewardExp(50);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-black text-slate-100">
                  Défi Feynman : "Explique à un Junior"
                </h2>
                <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  VULGARISATION TECHNIQUE SRE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                La maîtrise commence quand vous pouvez expliquer l'incompréhensible avec une tasse de café
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-2 rounded-xl hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Concept Selector */}
        <div className="bg-slate-950/60 border-b border-slate-800 px-4 py-2.5 flex items-center gap-2 overflow-x-auto text-xs">
          {CONCEPTS.map((c, idx) => (
            <button
              key={c.id}
              onClick={() => handleSelectConcept(idx)}
              className={`px-3 py-1.5 rounded-lg border font-medium whitespace-nowrap transition-all ${
                selectedIdx === idx
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/40 shadow-sm'
                  : 'bg-slate-800/40 text-slate-400 border-slate-700/60 hover:text-slate-200'
              }`}
            >
              {c.title.split('(')[0]}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {/* Junior question card */}
          <div className="bg-purple-950/20 border border-purple-500/30 rounded-xl p-4 space-y-2">
            <span className="text-[11px] font-bold text-purple-400 uppercase tracking-wider block">
              Question posée par un développeur junior :
            </span>
            <p className="text-sm font-semibold text-slate-200 italic">
              {concept.juniorQuestion}
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] text-slate-400">
              <span className="font-semibold text-slate-300">Pistes d'analogies suggérées :</span>
              {concept.analogyHints.map((hint, i) => (
                <span
                  key={i}
                  className="bg-slate-900 border border-purple-800/40 text-purple-300 px-2 py-0.5 rounded-md font-mono"
                >
                  💡 {hint}
                </span>
              ))}
            </div>
          </div>

          {/* User explanation box */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <label className="font-bold text-slate-300 flex items-center gap-1.5">
                <Lightbulb className="w-4 h-4 text-amber-400" />
                Votre explication simplifiée (25 à 120 mots) :
              </label>
              <span
                className={`font-mono text-[11px] ${
                  hasGoodLength ? 'text-emerald-400 font-bold' : 'text-slate-400'
                }`}
              >
                {wordCount} mots {hasGoodLength ? '✓ Optimal' : '(Objectif : 25 - 120 mots)'}
              </span>
            </div>
            <textarea
              rows={4}
              value={userText}
              onChange={(e) => setUserText(e.target.value)}
              placeholder="Commencez par une analogie du monde réel : 'Imagine un restaurant où...', 'C'est comme un facteur qui...'"
              className="w-full bg-slate-950/70 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-200 focus:outline-none focus:border-purple-500 leading-relaxed font-sans"
            />
          </div>

          {/* Real-time Quality Checker */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div
              className={`p-3 rounded-xl border flex items-center gap-2.5 ${
                hasAnalogyWord
                  ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-400'
              }`}
            >
              <CheckCircle2
                className={`w-4 h-4 ${hasAnalogyWord ? 'text-emerald-400' : 'text-slate-600'}`}
              />
              <span>Présence d'une analogie imagée</span>
            </div>
            <div
              className={`p-3 rounded-xl border flex items-center gap-2.5 ${
                hasGoodLength
                  ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-400'
              }`}
            >
              <CheckCircle2
                className={`w-4 h-4 ${hasGoodLength ? 'text-emerald-400' : 'text-slate-600'}`}
              />
              <span>Concision & Clarté sans digression</span>
            </div>
          </div>

          {/* Model solution comparison */}
          {showModel && (
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-2 animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                  <Award className="w-4 h-4" />
                  Explication Modèle (Staff SRE) :
                </span>
                <span className="text-[10px] text-slate-400 font-mono">100% Blameless & Clair</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                {concept.modelExplanation}
              </p>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="p-4 sm:p-5 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between gap-3">
          <button
            onClick={() => setShowModel(!showModel)}
            className="flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 font-bold px-3 py-2 rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <BookOpen className="w-4 h-4" />
            <span>{showModel ? 'Masquer la solution' : 'Voir l\'explication modèle'}</span>
          </button>

          <div className="flex items-center gap-2">
            {!evaluated ? (
              <button
                disabled={wordCount < 15}
                onClick={handleEvaluate}
                className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold px-4 py-2 rounded-xl text-xs transition-all shadow-md shadow-purple-900/40 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-4 h-4" />
                <span>Soumettre l'explication (+50 XP)</span>
              </button>
            ) : (
              <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-bold bg-emerald-950/40 border border-emerald-500/30 px-3 py-1.5 rounded-xl">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Défi validé ! Badge Pédagogue débloqué</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
