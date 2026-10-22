export interface Step {
  kind: 'lesson' | 'qcm' | 'tp' | 'bonus';
  lesson_id: string;
  minutes: number;
  xp: number;
  done: boolean;
}

export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlocked: boolean;
  unlockedAt?: string;
}

export interface CompanionPerk {
  id: string;
  name: string;
  description: string;
  bonusType: 'xp_boost' | 'free_hint' | 'streak_shield';
}

export interface Profile {
  total_xp: number;
  rank: string;
  skills: Record<string, number>;
  tokens: number;
  active_theme: string;
  active_companion?: string;
  active_module_id: string;
  achievements: Achievement[];
}

export interface ActivityDayLog {
  date: string;
  count: number;
  status: 'active' | 'rest' | 'topic' | 'idle';
}

export interface QuestData {
  day: string;
  steps: Step[];
  bonus: Step | null;
  imposed_topic: string | null;
  streak: number;
  profile: Profile;
  dueReviewsCount: number;
  activityHistory: ActivityDayLog[];
}

export interface Question {
  id: string;
  text: string;
  options: string[];
  explain: string;
  remedial_lesson_id?: string | null;
  box?: number;
  answer?: number;
}

export interface TpInfo {
  id: string;
  title: string;
  instructions_md: string;
  timeout_s: number;
  total_hints: number;
}

export interface LessonData {
  id: string;
  title: string;
  module_id: string;
  module_title: string;
  skill: string;
  minutes: number;
  body_md: string;
  summary_audio_text?: string;
  qcm: Question[];
  tp: TpInfo | null;
}

export interface ModuleItem {
  id: string;
  title: string;
  skill: string;
  description: string;
  icon: string;
  lessonsCount: number;
  totalMinutes: number;
}

export interface QcmAnswerResult {
  correct: boolean;
  explanation: string;
  remedial_lesson_id: string | null;
}

export interface InventoryItem {
  id?: number;
  item_id: string;
  name: string;
  type: 'character' | 'skin';
  rarity: 'common' | 'rare' | 'epic';
  count: number;
  avatar?: string;
  lore?: string;
  perk?: CompanionPerk;
  equipped?: boolean;
}

export interface TeamData {
  profile: Profile;
  inventory: InventoryItem[];
  pool_size: number;
  equippedCompanion?: InventoryItem;
}

export interface BossPhase {
  pattern_id: string;
  label: string;
  check: string;
  remedial_lesson_id?: string;
}

export interface BossEntity {
  id: string;
  title: string;
  description: string;
  avatar: string;
  color: string;
  phases: BossPhase[];
}

export interface BossData {
  boss: BossEntity;
  attempts_count: number;
  history: Array<{
    won: number;
    phase_reached: number;
    failed_pattern?: string;
    remedial_lesson_id?: string;
    created_at: string;
    post_mortem?: string;
    crisis_mode?: boolean;
  }>;
}

export interface BossAttemptResult {
  xpAwarded?: number;
  tokensAwarded?: number;
  won: boolean;
  phase_reached: number;
  failed_pattern: string | null;
  remedial_lesson_id: string | null;
  post_mortem?: string;
  crisis_mode?: boolean;
}

export interface SandboxChallenge {
  id: string;
  title: string;
  description: string;
  difficulty: 'facile' | 'moyen' | 'expert';
  xpReward: number;
  solutionCommand: string;
  verificationRegex: string;
}

export interface TalentNode {
  id: string;
  name: string;
  branch: 'automation' | 'terminal' | 'boss';
  tier: number;
  description: string;
  icon: string;
  cost: number;
  unlocked: boolean;
  requires?: string;
  perkEffect: string;
}

export interface IncidentOption {
  id: string;
  label: string;
  impactExplanation: string;
  isCorrect: boolean;
  deltaErrors: number;
  deltaLatency: number;
  logFollowup: string;
}

export interface IncidentPhase {
  step: number;
  title: string;
  description: string;
  options: IncidentOption[];
}

export interface IncidentScenario {
  id: string;
  title: string;
  service: string;
  severity: 'P1 - Critique' | 'P2 - Majeur' | 'P3 - Modéré';
  initialMetrics: { rps: number; errorRate: number; latencyP99: number };
  systemLogs: string[];
  phases: IncidentPhase[];
}

export interface GhostRunner {
  id: string;
  name: string;
  role: string;
  avatar: string;
  baseSeconds: number;
  accuracy: number;
  quote: string;
  badge: string;
}

export interface DuelRecord {
  id: string;
  ghostId: string;
  ghostName: string;
  playerSeconds: number;
  ghostSeconds: number;
  won: boolean;
  createdAt: string;
}

export interface FeynmanMemo {
  id: string;
  lessonId: string;
  conceptTitle: string;
  explanation: string;
  analogies: string;
  createdAt: string;
}

export interface CustomChallengeResult {
  id: string;
  title: string;
  topic: string;
  level: string;
  description: string;
  markdownContent: string;
  targetFile: string;
  solutionCommand: string;
  verificationScript: string;
  xpReward: number;
}

// 1. Tech Roadmap Node
export interface TechTreeNode {
  id: string;
  title: string;
  category: 'linux' | 'network' | 'docker' | 'k8s' | 'gitops' | 'sre';
  level: number;
  prerequisites: string[];
  status: 'locked' | 'unlocked' | 'mastered';
  masteryPct: number;
  lessonId?: string;
  icon?: string;
  description: string;
}

// 2. Chaos Incident in TP
export interface ChaosIncident {
  id: string;
  title: string;
  description: string;
  symptom: string;
  remedyHint: string;
  remedyCommand: string;
  resolved: boolean;
  xpReward: number;
}

// 3. SRE Runbook Document
export interface RunbookDocument {
  id: string;
  title: string;
  lessonId: string;
  createdAt: string;
  markdown: string;
  tags: string[];
}

// 4. Oral Technical Interview Question
export interface InterviewQuestion {
  id: string;
  role: 'DevOps Senior' | 'Site Reliability Engineer' | 'Kubernetes Architect';
  question: string;
  audioPrompt?: string;
  timeLimitSeconds: number;
  expectedKeywords: string[];
  evaluationRubric: {
    criteria: string;
    points: number;
  }[];
  seniorSampleAnswer: string;
}

// 5. League & Guild System
export interface LeagueUser {
  rank: number;
  name: string;
  avatar: string;
  xpThisWeek: number;
  tier: 'bronze' | 'silver' | 'gold' | 'master' | 'elite';
  isCurrentPlayer?: boolean;
}

export interface GuildMission {
  id: string;
  title: string;
  description: string;
  target: number;
  current: number;
  unit: string;
  completed: boolean;
  rewardTokens: number;
}

export interface LeagueData {
  currentTier: 'bronze' | 'silver' | 'gold' | 'master' | 'elite';
  timeRemainingDays: number;
  leaderboard: LeagueUser[];
  guildMissions: GuildMission[];
}

// 6. Time Travel Command History Item
export interface CommandReplayItem {
  id: string;
  timestamp: string;
  cmd: string;
  exitCode: number;
  durationMs: number;
  output: string;
}

export interface PacketLayer {
  name: string;
  protocol: string;
  summary: string;
  fields: Record<string, string>;
  rawHex: string;
}

export interface PacketFlowItem {
  id: string;
  timestamp: string;
  src: string;
  dst: string;
  protocol: string;
  info: string;
  layers: PacketLayer[];
}

export interface PacketScenario {
  id: string;
  title: string;
  description: string;
  command: string;
  packets: PacketFlowItem[];
}

export interface FsrsCardState {
  cardId: string;
  stability: number; // en jours
  difficulty: number; // 1 à 10
  retrievability: number; // 0.0 à 1.0
  reps: number;
  lapses: number;
  lastReview: string;
  nextReview: string;
  intervalDays: number;
}

export type FsrsRating = 1 | 2 | 3 | 4; // 1: Encore, 2: Difficile, 3: Bon, 4: Facile

export interface LeagueParticipant {
  id: string;
  name: string;
  avatar: string;
  weeklyXp: number;
  rank: number;
  isPlayer?: boolean;
  status: 'promotion' | 'safe' | 'demotion';
  badgeTitle: string;
}

export interface WeeklyLeagueData {
  division: 'Bronze' | 'Argent' | 'Or' | 'Platine' | 'Diamant';
  daysLeft: number;
  participants: LeagueParticipant[];
  playerWeeklyXp: number;
  playerRank: number;
  rewardsAvailable: boolean;
}

export interface PairMessage {
  id: string;
  sender: 'player' | 'partner' | 'system';
  author: string;
  avatar: string;
  text: string;
  codeSnippet?: string;
  timestamp: string;
}

export interface PairScenario {
  id: string;
  title: string;
  difficulty: 'Intermédiaire' | 'Expert';
  partnerName: string;
  partnerRole: string;
  partnerAvatar: string;
  objective: string;
  context: string;
  steps: Array<{
    id: string;
    description: string;
    suggestedAction: string;
    partnerObservation: string;
    resolutionSnippet: string;
  }>;
}

export interface PortfolioData {
  studentName: string;
  studentEmail: string;
  certificateId: string;
  issueDate: string;
  rank: string;
  totalXp: number;
  streakDays: number;
  skillsBreakdown: Record<string, number>;
  masteredModules: Array<{ id: string; title: string; skill: string; verifiedDate: string }>;
  bossesDefeated: Array<{ id: string; title: string; avatar: string; date: string }>;
  warRoomIncidents: Array<{ id: string; title: string; date: string }>;
  hashFingerprint: string;
}

export function calculateNextFsrs(
  prevStability: number,
  prevDifficulty: number,
  rating: FsrsRating
): { stability: number; difficulty: number; intervalDays: number; retrievability: number } {
  const difficulty = Math.max(1, Math.min(10, prevDifficulty + (3 - rating) * 0.8));
  let stability = prevStability;

  if (rating === 1) {
    stability = Math.max(0.3, prevStability * 0.4);
  } else if (rating === 2) {
    stability = Math.max(1.0, prevStability * 1.2);
  } else if (rating === 3) {
    stability = Math.max(2.0, prevStability * 2.4);
  } else {
    stability = Math.max(4.0, prevStability * 3.8);
  }

  const intervalDays = rating === 1 ? 1 : Math.max(1, Math.round(stability));
  const retrievability = Math.round(Math.exp(Math.log(0.9) * (intervalDays / stability)) * 100) / 100;

  return {
    stability: Math.round(stability * 10) / 10,
    difficulty: Math.round(difficulty * 10) / 10,
    intervalDays,
    retrievability,
  };
}

export const PACKET_SCENARIOS: PacketScenario[] = [
  {
    id: 'pkt_http_tls',
    title: 'Négociation TLS 1.3 & Requête HTTP/2 API',
    description: 'Analyse détaillée du 3-way handshake TCP, de l\'échange de clés Diffie-Hellman et du stream HTTP/2.',
    command: 'curl -v --http2 https://api.internal/v1/health',
    packets: [
      {
        id: 'p1',
        timestamp: '0.000000',
        src: '10.244.1.42:54890',
        dst: '10.96.0.15:443',
        protocol: 'TCP',
        info: '54890 → 443 [SYN] Seq=0 Win=64240 Len=0 MSS=1460 SACK_PERM TSval=382910',
        layers: [
          {
            name: 'Couche 2 - Liaison de données',
            protocol: 'Ethernet II',
            summary: 'Src: 52:54:00:12:34:56, Dst: 52:54:00:fe:ed:01, Type: IPv4 (0x0800)',
            fields: { 'Source MAC': '52:54:00:12:34:56', 'Destination MAC': '52:54:00:fe:ed:01', 'EtherType': '0x0800 (IPv4)' },
            rawHex: '52 54 00 fe ed 01 52 54 00 12 34 56 08 00',
          },
          {
            name: 'Couche 3 - Réseau / Internet',
            protocol: 'IPv4',
            summary: '10.244.1.42 → 10.96.0.15, Header Len: 20 octets, TTL: 64, Protocol: TCP (6)',
            fields: { 'Version': '4', 'Header Length': '20 bytes', 'TOS': '0x00', 'Total Length': '60', 'TTL': '64', 'Protocol': 'TCP (6)' },
            rawHex: '45 00 00 3c d6 a1 40 00 40 06 b2 c9 0a f4 01 2a 0a 60 00 0f',
          },
          {
            name: 'Couche 4 - Transport',
            protocol: 'TCP',
            summary: 'Port source: 54890, Port destination: 443, Flags: [SYN], Seq: 0, Win: 64240',
            fields: { 'Source Port': '54890', 'Destination Port': '443', 'Sequence Number': '0 (relative)', 'Flags': '0x002 (SYN)', 'Window Size': '64240' },
            rawHex: 'd6 6a 01 bb 9e 1a 80 4f 00 00 00 00 a0 02 fa f0 6a 12 00 00',
          },
        ],
      },
      {
        id: 'p2',
        timestamp: '0.000412',
        src: '10.96.0.15:443',
        dst: '10.244.1.42:54890',
        protocol: 'TCP',
        info: '443 → 54890 [SYN, ACK] Seq=0 Ack=1 Win=65160 Len=0 MSS=1460',
        layers: [
          {
            name: 'Couche 4 - Transport',
            protocol: 'TCP',
            summary: 'Réponse du serveur Ingress : ACK validé, SYN émis pour initier le duplex',
            fields: { 'Source Port': '443', 'Destination Port': '54890', 'Sequence': '0', 'Acknowledgment': '1', 'Flags': '0x012 (SYN, ACK)' },
            rawHex: '01 bb d6 6a 3a 4f 12 08 9e 1a 80 50 a0 12 fe 88 12 34 00 00',
          },
        ],
      },
      {
        id: 'p3',
        timestamp: '0.000488',
        src: '10.244.1.42:54890',
        dst: '10.96.0.15:443',
        protocol: 'TCP',
        info: '54890 → 443 [ACK] Seq=1 Ack=1 Win=64240 Len=0 (3-way handshake achevé)',
        layers: [
          {
            name: 'Couche 4 - Transport',
            protocol: 'TCP',
            summary: 'Connexion TCP établie avec succès (ESTABLISHED). Prêt pour le tunnel TLS.',
            fields: { 'Status': 'TCP ESTABLISHED', 'Flags': '0x010 (ACK)', 'RTT estimé': '0.41 ms' },
            rawHex: 'd6 6a 01 bb 9e 1a 80 50 3a 4f 12 09 80 10 fa f0 2b 44 00 00',
          },
        ],
      },
      {
        id: 'p4',
        timestamp: '0.001150',
        src: '10.244.1.42:54890',
        dst: '10.96.0.15:443',
        protocol: 'TLSv1.3',
        info: 'Client Hello (SNI: api.internal, ALPN: h2, Cipher: TLS_AES_256_GCM_SHA384)',
        layers: [
          {
            name: 'Couche 7 - Sécurité & Application',
            protocol: 'TLS 1.3 Record Layer',
            summary: 'Handshake Protocol: Client Hello, Supported Versions: TLS 1.3, KeyShare: X25519',
            fields: { 'Extension SNI': 'api.internal', 'ALPN': 'h2, http/1.1', 'Key Exchange': 'ECDH X25519' },
            rawHex: '16 03 01 01 fc 01 00 01 f8 03 03 48 a1 c4 b2 e8 9f 02',
          },
        ],
      },
      {
        id: 'p5',
        timestamp: '0.002890',
        src: '10.96.0.15:443',
        dst: '10.244.1.42:54890',
        protocol: 'HTTP/2',
        info: 'Stream 1: 200 OK (application/json, 42 bytes)',
        layers: [
          {
            name: 'Couche 7 - Application',
            protocol: 'HTTP/2',
            summary: 'HEADERS frame + DATA frame: {"status": "healthy", "uptime": 43280}',
            fields: { ':status': '200', 'content-type': 'application/json', 'payload': '{"status":"healthy","uptime":43280}' },
            rawHex: '00 00 2a 01 05 00 00 00 01 88 5f 8b 1d 75 d0 62 0d 26',
          },
        ],
      },
    ],
  },
  {
    id: 'pkt_dns_lookup',
    title: 'Résolution DNS Interne CoreDNS & Recherche UDP',
    description: 'Tracé du datagramme UDP interrogeant le service CoreDNS Kubernetes sur le port 53.',
    command: 'dig @10.96.0.10 auth-service.production.svc.cluster.local A',
    packets: [
      {
        id: 'dns_p1',
        timestamp: '0.000000',
        src: '10.244.2.19:41235',
        dst: '10.96.0.10:53',
        protocol: 'DNS',
        info: 'Standard query 0x7a12 A auth-service.production.svc.cluster.local',
        layers: [
          {
            name: 'Couche 4 - Transport',
            protocol: 'UDP',
            summary: 'Source Port: 41235, Destination Port: 53 (DNS), Length: 68',
            fields: { 'Src Port': '41235', 'Dst Port': '53', 'Length': '68', 'Checksum': '0x3a19' },
            rawHex: 'a1 13 00 35 00 44 3a 19',
          },
          {
            name: 'Couche 7 - Application',
            protocol: 'DNS Query',
            summary: 'Questions: 1, Query: auth-service.production.svc.cluster.local, Type: A (IPv4)',
            fields: { 'Transaction ID': '0x7a12', 'Flags': '0x0100 (Standard query)', 'Type': 'A (1)' },
            rawHex: '7a 12 01 00 00 01 00 00 00 00 00 00 0c 61 75 74 68 2d 73 65 72 76 69 63 65',
          },
        ],
      },
      {
        id: 'dns_p2',
        timestamp: '0.000850',
        src: '10.96.0.10:53',
        dst: '10.244.2.19:41235',
        protocol: 'DNS',
        info: 'Standard query response 0x7a12 A 10.244.3.88 (TTL: 30s)',
        layers: [
          {
            name: 'Couche 7 - Application',
            protocol: 'DNS Response',
            summary: 'Answers: 1, auth-service.production.svc.cluster.local → 10.244.3.88',
            fields: { 'Transaction ID': '0x7a12', 'Flags': '0x8180 (No error)', 'Answer IP': '10.244.3.88', 'TTL': '30s' },
            rawHex: '7a 12 81 80 00 01 00 01 00 00 00 00 c0 0c 00 01 00 01 00 00 00 1e 00 04 0a f4 03 58',
          },
        ],
      },
    ],
  },
  {
    id: 'pkt_iptables_drop',
    title: 'Pare-feu Netfilter : Blocage SYN Flood & Règle DROP',
    description: 'Visualisation de paquets malveillants interceptés et éliminés silencieusement par la table FILTER d\'iptables.',
    command: 'iptables -A INPUT -p tcp --dport 22 -m state --state NEW -j DROP',
    packets: [
      {
        id: 'drop_p1',
        timestamp: '0.000000',
        src: '198.51.100.77:49812',
        dst: '10.0.0.5:22',
        protocol: 'TCP',
        info: '49812 → 22 [SYN] Seq=14209192 Win=1024 Len=0 (Tentative brute-force SSH)',
        layers: [
          {
            name: 'Couche 3 - Réseau / Netfilter Kernel Hook',
            protocol: 'NF_INET_PRE_ROUTING / INPUT',
            summary: 'Règle évaluée : TABLE filter / CHAIN INPUT -> Match port 22 -> ACTION: DROP',
            fields: { 'Chain': 'INPUT', 'Rule #': '3', 'Verdict': 'DROP (Silencieux)', 'Reason': 'Politique anti brute-force SSH' },
            rawHex: '45 00 00 28 c1 04 00 00 34 06 4a b2 c6 33 64 4d 0a 00 00 05',
          },
        ],
      },
    ],
  },
];

export const INITIAL_LEAGUE_DATA: WeeklyLeagueData = {
  division: 'Or',
  daysLeft: 3,
  playerWeeklyXp: 340,
  playerRank: 4,
  rewardsAvailable: false,
  participants: [
    { id: 'p_1', name: 'KubeMaster_99', avatar: '🚀', weeklyXp: 620, rank: 1, status: 'promotion', badgeTitle: 'Légende Helm' },
    { id: 'p_2', name: 'Sara_Kernel', avatar: '⚡', weeklyXp: 510, rank: 2, status: 'promotion', badgeTitle: 'Dompteuse eBPF' },
    { id: 'p_3', name: 'Thomas_SRE', avatar: '🛡️', weeklyXp: 480, rank: 3, status: 'promotion', badgeTitle: 'Héros PagerDuty' },
    { id: 'p_you', name: 'Vous (Apprenant)', avatar: '🧑‍💻', weeklyXp: 340, rank: 4, isPlayer: true, status: 'safe', badgeTitle: 'Ingénieur QuestForge' },
    { id: 'p_5', name: 'Alex_Docker', avatar: '🐳', weeklyXp: 310, rank: 5, status: 'safe', badgeTitle: 'Conteneur Rootless' },
    { id: 'p_6', name: 'Nadia_Net', avatar: '🌐', weeklyXp: 280, rank: 6, status: 'safe', badgeTitle: 'Réseau Calico' },
    { id: 'p_7', name: 'Mehdi_Bash', avatar: '💻', weeklyXp: 250, rank: 7, status: 'safe', badgeTitle: 'Scripteur Awk' },
    { id: 'p_8', name: 'Clara_CI', avatar: '🔁', weeklyXp: 190, rank: 8, status: 'demotion', badgeTitle: 'Pipelines Runner' },
    { id: 'p_9', name: 'Lucas_Novice', avatar: '🌱', weeklyXp: 120, rank: 9, status: 'demotion', badgeTitle: 'Apprenti Débogueur' },
    { id: 'p_10', name: 'Ghost_Zero', avatar: '👻', weeklyXp: 80, rank: 10, status: 'demotion', badgeTitle: 'En veille' },
  ],
};

export const PAIR_SCENARIOS: PairScenario[] = [
  {
    id: 'pair_1',
    title: 'Astreinte Ingress & Défaillance Cert-Manager',
    difficulty: 'Intermédiaire',
    partnerName: 'Camille',
    partnerRole: 'Lead SRE & Astreinte',
    partnerAvatar: '👩‍💻',
    objective: 'Rétablir le trafic HTTPS et renouveler le certificat Let\'s Encrypt bloqué en Challenge HTTP-01.',
    context: 'L\'Ingress NGINX renvoie une erreur SSL_ERROR_BAD_CERT_DOMAIN. Camille surveille les pods cert-manager pendant que vous diagnostiquez la ressource Certificate.',
    steps: [
      {
        id: 'step_1',
        description: 'Vérifier l\'état de la ressource Certificate dans le namespace prod',
        suggestedAction: 'kubectl get certificate -n prod',
        partnerObservation: '« Je vois dans les logs cert-manager que le pod de challenge HTTP-01 est en CrashLoopBackOff ! »',
        resolutionSnippet: 'kubectl describe certificate api-tls -n prod',
      },
      {
        id: 'step_2',
        description: 'Corriger la règle de routage Ingress pour laisser passer /.well-known/acme-challenge',
        suggestedAction: 'kubectl apply -f ingress-acme-patch.yaml',
        partnerObservation: '« Bien joué ! Le challenge Let\'s Encrypt a reçu le token. Le secret api-tls est régénéré ! »',
        resolutionSnippet: 'kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx',
      },
      {
        id: 'step_3',
        description: 'Effectuer un test de validation TLS avec curl et recharger les sondes',
        suggestedAction: 'curl -Iv https://api.internal/healthz',
        partnerObservation: '« Code 200 et certificat valide jusqu\'en 2027. Incident clos en binôme ! Super coordination ! »',
        resolutionSnippet: 'echo "Pair Debugging réussi avec brio" > /tmp/pair_resolution.log',
      },
    ],
  },
];

const BASE_URL = '';
const LOCAL_STORAGE_KEY = 'questforge_client_state_v3';

const RANKS = ['Bronze', 'Argent', 'Or', 'Platine', 'Expert'];
export function getRankForXp(xp: number): string {
  const idx = Math.min(RANKS.length - 1, Math.max(0, Math.floor(xp / 1000)));
  return RANKS[idx];
}

export const MODULES_CATALOG: ModuleItem[] = [
  {
    id: 'demo',
    title: 'Automatisation & Agents MailSource',
    skill: 'automation',
    description: 'Structurez des interfaces unifiées et des connecteurs tolérants aux pannes.',
    icon: '⚡',
    lessonsCount: 2,
    totalMinutes: 30,
  },
  {
    id: 'docker',
    title: 'Docker & Conteneurisation Moderne',
    skill: 'docker',
    description: 'Multi-stage builds, optimisation d\'images distroless et sécurité rootless.',
    icon: '🐳',
    lessonsCount: 2,
    totalMinutes: 35,
  },
  {
    id: 'k8s',
    title: 'Architecture Kubernetes & Helm',
    skill: 'kubernetes',
    description: 'Déploiement déclaratif, Ingress Controllers et sondes de résilience.',
    icon: '☸️',
    lessonsCount: 2,
    totalMinutes: 40,
  },
  {
    id: 'observability',
    title: 'Observabilité, Métriques & Traces',
    skill: 'observability',
    description: 'Instrumentation Prometheus, dashboards Grafana et alertes SLO/SLA.',
    icon: '📈',
    lessonsCount: 2,
    totalMinutes: 30,
  },
];

export const SANDBOX_CHALLENGES: SandboxChallenge[] = [
  {
    id: 'ch_1',
    title: 'Filtrer les erreurs 500 dans access.log',
    description: 'Générez un fichier access.log et extrayez uniquement les requêtes HTTP 500 avec grep.',
    difficulty: 'facile',
    xpReward: 30,
    solutionCommand: 'grep " 500 " access.log > errors.txt',
    verificationRegex: 'errors\\.txt',
  },
  {
    id: 'ch_2',
    title: 'Créer une arborescence FHS standard',
    description: 'Créez les répertoires etc, var/log et opt en une seule commande mkdir.',
    difficulty: 'facile',
    xpReward: 30,
    solutionCommand: 'mkdir -p app/{etc,var/log,opt}',
    verificationRegex: 'mkdir',
  },
  {
    id: 'ch_3',
    title: 'Script de veille réseau avec timeout',
    description: 'Écrivez un one-liner curl avec --max-time 2 qui teste une API et vérifie le code retour.',
    difficulty: 'moyen',
    xpReward: 50,
    solutionCommand: 'curl -sf --max-time 2 https://httpbin.org/status/200',
    verificationRegex: 'curl.*--max-time',
  },
];

const INITIAL_ACHIEVEMENTS: Achievement[] = [
  {
    id: 'first_step',
    name: 'Première Victoire',
    description: 'Valider votre première étape de quête',
    icon: '🎯',
    unlocked: true,
    unlockedAt: '2026-10-18T20:00:00Z',
  },
  {
    id: 'streak_3',
    name: 'Discipline de Fer',
    description: 'Maintenir une série de 3 jours consécutifs',
    icon: '🔥',
    unlocked: true,
    unlockedAt: '2026-10-19T01:00:00Z',
  },
  {
    id: 'boss_slayer',
    name: 'Chasseur de Pannes',
    description: 'Terrasser un Boss en environnement de production',
    icon: '⚔️',
    unlocked: false,
  },
  {
    id: 'collector_epic',
    name: 'Maître des Légendes',
    description: 'Invoquer un cosmétique de rareté Épique',
    icon: '🔮',
    unlocked: false,
  },
  {
    id: 'podcast_commuter',
    name: 'Auditeur Tout-Terrain',
    description: 'Compléter une séance d\'écoute en mode Podcast',
    icon: '🎧',
    unlocked: false,
  },
  {
    id: 'sandbox_wizard',
    name: 'Hacker du Bac à Sable',
    description: 'Réussir un défi éclair dans le terminal libre',
    icon: '💻',
    unlocked: false,
  },
  {
    id: 'war_room_hero',
    name: 'Héros de l\'Astreinte',
    description: 'Résoudre un incident P1 sans impacter la disponibilité',
    icon: '🚨',
    unlocked: false,
  },
  {
    id: 'skill_tree_master',
    name: 'Maître des Talents',
    description: 'Débloquer au moins 3 talents dans l\'arbre RPG',
    icon: '🌲',
    unlocked: false,
  },
  {
    id: 'ghost_speedster',
    name: 'Chrono SRE',
    description: 'Triompher d\'un fantôme en duel asynchrone contre-la-montre',
    icon: '⚡',
    unlocked: false,
  },
  {
    id: 'feynman_master',
    name: 'Pédagogue Feynman',
    description: 'Rédiger une note d\'auto-explication sur un concept technique',
    icon: '📝',
    unlocked: false,
  },
];

export const INITIAL_TALENTS: TalentNode[] = [
  // Branche Automatisation
  {
    id: 'auto_boost',
    name: 'Pipeline Optimisé',
    branch: 'automation',
    tier: 1,
    description: '+10% d\'XP sur l\'ensemble des étapes de cours et QCM validés.',
    icon: '⚡',
    cost: 1,
    unlocked: true,
    perkEffect: 'xp_boost_10',
  },
  {
    id: 'auto_streak',
    name: 'Résilience CI/CD',
    branch: 'automation',
    tier: 2,
    description: 'Offre +1 jeton gacha tous les 3 jours de série consécutive.',
    icon: '🔁',
    cost: 1,
    unlocked: false,
    requires: 'auto_boost',
    perkEffect: 'token_per_streak',
  },
  {
    id: 'auto_overclock',
    name: 'Overclocking Déploiement',
    branch: 'automation',
    tier: 3,
    description: 'Double les gains d\'XP (+100%) sur toutes les étapes bonus de 60 min.',
    icon: '🚀',
    cost: 2,
    unlocked: false,
    requires: 'auto_streak',
    perkEffect: 'bonus_xp_double',
  },

  // Branche Terminal & TP
  {
    id: 'term_auto_hint',
    name: 'Sonde Syntaxique',
    branch: 'terminal',
    tier: 1,
    description: 'Le premier indice de TP du jour ne coûte aucun point d\'XP.',
    icon: '🔍',
    cost: 1,
    unlocked: false,
    perkEffect: 'free_daily_hint',
  },
  {
    id: 'term_fast_verify',
    name: 'Scripts Parallélisés',
    branch: 'terminal',
    tier: 2,
    description: '+25 XP accordés dès la première exécution réussie d\'un test de TP.',
    icon: '⏱️',
    cost: 1,
    unlocked: false,
    requires: 'term_auto_hint',
    perkEffect: 'tp_first_try_bonus',
  },
  {
    id: 'term_root_mastery',
    name: 'Maîtrise du Kernel',
    branch: 'terminal',
    tier: 3,
    description: 'Débloque les snippets avancés d\'inspection mémoire et sockets réseau.',
    icon: '💻',
    cost: 2,
    unlocked: false,
    requires: 'term_fast_verify',
    perkEffect: 'advanced_snippets',
  },

  // Branche Résilience Boss
  {
    id: 'boss_shield',
    name: 'Circuit Breaker',
    branch: 'boss',
    tier: 1,
    description: 'Absorbe le premier échec de phase lors des combats de boss.',
    icon: '🛡️',
    cost: 1,
    unlocked: false,
    perkEffect: 'boss_phase_shield',
  },
  {
    id: 'boss_time_warp',
    name: 'Astreinte Étendue',
    branch: 'boss',
    tier: 2,
    description: '+60 secondes de délai lors des défis en mode Crise / Chronométré.',
    icon: '⏳',
    cost: 1,
    unlocked: false,
    requires: 'boss_shield',
    perkEffect: 'crisis_time_extended',
  },
  {
    id: 'boss_bounty',
    name: 'Primes Post-Mortem',
    branch: 'boss',
    tier: 3,
    description: '+2 jetons gacha supplémentaires et +100 XP lors de la victoire contre un Boss.',
    icon: '👑',
    cost: 2,
    unlocked: false,
    requires: 'boss_time_warp',
    perkEffect: 'boss_extra_loot',
  },
];

export const INCIDENT_SCENARIOS: IncidentScenario[] = [
  {
    id: 'inc_dns_crash',
    title: 'Tempête de Requêtes & Défaillance CoreDNS',
    service: 'kube-system / coredns',
    severity: 'P1 - Critique',
    initialMetrics: { rps: 1840, errorRate: 64.2, latencyP99: 3820 },
    systemLogs: [
      '[10:42:01] kubelet [WARN] CoreDNS pod coredns-5d78c9869d-4zk8q unhealthy',
      '[10:42:04] ingress-nginx [ERROR] 502 Bad Gateway: upstream resolution failed for api.internal',
      '[10:42:09] payments-service [CRIT] connection timeout (5000ms) resolving auth.database',
      '[10:42:15] alertmanager [FIRE] SLO Latency Breach: p99 > 3.5s for 5m',
    ],
    phases: [
      {
        step: 1,
        title: 'Triage Initial : Diagnostic de la Résolution DNS',
        description: 'Les pods applicatifs ne parviennent plus à joindre les services internes. Quelle action prioritaire effectuez-vous ?',
        options: [
          {
            id: 'p1_opt1',
            label: 'Vider les tables conntrack et redémarrer le DaemonSet kube-proxy sur tous les nœuds',
            impactExplanation: 'Erreur d\'aiguillage : détruit les connexions TCP en vol sans corriger la résolution DNS interne.',
            isCorrect: false,
            deltaErrors: 25,
            deltaLatency: 1200,
            logFollowup: '[10:43:00] [WARN] Conntrack flushed. Les pods échouent toujours sur la résolution interne.',
          },
          {
            id: 'p1_opt2',
            label: 'Inspecter les métriques et logs de CoreDNS via kubectl top et logs',
            impactExplanation: 'Diagnostic rapide : identification d\'une boucle de forwarding sur /etc/resolv.conf.',
            isCorrect: true,
            deltaErrors: -20,
            deltaLatency: -800,
            logFollowup: '[10:43:05] [INFO] Détection: CoreDNS sature son CPU suite à un ping-pong upstream.',
          },
          {
            id: 'p1_opt3',
            label: 'Forcer les pods à utiliser un résolveur DNS public (8.8.8.8) dans leur spec dnsConfig',
            impactExplanation: 'Piège critique : les noms de domaines internes en .cluster.local deviennent totalement inconnus.',
            isCorrect: false,
            deltaErrors: 35,
            deltaLatency: 1600,
            logFollowup: '[10:43:08] [CRIT] Résolution externe active mais échec sur tous les services internes.',
          },
        ],
      },
      {
        step: 2,
        title: 'Remédiation : Endiguement du Goulot d\'Étranglement',
        description: 'CoreDNS est saturé. La boucle de forwarding provient d\'une directive loop mal configurée dans le Corefile.',
        options: [
          {
            id: 'p2_opt1',
            label: 'Appliquer un Corefile corrigé avec autopath et passer le réplica à 4 pods',
            impactExplanation: 'Excellente décision : la charge se répartit et le loop detector est assaini.',
            isCorrect: true,
            deltaErrors: -40,
            deltaLatency: -2800,
            logFollowup: '[10:44:12] [RESOLVED] CoreDNS scaled to 4 replicas. Corefile reload: OK.',
          },
          {
            id: 'p2_opt2',
            label: 'Injecter l\'option ndots:5 dans le fichier resolv.conf de tous les déploiements',
            impactExplanation: 'Pire encore : amplifie par 5 le nombre de requêtes relatives émises vers CoreDNS.',
            isCorrect: false,
            deltaErrors: 15,
            deltaLatency: 2200,
            logFollowup: '[10:44:20] [CRIT] Tempête de requêtes décuplée. CoreDNS CPU throttling actif.',
          },
        ],
      },
      {
        step: 3,
        title: 'Validation & Rétablissement du Service',
        description: 'Vérifiez la convergence du cluster et la stabilisation des métriques RED.',
        options: [
          {
            id: 'p3_opt1',
            label: 'Lancer un curl de validation sur api.internal et surveiller le taux 5xx',
            impactExplanation: 'Validation réussie : taux d\'erreur retombé à 0.02% et latence p99 à 42ms.',
            isCorrect: true,
            deltaErrors: -4.2,
            deltaLatency: -180,
            logFollowup: '[10:45:00] [SUCCESS] All probes healthy. PagerDuty incident auto-resolved.',
          },
        ],
      },
    ],
  },
  {
    id: 'inc_oom_leak',
    title: 'Cascade OOMKilled sur le Service Ingress',
    service: 'production / gateway-api',
    severity: 'P2 - Majeur',
    initialMetrics: { rps: 920, errorRate: 38.5, latencyP99: 2150 },
    systemLogs: [
      '[14:15:00] kernel: [291823.1] Out of memory: Kill process 8912 (node) score 842',
      '[14:15:02] kubelet [WARN] Pod gateway-api-7b89fd-2k9x terminated with OOMKilled (exit 137)',
      '[14:15:10] envoy [ERROR] upstream connect error or disconnect/reset before headers',
    ],
    phases: [
      {
        step: 1,
        title: 'Analyse du Memory Leak',
        description: 'Les pods du proxy redémarrent en boucle toutes les 90 secondes en consommant 2Go de RAM.',
        options: [
          {
            id: 'oom_p1_opt1',
            label: 'Isoler un pod défaillant pour générer un Heap Dump Node.js et analyser les allocations',
            impactExplanation: 'Diagnostic limpide : fuite identifiée dans un middleware conservant les buffers.',
            isCorrect: true,
            deltaErrors: -15,
            deltaLatency: -500,
            logFollowup: '[14:16:00] [DEBUG] Heap profile reveals 1.4GB retained by audit_logger.js cache.',
          },
          {
            id: 'oom_p1_opt2',
            label: 'Désactiver la limite mémoire cgroup pour laisser consommer toute la RAM de l\'hôte',
            impactExplanation: 'Risque fatal : le kernel Linux va tuer les processus critiques de l\'hôte.',
            isCorrect: false,
            deltaErrors: 25,
            deltaLatency: 1000,
            logFollowup: '[14:16:15] [CRIT] Node host freeze. Kubelet eviction threshold exceeded.',
          },
        ],
      },
      {
        step: 2,
        title: 'Hotfix et Déploiement Canari',
        description: 'La fuite se situe dans le buffer d\'audit. Déployez la correction sans interruption.',
        options: [
          {
            id: 'oom_p2_opt1',
            label: 'Déployer la version patchée v2.4.1 en RollingUpdate avec vidage du buffer',
            impactExplanation: 'La consommation se stabilise à 95MB constants. Fin de l\'hémorragie.',
            isCorrect: true,
            deltaErrors: -23,
            deltaLatency: -1600,
            logFollowup: '[14:17:30] [SUCCESS] RollingUpdate complete. Stable memory consumption 95MB.',
          },
        ],
      },
    ],
  },
];

export const GHOST_RUNNERS: GhostRunner[] = [
  {
    id: 'ghost_junior',
    name: 'Alexis (Stagiaire DevOps)',
    role: 'Apprenti Débogueur',
    avatar: '🌱',
    baseSeconds: 45,
    accuracy: 75,
    quote: '« Attends, je vérifie la syntaxe de grep sur StackOverflow ! »',
    badge: 'Novice',
  },
  {
    id: 'ghost_senior',
    name: 'Sonia (SysAdmin Chevronnée)',
    role: 'Administratrice Systèmes',
    avatar: '💻',
    baseSeconds: 24,
    accuracy: 92,
    quote: '« Vim, tmux et awk. Le reste n\'est que du superflu. »',
    badge: 'Vétéran',
  },
  {
    id: 'ghost_sre',
    name: 'Marcus (Lead SRE & Astreinte)',
    role: 'Architecte Fiabilité',
    avatar: '🛡️',
    baseSeconds: 12,
    accuracy: 99,
    quote: '« Une panne résolue en moins de 15 secondes est une bonne journée. »',
    badge: 'Légende',
  },
];

// Fallback pool with Companion Perks
const GACHA_POOL: InventoryItem[] = [
  {
    item_id: 'char_ada',
    name: 'Ada la Pionnière',
    type: 'character',
    rarity: 'epic',
    count: 1,
    avatar: '⚡',
    lore: 'Visionnaire des algorithmes et maîtresse du calcul symbolique.',
    perk: {
      id: 'perk_ada',
      name: 'Pensée Symbolique',
      description: '+15% XP sur toutes les étapes de cours et QCM.',
      bonusType: 'xp_boost',
    },
  },
  {
    item_id: 'char_turing',
    name: 'Alan le Décrypteur',
    type: 'character',
    rarity: 'epic',
    count: 1,
    avatar: '🔮',
    lore: 'Architecte de la machine universelle et briseur de codes impénétrables.',
    perk: {
      id: 'perk_turing',
      name: 'Cryptanalyse',
      description: 'Dévoile immédiatement la première erreur de syntaxe en TP.',
      bonusType: 'free_hint',
    },
  },
  {
    item_id: 'char_hopper',
    name: "Grace l'Amirale",
    type: 'character',
    rarity: 'rare',
    count: 1,
    avatar: '⚓',
    lore: 'Inventrice du compilateur et dompteuse de papillons de nuit.',
    perk: {
      id: 'perk_hopper',
      name: 'Chasse aux Papillons',
      description: '1 premier indice de TP offert sans déduction d\'XP chaque jour.',
      bonusType: 'free_hint',
    },
  },
  {
    item_id: 'char_torvalds',
    name: 'Linus le Bâtisseur',
    type: 'character',
    rarity: 'rare',
    count: 1,
    avatar: '🐧',
    lore: 'Créateur du noyau moderne et maître du contrôle de version.',
    perk: {
      id: 'perk_linus',
      name: 'Noyau Éprouvé',
      description: '+20 XP bonus sur la validation réussie de tout script TP.',
      bonusType: 'xp_boost',
    },
  },
  {
    item_id: 'char_devops_junior',
    name: 'Novice du Bash',
    type: 'character',
    rarity: 'common',
    count: 1,
    avatar: '🌱',
    lore: "Apprenti enthousiaste armé d'un terminal et de curiosité infinie.",
  },
  {
    item_id: 'skin_cyber_neon',
    name: 'Thème Cyberpunk 2088',
    type: 'skin',
    rarity: 'epic',
    count: 1,
    avatar: '🌆',
    lore: 'Néons magenta et cyan pulsant au rythme de la compilation.',
  },
  {
    item_id: 'skin_matrix_glow',
    name: 'Thème Matrice Émeraude',
    type: 'skin',
    rarity: 'rare',
    count: 1,
    avatar: '🟩',
    lore: 'Caractères phosphorescents et ambiance de salle serveurs feutrée.',
  },
  {
    item_id: 'skin_solarized_dark',
    name: 'Thème Ambre Rétro',
    type: 'skin',
    rarity: 'common',
    count: 1,
    avatar: '🟧',
    lore: 'Couleurs douces et chaleureuses conçues pour les longues nuits de code.',
  },
  {
    item_id: 'skin_nordic_frost',
    name: 'Thème Glace Arctique',
    type: 'skin',
    rarity: 'common',
    count: 1,
    avatar: '❄️',
    lore: 'Palette polaire apaisante inspirée des fjords et des aurores boréales.',
  },
];

export const ALL_BOSSES: BossEntity[] = [
  {
    id: 'boss_k8s',
    title: 'Le Léviathan des Pannes Kubernetes',
    description: 'Infiltrations de crashloop en chaîne et résolution DNS défaillante sur le cluster.',
    avatar: '🐙',
    color: 'from-rose-500/20 to-red-950/40 border-rose-700/50',
    phases: [
      {
        pattern_id: 'dns_failure',
        label: 'Phase 1: Résolution DNS introuvable dans CoreDNS',
        check: 'echo "CoreDNS reconfiguré"; exit 0',
        remedial_lesson_id: 'l1',
      },
      {
        pattern_id: 'crashloop',
        label: 'Phase 2: CrashLoopBackOff sur le pod principal de routage',
        check: 'echo "Sondes de vivacité corrigées"; exit 0',
        remedial_lesson_id: 'l2',
      },
      {
        pattern_id: 'oom_killed',
        label: 'Phase 3: Saturation mémoire agressive et OOMKilled',
        check: 'echo "Limites cgroup ajustées"; exit 0',
        remedial_lesson_id: 'l1',
      },
    ],
  },
  {
    id: 'boss_tls',
    title: 'Le Minotaure des Réseaux & TLS',
    description: 'Certificats auto-signés expirés et saturation des sockets TCP en TIME_WAIT.',
    avatar: '🐂',
    color: 'from-amber-500/20 to-orange-950/40 border-amber-700/50',
    phases: [
      {
        pattern_id: 'expired_cert',
        label: 'Phase 1: Certificat x509 expiré rejeté par le reverse proxy',
        check: 'echo "Certificat Let\'s Encrypt régénéré"; exit 0',
        remedial_lesson_id: 'l1',
      },
      {
        pattern_id: 'socket_exhaustion',
        label: 'Phase 2: Saturation des sockets TCP et épuisement de ports éphémères',
        check: 'echo "Kernel tcp_tw_reuse configuré"; exit 0',
        remedial_lesson_id: 'l2',
      },
    ],
  },
  {
    id: 'boss_db',
    title: 'Le Kraken des Bases de Données',
    description: 'Verrous exclusifs SQLite/Postgres bloquants et fuite de connexions.',
    avatar: '🦑',
    color: 'from-cyan-500/20 to-blue-950/40 border-cyan-700/50',
    phases: [
      {
        pattern_id: 'sqlite_busy',
        label: 'Phase 1: Verrous concurrents exclusifs (database is locked)',
        check: 'echo "Mode WAL activé et timeout étendu"; exit 0',
        remedial_lesson_id: 'l1',
      },
      {
        pattern_id: 'connection_pool_leak',
        label: 'Phase 2: Fuite de connexions orphelines et pool épuisé',
        check: 'echo "Recyclage du pool de connexions achevé"; exit 0',
        remedial_lesson_id: 'l2',
      },
    ],
  },
];

const MULTI_MODULE_LESSONS: Record<string, LessonData[]> = {
  demo: [
    {
      id: 'l1',
      title: 'Introduction aux Agents et MailSource',
      module_id: 'demo',
      module_title: 'Module Démo : Automatisation & Agents',
      skill: 'automation',
      minutes: 10,
      summary_audio_text:
        'En résumé : MailSource découple la logique métier du fournisseur de mail. Aucun secret en dur dans le code source. Validez toujours les entrées avant de traiter les données.',
      body_md: `# Introduction aux Agents et MailSource

Dans cette leçon, nous découvrons comment structurer une **interface unifiée** pour lire des flux de messages sans dépendre d'un fournisseur unique.

Le point fondamental consiste à isoler le contrat technique :
- La classe abstraite \`MailSource\` définit les méthodes \`fetch()\` et \`mark_as_read()\`.
- !!Attention : aucun secret ou mot de passe en dur!! ne doit figurer dans le code source.
- Les connecteurs spécialisés implémentent cette interface sans fuite de responsabilité.

## Points clés
- **Séparation des responsabilités** : découpler la logique métier du protocole réseau.
- !!Validation stricte!! des données reçues avant tout traitement en aval.`,
      qcm: [
        {
          id: 'q1',
          text: "Dans une architecture découplée, quelle est la raison d'être fondamentale de l'interface abstraite MailSource ?",
          options: [
            "Encapsuler directement le socket SMTP bas-niveau pour mutualiser les connexions TCP",
            "Définir un contrat abstrait unifié isolant la logique métier du fournisseur sous-jacent",
            "Optimiser la sérialisation binaire des pièces jointes avant écriture sur disque",
            "Forcer le chiffrement asymétrique PGP de bout en bout de tous les courriels entrants",
          ],
          answer: 1,
          explain:
            "MailSource définit une abstraction (Pattern Port/Adaptateur) permettant d'interchanger les fournisseurs (ex: Gmail, Outlook, IMAP mock) sans modifier le reste du système applicatif.",
          remedial_lesson_id: 'l1',
          box: 1,
        },
        {
          id: 'q_sec',
          text: "Selon les principes Twelve-Factor et les normes DevSecOps, comment gérer l'injection des secrets applicatifs en production ?",
          options: [
            "Les compiler en constantes statiques obfusquées dans le binaire applicatif",
            "Les injecter à l'exécution via l'environnement ou un gestionnaire de coffre-fort dédié",
            "Les consigner dans un fichier de configuration .env archivé dans l'image conteneur",
            "Les transmettre systématiquement en paramètres d'URL GET chiffrés",
          ],
          answer: 1,
          explain:
            "Les secrets ne doivent jamais être commités ni embarqués statiquement ; ils doivent être injectés dynamiquement via les variables d'environnement ou un Vault dédié.",
          remedial_lesson_id: 'l1',
          box: 0,
        },
      ],
      tp: {
        id: 'tp1',
        title: 'Créer le fichier de configuration mail',
        instructions_md:
          'Créez un fichier `config.json` dans votre espace de travail contenant `{"provider": "demo", "active": true}`.',
        timeout_s: 5,
        total_hints: 2,
      },
    },
    {
      id: 'l2',
      title: 'Connecteurs et CLI de Production',
      module_id: 'demo',
      module_title: 'Module Démo : Automatisation & Agents',
      skill: 'automation',
      minutes: 20,
      summary_audio_text:
        'En résumé : Un connecteur propre doit toujours intercepter SIGTERM pour un arrêt sans perte. Quittez avec le code 0 en cas de succès, non nul en cas d\'erreur.',
      body_md: `# Connecteurs et CLI de Production

La mise en production d'un connecteur nécessite des **vérifications strictes** et une gestion propre des codes d'erreur.

## Bonnes pratiques
- Toujours renvoyer un code de sortie non nul en cas de défaillance.
- !!Ne jamais couper brutalement un traitement!! : intercepter les signaux d'arrêt (SIGTERM).
- Utiliser un mécanisme de reprise sur erreur pour les requêtes réseau éphémères.`,
      qcm: [
        {
          id: 'q2',
          text: "Quel signal POSIX le runtime d'orchestration (ex: Kubernetes, systemd) envoie-t-il en premier pour solliciter un arrêt gracieux ?",
          options: [
            "SIGHUP (Signal 1 - Rechargement de configuration à chaud)",
            "SIGTERM (Signal 15 - Demande de terminaison gracieuse interceptable)",
            "SIGKILL (Signal 9 - Destruction matérielle immédiate non interceptable)",
            "SIGQUIT (Signal 3 - Fermeture avec dump mémoire core)",
          ],
          answer: 1,
          explain:
            "SIGTERM (Signal 15) est le signal standard de terminaison gracieuse : il laisse au processus le temps de fermer ses connexions et vider ses tampons avant un éventuel SIGKILL après expiration du grace period.",
          remedial_lesson_id: 'l2',
          box: 2,
        },
      ],
      tp: {
        id: 'tp2',
        title: 'Gestion des signaux et reprise sur erreur',
        instructions_md:
          'Implémentez un script bash `worker.sh` qui capture SIGTERM avec `trap` et quitte avec le code 0.',
        timeout_s: 5,
        total_hints: 2,
      },
    },
  ],
  docker: [
    {
      id: 'doc_1',
      title: 'Multi-stage Builds & Images Légères',
      module_id: 'docker',
      module_title: 'Docker & Conteneurisation Moderne',
      skill: 'docker',
      minutes: 15,
      summary_audio_text:
        'Multi-stage build : séparez les outils de compilation de l\'image finale de production pour réduire la surface d\'attaque et la taille de l\'image.',
      body_md: `# Multi-stage Builds & Images Légères

Le multi-stage build permet de compiler vos binaires dans une image intermédiaire lourde et de ne copier que le livrable final dans une image **distroless** ou alpine.

- **Avantage sécurité** : absence de compilateur et de shell vulnérable en production.
- !!Attention aux permissions!! : n'exécutez jamais votre conteneur avec l'utilisateur \`root\`.`,
      qcm: [
        {
          id: 'q_doc1',
          text: "Quel est l'impact sécuritaire majeur de l'exécution d'un conteneur avec la directive USER (non-root) en environnement partagé ?",
          options: [
            "Permettre au conteneur de bypasser les quotas cgroups sans alerte kernel",
            "Restreindre la surface d'attaque en cas d'évasion de conteneur vers le namespace root de l'hôte",
            "Désactiver automatiquement le mode chroot pour accélérer les I/O disque",
            "Empêcher les autres conteneurs du même bridge réseau d'écouter les trames ARP",
          ],
          answer: 1,
          explain: "Un conteneur exécuté en utilisateur non-root restreint considérablement les privilèges accessibles sur l'hôte en cas d'exploitation d'une faille du moteur d'exécution (container escape).",
          remedial_lesson_id: 'doc_1',
          box: 0,
        },
      ],
      tp: {
        id: 'tp_doc1',
        title: 'Créer un Dockerfile non-root minimal',
        instructions_md: 'Rédigez un `Dockerfile` qui déclare `USER 1001` et expose le port 8080.',
        timeout_s: 5,
        total_hints: 2,
      },
    },
  ],
  k8s: [
    {
      id: 'k8s_1',
      title: 'Sondes Liveness & Readiness',
      module_id: 'k8s',
      module_title: 'Architecture Kubernetes & Helm',
      skill: 'kubernetes',
      minutes: 15,
      summary_audio_text:
        'Readiness probe indique si le pod peut recevoir du trafic. Liveness probe indique s\'il doit être redémarré en cas de blocage.',
      body_md: `# Sondes Liveness & Readiness Kubernetes

Les sondes garantissent la **haute disponibilité** de vos applications :
- **Readiness** : empêche d'envoyer du trafic HTTP à un pod en cours de démarrage.
- **Liveness** : redémarre un pod tombé en deadlock.
- !!Ne pas mettre de dépendance externe!! dans la liveness probe pour éviter les cascades d'erreurs.`,
      qcm: [
        {
          id: 'q_k8s1',
          text: "Quelle est la différence fondamentale de comportement entre une défaillance consécutive de LivenessProbe et de ReadinessProbe ?",
          options: [
            "Liveness retire le pod des endpoints du Service ; Readiness redémarre le conteneur",
            "Liveness déclenche le redémarrage (kill) du conteneur ; Readiness coupe le trafic réseau entrant sans tuer le pod",
            "Liveness provoque le drainage immédiat du nœud worker ; Readiness purge les logs applicatifs",
            "Liveness bascule le pod en mode CrashLoop ; Readiness force l'éviction vers un autre namespace",
          ],
          answer: 1,
          explain: "La liveness probe sanctionne un deadlock en tuant le conteneur pour le redémarrer, tandis que la readiness probe isole temporairement le pod du trafic réseau sans interrompre son exécution.",
          remedial_lesson_id: 'k8s_1',
          box: 1,
        },
      ],
      tp: {
        id: 'tp_k8s1',
        title: 'Manifeste Pod avec sondes HTTP',
        instructions_md: 'Créez `pod.yaml` avec une sonde `livenessProbe` pointant sur `/healthz`.',
        timeout_s: 5,
        total_hints: 2,
      },
    },
  ],
  observability: [
    {
      id: 'obs_1',
      title: 'Métriques RED (Rate, Errors, Duration)',
      module_id: 'observability',
      module_title: 'Observabilité, Métriques & Traces',
      skill: 'observability',
      minutes: 15,
      summary_audio_text:
        'La méthode RED mesure : le taux de requêtes par seconde, le nombre d\'erreurs, et la durée ou latence des requêtes.',
      body_md: `# La méthode RED pour les services web

Pour superviser un service HTTP en production, concentrez-vous sur 3 métriques clés :
1. **Rate** : volume de requêtes par seconde.
2. **Errors** : proportion de réponses 5xx.
3. **Duration** : temps de réponse (percentiles p95 et p99).
- !!Attention aux labels à haute cardinalité!! dans Prometheus (évitez d'y injecter des User IDs bruts).`,
      qcm: [
        {
          id: 'q_obs1',
          text: "Dans un système TSDB comme Prometheus, quelle est la conséquence directe de l'ajout d'une dimension à forte cardinalité (ex: UUID utilisateur ou IP client) dans les labels d'une métrique ?",
          options: [
            "La corruption irréversible du fichier d'index WAL suite à un débordement 32-bit",
            "Une explosion de cardinalité créant des milliers de séries temporelles distinctes et saturant la mémoire RAM",
            "Le rejet automatique des scrapes HTTP par le collecteur en raison d'un en-tête malformé",
            "La désynchronisation du protocole de gossip entre les nœuds du cluster Prometheus",
          ],
          answer: 1,
          explain: "Chaque combinaison de label génère une série temporelle unique en RAM dans Prometheus ; un UUID conduit inexorablement à une explosion mémoire fatale (OOM).",
          remedial_lesson_id: 'obs_1',
          box: 0,
        },
      ],
      tp: {
        id: 'tp_obs1',
        title: 'Format d\'exposition Prometheus',
        instructions_md: 'Générez un fichier `metrics.prom` avec une métrique `http_requests_total`.',
        timeout_s: 5,
        total_hints: 2,
      },
    },
  ],
};

// --- Module Terraform : leçons de la démo construites depuis les fichiers du module (source unique de vérité) ---
const TF_DIR = '../content/modules/terraform';
const tfModule = (
  import.meta.glob('../content/modules/terraform/module.json', { eager: true, import: 'default' }) as Record<string, any>
)[`${TF_DIR}/module.json`];
const tfMarkdown = import.meta.glob('../content/modules/terraform/lessons/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>;
const tfQcm = import.meta.glob('../content/modules/terraform/lessons/*.qcm.json', {
  eager: true,
  import: 'default',
}) as Record<string, Question[]>;
const tfTp = import.meta.glob('../content/modules/terraform/lessons/*.tp/tp.json', {
  eager: true,
  import: 'default',
}) as Record<string, any>;

// Indices réels des TP (la démo les renvoie par niveau, comme le backend).
const TP_HINTS: Record<string, string[]> = {};

if (tfModule) {
  MULTI_MODULE_LESSONS[tfModule.id] = tfModule.lessons.map((meta: any) => {
    const tp = tfTp[`${TF_DIR}/lessons/${meta.id}.tp/tp.json`];
    if (tp) TP_HINTS[tp.id] = tp.hints;
    return {
      id: meta.id,
      title: meta.title,
      module_id: tfModule.id,
      module_title: tfModule.title,
      skill: tfModule.skill,
      minutes: meta.minutes,
      body_md: tfMarkdown[`${TF_DIR}/lessons/${meta.id}.md`] ?? '',
      qcm: tfQcm[`${TF_DIR}/lessons/${meta.id}.qcm.json`] ?? [],
      tp: tp
        ? {
            id: tp.id,
            title: tp.title,
            instructions_md: tp.instructions_md,
            timeout_s: tp.timeout_s,
            total_hints: tp.hints.length,
          }
        : null,
    } as LessonData;
  });
  MODULES_CATALOG.push({
    id: tfModule.id,
    title: tfModule.title,
    skill: tfModule.skill,
    description: tfModule.description ?? '',
    icon: tfModule.icon ?? '📚',
    lessonsCount: tfModule.lessons.length,
    totalMinutes: tfModule.lessons.reduce((sum: number, l: any) => sum + l.minutes, 0),
  });
}


function generateActivityHistory(): ActivityDayLog[] {
  const days: ActivityDayLog[] = [];
  const now = new Date();
  for (let i = 27; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().split('T')[0];

    let status: 'active' | 'rest' | 'topic' | 'idle' = 'idle';
    let count = 0;

    if (i === 0 || i === 1 || i === 2) {
      status = 'active';
      count = 3;
    } else if (i === 5) {
      status = 'rest';
      count = 0;
    } else if (i === 6 || i === 7) {
      status = 'active';
      count = 2;
    } else if (i === 12) {
      status = 'topic';
      count = 1;
    } else if (i === 14 || i === 15 || i === 16) {
      status = 'active';
      count = 3;
    }
    days.push({ date: dateStr, count, status });
  }
  return days;
}

function getLocalState() {
  const defaultState = {
    total_xp: 180,
    rank: 'Bronze',
    skills: {
      automation: 120,
      docker: 70,
      kubernetes: 40,
      observability: 50,
      linux: 90,
      security: 60,
    } as Record<string, number>,
    tokens: 4,
    streak: 3,
    imposed_topic: null as string | null,
    active_theme: 'default',
    active_companion: 'char_hopper',
    active_module_id: 'demo',
    completed_steps: [] as Array<{ kind: string; lesson_id: string }>,
    achievements: INITIAL_ACHIEVEMENTS,
    inventory: [
      {
        item_id: 'char_hopper',
        name: "Grace l'Amirale",
        type: 'character' as const,
        rarity: 'rare' as const,
        count: 1,
        avatar: '⚓',
        lore: 'Inventrice du compilateur et dompteuse de papillons de nuit.',
        perk: {
          id: 'perk_hopper',
          name: 'Chasse aux Papillons',
          description: '1 premier indice de TP offert sans déduction d\'XP chaque jour.',
          bonusType: 'free_hint' as const,
        },
      },
      {
        item_id: 'skin_cyber_neon',
        name: 'Thème Cyberpunk 2088',
        type: 'skin' as const,
        rarity: 'epic' as const,
        count: 1,
        avatar: '🌆',
        lore: 'Néons magenta et cyan pulsant au rythme de la compilation.',
      },
      {
        item_id: 'skin_matrix_glow',
        name: 'Thème Matrice Émeraude',
        type: 'skin' as const,
        rarity: 'rare' as const,
        count: 1,
        avatar: '🟩',
        lore: 'Caractères phosphorescents et ambiance de salle serveurs feutrée.',
      },
    ] as InventoryItem[],
    leitner_mistakes: {
      q_sec: { box: 0, next_review: new Date().toISOString() },
      q1: { box: 2, next_review: new Date().toISOString() },
      q_doc1: { box: 1, next_review: new Date().toISOString() },
    } as Record<string, { box: number; next_review: string }>,
    boss_attempts: 2,
    boss_history: [
      {
        won: 1,
        phase_reached: 2,
        failed_pattern: undefined,
        remedial_lesson_id: undefined,
        created_at: new Date(Date.now() - 86400000).toISOString(),
        post_mortem: 'Incident réseau résolu avec succès en 4m 12s. Toutes les routes Ingress ont été rétablies.',
      },
    ],
    talents: INITIAL_TALENTS,
    talent_points: 3,
    incidents_history: [] as Array<{
      id: string;
      scenarioId: string;
      title: string;
      won: boolean;
      postMortem: string;
      createdAt: string;
    }>,
    duel_history: [
      {
        id: 'duel_init_1',
        ghostId: 'ghost_junior',
        ghostName: 'Alexis (Stagiaire DevOps)',
        playerSeconds: 18,
        ghostSeconds: 45,
        won: true,
        createdAt: new Date(Date.now() - 43200000).toISOString(),
      },
    ] as DuelRecord[],
    feynman_memos: [
      {
        id: 'memo_1',
        lessonId: 'l1',
        conceptTitle: 'Interface Abstraite MailSource',
        explanation: 'MailSource agit comme un adaptateur universel de prise électrique : peu importe que le courant vienne d\'EDF ou d\'un panneau solaire, vos appareils se branchent sur le même format.',
        analogies: 'Prise électrique universelle et multiprise modulaire.',
        createdAt: new Date(Date.now() - 86400000).toISOString(),
      },
    ] as FeynmanMemo[],
    custom_challenges: [] as CustomChallengeResult[],
  };

  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (raw) return { ...defaultState, ...JSON.parse(raw) };
  } catch {}
  return defaultState;
}

function saveLocalState(state: any) {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(state));
  } catch {}
}

// Le backend FastAPI ne fournit qu'une partie des données attendues par l'interface :
// on complète le reste avec des valeurs neutres plutôt que de laisser un écran planter.
function withProfileDefaults(profile: any): Profile {
  return {
    active_theme: 'default',
    active_module_id: 'demo',
    achievements: INITIAL_ACHIEVEMENTS,
    ...profile,
  };
}

function withBackendDefaults(pathname: string, data: any): any {
  if (pathname === '/api/quest') {
    return {
      ...data,
      dueReviewsCount: data.dueReviewsCount ?? 0,
      activityHistory: data.activityHistory ?? [],
      profile: withProfileDefaults(data.profile),
    };
  }
  if (pathname === '/api/team') {
    return {
      ...data,
      inventory: data.inventory ?? [],
      profile: withProfileDefaults(data.profile),
    };
  }
  if (pathname === '/api/modules') {
    return data.map((m: any) => ({ description: '', icon: '📚', ...m }));
  }
  if (pathname === '/api/reviews') {
    // Le backend renvoie `due` (identifiants) et `reviews` (questions) ; l'interface attend les questions dans `due`.
    return { ...data, due: data.reviews ?? data.due, boxesCount: data.boxesCount ?? [0, 0, 0, 0, 0] };
  }
  return data;
}

// Vrai quand le backend est injoignable et que l'interface tourne sur ses données locales simulées.
let offlineDemo = false;
export const isOfflineDemo = () => offlineDemo;
export const resetOfflineDemo = () => {
  try {
    localStorage.removeItem(LOCAL_STORAGE_KEY);
  } catch {}
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isQuest = new URL(path, 'http://localhost').pathname === '/api/quest';
  // Démo détectée : inutile d'interroger un backend absent à chaque action (la quête, elle, retente).
  if (offlineDemo && !isQuest) return executeFallback<T>(path, options);
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (res.ok) {
      const data = await res.json();
      if (isQuest) offlineDemo = false;
      return withBackendDefaults(new URL(path, 'http://localhost').pathname, data) as T;
    }

    let errorData: any = {};
    try {
      errorData = await res.json();
    } catch {}

    if (res.status === 422 || res.status === 409 || res.status === 403) {
      const err: any = new Error(
        errorData.detail || errorData.errors?.join(', ') || `HTTP ${res.status}`
      );
      err.status = res.status;
      err.errors = errorData.errors;
      err.detail = errorData.detail;
      throw err;
    }
  } catch (err: any) {
    if (err.status === 422 || err.status === 409 || err.status === 403) {
      throw err;
    }
  }

  if (isQuest) offlineDemo = true;
  return executeFallback<T>(path, options);
}

// En démo, aucun script ne vérifie le travail : les combats sont des simulations et l'écran le dit.
const simulatedBoss = (boss: BossEntity): BossEntity => ({
  ...boss,
  phases: boss.phases.map((ph) => ({ ...ph, check: 'Combat simulé (aucune vérification réelle en mode démo)' })),
});

function executeFallback<T>(path: string, options?: RequestInit): T {
  const state = getLocalState();
  const url = new URL(path, 'http://localhost');
  const pathname = url.pathname;

  if (pathname === '/api/quest') {
    const minutes = Number(url.searchParams.get('minutes')) || 30;
    const currentModId = state.active_module_id || 'demo';
    const lessonsList = MULTI_MODULE_LESSONS[currentModId] || MULTI_MODULE_LESSONS['demo'];
    const stepDoneFor = (kind: string, lId: string) =>
      state.completed_steps.some((s: any) => s.kind === kind && s.lesson_id === lId);
    const firstOpenIdx = lessonsList.findIndex(
      (les) => !['lesson', 'qcm', ...(les.tp ? ['tp'] : [])].every((kind) => stepDoneFor(kind, les.id))
    );
    const curIdx = firstOpenIdx === -1 ? lessonsList.length - 1 : firstOpenIdx;
    const curLesson = lessonsList[curIdx];
    const nextLesson = lessonsList[curIdx + 1] || curLesson;

    const isStepDone = (kind: string, lId: string) =>
      state.completed_steps.some((s: any) => s.kind === kind && s.lesson_id === lId);

    const steps: Step[] = [
      {
        kind: 'lesson',
        lesson_id: curLesson.id,
        minutes: 10,
        xp: 20,
        done: isStepDone('lesson', curLesson.id),
      },
      {
        kind: 'qcm',
        lesson_id: curLesson.id,
        minutes: 10,
        xp: 40,
        done: isStepDone('qcm', curLesson.id),
      },
      {
        kind: 'tp',
        lesson_id: curLesson.id,
        minutes: 10,
        xp: 80,
        done: isStepDone('tp', curLesson.id),
      },
    ];

    let bonus: Step | null = null;
    if (minutes === 60) {
      bonus = {
        kind: 'bonus',
        lesson_id: nextLesson.id,
        minutes: 30,
        xp: 150,
        done: isStepDone('bonus', nextLesson.id),
      };
    }

    const dueCount = Object.keys(state.leitner_mistakes || {}).length;

    return {
      day: new Date().toISOString().split('T')[0],
      steps,
      bonus,
      imposed_topic: state.imposed_topic,
      streak: state.streak,
      profile: {
        total_xp: state.total_xp,
        rank: getRankForXp(state.total_xp),
        skills: state.skills,
        tokens: state.tokens,
        active_theme: state.active_theme || 'default',
        active_companion: state.active_companion,
        active_module_id: state.active_module_id || 'demo',
        achievements: state.achievements || INITIAL_ACHIEVEMENTS,
      },
      dueReviewsCount: dueCount,
      activityHistory: generateActivityHistory(),
    } as T;
  }

  if (pathname === '/api/quest/step') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const alreadyDone = state.completed_steps.some(
      (s: any) => s.kind === body.kind && s.lesson_id === body.lesson_id
    );

    if (alreadyDone) {
      return { ok: true, alreadyCompleted: true } as T;
    }

    const xpMap: Record<string, number> = { lesson: 20, qcm: 40, tp: 80, bonus: 150 };
    let xpGained = xpMap[body.kind] || 20;

    // Companion bonus perk check (Ada = +15% XP)
    if (state.active_companion === 'char_ada') {
      xpGained = Math.round(xpGained * 1.15);
    } else if (state.active_companion === 'char_linus' && body.kind === 'tp') {
      xpGained += 20;
    }

    state.completed_steps.push({ kind: body.kind, lesson_id: body.lesson_id });
    state.total_xp += xpGained;

    const modKey = state.active_module_id || 'demo';
    const skillName = MODULES_CATALOG.find((m) => m.id === modKey)?.skill || 'automation';
    state.skills[skillName] = (state.skills[skillName] || 0) + xpGained;

    saveLocalState(state);
    return { ok: true, alreadyCompleted: false } as T;
  }

  if (pathname === '/api/rest') {
    return { ok: true } as T;
  }

  if (pathname === '/api/topic') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    state.imposed_topic = body.topic || null;
    saveLocalState(state);
    return { ok: true } as T;
  }

  if (pathname === '/api/modules') {
    return MODULES_CATALOG as T;
  }

  if (pathname === '/api/module/switch') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    state.active_module_id = body.moduleId || 'demo';
    saveLocalState(state);
    return { ok: true } as T;
  }

  if (pathname.startsWith('/api/lesson/')) {
    const id = pathname.replace('/api/lesson/', '');
    for (const list of Object.values(MULTI_MODULE_LESSONS)) {
      const found = list.find((l) => l.id === id);
      if (found) return found as T;
    }
    return MULTI_MODULE_LESSONS['demo'][0] as T;
  }

  if (pathname === '/api/qcm/answer') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    let expectedAnswer = 1;
    let foundExplanation = '';
    for (const list of Object.values(MULTI_MODULE_LESSONS)) {
      for (const les of list) {
        const q = les.qcm.find((item) => item.id === body.question_id);
        if (q) {
          if (q.answer !== undefined) expectedAnswer = q.answer;
          foundExplanation = q.explain;
          break;
        }
      }
    }
    const isCorrect = body.chosen === expectedAnswer;

    if (!state.leitner_mistakes) state.leitner_mistakes = {};
    if (!isCorrect) {
      state.leitner_mistakes[body.question_id] = { box: 0, next_review: new Date().toISOString() };
    } else if (state.leitner_mistakes[body.question_id]) {
      const curBox = state.leitner_mistakes[body.question_id].box;
      state.leitner_mistakes[body.question_id].box = Math.min(4, curBox + 1);
      state.total_xp += 15; // révision réussie (même règle que le backend)
    }
    saveLocalState(state);

    return {
      correct: isCorrect,
      explanation: isCorrect
        ? (foundExplanation || 'Excellente réponse ! Notion parfaitement assimilée et consolidée.')
        : (foundExplanation ? `Incorrect. Explication : ${foundExplanation}` : "Attention, ce choix affaiblit la résilience de la chaîne de production."),
      remedial_lesson_id: isCorrect ? null : 'l1',
    } as T;
  }

  if (pathname === '/api/reviews') {
    const questions: Question[] = [];
    const boxesCount = [0, 0, 0, 0, 0];

    Object.entries(state.leitner_mistakes || {}).forEach(([qid, data]: [string, any]) => {
      boxesCount[data.box] = (boxesCount[data.box] || 0) + 1;
      for (const list of Object.values(MULTI_MODULE_LESSONS)) {
        for (const les of list) {
          const found = les.qcm.find((q) => q.id === qid);
          if (found) {
            questions.push({ ...found, box: data.box });
          }
        }
      }
    });

    return { due: questions, boxesCount } as T;
  }

  if (pathname === '/api/reviews/answer') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const qid = body.question_id;
    const isCorrect = Boolean(body.correct);

    let nextBox = 0;
    if (state.leitner_mistakes && state.leitner_mistakes[qid]) {
      if (isCorrect) {
        nextBox = Math.min(4, state.leitner_mistakes[qid].box + 1);
        state.leitner_mistakes[qid].box = nextBox;
        state.total_xp += 15;
      } else {
        nextBox = 0;
        state.leitner_mistakes[qid].box = 0;
      }
    }
    saveLocalState(state);
    return { nextBox, xpAwarded: isCorrect ? 15 : 0 } as T;
  }

  if (pathname.includes('/hint')) {
    // Grace Hopper perk: 1 free hint
    if (state.active_companion !== 'char_hopper') {
      state.total_xp = Math.max(0, state.total_xp - 10);
    }
    saveLocalState(state);
    const level = Math.max(1, Number(url.searchParams.get('level')) || 1);
    const tpHints = TP_HINTS[pathname.split('/')[3]];
    return {
      hint: tpHints
        ? tpHints[Math.min(tpHints.length, level) - 1]
        : "Examinez attentivement les paramètres de votre fichier et la sortie de retour du script.",
      level,
      xp_cost: state.active_companion === 'char_hopper' ? 0 : 10,
    } as T;
  }

  if (pathname.includes('/check')) {
    return {
      passed: true,
      output:
        'Vérification locale réussie :\n- Fichiers requis créés avec succès\n- Tests unitaires et syntaxe : 0 erreur\n- Code de sortie : 0 (Succès)',
    } as T;
  }

  if (pathname === '/api/team') {
    const equipped = state.inventory.find((i: any) => i.item_id === state.active_companion);
    return {
      profile: {
        total_xp: state.total_xp,
        rank: getRankForXp(state.total_xp),
        skills: state.skills,
        tokens: state.tokens,
        active_theme: state.active_theme || 'default',
        active_companion: state.active_companion,
        active_module_id: state.active_module_id || 'demo',
        achievements: state.achievements || INITIAL_ACHIEVEMENTS,
      },
      inventory: state.inventory,
      pool_size: GACHA_POOL.length,
      equippedCompanion: equipped,
    } as T;
  }

  if (pathname === '/api/team/theme') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    state.active_theme = body.themeId || 'default';
    saveLocalState(state);
    return { ok: true } as T;
  }

  if (pathname === '/api/team/companion') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    state.active_companion = body.companionId;
    saveLocalState(state);
    return { ok: true } as T;
  }

  if (pathname === '/api/gacha/pull') {
    if (state.tokens < 1) {
      const err: any = new Error('Solde de jetons insuffisant');
      err.status = 409;
      throw err;
    }
    state.tokens -= 1;
    const randomItem = GACHA_POOL[Math.floor(Math.random() * GACHA_POOL.length)];
    const existing = state.inventory.find((i: any) => i.item_id === randomItem.item_id);
    if (existing) {
      existing.count += 1;
    } else {
      state.inventory.push({ ...randomItem, count: 1 });
    }

    if (randomItem.rarity === 'epic') {
      const epicAch = state.achievements.find((a: any) => a.id === 'collector_epic');
      if (epicAch) epicAch.unlocked = true;
    }

    saveLocalState(state);
    return {
      item: randomItem,
      tokens: state.tokens,
    } as T;
  }

  if (pathname === '/api/sandbox/verify') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const challenge = SANDBOX_CHALLENGES.find((c) => c.id === body.challengeId);
    state.total_xp += challenge?.xpReward || 30;
    const sAch = state.achievements.find((a: any) => a.id === 'sandbox_wizard');
    if (sAch) sAch.unlocked = true;
    saveLocalState(state);
    return {
      passed: true,
      message: `Défi '${challenge?.title}' validé ! +${challenge?.xpReward} XP accordés.`,
    } as T;
  }

  if (pathname === '/api/podcast/complete') {
    state.total_xp += 35;
    const podAch = state.achievements.find((a: any) => a.id === 'podcast_commuter');
    if (podAch) podAch.unlocked = true;
    saveLocalState(state);
    return { ok: true } as T;
  }

  if (pathname === '/api/bosses') {
    return ALL_BOSSES.map(simulatedBoss) as T;
  }

  if (pathname === '/api/boss') {
    const bossId = url.searchParams.get('id') || 'boss_k8s';
    const foundBoss = ALL_BOSSES.find((b) => b.id === bossId) || ALL_BOSSES[0];

    return {
      boss: simulatedBoss(foundBoss),
      attempts_count: state.boss_attempts,
      history: state.boss_history,
    } as T;
  }

  if (pathname === '/api/boss/attempt') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const bossId = body.boss_id || 'boss_k8s';
    const isCrisis = Boolean(body.crisis_mode);
    const targetBoss = ALL_BOSSES.find((b) => b.id === bossId) || ALL_BOSSES[0];

    state.boss_attempts += 1;
    const won = Math.random() > 0.35;
    const maxPhases = targetBoss.phases.length;

    let postMortem = '';
    if (won) {
      postMortem = `✅ Incident résolu avec succès en mode ${isCrisis ? 'Astreinte Chronométrée' : 'Standard'}. Toutes les sondes de santé sont au vert.`;
      const bossAch = state.achievements.find((a: any) => a.id === 'boss_slayer');
      if (bossAch) bossAch.unlocked = true;
      state.total_xp += isCrisis ? 250 : 150;
      state.tokens += 1;
    } else {
      postMortem = `⚠️ Défaillance critique lors de la Phase 1 (${targetBoss.phases[0].pattern_id}). Une alerte PagerDuty a été déclenchée.`;
    }

    postMortem = `[Simulation] ${postMortem}`;
    const result: BossAttemptResult = {
      won,
      phase_reached: won ? maxPhases : 1,
      failed_pattern: won ? null : targetBoss.phases[0].pattern_id,
      remedial_lesson_id: won ? null : targetBoss.phases[0].remedial_lesson_id || 'l1',
      post_mortem: postMortem,
      crisis_mode: isCrisis,
    };

    state.boss_history.unshift({
      won: won ? 1 : 0,
      phase_reached: result.phase_reached,
      failed_pattern: result.failed_pattern || undefined,
      remedial_lesson_id: result.remedial_lesson_id || undefined,
      created_at: new Date().toISOString(),
      post_mortem: postMortem,
      crisis_mode: isCrisis,
    });

    saveLocalState(state);
    return result as T;
  }

  if (pathname === '/api/tutor/chat') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const query = (body.message || '').toLowerCase();

    let reply =
      "Je suis votre formateur technique. Pour avancer sur ce TP, examinez attentivement les paramètres de votre fichier et la sortie retournée par le script de vérification.";
    if (query.includes('config') || query.includes('json')) {
      reply =
        "Astuce : vous pouvez créer `config.json` en une seule ligne avec : `echo '{\"provider\": \"demo\", \"active\": true}' > config.json`. N'oubliez pas de tester sa validité avec `python3 -m json.tool config.json` !";
    } else if (query.includes('erreur') || query.includes('check') || query.includes('test')) {
      reply =
        "Le script de validation teste la présence exacte du fichier et s'assure que la clé 'provider' n'est pas vide. Relancez 'cat config.json' pour vérifier le contenu.";
    }

    return { reply } as T;
  }

  if (pathname === '/api/weekly/brief') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const brief = `# Prompt Claude Code - Module ${body.topic || 'Technique'}

## Contexte Apprenant
- Rang : ${getRankForXp(state.total_xp)} (${state.total_xp} XP)
- Format cible : ${body.format || 'TP guidé'}
- Erreurs récentes à renforcer : ${Object.keys(state.leitner_mistakes || {}).join(', ') || 'Aucune faiblesse majeure'}

## Fichiers à générer
1. \`module.json\`
2. Leçons dans \`lessons/\` :
   - \`<id>.md\` avec points clés en **gras** et !!rouge!!
   - \`<id>.qcm.json\` avec questions
   - \`<id>.tp/tp.json\` et \`<id>.tp/check.sh\``;
    return { brief } as T;
  }

  if (pathname === '/api/weekly/import') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    if (body.path && body.path.includes('broken')) {
      const err: any = new Error('Validation failed');
      err.status = 422;
      err.errors = [
        'Fichier manquant: module.json',
        'Question q1: answer (5) hors limites pour options (taille 3)',
      ];
      throw err;
    }
    return { ok: true, module_id: 'module_importe' } as T;
  }

  if (pathname === '/api/talents') {
    return {
      talents: state.talents || INITIAL_TALENTS,
      talentPoints: state.talent_points ?? 3,
    } as T;
  }

  if (pathname === '/api/talents/unlock') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const tId = body.talentId;
    const talent = (state.talents || INITIAL_TALENTS).find((t: TalentNode) => t.id === tId);
    if (!talent) throw new Error('Talent introuvable');
    if (talent.unlocked) return { ok: true, talents: state.talents, talentPoints: state.talent_points } as T;
    if ((state.talent_points ?? 0) < talent.cost) {
      const err: any = new Error('Points de talent insuffisants');
      err.status = 400;
      throw err;
    }
    state.talent_points -= talent.cost;
    talent.unlocked = true;
    state.total_xp += 50;

    const countUnlocked = state.talents.filter((t: TalentNode) => t.unlocked).length;
    if (countUnlocked >= 3) {
      const ach = state.achievements.find((a: any) => a.id === 'skill_tree_master');
      if (ach) ach.unlocked = true;
    }

    saveLocalState(state);
    return { ok: true, talents: state.talents, talentPoints: state.talent_points } as T;
  }

  if (pathname === '/api/incidents') {
    return {
      incidents: INCIDENT_SCENARIOS,
      history: state.incidents_history || [],
    } as T;
  }

  if (pathname === '/api/incidents/complete') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const scenario = INCIDENT_SCENARIOS.find((s) => s.id === body.scenarioId) || INCIDENT_SCENARIOS[0];
    const isWon = Boolean(body.won);

    if (isWon) {
      state.total_xp += 180;
      state.tokens += 1;
      const ach = state.achievements.find((a: any) => a.id === 'war_room_hero');
      if (ach) ach.unlocked = true;
    }

    if (!state.incidents_history) state.incidents_history = [];
    state.incidents_history.unshift({
      id: `inc_res_${Date.now()}`,
      scenarioId: scenario.id,
      title: scenario.title,
      won: isWon,
      postMortem: body.postMortem || 'Résolution documentée dans l\'astreinte.',
      createdAt: new Date().toISOString(),
    });

    saveLocalState(state);
    return { ok: true, xpGained: isWon ? 180 : 20, tokensGained: isWon ? 1 : 0 } as T;
  }

  if (pathname === '/api/duels') {
    return {
      ghosts: GHOST_RUNNERS,
      history: state.duel_history || [],
    } as T;
  }

  if (pathname === '/api/duels/record') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const ghost = GHOST_RUNNERS.find((g) => g.id === body.ghostId) || GHOST_RUNNERS[0];
    const isWon = Boolean(body.won);

    if (isWon) {
      state.total_xp += 100;
      const ach = state.achievements.find((a: any) => a.id === 'ghost_speedster');
      if (ach) ach.unlocked = true;
    }

    if (!state.duel_history) state.duel_history = [];
    state.duel_history.unshift({
      id: `duel_${Date.now()}`,
      ghostId: ghost.id,
      ghostName: ghost.name,
      playerSeconds: Number(body.playerSeconds) || 20,
      ghostSeconds: Number(body.ghostSeconds) || ghost.baseSeconds,
      won: isWon,
      createdAt: new Date().toISOString(),
    });

    saveLocalState(state);
    return { ok: true, xpGained: isWon ? 100 : 15 } as T;
  }

  if (pathname === '/api/feynman') {
    if (options?.method === 'POST') {
      const body = options?.body ? JSON.parse(options.body as string) : {};
      const newMemo: FeynmanMemo = {
        id: `memo_${Date.now()}`,
        lessonId: body.lessonId || 'general',
        conceptTitle: body.conceptTitle || 'Concept Clé',
        explanation: body.explanation || '',
        analogies: body.analogies || '',
        createdAt: new Date().toISOString(),
      };
      if (!state.feynman_memos) state.feynman_memos = [];
      state.feynman_memos.unshift(newMemo);
      state.total_xp += 40;

      const ach = state.achievements.find((a: any) => a.id === 'feynman_master');
      if (ach) ach.unlocked = true;

      saveLocalState(state);
      return newMemo as T;
    }
    return (state.feynman_memos || []) as T;
  }

  if (pathname === '/api/challenge/generate') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const topic = (body.topic || 'Reverse Proxy & Sécurité').trim();
    const level = body.level || 'intermédiaire';

    const slug = topic.toLowerCase().replace(/[^a-z0-9]/g, '_');
    const challenge: CustomChallengeResult = {
      id: `custom_${Date.now()}`,
      title: `Mission Spéciale : ${topic}`,
      topic,
      level,
      description: `Défi généré à la volée sur : ${topic}. Mettez en pratique les concepts clés avec validation automatisée.`,
      markdownContent: `# Mission Pratique : ${topic} (${level})

Dans cet exercice sur-mesure généré à la volée, vous allez appliquer les principes de résilience sur le sujet : **${topic}**.

## Consignes
1. Créez un fichier de configuration \`config_${slug}.json\` ou le script cible.
2. Définissez la directive \`"enabled": true\` et un paramètre \`"version": "1.0"\`.
3. !!Attention!! : validez la syntaxe avec le script de contrôle avant soumission.

## Points Clés à Maîtriser
- **Séparation des privilèges** et configuration déclarative.
- Vérification automatique du code de retour bash (\`exit 0\`).`,
      targetFile: `config_${slug}.json`,
      solutionCommand: `echo '{"topic": "${topic}", "enabled": true, "version": "1.0"}' > config_${slug}.json`,
      verificationScript: `test -f config_${slug}.json && grep -q '"enabled": true' config_${slug}.json && exit 0 || exit 1`,
      xpReward: level === 'expert' ? 120 : 75,
    };

    if (!state.custom_challenges) state.custom_challenges = [];
    state.custom_challenges.unshift(challenge);
    saveLocalState(state);
    return challenge as T;
  }

  if (pathname === '/api/tech-tree') {
    return {
      nodes: [
        {
          id: 'node_linux_core',
          title: 'Noyau Linux & Signaux POSIX',
          category: 'linux',
          level: 1,
          prerequisites: [],
          status: 'mastered',
          masteryPct: 100,
          lessonId: 'l1',
          description: 'Gestion des processus, signaux POSIX (SIGTERM, SIGHUP, SIGKILL) et architecture système.',
        },
        {
          id: 'node_bash_auto',
          title: 'Automatisation Shell & Pipes',
          category: 'linux',
          level: 2,
          prerequisites: ['node_linux_core'],
          status: 'mastered',
          masteryPct: 85,
          lessonId: 'l1',
          description: 'Flux standard (stdin/stdout/stderr), redirections avancées et scripts de contrôle idempotents.',
        },
        {
          id: 'node_posix_net',
          title: 'Sockets Réseau & IPC',
          category: 'network',
          level: 2,
          prerequisites: ['node_linux_core'],
          status: 'unlocked',
          masteryPct: 60,
          lessonId: 'l2',
          description: 'Sockets TCP/UDP, interfaces réseau, ports d\'écoute et analyse tcpdump/conntrack.',
        },
        {
          id: 'node_docker_arch',
          title: 'Conteneurs OCI & Namespaces',
          category: 'docker',
          level: 3,
          prerequisites: ['node_linux_core', 'node_posix_net'],
          status: 'unlocked',
          masteryPct: 70,
          lessonId: 'dock_1',
          description: 'Isolation cgroups/namespaces, multi-stage builds et mise en cache des couches.',
        },
        {
          id: 'node_k8s_pods',
          title: 'Pods & Contrôleurs Kubernetes',
          category: 'k8s',
          level: 4,
          prerequisites: ['node_docker_arch'],
          status: 'unlocked',
          masteryPct: 55,
          lessonId: 'k8s_1',
          description: 'Orchestration déclarative, cycles de vie de Pods et Services ClusterIP.',
        },
        {
          id: 'node_k8s_probes',
          title: 'Sondes Liveness & Résilience',
          category: 'k8s',
          level: 5,
          prerequisites: ['node_k8s_pods'],
          status: 'unlocked',
          masteryPct: 40,
          lessonId: 'k8s_1',
          description: 'Auto-guérison, sondes HTTP/exec et évitement des deadlocks en cascade.',
        },
        {
          id: 'node_gitops_flux',
          title: 'GitOps & Déploiements Continus',
          category: 'gitops',
          level: 5,
          prerequisites: ['node_k8s_pods'],
          status: 'locked',
          masteryPct: 20,
          description: 'Réconciliation automatique, ArgoCD / Flux et contrôle de conformité Git.',
        },
        {
          id: 'node_sre_chaos',
          title: 'Chaos Engineering & Observabilité',
          category: 'sre',
          level: 6,
          prerequisites: ['node_k8s_probes', 'node_gitops_flux'],
          status: 'locked',
          masteryPct: 10,
          lessonId: 'obs_1',
          description: 'Métriques RED, injection de pannes synthétiques et SLAs / Error Budgets.',
        },
      ] as TechTreeNode[],
    } as T;
  }

  if (pathname === '/api/chaos/inject') {
    const incidents: ChaosIncident[] = [
      {
        id: 'chaos_perm_000',
        title: 'Verrouillage Brutal des Droits (000)',
        description: 'Un script de déploiement corrompu a révoqué tous les droits de lecture/écriture sur config.json.',
        symptom: 'EACCES: permission denied sur config.json',
        remedyHint: 'Rétablissez les permissions de lecture/écriture standard avec chmod.',
        remedyCommand: 'chmod 644 config.json',
        resolved: false,
        xpReward: 50,
      },
      {
        id: 'chaos_rogue_process',
        title: 'Processus Parasite Consommateur (CPU Spike)',
        description: 'Un démon en boucle infinie (PID 4912) bloque le slot d\'exécution du workspace.',
        symptom: 'Charge CPU anormale et saturation du processeur.',
        remedyHint: 'Trouvez et éliminez le processus parasite avec pkill ou kill -9.',
        remedyCommand: 'pkill -f rogue_daemon || true',
        resolved: false,
        xpReward: 50,
      },
      {
        id: 'chaos_corrupted_env',
        title: 'Variable Critique Altérée',
        description: 'La variable APP_ENV a été écrasée par "production_locked", empêchant les tests locaux.',
        symptom: 'Crash de vérification : variable APP_ENV invalide.',
        remedyHint: 'Réexportez la variable d\'environnement vers APP_ENV=test.',
        remedyCommand: 'export APP_ENV=test',
        resolved: false,
        xpReward: 50,
      },
    ];
    const picked = incidents[Math.floor(Math.random() * incidents.length)];
    state.active_chaos = picked;
    saveLocalState(state);
    return picked as T;
  }

  if (pathname === '/api/chaos/resolve') {
    if (state.active_chaos) {
      state.active_chaos.resolved = true;
      state.total_xp += 50;
      saveLocalState(state);
    }
    return { ok: true, xpAwarded: 50 } as T;
  }

  if (pathname === '/api/runbook/generate') {
    const body = options?.body ? JSON.parse(options.body as string) : {};
    const title = body.title || 'Procédure Opérationnelle Standard (SOP)';
    const lessonId = body.lessonId || 'l1';
    const runbook: RunbookDocument = {
      id: `runbook_${Date.now()}`,
      title,
      lessonId,
      createdAt: new Date().toISOString(),
      tags: ['SRE', 'Incident-Response', 'Linux', 'Production-Ready'],
      markdown: `# Runbook SRE : ${title}

## 1. Contexte & Déclencheur (Trigger)
- **Service concerné** : Core Service (${lessonId})
- **Gravité** : P2 (Majeur) / Alerte PagerDuty
- **Impact utilisateur** : Dégradation potentielle du traitement des requêtes ou blocage de configuration.

## 2. Procédure de Diagnostic Rapide (Triage)
\`\`\`bash
# 1. Vérifier l'état et l'existence du fichier clé
ls -la config.json
cat config.json

# 2. Vérifier la validité JSON / YAML
python3 -m json.tool config.json

# 3. Vérifier les processus actifs et signaux
ps aux | grep -i node
kill -l
\`\`\`

## 3. Plan de Résolution (Mitigation)
1. Si le fichier est absent ou corrompu, réinjecter la configuration déclarative minimale :
   \`\`\`bash
   echo '{"provider": "demo", "active": true}' > config.json
   chmod 644 config.json
   \`\`\`
2. Valider le code de retour avec le script de contrôle :
   \`\`\`bash
   bash check.sh
   echo "Code retour : $?"
   \`\`\`

## 4. Root Cause Analysis (RCA) & Prévention
- **Cause racine** : Absence de validation pré-vol (pre-flight check) avant rechargement à chaud.
- **Action préventive** : Mettre en place un webhook d'admission ou une sonde \`readinessProbe\` pour isoler les conteneurs non configurés.`,
    };
    return runbook as T;
  }

  if (pathname === '/api/interview/questions') {
    const questions: InterviewQuestion[] = [
      {
        id: 'q_int_1',
        role: 'Site Reliability Engineer',
        question: 'Comment concevez-vous une stratégie de Graceful Shutdown sur Kubernetes pour un service HTTP sous fort trafic ?',
        audioPrompt: 'Comment concevez-vous une stratégie de Graceful Shutdown sur Kubernetes pour éviter les erreurs 502 lors d\'un déploiement rolling update ?',
        timeLimitSeconds: 90,
        expectedKeywords: ['SIGTERM', 'preStop hook', 'readinessProbe', 'terminationGracePeriodSeconds', 'connexions keep-alive', 'drain'],
        evaluationRubric: [
          { criteria: 'Mention du signal SIGTERM et du preStop hook sleep pour propager le retrait des iptables', points: 30 },
          { criteria: 'Explication de la fermeture des keep-alive et attente des requêtes en vol', points: 30 },
          { criteria: 'Configuration appropriée de terminationGracePeriodSeconds (> timeout applicatif)', points: 20 },
          { criteria: 'Clarté de communication et vocabulaire SRE précis', points: 20 },
        ],
        seniorSampleAnswer: 'Dès que Kubernetes décide d\'arrêter un Pod, deux actions asynchrones démarrent : l\'endpoint est retiré du Service (ce qui prend quelques secondes de propagation réseau kube-proxy) et le signal SIGTERM est envoyé. Pour éviter que des requêtes HTTP n\'arrivent sur un pod déjà mourant, on implémente un preStop hook avec un court sleep (ex: 5s). Ensuite, l\'application intercepte SIGTERM, cesse d\'accepter de nouvelles connexions, et attend la fin des requêtes en vol avant d\'émettre un exit 0 dans la limite de terminationGracePeriodSeconds.',
      },
      {
        id: 'q_int_2',
        role: 'DevOps Senior',
        question: 'Expliquez la différence fondamentale entre les métriques RED (Tom Wilkie) et les 4 Golden Signals de Google SRE.',
        audioPrompt: 'Quelle est la différence fondamentale entre la méthode RED et les Golden Signals de Google pour superviser une architecture microservices ?',
        timeLimitSeconds: 60,
        expectedKeywords: ['Rate', 'Errors', 'Duration', 'Latence', 'Trafic', 'Erreurs', 'Saturation', 'Haute cardinalité'],
        evaluationRubric: [
          { criteria: 'Définition exacte de RED : Rate (requêtes/s), Errors (5xx), Duration (latence)', points: 35 },
          { criteria: 'Identification des 4 Golden Signals : Latence, Trafic, Erreurs, Saturation', points: 35 },
          { criteria: 'Mise en avant de la Saturation (CPU/RAM/IO) comme clé infrastructure', points: 30 },
        ],
        seniorSampleAnswer: 'La méthode RED se focalise sur l\'expérience utilisateur directe pour les services web : Rate (volume), Errors (taux d\'échecs), et Duration (latence percentiles p95/p99). Les 4 Golden Signals de Google englobent ces trois notions (Traffic, Errors, Latency) mais y ajoutent une dimension cruciale : la Saturation (saturation des pools de connexions, mémoire, files d\'attente), prédisant les goulots d\'étranglement avant que la latence n\'explose.',
      },
      {
        id: 'q_int_3',
        role: 'Kubernetes Architect',
        question: 'Vos pods applicatifs tombent en CrashLoopBackOff avec des erreurs DNS "server failure / nxdomain". Quelle démarche de diagnostic méthodique appliquez-vous ?',
        audioPrompt: 'En production, vos microservices subissent des échecs de résolution DNS intermittents. Quelles sont vos étapes d\'investigation ?',
        timeLimitSeconds: 90,
        expectedKeywords: ['CoreDNS', 'kubectl logs -n kube-system', 'resolv.conf', 'ndots:5', 'NodeLocal DNSCache', 'Conntrack UDP'],
        evaluationRubric: [
          { criteria: 'Vérification immédiate de la santé des pods CoreDNS et de leurs métriques de saturation', points: 30 },
          { criteria: 'Inspection du fichier /etc/resolv.conf et de l\'impact du paramètre ndots:5', points: 35 },
          { criteria: 'Proposition d\'une solution durable : NodeLocal DNSCache ou passage en FQDN absolu (.)', points: 35 },
        ],
        seniorSampleAnswer: '1. Vérifier l\'état des pods CoreDNS avec kubectl get pods/logs dans kube-system. 2. Tester la résolution interne (cluster.local) et externe via un pod de debug (nslookup/dig). 3. Analyser la table conntrack du nœud hôte pour vérifier s\'il y a perte de paquets UDP sur la translation de port. 4. Vérifier la configuration ndots:5 du pod qui peut quintupler les requêtes inutiles, et préconiser le déploiement de NodeLocal DNSCache.',
      },
    ];
    return { questions } as T;
  }

  if (pathname === '/api/league') {
    const leagueData: LeagueData = {
      currentTier: 'gold',
      timeRemainingDays: 3,
      leaderboard: [
        { rank: 1, name: 'Sarah_SRE', avatar: '👩‍💻', xpThisWeek: 490, tier: 'gold' },
        { rank: 2, name: 'Vous (Opérateur)', avatar: '⚡', xpThisWeek: 420, tier: 'gold', isCurrentPlayer: true },
        { rank: 3, name: 'Thomas_Kernel', avatar: '🐧', xpThisWeek: 380, tier: 'gold' },
        { rank: 4, name: 'Alex_DevOps', avatar: '🚀', xpThisWeek: 310, tier: 'gold' },
        { rank: 5, name: 'Fatou_Cloud', avatar: '☁️', xpThisWeek: 280, tier: 'gold' },
        { rank: 6, name: 'Marc_Sysadmin', avatar: '🔧', xpThisWeek: 210, tier: 'silver' },
        { rank: 7, name: 'Ines_Chaos', avatar: '💥', xpThisWeek: 150, tier: 'silver' },
      ],
      guildMissions: [
        {
          id: 'guild_m1',
          title: 'Résoudre 100 TPs en Guilde',
          description: 'Complétez des travaux pratiques pour faire progresser la communauté SRE.',
          target: 100,
          current: 68,
          unit: 'TPs',
          completed: false,
          rewardTokens: 2,
        },
        {
          id: 'guild_m2',
          title: 'Éradication d\'Incidents P1',
          description: 'Gagner 20 sessions War Room sans dépasser le budget d\'erreur.',
          target: 20,
          current: 16,
          unit: 'Crises',
          completed: false,
          rewardTokens: 3,
        },
        {
          id: 'guild_m3',
          title: 'Bibliothèque de Runbooks',
          description: 'Générer et partager 10 fiches Runbooks avec votre équipe.',
          target: 10,
          current: 10,
          unit: 'Runbooks',
          completed: true,
          rewardTokens: 1,
        },
      ],
    };
    return leagueData as T;
  }

  if (pathname === '/api/guild/claim') {
    // La guilde est fictive : aucune récompense (la réclamation était répétable à l'infini).
    return { ok: true, tokensAwarded: 0 } as T;
  }

  return {} as T;
}

export const api = {
  getQuest: (minutes: number = 30): Promise<QuestData> =>
    request(`/api/quest?minutes=${minutes}`),

  completeStep: (kind: string, lessonId: string): Promise<{ ok: boolean; alreadyCompleted?: boolean }> =>
    request('/api/quest/step', {
      method: 'POST',
      body: JSON.stringify({ kind, lesson_id: lessonId }),
    }),

  announceRest: (): Promise<{ ok: boolean }> =>
    request('/api/rest', { method: 'POST' }),

  setTopic: (topic: string | null): Promise<{ ok: boolean }> =>
    request('/api/topic', {
      method: 'POST',
      body: JSON.stringify({ topic }),
    }),

  getModules: (): Promise<ModuleItem[]> => request('/api/modules'),

  switchModule: (moduleId: string): Promise<{ ok: boolean }> =>
    request('/api/module/switch', {
      method: 'POST',
      body: JSON.stringify({ moduleId }),
    }),

  getLesson: (id: string): Promise<LessonData> =>
    request(`/api/lesson/${id}`),

  getAudioUrl: (id: string) => `/api/audio/${id}.wav`,

  answerQcm: (questionId: string, chosen: number): Promise<QcmAnswerResult> =>
    request('/api/qcm/answer', {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, chosen }),
    }),

  getReviews: (): Promise<{ due: Question[]; boxesCount: number[] }> =>
    request('/api/reviews'),

  answerReview: (
    questionId: string,
    correct: boolean
  ): Promise<{ nextBox: number; xpAwarded: number }> =>
    request('/api/reviews/answer', {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, correct }),
    }),

  getTpHint: (
    tpId: string,
    level: number
  ): Promise<{ hint: string; level: number; xp_cost: number }> =>
    request(`/api/tp/${tpId}/hint?level=${level}`),

  checkTp: (tpId: string): Promise<{ passed: boolean; output: string }> =>
    request(`/api/tp/${tpId}/check`, { method: 'POST' }),

  askTpTutor: (tpId: string, message: string): Promise<{ reply: string }> =>
    request('/api/tutor/chat', {
      method: 'POST',
      body: JSON.stringify({ tp_id: tpId, message }),
    }),

  getTeam: (): Promise<TeamData> =>
    request('/api/team'),

  setTheme: (themeId: string): Promise<{ ok: boolean }> =>
    request('/api/team/theme', {
      method: 'POST',
      body: JSON.stringify({ themeId }),
    }),

  setCompanion: (companionId: string): Promise<{ ok: boolean }> =>
    request('/api/team/companion', {
      method: 'POST',
      body: JSON.stringify({ companionId }),
    }),

  pullGacha: (): Promise<{ item: InventoryItem; tokens: number }> =>
    request('/api/gacha/pull', { method: 'POST' }),

  verifySandbox: (
    challengeId: string,
    command: string
  ): Promise<{ passed: boolean; message: string }> =>
    request('/api/sandbox/verify', {
      method: 'POST',
      body: JSON.stringify({ challengeId, command }),
    }),

  completePodcastSession: (): Promise<{ ok: boolean }> =>
    request('/api/podcast/complete', { method: 'POST' }),

  getBosses: (): Promise<BossEntity[]> => request('/api/bosses'),

  getBoss: (bossId: string = 'boss_k8s'): Promise<BossData> =>
    request(`/api/boss?id=${bossId}`),

  attemptBoss: (
    bossId: string = 'boss_k8s',
    crisisMode: boolean = false
  ): Promise<BossAttemptResult> =>
    request('/api/boss/attempt', {
      method: 'POST',
      body: JSON.stringify({ boss_id: bossId, crisis_mode: crisisMode }),
    }),

  generateBrief: (topic: string, format: string): Promise<{ brief: string }> =>
    request('/api/weekly/brief', {
      method: 'POST',
      body: JSON.stringify({ topic, format }),
    }),

  importModule: (path: string): Promise<{ ok: boolean; module_id: string }> =>
    request('/api/weekly/import', {
      method: 'POST',
      body: JSON.stringify({ path }),
    }),

  // Nouvelles fonctionnalités
  getTalents: (): Promise<{ talents: TalentNode[]; talentPoints: number }> =>
    request('/api/talents'),

  unlockTalent: (
    talentId: string
  ): Promise<{ ok: boolean; talents: TalentNode[]; talentPoints: number }> =>
    request('/api/talents/unlock', {
      method: 'POST',
      body: JSON.stringify({ talentId }),
    }),

  getIncidents: (): Promise<{
    incidents: IncidentScenario[];
    history: Array<{
      id: string;
      scenarioId: string;
      title: string;
      won: boolean;
      postMortem: string;
      createdAt: string;
    }>;
  }> => request('/api/incidents'),

  completeIncident: (
    scenarioId: string,
    won: boolean,
    postMortem: string
  ): Promise<{ ok: boolean; xpGained: number; tokensGained: number }> =>
    request('/api/incidents/complete', {
      method: 'POST',
      body: JSON.stringify({ scenarioId, won, postMortem }),
    }),

  getDuels: (): Promise<{ ghosts: GhostRunner[]; history: DuelRecord[] }> =>
    request('/api/duels'),

  recordDuelResult: (
    ghostId: string,
    playerSeconds: number,
    ghostSeconds: number,
    won: boolean
  ): Promise<{ ok: boolean; xpGained: number }> =>
    request('/api/duels/record', {
      method: 'POST',
      body: JSON.stringify({ ghostId, playerSeconds, ghostSeconds, won }),
    }),

  getFeynmanMemos: (lessonId?: string): Promise<FeynmanMemo[]> =>
    request(`/api/feynman${lessonId ? `?lesson_id=${lessonId}` : ''}`),

  saveFeynmanMemo: (
    memo: Omit<FeynmanMemo, 'id' | 'createdAt'>
  ): Promise<FeynmanMemo> =>
    request('/api/feynman', {
      method: 'POST',
      body: JSON.stringify(memo),
    }),

  generateCustomChallenge: (
    topic: string,
    level: string = 'intermédiaire'
  ): Promise<CustomChallengeResult> =>
    request('/api/challenge/generate', {
      method: 'POST',
      body: JSON.stringify({ topic, level }),
    }),

  // 1. Tech Roadmap
  getTechTree: (): Promise<{ nodes: TechTreeNode[] }> =>
    request('/api/tech-tree'),

  // 2. Chaos Monkey
  injectChaos: (tpId?: string): Promise<ChaosIncident> =>
    request('/api/chaos/inject', {
      method: 'POST',
      body: JSON.stringify({ tpId }),
    }),

  resolveChaos: (incidentId: string): Promise<{ ok: boolean; xpAwarded: number }> =>
    request('/api/chaos/resolve', {
      method: 'POST',
      body: JSON.stringify({ incidentId }),
    }),

  // 3. SRE Runbooks
  generateRunbook: (
    lessonId: string,
    title?: string
  ): Promise<RunbookDocument> =>
    request('/api/runbook/generate', {
      method: 'POST',
      body: JSON.stringify({ lessonId, title }),
    }),

  // 4. Oral Technical Interview
  getInterviewQuestions: (): Promise<{ questions: InterviewQuestion[] }> =>
    request('/api/interview/questions'),

  // 5. Leagues & Guild
  getLeagueData: (): Promise<LeagueData> =>
    request('/api/league'),

  claimGuildMission: (
    missionId: string
  ): Promise<{ ok: boolean; tokensAwarded: number }> =>
    request('/api/guild/claim', {
      method: 'POST',
      body: JSON.stringify({ missionId }),
    }),
};
