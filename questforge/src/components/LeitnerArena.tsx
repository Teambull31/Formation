import React, { useState, useEffect } from 'react';
import {
  Brain,
  CheckCircle2,
  XCircle,
  Sparkles,
  ArrowRight,
  BookOpen,
  Award,
  Layers,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, Question } from '../api';

interface LeitnerArenaProps {
  onClose: () => void;
  onSelectLesson: (lessonId: string) => void;
  onRefreshQuest: () => void;
}

const BOX_INTERVALS = ['1 jour', '2 jours', '4 jours', '7 jours', '14 jours'];

export const LeitnerArena: React.FC<LeitnerArenaProps> = ({
  onClose,
  onSelectLesson,
  onRefreshQuest,
}) => {
  const [loading, setLoading] = useState(true);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [boxesCount, setBoxesCount] = useState<number[]>([0, 0, 0, 0, 0]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [isAnswered, setIsAnswered] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sessionCompleted, setSessionCompleted] = useState(false);

  const loadReviews = async () => {
    setLoading(true);
    try {
      const res = await api.getReviews();
      setQuestions(res.due);
      setBoxesCount(res.boxesCount);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReviews();
  }, []);

  const currentQ = questions[currentIndex];

  const handleValidate = async () => {
    if (selectedOption === null || !currentQ) return;
    setSubmitting(true);

    const correct = selectedOption === 1; // standard demo correct option index
    setIsCorrect(correct);
    setIsAnswered(true);

    try {
      await api.answerReview(currentQ.id, correct);
      if (correct) {
        confetti({ particleCount: 40, spread: 60, origin: { y: 0.7 } });
      }
      onRefreshQuest();
    } catch {
      // Ignored
    } finally {
      setSubmitting(false);
    }
  };

  const handleNext = () => {
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOption(null);
      setIsAnswered(false);
    } else {
      setSessionCompleted(true);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full space-y-5 shadow-2xl relative overflow-hidden">
        {/* Glow background */}
        <div className="absolute top-0 right-0 w-48 h-48 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">Arène de Répétition Espacée</h2>
              <p className="text-[10px] text-slate-400">Système Leitner : 5 boîtes de mémorisation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Visualisation de la pyramide Leitner */}
        <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-purple-400" /> Pyramide des 5 Boîtes
            </span>
            <span className="text-[10px] font-mono text-purple-300">+15 XP par notion consolidée</span>
          </div>

          <div className="grid grid-cols-5 gap-1.5 pt-1">
            {BOX_INTERVALS.map((label, idx) => (
              <div
                key={idx}
                className={`p-2 rounded-xl border text-center transition-all ${
                  currentQ && currentQ.box === idx
                    ? 'bg-purple-950/60 border-purple-500/60 shadow-md shadow-purple-500/20'
                    : 'bg-slate-900/60 border-slate-800/60'
                }`}
              >
                <div className="text-[10px] font-mono text-slate-400">B{idx + 1}</div>
                <div className="text-xs font-black text-slate-100 my-0.5 font-mono">
                  {boxesCount[idx] || 0}
                </div>
                <div className="text-[9px] text-slate-500 leading-tight">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Contenu principal de la révision */}
        {loading ? (
          <div className="py-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-purple-400" />
            <span>Chargement des questions dues...</span>
          </div>
        ) : sessionCompleted || questions.length === 0 ? (
          <div className="py-8 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center border border-emerald-500/30">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-black text-slate-100">Toutes les révisions sont terminées !</h3>
              <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
                Aucune notion n'est en souffrance aujourd'hui. Vos boîtes de Leitner sont à jour.
              </p>
            </div>
            <button
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs cursor-pointer transition-all shadow-lg shadow-purple-600/20"
            >
              Fermer et retourner à la quête
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-between items-center text-xs font-mono text-slate-400">
              <span>
                Notion {currentIndex + 1} sur {questions.length}
              </span>
              <span className="text-purple-400">Boîte actuelle : {currentQ.box !== undefined ? currentQ.box + 1 : 1}</span>
            </div>

            <div className="p-4 bg-slate-950/80 rounded-2xl border border-slate-800 space-y-3">
              <h4 className="text-sm font-bold text-slate-100 leading-snug">{currentQ.text}</h4>

              <div className="space-y-2 pt-1">
                {currentQ.options.map((opt, oIdx) => {
                  const isSelected = selectedOption === oIdx;
                  return (
                    <div
                      key={oIdx}
                      onClick={() => !isAnswered && setSelectedOption(oIdx)}
                      className={`p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-start gap-2.5 ${
                        isSelected
                          ? 'bg-purple-950/40 border-purple-500 text-purple-100'
                          : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <input
                        type="radio"
                        checked={isSelected}
                        onChange={() => {}}
                        className="mt-0.5 text-purple-500"
                      />
                      <span>{opt}</span>
                    </div>
                  );
                })}
              </div>

              {!isAnswered ? (
                <button
                  onClick={handleValidate}
                  disabled={selectedOption === null || submitting}
                  className="w-full mt-2 py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white font-bold text-xs cursor-pointer transition-all"
                >
                  {submitting ? 'Vérification...' : 'Valider la réponse'}
                </button>
              ) : (
                <div
                  className={`p-3.5 rounded-xl border text-xs leading-relaxed space-y-2 mt-2 ${
                    isCorrect
                      ? 'bg-emerald-950/40 border-emerald-600 text-emerald-200'
                      : 'bg-rose-950/40 border-rose-600 text-rose-200'
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold text-sm">
                    {isCorrect ? (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Bonne réponse (+15 XP) !
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-rose-400" /> Erreur : rétrogradé en Boîte 1
                      </>
                    )}
                  </div>
                  <p>{currentQ.explain}</p>

                  <div className="flex justify-between items-center pt-2 border-t border-slate-800">
                    {currentQ.remedial_lesson_id && (
                      <button
                        onClick={() => {
                          onSelectLesson(currentQ.remedial_lesson_id!);
                          onClose();
                        }}
                        className="text-amber-400 hover:text-amber-300 font-semibold text-[11px] underline flex items-center gap-1 cursor-pointer"
                      >
                        <BookOpen className="w-3 h-3" /> Ouvrir la fiche de cours
                      </button>
                    )}
                    <button
                      onClick={handleNext}
                      className="ml-auto px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs flex items-center gap-1 cursor-pointer"
                    >
                      <span>Suivant</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
