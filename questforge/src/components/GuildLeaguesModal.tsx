import React, { useState, useEffect } from 'react';
import {
  Trophy,
  Users,
  X,
  Sparkles,
  Flame,
  Award,
  Clock,
  Shield,
  CheckCircle2,
  Gift,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { api, LeagueData, GuildMission } from '../api';
import confetti from 'canvas-confetti';

interface GuildLeaguesModalProps {
  onClose: () => void;
  onRefreshQuest?: () => void;
}

export const GuildLeaguesModal: React.FC<GuildLeaguesModalProps> = ({
  onClose,
  onRefreshQuest,
}) => {
  const [leagueData, setLeagueData] = useState<LeagueData | null>(null);
  const [activeTab, setActiveTab] = useState<'league' | 'guild'>('league');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getLeagueData()
      .then((data) => setLeagueData(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Trophy className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-100">
                  Ligue & Guilde SRE · Simulation
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  Division Or
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Affrontez les ingénieurs de votre division et progressez collectivement sur les objectifs SRE.
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

        {/* Tab Toggle */}
        <div className="px-4 py-2 bg-slate-950/40 border-b border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setActiveTab('league')}
              className={`px-3 py-1 rounded-xl font-bold cursor-pointer transition-all flex items-center gap-1.5 ${
                activeTab === 'league'
                  ? 'bg-amber-500 text-slate-950'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              <Trophy className="w-3.5 h-3.5" />
              <span>Classement de la Ligue (Semaine)</span>
            </button>
            <button
              onClick={() => setActiveTab('guild')}
              className={`px-3 py-1 rounded-xl font-bold cursor-pointer transition-all flex items-center gap-1.5 ${
                activeTab === 'guild'
                  ? 'bg-amber-500 text-slate-950'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              <Users className="w-3.5 h-3.5" />
              <span>Missions Collectives de Guilde</span>
            </button>
          </div>

          <div className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>Reset simulé dans {leagueData?.timeRemainingDays || 3} jours</span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 bg-slate-950/50">
          {activeTab === 'league' ? (
            <div className="space-y-3">
              {/* Promotion / Demotion Info Banner */}
              <div className="p-3 bg-gradient-to-r from-amber-950/30 to-slate-900 border border-amber-500/30 rounded-xl flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-amber-400" />
                  <span className="text-slate-200">
                    Les <strong>3 premiers</strong> montent en <strong>Division Diamant SRE</strong> dimanche minuit.
                  </span>
                </div>
                <span className="text-[10px] font-mono font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                  Zone de Promotion 🚀
                </span>
              </div>

              {/* Leaderboard Table */}
              <div className="space-y-1.5">
                {leagueData?.leaderboard.map((user) => {
                  const isTop3 = user.rank <= 3;
                  return (
                    <div
                      key={user.rank}
                      className={`p-3 rounded-xl border flex items-center justify-between text-xs transition-all ${
                        user.isCurrentPlayer
                          ? 'bg-amber-500/10 border-amber-500/60 shadow-md ring-1 ring-amber-500/30'
                          : isTop3
                          ? 'bg-slate-900/90 border-slate-800'
                          : 'bg-slate-950/60 border-slate-900 text-slate-400'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={`font-mono font-black text-sm w-6 text-center ${
                            user.rank === 1
                              ? 'text-amber-400'
                              : user.rank === 2
                              ? 'text-slate-200'
                              : user.rank === 3
                              ? 'text-amber-600'
                              : 'text-slate-500'
                          }`}
                        >
                          #{user.rank}
                        </span>

                        <span className="text-lg">{user.avatar}</span>

                        <div>
                          <div className="flex items-center gap-2">
                            <span
                              className={`font-bold ${
                                user.isCurrentPlayer ? 'text-amber-300' : 'text-slate-200'
                              }`}
                            >
                              {user.name}
                            </span>
                            {user.isCurrentPlayer && (
                              <span className="text-[9px] font-mono bg-amber-500 text-slate-950 font-black px-1.5 py-0.2 rounded-full">
                                VOUS
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {isTop3 ? (
                              <span className="text-emerald-400 flex items-center gap-0.5">
                                <ArrowUp className="w-2.5 h-2.5" /> Promotion
                              </span>
                            ) : (
                              <span>Maintien</span>
                            )}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 font-mono font-bold text-amber-400 text-sm">
                        <Flame className="w-4 h-4 fill-amber-500 text-amber-500" />
                        <span>+{user.xpThisWeek} XP</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Guild Missions Tab */
            <div className="space-y-3">
              <div className="p-3 bg-indigo-950/30 border border-indigo-500/30 rounded-xl text-xs text-indigo-200">
                <strong>Simulation :</strong> ces missions et les autres joueurs sont fictifs (QuestForge est une application locale à un seul joueur). Aucune récompense n'est attribuée.
              </div>

              <div className="space-y-2.5">
                {leagueData?.guildMissions.map((m) => {
                  const pct = Math.min(100, Math.round((m.current / m.target) * 100));

                  return (
                    <div
                      key={m.id}
                      className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-3 shadow-md"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-bold text-xs text-slate-100">{m.title}</h4>
                            {m.completed && (
                              <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2 py-0.2 rounded-full font-bold">
                                Objectif Atteint !
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">{m.description}</p>
                        </div>

                      </div>

                      {/* Progress Bar */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-[11px] font-mono text-slate-400">
                          <span>Progression</span>
                          <span className="text-slate-200 font-bold">
                            {m.current} / {m.target} {m.unit} ({pct}%)
                          </span>
                        </div>
                        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-700 ${
                              m.completed ? 'bg-emerald-400' : 'bg-indigo-500'
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>

                      {m.completed && (
                        <div className="pt-1 flex justify-end text-[11px] font-bold text-emerald-300 items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Objectif atteint (fictif)</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
          <span>Données fictives de démonstration : aucun autre joueur.</span>
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
