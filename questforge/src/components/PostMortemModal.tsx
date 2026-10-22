import React, { useState } from 'react';
import {
  FileText,
  X,
  Copy,
  Check,
  Download,
  AlertTriangle,
  Clock,
  Sparkles,
  HelpCircle,
  ShieldCheck,
  CheckCircle2,
  Share2,
} from 'lucide-react';

interface PostMortemModalProps {
  onClose: () => void;
  onRewardExp?: (xp: number) => void;
}

interface ActionItem {
  id: string;
  type: 'PREVENT' | 'MITIGATE' | 'DETECT';
  description: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2';
}

const TEMPLATES = [
  {
    id: 'k8s_oom',
    title: 'Incident P1 : OOMKilled cascade sur cluster Kubernetes de paiement',
    severity: 'P1 - CRITICAL',
    service: 'payment-gateway-prod',
    date: '2026-10-22',
    ttd: '3 min',
    ttm: '11 min',
    ttr: '24 min',
    summary:
      'Fuite de mémoire non détectée dans le worker de réconciliation entraînant le dépassement des limites cgroups v2, provoquant le redémarrage en boucle des pods et la dégradation de 18% des transactions.',
    whys: [
      { why: 'Pourquoi les pods de paiement sont tombés en CrashLoopBackOff ?', ans: 'Le noyau Linux a envoyé un signal SIGKILL via le OOM Killer car le conteneur a dépassé sa memory limit de 512Mi.' },
      { why: 'Pourquoi le conteneur a dépassé 512Mi de RAM ?', ans: 'Une requête batch volumineuse a chargé tous les logs JSON en mémoire au lieu d\'utiliser un buffer streaming.' },
      { why: 'Pourquoi cette requête batch a été exécutée sur les pods temps réel ?', ans: 'Aucune séparation n\'existait entre les charges batch analytiques et le trafic de paiement critique.' },
      { why: 'Pourquoi l\'alerte n\'a pas prévenu avant le crash ?', ans: 'L\'alerte Prometheus ne surveillait que l\'utilisation CPU globale et non le ratio container_memory_working_set_bytes / limit.' },
      { why: 'Pourquoi ce manque de sonde sur la mémoire ?', ans: 'Le template Helm standard n\'avait pas été audité lors de la migration vers Kubernetes 1.30.' },
    ],
    actions: [
      { id: '1', type: 'PREVENT', description: 'Séparer les workers batch sur un node pool dédié avec taints & tolerations', owner: '@infra-team', priority: 'P0' },
      { id: '2', type: 'DETECT', description: 'Déployer une alerte Prometheus container_memory > 85% limit avec préavis de 5m', owner: '@sre-duty', priority: 'P0' },
      { id: '3', type: 'MITIGATE', description: 'Activer le Horizontal Pod Autoscaler (HPA) basé sur le working_set_bytes avec max 20 replicas', owner: '@backend-leads', priority: 'P1' },
    ] as ActionItem[],
  },
  {
    id: 'dns_blackhole',
    title: 'Incident P2 : Coupure de résolution CoreDNS suite à un flood UDP',
    severity: 'P2 - HIGH',
    service: 'coredns / kube-system',
    date: '2026-10-22',
    ttd: '5 min',
    ttm: '8 min',
    ttr: '19 min',
    summary:
      'Un microservice en boucle de retry sans jitter ni exponential backoff a saturé les instances CoreDNS en requêtes UDP non mises en cache, provoquant des erreurs 502 Bad Gateway sporadiques.',
    whys: [
      { why: 'Pourquoi les requêtes HTTP échouaient avec 502 ?', ans: 'Les pods applicatifs n\'arrivaient plus à résoudre le nom DNS interne de la base PostgreSQL.' },
      { why: 'Pourquoi la résolution DNS interne échouait ?', ans: 'Les 2 répliques de CoreDNS étaient à 100% de CPU et perdaient 45% des paquets UDP.' },
      { why: 'Pourquoi un volume aussi anormal de requêtes DNS ?', ans: 'Un microservice fraîchement déployé ouvrait une nouvelle connexion avec résolution DNS à chaque requête cliente au lieu d\'utiliser un pool HTTP persistant (Keep-Alive).' },
      { why: 'Pourquoi NodeLocal DNSCache n\'était pas actif ?', ans: 'Le composant n\'avait pas été activé sur le cluster OCI Container Engine.' },
      { why: 'Pourquoi le problème a traversé la CI/CD ?', ans: 'Les tests de charge synthétiques en staging ne testaient pas l\'épuisement des sockets DNS sous volume nominal.' },
    ],
    actions: [
      { id: '1', type: 'PREVENT', description: 'Déployer NodeLocal DNSCache (DaemonSet) sur tous les nœuds de calcul OCI', owner: '@platform-team', priority: 'P0' },
      { id: '2', type: 'MITIGATE', description: 'Ajouter un client HTTP avec connection pooling (Keep-Alive) dans le SDK interne', owner: '@core-libs', priority: 'P0' },
      { id: '3', type: 'DETECT', description: 'Alerter sur le taux de paquets drop coredns_dns_request_duration_seconds > 200ms', owner: '@sre-duty', priority: 'P1' },
    ] as ActionItem[],
  },
];

export const PostMortemModal: React.FC<PostMortemModalProps> = ({ onClose, onRewardExp }) => {
  const [selectedTemplate, setSelectedTemplate] = useState<number>(0);
  const [copied, setCopied] = useState(false);
  const [validated, setValidated] = useState(false);

  // Active form data
  const tpl = TEMPLATES[selectedTemplate];
  const [title, setTitle] = useState(tpl.title);
  const [severity, setSeverity] = useState(tpl.severity);
  const [service, setService] = useState(tpl.service);
  const [ttd, setTtd] = useState(tpl.ttd);
  const [ttm, setTtm] = useState(tpl.ttm);
  const [ttr, setTtr] = useState(tpl.ttr);
  const [summary, setSummary] = useState(tpl.summary);
  const [whys, setWhys] = useState(tpl.whys);
  const [actions, setActions] = useState<ActionItem[]>(tpl.actions);

  const handleSelectTemplate = (idx: number) => {
    setSelectedTemplate(idx);
    const item = TEMPLATES[idx];
    setTitle(item.title);
    setSeverity(item.severity);
    setService(item.service);
    setTtd(item.ttd);
    setTtm(item.ttm);
    setTtr(item.ttr);
    setSummary(item.summary);
    setWhys(item.whys);
    setActions(item.actions);
    setValidated(false);
  };

  const handleWhyChange = (index: number, newAns: string) => {
    const updated = [...whys];
    updated[index].ans = newAns;
    setWhys(updated);
  };

  const generateMarkdown = () => {
    const actionsMd = actions
      .map(
        (a) =>
          `- [ ] **[${a.priority}] [${a.type}]** ${a.description} *(Responsable: ${a.owner})*`
      )
      .join('\n');

    const whysMd = whys
      .map((w, i) => `${i + 1}. **${w.why}**\n   ➔ ${w.ans}`)
      .join('\n\n');

    return `# 🛡️ Rapport d'Incident Post-Mortem Blameless (Google SRE Standard)

## 📌 Informations Générales
- **Titre de l'incident :** ${title}
- **Sévérité :** \`${severity}\`
- **Service impacté :** \`${service}\`
- **Date :** ${new Date().toISOString().split('T')[0]}

---

## ⏱️ Métriques de Résolution SRE
| Métrique | Valeur | Définition |
|---|---|---|
| **TTD** (Time To Detect) | **${ttd}** | Délai entre le début de la dégradation et la première alerte |
| **TTM** (Time To Mitigate) | **${ttm}** | Délai jusqu'à l'atténuation de l'impact pour les utilisateurs |
| **TTR** (Time To Resolve) | **${ttr}** | Délai jusqu'au retour à la stabilité nominale complète |

---

## 📝 Résumé Exécutif & Impact Utilisateur
${summary}

---

## 🔍 Analyse Causale des 5 Pourquoi (Blameless Root Cause)
*Principe fondamental : nous nous concentrons sur les faiblesses du système et des garde-fous, jamais sur la faute d'un individu.*

${whysMd}

---

## 🚀 Plan d'Actions Correctives (Action Items)
${actionsMd}

---
*Généré avec QuestForge SRE Odyssey • Conforme aux directives Google SRE Blameless Post-Mortem*
`;
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(generateMarkdown());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([generateMarkdown()], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `post-mortem-${service}-${new Date().toISOString().split('T')[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleValidateReport = () => {
    setValidated(true);
    if (onRewardExp) {
      onRewardExp(60);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-black text-slate-100">
                  Studio Post-Mortem Blameless
                </h2>
                <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  STANDARD GOOGLE SRE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Rétro-ingénierie systémique sans culpabilisation & matrice d'actions
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

        {/* Template Selector Bar */}
        <div className="bg-slate-950/60 border-b border-slate-800 px-4 py-2.5 flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-slate-400 font-semibold whitespace-nowrap">Modèles pré-configurés :</span>
          {TEMPLATES.map((t, idx) => (
            <button
              key={t.id}
              onClick={() => handleSelectTemplate(idx)}
              className={`px-3 py-1.5 rounded-lg border font-medium whitespace-nowrap transition-all ${
                selectedTemplate === idx
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm'
                  : 'bg-slate-800/40 text-slate-400 border-slate-700/60 hover:text-slate-200'
              }`}
            >
              {t.title.split(':')[0]}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 text-sm">
          {/* Top metadata grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl">
              <label className="text-[11px] font-bold text-slate-400 block mb-1">TITRE DE L'INCIDENT</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
              />
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl">
              <label className="text-[11px] font-bold text-slate-400 block mb-1">SÉVÉRITÉ & SERVICE</label>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-rose-400 font-bold focus:outline-none focus:border-amber-500"
                />
                <input
                  type="text"
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl flex items-center justify-around text-center">
              <div>
                <span className="text-[10px] text-slate-400 font-mono block">TTD (Détection)</span>
                <span className="text-sm font-black text-amber-400">{ttd}</span>
              </div>
              <div className="h-6 w-px bg-slate-800" />
              <div>
                <span className="text-[10px] text-slate-400 font-mono block">TTM (Atténuation)</span>
                <span className="text-sm font-black text-cyan-400">{ttm}</span>
              </div>
              <div className="h-6 w-px bg-slate-800" />
              <div>
                <span className="text-[10px] text-slate-400 font-mono block">TTR (Résolution)</span>
                <span className="text-sm font-black text-emerald-400">{ttr}</span>
              </div>
            </div>
          </div>

          {/* Impact summary */}
          <div className="bg-slate-950/50 border border-slate-800/80 rounded-xl p-4">
            <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Résumé de l'Impact Utilisateur
            </h3>
            <textarea
              rows={2}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="w-full bg-slate-900/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-sans"
            />
          </div>

          {/* 5 Whys section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-cyan-400" />
                Analyse Causale des "5 Pourquoi" (Blameless Root Cause)
              </h3>
              <span className="text-[11px] text-slate-400 italic">
                Ciblez les failles du système, non les individus
              </span>
            </div>
            <div className="space-y-2.5">
              {whys.map((item, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3 flex flex-col sm:flex-row sm:items-start gap-2.5"
                >
                  <div className="w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 font-mono font-bold flex items-center justify-center text-xs shrink-0 mt-0.5">
                    {idx + 1}
                  </div>
                  <div className="flex-1 space-y-1">
                    <p className="text-xs font-semibold text-slate-300">{item.why}</p>
                    <input
                      type="text"
                      value={item.ans}
                      onChange={(e) => handleWhyChange(idx, e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/70 rounded-md px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Action Items Matrix */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Matrice des Actions Correctives Préventives
              </h3>
              <span className="text-[11px] text-slate-400">P0 / P1 / P2</span>
            </div>
            <div className="space-y-2">
              {actions.map((act) => (
                <div
                  key={act.id}
                  className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 flex items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-2.5 flex-1 min-w-0">
                    <span
                      className={`text-[10px] font-black px-2 py-0.5 rounded font-mono ${
                        act.priority === 'P0'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : act.priority === 'P1'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                      }`}
                    >
                      {act.priority}
                    </span>
                    <span className="text-[10px] font-bold text-cyan-400 bg-cyan-950/50 px-2 py-0.5 rounded border border-cyan-800/40">
                      {act.type}
                    </span>
                    <p className="text-xs text-slate-200 truncate">{act.description}</p>
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono shrink-0">{act.owner}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="p-4 sm:p-5 border-t border-slate-800 bg-slate-900/90 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {!validated ? (
              <button
                onClick={handleValidateReport}
                className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs transition-all shadow-md shadow-emerald-900/30 cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                <span>Valider le Rapport (+60 XP)</span>
              </button>
            ) : (
              <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-semibold bg-emerald-950/40 border border-emerald-500/30 px-3 py-1.5 rounded-xl">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Rapport validé conforme aux standards SRE !</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              <span>{copied ? 'Copié !' : 'Copier Markdown'}</span>
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Télécharger .md</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
