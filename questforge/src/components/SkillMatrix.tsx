import React from 'react';
import {
  Radar,
  Award,
  TrendingUp,
  Brain,
  Calendar,
  Layers,
  ChevronRight,
  Flame,
  Coffee,
  Tag,
  CheckCircle2,
} from 'lucide-react';
import { Profile, ActivityDayLog } from '../api';

interface SkillMatrixProps {
  profile: Profile;
  activityHistory: ActivityDayLog[];
  onClose: () => void;
}

export const SkillMatrix: React.FC<SkillMatrixProps> = ({
  profile,
  activityHistory,
  onClose,
}) => {
  const skillsList = [
    { key: 'automation', label: 'Automatisation', max: 200 },
    { key: 'docker', label: 'Docker', max: 200 },
    { key: 'kubernetes', label: 'Kubernetes', max: 200 },
    { key: 'observability', label: 'Observabilité', max: 200 },
    { key: 'linux', label: 'Linux & Bash', max: 200 },
    { key: 'security', label: 'Sécurité DevSecOps', max: 200 },
  ];

  // Calculate radar polygon points
  const centerX = 120;
  const centerY = 120;
  const radius = 85;

  const points = skillsList.map((skill, index) => {
    const angle = (Math.PI * 2 / skillsList.length) * index - Math.PI / 2;
    const value = Math.min(skill.max, profile.skills[skill.key] || 20);
    const r = (value / skill.max) * radius;
    const x = centerX + r * Math.cos(angle);
    const y = centerY + r * Math.sin(angle);
    return `${x},${y}`;
  });

  const polygonPoints = points.join(' ');

  // Background radar grid webs
  const gridLevels = [0.25, 0.5, 0.75, 1];

  const xpTowardsNext = profile.total_xp % 1000;
  const xpNeeded = 1000 - xpTowardsNext;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-xl w-full space-y-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
              <TrendingUp className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">Matrice de Compétences & Analyse</h2>
              <p className="text-[10px] text-slate-400">Suivi holistique de vos compétences et rétention</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* 1. Radar Chart SVG & Statut du Rang */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center bg-slate-950/70 p-4 rounded-2xl border border-slate-800">
          <div className="flex justify-center">
            <svg width="240" height="240" className="overflow-visible">
              {/* Radar webs */}
              {gridLevels.map((lvl, lIdx) => (
                <polygon
                  key={lIdx}
                  points={skillsList
                    .map((_, i) => {
                      const angle = (Math.PI * 2 / skillsList.length) * i - Math.PI / 2;
                      const x = centerX + radius * lvl * Math.cos(angle);
                      const y = centerY + radius * lvl * Math.sin(angle);
                      return `${x},${y}`;
                    })
                    .join(' ')}
                  fill="none"
                  stroke="#334155"
                  strokeWidth="1"
                  strokeDasharray={lIdx < 3 ? '2,2' : undefined}
                />
              ))}

              {/* Axis lines */}
              {skillsList.map((_, i) => {
                const angle = (Math.PI * 2 / skillsList.length) * i - Math.PI / 2;
                const x = centerX + radius * Math.cos(angle);
                const y = centerY + radius * Math.sin(angle);
                return (
                  <line
                    key={i}
                    x1={centerX}
                    y1={centerY}
                    x2={x}
                    y2={y}
                    stroke="#1e293b"
                    strokeWidth="1"
                  />
                );
              })}

              {/* Data polygon */}
              <polygon
                points={polygonPoints}
                fill="rgba(245, 158, 11, 0.25)"
                stroke="#f59e0b"
                strokeWidth="2"
              />

              {/* Vertex dots & Labels */}
              {skillsList.map((s, i) => {
                const angle = (Math.PI * 2 / skillsList.length) * i - Math.PI / 2;
                const val = Math.min(s.max, profile.skills[s.key] || 20);
                const r = (val / s.max) * radius;
                const x = centerX + r * Math.cos(angle);
                const y = centerY + r * Math.sin(angle);

                const labelR = radius + 18;
                const lx = centerX + labelR * Math.cos(angle);
                const ly = centerY + labelR * Math.sin(angle);

                return (
                  <g key={i}>
                    <circle cx={x} cy={y} r="3.5" fill="#f59e0b" />
                    <text
                      x={lx}
                      y={ly}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize="9"
                      fill="#94a3b8"
                      fontFamily="monospace"
                    >
                      {s.label.split(' ')[0]}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div className="space-y-3">
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800 space-y-1">
              <span className="text-[10px] text-slate-400 font-mono">Rang Actuel :</span>
              <div className="text-base font-extrabold text-amber-300">
                {profile.rank} ({profile.total_xp} XP)
              </div>
              <p className="text-[11px] text-slate-400">
                Plus que <strong className="text-amber-400">{xpNeeded} XP</strong> pour franchir le prochain palier.
              </p>
            </div>

            <div className="space-y-1.5">
              {skillsList.slice(0, 3).map((s) => (
                <div key={s.key} className="flex justify-between text-xs">
                  <span className="text-slate-300 font-medium">{s.label} :</span>
                  <span className="font-mono text-amber-400 font-bold">{profile.skills[s.key] || 0} XP</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 2. Rétention Ebbinghaus & Leitner */}
        <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              <Brain className="w-4 h-4 text-purple-400" /> Taux de Rétention Mnésique
            </span>
            <span className="text-emerald-400 font-mono font-bold text-xs">88% Stable</span>
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            Modèle d'Ebbinghaus : grâce à vos révisions quotidiennes espacées, les notions en Boîtes 4 et 5 sont gravées dans la mémoire à long terme sans déperdition.
          </p>

          <div className="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden flex border border-slate-800">
            <div className="bg-emerald-500 h-full w-[65%]" title="Boîtes 4-5 : Ancré" />
            <div className="bg-amber-500 h-full w-[23%]" title="Boîtes 2-3 : En consolidation" />
            <div className="bg-rose-500 h-full w-[12%]" title="Boîte 1 : Vulnérable" />
          </div>
          <div className="flex justify-between text-[9px] font-mono text-slate-400">
            <span className="text-emerald-400">● 65% Ancré (B4-B5)</span>
            <span className="text-amber-400">● 23% Consolidation</span>
            <span className="text-rose-400">● 12% Vulnérable (B1)</span>
          </div>
        </div>

        {/* 3. Heatmap d'Activité (Dernières 4 semaines) */}
        <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-emerald-400" /> Historique d'Assiduité (28 jours)
            </span>
            <span className="text-[10px] text-slate-400 font-mono">Consécutifs : {profile.total_xp > 0 ? 3 : 0}j</span>
          </div>

          <div className="grid grid-cols-7 gap-1.5 pt-1">
            {activityHistory.map((day, idx) => (
              <div
                key={idx}
                title={`${day.date} - ${day.status}`}
                className={`h-7 rounded-lg border flex items-center justify-center text-[10px] font-mono transition-transform hover:scale-110 cursor-pointer ${
                  day.status === 'active'
                    ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                    : day.status === 'rest'
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                    : day.status === 'topic'
                    ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-300'
                    : 'bg-slate-900 border-slate-800 text-slate-600'
                }`}
              >
                {day.status === 'active' ? '🔥' : day.status === 'rest' ? '☕' : day.status === 'topic' ? '🏷️' : ''}
              </div>
            ))}
          </div>

          <div className="flex items-center gap-4 text-[10px] text-slate-400 pt-1">
            <span className="flex items-center gap-1">🔥 Quête accomplie</span>
            <span className="flex items-center gap-1">☕ Repos annoncé</span>
            <span className="flex items-center gap-1">🏷️ Sujet pro imposé</span>
          </div>
        </div>
      </div>
    </div>
  );
};
