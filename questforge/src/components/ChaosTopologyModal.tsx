import React, { useState, useEffect } from 'react';
import {
  Layers,
  X,
  AlertTriangle,
  ShieldCheck,
  Zap,
  RotateCcw,
  Sparkles,
  Server,
  Database,
  Globe,
  Radio,
  CheckCircle2,
  Clock,
  ArrowRight,
} from 'lucide-react';

interface ChaosTopologyModalProps {
  onClose: () => void;
  onRewardExp?: (xp: number) => void;
}

interface ChaosScenario {
  id: string;
  name: string;
  targetNodeId: string;
  impactDescription: string;
  solutionId: string;
  solutionName: string;
  solutionHint: string;
}

const SCENARIOS: ChaosScenario[] = [
  {
    id: 'db_latency',
    name: 'Network Partition sur PostgreSQL',
    targetNodeId: 'db',
    impactDescription: 'Latence TCP +3200ms entre les pods applicatifs et PostgreSQL. Les requêtes s\'empilent et bloquent les workers.',
    solutionId: 'circuit_breaker',
    solutionName: 'Activer le Circuit Breaker (Envoy / Istio) & Fallback Cache',
    solutionHint: 'Coupe instantanément les appels vers la DB dès 5 échecs consécutifs et renvoie les réponses en cache pour éviter l\'effet domino.',
  },
  {
    id: 'oom_storm',
    name: 'OOMKilled Storm sur les Pods',
    targetNodeId: 'pods',
    impactDescription: 'Consommation mémoire incontrôlée, le noyau Linux SIGKILL les pods en boucle (CrashLoopBackOff).',
    solutionId: 'hpa_probes',
    solutionName: 'Déployer HPA Autoscaler + Liveness/Readiness Probes calibrées',
    solutionHint: 'Définit des limites strictes avec graduation de scale-out automatique et graceful shutdown pour amortir la charge.',
  },
  {
    id: 'tls_expired',
    name: 'Expiration du Certificat TLS Ingress',
    targetNodeId: 'ingress',
    impactDescription: 'Le certificat Let\'s Encrypt a expiré il y a 10 minutes. Tous les navigateurs rejettent les requêtes HTTPS avec SEC_ERROR_EXPIRED_CERTIFICATE.',
    solutionId: 'cert_manager',
    solutionName: 'Injecter cert-manager OCI avec Auto-Renew CronJob',
    solutionHint: 'Automatise le renouvellement ACME à J-30 et recharge à chaud la configuration Envoy sans interruption.',
  },
  {
    id: 'redis_stampede',
    name: 'Cache Stampede & Éviction Redis',
    targetNodeId: 'redis',
    impactDescription: 'La clé de cache du catalogue a expiré. 50 000 requêtes/sec frappent simultanément la base de données relationnelle brute.',
    solutionId: 'mutex_lock',
    solutionName: 'Verrou Mutex Probabiliste (XFetch) & Early Recomputation',
    solutionHint: 'Une seule requête régénère le cache pendant que les autres reçoivent la valeur stale, évitant l\'écroulement de la DB.',
  },
];

interface NodeStatus {
  id: string;
  name: string;
  icon: any;
  status: 'nominal' | 'degraded' | 'critical' | 'mitigated';
  latencyMs: number;
}

export const ChaosTopologyModal: React.FC<ChaosTopologyModalProps> = ({ onClose, onRewardExp }) => {
  const [activeScenario, setActiveScenario] = useState<ChaosScenario | null>(null);
  const [nodes, setNodes] = useState<NodeStatus[]>([
    { id: 'cdn', name: 'Cloudflare Edge / WAF', icon: Globe, status: 'nominal', latencyMs: 12 },
    { id: 'ingress', name: 'OCI Ingress Gateway', icon: Radio, status: 'nominal', latencyMs: 24 },
    { id: 'pods', name: 'Microservices Pods', icon: Server, status: 'nominal', latencyMs: 38 },
    { id: 'redis', name: 'Redis Cache Cluster', icon: Database, status: 'nominal', latencyMs: 4 },
    { id: 'db', name: 'PostgreSQL Primary / Replica', icon: Database, status: 'nominal', latencyMs: 18 },
  ]);

  const [timerSeconds, setTimerSeconds] = useState<number>(0);
  const [timerActive, setTimerActive] = useState<boolean>(false);
  const [resolved, setResolved] = useState<boolean>(false);

  useEffect(() => {
    let interval: any = null;
    if (timerActive) {
      interval = setInterval(() => {
        setTimerSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [timerActive]);

  const handleInjectChaos = (sc: ChaosScenario) => {
    setActiveScenario(sc);
    setResolved(false);
    setTimerSeconds(0);
    setTimerActive(true);

    setNodes((prev) =>
      prev.map((n) => {
        if (n.id === sc.targetNodeId) {
          return { ...n, status: 'critical', latencyMs: n.latencyMs + 3200 };
        }
        if (n.id === 'ingress' && sc.targetNodeId !== 'cdn') {
          return { ...n, status: 'degraded', latencyMs: n.latencyMs + 450 };
        }
        return n;
      })
    );
  };

  const handleApplyCountermeasure = (solutionId: string) => {
    if (!activeScenario || activeScenario.solutionId !== solutionId) return;

    setTimerActive(false);
    setResolved(true);

    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        status: 'nominal',
        latencyMs: n.id === 'redis' ? 4 : n.id === 'cdn' ? 12 : n.id === 'db' ? 20 : 35,
      }))
    );

    if (onRewardExp) {
      const bonus = timerSeconds < 15 ? 75 : 50;
      onRewardExp(bonus);
    }
  };

  const handleResetTopology = () => {
    setActiveScenario(null);
    setTimerActive(false);
    setTimerSeconds(0);
    setResolved(false);
    setNodes([
      { id: 'cdn', name: 'Cloudflare Edge / WAF', icon: Globe, status: 'nominal', latencyMs: 12 },
      { id: 'ingress', name: 'OCI Ingress Gateway', icon: Radio, status: 'nominal', latencyMs: 24 },
      { id: 'pods', name: 'Microservices Pods', icon: Server, status: 'nominal', latencyMs: 38 },
      { id: 'redis', name: 'Redis Cache Cluster', icon: Database, status: 'nominal', latencyMs: 4 },
      { id: 'db', name: 'PostgreSQL Primary / Replica', icon: Database, status: 'nominal', latencyMs: 18 },
    ]);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-black text-slate-100">
                  Topology Breakdown & Chaos Injector
                </h2>
                <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  DISTRIBUTED RESILIENCE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Visualisez la cascade de panne et appliquez les contre-mesures architecturales SRE
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

        {/* Live Topology Diagram */}
        <div className="bg-slate-950/80 p-4 sm:p-6 border-b border-slate-800">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              Topologie de Production en Temps Réel
            </span>
            <div className="flex items-center gap-3 text-xs font-mono">
              {timerActive && (
                <span className="flex items-center gap-1.5 text-rose-400 font-bold bg-rose-950/60 border border-rose-500/30 px-2.5 py-1 rounded-lg">
                  <Clock className="w-3.5 h-3.5 animate-spin" />
                  MTTR Chrono : {timerSeconds}s
                </span>
              )}
              <button
                onClick={handleResetTopology}
                className="flex items-center gap-1 text-slate-400 hover:text-slate-200 bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-700 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
                Reset
              </button>
            </div>
          </div>

          {/* Interactive Topology Nodes Pipeline */}
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 relative">
            {nodes.map((node, index) => {
              const Icon = node.icon;
              return (
                <div
                  key={node.id}
                  className={`p-3.5 rounded-xl border flex flex-col justify-between transition-all duration-300 relative ${
                    node.status === 'critical'
                      ? 'bg-rose-950/40 border-rose-500/70 shadow-lg shadow-rose-950/50 animate-pulse'
                      : node.status === 'degraded'
                      ? 'bg-amber-950/30 border-amber-500/50 shadow-md'
                      : 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                        node.status === 'critical'
                          ? 'bg-rose-500/20 text-rose-400'
                          : node.status === 'degraded'
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-cyan-500/10 text-cyan-400'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <span
                      className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                        node.status === 'critical'
                          ? 'bg-rose-500/30 text-rose-300'
                          : node.status === 'degraded'
                          ? 'bg-amber-500/30 text-amber-300'
                          : 'bg-emerald-500/20 text-emerald-300'
                      }`}
                    >
                      {node.status.toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-200 truncate">{node.name}</h4>
                    <span className="text-[11px] font-mono text-slate-400 block mt-0.5">
                      Latence : {node.latencyMs}ms
                    </span>
                  </div>

                  {index < nodes.length - 1 && (
                    <div className="hidden sm:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-slate-600">
                      ➔
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Action and Resolution Zone */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {/* Active Incident Alert */}
          {activeScenario && !resolved && (
            <div className="bg-rose-950/40 border border-rose-500/50 rounded-xl p-4 space-y-3 animate-fade-in">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                <div>
                  <h3 className="text-sm font-bold text-rose-200">
                    INCIDENT ACTIF : {activeScenario.name}
                  </h3>
                  <p className="text-xs text-rose-300 mt-0.5">
                    {activeScenario.impactDescription}
                  </p>
                </div>
              </div>

              <div className="pt-2 border-t border-rose-800/40">
                <h4 className="text-xs font-bold text-slate-300 mb-2">
                  Sélectionnez la contre-mesure architecturale SRE adaptée :
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {SCENARIOS.map((sc) => (
                    <button
                      key={sc.id}
                      onClick={() => handleApplyCountermeasure(sc.solutionId)}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                        sc.solutionId === activeScenario.solutionId
                          ? 'bg-emerald-950/40 border-emerald-500/60 hover:bg-emerald-900/50 text-emerald-200'
                          : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <span className="text-xs font-bold block mb-1 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        {sc.solutionName}
                      </span>
                      <span className="text-[11px] text-slate-400 block">{sc.solutionHint}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Success Banner */}
          {resolved && (
            <div className="bg-emerald-950/40 border border-emerald-500/50 rounded-xl p-4 flex items-center justify-between gap-3 text-xs text-emerald-300 animate-fade-in">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-black text-emerald-200">
                    Système Rétabli ! MTTR : {timerSeconds} secondes
                  </h4>
                  <p className="text-emerald-400/90 mt-0.5">
                    La contre-mesure a neutralisé l'effet domino et rééquilibré la topologie.
                  </p>
                </div>
              </div>
              <span className="bg-emerald-500/20 text-emerald-300 font-mono font-bold px-3 py-1.5 rounded-xl border border-emerald-500/40">
                +60 XP SRE
              </span>
            </div>
          )}

          {/* Chaos Injection Menu */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Catalogue d'Injection de Pannes (Chaos Monkey)
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {SCENARIOS.map((sc) => (
                <div
                  key={sc.id}
                  className="bg-slate-950/60 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 flex flex-col justify-between gap-3"
                >
                  <div>
                    <span className="text-xs font-bold text-slate-200 block mb-1">{sc.name}</span>
                    <p className="text-[11px] text-slate-400">{sc.impactDescription}</p>
                  </div>
                  <button
                    disabled={activeScenario !== null && !resolved}
                    onClick={() => handleInjectChaos(sc)}
                    className="flex items-center justify-center gap-1.5 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-bold py-1.5 px-3 rounded-lg transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    <span>Déclencher la Panne</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs text-slate-400">
          <span>Principles of Chaos Engineering • Netflix & Google Reliability</span>
          <button
            onClick={onClose}
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-xl font-medium transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
