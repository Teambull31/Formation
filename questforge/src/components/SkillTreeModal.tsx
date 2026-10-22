import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Award,
  Layers,
  Lock,
  CheckCircle2,
  Zap,
  Shield,
  Terminal,
  Cpu,
  RefreshCw,
  Info,
  ChevronRight,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, TalentNode, Profile } from '../api';

interface SkillTreeProps {
  profile: Profile;
  onClose: () => void;
  onRefreshQuest: () => void;
}

export const SkillTreeModal: React.FC<SkillTreeProps> = ({ profile, onClose, onRefreshQuest }) => {
  const [talents, setTalents] = useState<TalentNode[]>([]);
  const [talentPoints, setTalentPoints] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedTalent, setSelectedTalent] = useState<TalentNode | null>(null);
  const [unlocking, setUnlocking] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    loadTalents();
  }, []);

  const loadTalents = async () => {
    setLoading(true);
    try {
      const res = await api.getTalents();
      setTalents(res.talents);
      setTalentPoints(res.talentPoints);
      if (res.talents.length > 0) {
        setSelectedTalent(res.talents[0]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUnlock = async (talent: TalentNode) => {
    if (talent.unlocked || talentPoints < talent.cost) return;

    // Check requirement
    if (talent.requires) {
      const reqTalent = talents.find((t) => t.id === talent.requires);
      if (reqTalent && !reqTalent.unlocked) {
        setErrorMessage(`Prérequis requis : ${reqTalent.name}`);
        return;
      }
    }

    setUnlocking(true);
    setErrorMessage(null);
    try {
      const res = await api.unlockTalent(talent.id);
      setTalents(res.talents);
      setTalentPoints(res.talentPoints);
      const updated = res.talents.find((t) => t.id === talent.id) || null;
      setSelectedTalent(updated);
      confetti({ particleCount: 70, spread: 50, origin: { y: 0.6 } });
      onRefreshQuest();
    } catch (err: any) {
      setErrorMessage(err.message || 'Impossible de débloquer ce talent');
    } finally {
      setUnlocking(false);
    }
  };

  const getBranchColor = (branch: TalentNode['branch']) => {
    switch (branch) {
      case 'automation':
        return 'from-amber-500/20 to-amber-950/40 border-amber-500/40 text-amber-300';
      case 'terminal':
        return 'from-emerald-500/20 to-emerald-950/40 border-emerald-500/40 text-emerald-300';
      case 'boss':
        return 'from-rose-500/20 to-rose-950/40 border-rose-500/40 text-rose-300';
    }
  };

  const branches = [
    { key: 'automation', title: 'Automatisation & CI/CD', icon: '⚡' },
    { key: 'terminal', title: 'Terminal & Scripts TP', icon: '💻' },
    { key: 'boss', title: 'Résilience & Boss PagerDuty', icon: '🛡️' },
  ] as const;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-950 border border-amber-500/30 rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl text-slate-100 animate-scale-up">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-600 to-amber-400 text-slate-950 flex items-center justify-center font-black shadow-md shadow-amber-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-black text-slate-100">Arbre de Talents RPG</h2>
                <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-bold">
                  {talentPoints} {talentPoints > 1 ? 'Points' : 'Point'} disponible{talentPoints > 1 ? 's' : ''}
                </span>
              </div>
              <p className="text-[10px] text-slate-400">Bonus permanents et spécialisations techniques</p>
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
        <div className="p-5 space-y-6 flex-1">
          {errorMessage && (
            <div className="p-3 bg-rose-950/50 border border-rose-500/50 rounded-xl text-xs text-rose-300">
              {errorMessage}
            </div>
          )}

          {/* 3 Skill Branches Columns */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {branches.map((b) => {
              const branchTalents = talents
                .filter((t) => t.branch === b.key)
                .sort((a, b) => a.tier - b.tier);

              return (
                <div key={b.key} className="bg-slate-900/60 border border-slate-800 rounded-2xl p-3 space-y-3">
                  <div className="flex items-center gap-1.5 pb-2 border-b border-slate-800/80">
                    <span className="text-sm">{b.icon}</span>
                    <h3 className="text-xs font-bold text-slate-200">{b.title}</h3>
                  </div>

                  <div className="space-y-2">
                    {branchTalents.map((t) => {
                      const isSelected = selectedTalent?.id === t.id;
                      const canUnlock = !t.unlocked && talentPoints >= t.cost;

                      return (
                        <div
                          key={t.id}
                          onClick={() => setSelectedTalent(t)}
                          className={`p-2.5 rounded-xl border text-xs cursor-pointer transition-all relative ${
                            t.unlocked
                              ? 'bg-amber-950/20 border-amber-500/40 text-amber-200 shadow-sm'
                              : isSelected
                              ? 'bg-slate-800 border-slate-600 text-slate-100'
                              : 'bg-slate-950/80 border-slate-800/80 hover:border-slate-700 text-slate-400'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-base">{t.icon}</span>
                              <div>
                                <span className="font-bold text-[11px] block">{t.name}</span>
                                <span className="text-[9px] text-slate-400">Palier {t.tier}</span>
                              </div>
                            </div>

                            {t.unlocked ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-amber-400" />
                            ) : (
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                                {t.cost} pt
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Selected Talent Inspector Panel */}
          {selectedTalent && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-xl">
                    {selectedTalent.icon}
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-100 flex items-center gap-2">
                      <span>{selectedTalent.name}</span>
                      {selectedTalent.unlocked && (
                        <span className="text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold">
                          ACTIF
                        </span>
                      )}
                    </h4>
                    <span className="text-[10px] text-slate-400">
                      Coût : {selectedTalent.cost} point{selectedTalent.cost > 1 ? 's' : ''} de talent
                    </span>
                  </div>
                </div>

                {!selectedTalent.unlocked && (
                  <button
                    disabled={talentPoints < selectedTalent.cost || unlocking}
                    onClick={() => handleUnlock(selectedTalent)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-md ${
                      talentPoints >= selectedTalent.cost
                        ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20'
                        : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                    }`}
                  >
                    {unlocking ? 'Déblocage...' : 'Débloquer le Talent'}
                  </button>
                )}
              </div>

              <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/70 p-3 rounded-xl border border-slate-800/80">
                {selectedTalent.description}
              </p>

              {selectedTalent.requires && (
                <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                  <Info className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                  <span>
                    Prérequis requis : <strong>{selectedTalent.requires}</strong>
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
