import React, { useState } from 'react';
import {
  Flame,
  Award,
  Clock,
  BookOpen,
  HelpCircle,
  Terminal,
  Sparkles,
  Coffee,
  CheckCircle2,
  Tag,
  ArrowRight,
  Brain,
  Palette,
  RefreshCw,
  TrendingUp,
  Headphones,
  Code,
  Layers,
  ChevronDown,
  AlertTriangle,
  Swords,
  Wand2,
  FileSpreadsheet,
  Volume2,
  Bot,
  GitFork,
  Trophy,
  Mic,
  FileText,
  Activity,
  Lightbulb,
} from 'lucide-react';
import { QuestData, Step, ModuleItem } from '../api';

interface QuestProps {
  quest: QuestData | null;
  modules: ModuleItem[];
  loading: boolean;
  minutes: number;
  onMinutesChange: (m: number) => void;
  onSelectLesson: (lessonId: string, initialTab?: 'body' | 'qcm' | 'tp') => void;
  onAnnounceRest: () => void;
  onSetTopic: (topic: string | null) => void;
  onSwitchModule: (moduleId: string) => void;
  onRefresh: () => void;
  onOpenLeitner: () => void;
  onOpenSkillMatrix: () => void;
  onOpenPodcast: () => void;
  onOpenSandbox: () => void;
  onOpenWarRoom: () => void;
  onOpenSkillTree: () => void;
  onOpenGhostDuel: () => void;
  onOpenAnkiExport: () => void;
  onOpenSoundtrack: () => void;
  onOpenCustomChallenge: () => void;
  onOpenClaudePrompt?: () => void;
  onOpenTechTree?: () => void;
  onOpenGuildLeagues?: () => void;
  onOpenInterviewSimulator?: () => void;
  onOpenRunbookExport?: () => void;
  onOpenPostMortem?: () => void;
  onOpenSloSimulator?: () => void;
  onOpenChaosTopology?: () => void;
  onOpenFeynmanChallenge?: () => void;
  onOpenThemeSelector?: () => void;
}

export const QuestScreen: React.FC<QuestProps> = ({
  quest,
  modules,
  loading,
  minutes,
  onMinutesChange,
  onSelectLesson,
  onAnnounceRest,
  onSetTopic,
  onSwitchModule,
  onRefresh,
  onOpenLeitner,
  onOpenSkillMatrix,
  onOpenPodcast,
  onOpenSandbox,
  onOpenWarRoom,
  onOpenSkillTree,
  onOpenGhostDuel,
  onOpenAnkiExport,
  onOpenSoundtrack,
  onOpenCustomChallenge,
  onOpenClaudePrompt,
  onOpenTechTree,
  onOpenGuildLeagues,
  onOpenInterviewSimulator,
  onOpenRunbookExport,
  onOpenPostMortem,
  onOpenSloSimulator,
  onOpenChaosTopology,
  onOpenFeynmanChallenge,
  onOpenThemeSelector,
}) => {
  const [topicInput, setTopicInput] = useState(quest?.imposed_topic || '');
  const [showTopicModal, setShowTopicModal] = useState(false);
  const [showModuleDropdown, setShowModuleDropdown] = useState(false);

  if (loading || !quest) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin mb-3 text-amber-500" />
        <p className="text-sm">Chargement de votre quête du jour...</p>
      </div>
    );
  }

  const { steps, bonus, streak, profile, imposed_topic, dueReviewsCount } = quest;
  if (modules.length === 0) return null;
  const currentModule =
    modules.find((m) => m.id === profile.active_module_id) || modules[0];

  const getRankBadgeColor = (rank: string) => {
    switch (rank) {
      case 'Expert':
        return 'from-purple-500 to-indigo-600 text-purple-100 border-purple-400/40';
      case 'Platine':
        return 'from-cyan-400 to-blue-600 text-cyan-100 border-cyan-400/40';
      case 'Or':
        return 'from-amber-400 to-yellow-600 text-amber-950 border-amber-300 font-bold';
      case 'Argent':
        return 'from-slate-300 to-slate-500 text-slate-900 border-slate-300 font-semibold';
      default:
        return 'from-amber-700 to-amber-900 text-amber-100 border-amber-600/50';
    }
  };

  const getStepIcon = (kind: Step['kind']) => {
    switch (kind) {
      case 'lesson':
        return <BookOpen className="w-5 h-5 text-blue-400" />;
      case 'qcm':
        return <HelpCircle className="w-5 h-5 text-purple-400" />;
      case 'tp':
        return <Terminal className="w-5 h-5 text-emerald-400" />;
      case 'bonus':
        return <Sparkles className="w-5 h-5 text-amber-400" />;
    }
  };

  const getStepTitle = (kind: Step['kind']) => {
    switch (kind) {
      case 'lesson':
        return 'Leçon du jour';
      case 'qcm':
        return 'Validation des acquis (QCM)';
      case 'tp':
        return 'Mise en pratique (TP Terminal)';
      case 'bonus':
        return 'Quête Bonus approfondie';
    }
  };

  const getStepInitialTab = (kind: Step['kind']): 'body' | 'qcm' | 'tp' => {
    switch (kind) {
      case 'lesson':
        return 'body';
      case 'qcm':
        return 'qcm';
      case 'tp':
      case 'bonus':
        return 'tp';
    }
  };

  const completedStepsCount = steps.filter((s) => s.done).length + (bonus?.done ? 1 : 0);
  const totalStepsCount = steps.length + (bonus ? 1 : 0);

  const xpTowardsNext1000 = profile.total_xp % 1000;
  const rankProgress = (xpTowardsNext1000 / 1000) * 100;

  return (
    <div className="space-y-5 max-w-xl mx-auto pb-10">
      {/* Sélecteur de Parcours Multi-Modules */}
      <div className="relative">
        <button
          onClick={() => setShowModuleDropdown(!showModuleDropdown)}
          className="w-full bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-3 flex items-center justify-between text-left transition-all cursor-pointer shadow-md"
        >
          <div className="flex items-center gap-2.5">
            <span className="text-xl p-1.5 bg-slate-950 rounded-xl border border-slate-800">
              {currentModule.icon}
            </span>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Parcours Actif ({currentModule.skill})
              </span>
              <h3 className="text-xs font-bold text-slate-100">{currentModule.title}</h3>
            </div>
          </div>
          <ChevronDown className="w-4 h-4 text-slate-400" />
        </button>

        {showModuleDropdown && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900 border border-slate-800 rounded-2xl p-2 shadow-2xl z-30 space-y-1 animate-fade-in">
            {modules.map((mod) => (
              <div
                key={mod.id}
                onClick={() => {
                  onSwitchModule(mod.id);
                  setShowModuleDropdown(false);
                }}
                className={`p-2.5 rounded-xl flex items-center justify-between cursor-pointer text-xs transition-all ${
                  mod.id === currentModule.id
                    ? 'bg-amber-500/20 text-amber-200 border border-amber-500/30'
                    : 'hover:bg-slate-800 text-slate-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span>{mod.icon}</span>
                  <span className="font-bold">{mod.title}</span>
                </div>
                <span className="text-[10px] font-mono text-slate-400">{mod.totalMinutes}m</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top Banner : Profil, Rang, Série et Jetons */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-5 shadow-xl relative overflow-hidden backdrop-blur-sm">
        <div className="absolute top-0 right-0 w-48 h-48 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div
              className={`px-3 py-1 rounded-xl text-xs uppercase tracking-wider font-extrabold bg-gradient-to-r border shadow-sm ${getRankBadgeColor(
                profile.rank
              )}`}
            >
              Rang {profile.rank}
            </div>
            <div className="flex items-center gap-1.5 text-xs text-amber-400 font-mono font-semibold bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/20">
              <Award className="w-3.5 h-3.5" />
              <span>{profile.total_xp} XP</span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-1.5 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 rounded-lg text-rose-400 font-semibold text-xs">
              <Flame className="w-3.5 h-3.5 text-rose-500 fill-rose-500 animate-pulse" />
              <span>{streak} j {streak > 1 ? 'consécutifs' : 'série'}</span>
            </div>
            <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg text-amber-300 font-semibold text-xs">
              <span>🪙 {profile.tokens}</span>
            </div>
          </div>
        </div>

        {/* Progression du rang */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-slate-400">
            <span>Progression palier ({xpTowardsNext1000}/1000 XP)</span>
            <span className="font-mono text-slate-300">{Math.round(rankProgress)}%</span>
          </div>
          <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
            <div
              className="bg-gradient-to-r from-amber-500 to-amber-300 h-full transition-all duration-500"
              style={{ width: `${rankProgress}%` }}
            />
          </div>
        </div>

        {imposed_topic && (
          <div className="mt-4 p-3 bg-indigo-950/60 border border-indigo-700/50 rounded-xl flex items-center justify-between gap-3 text-xs text-indigo-200">
            <div className="flex items-center gap-2">
              <Tag className="w-4 h-4 text-indigo-400 flex-shrink-0" />
              <span>
                <strong>Sujet imposé :</strong> {imposed_topic} (série préservée)
              </span>
            </div>
            <button
              onClick={() => onSetTopic(null)}
              className="text-xs text-indigo-300 hover:text-white underline cursor-pointer"
            >
              Terminer
            </button>
          </div>
        )}
      </div>

      {/* Bannière Répétition Espacée (Leitner Arena) + Bouton Export Anki */}
      <div className="bg-gradient-to-r from-purple-950/40 to-slate-900 border border-purple-800/50 rounded-2xl p-4 flex items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-purple-100">Arène de Répétition Leitner</h3>
              {dueReviewsCount > 0 && (
                <span className="text-[10px] font-mono px-2 py-0.2 rounded-full bg-purple-500 text-slate-950 font-black">
                  {dueReviewsCount} due{dueReviewsCount > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-300 mt-0.5">
              Consolidez vos acquis à long terme (+15 XP par notion retenue)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onOpenAnkiExport}
            className="p-2 rounded-xl bg-purple-900/50 hover:bg-purple-800/70 border border-purple-700/50 text-purple-200 text-xs font-semibold flex items-center gap-1 cursor-pointer transition-all"
            title="Exporter les fiches au format Anki / Markdown"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button
            onClick={onOpenLeitner}
            className="px-3 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-1.5 cursor-pointer shadow-md shadow-purple-950/40 transition-all flex-shrink-0"
          >
            <span>Réviser</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Configuration du temps de séance : 30 min vs 60 min */}
      <div className="flex items-center justify-between bg-slate-900/60 p-2 rounded-2xl border border-slate-800/80">
        <span className="text-xs font-semibold text-slate-400 px-3 flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" /> Format séance :
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => onMinutesChange(30)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              minutes === 30
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            30 min (Idéal)
          </button>
          <button
            onClick={() => onMinutesChange(60)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              minutes === 60
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            60 min (+ Bonus)
          </button>
        </div>
      </div>

      {/* Liste des étapes de la quête */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
            <span>Étapes de la quête</span>
            <span className="text-xs font-mono font-normal text-slate-400">
              ({completedStepsCount}/{totalStepsCount} terminées)
            </span>
          </h2>
          <button
            onClick={onRefresh}
            className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" /> Actualiser
          </button>
        </div>

        <div className="space-y-2.5">
          {steps.map((step, index) => (
            <div
              key={`${step.kind}-${step.lesson_id}-${index}`}
              onClick={() => onSelectLesson(step.lesson_id, getStepInitialTab(step.kind))}
              className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                step.done
                  ? 'bg-emerald-950/20 border-emerald-800/40 hover:border-emerald-700/60'
                  : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 hover:bg-slate-900'
              }`}
            >
              <div className="flex items-center gap-3.5">
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                    step.done ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-300'
                  }`}
                >
                  {step.done ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : getStepIcon(step.kind)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-100">{getStepTitle(step.kind)}</span>
                    <span className="text-[10px] font-mono uppercase bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                      {step.minutes}m
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {step.kind === 'lesson' && 'Cours écrit avec synthèse vocale intégrée'}
                    {step.kind === 'qcm' && 'Contrôle des connaissances avec remédiation guidée'}
                    {step.kind === 'tp' && 'Mise en pratique autonome dans le terminal'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <span
                  className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                    step.done
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}
                >
                  +{step.xp} XP
                </span>
                <ArrowRight className="w-4 h-4 text-slate-500" />
              </div>
            </div>
          ))}

          {/* Étape Bonus si séance de 60 min */}
          {bonus && (
            <div
              onClick={() => onSelectLesson(bonus.lesson_id, 'tp')}
              className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                bonus.done
                  ? 'bg-emerald-950/20 border-emerald-800/40 hover:border-emerald-700/60'
                  : 'bg-gradient-to-r from-amber-950/20 to-slate-900 border-amber-700/40 hover:border-amber-600/70'
              }`}
            >
              <div className="flex items-center gap-3.5">
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                    bonus.done ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                  }`}
                >
                  {bonus.done ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <Sparkles className="w-5 h-5" />}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-amber-200">Quête Bonus de 60 min</span>
                    <span className="text-[10px] font-mono uppercase bg-amber-900/60 text-amber-300 px-1.5 py-0.5 rounded border border-amber-700/50">
                      {bonus.minutes}m
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">Défi technique avancé de la leçon suivante</p>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  +{bonus.xp} XP
                </span>
                <ArrowRight className="w-4 h-4 text-amber-400" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Actions rapides : Sujet imposé & Annoncer un jour de repos */}
      <div className="pt-2 border-t border-slate-800/80 flex flex-wrap gap-2.5">
        <button
          onClick={() => setShowTopicModal(true)}
          className="flex-1 py-2.5 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-semibold text-slate-300 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
        >
          <Tag className="w-3.5 h-3.5 text-indigo-400" />
          <span>{imposed_topic ? 'Modifier sujet pro' : 'Sujet imposé'}</span>
        </button>

        <button
          onClick={onAnnounceRest}
          className="flex-1 py-2.5 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-semibold text-slate-300 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
        >
          <Coffee className="w-3.5 h-3.5 text-amber-400" />
          <span>Annoncer repos</span>
        </button>
      </div>

      {/* Hub d'Activités & Outils Avancés */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Centre d'Entraînement Avancé
          </span>
          <span className="text-[10px] text-amber-400 font-mono">15 modes annexes</span>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {/* Ligne 1 */}
          <button
            onClick={onOpenWarRoom}
            className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-rose-500/30 hover:border-rose-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
          >
            <AlertTriangle className="w-4 h-4 text-rose-400 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-bold text-rose-200">War Room P1</span>
            <span className="text-[9px] text-slate-400">Simulateur Crise</span>
          </button>

          <button
            onClick={onOpenSkillTree}
            className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-amber-500/30 hover:border-amber-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
          >
            <Sparkles className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-bold text-amber-200">Arbre Talents</span>
            <span className="text-[9px] text-slate-400">RPG & Perks</span>
          </button>

          <button
            onClick={onOpenGhostDuel}
            className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-indigo-500/30 hover:border-indigo-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
          >
            <Swords className="w-4 h-4 text-indigo-400 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-bold text-indigo-200">Duels Ghost</span>
            <span className="text-[9px] text-slate-400">Contre-la-montre</span>
          </button>

          {/* Ligne 2 */}
          <button
            onClick={onOpenCustomChallenge}
            className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-emerald-500/30 hover:border-emerald-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
          >
            <Wand2 className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-bold text-emerald-200">Défis Sur-Mesure</span>
            <span className="text-[9px] text-slate-400">Générateur TP</span>
          </button>

          <button
            onClick={onOpenSoundtrack}
            className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-teal-500/30 hover:border-teal-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
          >
            <Volume2 className="w-4 h-4 text-teal-400 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-bold text-teal-200">Lo-Fi Serveurs</span>
            <span className="text-[9px] text-slate-400">Ambiance & Feynman</span>
          </button>

          <button
            onClick={onOpenSkillMatrix}
            className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
          >
            <TrendingUp className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-bold text-slate-200">Matrice Radar</span>
            <span className="text-[9px] text-slate-400">6 Compétences</span>
          </button>

          {/* Ligne 3 : Nouvelles Extensions SRE & Communauté */}
          {onOpenTechTree && (
            <button
              onClick={onOpenTechTree}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-sky-500/30 hover:border-sky-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <GitFork className="w-4 h-4 text-sky-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-sky-200">Arbre Tech OCI</span>
              <span className="text-[9px] text-slate-400">Branches & Déblocages</span>
            </button>
          )}

          {onOpenGuildLeagues && (
            <button
              onClick={onOpenGuildLeagues}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-amber-500/30 hover:border-amber-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <Trophy className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-amber-200">Ligues & Guilde</span>
              <span className="text-[9px] text-slate-400">Divisions & Coop SRE</span>
            </button>
          )}

          {onOpenInterviewSimulator && (
            <button
              onClick={onOpenInterviewSimulator}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-purple-500/30 hover:border-purple-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <Mic className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-purple-200">Oral SRE (90s)</span>
              <span className="text-[9px] text-slate-400">Mots-clés & Méthode</span>
            </button>
          )}

          {onOpenRunbookExport && (
            <button
              onClick={onOpenRunbookExport}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-blue-500/30 hover:border-blue-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <FileText className="w-4 h-4 text-blue-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-blue-200">Runbooks SOP</span>
              <span className="text-[9px] text-slate-400">Export Markdown</span>
            </button>
          )}

          {/* Ligne 4 : Excellence SRE & Personnalisation */}
          {onOpenPostMortem && (
            <button
              onClick={onOpenPostMortem}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-amber-500/30 hover:border-amber-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <FileText className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-amber-200">Post-Mortem SRE</span>
              <span className="text-[9px] text-slate-400">5 Pourquoi & Blameless</span>
            </button>
          )}

          {onOpenSloSimulator && (
            <button
              onClick={onOpenSloSimulator}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-cyan-500/30 hover:border-cyan-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <Activity className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-cyan-200">Simulateur SLO</span>
              <span className="text-[9px] text-slate-400">Error Budget 99.9%</span>
            </button>
          )}

          {onOpenChaosTopology && (
            <button
              onClick={onOpenChaosTopology}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-rose-500/30 hover:border-rose-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <Layers className="w-4 h-4 text-rose-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-rose-200">Chaos Topologie</span>
              <span className="text-[9px] text-slate-400">Pannes & Résilience</span>
            </button>
          )}

          {onOpenFeynmanChallenge && (
            <button
              onClick={onOpenFeynmanChallenge}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-purple-500/30 hover:border-purple-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <Lightbulb className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-purple-200">Défi Feynman</span>
              <span className="text-[9px] text-slate-400">Explique à un Junior</span>
            </button>
          )}

          {onOpenThemeSelector && (
            <button
              onClick={onOpenThemeSelector}
              className="p-3 bg-slate-900/90 hover:bg-slate-800 border border-emerald-500/30 hover:border-emerald-500/60 rounded-2xl flex flex-col items-center gap-1 text-center cursor-pointer transition-all group"
            >
              <Palette className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold text-emerald-200">Thèmes Terminal</span>
              <span className="text-[9px] text-slate-400">Dracula, Nord, Matrix</span>
            </button>
          )}
        </div>
      </div>

      {/* Raccourcis Complémentaires : Podcast Trajet, Bac à sable & Prompt Claude Code */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <button
          onClick={onOpenPodcast}
          className="p-2.5 bg-slate-900/60 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center justify-center gap-2 cursor-pointer transition-all"
        >
          <Headphones className="w-4 h-4 text-orange-400" />
          <span className="text-xs font-semibold text-slate-300">Mode Podcast (45s)</span>
        </button>

        <button
          onClick={onOpenSandbox}
          className="p-2.5 bg-slate-900/60 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center justify-center gap-2 cursor-pointer transition-all"
        >
          <Code className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-slate-300">Bac à Sable</span>
        </button>

        {onOpenClaudePrompt && (
          <button
            onClick={onOpenClaudePrompt}
            className="p-2.5 bg-cyan-950/40 hover:bg-cyan-900/50 border border-cyan-500/40 rounded-xl flex items-center justify-center gap-2 cursor-pointer transition-all group"
          >
            <Bot className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-semibold text-cyan-200">Prompt Claude Code</span>
          </button>
        )}
      </div>

      {/* Modal Sujet imposé */}
      {showTopicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 max-w-sm w-full space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Tag className="w-4 h-4 text-indigo-400" /> Sujet imposé (Urgence pro)
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Un sujet imposé au travail ne casse pas votre série de quêtes. Entrez son intitulé :
            </p>
            <input
              type="text"
              placeholder="ex: Migration Helm, Debug NGINX..."
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-sans"
            />
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setShowTopicModal(false)}
                className="flex-1 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 bg-slate-800/80 rounded-xl cursor-pointer"
              >
                Annuler
              </button>
              <button
                onClick={() => {
                  onSetTopic(topicInput || null);
                  setShowTopicModal(false);
                }}
                className="flex-1 py-2 text-xs font-bold text-slate-950 bg-indigo-400 hover:bg-indigo-300 rounded-xl cursor-pointer transition-all"
              >
                Valider
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
