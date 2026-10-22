import React, { useState, useEffect, useRef } from 'react';
import {
  Headphones,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Volume2,
  CheckCircle2,
  Zap,
  Radio,
  Clock,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, LessonData } from '../api';

interface PodcastPlayerProps {
  lesson: LessonData;
  onClose: () => void;
  onRefreshQuest: () => void;
}

export const PodcastPlayer: React.FC<PodcastPlayerProps> = ({
  lesson,
  onClose,
  onRefreshQuest,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [flashMode, setFlashMode] = useState(true);
  const [speed, setSpeed] = useState<1 | 1.5 | 2>(1);
  const [stage, setStage] = useState<'intro' | 'summary' | 'qcm_quiz' | 'qcm_answer' | 'finished'>('intro');
  const [completed, setCompleted] = useState(false);

  // Web Speech API synthesiser ref
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis;
    }
    return () => {
      if (synthRef.current) synthRef.current.cancel();
    };
  }, []);

  const speakText = (text: string, onEnd?: () => void) => {
    if (!synthRef.current) return;
    synthRef.current.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'fr-FR';
    utterance.rate = speed;
    utterance.onend = () => {
      if (onEnd) onEnd();
    };
    utteranceRef.current = utterance;
    synthRef.current.speak(utterance);
    setIsPlaying(true);
  };

  const startPodcastFlow = () => {
    if (flashMode) {
      setStage('summary');
      const summary =
        lesson.summary_audio_text ||
        `Résumé flash de la leçon ${lesson.title} : découpler la logique métier du fournisseur. Aucun secret en dur. Validez toujours les entrées avant traitement.`;
      speakText(summary, () => {
        handleComplete();
      });
    } else {
      // Full podcast
      setStage('summary');
      const intro = `Bienvenue dans votre podcast technique QuestForge. Nous étudions aujourd'hui : ${lesson.title}.`;
      speakText(intro, () => {
        setStage('qcm_quiz');
        const q = lesson.qcm[0];
        const qText = q
          ? `Question de contrôle : ${q.text}. Option 1 : ${q.options[0]}. Option 2 : ${q.options[1]}. Prenez un instant pour réfléchir.`
          : 'Poursuivons vers la validation.';
        speakText(qText, () => {
          setTimeout(() => {
            setStage('qcm_answer');
            const answerText = q
              ? `La bonne réponse était l'option 2. ${q.explain}`
              : 'Fin de la session audio.';
            speakText(answerText, () => {
              handleComplete();
            });
          }, 3500);
        });
      });
    }
  };

  const handleTogglePlay = () => {
    if (!synthRef.current) return;
    if (isPlaying) {
      synthRef.current.pause();
      setIsPlaying(false);
    } else {
      if (synthRef.current.paused) {
        synthRef.current.resume();
        setIsPlaying(true);
      } else {
        startPodcastFlow();
      }
    }
  };

  const handleComplete = async () => {
    setIsPlaying(false);
    setStage('finished');
    setCompleted(true);
    confetti({ particleCount: 50, spread: 70, origin: { y: 0.7 } });
    try {
      await api.completePodcastSession();
      onRefreshQuest();
    } catch {}
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full space-y-6 shadow-2xl relative overflow-hidden text-center">
        {/* Glow */}
        <div className="absolute top-0 right-0 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-amber-400 animate-pulse" />
            <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">
              QuestForge Trajet & Podcast
            </span>
          </div>
          <button
            onClick={() => {
              if (synthRef.current) synthRef.current.cancel();
              onClose();
            }}
            className="w-7 h-7 rounded-lg bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Pochette audio animée */}
        <div className="w-24 h-24 rounded-3xl bg-gradient-to-tr from-amber-600 via-orange-500 to-amber-300 flex items-center justify-center mx-auto shadow-xl shadow-amber-500/20 relative">
          <Headphones className="w-12 h-12 text-slate-950" />
          {isPlaying && (
            <div className="absolute -bottom-2 px-2.5 py-0.5 rounded-full bg-slate-950 text-amber-400 font-mono text-[9px] font-bold border border-amber-500/40">
              AUDIO ACTIF
            </div>
          )}
        </div>

        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2.5 py-0.5 rounded-md border border-amber-500/20">
            {lesson.module_title}
          </span>
          <h3 className="text-base font-black text-slate-100 mt-1">{lesson.title}</h3>
          <p className="text-xs text-slate-400 mt-1">
            {stage === 'intro' && 'Prêt pour une écoute mains libres ?'}
            {stage === 'summary' && 'Écoute de la synthèse essentielle...'}
            {stage === 'qcm_quiz' && 'Question de quiz posée à voix haute...'}
            {stage === 'qcm_answer' && 'Débriefing et explication technique...'}
            {stage === 'finished' && 'Séance terminée avec succès ! (+35 XP)'}
          </p>
        </div>

        {/* Ondes sonores visuelles */}
        <div className="flex items-center justify-center gap-1.5 h-8">
          {[20, 45, 75, 90, 50, 30, 85, 60, 40].map((h, i) => (
            <div
              key={i}
              className={`w-1 rounded-full bg-amber-400 transition-all duration-300 ${
                isPlaying ? 'opacity-100' : 'opacity-30'
              }`}
              style={{ height: isPlaying ? `${h}%` : '20%' }}
            />
          ))}
        </div>

        {/* Sélection Mode : Flash 45s vs Podcast Complet */}
        <div className="flex bg-slate-950 p-1.5 rounded-2xl border border-slate-800 text-xs">
          <button
            onClick={() => setFlashMode(true)}
            className={`flex-1 py-1.5 rounded-xl font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
              flashMode
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5" /> Flash 45s
          </button>
          <button
            onClick={() => setFlashMode(false)}
            className={`flex-1 py-1.5 rounded-xl font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
              !flashMode
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" /> Podcast Complet (Quiz inclus)
          </button>
        </div>

        {/* Contrôles Audio */}
        <div className="flex items-center justify-center gap-4">
          <div className="flex bg-slate-950 px-2 py-1 rounded-xl border border-slate-800">
            {([1, 1.5, 2] as const).map((r) => (
              <button
                key={r}
                onClick={() => setSpeed(r)}
                className={`text-[10px] font-mono px-2 py-0.5 rounded cursor-pointer ${
                  speed === r ? 'bg-amber-500 text-slate-950 font-bold' : 'text-slate-400'
                }`}
              >
                {r}x
              </button>
            ))}
          </div>

          <button
            onClick={handleTogglePlay}
            className="w-14 h-14 rounded-2xl bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center justify-center shadow-xl shadow-amber-500/30 cursor-pointer transition-all"
          >
            {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current ml-1" />}
          </button>

          <button
            onClick={() => {
              if (synthRef.current) synthRef.current.cancel();
              setIsPlaying(false);
              setStage('intro');
            }}
            className="p-2.5 rounded-xl bg-slate-800 text-slate-400 hover:text-white cursor-pointer"
            title="Recommencer"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {completed && (
          <div className="p-3 bg-emerald-950/40 border border-emerald-600/50 rounded-xl text-xs text-emerald-200 flex items-center gap-2 justify-center animate-fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Séance podcast validée ! +35 XP accordés.</span>
          </div>
        )}
      </div>
    </div>
  );
};
