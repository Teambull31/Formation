import React, { useState } from 'react';
import {
  Palette,
  X,
  Check,
  Sparkles,
  Terminal,
  Shield,
  Monitor,
} from 'lucide-react';

interface ThemeSelectorModalProps {
  currentTheme: string;
  onSelectTheme: (themeId: string) => void;
  onClose: () => void;
}

interface ThemeItem {
  id: string;
  name: string;
  tagline: string;
  bgHex: string;
  cardHex: string;
  accentHex: string;
  accentName: string;
  previewPrompt: string;
}

const THEMES: ThemeItem[] = [
  {
    id: 'default',
    name: 'SRE Carbon Pro (Défaut)',
    tagline: 'Standard moderne sobre pour ingénieurs de production',
    bgHex: '#020617',
    cardHex: '#0f172a',
    accentHex: '#f59e0b',
    accentName: 'Ambre Gold',
    previewPrompt: 'root@sre-bastion:~$ oci ce cluster list --status ACTIVE',
  },
  {
    id: 'cyberpunk',
    name: 'OCI Cyberpunk Neon',
    tagline: 'Néons ultraviolets et cyan électrique pour astreintes nocturnes',
    bgHex: '#0c0814',
    cardHex: '#181126',
    accentHex: '#06b6d4',
    accentName: 'Cyan Électrique & Magenta',
    previewPrompt: 'cyber@night-city:~$ kubectl get pods -n war-room --watch',
  },
  {
    id: 'matrix',
    name: 'Matrix Phosphor Green',
    tagline: 'Terminal vert CRT phosphorescent façon console VT100',
    bgHex: '#040d06',
    cardHex: '#0a1a0d',
    accentHex: '#22c55e',
    accentName: 'Phosphore 550nm',
    previewPrompt: 'neo@zion-gateway:~$ tcpdump -nnvv -i eth0 port 443',
  },
  {
    id: 'dracula',
    name: 'Dracula Mystic Dark',
    tagline: 'Pourpre gothique et contrastes doux pour reposer les yeux',
    bgHex: '#14141e',
    cardHex: '#1e1f2e',
    accentHex: '#bd93f9',
    accentName: 'Violet & Rose Pastel',
    previewPrompt: 'dracula@castle:~$ journalctl -u coredns.service -f',
  },
  {
    id: 'nord',
    name: 'Nord Datacenter Arctic',
    tagline: 'Palette arctique scandinave épurée et rafraîchissante',
    bgHex: '#0b121a',
    cardHex: '#14202d',
    accentHex: '#38bdf8',
    accentName: 'Bleu Glacier & Ardoise',
    previewPrompt: 'nord@fjord-node01:~$ sar -u -r 1 5',
  },
  {
    id: 'amber',
    name: 'Vintage Amber CRT',
    tagline: 'Légende des mainframes UNIX ambrés des années 1980',
    bgHex: '#140d04',
    cardHex: '#241708',
    accentHex: '#fbbf24',
    accentName: 'Ambre Cathodique',
    previewPrompt: 'operator@pdp11:~$ cat /etc/resolv.conf',
  },
  {
    id: 'tokyonight',
    name: 'Tokyo Night Storm',
    tagline: 'Ambiance métropole pluvieuse avec accents bleu saphir',
    bgHex: '#0f141c',
    cardHex: '#192333',
    accentHex: '#818cf8',
    accentName: 'Saphir & Lavande',
    previewPrompt: 'tokyo@shibuya-core:~$ envoy -c envoy.yaml --mode validate',
  },
];

export const ThemeSelectorModal: React.FC<ThemeSelectorModalProps> = ({
  currentTheme,
  onSelectTheme,
  onClose,
}) => {
  const [selectedTheme, setSelectedTheme] = useState<string>(currentTheme || 'default');

  const handleApply = (themeId: string) => {
    setSelectedTheme(themeId);
    onSelectTheme(themeId);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Palette className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-black text-slate-100">
                  Thèmes Hacker & Terminal OCI
                </h2>
                <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  PERSONNALISATION TOTALE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Changez l'ambiance visuelle globale et les couleurs de vos sessions de débug
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-2 rounded-xl hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Theme Grid */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3">
          {THEMES.map((theme) => {
            const isEquipped = selectedTheme === theme.id;
            return (
              <div
                key={theme.id}
                onClick={() => handleApply(theme.id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
                  isEquipped
                    ? 'border-amber-500/70 shadow-md bg-slate-800/60'
                    : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/60'
                }`}
              >
                <div className="flex items-center gap-3.5">
                  {/* Color preview swatch */}
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center border shadow-inner shrink-0"
                    style={{
                      backgroundColor: theme.bgHex,
                      borderColor: theme.accentHex,
                    }}
                  >
                    <div
                      className="w-5 h-5 rounded-md"
                      style={{ backgroundColor: theme.accentHex }}
                    />
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-bold text-slate-100">{theme.name}</h4>
                      {isEquipped && (
                        <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.2 rounded-full font-bold">
                          ACTIF
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">{theme.tagline}</p>
                    <div className="mt-1.5 flex items-center gap-2">
                      <code className="text-[10px] font-mono text-slate-300 bg-black/40 px-2 py-0.5 rounded border border-white/5 truncate max-w-xs sm:max-w-md block">
                        {theme.previewPrompt}
                      </code>
                    </div>
                  </div>
                </div>

                <div className="shrink-0 self-end sm:self-center">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleApply(theme.id);
                    }}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                      isEquipped
                        ? 'bg-amber-500 text-slate-950 shadow-sm'
                        : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                    }`}
                  >
                    {isEquipped && <Check className="w-3.5 h-3.5" />}
                    <span>{isEquipped ? 'Appliqué' : 'Activer'}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs text-slate-400">
          <span>Le thème actif est synchronisé avec votre profil SRE</span>
          <button
            onClick={onClose}
            className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-4 py-1.5 rounded-xl transition-colors cursor-pointer"
          >
            Terminé
          </button>
        </div>
      </div>
    </div>
  );
};
