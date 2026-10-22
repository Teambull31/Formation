import React, { useState } from 'react';
import {
  Terminal,
  Copy,
  Check,
  X,
  Sparkles,
  Bot,
  FileCode,
  Layers,
  Wand2,
  Cpu,
  ShieldCheck,
  BookOpen,
} from 'lucide-react';

interface ClaudeCodePromptModalProps {
  onClose: () => void;
}

export const ClaudeCodePromptModal: React.FC<ClaudeCodePromptModalProps> = ({ onClose }) => {
  const [copied, setCopied] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<'full' | 'devops' | 'minimal'>('full');
  const [includeVim, setIncludeVim] = useState(true);
  const [includeWarRoom, setIncludeWarRoom] = useState(true);
  const [includeTalents, setIncludeTalents] = useState(true);

  const generatePrompt = () => {
    return `# PROMPT CLAUDE CODE — ARCHITECTURE & IMPLÉMENTATION COMPLÈTE QUESTFORGE

Agis en tant qu'Architecte Logiciel Senior et Développeur Full-Stack d'élite.
Votre mission est de concevoir et implémenter **QuestForge**, une plateforme gamifiée d'apprentissage technique quotidien (DevOps, Linux, Kubernetes, SRE) combinant le micro-learning (sessions quotidiennes de 15, 30 ou 60 minutes), un terminal interactif avec support de Vim, des quiz rigoureux sans réponses évidentes, et des mécaniques RPG motivantes.

---

## 🏗️ 1. STACK TECHNIQUE & CONTRAINTES
- **Frontend** : React 19, TypeScript strict, Vite, Tailwind CSS v4, Lucide-react, Canvas-Confetti, xterm.js avec @xterm/addon-fit.
- **Backend** : Python 3.11+, FastAPI, Uvicorn, SQLite3 pour la persistance locale ultra-rapide.
- **Terminal Web / PTY** : WebSocket \`/ws/terminal\` connecté à un pseudo-terminal bash sous Linux (\`pty.openpty()\`) avec redimensionnement dynamique (\`TIOCSWINSZ\`) pour supporter **Vim**, nano, htop et les scripts shell sans décalage.
- **Tests** : Vitest avec React Testing Library pour le frontend, Pytest pour le backend.
- **Design Constitution** : Dark mode cyberpunk/SRE sombre (ardoise 950, accents ambre/cyan/émeraude/violet), zéro bouton "pill" générique, typographie monospaced pour les commandes, composants modulaires ultra-soignés.

---

## 🎯 2. RÈGLES CRITIQUES D'EXPÉRIENCE & DE PÉDAGOGIE
1. **Pas de Réponses Sous les Yeux** :
   - Les solutions des TP ne doivent JAMAIS être affichées en clair ou pré-remplies par défaut. L'apprenant doit taper ses commandes.
   - Les distracteurs de QCM doivent être plausibles, techniques et réalistes (éviter les options loufoques ou triviales).
   - Validation stricte des réponses via des scripts shell de contrôle (\`check.sh\`) évaluant le résultat réel sur le système de fichiers.
2. **Gestion Stricte de l'XP (Anti-Duplicate)** :
   - Un TP validé ne donne ses points d'XP (+80 XP) QU'UNE SEULE FOIS.
   - Ré-exécuter la vérification sur un TP déjà réussi confirme que les tests passent sans ré-attribuer d'XP.
3. **Éditeur Vim Intégré** :
   - Support complet de Vim dans le terminal xterm avec transmission des dimensions colonnes/lignes.
   - Guide d'aide mémo Vim intégré (touches \`i\`, \`Esc\`, \`:wq\`, \`:q!\`, \`dd\`, \`u\`).
   - Émulateur de secours en mode conteneur/simulateur pour manipuler des fichiers par syntaxe Vim.

---

## 📦 3. MODULES & FONCTIONNALITÉS À IMPLÉMENTER

### A. Quête Quotidienne Modulaire (\`Quest.tsx\`)
- Sélection de durée : 15 min (Express), 30 min (Standard : Leçon + QCM + TP), 60 min (Hardcore + Boss ou Bonus).
- Calcul dynamique du rang SRE : Padawan Junior -> Opérateur Bash -> Gardien du Kernel -> Maître Kubernetes -> Architecte Chaos.
- Calendrier d'activité façon GitHub Contributions et suivi de streak quotidien avec jour de repos optionnel.

### B. Écran de Leçon & Terminal TP (\`Lesson.tsx\`)
- Onglet 1 : **Synthèse & Audio** (lecteur MP3/TTS simulé, texte formaté avec notions clés).
- Onglet 2 : **QCM technique** (vérification avec explications pédagogiques détaillées).
- Onglet 3 : **TP Pratique** avec terminal bash en direct, support de Vim, script de vérification local et indices progressifs payants en XP.

${
  includeWarRoom
    ? `### C. War Room SRE / Incidents P1 (\`WarRoomModal.tsx\`)
- Simulateur d'astreinte en temps réel : panne DNS Kubernetes, cascade de saturation pool PostgreSQL, crashloop de microservices.
- Diagnostic par étapes avec métriques, logs et répercussions réelles.
- Rédaction de post-mortem technique.`
    : ''
}

${
  includeTalents
    ? `### D. Arbre de Talents RPG (\`SkillTreeModal.tsx\`)
- 3 Branches : *Automatisation Shell*, *Conteneurs & K8s*, *Résilience & Chaos SRE*.
- Déblocage de perks passifs (bonus XP, réduction du coût des indices, vitesse de diagnostic).`
    : ''
}

### E. Arène de Leitner & Répétition Espacée (\`LeitnerArena.tsx\`)
- Système à 5 boîtes pour réviser les questions erronées selon la courbe de l'oubli d'Ebbinghaus.

### F. Mode Focus & Ambiance
- Mode Focus plein écran activable via \`Échap\` (masque les distractions, isole le contenu d'apprentissage).
- Générateur d'ambiance Lo-Fi (bruit blanc salle serveurs, ondes 432 Hz).

---

## 🚀 4. STRUCTURE DE FICHIERS ATTENDUE
\`\`\`
├── backend/
│   ├── app/
│   │   ├── main.py            # API FastAPI & WebSockets
│   │   ├── terminal.py        # Gestion PTY & redimensionnement
│   │   ├── quests.py          # Logique quêtes, XP & streak
│   │   ├── content.py         # Chargement dynamique des modules
│   │   └── tp.py              # Exécution sécurisée des vérifications
│   └── tests/
├── content/
│   └── modules/
│       ├── demo/              # Leçons, qcm.json, tp/check.sh
│       ├── kubernetes/
│       └── docker/
├── src/
│   ├── components/            # Modales & widgets spécialisés
│   ├── screens/               # Quest, Lesson, Boss, Team, Weekly
│   ├── api.ts                 # Client HTTP & fallback local
│   └── App.tsx                # Orchestration et routeur
└── server.ts                  # Serveur full-stack proxy & Vite
\`\`\`

Construis cette application de façon professionnelle, autonome, entièrement typée et sans mock incomplet.`;
  };

  const handleCopy = () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(generatePrompt());
      }
    } catch {}
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 bg-slate-950/70 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-100">Prompt Claude Code — Replicateur QuestForge</h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  Prêt à coller
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Générez le prompt complet pour reproduire l'ensemble des fonctionnalités et architectures dans Claude Code.
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

        {/* Options de personnalisation */}
        <div className="p-3 bg-slate-950/40 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={includeVim}
                onChange={(e) => setIncludeVim(e.target.checked)}
                className="rounded accent-cyan-500"
              />
              <span>Terminal & Vim</span>
            </label>
            <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={includeWarRoom}
                onChange={(e) => setIncludeWarRoom(e.target.checked)}
                className="rounded accent-rose-500"
              />
              <span>War Room P1</span>
            </label>
            <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={includeTalents}
                onChange={(e) => setIncludeTalents(e.target.checked)}
                className="rounded accent-amber-500"
              />
              <span>Arbre de Talents</span>
            </label>
          </div>

          <button
            onClick={handleCopy}
            className={`px-3 py-1.5 rounded-xl font-bold text-xs flex items-center gap-1.5 cursor-pointer transition-all ${
              copied
                ? 'bg-emerald-500 text-slate-950'
                : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/20'
            }`}
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            <span>{copied ? 'Copié dans le presse-papier !' : 'Copier le Prompt'}</span>
          </button>
        </div>

        {/* Zone de preview du Prompt */}
        <div className="p-4 flex-1 overflow-y-auto font-mono text-xs text-slate-300 bg-slate-950/60 space-y-3">
          <pre className="whitespace-pre-wrap leading-relaxed select-all">
            {generatePrompt()}
          </pre>
        </div>

        {/* Footer */}
        <div className="p-3 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5 text-cyan-300">
            <Sparkles className="w-3.5 h-3.5" />
            Compatible avec Claude Code (CLI) et Cursor / Windsurf
          </span>
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
