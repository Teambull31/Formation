import React, { useState } from 'react';
import { Sparkles, MessageSquare, ChevronUp, ChevronDown, Award } from 'lucide-react';
import { InventoryItem } from '../api';

interface CompanionBarProps {
  companion?: InventoryItem;
  onOpenTeam: () => void;
}

const QUOTES: Record<string, string[]> = {
  char_hopper: [
    "« La phrase la plus dangereuse de la langue est : Nous avons toujours fait ainsi. »",
    "« Un premier bug trouvé aujourd'hui ? Gardez toujours votre papillon de nuit sous la main ! »",
    "« Vos scripts de TP sont prometteurs. N'hésitez pas à poser une question au tuteur. »",
  ],
  char_ada: [
    "« Ce moteur analytique tisse des motifs algébriques tout comme le métier Jacquard tisse des fleurs. »",
    "« La rigueur de votre architecture MailSource impressionne ! »",
    "« N'oubliez pas : chaque bug résolu est un pas de plus vers l'abstraction parfaite. »",
  ],
  char_turing: [
    "« Une machine peut-elle penser ? Elle peut assurément vous aider à réussir vos déploiements ! »",
    "« Analysez les sorties stderr comme un message chiffré : la réponse y est toujours. »",
  ],
  char_torvalds: [
    "« Parler ne coûte rien. Montrez-moi le code ! »",
    "« Un bon développeur n'a pas peur de la ligne de commande bash. »",
  ],
};

export const CompanionBar: React.FC<CompanionBarProps> = ({ companion, onOpenTeam }) => {
  const [expanded, setExpanded] = useState(false);
  const [quoteIndex, setQuoteIndex] = useState(0);

  if (!companion) return null;

  const quotes = QUOTES[companion.item_id] || [
    "« Gardez le cap ! Chaque quête quotidienne consolide votre expertise. »",
  ];
  const currentQuote = quotes[quoteIndex % quotes.length];

  const handleNextQuote = () => {
    setQuoteIndex((prev) => prev + 1);
  };

  return (
    <div className="fixed bottom-16 right-4 z-40 max-w-xs transition-all">
      <div className="bg-slate-900/95 border border-amber-500/40 rounded-2xl p-3 shadow-2xl backdrop-blur-md space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div
            onClick={handleNextQuote}
            className="flex items-center gap-2 cursor-pointer group"
            title="Cliquer pour une autre pensée"
          >
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center text-lg border border-amber-500/30 group-hover:scale-110 transition-transform">
              {companion.avatar || '👤'}
            </div>
            <div>
              <div className="text-xs font-bold text-slate-100 flex items-center gap-1">
                <span>{companion.name}</span>
                <span className="text-[9px] text-amber-400 font-mono">Compagnon</span>
              </div>
              <p className="text-[10px] text-slate-400 line-clamp-1">{companion.perk?.name || 'Mascotte active'}</p>
            </div>
          </div>

          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 rounded-lg bg-slate-800 text-slate-400 hover:text-white cursor-pointer"
          >
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>

        {expanded && (
          <div className="pt-2 border-t border-slate-800 space-y-2 animate-fade-in text-[11px]">
            <p className="text-slate-300 italic leading-relaxed">{currentQuote}</p>

            {companion.perk && (
              <div className="p-2 bg-amber-950/30 border border-amber-600/30 rounded-xl text-[10px] text-amber-200 flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-amber-400 flex-shrink-0" />
                <span>
                  <strong>Perk Actif :</strong> {companion.perk.description}
                </span>
              </div>
            )}

            <button
              onClick={onOpenTeam}
              className="w-full py-1 text-[10px] font-semibold text-slate-400 hover:text-amber-400 text-center cursor-pointer"
            >
              Changer de compagnon dans l'Équipe →
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
