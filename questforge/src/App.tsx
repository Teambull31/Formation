import React, { useEffect, useState } from 'react';
import {
  Compass,
  Users,
  Swords,
  Calendar,
  Sparkles,
  Flame,
  Award,
  BookOpen,
  Brain,
  Headphones,
  Maximize2,
  Minimize2,
  Target,
  Bot,
} from 'lucide-react';
import { api, isOfflineDemo, resetOfflineDemo, MODULES_CATALOG, ModuleItem, QuestData, TeamData, BossData, LessonData } from './api';
import { QuestScreen } from './screens/Quest';
import { LessonScreen } from './screens/Lesson';
import { TeamScreen } from './screens/Team';
import { BossScreen } from './screens/Boss';
import { WeeklyScreen } from './screens/Weekly';
import { LeitnerArena } from './components/LeitnerArena';
import { SkillMatrix } from './components/SkillMatrix';
import { PodcastPlayer } from './components/PodcastPlayer';
import { SandboxPlayground } from './components/SandboxPlayground';
import { CompanionBar } from './components/CompanionBar';
import { WarRoomModal } from './components/WarRoomModal';
import { SkillTreeModal } from './components/SkillTreeModal';
import { GhostDuelModal } from './components/GhostDuelModal';
import { AnkiExportModal } from './components/AnkiExportModal';
import { SoundtrackPlayer } from './components/SoundtrackPlayer';
import { CustomChallengeModal } from './components/CustomChallengeModal';
import { ClaudeCodePromptModal } from './components/ClaudeCodePromptModal';
import { GuildLeaguesModal } from './components/GuildLeaguesModal';
import { InterviewSimulatorModal } from './components/InterviewSimulatorModal';
import { RunbookExportModal } from './components/RunbookExportModal';
import { TechTreeModal } from './components/TechTreeModal';
import { PostMortemModal } from './components/PostMortemModal';
import { SloSimulatorModal } from './components/SloSimulatorModal';
import { ChaosTopologyModal } from './components/ChaosTopologyModal';
import { FeynmanChallengeModal } from './components/FeynmanChallengeModal';
import { ThemeSelectorModal } from './components/ThemeSelectorModal';

type Tab = 'quest' | 'lesson' | 'team' | 'boss' | 'weekly';

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>('quest');
  const [minutes, setMinutes] = useState<number>(30);

  // Focus Mode state (intense work session without distractions)
  const [focusMode, setFocusMode] = useState(false);

  // Quest state
  const [quest, setQuest] = useState<QuestData | null>(null);
  const [questLoading, setQuestLoading] = useState(true);

  // Active lesson state
  const [activeLessonId, setActiveLessonId] = useState<string | null>(null);
  const [initialLessonTab, setInitialLessonTab] = useState<'body' | 'qcm' | 'tp'>('body');

  // Team state
  const [teamData, setTeamData] = useState<TeamData | null>(null);
  const [teamLoading, setTeamLoading] = useState(false);

  // Boss state
  const [bossData, setBossData] = useState<BossData | null>(null);
  const [bossLoading, setBossLoading] = useState(false);

  // Modals state
  const [showLeitner, setShowLeitner] = useState(false);
  const [showSkillMatrix, setShowSkillMatrix] = useState(false);
  const [showPodcast, setShowPodcast] = useState(false);
  const [podcastLesson, setPodcastLesson] = useState<LessonData | null>(null);
  const [showSandbox, setShowSandbox] = useState(false);
  const [showWarRoom, setShowWarRoom] = useState(false);
  const [showSkillTree, setShowSkillTree] = useState(false);
  const [showGhostDuel, setShowGhostDuel] = useState(false);
  const [showAnkiExport, setShowAnkiExport] = useState(false);
  const [showSoundtrack, setShowSoundtrack] = useState(false);
  const [showCustomChallenge, setShowCustomChallenge] = useState(false);
  const [showClaudePrompt, setShowClaudePrompt] = useState(false);
  const [showGuildLeagues, setShowGuildLeagues] = useState(false);
  const [showInterviewSimulator, setShowInterviewSimulator] = useState(false);
  const [showTechTree, setShowTechTree] = useState(false);
  const [showRunbookExport, setShowRunbookExport] = useState(false);
  const [runbookLessonId, setRunbookLessonId] = useState<string>('l1');
  const [runbookLessonTitle, setRunbookLessonTitle] = useState<string>('Procédure Opérationnelle Standard (SOP)');
  const [showPostMortem, setShowPostMortem] = useState(false);
  const [showSloSimulator, setShowSloSimulator] = useState(false);
  const [showChaosTopology, setShowChaosTopology] = useState(false);
  const [showFeynmanChallenge, setShowFeynmanChallenge] = useState(false);
  const [showThemeSelector, setShowThemeSelector] = useState(false);

  // Active theme
  const [activeTheme, setActiveTheme] = useState('default');

  // Feedback notification toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [offlineDemo, setOfflineDemo] = useState(false);
  const [modules, setModules] = useState<ModuleItem[]>(MODULES_CATALOG);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const loadQuest = async (m: number = minutes) => {
    setQuestLoading(true);
    try {
      const data = await api.getQuest(m);
      setOfflineDemo(isOfflineDemo());
      setQuest(data);
      api.getModules().then(setModules).catch(() => {});
      if (data.profile.active_theme) {
        setActiveTheme(data.profile.active_theme);
      }
    } catch (err: any) {
      console.error('Erreur chargement quête:', err);
    } finally {
      setQuestLoading(false);
    }
  };

  const loadTeam = async () => {
    setTeamLoading(true);
    try {
      const data = await api.getTeam();
      setTeamData(data);
      if (data.profile.active_theme) {
        setActiveTheme(data.profile.active_theme);
      }
    } catch (err: any) {
      console.error('Erreur chargement équipe:', err);
    } finally {
      setTeamLoading(false);
    }
  };

  const loadBoss = async () => {
    setBossLoading(true);
    try {
      const data = await api.getBoss();
      setBossData(data);
    } catch (err: any) {
      console.error('Erreur chargement boss:', err);
    } finally {
      setBossLoading(false);
    }
  };

  useEffect(() => {
    loadQuest(minutes);
    loadTeam();
  }, [minutes]);

  useEffect(() => {
    if (activeTab === 'team') {
      loadTeam();
    } else if (activeTab === 'boss') {
      loadBoss();
    }
  }, [activeTab]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && focusMode) {
        setFocusMode(false);
        showToast('Mode Focus désactivé');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [focusMode]);

  const handleSelectLesson = (lessonId: string, initialTab: 'body' | 'qcm' | 'tp' = 'body') => {
    setActiveLessonId(lessonId);
    setInitialLessonTab(initialTab);
    setActiveTab('lesson');
  };

  const handleAnnounceRest = async () => {
    try {
      await api.announceRest();
      showToast('Jour de repos annoncé pris en compte ! Votre série est préservée.');
      loadQuest();
    } catch (err: any) {
      showToast(err.message || 'Erreur lors de l’annonce du repos');
    }
  };

  const handleSetTopic = async (topic: string | null) => {
    try {
      await api.setTopic(topic);
      showToast(topic ? `Sujet imposé activé: ${topic}` : 'Sujet imposé retiré');
      loadQuest();
    } catch (err: any) {
      showToast(err.message || 'Erreur lors de la mise à jour du sujet');
    }
  };

  const handleSwitchModule = async (moduleId: string) => {
    try {
      await api.switchModule(moduleId);
      showToast(`Parcours sélectionné : ${moduleId}`);
      await loadQuest();
    } catch (err: any) {
      showToast(err.message || 'Erreur lors du changement de parcours');
    }
  };

  const handleOpenPodcast = async () => {
    const targetId = activeLessonId || quest?.steps[0]?.lesson_id || 'l1';
    try {
      const l = await api.getLesson(targetId);
      setPodcastLesson(l);
      setShowPodcast(true);
    } catch (err: any) {
      showToast('Impossible de charger la leçon en mode podcast');
    }
  };

  const activeCompanion =
    teamData?.equippedCompanion ||
    teamData?.inventory.find((i) => i.item_id === quest?.profile.active_companion);

  const getThemeClass = (theme: string) => {
    switch (theme) {
      case 'cyberpunk':
        return 'theme-cyberpunk bg-[#0c0814]';
      case 'matrix':
        return 'theme-matrix bg-[#040d06]';
      case 'dracula':
        return 'theme-dracula bg-[#14141e]';
      case 'nord':
      case 'arctic':
        return 'theme-nord bg-[#0b121a]';
      case 'amber':
        return 'theme-amber bg-[#140d04]';
      case 'tokyonight':
        return 'theme-tokyonight bg-[#0f141c]';
      default:
        return 'bg-slate-950';
    }
  };

  return (
    <div className={`min-h-screen text-slate-100 flex flex-col font-sans transition-colors duration-300 ${getThemeClass(activeTheme)}`}>
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-amber-500 text-slate-950 px-4 py-2 rounded-xl font-bold text-xs shadow-2xl animate-bounce">
          {toastMessage}
        </div>
      )}

      {/* Mode démo : backend injoignable, données locales simulées */}
      {offlineDemo && (
        <div role="status" className="bg-amber-500/15 border-b border-amber-500/40 text-amber-200 text-[11px] px-4 py-1.5 text-center">
          <strong>Mode démo hors-ligne</strong> : progression enregistrée dans ce navigateur, données pré-remplies et vérifications des TP simulées.{' '}
          <button
            onClick={() => {
              resetOfflineDemo();
              window.location.reload();
            }}
            className="underline font-bold cursor-pointer hover:text-amber-100"
          >
            Réinitialiser
          </button>
        </div>
      )}

      {/* Top Header Bar */}
      <header className="sticky top-0 z-40 bg-slate-950/85 backdrop-blur-md border-b border-slate-800/80 px-4 py-3">
        <div className="max-w-xl mx-auto flex items-center justify-between">
          <div
            onClick={() => setActiveTab('quest')}
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-600 to-amber-400 flex items-center justify-center text-slate-950 font-black shadow-md shadow-amber-500/20 group-hover:scale-105 transition-transform">
              <Compass className="w-4 h-4 fill-current" />
            </div>
            <div>
              <span className="text-sm font-black tracking-tight text-slate-100 block">
                Quest<span className="text-amber-400">Forge</span>
              </span>
              <span className="text-[10px] text-slate-400 block -mt-0.5">Formation Gamifiée Locale</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Focus Mode Toggle Button */}
            <button
              onClick={() => {
                const next = !focusMode;
                setFocusMode(next);
                showToast(next ? 'Mode Focus activé : distractions masquées' : 'Mode Focus désactivé');
              }}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl font-bold text-xs transition-all cursor-pointer border ${
                focusMode
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-lg shadow-cyan-500/20'
                  : 'bg-slate-900 hover:bg-slate-800 border-slate-800 text-slate-300 hover:text-white'
              }`}
              title={focusMode ? 'Quitter le mode Focus (Échap)' : 'Activer le mode Focus (Session de travail intense)'}
            >
              {focusMode ? <Minimize2 className="w-3.5 h-3.5 text-cyan-300" /> : <Maximize2 className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{focusMode ? 'Quitter Focus' : 'Focus'}</span>
            </button>

            {focusMode ? (
              <div className="flex items-center gap-1.5 bg-cyan-950/70 border border-cyan-500/40 px-2.5 py-1 rounded-xl text-[11px] text-cyan-300 font-mono font-semibold">
                <Target className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                <span>SESSION INTENSE</span>
              </div>
            ) : (
              <>
                <button
                  onClick={() => setShowSoundtrack(true)}
                  className="flex items-center gap-1 bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 px-2 py-1 rounded-xl text-teal-300 font-bold text-xs transition-all cursor-pointer"
                  title="Ambiance Sonore Datacenter & Mémos Feynman"
                >
                  <Headphones className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => setShowClaudePrompt(true)}
                  className="flex items-center gap-1 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 px-2 py-1 rounded-xl text-cyan-300 font-bold text-xs transition-all cursor-pointer"
                  title="Prompt Claude Code pour répliquer le projet"
                >
                  <Bot className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => setShowLeitner(true)}
                  className="flex items-center gap-1 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 px-2.5 py-1 rounded-xl text-purple-300 font-bold text-xs transition-all cursor-pointer"
                  title="Ouvrir l'Arène de répétition espacée Leitner"
                >
                  <Brain className="w-3.5 h-3.5" />
                  <span>{quest?.dueReviewsCount || 0}</span>
                </button>

                {quest && (
                  <>
                    <div className="flex items-center gap-1 bg-rose-500/10 border border-rose-500/20 px-2 py-1 rounded-lg text-rose-400 font-semibold text-xs">
                      <Flame className="w-3.5 h-3.5 fill-rose-500 text-rose-500" />
                      <span>{quest.streak} j</span>
                    </div>
                    <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded-lg text-amber-300 font-semibold text-xs">
                      <Award className="w-3.5 h-3.5" />
                      <span>{quest.profile.total_xp} XP</span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 px-4 py-6 max-w-xl mx-auto w-full">
        {activeTab === 'quest' && (
          <QuestScreen
            quest={quest}
            modules={modules}
            loading={questLoading}
            minutes={minutes}
            onMinutesChange={setMinutes}
            onSelectLesson={handleSelectLesson}
            onAnnounceRest={handleAnnounceRest}
            onSetTopic={handleSetTopic}
            onSwitchModule={handleSwitchModule}
            onRefresh={() => loadQuest()}
            onOpenLeitner={() => setShowLeitner(true)}
            onOpenSkillMatrix={() => setShowSkillMatrix(true)}
            onOpenPodcast={handleOpenPodcast}
            onOpenSandbox={() => setShowSandbox(true)}
            onOpenWarRoom={() => setShowWarRoom(true)}
            onOpenSkillTree={() => setShowSkillTree(true)}
            onOpenGhostDuel={() => setShowGhostDuel(true)}
            onOpenAnkiExport={() => setShowAnkiExport(true)}
            onOpenSoundtrack={() => setShowSoundtrack(true)}
            onOpenCustomChallenge={() => setShowCustomChallenge(true)}
            onOpenClaudePrompt={() => setShowClaudePrompt(true)}
            onOpenTechTree={() => setShowTechTree(true)}
            onOpenGuildLeagues={() => setShowGuildLeagues(true)}
            onOpenInterviewSimulator={() => setShowInterviewSimulator(true)}
            onOpenRunbookExport={() => {
              setRunbookLessonId(activeLessonId || 'l1');
              setRunbookLessonTitle('Procédure Opérationnelle Standard (SOP)');
              setShowRunbookExport(true);
            }}
            onOpenPostMortem={() => setShowPostMortem(true)}
            onOpenSloSimulator={() => setShowSloSimulator(true)}
            onOpenChaosTopology={() => setShowChaosTopology(true)}
            onOpenFeynmanChallenge={() => setShowFeynmanChallenge(true)}
            onOpenThemeSelector={() => setShowThemeSelector(true)}
          />
        )}

        {activeTab === 'lesson' && activeLessonId && (
          <LessonScreen
            lessonId={activeLessonId}
            initialTab={initialLessonTab}
            isTpCompleted={quest?.steps.some(
              (s) => s.kind === 'tp' && s.lesson_id === activeLessonId && s.done
            )}
            onBack={() => setActiveTab('quest')}
            onRefreshQuest={() => loadQuest()}
          />
        )}

        {activeTab === 'team' && (
          <TeamScreen
            teamData={teamData}
            loading={teamLoading}
            onRefresh={() => {
              loadTeam();
              loadQuest();
            }}
            onThemeChanged={(theme) => setActiveTheme(theme)}
          />
        )}

        {activeTab === 'boss' && (
          <BossScreen
            bossData={bossData}
            loading={bossLoading}
            onRefresh={() => {
              loadBoss();
              loadQuest();
            }}
            onSelectLesson={handleSelectLesson}
          />
        )}

        {activeTab === 'weekly' && (
          <WeeklyScreen
            onModuleImported={() => {
              loadQuest();
              showToast('Nouveau module pris en compte !');
            }}
          />
        )}
      </main>

      {/* Modal Arène de Leitner */}
      {showLeitner && (
        <LeitnerArena
          onClose={() => setShowLeitner(false)}
          onSelectLesson={(lId) => {
            setShowLeitner(false);
            handleSelectLesson(lId);
          }}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Matrice des Compétences & Radar */}
      {showSkillMatrix && quest && (
        <SkillMatrix
          profile={quest.profile}
          activityHistory={quest.activityHistory}
          onClose={() => setShowSkillMatrix(false)}
        />
      )}

      {/* Modal Lecteur Podcast / Mode Trajet */}
      {showPodcast && podcastLesson && (
        <PodcastPlayer
          lesson={podcastLesson}
          onClose={() => setShowPodcast(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Bac à Sable Libre / Défis Bash */}
      {showSandbox && (
        <SandboxPlayground
          onClose={() => setShowSandbox(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal War Room (Astreinte P1) */}
      {showWarRoom && (
        <WarRoomModal
          onClose={() => setShowWarRoom(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Arbre de Talents RPG */}
      {showSkillTree && quest && (
        <SkillTreeModal
          profile={quest.profile}
          onClose={() => setShowSkillTree(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Duels Fantômes SRE */}
      {showGhostDuel && (
        <GhostDuelModal
          onClose={() => setShowGhostDuel(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Export Anki & Cheat-Sheet */}
      {showAnkiExport && (
        <AnkiExportModal
          onClose={() => setShowAnkiExport(false)}
        />
      )}

      {/* Modal Ambiance Sonore & Feynman */}
      {showSoundtrack && (
        <SoundtrackPlayer
          onClose={() => setShowSoundtrack(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Générateur Instantané de Défis TP */}
      {showCustomChallenge && (
        <CustomChallengeModal
          onClose={() => setShowCustomChallenge(false)}
          onRefreshQuest={() => loadQuest()}
        />
      )}

      {/* Modal Prompt Claude Code */}
      {showClaudePrompt && (
        <ClaudeCodePromptModal onClose={() => setShowClaudePrompt(false)} />
      )}

      {/* Modal Tech Tree SRE & Linux */}
      {showTechTree && (
        <TechTreeModal
          onClose={() => setShowTechTree(false)}
        />
      )}

      {/* Modal Ligues de Guilde & Raids Hebdomadaires */}
      {showGuildLeagues && (
        <GuildLeaguesModal
          onClose={() => setShowGuildLeagues(false)}
        />
      )}

      {/* Modal Simulateur d'Entretien Oral SRE */}
      {showInterviewSimulator && (
        <InterviewSimulatorModal
          onClose={() => setShowInterviewSimulator(false)}
        />
      )}

      {/* Modal Export Runbook / SOP Markdown */}
      {showRunbookExport && (
        <RunbookExportModal
          lessonId={runbookLessonId}
          title={runbookLessonTitle}
          onClose={() => setShowRunbookExport(false)}
        />
      )}

      {/* Modal Studio Post-Mortem Blameless */}
      {showPostMortem && (
        <PostMortemModal
          onClose={() => setShowPostMortem(false)}
          onRewardExp={(xp) => {
            loadQuest();
            showToast(`+${xp} XP Rapport Post-Mortem validé !`);
          }}
        />
      )}

      {/* Modal Simulateur SLI / SLO & Error Budget */}
      {showSloSimulator && (
        <SloSimulatorModal
          onClose={() => setShowSloSimulator(false)}
          onRewardExp={(xp) => {
            loadQuest();
            showToast(`+${xp} XP Session Fiabilité SRE terminée !`);
          }}
        />
      )}

      {/* Modal Topology Breakdown & Chaos Injector */}
      {showChaosTopology && (
        <ChaosTopologyModal
          onClose={() => setShowChaosTopology(false)}
          onRewardExp={(xp) => {
            loadQuest();
            showToast(`+${xp} XP Panne d'Architecture résolue !`);
          }}
        />
      )}

      {/* Modal Défi Feynman : Explique à un Junior */}
      {showFeynmanChallenge && (
        <FeynmanChallengeModal
          onClose={() => setShowFeynmanChallenge(false)}
          onRewardExp={(xp) => {
            loadQuest();
            showToast(`+${xp} XP Défi Pédagogique Feynman validé !`);
          }}
        />
      )}

      {/* Modal Thèmes Terminal Hacker & OCI */}
      {showThemeSelector && (
        <ThemeSelectorModal
          currentTheme={activeTheme}
          onClose={() => setShowThemeSelector(false)}
          onSelectTheme={async (themeId) => {
            setActiveTheme(themeId);
            try {
              await api.setTheme(themeId);
              showToast(`Thème appliqué : ${themeId}`);
              loadQuest();
            } catch {
              // Local fallback
            }
          }}
        />
      )}

      {/* Mascotte Compagnon Flottante (masquée en mode focus) */}
      {!focusMode && (
        <CompanionBar
          companion={activeCompanion}
          onOpenTeam={() => setActiveTab('team')}
        />
      )}

      {/* Floating Exit Pill for Focus Mode */}
      {focusMode && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 animate-fade-in">
          <button
            onClick={() => {
              setFocusMode(false);
              showToast('Mode Focus désactivé');
            }}
            className="bg-slate-900/95 hover:bg-slate-800 border border-cyan-500/50 text-cyan-300 hover:text-cyan-200 px-4 py-2 rounded-full text-xs font-bold shadow-2xl backdrop-blur-md flex items-center gap-2 cursor-pointer transition-all hover:scale-105"
          >
            <Minimize2 className="w-3.5 h-3.5" />
            <span>Quitter le mode Focus (Échap)</span>
          </button>
        </div>
      )}

      {/* Bottom Sticky Tab Navigation Bar (masquée en mode focus) */}
      {!focusMode && (
        <nav className="sticky bottom-0 z-40 bg-slate-950/95 backdrop-blur-md border-t border-slate-800 px-3 py-2">
          <div className="max-w-xl mx-auto flex items-center justify-around">
            <button
              onClick={() => setActiveTab('quest')}
              className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all cursor-pointer ${
                activeTab === 'quest'
                  ? 'text-amber-400 font-bold scale-105'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Compass className="w-5 h-5" />
              <span className="text-[10px]">Quête</span>
            </button>

            {activeLessonId && (
              <button
                onClick={() => setActiveTab('lesson')}
                className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all cursor-pointer ${
                  activeTab === 'lesson'
                    ? 'text-amber-400 font-bold scale-105'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BookOpen className="w-5 h-5" />
                <span className="text-[10px]">Leçon</span>
              </button>
            )}

            <button
              onClick={() => setActiveTab('team')}
              className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all cursor-pointer ${
                activeTab === 'team'
                  ? 'text-amber-400 font-bold scale-105'
                : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Users className="w-5 h-5" />
              <span className="text-[10px]">Équipe</span>
            </button>

            <button
              onClick={() => setActiveTab('boss')}
              className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all cursor-pointer ${
                activeTab === 'boss'
                  ? 'text-rose-400 font-bold scale-105'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Swords className="w-5 h-5" />
              <span className="text-[10px]">Boss</span>
            </button>

            <button
              onClick={() => setActiveTab('weekly')}
              className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all cursor-pointer ${
                activeTab === 'weekly'
                  ? 'text-indigo-400 font-bold scale-105'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Calendar className="w-5 h-5" />
              <span className="text-[10px]">Semaine</span>
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}

export default App;
