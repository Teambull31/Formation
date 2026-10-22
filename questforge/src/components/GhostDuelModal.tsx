import React, { useState, useEffect, useRef } from 'react';
import {
  Zap,
  Clock,
  Swords,
  Trophy,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Sparkles,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, GhostRunner, DuelRecord, GHOST_RUNNERS } from '../api';

interface GhostDuelProps {
  onClose: () => void;
  onRefreshQuest: () => void;
}

const DUEL_QUESTIONS = [
  {
    q: 'Quelle commande permet de capturer les paquets TCP sur eth0 sans résolution DNS inverse ni conversion de ports ?',
    options: [
      'netstat -tulpn --numeric-ports -i eth0',
      'tcpdump -nn -i eth0 tcp',
      'ss -t -a --summary -o eth0',
      'iptables -nvL --line-numbers -i eth0',
    ],
    answer: 1,
  },
  {
    q: 'Dans un Dockerfile Node.js, quel agencement garantit la réutilisation optimale du cache des calques ?',
    options: [
      'COPY . . puis RUN npm ci pour fusionner les instructions en un calque unique',
      'COPY package*.json ./ puis RUN npm ci, avant de copier les sources de l\'application',
      'RUN npm install -g pnpm puis ADD https://registry.npmjs.org/sources.tar.gz .',
      'VOLUME ["/app/node_modules"] déclaré en tête de Dockerfile avant les dépendances',
    ],
    answer: 1,
  },
  {
    q: 'Quel signal POSIX le runtime Kubernetes transmet-il en priorité pour déclencher le graceful shutdown d\'un pod ?',
    options: [
      'SIGKILL (9) - Purge immédiate de la mémoire virtuelle',
      'SIGTERM (15) - Signal de terminaison gracieuse avec délai de grâce',
      'SIGHUP (1) - Réinitialisation du contexte de configuration',
      'SIGSTOP (19) - Suspension temporaire de l\'ordonnancement',
    ],
    answer: 1,
  },
];

export const GhostDuelModal: React.FC<GhostDuelProps> = ({ onClose, onRefreshQuest }) => {
  const [ghosts, setGhosts] = useState<GhostRunner[]>(GHOST_RUNNERS);
  const [selectedGhost, setSelectedGhost] = useState<GhostRunner>(GHOST_RUNNERS[1]);
  const [history, setHistory] = useState<DuelRecord[]>([]);

  // Duel State
  const [inDuel, setInDuel] = useState(false);
  const [playerQuestionIdx, setPlayerQuestionIdx] = useState(0);
  const [playerElapsed, setPlayerElapsed] = useState(0);
  const [ghostProgress, setGhostProgress] = useState(0);
  const [finished, setFinished] = useState(false);
  const [playerWon, setPlayerWon] = useState(false);
  const [selectedAns, setSelectedAns] = useState<number | null>(null);

  const timerRef = useRef<any>(null);

  useEffect(() => {
    loadDuels();
  }, []);

  const loadDuels = async () => {
    const res = await api.getDuels();
    setGhosts(res.ghosts);
    setHistory(res.history);
  };

  const startDuel = () => {
    setInDuel(true);
    setPlayerQuestionIdx(0);
    setPlayerElapsed(0);
    setGhostProgress(0);
    setFinished(false);
    setSelectedAns(null);

    const startTime = Date.now();
    const targetGhostTime = selectedGhost.baseSeconds * 1000;

    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      setPlayerElapsed(elapsed);

      // Ghost progresses smoothly towards 100%
      const gPct = Math.min(100, Math.floor(((Date.now() - startTime) / targetGhostTime) * 100));
      setGhostProgress(gPct);

      if (gPct >= 100) {
        // Ghost reached finish line first!
        clearInterval(timerRef.current);
        handleEndDuel(false, elapsed);
      }
    }, 200);
  };

  const handleEndDuel = async (won: boolean, elapsedSec: number) => {
    clearInterval(timerRef.current);
    setFinished(true);
    setPlayerWon(won);

    if (won) {
      confetti({ particleCount: 75, spread: 60, origin: { y: 0.6 } });
    }

    await api.recordDuelResult(selectedGhost.id, elapsedSec, selectedGhost.baseSeconds, won);
    onRefreshQuest();
    loadDuels();
  };

  const handleAnswer = (idx: number) => {
    if (selectedAns !== null || finished) return;
    setSelectedAns(idx);

    const currentQ = DUEL_QUESTIONS[playerQuestionIdx];
    const isCorrect = idx === currentQ.answer;

    setTimeout(() => {
      if (isCorrect) {
        if (playerQuestionIdx + 1 < DUEL_QUESTIONS.length) {
          setPlayerQuestionIdx((prev) => prev + 1);
          setSelectedAns(null);
        } else {
          // Player completed all 3 questions first!
          handleEndDuel(true, playerElapsed);
        }
      } else {
        // Wrong answer penalty: +3s delay
        setPlayerElapsed((prev) => prev + 3);
        setSelectedAns(null);
      }
    }, 350);
  };

  const playerProgress = Math.floor((playerQuestionIdx / DUEL_QUESTIONS.length) * 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-950 border border-indigo-500/30 rounded-3xl max-w-xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl text-slate-100 animate-scale-up">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-100">Duels Asynchrones & Ghost Run</h2>
              <p className="text-[10px] text-slate-400">Contre-la-montre face aux opérateurs virtuels</p>
            </div>
          </div>

          <button
            onClick={() => {
              clearInterval(timerRef.current);
              onClose();
            }}
            className="w-7 h-7 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-5 flex-1">
          {!inDuel && !finished && (
            <>
              {/* Opponent Selection Cards */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                  Choisissez votre adversaire fantôme :
                </span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                  {ghosts.map((g) => (
                    <div
                      key={g.id}
                      onClick={() => setSelectedGhost(g)}
                      className={`p-3 rounded-2xl border text-xs cursor-pointer transition-all ${
                        selectedGhost.id === g.id
                          ? 'bg-indigo-950/40 border-indigo-500/60 text-indigo-100 shadow-md'
                          : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="text-2xl mb-1">{g.avatar}</div>
                      <div className="font-bold text-[11px]">{g.name}</div>
                      <div className="text-[10px] text-slate-400">{g.role}</div>
                      <div className="mt-2 text-[10px] font-mono font-semibold text-indigo-300">
                        Chrono : {g.baseSeconds}s
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Ghost Quote */}
              <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl text-xs text-slate-300 italic">
                {selectedGhost.quote}
              </div>

              {/* Launch Button */}
              <button
                onClick={startDuel}
                className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
              >
                <Swords className="w-4 h-4" />
                <span>Lancer le Duel contre {selectedGhost.name}</span>
              </button>

              {/* History */}
              {history.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Derniers Records de Duel :
                  </span>
                  <div className="space-y-1.5">
                    {history.slice(0, 3).map((h) => (
                      <div
                        key={h.id}
                        className="p-2.5 bg-slate-900/60 border border-slate-800 rounded-xl flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span>{h.won ? '🏆' : '💀'}</span>
                          <span className="font-bold">{h.ghostName}</span>
                        </div>
                        <span className="font-mono text-slate-400 text-[11px]">
                          Vous : {h.playerSeconds}s | Fantôme : {h.ghostSeconds}s
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Active Duel View */}
          {inDuel && !finished && (
            <div className="space-y-5 animate-fade-in">
              {/* Dual Progress Bars */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
                {/* Player Track */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-bold text-slate-200">Vous (Opérateur)</span>
                    <span className="font-mono text-indigo-400">{playerElapsed}s</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden border border-slate-800">
                    <div
                      className="bg-gradient-to-r from-indigo-500 to-cyan-400 h-full transition-all duration-300"
                      style={{ width: `${playerProgress}%` }}
                    />
                  </div>
                </div>

                {/* Ghost Track */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-bold text-slate-400 flex items-center gap-1">
                      <span>{selectedGhost.avatar}</span>
                      <span>{selectedGhost.name}</span>
                    </span>
                    <span className="font-mono text-slate-400">{Math.round((ghostProgress / 100) * selectedGhost.baseSeconds)}s</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden border border-slate-800">
                    <div
                      className="bg-gradient-to-r from-rose-500 to-amber-400 h-full transition-all duration-200"
                      style={{ width: `${ghostProgress}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Active Duel Question */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
                <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <span>Question {playerQuestionIdx + 1} / {DUEL_QUESTIONS.length}</span>
                  <span className="text-amber-400">Erreur = +3s pénalité</span>
                </div>

                <p className="text-xs font-semibold text-slate-200">
                  {DUEL_QUESTIONS[playerQuestionIdx].q}
                </p>

                <div className="space-y-2 pt-1">
                  {DUEL_QUESTIONS[playerQuestionIdx].options.map((opt, oIdx) => {
                    const isSelected = selectedAns === oIdx;
                    return (
                      <button
                        key={oIdx}
                        onClick={() => handleAnswer(oIdx)}
                        className={`w-full p-2.5 text-left rounded-xl text-xs font-mono border transition-all cursor-pointer ${
                          isSelected
                            ? oIdx === DUEL_QUESTIONS[playerQuestionIdx].answer
                              ? 'bg-emerald-950/60 border-emerald-500 text-emerald-200'
                              : 'bg-rose-950/60 border-rose-500 text-rose-200'
                            : 'bg-slate-950 border-slate-800 hover:border-slate-700 text-slate-300'
                        }`}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Finished Outcome View */}
          {finished && (
            <div className="space-y-4 animate-scale-up text-center py-4">
              <div className="text-4xl">{playerWon ? '🏆' : '⏱️'}</div>
              <h3 className="text-base font-black">
                {playerWon ? 'Victoire Éclatante !' : 'Battu au Chrono !'}
              </h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                {playerWon
                  ? `Vous avez complété l'épreuve en ${playerElapsed}s, devançant ${selectedGhost.name} (${selectedGhost.baseSeconds}s) ! +100 XP accordés.`
                  : `Le fantôme de ${selectedGhost.name} a franchi la ligne en premier. Entraînez-vous encore sur la rapidité de diagnostic.`}
              </p>

              <div className="flex gap-2 justify-center pt-2">
                <button
                  onClick={startDuel}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl flex items-center gap-1.5 cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Rejouer le Duel</span>
                </button>
                <button
                  onClick={() => {
                    setInDuel(false);
                    setFinished(false);
                  }}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 font-bold text-xs rounded-xl cursor-pointer"
                >
                  Changer d'Adversaire
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
