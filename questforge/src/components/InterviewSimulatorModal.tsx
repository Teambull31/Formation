import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  Play,
  Pause,
  RotateCcw,
  Volume2,
  CheckCircle2,
  X,
  Award,
  Sparkles,
  ChevronRight,
  Eye,
  EyeOff,
  HelpCircle,
  Briefcase,
} from 'lucide-react';
import { api, InterviewQuestion } from '../api';

interface InterviewSimulatorModalProps {
  onClose: () => void;
}

export const InterviewSimulatorModal: React.FC<InterviewSimulatorModalProps> = ({
  onClose,
}) => {
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  // Timer state
  const [timeLeft, setTimeLeft] = useState(90);
  const [timerRunning, setTimerRunning] = useState(false);
  const timerRef = useRef<any>(null);

  // User checklist of keywords mentioned
  const [checkedKeywords, setCheckedKeywords] = useState<Record<string, boolean>>({});
  const [showAnswer, setShowAnswer] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    api
      .getInterviewQuestions()
      .then((data) => {
        setQuestions(data.questions);
        if (data.questions.length > 0) {
          setTimeLeft(data.questions[0].timeLimitSeconds);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const curQ = questions[currentIndex];

  useEffect(() => {
    if (timerRunning) {
      timerRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            clearInterval(timerRef.current);
            setTimerRunning(false);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [timerRunning]);

  const handleNextQuestion = () => {
    const nextIdx = (currentIndex + 1) % questions.length;
    setCurrentIndex(nextIdx);
    setTimeLeft(questions[nextIdx]?.timeLimitSeconds || 90);
    setTimerRunning(false);
    setCheckedKeywords({});
    setShowAnswer(false);
  };

  const toggleTimer = () => {
    setTimerRunning((prev) => !prev);
  };

  const handleResetTimer = () => {
    setTimerRunning(false);
    setTimeLeft(curQ?.timeLimitSeconds || 90);
  };

  const handleSpeakQuestion = () => {
    if (!curQ) return;
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(
        curQ.audioPrompt || curQ.question
      );
      utterance.lang = 'fr-FR';
      utterance.rate = 1.0;
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(utterance);
    } else {
      alert("La synthèse vocale n'est pas supportée par votre navigateur.");
    }
  };

  const toggleKeyword = (kw: string) => {
    setCheckedKeywords((prev) => ({
      ...prev,
      [kw]: !prev[kw],
    }));
  };

  const checkedCount = Object.values(checkedKeywords).filter(Boolean).length;
  const totalKeywords = curQ?.expectedKeywords.length || 1;
  const completionPct = Math.round((checkedCount / totalKeywords) * 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
              <Mic className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-100">
                  Simulateur d'Entretien Technique Oral (SRE & DevOps)
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40">
                  {curQ?.role || 'Senior SRE'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Structurez votre réponse à voix haute sous contrainte de temps comme face à un Lead Architecte.
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

        {/* Content */}
        {curQ && (
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-950/50">
            {/* Question Card */}
            <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 to-rose-950/20 border border-rose-500/30 space-y-3 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-rose-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Briefcase className="w-3.5 h-3.5" /> Question #{currentIndex + 1} / {questions.length}
                </span>

                <button
                  onClick={handleSpeakQuestion}
                  className={`px-2.5 py-1 rounded-xl text-xs font-semibold flex items-center gap-1 cursor-pointer transition-all ${
                    speaking
                      ? 'bg-rose-500 text-slate-950 animate-pulse'
                      : 'bg-slate-800 hover:bg-slate-700 text-rose-300 border border-rose-500/30'
                  }`}
                  title="Écouter la question posée oralement"
                >
                  <Volume2 className="w-3.5 h-3.5" />
                  <span>{speaking ? 'Lecture en cours...' : 'Écouter'}</span>
                </button>
              </div>

              <h3 className="text-sm sm:text-base font-extrabold text-slate-100 leading-snug">
                « {curQ.question} »
              </h3>

              {/* Timer Bar */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
                <div className="flex items-center gap-3">
                  <div
                    className={`text-lg font-black font-mono px-3 py-1 rounded-xl border ${
                      timeLeft <= 15
                        ? 'bg-rose-500/20 border-rose-500 text-rose-300 animate-pulse'
                        : 'bg-slate-900 border-slate-800 text-amber-300'
                    }`}
                  >
                    ⏱️ {Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, '0')}
                  </div>

                  <button
                    onClick={toggleTimer}
                    className={`px-3 py-1.5 rounded-xl font-bold text-xs flex items-center gap-1.5 cursor-pointer transition-all ${
                      timerRunning
                        ? 'bg-amber-500 text-slate-950'
                        : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                    }`}
                  >
                    {timerRunning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                    <span>{timerRunning ? 'Pause' : 'Démarrer chrono'}</span>
                  </button>

                  <button
                    onClick={handleResetTimer}
                    className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 cursor-pointer"
                    title="Réinitialiser"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                </div>

                <button
                  onClick={handleNextQuestion}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1 cursor-pointer transition-all"
                >
                  <span>Question Suivante</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Checklist of Expected Technical Keywords */}
            <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-200">
                    Mots-clés & Concepts attendus par le recruteur
                  </h4>
                  <p className="text-[11px] text-slate-400">
                    Cochez les termes que vous avez naturellement abordés pendant votre tirade orale.
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs font-black font-mono text-emerald-400">
                    {checkedCount} / {totalKeywords} ({completionPct}%)
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                {curQ.expectedKeywords.map((kw) => {
                  const isChecked = Boolean(checkedKeywords[kw]);
                  return (
                    <button
                      key={kw}
                      onClick={() => toggleKeyword(kw)}
                      className={`px-3 py-1.5 rounded-xl font-mono text-xs flex items-center gap-2 cursor-pointer transition-all border ${
                        isChecked
                          ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300 font-bold'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <CheckCircle2
                        className={`w-3.5 h-3.5 ${
                          isChecked ? 'text-emerald-400' : 'text-slate-600'
                        }`}
                      />
                      <span>{kw}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Evaluation Rubric & Sample Answer Toggle */}
            <div className="space-y-3">
              <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-2">
                <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-amber-400" /> Grille de Notation Recruteur (100 pts)
                </h4>
                <div className="space-y-1.5 pt-1">
                  {curQ.evaluationRubric.map((r, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between text-xs p-2 rounded-xl bg-slate-950/50 border border-slate-800/80"
                    >
                      <span className="text-slate-300">{r.criteria}</span>
                      <span className="font-mono font-bold text-amber-400 text-[11px] flex-shrink-0 ml-2">
                        +{r.points} pts
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Reveal Senior SRE Sample Answer */}
              <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-3">
                <button
                  onClick={() => setShowAnswer(!showAnswer)}
                  className="w-full py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs flex items-center justify-between cursor-pointer transition-all"
                >
                  <span className="flex items-center gap-2">
                    {showAnswer ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-cyan-400" />}
                    <span>{showAnswer ? 'Masquer la réponse idéale' : 'Voir la réponse modèle (Exemple Senior SRE)'}</span>
                  </span>
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                </button>

                {showAnswer && (
                  <div className="p-3.5 bg-slate-950/80 border border-cyan-500/30 rounded-xl space-y-2 animate-fade-in text-xs text-slate-300 leading-relaxed font-sans">
                    <div className="font-bold text-cyan-300 text-[11px]">
                      Réponse type d'un Architecte Senior :
                    </div>
                    <p className="whitespace-pre-wrap">{curQ.seniorSampleAnswer}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-3 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
          <span>Pratiquez régulièrement pour développer votre fluidité technique lors des entretiens.</span>
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
