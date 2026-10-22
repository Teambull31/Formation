import React, { useState, useEffect } from 'react';
import {
  GitFork,
  X,
  CheckCircle2,
  Lock,
  Sparkles,
  ArrowRight,
  Cpu,
  Layers,
  Network,
  ShieldAlert,
  Server,
  Zap,
} from 'lucide-react';
import { api, TechTreeNode } from '../api';

interface TechTreeModalProps {
  onClose: () => void;
  onSelectLesson?: (lessonId: string) => void;
}

export const TechTreeModal: React.FC<TechTreeModalProps> = ({
  onClose,
  onSelectLesson,
}) => {
  const [nodes, setNodes] = useState<TechTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [activeNode, setActiveNode] = useState<TechTreeNode | null>(null);

  useEffect(() => {
    api
      .getTechTree()
      .then((data) => {
        setNodes(data.nodes);
        if (data.nodes.length > 0) setActiveNode(data.nodes[0]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const categories = [
    { id: 'all', label: 'Toutes les Branches' },
    { id: 'linux', label: '🐧 Linux Kernel' },
    { id: 'network', label: '🌐 Réseau' },
    { id: 'docker', label: '🐳 Conteneurs' },
    { id: 'k8s', label: '☸️ Kubernetes' },
    { id: 'gitops', label: '🔄 GitOps' },
    { id: 'sre', label: '🛡️ SRE & Chaos' },
  ];

  const filteredNodes =
    selectedCategory === 'all'
      ? nodes
      : nodes.filter((n) => n.category === selectedCategory);

  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case 'linux':
        return 'text-amber-400 border-amber-500/40 bg-amber-500/10';
      case 'network':
        return 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10';
      case 'docker':
        return 'text-blue-400 border-blue-500/40 bg-blue-500/10';
      case 'k8s':
        return 'text-indigo-400 border-indigo-500/40 bg-indigo-500/10';
      case 'gitops':
        return 'text-purple-400 border-purple-500/40 bg-purple-500/10';
      case 'sre':
        return 'text-rose-400 border-rose-500/40 bg-rose-500/10';
      default:
        return 'text-slate-300 border-slate-700 bg-slate-800';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <GitFork className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-100">
                  Carte des Dépendances Technologiques (Tech Tree)
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                  Roadmap SRE
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Visualisez l'arbre des prérequis et votre taux de maîtrise de chaque brique d'infrastructure.
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

        {/* Category Filters */}
        <div className="px-4 py-2 bg-slate-950/40 border-b border-slate-800/80 flex items-center gap-1.5 overflow-x-auto text-xs">
          {categories.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedCategory(c.id)}
              className={`px-3 py-1 rounded-xl font-medium text-xs whitespace-nowrap cursor-pointer transition-all ${
                selectedCategory === c.id
                  ? 'bg-indigo-600 text-white font-bold shadow-md shadow-indigo-600/20'
                  : 'bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Main Tech Tree View */}
        <div className="flex-1 overflow-y-auto p-4 grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-950/50">
          {/* Nodes Grid */}
          <div className="md:col-span-2 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {filteredNodes.map((n) => {
                const isSelected = activeNode?.id === n.id;
                const isMastered = n.status === 'mastered';
                const isLocked = n.status === 'locked';

                return (
                  <div
                    key={n.id}
                    onClick={() => setActiveNode(n)}
                    className={`p-3 rounded-2xl border transition-all cursor-pointer relative ${
                      isSelected
                        ? 'border-indigo-400 bg-slate-800/90 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-400/50'
                        : isLocked
                        ? 'border-slate-800/80 bg-slate-950/40 opacity-60 hover:opacity-80'
                        : 'border-slate-800 hover:border-slate-700 bg-slate-900/80'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase ${getCategoryColor(
                            n.category
                          )}`}
                        >
                          {n.category}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">Niv. {n.level}</span>
                      </div>
                      {isMastered ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : isLocked ? (
                        <Lock className="w-3.5 h-3.5 text-slate-500" />
                      ) : (
                        <Zap className="w-3.5 h-3.5 text-amber-400" />
                      )}
                    </div>

                    <h3 className="font-bold text-xs text-slate-200 mt-2">{n.title}</h3>

                    {/* Progress Bar */}
                    <div className="mt-2.5 space-y-1">
                      <div className="flex justify-between text-[10px] font-mono text-slate-400">
                        <span>Maîtrise</span>
                        <span className="text-indigo-300 font-bold">{n.masteryPct}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            isMastered
                              ? 'bg-emerald-400'
                              : isLocked
                              ? 'bg-slate-600'
                              : 'bg-indigo-500'
                          }`}
                          style={{ width: `${n.masteryPct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Details Sidebar */}
          {activeNode && (
            <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl flex flex-col justify-between space-y-4 shadow-xl">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase ${getCategoryColor(
                      activeNode.category
                    )}`}
                  >
                    {activeNode.category}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      activeNode.status === 'mastered'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : activeNode.status === 'locked'
                        ? 'bg-slate-800 text-slate-400'
                        : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                    }`}
                  >
                    {activeNode.status === 'mastered'
                      ? '✓ Maîtrisé'
                      : activeNode.status === 'locked'
                      ? '🔒 Verrouillé'
                      : '⚡ Débloqué'}
                  </span>
                </div>

                <h3 className="text-sm font-extrabold text-slate-100">{activeNode.title}</h3>
                <p className="text-xs text-slate-300 leading-relaxed">{activeNode.description}</p>

                {/* Prerequisites */}
                <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1.5">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Dépendances & Prérequis
                  </span>
                  {activeNode.prerequisites.length === 0 ? (
                    <span className="text-[11px] text-emerald-400 font-mono">
                      ✓ Aucun prérequis — Nœud fondamental d'entrée
                    </span>
                  ) : (
                    <div className="space-y-1">
                      {activeNode.prerequisites.map((pId) => {
                        const target = nodes.find((n) => n.id === pId);
                        return (
                          <div
                            key={pId}
                            className="text-[11px] text-slate-300 flex items-center gap-1.5 font-mono"
                          >
                            <ArrowRight className="w-3 h-3 text-indigo-400 flex-shrink-0" />
                            <span>{target ? target.title : pId}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {activeNode.lessonId && (
                <button
                  onClick={() => {
                    onClose();
                    if (onSelectLesson && activeNode.lessonId) {
                      onSelectLesson(activeNode.lessonId);
                    }
                  }}
                  className="w-full py-2.5 px-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-1.5 shadow-lg shadow-indigo-600/20 cursor-pointer transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                  <span>S'entraîner sur ce module</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
          <span>Complétez les leçons et TP pour faire progresser vos jauges de maîtrise.</span>
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
