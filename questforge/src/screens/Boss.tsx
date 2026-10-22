import React, { useState, useEffect } from 'react';
import {
  Skull,
  Swords,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  ExternalLink,
  RefreshCw,
  Trophy,
  History,
  Clock,
  Flame,
  FileCheck2,
  AlertTriangle,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, BossData, BossAttemptResult, ALL_BOSSES, BossEntity } from '../api';

interface BossProps {
  bossData: BossData | null;
  loading: boolean;
  onRefresh: () => void;
  onSelectLesson: (lessonId: string) => void;
}

export const BossScreen: React.FC<BossProps> = ({
  bossData,
  loading,
  onRefresh,
  onSelectLesson,
}) => {
  const [bosses, setBosses] = useState<BossEntity[]>(ALL_BOSSES);
  const [selectedBossId, setSelectedBossId] = useState<string>('boss_k8s');
  const [currentBossData, setCurrentBossData] = useState<BossData | null>(bossData);
  const [internalLoading, setInternalLoading] = useState(false);
  const [attempting, setAttempting] = useState(false);
  const [lastResult, setLastResult] = useState<BossAttemptResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Crisis Mode / Astreinte Chronométrée
  const [crisisMode, setCrisisMode] = useState(false);
  const [timeLeft, setTimeLeft] = useState<number>(300); // 5 minutes
  const [timerRunning, setTimerRunning] = useState(false);

  useEffect(() => {
    let timer: any;
    if (timerRunning && timeLeft > 0) {
      timer = setInterval(() => setTimeLeft((t) => t - 1), 1000);
    } else if (timeLeft === 0 && timerRunning) {
      setTimerRunning(false);
      setErrorMessage("Temps d'astreinte écoulé ! L'incident a entraîné un impact utilisateur.");
    }
    return () => clearInterval(timer);
  }, [timerRunning, timeLeft]);

  // La liste des boss vient du backend (vrais combats) ; sans backend, la démo simulée.
  useEffect(() => {
    api
      .getBosses()
      .then((list) => {
        if (list.length === 0) return;
        setBosses(list);
        if (!list.some((b) => b.id === selectedBossId)) loadSpecificBoss(list[0].id);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSpecificBoss = async (bId: string) => {
    setInternalLoading(true);
    try {
      const res = await api.getBoss(bId);
      setCurrentBossData(res);
      setSelectedBossId(bId);
    } catch {
      // Ignored
    } finally {
      setInternalLoading(false);
    }
  };

  const handleChallenge = async () => {
    setAttempting(true);
    setErrorMessage(null);
    setLastResult(null);

    if (crisisMode) {
      setTimeLeft(300);
      setTimerRunning(true);
    }

    try {
      const res = await api.attemptBoss(selectedBossId, crisisMode);
      setLastResult(res);

      if (res.won) {
        setTimerRunning(false);
        confetti({
          particleCount: 120,
          spread: 100,
          origin: { y: 0.5 },
        });
      }
      onRefresh();
      loadSpecificBoss(selectedBossId);
    } catch (err: any) {
      setErrorMessage(err.message || 'Erreur lors du combat de Boss.');
    } finally {
      setAttempting(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const activeBoss = currentBossData?.boss || bosses[0];
  const attempts = currentBossData?.attempts_count || 0;
  const history = currentBossData?.history || [];

  return (
    <div className="space-y-6 max-w-xl mx-auto pb-12">
      {/* Bestiaire / Sélecteur des 3 Boss */}
      <div className="space-y-2">
        <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
          <Skull className="w-4 h-4 text-rose-500" /> Bestiaire des Pannes Majeures (Sélectionner le Boss) :
        </span>
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(3, bosses.length)}, minmax(0, 1fr))` }}>
          {bosses.map((b) => (
            <button
              key={b.id}
              onClick={() => loadSpecificBoss(b.id)}
              className={`p-3 rounded-2xl border text-center transition-all cursor-pointer flex flex-col items-center gap-1 ${
                selectedBossId === b.id
                  ? 'bg-rose-950/60 border-rose-500 text-rose-100 shadow-lg shadow-rose-950/30'
                  : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:border-slate-700'
              }`}
            >
              <span className="text-2xl">{b.avatar}</span>
              <span className="text-[11px] font-bold line-clamp-1 leading-snug">{b.title.split(' ')[1] || b.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Carte du Boss actif */}
      <div
        className={`bg-gradient-to-b from-rose-950/40 via-slate-900 to-slate-900 border rounded-3xl p-6 shadow-2xl relative overflow-hidden space-y-4 ${
          crisisMode && timerRunning ? 'animate-crisis' : 'border-rose-800/40'
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
            <Skull className="w-3.5 h-3.5" /> Épreuve d'Incident
          </span>
          <span className="text-xs font-mono text-slate-400 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
            {attempts} tentative{attempts > 1 ? 's' : ''} (illimitées)
          </span>
        </div>

        <div>
          <div className="flex items-center gap-3">
            <span className="text-3xl">{activeBoss.avatar}</span>
            <div>
              <h1 className="text-xl font-black text-rose-100">{activeBoss.title}</h1>
              <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">{activeBoss.description}</p>
            </div>
          </div>
        </div>

        {/* Mode Astreinte Chronométrée */}
        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-2xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className={`w-4 h-4 ${crisisMode ? 'text-rose-400 animate-pulse' : 'text-slate-400'}`} />
            <div>
              <span className="text-xs font-bold text-slate-200 block">Mode Astreinte sous tension</span>
              <span className="text-[10px] text-slate-400 block">Chronomètre 5 min · première victoire : +150 XP & 1 jeton</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {timerRunning && (
              <span className="font-mono text-sm font-black text-rose-400 px-2 py-0.5 rounded bg-rose-950/60 border border-rose-800">
                {formatTime(timeLeft)}
              </span>
            )}
            <input
              type="checkbox"
              checked={crisisMode}
              onChange={(e) => setCrisisMode(e.target.checked)}
              className="w-4 h-4 accent-rose-500 rounded cursor-pointer"
            />
          </div>
        </div>

        {/* Phases du Boss */}
        <div className="space-y-2 pt-1">
          <span className="text-xs font-bold text-slate-300">Phases de résolution :</span>
          <div className="space-y-2">
            {activeBoss.phases.map((phase, idx) => (
              <div
                key={phase.pattern_id}
                className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl flex items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded-lg bg-rose-500/10 text-rose-400 font-mono font-bold flex items-center justify-center text-[11px] border border-rose-500/20">
                    {idx + 1}
                  </span>
                  <div>
                    <h4 className="font-bold text-slate-100">{phase.label}</h4>
                    <span className="text-[10px] font-mono text-slate-400">Vérification : {phase.check}</span>
                  </div>
                </div>

                {phase.remedial_lesson_id && (
                  <button
                    onClick={() => onSelectLesson(phase.remedial_lesson_id!)}
                    className="text-[10px] text-amber-400 hover:text-amber-300 underline flex items-center gap-1 cursor-pointer flex-shrink-0"
                  >
                    Fiche associée <ExternalLink className="w-3 h-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Bouton de défi */}
        <button
          onClick={handleChallenge}
          disabled={attempting}
          className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-rose-600 via-red-600 to-rose-600 hover:from-rose-500 hover:to-rose-500 text-white font-black text-sm flex items-center justify-center gap-2 shadow-xl shadow-rose-950/40 cursor-pointer transition-all"
        >
          {attempting ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <Swords className="w-4 h-4" /> Défier {activeBoss.title}
            </>
          )}
        </button>

        {errorMessage && (
          <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl text-xs text-amber-300 text-center">
            {errorMessage}
          </div>
        )}

        {/* Résultat du combat et Rapport Post-Mortem */}
        {lastResult && (
          <div
            className={`p-4 rounded-xl border text-xs leading-relaxed space-y-3 animate-fade-in ${
              lastResult.won
                ? 'bg-emerald-950/50 border-emerald-600 text-emerald-200'
                : 'bg-rose-950/50 border-rose-600 text-rose-200'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-sm">
              {lastResult.won ? (
                <>
                  <Trophy className="w-5 h-5 text-amber-400" /> VICTOIRE ! Panne résolue avec succès ! (+1 Jeton Gacha)
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-rose-400" /> Défaillance lors de l'incident
                </>
              )}
            </div>

            {/* Rapport Post-Mortem */}
            {lastResult.post_mortem && (
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800/80 space-y-1.5 text-[11px]">
                <div className="flex items-center gap-1.5 font-bold text-slate-300">
                  <FileCheck2 className="w-3.5 h-3.5 text-indigo-400" /> Rapport Post-Mortem :
                </div>
                <p className="text-slate-300 leading-relaxed font-mono">{lastResult.post_mortem}</p>
              </div>
            )}

            {!lastResult.won && lastResult.remedial_lesson_id && (
              <div className="pt-2 border-t border-rose-800/40 flex items-center justify-between">
                <span className="text-[11px] text-slate-300">Remédiation recommandée :</span>
                <button
                  onClick={() => onSelectLesson(lastResult.remedial_lesson_id!)}
                  className="text-xs font-bold text-amber-300 hover:text-amber-200 underline flex items-center gap-1 cursor-pointer"
                >
                  Étudier la leçon {lastResult.remedial_lesson_id} <ExternalLink className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Historique des combats */}
      {history.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h2 className="text-xs font-bold text-slate-300 flex items-center gap-2">
            <History className="w-4 h-4 text-slate-400" /> Historique des astreintes et combats
          </h2>
          <div className="space-y-2">
            {history.map((item, idx) => (
              <div
                key={idx}
                className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2">
                  {item.won ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400" />
                  )}
                  <span className="font-semibold text-slate-200">
                    {item.won ? 'Incident Résolu' : `Interrompu Phase ${item.phase_reached}`}
                  </span>
                  {item.crisis_mode && (
                    <span className="text-[9px] font-mono text-rose-400 bg-rose-950/60 px-1.5 py-0.2 rounded border border-rose-800">
                      Astreinte 5m
                    </span>
                  )}
                </div>
                {item.failed_pattern && (
                  <span className="text-[10px] font-mono text-slate-400">{item.failed_pattern}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
