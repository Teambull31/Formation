import React, { useState } from 'react';
import {
  Activity,
  X,
  TrendingUp,
  AlertOctagon,
  ShieldAlert,
  Zap,
  Sparkles,
  RefreshCw,
  Trophy,
  CheckCircle2,
  AlertTriangle,
  Server,
  Layers,
} from 'lucide-react';

interface SloSimulatorModalProps {
  onClose: () => void;
  onRewardExp?: (xp: number) => void;
}

interface IncidentEvent {
  title: string;
  desc: string;
  budgetDrain: number;
  mitigatedDrain: number;
}

const RANDOM_EVENTS: IncidentEvent[] = [
  {
    title: '🔥 Panne DNS du fournisseur Cloud',
    desc: 'Baisse globale de joignabilité pendant 18 minutes sur la région EMEA.',
    budgetDrain: 30,
    mitigatedDrain: 10,
  },
  {
    title: '⚠️ Régression N+1 Queries sur la page Panier',
    desc: 'Saturation brutale du pool de connexions PostgreSQL lors du pic de midi.',
    budgetDrain: 25,
    mitigatedDrain: 8,
  },
  {
    title: '⚡ Pic de trafic x5 inopiné (Campagne Marketing)',
    desc: 'L\'Ingress Controller throttle les requêtes avant que l\'Autoscaler ne réagisse.',
    budgetDrain: 20,
    mitigatedDrain: 5,
  },
  {
    title: '🐞 Fuite de mémoire Goroutines dans le microservice Auth',
    desc: 'CrashLoopBackOff progressif des instances toutes les 4 heures.',
    budgetDrain: 22,
    mitigatedDrain: 7,
  },
];

export const SloSimulatorModal: React.FC<SloSimulatorModalProps> = ({ onClose, onRewardExp }) => {
  const [targetSlo, setTargetSlo] = useState<'99.9%' | '99.99%'>('99.9%');
  const [sprint, setSprint] = useState<number>(1);
  const maxSprints = 6;

  // Reliability Engine State
  const [errorBudgetPercent, setErrorBudgetPercent] = useState<number>(100);
  const [featureVelocityScore, setFeatureVelocityScore] = useState<number>(0);
  const [observabilityLevel, setObservabilityLevel] = useState<number>(1);
  const [resilienceLevel, setResilienceLevel] = useState<number>(1);

  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const [isFrozen, setIsFrozen] = useState<boolean>(false);
  const [gameFinished, setGameFinished] = useState<boolean>(false);

  const handleDecision = (actionType: 'aggressive' | 'canary' | 'resilience' | 'observability') => {
    if (gameFinished) return;

    let newVelocity = featureVelocityScore;
    let newBudget = errorBudgetPercent;
    let newObs = observabilityLevel;
    let newRes = resilienceLevel;
    let eventLog = '';

    // Apply decision benefits
    if (actionType === 'aggressive') {
      if (isFrozen) {
        eventLog = '🚫 FEATURE FREEZE ACTIF : Déploiements bloqués par l\'équipe SRE ! Vous devez restaurer la fiabilité.';
      } else {
        newVelocity += 30;
        eventLog = '🚀 Déploiement Big Bang effectué : +30 Vélocité Produit.';
      }
    } else if (actionType === 'canary') {
      if (isFrozen) {
        newVelocity += 5;
        eventLog = '⚠️ Déploiement Canari sous dérogation : +5 Vélocité Produit.';
      } else {
        newVelocity += 18;
        eventLog = '🐥 Déploiement Canari & Feature Flags : +18 Vélocité Produit, risque maîtrisé.';
      }
    } else if (actionType === 'resilience') {
      newRes += 1;
      newBudget = Math.min(100, newBudget + 20);
      eventLog = '🛡️ Refactoring & Chaos Engineering : +20% d\'Error Budget reconstitué !';
    } else if (actionType === 'observability') {
      newObs += 1;
      newBudget = Math.min(100, newBudget + 10);
      eventLog = '📡 Observabilité & Alerting affiné : Burn rate sous contrôle et détection rapide.';
    }

    // Trigger incident chance
    const roll = Math.random();
    const incidentChance = actionType === 'aggressive' ? 0.75 : actionType === 'canary' ? 0.35 : 0.15;

    if (roll < incidentChance) {
      const evt = RANDOM_EVENTS[Math.floor(Math.random() * RANDOM_EVENTS.length)];
      // Mitigation discount based on resilience and observability
      const reduction = Math.min(0.7, (newObs - 1) * 0.15 + (newRes - 1) * 0.2);
      const impact = Math.round(evt.budgetDrain * (1 - reduction));
      newBudget = Math.max(0, newBudget - impact);
      eventLog += ` | 💥 ${evt.title} (-${impact}% Error Budget)`;
    }

    // Check freeze
    const frozenState = newBudget <= 10;
    setIsFrozen(frozenState);

    setErrorBudgetPercent(newBudget);
    setFeatureVelocityScore(newVelocity);
    setObservabilityLevel(newObs);
    setResilienceLevel(newRes);
    setLastEvent(eventLog);

    if (sprint >= maxSprints) {
      setGameFinished(true);
      if (onRewardExp) {
        const bonus = newBudget > 20 ? 80 : 40;
        onRewardExp(bonus);
      }
    } else {
      setSprint(sprint + 1);
    }
  };

  const handleRestart = () => {
    setSprint(1);
    setErrorBudgetPercent(100);
    setFeatureVelocityScore(0);
    setObservabilityLevel(1);
    setResilienceLevel(1);
    setLastEvent(null);
    setIsFrozen(false);
    setGameFinished(false);
  };

  const maxAllowedDowntime = targetSlo === '99.9%' ? '43 min 12 sec' : '4 min 19 sec';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-black text-slate-100">
                  Simulateur SLI / SLO & Error Budget
                </h2>
                <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  RELIABILITY ENGINE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Arbitrez entre cadence de livraison de code et disponibilité de production
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

        {/* Status Dashboard */}
        <div className="bg-slate-950/70 border-b border-slate-800 p-4 sm:p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-semibold">Cible SLO :</span>
              <button
                onClick={() => setTargetSlo('99.9%')}
                className={`px-2.5 py-1 rounded-lg border font-mono font-bold transition-all ${
                  targetSlo === '99.9%'
                    ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-sm'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                99.9% (Three Nines)
              </button>
              <button
                onClick={() => setTargetSlo('99.99%')}
                className={`px-2.5 py-1 rounded-lg border font-mono font-bold transition-all ${
                  targetSlo === '99.99%'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-sm'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                99.99% (Four Nines)
              </button>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-slate-400 font-mono">
                Downtime max autorisé : <strong className="text-slate-200">{maxAllowedDowntime}</strong>
              </span>
              <span className="bg-slate-800 px-3 py-1 rounded-lg border border-slate-700 text-amber-400 font-mono font-bold">
                Sprint {sprint} / {maxSprints}
              </span>
            </div>
          </div>

          {/* Error budget meter */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-300 font-bold flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-cyan-400" />
                Budget d'Erreur Restant (Error Budget)
              </span>
              <span
                className={`font-black ${
                  errorBudgetPercent > 50
                    ? 'text-emerald-400'
                    : errorBudgetPercent > 20
                    ? 'text-amber-400'
                    : 'text-rose-400 animate-pulse'
                }`}
              >
                {errorBudgetPercent}%
              </span>
            </div>
            <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden border border-slate-800 p-0.5">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  errorBudgetPercent > 50
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                    : errorBudgetPercent > 20
                    ? 'bg-gradient-to-r from-amber-500 to-yellow-400'
                    : 'bg-gradient-to-r from-rose-600 to-red-500'
                }`}
                style={{ width: `${errorBudgetPercent}%` }}
              />
            </div>
          </div>

          {/* Metric cards */}
          <div className="grid grid-cols-3 gap-2.5 text-center text-xs">
            <div className="bg-slate-900 border border-slate-800 p-2.5 rounded-xl">
              <span className="text-slate-400 block text-[11px] mb-0.5">Vélocité Produit</span>
              <span className="text-base font-black text-amber-400 font-mono">
                {featureVelocityScore} pts
              </span>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-2.5 rounded-xl">
              <span className="text-slate-400 block text-[11px] mb-0.5">Niveau Observabilité</span>
              <span className="text-base font-black text-cyan-400 font-mono">
                Lvl {observabilityLevel}
              </span>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-2.5 rounded-xl">
              <span className="text-slate-400 block text-[11px] mb-0.5">Résilience & Chaos</span>
              <span className="text-base font-black text-emerald-400 font-mono">
                Lvl {resilienceLevel}
              </span>
            </div>
          </div>
        </div>

        {/* Main interactive area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {/* Active warning or freeze */}
          {isFrozen && !gameFinished && (
            <div className="bg-rose-950/40 border border-rose-500/40 rounded-xl p-3.5 flex items-center gap-3 text-xs text-rose-300">
              <AlertOctagon className="w-6 h-6 text-rose-400 shrink-0 animate-bounce" />
              <div>
                <strong className="block text-rose-200 uppercase font-black tracking-wide">
                  🚨 FEATURE FREEZE DÉCLENCHÉ PAR L'ÉQUIPE SRE !
                </strong>
                <span>
                  Le budget d'erreur est épuisé (&lt;10%). Les déploiements de fonctionnalités agressives sont
                  bloqués. Consacrez vos sprints à la résilience et à la fiabilisation !
                </span>
              </div>
            </div>
          )}

          {/* Event feedback feed */}
          {lastEvent && (
            <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3 text-xs text-slate-300 font-mono">
              <span className="text-cyan-400 font-bold block mb-1">Rapport du Sprint précédent :</span>
              {lastEvent}
            </div>
          )}

          {/* Decision Cards */}
          {!gameFinished ? (
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Choisissez la stratégie du Sprint {sprint} :
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  disabled={isFrozen}
                  onClick={() => handleDecision('aggressive')}
                  className={`p-3.5 rounded-xl border text-left transition-all ${
                    isFrozen
                      ? 'bg-slate-900/50 border-slate-800 text-slate-600 cursor-not-allowed opacity-60'
                      : 'bg-slate-950/60 border-slate-800 hover:border-amber-500/50 hover:bg-slate-900/80 cursor-pointer'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                      <Zap className="w-4 h-4" />
                      Déploiement Agressif
                    </span>
                    <span className="text-[10px] font-mono text-amber-300 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/40">
                      +30 Vélocité
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Release immédiate de gros blocs de code. Risque élevé d'incident sévère (-25% à -40% d'error budget).
                  </p>
                </button>

                <button
                  onClick={() => handleDecision('canary')}
                  className="bg-slate-950/60 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-900/80 p-3.5 rounded-xl text-left transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4" />
                      Canari & Feature Flags
                    </span>
                    <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/40">
                      +18 Vélocité
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Déploiement progressif à 5% du trafic avec rollback instantané. Risque et impact d'incident faibles.
                  </p>
                </button>

                <button
                  onClick={() => handleDecision('resilience')}
                  className="bg-slate-950/60 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-900/80 p-3.5 rounded-xl text-left transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                      <Server className="w-4 h-4" />
                      Résilience & Chaos Testing
                    </span>
                    <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                      +20% Budget
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Remboursement de dette technique, tests d'injection de pannes et consolidation du budget d'erreur.
                  </p>
                </button>

                <button
                  onClick={() => handleDecision('observability')}
                  className="bg-slate-950/60 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-900/80 p-3.5 rounded-xl text-left transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                      <Layers className="w-4 h-4" />
                      Observabilité & Alerting
                    </span>
                    <span className="text-[10px] font-mono text-purple-300 bg-purple-950/60 px-1.5 py-0.5 rounded border border-purple-800/40">
                      +10% Budget
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Amélioration des alertes sur le burn rate multi-fenêtres pour détecter les fuites avant l'impact client.
                  </p>
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-5 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
                <Trophy className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-black text-slate-100">Cycle de Simulation Achevé !</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
                  {errorBudgetPercent > 30
                    ? '🎉 Succès éclatant : Vous avez maintenu le SLO contractuel tout en maintenant une excellente vélocité produit !'
                    : errorBudgetPercent > 0
                    ? '⚠️ Sur le fil : Le SLO est respecté de justesse mais le budget d\'erreur était critique.'
                    : '💥 Rupture de contrat : Le budget d\'erreur a été entièrement consommé. Revue de gouvernance SRE obligatoire !'}
                </p>
              </div>

              <div className="flex items-center justify-center gap-4 text-xs font-mono">
                <div className="bg-slate-900 px-3 py-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Vélocité Finale</span>
                  <span className="text-amber-400 font-bold">{featureVelocityScore} pts</span>
                </div>
                <div className="bg-slate-900 px-3 py-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Error Budget Résiduel</span>
                  <span className="text-emerald-400 font-bold">{errorBudgetPercent}%</span>
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={handleRestart}
                  className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs transition-all cursor-pointer shadow-md"
                >
                  Rejouer une Session
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs text-slate-400">
          <span>Google SRE Handbook • Chapitre 3 : Embracing Risk & Service Level Objectives</span>
          <button
            onClick={onClose}
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-xl font-medium transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
