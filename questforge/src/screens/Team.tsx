import React, { useState } from 'react';
import {
  Users,
  Sparkles,
  Award,
  Layers,
  Palette,
  ShieldAlert,
  Check,
  RefreshCw,
  Gift,
  Trophy,
  CheckCircle2,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, TeamData, InventoryItem, Achievement } from '../api';

interface TeamProps {
  teamData: TeamData | null;
  loading: boolean;
  onRefresh: () => void;
  onThemeChanged?: (themeId: string) => void;
}

export const TeamScreen: React.FC<TeamProps> = ({
  teamData,
  loading,
  onRefresh,
  onThemeChanged,
}) => {
  const [pulling, setPulling] = useState(false);
  const [pulledItem, setPulledItem] = useState<InventoryItem | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isEquipping, setIsEquipping] = useState<string | null>(null);

  if (loading || !teamData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin mb-3 text-amber-500" />
        <p className="text-sm">Chargement de votre équipe...</p>
      </div>
    );
  }

  const { profile, inventory } = teamData;
  const currentTheme = profile.active_theme || 'default';

  const handlePull = async () => {
    setPulling(true);
    setErrorMessage(null);
    setPulledItem(null);

    // Dramatic suspension delay
    await new Promise((r) => setTimeout(r, 600));

    try {
      const res = await api.pullGacha();
      setPulledItem(res.item);

      const particleColor =
        res.item.rarity === 'epic'
          ? ['#a855f7', '#ec4899', '#fbbf24']
          : res.item.rarity === 'rare'
          ? ['#06b6d4', '#3b82f6']
          : ['#10b981', '#34d399'];

      confetti({
        particleCount: res.item.rarity === 'epic' ? 120 : 70,
        spread: 90,
        colors: particleColor,
        origin: { y: 0.6 },
      });
      onRefresh();
    } catch (err: any) {
      if (err.status === 409) {
        setErrorMessage('Plus de jetons disponibles ! Complétez des quêtes pour en gagner.');
      } else {
        setErrorMessage(err.message || "Erreur lors de l'invocation.");
      }
    } finally {
      setPulling(false);
    }
  };

  const handleEquipTheme = async (skinId: string) => {
    let themeCode = 'default';
    if (skinId.includes('cyber')) themeCode = 'cyberpunk';
    else if (skinId.includes('matrix')) themeCode = 'matrix';
    else if (skinId.includes('solarized') || skinId.includes('amber')) themeCode = 'amber';
    else if (skinId.includes('nordic') || skinId.includes('frost')) themeCode = 'arctic';

    setIsEquipping(skinId);
    try {
      await api.setTheme(themeCode);
      if (onThemeChanged) onThemeChanged(themeCode);
      onRefresh();
    } catch {
      // Ignored
    } finally {
      setIsEquipping(null);
    }
  };

  const getRarityBadge = (rarity: string) => {
    switch (rarity) {
      case 'epic':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/40 font-bold';
      case 'rare':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 font-semibold';
      default:
        return 'bg-slate-700/50 text-slate-300 border-slate-600/40';
    }
  };

  const getRarityBorder = (rarity: string) => {
    switch (rarity) {
      case 'epic':
        return 'border-purple-500/50 shadow-purple-500/10 shadow-lg';
      case 'rare':
        return 'border-cyan-500/50 shadow-cyan-500/10 shadow-lg';
      default:
        return 'border-slate-800';
    }
  };

  return (
    <div className="space-y-6 max-w-xl mx-auto pb-12">
      {/* Header : Rang et Jetons */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl flex items-center justify-between">
        <div>
          <span className="text-xs uppercase font-extrabold text-amber-400 tracking-wider">
            Compétences & Invocations
          </span>
          <h1 className="text-lg font-bold text-slate-100 mt-0.5">Votre Équipe & Thèmes</h1>
        </div>
        <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 px-3.5 py-1.5 rounded-xl text-amber-300 font-bold text-sm">
          <span>🪙 {profile.tokens} jeton{profile.tokens > 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Compétences & Niveaux */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" /> Progression par compétence
        </h2>

        {Object.keys(profile.skills).length === 0 ? (
          <p className="text-xs text-slate-400 italic">
            Aucun point d'XP encore attribué. Complétez votre première quête !
          </p>
        ) : (
          <div className="space-y-3">
            {Object.entries(profile.skills).map(([skill, xp]) => {
              const level = Math.floor(Math.sqrt(xp / 50)) + 1;
              const nextLvlXp = level ** 2 * 50;
              const curLvlBaseXp = (level - 1) ** 2 * 50;
              const progressInLevel = Math.min(
                100,
                Math.max(0, ((xp - curLvlBaseXp) / (nextLvlXp - curLvlBaseXp || 1)) * 100)
              );

              return (
                <div key={skill} className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-slate-200 capitalize">{skill}</span>
                    <span className="text-[11px] font-mono text-indigo-300 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/40">
                      Niveau {level} ({xp} XP)
                    </span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                    <div
                      className="bg-indigo-500 h-full transition-all duration-500 rounded-full"
                      style={{ width: `${progressInLevel}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Portail d'invocation Gacha avec Orbe Animée */}
      <div className="bg-gradient-to-b from-purple-950/40 via-slate-900 to-slate-900 border border-purple-800/50 rounded-3xl p-6 shadow-2xl relative overflow-hidden text-center space-y-4">
        <div className={`w-16 h-16 rounded-full bg-gradient-to-tr from-purple-600 via-pink-500 to-amber-400 flex items-center justify-center mx-auto shadow-2xl ${pulling ? 'animate-orb' : ''}`}>
          <Sparkles className="w-8 h-8 text-white" />
        </div>

        <div>
          <h2 className="text-base font-black text-purple-100">Portail Cosmique des Héros & Thèmes</h2>
          <p className="text-xs text-slate-300 max-w-sm mx-auto mt-1 leading-relaxed">
            Invoquez des mascottes pionnières et personnalisez le thème de votre console (100% cosmétique).
          </p>
        </div>

        <button
          onClick={handlePull}
          disabled={pulling || profile.tokens < 1}
          className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-600 hover:opacity-95 disabled:opacity-40 text-white font-black text-sm flex items-center justify-center gap-2 shadow-xl shadow-purple-950/50 cursor-pointer transition-all"
        >
          {pulling ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <Gift className="w-4 h-4" /> Invoquer (1 Jeton)
            </>
          )}
        </button>

        {errorMessage && (
          <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-xl text-xs text-rose-300 flex items-center gap-2 justify-center">
            <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Carte de l'objet tiré */}
        {pulledItem && (
          <div
            className={`p-4 rounded-2xl border bg-slate-950/90 text-left space-y-2 mt-3 animate-fade-in ${getRarityBorder(
              pulledItem.rarity
            )}`}
          >
            <div className="flex items-center justify-between">
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase ${getRarityBadge(
                  pulledItem.rarity
                )}`}
              >
                {pulledItem.rarity}
              </span>
              <span className="text-xs text-slate-400 capitalize">{pulledItem.type}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-3xl p-2 bg-slate-900 rounded-xl border border-slate-800">
                {pulledItem.avatar || (pulledItem.type === 'character' ? '👤' : '🎨')}
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-100">{pulledItem.name}</h4>
                <p className="text-xs text-slate-400 mt-0.5">{pulledItem.lore || 'Nouvel élément débloqué !'}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Section Succès & Trophées débloqués */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold text-slate-200 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Trophy className="w-4 h-4 text-amber-400" /> Succès & Trophées
          </span>
          <span className="text-xs font-mono text-slate-400">
            {profile.achievements.filter((a) => a.unlocked).length} / {profile.achievements.length}
          </span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {profile.achievements.map((ach) => (
            <div
              key={ach.id}
              className={`p-3 rounded-xl border flex items-center gap-3 text-xs transition-all ${
                ach.unlocked
                  ? 'bg-amber-950/20 border-amber-600/40 text-amber-100'
                  : 'bg-slate-950/40 border-slate-800/80 text-slate-500 opacity-60'
              }`}
            >
              <div className="text-xl">{ach.icon}</div>
              <div className="min-w-0 flex-1">
                <div className="font-bold flex items-center gap-1.5">
                  <span>{ach.name}</span>
                  {ach.unlocked && <CheckCircle2 className="w-3.5 h-3.5 text-amber-400" />}
                </div>
                <div className="text-[10px] text-slate-400 leading-tight mt-0.5">{ach.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Inventaire des récompenses & Thèmes équipables */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold text-slate-200 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Palette className="w-4 h-4 text-amber-400" /> Inventaire cosmétique & Thèmes
          </span>
          <span className="text-xs font-mono font-normal text-slate-400">
            {inventory.length} objets
          </span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {inventory.map((item, idx) => {
            const isSkin = item.type === 'skin';
            let skinTheme = 'default';
            if (item.item_id.includes('cyber')) skinTheme = 'cyberpunk';
            else if (item.item_id.includes('matrix')) skinTheme = 'matrix';
            else if (item.item_id.includes('amber') || item.item_id.includes('solarized')) skinTheme = 'amber';
            else if (item.item_id.includes('nordic') || item.item_id.includes('frost')) skinTheme = 'arctic';

            const isCurrentTheme = isSkin && currentTheme === skinTheme;

            return (
              <div
                key={`${item.item_id}-${idx}`}
                className={`p-3.5 rounded-2xl border bg-slate-900/80 flex flex-col justify-between gap-3 ${getRarityBorder(
                  item.rarity
                )}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-2xl p-2 bg-slate-950 rounded-xl border border-slate-800 flex-shrink-0">
                      {item.avatar || (item.type === 'character' ? '👤' : '🎨')}
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-xs font-bold text-slate-100 truncate">{item.name}</h4>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.2 rounded border uppercase mt-1 inline-block ${getRarityBadge(
                          item.rarity
                        )}`}
                      >
                        {item.rarity}
                      </span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700">
                    x{item.count}
                  </span>
                </div>

                {isSkin && (
                  <button
                    onClick={() => handleEquipTheme(item.item_id)}
                    className={`w-full py-1.5 rounded-xl text-[11px] font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                      isCurrentTheme
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
                    }`}
                  >
                    {isCurrentTheme ? (
                      <>
                        <Check className="w-3.5 h-3.5" /> Thème Équipé
                      </>
                    ) : (
                      'Équiper ce thème'
                    )}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
