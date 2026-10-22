import React, { useState, useEffect, useRef } from 'react';
import {
  Volume2,
  VolumeX,
  Play,
  Pause,
  Headphones,
  Sliders,
  Sparkles,
  BookOpen,
  Send,
  CheckCircle2,
  HelpCircle,
  FileText,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { api, FeynmanMemo } from '../api';

interface SoundtrackProps {
  onClose?: () => void;
  onRefreshQuest?: () => void;
}

type SoundPreset = 'datacenter' | 'keyboard' | 'binaural';

export const SoundtrackPlayer: React.FC<SoundtrackProps> = ({ onClose, onRefreshQuest }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [preset, setPreset] = useState<SoundPreset>('datacenter');
  const [volume, setVolume] = useState(0.25);

  // Feynman Memo state
  const [showFeynman, setShowFeynman] = useState(false);
  const [conceptTitle, setConceptTitle] = useState('');
  const [explanation, setExplanation] = useState('');
  const [analogies, setAnalogies] = useState('');
  const [savedMemos, setSavedMemos] = useState<FeynmanMemo[]>([]);
  const [savingMemo, setSavingMemo] = useState(false);

  // Web Audio Context refs
  const audioCtxRef = useRef<AudioContext | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const sourceNodeRef = useRef<AudioNode | null>(null);

  useEffect(() => {
    loadMemos();
    return () => {
      stopAudio();
    };
  }, []);

  const loadMemos = async () => {
    try {
      const memos = await api.getFeynmanMemos();
      setSavedMemos(memos);
    } catch {}
  };

  const initAudio = () => {
    if (!audioCtxRef.current) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      audioCtxRef.current = new AudioCtx();
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
  };

  const startPreset = (selectedPreset: SoundPreset) => {
    initAudio();
    stopAudio();

    const ctx = audioCtxRef.current;
    if (!ctx) return;

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.connect(ctx.destination);
    gainNodeRef.current = gain;

    if (selectedPreset === 'datacenter') {
      // Pink / Brown noise simulation for server fans
      const bufferSize = ctx.sampleRate * 2;
      const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      let lastOut = 0.0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        output[i] = (lastOut + 0.02 * white) / 1.02;
        lastOut = output[i];
        output[i] *= 2.5; // Gain compensation
      }

      const whiteNoise = ctx.createBufferSource();
      whiteNoise.buffer = noiseBuffer;
      whiteNoise.loop = true;

      // Lowpass filter simulating fan humming enclosure
      const filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(420, ctx.currentTime);

      whiteNoise.connect(filter);
      filter.connect(gain);
      whiteNoise.start();
      sourceNodeRef.current = whiteNoise;
    } else if (selectedPreset === 'binaural') {
      // 432Hz focus frequency
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      osc1.type = 'sine';
      osc2.type = 'sine';
      osc1.frequency.setValueAtTime(216, ctx.currentTime);
      osc2.frequency.setValueAtTime(220, ctx.currentTime);

      const panner1 = ctx.createStereoPanner ? ctx.createStereoPanner() : null;
      if (panner1) panner1.pan.value = -0.8;

      osc1.connect(gain);
      osc2.connect(gain);
      osc1.start();
      osc2.start();
      sourceNodeRef.current = osc1;
    } else if (selectedPreset === 'keyboard') {
      // Calming low rumble with rhythm
      const osc = ctx.createOscillator();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(110, ctx.currentTime);
      osc.connect(gain);
      osc.start();
      sourceNodeRef.current = osc;
    }

    setIsPlaying(true);
  };

  const stopAudio = () => {
    if (sourceNodeRef.current) {
      try {
        (sourceNodeRef.current as any).stop?.();
      } catch {}
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    setIsPlaying(false);
  };

  const togglePlay = () => {
    if (isPlaying) {
      stopAudio();
    } else {
      startPreset(preset);
    }
  };

  const handleVolumeChange = (newVol: number) => {
    setVolume(newVol);
    if (gainNodeRef.current && audioCtxRef.current) {
      gainNodeRef.current.gain.setValueAtTime(newVol, audioCtxRef.current.currentTime);
    }
  };

  const handlePresetSelect = (p: SoundPreset) => {
    setPreset(p);
    if (isPlaying) {
      startPreset(p);
    }
  };

  const handleSaveFeynman = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conceptTitle.trim() || !explanation.trim()) return;

    setSavingMemo(true);
    try {
      const saved = await api.saveFeynmanMemo({
        lessonId: 'general',
        conceptTitle: conceptTitle.trim(),
        explanation: explanation.trim(),
        analogies: analogies.trim(),
      });
      setSavedMemos((prev) => [saved, ...prev]);
      setConceptTitle('');
      setExplanation('');
      setAnalogies('');
      confetti({ particleCount: 50, spread: 50 });
      if (onRefreshQuest) onRefreshQuest();
    } finally {
      setSavingMemo(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="bg-slate-950 border border-teal-500/30 rounded-3xl max-w-xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl text-slate-100 animate-scale-up">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-teal-500/20 text-teal-400 flex items-center justify-center border border-teal-500/30">
              <Headphones className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-100">Ambiance Datacenter & Méthode Feynman</h2>
              <p className="text-[10px] text-slate-400">Concentration acoustique & auto-explication</p>
            </div>
          </div>

          {onClose && (
            <button
              onClick={() => {
                stopAudio();
                onClose();
              }}
              className="w-7 h-7 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs cursor-pointer"
            >
              ✕
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-5 space-y-5 flex-1">
          {/* Sound Controls Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300">Générateur d'Ambiance Synthétisé</span>
              <button
                onClick={togglePlay}
                className={`px-3 py-1.5 rounded-xl font-bold text-xs flex items-center gap-1.5 cursor-pointer shadow-md transition-all ${
                  isPlaying
                    ? 'bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20'
                    : 'bg-teal-500 hover:bg-teal-400 text-slate-950 shadow-teal-500/20'
                }`}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{isPlaying ? 'Couper le son' : 'Activer l\'Ambiance'}</span>
              </button>
            </div>

            {/* Presets */}
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => handlePresetSelect('datacenter')}
                className={`p-2.5 rounded-xl text-xs font-semibold border text-center cursor-pointer transition-all ${
                  preset === 'datacenter'
                    ? 'bg-teal-950/40 border-teal-500/60 text-teal-200'
                    : 'bg-slate-950/70 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <div className="text-base mb-0.5">🖥️</div>
                <div className="font-bold text-[11px]">Salle Serveurs</div>
                <div className="text-[9px] text-slate-400">Ronronnement fans</div>
              </button>

              <button
                onClick={() => handlePresetSelect('binaural')}
                className={`p-2.5 rounded-xl text-xs font-semibold border text-center cursor-pointer transition-all ${
                  preset === 'binaural'
                    ? 'bg-teal-950/40 border-teal-500/60 text-teal-200'
                    : 'bg-slate-950/70 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <div className="text-base mb-0.5">🧘</div>
                <div className="font-bold text-[11px]">Onde Alpha</div>
                <div className="text-[9px] text-slate-400">Binaural 432 Hz</div>
              </button>

              <button
                onClick={() => handlePresetSelect('keyboard')}
                className={`p-2.5 rounded-xl text-xs font-semibold border text-center cursor-pointer transition-all ${
                  preset === 'keyboard'
                    ? 'bg-teal-950/40 border-teal-500/60 text-teal-200'
                    : 'bg-slate-950/70 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <div className="text-base mb-0.5">⌨️</div>
                <div className="font-bold text-[11px]">Lo-Fi Rumble</div>
                <div className="text-[9px] text-slate-400">Basse feutrée</div>
              </button>
            </div>

            {/* Volume slider */}
            <div className="flex items-center gap-3 pt-1">
              <span className="text-[10px] text-slate-400 font-mono">Volume :</span>
              <input
                type="range"
                min="0.05"
                max="0.8"
                step="0.05"
                value={volume}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                className="flex-1 accent-teal-400 h-1.5 bg-slate-950 rounded-lg cursor-pointer"
              />
              <span className="text-[10px] font-mono text-slate-300 w-8 text-right">
                {Math.round(volume * 100)}%
              </span>
            </div>
          </div>

          {/* Section Méthode Feynman */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold text-slate-100">Méthode Feynman : Reformulation Personnelle</h3>
              </div>
              <button
                onClick={() => setShowFeynman(!showFeynman)}
                className="text-[11px] text-amber-400 hover:underline cursor-pointer font-semibold"
              >
                {showFeynman ? 'Masquer' : '+ Rédiger un Mémo (+40 XP)'}
              </button>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Pour ancrer durablement une notion technique, formulez-la avec vos propres mots en évitant le jargon et en utilisant une analogie du quotidien.
            </p>

            {showFeynman && (
              <form onSubmit={handleSaveFeynman} className="space-y-3 pt-2 animate-fade-in">
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Concept à vulgariser :
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Sonde de Liveness Kubernetes, Ingress NGINX..."
                    value={conceptTitle}
                    onChange={(e) => setConceptTitle(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Explication vulgarisée (comme à un enfant de 10 ans) :
                  </label>
                  <textarea
                    required
                    rows={2}
                    placeholder="Pourquoi cette notion existe et comment elle fonctionne..."
                    value={explanation}
                    onChange={(e) => setExplanation(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Analogie concrète :
                  </label>
                  <input
                    type="text"
                    placeholder="Ex: C'est comme le disjoncteur différentiel d'un tableau électrique..."
                    value={analogies}
                    onChange={(e) => setAnalogies(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <button
                  type="submit"
                  disabled={savingMemo}
                  className="w-full py-2 bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 font-bold text-xs rounded-xl flex items-center justify-center gap-1.5 cursor-pointer shadow-md shadow-amber-500/20"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Enregistrer mon Mémo (+40 XP)</span>
                </button>
              </form>
            )}

            {/* List of saved memos */}
            {savedMemos.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Vos Mémos Mémorisés ({savedMemos.length}) :
                </span>
                <div className="space-y-2 max-h-36 overflow-y-auto">
                  {savedMemos.map((m) => (
                    <div key={m.id} className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-xl space-y-1 text-xs">
                      <div className="font-bold text-amber-300">{m.conceptTitle}</div>
                      <p className="text-slate-300 text-[11px] leading-relaxed">{m.explanation}</p>
                      {m.analogies && (
                        <div className="text-[10px] text-teal-300 italic">💡 Analogie : {m.analogies}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
