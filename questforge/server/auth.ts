import { createHash, timingSafeEqual } from 'crypto';

/** En-tête ajouté par le relais, après authentification, pour que le backend lui fasse confiance. */
export const INTERNAL_HEADER = 'x-questforge-internal';

const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', 'localhost']);
export const isLoopbackHost = (host: string) => LOOPBACK_HOSTS.has(host);

const digest = (value: string) => createHash('sha256').update(value).digest();

/** Authentification HTTP Basic : seul le mot de passe compte, le nom d'utilisateur est libre. */
export function checkBasicAuth(header: string | undefined, password: string): boolean {
  if (!header || !header.startsWith('Basic ')) return false;
  const decoded = Buffer.from(header.slice(6), 'base64').toString('utf8');
  const separator = decoded.indexOf(':');
  if (separator < 0) return false;
  return timingSafeEqual(digest(decoded.slice(separator + 1)), digest(password));
}

export const MIN_PASSWORD_LENGTH = 12;

export interface ListenConfig {
  host: string;
  port: number;
  password?: string;
}

/**
 * Sécurité par défaut : sans mot de passe, le serveur n'écoute que sur la machine locale.
 * Le terminal et les scripts de TP exécutent des commandes : on ne les expose jamais sans mot de passe.
 */
export function resolveListenConfig(env: Record<string, string | undefined>): ListenConfig {
  const password = env.QUESTFORGE_PASSWORD || undefined;
  if (password && password.length < MIN_PASSWORD_LENGTH) {
    throw new Error(`QUESTFORGE_PASSWORD doit contenir au moins ${MIN_PASSWORD_LENGTH} caractères.`);
  }
  const host = env.HOST || (password ? '0.0.0.0' : '127.0.0.1');
  if (!isLoopbackHost(host) && !password) {
    throw new Error(
      `HOST=${host} exposerait le terminal au réseau sans authentification : définissez QUESTFORGE_PASSWORD ou utilisez HOST=127.0.0.1.`
    );
  }
  return { host, port: Number(env.PORT) || 3000, password };
}

const PRIVATE_ADDRESS = /^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1$|f[cd][0-9a-f]{2}:|::ffff:(127|10|192\.168)\.)/i;

/** Identifie le client pour la limitation : derrière un relais privé (Caddy, Docker), on lit X-Forwarded-For. */
export function clientKey(remoteAddress: string | undefined, forwardedFor: string | undefined): string {
  const remote = remoteAddress ?? 'inconnu';
  if (forwardedFor && PRIVATE_ADDRESS.test(remote)) {
    return forwardedFor.split(',')[0].trim() || remote;
  }
  return remote;
}

/** Bloque une adresse après trop d'échecs d'authentification dans une fenêtre de temps. */
export class FailureLimiter {
  private failures = new Map<string, number[]>();

  constructor(
    private readonly max = 10,
    private readonly windowMs = 15 * 60 * 1000,
    private readonly now: () => number = Date.now
  ) {}

  private recent(key: string): number[] {
    const cutoff = this.now() - this.windowMs;
    const kept = (this.failures.get(key) ?? []).filter((t) => t > cutoff);
    if (kept.length > 0) this.failures.set(key, kept);
    else this.failures.delete(key);
    return kept;
  }

  isBlocked(key: string): boolean {
    return this.recent(key).length >= this.max;
  }

  recordFailure(key: string): void {
    this.failures.set(key, [...this.recent(key), this.now()]);
  }

  reset(key: string): void {
    this.failures.delete(key);
  }
}
