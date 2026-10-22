import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  Flame,
  ShieldAlert,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Terminal,
  FileText,
  Copy,
  Check,
  RotateCcw,
  Sparkles,
  ArrowRight,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, IncidentScenario, IncidentPhase, IncidentOption } from '../api';

interface WarRoomProps {
  onClose: () => void;
  onRefreshQuest: () => void;
}

export const WarRoomModal: React.FC<WarRoomProps> = ({ onClose, onRefreshQuest }) => {
  const [incidents, setIncidents] = useState<IncidentScenario[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [activeScenario, setActiveScenario] = useState<IncidentScenario | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<IncidentOption | null>(null);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [metrics, setMetrics] = useState({ rps: 0, errorRate: 0, latencyP99: 0 });
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const [isResolved, setIsResolved] = useState<boolean | null>(null);
  const [postMortemText, setPostMortemText] = useState('');
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadIncidents();
  }, []);

  const loadIncidents = async () => {
    setLoading(true);
    try {
      const res = await api.getIncidents();
      setIncidents(res.incidents);
      setHistory(res.history);
      if (res.incidents.length > 0) {
        startScenario(res.incidents[0]);
      }
    } finally {
      setLoading(false);
    }
  };

  const startScenario = (scenario: IncidentScenario) => {
    setActiveScenario(scenario);
    setCurrentStepIndex(0);
    setSelectedOption(null);
    setLiveLogs([...scenario.systemLogs]);
    setMetrics({ ...scenario.initialMetrics });
    setSecondsElapsed(0);
    setIsResolved(null);
    setPostMortemText('');
  };

  useEffect(() => {
    if (activeScenario && isResolved === null) {
      const timer = setInterval(() => {
        setSecondsElapsed((s) => s + 1);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [activeScenario, isResolved]);

  const handleChooseOption = (option: IncidentOption) => {
    if (selectedOption || isResolved !== null) return;
    setSelectedOption(option);

    // Update metrics and logs
    setMetrics((prev) => ({
      rps: Math.max(10, prev.rps + (option.isCorrect ? 150 : -200)),
      errorRate: Math.max(0.01, Number((prev.errorRate + option.deltaErrors).toFixed(1))),
      latencyP99: Math.max(35, prev.latencyP99 + option.deltaLatency),
    }));

    setLiveLogs((prev) => [...prev, option.logFollowup]);

    if (!option.isCorrect) {
      // Wrong choice penalty
    }
  };

  const handleNextPhase = async () => {
    if (!activeScenario || !selectedOption) return;

    if (!selectedOption.isCorrect) {
      // Incident failed
      setIsResolved(false);
      const report = `# Incident Post-Mortem : ${activeScenario.title}
- **Service** : ${activeScenario.service}
- **Gravité** : ${activeScenario.severity}
- **Statut** : Échec / Dégradation prolongée
- **Durée** : ${secondsElapsed} secondes
- **Erreur finale** : ${metrics.errorRate}%
- **Cause racine** : Mauvaise décision lors de la phase ${currentStepIndex + 1}.`;
      setPostMortemText(report);
      await api.completeIncident(activeScenario.id, false, report);
      onRefreshQuest();
      return;
    }

    if (currentStepIndex + 1 < activeScenario.phases.length) {
      setCurrentStepIndex((prev) => prev + 1);
      setSelectedOption(null);
    } else {
      // Completed successfully!
      setIsResolved(true);
      confetti({ particleCount: 80, spread: 60, origin: { y: 0.6 } });
      const report = `# Incident Post-Mortem : ${activeScenario.title}
- **Service** : ${activeScenario.service}
- **Gravité** : ${activeScenario.severity}
- **Statut** : Résolu avec succès ✅
- **Temps de rétablissement (MTTR)** : ${secondsElapsed} secondes
- **Taux d'erreur résiduel** : ${metrics.errorRate}%
- **Latence p99 stabilisée** : ${metrics.latencyP99}ms
- **Action corrective appliquée** : Déploiement du patch & assainissement de la configuration.`;
      setPostMortemText(report);
      await api.completeIncident(activeScenario.id, true, report);
      onRefreshQuest();
    }
  };

  const handleCopyReport = () => {
    navigator.clipboard.writeText(postMortemText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentPhase: IncidentPhase | undefined = activeScenario?.phases[currentStepIndex];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-950 border border-rose-500/30 rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl text-slate-100 animate-scale-up">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center border border-rose-500/30 animate-pulse">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-black text-rose-300">War Room — Astreinte Incident P1</h2>
                <span className="text-[10px] bg-rose-950/80 text-rose-400 border border-rose-800 px-2 py-0.5 rounded-full font-mono font-bold">
                  DIRECT
                </span>
              </div>
              <p className="text-[10px] text-slate-400">Simulateur d'urgence système sous haute tension</p>
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
          {/* Scenario Selector Pills */}
          <div className="flex gap-2 overflow-x-auto pb-1">
            {incidents.map((sc) => (
              <button
                key={sc.id}
                onClick={() => startScenario(sc)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap cursor-pointer transition-all border ${
                  activeScenario?.id === sc.id
                    ? 'bg-rose-500/20 border-rose-500/50 text-rose-200'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {sc.title}
              </button>
            ))}
          </div>

          {activeScenario && (
            <>
              {/* Telemetry Dashboard Strip */}
              <div className="grid grid-cols-4 gap-2">
                <div className="p-2.5 bg-slate-900/90 border border-slate-800 rounded-2xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Chrono</span>
                  <div className="text-sm font-black font-mono text-amber-400 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{secondsElapsed}s</span>
                  </div>
                </div>

                <div className="p-2.5 bg-slate-900/90 border border-slate-800 rounded-2xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Erreurs 5xx</span>
                  <div
                    className={`text-sm font-black font-mono flex items-center gap-1 ${
                      metrics.errorRate > 10 ? 'text-rose-400' : 'text-emerald-400'
                    }`}
                  >
                    <Activity className="w-3.5 h-3.5" />
                    <span>{metrics.errorRate}%</span>
                  </div>
                </div>

                <div className="p-2.5 bg-slate-900/90 border border-slate-800 rounded-2xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Latence p99</span>
                  <div
                    className={`text-sm font-black font-mono ${
                      metrics.latencyP99 > 1000 ? 'text-amber-400' : 'text-emerald-400'
                    }`}
                  >
                    {metrics.latencyP99}ms
                  </div>
                </div>

                <div className="p-2.5 bg-slate-900/90 border border-slate-800 rounded-2xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Débit HTTP</span>
                  <div className="text-sm font-black font-mono text-cyan-400">{metrics.rps} req/s</div>
                </div>
              </div>

              {/* Streaming Logs Terminal Box */}
              <div className="bg-black/90 border border-slate-800 rounded-2xl p-3 font-mono text-[11px] space-y-1 max-h-36 overflow-y-auto">
                <div className="text-[10px] text-slate-400 border-b border-slate-900 pb-1 flex items-center justify-between">
                  <span>journalctl -u {activeScenario.service} -f</span>
                  <span className="text-rose-400 animate-pulse">● LIVE</span>
                </div>
                {liveLogs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`${
                      log.includes('CRIT') || log.includes('PANIC') || log.includes('ERROR')
                        ? 'text-rose-400'
                        : log.includes('RESOLVED') || log.includes('SUCCESS')
                        ? 'text-emerald-400'
                        : 'text-slate-300'
                    }`}
                  >
                    {log}
                  </div>
                ))}
              </div>

              {/* Triage Decision Card */}
              {isResolved === null && currentPhase && (
                <div className="space-y-3 bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400">
                      Phase {currentPhase.step} sur {activeScenario.phases.length}
                    </span>
                    <span className="text-xs font-bold text-slate-300">{currentPhase.title}</span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">{currentPhase.description}</p>

                  <div className="space-y-2 pt-2">
                    {currentPhase.options.map((opt) => {
                      const isChosen = selectedOption?.id === opt.id;
                      return (
                        <div
                          key={opt.id}
                          onClick={() => handleChooseOption(opt)}
                          className={`p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                            isChosen
                              ? opt.isCorrect
                                ? 'bg-emerald-950/40 border-emerald-500/60 text-emerald-200'
                                : 'bg-rose-950/40 border-rose-500/60 text-rose-200'
                              : 'bg-slate-950/70 border-slate-800 hover:border-slate-700 text-slate-300'
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <span className="font-bold text-slate-400 mt-0.5">▶</span>
                            <span className="font-semibold leading-snug">{opt.label}</span>
                          </div>

                          {isChosen && (
                            <div className="mt-2 pt-2 border-t border-slate-800 text-[11px] space-y-1 animate-fade-in">
                              <p className={opt.isCorrect ? 'text-emerald-300' : 'text-rose-300'}>
                                {opt.impactExplanation}
                              </p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {selectedOption && (
                    <button
                      onClick={handleNextPhase}
                      className="w-full mt-3 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 cursor-pointer shadow-lg shadow-rose-600/20"
                    >
                      <span>Continuer l'Intervention</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )}

              {/* Resolved / Failed Final State */}
              {isResolved !== null && (
                <div className="space-y-4 animate-scale-up">
                  <div
                    className={`p-4 rounded-2xl border flex items-center gap-3 ${
                      isResolved
                        ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-200'
                        : 'bg-rose-950/40 border-rose-500/40 text-rose-200'
                    }`}
                  >
                    {isResolved ? (
                      <CheckCircle2 className="w-7 h-7 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-7 h-7 text-rose-400 flex-shrink-0" />
                    )}
                    <div>
                      <h4 className="text-sm font-bold">
                        {isResolved ? 'Incident Maîtrisé ! SLA Préservé' : 'Échec de l\'Intervention'}
                      </h4>
                      <p className="text-xs opacity-90">
                        {isResolved
                          ? 'Félicitations, vous avez diagnostiqué et endigué la panne en temps record (+180 XP, +1 Jeton).'
                          : 'La décision a entraîné une cascade d\'erreurs. Relisez le post-mortem pour consolider la méthode.'}
                      </p>
                    </div>
                  </div>

                  {/* Post-Mortem Card */}
                  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-amber-400" />
                        Rapport Post-Mortem Généré
                      </span>
                      <button
                        onClick={handleCopyReport}
                        className="flex items-center gap-1 text-[11px] text-amber-400 hover:text-amber-300 cursor-pointer font-semibold"
                      >
                        {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        <span>{copied ? 'Copié !' : 'Copier Markdown'}</span>
                      </button>
                    </div>
                    <pre className="p-3 bg-black/80 rounded-xl text-[11px] font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap">
                      {postMortemText}
                    </pre>
                  </div>

                  <button
                    onClick={() => startScenario(activeScenario)}
                    className="w-full py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-xs font-bold text-slate-300 flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Recommencer ce scénario</span>
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
