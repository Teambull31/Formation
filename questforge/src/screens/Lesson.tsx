import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  Volume2,
  Play,
  Pause,
  BookOpen,
  HelpCircle,
  Terminal as TerminalIcon,
  CheckCircle2,
  XCircle,
  HelpCircle as HintIcon,
  ShieldAlert,
  Sparkles,
  RefreshCw,
  ExternalLink,
  Download,
  Copy,
  Check,
  Bot,
  Send,
  Code,
  Zap,
  Edit3,
  FileCode,
  Info,
  FolderTree,
  History,
  FileText,
  AlertTriangle,
} from 'lucide-react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import confetti from 'canvas-confetti';
import { api, LessonData, QcmAnswerResult, ChaosIncident } from '../api';
import { renderLesson } from '../renderLesson';
import { RunbookExportModal } from '../components/RunbookExportModal';

interface LessonProps {
  lessonId: string;
  initialTab?: 'body' | 'qcm' | 'tp';
  isTpCompleted?: boolean;
  onBack: () => void;
  onRefreshQuest: () => void;
}

const SNIPPETS = [
  { label: 'ouvrir avec vim', code: `vim config.json` },
  { label: 'inspecter fichier', code: `cat config.json` },
  { label: 'lister workspace', code: `ls -la` },
  { label: 'vérifier syntaxe json', code: `python3 -m json.tool config.json` },
  { label: 'afficher variables', code: `env | grep -E "PATH|USER|PWD"` },
  { label: 'signaux unix', code: `kill -l` },
];

export const LessonScreen: React.FC<LessonProps> = ({
  lessonId,
  initialTab = 'body',
  isTpCompleted = false,
  onBack,
  onRefreshQuest,
}) => {
  const [activeTab, setActiveTab] = useState<'body' | 'qcm' | 'tp'>(initialTab);
  const [lesson, setLesson] = useState<LessonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Audio state
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState<1 | 1.5 | 2>(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // QCM state
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [qcmResults, setQcmResults] = useState<Record<string, QcmAnswerResult>>({});
  const [qcmSubmitting, setQcmSubmitting] = useState(false);

  // TP state
  const [checkResult, setCheckResult] = useState<{ passed: boolean; output: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const [tpAlreadyDone, setTpAlreadyDone] = useState(isTpCompleted || false);
  const [tpAlreadyDoneNotice, setTpAlreadyDoneNotice] = useState(false);
  const [hintLevel, setHintLevel] = useState(1);
  const [hints, setHints] = useState<string[]>([]);
  const [hintLoading, setHintLoading] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);
  const [isRemote403, setIsRemote403] = useState(false);
  const [showVimGuide, setShowVimGuide] = useState(false);

  // 1. Workspace File Explorer & Diff Viewer
  const [showFileExplorer, setShowFileExplorer] = useState(false);
  const [selectedDiffFile, setSelectedDiffFile] = useState<string | null>(null);

  // 2. Mode Chaos Monkey
  const [activeChaos, setActiveChaos] = useState<ChaosIncident | null>(null);
  const [chaosLoading, setChaosLoading] = useState(false);
  const [chaosResolvedNotice, setChaosResolvedNotice] = useState(false);

  // 3. Time-Travel History Replay
  const [showTimeTravel, setShowTimeTravel] = useState(false);
  const [timeTravelIndex, setTimeTravelIndex] = useState(0);

  // 4. SRE Runbook Modal
  const [showRunbookModal, setShowRunbookModal] = useState(false);

  // Simulated commands state for mobile / remote
  const [simulatedCmd, setSimulatedCmd] = useState('');
  const [simulatedVimOpen, setSimulatedVimOpen] = useState(false);
  const [simulatedVimFile, setSimulatedVimFile] = useState('config.json');
  const [simulatedVimContent, setSimulatedVimContent] = useState('{\n  "provider": "demo",\n  "active": true\n}');
  const [simulatedVimMode, setSimulatedVimMode] = useState<'NORMAL' | 'INSERT'>('NORMAL');
  const [simulatedVimStatus, setSimulatedVimStatus] = useState<string | null>(null);

  const [terminalHistory, setTerminalHistory] = useState<Array<{ cmd: string; out: string }>>([
    {
      cmd: '# Bienvenue dans le terminal QuestForge',
      out: 'Environnement de TP préparé. Entrez vos commandes (ex: vim config.json, ls, cat) ou utilisez les snippets.',
    },
  ]);

  // AI Tutor drawer
  const [showTutor, setShowTutor] = useState(false);
  const [tutorMessages, setTutorMessages] = useState<Array<{ role: 'user' | 'tutor'; text: string }>>([
    {
      role: 'tutor',
      text: "Bonjour ! Je suis votre tuteur technique Qwen. Une hésitation sur le TP ou un doute sur une syntaxe ? Posez-moi votre question !",
    },
  ]);
  const [tutorInput, setTutorInput] = useState('');
  const [tutorLoading, setTutorLoading] = useState(false);

  // Terminal DOM ref
  const terminalContainerRef = useRef<HTMLDivElement | null>(null);
  const termInstanceRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (isTpCompleted !== undefined) {
      setTpAlreadyDone(isTpCompleted);
    }
  }, [isTpCompleted]);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    api
      .getLesson(lessonId)
      .then((data) => {
        if (isMounted) {
          setLesson(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Impossible de charger la leçon');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [lessonId]);

  // Terminal initialization on TP tab
  useEffect(() => {
    if (activeTab !== 'tp' || !terminalContainerRef.current) return;

    if (termInstanceRef.current) {
      termInstanceRef.current.dispose();
      termInstanceRef.current = null;
    }

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'Fira Code', monospace",
      theme: {
        background: '#090d16',
        foreground: '#e2e8f0',
        cursor: '#f59e0b',
        selectionBackground: 'rgba(245, 158, 11, 0.3)',
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalContainerRef.current);
    fitAddon.fit();
    termInstanceRef.current = term;

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      // Send initial terminal dimensions to PTY so full-screen vim works accurately
      try {
        ws.send(JSON.stringify({ resize: [term.rows, term.cols] }));
      } catch {}
      term.writeln('\x1b[1;33m[QuestForge Terminal]\x1b[0m Connecté au terminal bash local.');
      term.writeln('Entrez vos commandes (ex: \x1b[32mvim config.json\x1b[0m, cat, ls, check.sh)...\n');
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        term.write(new Uint8Array(event.data));
      } else {
        term.write(event.data);
      }
    };

    ws.onerror = () => {
      setIsRemote403(true);
    };

    ws.onclose = (event) => {
      if (event.code === 1008) {
        setIsRemote403(true);
      }
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    const handleResize = () => {
      fitAddon.fit();
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ resize: [term.rows, term.cols] }));
        } catch {}
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      term.dispose();
      termInstanceRef.current = null;
    };
  }, [activeTab]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(() => {});
    }
  };

  const handleSpeedChange = (rate: 1 | 1.5 | 2) => {
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  };

  const markLessonCompleted = async () => {
    try {
      await api.completeStep('lesson', lessonId);
      confetti({ particleCount: 40, spread: 60, origin: { y: 0.8 } });
      onRefreshQuest();
      setActiveTab('qcm');
    } catch {}
  };

  const handleQcmSubmit = async (questionId: string) => {
    const chosen = selectedAnswers[questionId];
    if (chosen === undefined) return;

    setQcmSubmitting(true);
    try {
      const res = await api.answerQcm(questionId, chosen);
      setQcmResults((prev) => ({ ...prev, [questionId]: res }));

      if (res.correct) {
        await api.completeStep('qcm', lessonId);
        confetti({ particleCount: 50, spread: 70, origin: { y: 0.7 } });
        onRefreshQuest();
      }
    } catch (err: any) {
      alert(err.message || 'Erreur lors de la validation du QCM');
    } finally {
      setQcmSubmitting(false);
    }
  };

  const handleCheckTp = async () => {
    if (!lesson?.tp) return;
    setChecking(true);
    setTpAlreadyDoneNotice(false);
    try {
      const res = await api.checkTp(lesson.tp.id);
      setCheckResult(res);
      if (res.passed) {
        const stepRes = await api.completeStep('tp', lessonId);
        if (stepRes.alreadyCompleted || tpAlreadyDone) {
          setTpAlreadyDone(true);
          setTpAlreadyDoneNotice(true);
        } else {
          setTpAlreadyDone(true);
          confetti({ particleCount: 90, spread: 80, origin: { y: 0.6 } });
        }
        onRefreshQuest();
      }
    } catch (err: any) {
      if (err.status === 403) {
        setIsRemote403(true);
      } else {
        setCheckResult({ passed: false, output: err.message || 'Erreur lors de la vérification' });
      }
    } finally {
      setChecking(false);
    }
  };

  const handleGetHint = async () => {
    if (!lesson?.tp) return;
    setHintLoading(true);
    try {
      const res = await api.getTpHint(lesson.tp.id, hintLevel);
      setHints((prev) => [...prev, res.hint]);
      setHintLevel((prev) => prev + 1);
      onRefreshQuest();
    } catch (err: any) {
      alert(err.message || "Erreur lors de l'obtention de l'indice");
    } finally {
      setHintLoading(false);
    }
  };

  const handleSendSnippet = (code: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(code + '\n');
    } else {
      if (code.startsWith('vim') || code.startsWith('vi')) {
        handleOpenSimulatedVim(code.split(' ')[1] || 'config.json');
        return;
      }
      // Add to simulated terminal
      setTerminalHistory((prev) => [
        ...prev,
        { cmd: code, out: `✓ Exécuté : ${code}` },
      ]);
    }
    setCopiedSnippet(code);
    setTimeout(() => setCopiedSnippet(null), 1500);
  };

  const handleOpenSimulatedVim = (fileName: string = 'config.json') => {
    setSimulatedVimFile(fileName);
    setSimulatedVimMode('NORMAL');
    setSimulatedVimStatus(null);
    setSimulatedVimOpen(true);
  };

  const handleSaveSimulatedVim = () => {
    setTerminalHistory((prev) => [
      ...prev,
      {
        cmd: `vim ${simulatedVimFile}  [:wq]`,
        out: `"${simulatedVimFile}" 4L, 56B written.\n✓ Fichier '${simulatedVimFile}' sauvegardé avec succès et prêt pour la vérification.`,
      },
    ]);
    setSimulatedVimOpen(false);
  };

  const handleSimulatedSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!simulatedCmd.trim()) return;

    const cmd = simulatedCmd.trim();
    if (cmd.startsWith('vim') || cmd.startsWith('vi ') || cmd === 'vi') {
      const target = cmd.split(' ')[1] || 'config.json';
      handleOpenSimulatedVim(target);
      setSimulatedCmd('');
      return;
    }

    let out = '';
    if (cmd.includes('config.json')) {
      out = 'config.json créé avec succès {"provider": "demo", "active": true}';
    } else if (cmd.includes('ls')) {
      out = 'total 4\n-rw-r--r-- 1 student student 42 config.json\n-rwxr-xr-x 1 student student 180 check.sh';
    } else if (cmd.includes('cat') || cmd.includes('json')) {
      out = simulatedVimContent || '{\n  "provider": "demo",\n  "active": true\n}';
    } else if (cmd === 'clear') {
      setTerminalHistory([]);
      setSimulatedCmd('');
      return;
    } else {
      out = `bash: commande simulée exécutée avec code 0`;
    }

    setTerminalHistory((prev) => [...prev, { cmd, out }]);
    setSimulatedCmd('');
  };

  const handleInjectChaos = async () => {
    setChaosLoading(true);
    setChaosResolvedNotice(false);
    try {
      const incident = await api.injectChaos(lesson?.tp?.id);
      setActiveChaos(incident);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(`\n# [CHAOS MONKEY ALERTE P1] : ${incident.title}\n`);
      } else {
        setTerminalHistory((prev) => [
          ...prev,
          {
            cmd: `[CHAOS] ${incident.title}`,
            out: `⚠️ DÉFAILLANCE DE PRODUCTION INJECTÉE :\n${incident.description}\nSymptôme : ${incident.symptom}\nAstuce : ${incident.remedyHint}`,
          },
        ]);
      }
    } catch (err: any) {
      alert(err.message || 'Erreur lors de l\'injection de chaos');
    } finally {
      setChaosLoading(false);
    }
  };

  const handleResolveChaos = async () => {
    if (!activeChaos) return;
    try {
      await api.resolveChaos(activeChaos.id);
      setActiveChaos((prev) => (prev ? { ...prev, resolved: true } : null));
      setChaosResolvedNotice(true);
      confetti({ particleCount: 70, spread: 80, origin: { y: 0.6 } });
      onRefreshQuest();
    } catch (err: any) {
      alert(err.message || 'Erreur lors de la résolution du chaos');
    }
  };

  const [hintMessage, setHintMessage] = useState<string | null>(null);

  const handleRequestHint = async () => {
    if (!lesson?.tp) return;
    setHintLoading(true);
    try {
      const nextLevel = hintLevel + 1;
      const res = await api.getTpHint(lesson.tp.id, nextLevel);
      setHintLevel(nextLevel);
      setHintMessage(res.hint);
    } catch {
      setHintMessage("Conseil : analysez les consignes pour repérer le nom de fichier et les clés demandées.");
    } finally {
      setHintLoading(false);
    }
  };

  const handleExportSkeleton = () => {
    const scriptContent = `#!/usr/bin/env bash
# Canevas de travail — Exercice : ${lesson?.tp?.title || 'TP'}
# Consigne : rédigez vos commandes bash pour satisfaire les critères du test
set -e

echo "[+] Démarrage de l'exercice..."

# TODO: Écrivez vos commandes ici (sans solution pré-écrite)
# Ex: créer les fichiers requis, appliquer les permissions, etc.

echo "[+] Fin du script."
`;
    const blob = new Blob([scriptContent], { type: 'text/x-shellscript' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `canevas_${lesson?.id || 'tp'}.sh`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleAskTutor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tutorInput.trim() || !lesson?.tp) return;

    const userText = tutorInput.trim();
    setTutorMessages((prev) => [...prev, { role: 'user', text: userText }]);
    setTutorInput('');
    setTutorLoading(true);

    try {
      const res = await api.askTpTutor(lesson.tp.id, userText);
      setTutorMessages((prev) => [...prev, { role: 'tutor', text: res.reply }]);
    } catch {
      setTutorMessages((prev) => [
        ...prev,
        {
          role: 'tutor',
          text: "Pour réussir ce TP, vérifiez que le fichier config.json existe bien dans le dossier courant et comporte les attributs 'provider' et 'active'.",
        },
      ]);
    } finally {
      setTutorLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin mb-3 text-amber-500" />
        <p className="text-sm">Chargement de la leçon...</p>
      </div>
    );
  }

  if (error || !lesson) {
    return (
      <div className="max-w-xl mx-auto p-6 bg-rose-950/30 border border-rose-800 rounded-2xl text-center space-y-3">
        <XCircle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-base font-bold text-rose-200">Erreur de chargement</h3>
        <p className="text-xs text-rose-300">{error || 'Leçon non trouvée'}</p>
        <button
          onClick={onBack}
          className="mt-3 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl cursor-pointer"
        >
          Retour à la quête
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-xl mx-auto pb-12 relative">
      {/* Header avec bouton retour et badges */}
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-slate-100 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl cursor-pointer transition-all"
        >
          <ArrowLeft className="w-4 h-4" /> Retour
        </button>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 px-2.5 py-1 rounded-lg">
            {lesson.skill}
          </span>
          <span className="text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-1 rounded-lg">
            ~{lesson.minutes} min
          </span>
        </div>
      </div>

      {/* Titre de la leçon */}
      <div>
        <p className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
          {lesson.module_title}
        </p>
        <h1 className="text-xl font-extrabold text-slate-100 mt-1">{lesson.title}</h1>
      </div>

      {/* Onglets de la leçon */}
      <div className="flex bg-slate-900/90 p-1 rounded-xl border border-slate-800">
        <button
          onClick={() => setActiveTab('body')}
          className={`flex-1 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
            activeTab === 'body'
              ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" /> 1. Cours & Audio
        </button>
        <button
          onClick={() => setActiveTab('qcm')}
          className={`flex-1 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
            activeTab === 'qcm'
              ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <HelpCircle className="w-3.5 h-3.5" /> 2. QCM ({lesson.qcm.length})
        </button>
        {lesson.tp && (
          <button
            onClick={() => setActiveTab('tp')}
            className={`flex-1 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              activeTab === 'tp'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <TerminalIcon className="w-3.5 h-3.5" /> 3. TP Terminal
          </button>
        )}
      </div>

      {/* ONGLET 1 : Cours & Audio */}
      {activeTab === 'body' && (
        <div className="space-y-6">
          {/* Lecteur audio intégré */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <Volume2 className="w-4 h-4 text-amber-400" /> Synthèse vocale de la leçon
              </span>
              <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
                {([1, 1.5, 2] as const).map((rate) => (
                  <button
                    key={rate}
                    onClick={() => handleSpeedChange(rate)}
                    className={`text-[10px] font-mono px-1.5 py-0.5 rounded cursor-pointer ${
                      playbackRate === rate
                        ? 'bg-amber-500 text-slate-950 font-bold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {rate}x
                  </button>
                ))}
              </div>
            </div>

            <audio
              ref={audioRef}
              src={api.getAudioUrl(lesson.id)}
              onTimeUpdate={(e) => setCurrentTime((e.target as HTMLAudioElement).currentTime)}
              onLoadedMetadata={(e) => setDuration((e.target as HTMLAudioElement).duration)}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              className="hidden"
            />

            <div className="flex items-center gap-3">
              <button
                onClick={togglePlay}
                className="w-10 h-10 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center justify-center shadow-lg shadow-amber-500/20 cursor-pointer transition-all flex-shrink-0"
              >
                {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
              </button>

              <div className="flex-1 space-y-1">
                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  value={currentTime}
                  onChange={(e) => {
                    if (audioRef.current) {
                      audioRef.current.currentTime = parseFloat(e.target.value);
                    }
                  }}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
                <div className="flex justify-between text-[10px] font-mono text-slate-400">
                  <span>{Math.floor(currentTime)}s</span>
                  <span>{Math.floor(duration || 0)}s</span>
                </div>
              </div>
            </div>
          </div>

          {/* Contenu Markdown rendu */}
          <div
            className="prose prose-invert max-w-none text-slate-200 bg-slate-900/60 p-5 rounded-2xl border border-slate-800/80 shadow-md leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderLesson(lesson.body_md) }}
          />

          <button
            onClick={markLessonCompleted}
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 cursor-pointer transition-all"
          >
            <CheckCircle2 className="w-4 h-4" /> Marquer le cours lu (+20 XP) & passer au QCM
          </button>
        </div>
      )}

      {/* ONGLET 2 : QCM */}
      {activeTab === 'qcm' && (
        <div className="space-y-5">
          {lesson.qcm.length === 0 ? (
            <p className="text-center text-xs text-slate-400 py-8">Aucun QCM associé à cette leçon.</p>
          ) : (
            lesson.qcm.map((q, idx) => {
              const res = qcmResults[q.id];
              return (
                <div
                  key={q.id}
                  className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4"
                >
                  <div className="flex items-center gap-2 text-xs font-mono text-purple-400">
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20">
                      Question {idx + 1}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-100 leading-snug">{q.text}</h3>

                  <div className="space-y-2">
                    {q.options.map((opt, optIdx) => {
                      const isSelected = selectedAnswers[q.id] === optIdx;
                      return (
                        <label
                          key={optIdx}
                          onClick={() => setSelectedAnswers((prev) => ({ ...prev, [q.id]: optIdx }))}
                          className={`flex items-start gap-3 p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                            isSelected
                              ? 'bg-purple-950/30 border-purple-500 text-purple-100'
                              : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          <input
                            type="radio"
                            name={`q-${q.id}`}
                            checked={isSelected}
                            onChange={() => {}}
                            className="mt-0.5 text-purple-600 focus:ring-purple-500 bg-slate-900 border-slate-700"
                          />
                          <span className="leading-relaxed">{opt}</span>
                        </label>
                      );
                    })}
                  </div>

                  {!res ? (
                    <button
                      onClick={() => handleQcmSubmit(q.id)}
                      disabled={selectedAnswers[q.id] === undefined || qcmSubmitting}
                      className="w-full py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                    >
                      {qcmSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Valider la réponse'}
                    </button>
                  ) : (
                    <div
                      className={`p-4 rounded-xl border space-y-2 text-xs leading-relaxed ${
                        res.correct
                          ? 'bg-emerald-950/40 border-emerald-700/60 text-emerald-200'
                          : 'bg-rose-950/40 border-rose-700/60 text-rose-200'
                      }`}
                    >
                      <div className="flex items-center gap-2 font-bold text-sm">
                        {res.correct ? (
                          <>
                            <CheckCircle2 className="w-5 h-5 text-emerald-400" /> Bonne réponse ! (+40 XP)
                          </>
                        ) : (
                          <>
                            <XCircle className="w-5 h-5 text-rose-400" /> Réponse incorrecte
                          </>
                        )}
                      </div>
                      <p>{res.explanation}</p>

                      {/* Mini-remédiation guidée */}
                      {!res.correct && (
                        <div className="pt-2 border-t border-rose-800/40 flex items-center justify-between">
                          <button
                            onClick={() => setActiveTab('body')}
                            className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-100 font-bold text-[11px] flex items-center gap-1.5 cursor-pointer shadow-sm transition-all"
                          >
                            <Zap className="w-3.5 h-3.5 text-amber-400" /> Mini-remédiation 3 min (Voir notion dans le cours)
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ONGLET 3 : TP Terminal */}
      {activeTab === 'tp' && lesson.tp && (
        <div className="space-y-5">
          {/* Instructions du TP */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                <TerminalIcon className="w-4 h-4" /> Consignes du TP
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRequestHint}
                  disabled={hintLoading}
                  className="text-[10px] font-semibold text-amber-300 bg-amber-950/80 hover:bg-amber-900 px-2.5 py-1 rounded-lg border border-amber-700/60 flex items-center gap-1 cursor-pointer transition-all"
                  title="Demander un indice progressif sans révéler la commande complète"
                >
                  <Sparkles className="w-3 h-3 text-amber-400" /> {hintLoading ? 'Chargement...' : hintLevel > 0 ? `Indice ${hintLevel}/2` : 'Indice'}
                </button>
                <button
                  onClick={handleExportSkeleton}
                  className="text-[10px] font-mono text-slate-300 bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded-lg border border-slate-700 flex items-center gap-1 cursor-pointer transition-all"
                  title="Télécharger un modèle de script vierge avec commentaires"
                >
                  <Download className="w-3 h-3 text-cyan-400" /> Canevas (.sh)
                </button>
                <button
                  onClick={() => setShowTutor(!showTutor)}
                  className="text-[10px] font-semibold text-purple-300 bg-purple-950/80 hover:bg-purple-900 px-2.5 py-1 rounded-lg border border-purple-700/60 flex items-center gap-1 cursor-pointer transition-all"
                >
                  <Bot className="w-3 h-3 text-purple-400" /> {showTutor ? 'Masquer Tuteur' : 'Tuteur IA'}
                </button>
              </div>
            </div>

            {hintMessage && (
              <div className="p-3 bg-amber-950/40 border border-amber-500/40 rounded-xl text-xs text-amber-200 animate-fade-in space-y-1">
                <div className="flex items-center justify-between font-bold text-[11px] text-amber-300">
                  <span>💡 Indice méthodologique (Niveau {hintLevel})</span>
                  <button
                    onClick={() => setHintMessage(null)}
                    className="text-[10px] text-amber-400 hover:text-white cursor-pointer"
                  >
                    Fermer
                  </button>
                </div>
                <p className="leading-relaxed">{hintMessage}</p>
              </div>
            )}

            <div
              className="prose prose-invert text-xs text-slate-200 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: renderLesson(lesson.tp.instructions_md) }}
            />
          </div>

          {/* Snippets rapides */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1 font-semibold">
                <Code className="w-3.5 h-3.5 text-amber-400" /> Snippets & Commandes rapides (1 clic) :
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {SNIPPETS.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendSnippet(s.code)}
                  className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[11px] font-mono text-slate-300 rounded-lg flex items-center gap-1.5 cursor-pointer transition-all group"
                >
                  <span>{s.label}</span>
                  {copiedSnippet === s.code ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3 text-slate-500 group-hover:text-slate-300" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Barre d'outils et Outils Avancés Terminal */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-slate-900/80 border border-slate-800 rounded-xl text-xs">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-bold text-slate-300 flex items-center gap-1.5 text-[11px] mr-1">
                <Edit3 className="w-3.5 h-3.5 text-amber-400" /> Outils :
              </span>
              <button
                onClick={() => handleSendSnippet('vim config.json')}
                className="px-2 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-mono cursor-pointer transition-all"
                title="Lancer vim sur le fichier config.json"
              >
                vim config.json
              </button>
              <button
                onClick={() => handleSendSnippet('cat config.json')}
                className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[10px] font-mono cursor-pointer transition-all"
                title="Afficher le contenu du fichier"
              >
                cat config.json
              </button>

              <button
                onClick={() => setShowFileExplorer(!showFileExplorer)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 cursor-pointer transition-all border ${
                  showFileExplorer
                    ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 font-bold'
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                }`}
                title="Ouvrir l'explorateur de fichiers du workspace et le comparateur Diff"
              >
                <FolderTree className="w-3 h-3 text-cyan-400" />
                <span>Explorateur & Diff</span>
              </button>

              <button
                onClick={handleInjectChaos}
                disabled={chaosLoading}
                className="px-2 py-0.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-mono flex items-center gap-1 cursor-pointer transition-all"
                title="Injecter une défaillance réelle imprévue pour tester vos réflexes d'astreinte (+50 XP)"
              >
                <AlertTriangle className="w-3 h-3 text-rose-400" />
                <span>Chaos Monkey (+50 XP)</span>
              </button>

              <button
                onClick={() => setShowTimeTravel(!showTimeTravel)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 cursor-pointer transition-all border ${
                  showTimeTravel
                    ? 'bg-purple-500/20 border-purple-400 text-purple-300 font-bold'
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                }`}
                title="Rejouer l'historique de vos commandes pas à pas"
              >
                <History className="w-3 h-3 text-purple-400" />
                <span>Replay Historique</span>
              </button>

              <button
                onClick={() => setShowRunbookModal(true)}
                className="px-2 py-0.5 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-mono flex items-center gap-1 cursor-pointer transition-all"
                title="Générer la Procédure Opérationnelle Standard (SOP) / Runbook Markdown"
              >
                <FileText className="w-3 h-3 text-blue-400" />
                <span>Runbook SOP</span>
              </button>
            </div>

            <button
              onClick={() => setShowVimGuide(!showVimGuide)}
              className="px-2 py-1 rounded-lg bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-200 text-[11px] font-semibold flex items-center gap-1.5 cursor-pointer transition-all"
            >
              <Info className="w-3.5 h-3.5 text-indigo-400" />
              <span>{showVimGuide ? 'Masquer Guide Vim' : 'Guide Vim'}</span>
            </button>
          </div>

          {/* Bannière Défaillance Chaos Monkey */}
          {activeChaos && (
            <div
              className={`p-3.5 rounded-xl border text-xs space-y-2 animate-fade-in shadow-xl ${
                activeChaos.resolved || chaosResolvedNotice
                  ? 'bg-emerald-950/40 border-emerald-500 text-emerald-200'
                  : 'bg-rose-950/50 border-rose-500/80 text-rose-200'
              }`}
            >
              <div className="flex items-center justify-between font-bold text-sm">
                <div className="flex items-center gap-2">
                  <AlertTriangle
                    className={`w-4 h-4 ${
                      activeChaos.resolved ? 'text-emerald-400' : 'text-rose-400 animate-bounce'
                    }`}
                  />
                  <span>
                    {activeChaos.resolved
                      ? '✓ Incident Chaos Résolu avec succès (+50 XP) !'
                      : `[CHAOS MONKEY ALERTE P1] : ${activeChaos.title}`}
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-900 border border-rose-500/40 text-rose-300">
                  Défi Résilience
                </span>
              </div>

              <p className="text-xs leading-relaxed text-slate-200">{activeChaos.description}</p>

              <div className="p-2.5 bg-slate-950/80 rounded-lg font-mono text-[11px] space-y-1 border border-slate-800">
                <div className="text-rose-400 font-bold">Symptôme : {activeChaos.symptom}</div>
                <div className="text-slate-400">Indice : {activeChaos.remedyHint}</div>
                <div className="text-cyan-300">Commande corrective : <code>{activeChaos.remedyCommand}</code></div>
              </div>

              {!activeChaos.resolved && (
                <div className="flex justify-end pt-1">
                  <button
                    onClick={handleResolveChaos}
                    className="px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs rounded-xl flex items-center gap-1.5 cursor-pointer shadow-md shadow-emerald-500/20"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Valider la résolution du Chaos (+50 XP)</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Explorateur de Fichiers & Diff Viewer */}
          {showFileExplorer && (
            <div className="p-3 bg-slate-900 border border-cyan-500/40 rounded-xl space-y-3 animate-fade-in text-xs shadow-xl">
              <div className="flex items-center justify-between font-bold text-cyan-300 text-xs border-b border-slate-800 pb-1.5">
                <span className="flex items-center gap-1.5">
                  <FolderTree className="w-4 h-4 text-cyan-400" /> Explorateur Workspace & Diff Viewer
                </span>
                <span className="text-[10px] font-mono text-slate-400">Répertoire : /app/workspace</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* File List */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Fichiers du Workspace
                  </span>
                  <div className="space-y-1 font-mono text-xs">
                    <button
                      onClick={() => setSelectedDiffFile('config.json')}
                      className={`w-full p-2 rounded-lg border text-left flex items-center justify-between cursor-pointer transition-all ${
                        selectedDiffFile === 'config.json' || !selectedDiffFile
                          ? 'bg-cyan-500/10 border-cyan-400 text-cyan-200'
                          : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileCode className="w-3.5 h-3.5 text-amber-400" />
                        <span className="font-bold">config.json</span>
                      </div>
                      <span className="text-[10px] text-slate-500">-rw-r--r-- (42 B)</span>
                    </button>

                    <button
                      onClick={() => setSelectedDiffFile('check.sh')}
                      className={`w-full p-2 rounded-lg border text-left flex items-center justify-between cursor-pointer transition-all ${
                        selectedDiffFile === 'check.sh'
                          ? 'bg-cyan-500/10 border-cyan-400 text-cyan-200'
                          : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileCode className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="font-bold">check.sh</span>
                      </div>
                      <span className="text-[10px] text-slate-500">-rwxr-xr-x (180 B)</span>
                    </button>
                  </div>
                </div>

                {/* Diff Viewer */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Comparateur Diff (Actuel vs Référence Attendue)
                  </span>
                  <div className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg font-mono text-[11px] leading-relaxed overflow-x-auto space-y-0.5">
                    <div className="text-slate-500 border-b border-slate-800 pb-1 mb-1">
                      --- workspace/{selectedDiffFile || 'config.json'} (Actuel)
                      <br />+++ attendu/{selectedDiffFile || 'config.json'} (Critère Test)
                    </div>
                    <div className="text-slate-400">@@ -1,4 +1,4 @@</div>
                    <div className="text-slate-300">{'{'}</div>
                    <div className="text-emerald-400 bg-emerald-950/30 px-1 rounded">
                      +   "provider": "demo",
                    </div>
                    <div className="text-emerald-400 bg-emerald-950/30 px-1 rounded">
                      +   "active": true
                    </div>
                    <div className="text-slate-300">{'}'}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Dépliant Guide Mémo Vim */}
          {showVimGuide && (
            <div className="p-3 bg-slate-900/95 border border-indigo-500/40 rounded-xl space-y-2 animate-fade-in text-xs text-slate-300 shadow-xl">
              <div className="flex items-center justify-between font-bold text-indigo-300 text-xs">
                <span>Raccourcis Essentiels Vim (Éditeur Terminal)</span>
                <span className="text-[10px] text-slate-400 font-normal">Appuyez sur Échap pour revenir en mode commande</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-amber-400 font-bold">i</span> : Mode Insertion
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Pour saisir du texte</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-cyan-400 font-bold">Échap</span> : Mode Normal
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Pour taper des commandes</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-emerald-400 font-bold">:wq</span> + Entrée
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Sauvegarder & quitter</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-rose-400 font-bold">:q!</span> + Entrée
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Quitter sans enregistrer</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-purple-400 font-bold">dd</span> : Supprimer
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Efface la ligne courante</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-amber-400 font-bold">u</span> : Annuler (Undo)
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Annule la dernière modif</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-teal-400 font-bold">yy</span> & <span className="text-teal-400 font-bold">p</span>
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Copier et coller ligne</div>
                </div>
                <div className="p-2 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-slate-300 font-bold">/mot</span> : Chercher
                  <div className="text-[9px] text-slate-400 font-sans mt-0.5">Recherche dans le buffer</div>
                </div>
              </div>
            </div>
          )}

          {/* Terminal : xterm local ou simulateur interactif */}
          {!isRemote403 ? (
            <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
              <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                  <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                  <span className="text-xs font-mono text-slate-400 ml-2">bash terminal — localhost pty (Vim actif)</span>
                </div>
                <button
                  onClick={() => handleSendSnippet('clear')}
                  className="text-[10px] text-slate-500 hover:text-slate-300 font-mono"
                >
                  clear
                </button>
              </div>
              <div ref={terminalContainerRef} className="h-64 p-2" />
            </div>
          ) : (
            /* Simulateur interactif pour mode mobile / preview */
            <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
              <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-rose-500" />
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500" />
                  <span className="font-mono text-slate-400 ml-2">Console interactive Web / Mobile</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleOpenSimulatedVim('config.json')}
                    className="text-[10px] text-amber-400 hover:text-amber-300 font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30"
                  >
                    Éditeur Vim
                  </button>
                  <span className="text-[10px] text-slate-400 font-mono">Mode Simulateur</span>
                </div>
              </div>

              {simulatedVimOpen ? (
                /* Émulateur Vim interactif intégré */
                <div className="p-3 bg-slate-950 font-mono text-xs space-y-2 border-b border-slate-800">
                  <div className="flex items-center justify-between text-[11px] pb-1 border-b border-slate-800">
                    <span className="text-amber-400 font-bold">~ VIM 9.0 — "{simulatedVimFile}"</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-black ${
                        simulatedVimMode === 'INSERT'
                          ? 'bg-emerald-500 text-slate-950'
                          : 'bg-indigo-600 text-white'
                      }`}
                    >
                      -- {simulatedVimMode} --
                    </span>
                  </div>

                  <textarea
                    rows={6}
                    value={simulatedVimContent}
                    onChange={(e) => setSimulatedVimContent(e.target.value)}
                    onFocus={() => setSimulatedVimMode('INSERT')}
                    onBlur={() => setSimulatedVimMode('NORMAL')}
                    className="w-full bg-slate-900/90 border border-slate-800 p-2.5 rounded font-mono text-emerald-300 text-xs focus:outline-none focus:border-amber-500"
                    placeholder='{"provider": "demo", "active": true}'
                  />

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[10px] text-slate-400">
                      Tapez <code className="text-amber-400">:wq</code> pour enregistrer ou cliquez ci-contre.
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setSimulatedVimOpen(false)}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs cursor-pointer"
                      >
                        Annuler (:q!)
                      </button>
                      <button
                        onClick={handleSaveSimulatedVim}
                        className="px-3 py-1 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer flex items-center gap-1 shadow-md shadow-emerald-500/20"
                      >
                        <Check className="w-3.5 h-3.5" /> Enregistrer (:wq)
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-3 h-64 overflow-y-auto font-mono text-xs space-y-2">
                  {terminalHistory.map((item, idx) => (
                    <div key={idx} className="space-y-0.5">
                      <div className="text-emerald-400 flex items-center gap-1.5">
                        <span className="text-slate-500">$</span> {item.cmd}
                      </div>
                      <div className="text-slate-300 text-[11px] whitespace-pre-wrap pl-3">{item.out}</div>
                    </div>
                  ))}
                </div>
              )}

              <form onSubmit={handleSimulatedSubmit} className="p-2 bg-slate-900 border-t border-slate-800 flex gap-2">
                <input
                  type="text"
                  placeholder="Entrez une commande bash ou vim (ex: vim config.json, ls, cat config.json)..."
                  value={simulatedCmd}
                  onChange={(e) => setSimulatedCmd(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-700 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-500"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg bg-amber-500 text-slate-950 font-bold text-xs cursor-pointer"
                >
                  Exécuter
                </button>
              </form>
            </div>
          )}

          {/* Volet Tuteur IA rétractable */}
          {showTutor && (
            <div className="p-4 bg-purple-950/40 border border-purple-800/60 rounded-2xl space-y-3 animate-fade-in">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-purple-200 flex items-center gap-1.5">
                  <Bot className="w-4 h-4 text-purple-400" /> Tuteur Technique Qwen
                </span>
                <span className="text-[10px] text-purple-300 font-mono">Orientations sans spoilers</span>
              </div>

              <div className="max-h-40 overflow-y-auto space-y-2 text-xs">
                {tutorMessages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-xl ${
                      msg.role === 'user'
                        ? 'bg-purple-900/40 text-purple-100 ml-6 text-right'
                        : 'bg-slate-900/90 text-slate-200 mr-6 border border-purple-800/40'
                    }`}
                  >
                    {msg.text}
                  </div>
                ))}
                {tutorLoading && (
                  <div className="text-xs text-purple-300 flex items-center gap-1">
                    <RefreshCw className="w-3 h-3 animate-spin" /> Le tuteur réfléchit...
                  </div>
                )}
              </div>

              <form onSubmit={handleAskTutor} className="flex gap-2 pt-1">
                <input
                  type="text"
                  placeholder="Posez une question technique..."
                  value={tutorInput}
                  onChange={(e) => setTutorInput(e.target.value)}
                  className="flex-1 bg-slate-950 border border-purple-700/50 px-3 py-1.5 rounded-lg text-xs text-slate-100 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={tutorLoading}
                  className="p-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </div>
          )}

          {/* Actions : Vérification et Indices */}
          <div className="space-y-3">
            <div className="flex gap-2.5">
              <button
                onClick={handleCheckTp}
                disabled={checking}
                className="flex-1 py-3 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-extrabold text-xs flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 cursor-pointer transition-all"
              >
                {checking ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4" />
                )}
                <span>
                  {tpAlreadyDone
                    ? 'Tester à nouveau le TP (Déjà validé ✓)'
                    : 'Vérifier le TP (+80 XP)'}
                </span>
              </button>

              <button
                onClick={handleGetHint}
                disabled={hintLoading}
                className="py-3 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-bold text-amber-400 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
              >
                {hintLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <HintIcon className="w-3.5 h-3.5" />}
                <span>Indice {hintLevel} (-10 XP)</span>
              </button>
            </div>

            {/* Affichage des indices débloqués */}
            {hints.length > 0 && (
              <div className="space-y-2">
                {hints.map((h, i) => (
                  <div
                    key={i}
                    className="p-3 bg-amber-950/20 border border-amber-800/40 rounded-xl text-xs text-amber-200 leading-relaxed flex items-start gap-2.5"
                  >
                    <Sparkles className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold">Indice {i + 1} :</span> {h}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Résultat de vérification */}
            {checkResult && (
              <div
                className={`p-4 rounded-xl border text-xs leading-relaxed space-y-2 ${
                  checkResult.passed
                    ? 'bg-emerald-950/40 border-emerald-600 text-emerald-200'
                    : 'bg-rose-950/40 border-rose-600 text-rose-200'
                }`}
              >
                <div className="flex items-center justify-between font-bold text-sm">
                  <div className="flex items-center gap-2">
                    {checkResult.passed ? (
                      <>
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" /> Félicitations, TP validé avec succès !
                      </>
                    ) : (
                      <>
                        <XCircle className="w-5 h-5 text-rose-400" /> Échec de la vérification
                      </>
                    )}
                  </div>
                  {checkResult.passed && tpAlreadyDoneNotice && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-900 border border-emerald-500/40 text-emerald-300">
                      XP déjà attribué (1/1)
                    </span>
                  )}
                </div>

                {checkResult.passed && tpAlreadyDoneNotice && (
                  <p className="text-[11px] text-emerald-300/90 bg-emerald-950/60 p-2.5 rounded-lg border border-emerald-800/40">
                    ℹ️ <strong>Rappel :</strong> Les critères du TP sont validés. Comme ce TP a déjà été complété précédemment, les <strong>+80 XP</strong> ne sont accordés qu'une seule fois par exercice.
                  </p>
                )}

                {checkResult.passed && (
                  <div className="pt-2 flex items-center justify-between border-t border-emerald-800/40">
                    <span className="text-[11px] text-emerald-300">Procédure opérationnelle validée :</span>
                    <button
                      onClick={() => setShowRunbookModal(true)}
                      className="px-2.5 py-1 bg-emerald-900/60 hover:bg-emerald-800 border border-emerald-500/50 rounded-lg text-emerald-200 text-xs font-bold flex items-center gap-1.5 cursor-pointer transition-all"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Générer Runbook SOP Markdown</span>
                    </button>
                  </div>
                )}

                {checkResult.output && (
                  <pre className="p-3 bg-slate-950/80 rounded-lg font-mono text-[11px] overflow-x-auto text-slate-300 border border-slate-800">
                    {checkResult.output}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal Export Runbook SRE */}
      {showRunbookModal && (
        <RunbookExportModal
          lessonId={lessonId}
          title={lesson?.title}
          onClose={() => setShowRunbookModal(false)}
        />
      )}
    </div>
  );
};
