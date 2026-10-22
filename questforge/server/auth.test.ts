// @vitest-environment node
import { describe, test, expect } from 'vitest';
import {
  FailureLimiter,
  checkBasicAuth,
  clientKey,
  isLoopbackHost,
  resolveListenConfig,
} from './auth';

const basic = (user: string, password: string) => 'Basic ' + Buffer.from(`${user}:${password}`).toString('base64');
const PASSWORD = 'un-mot-de-passe-solide';

describe('checkBasicAuth', () => {
  test('accepte le bon mot de passe, quel que soit le nom d\'utilisateur', () => {
    expect(checkBasicAuth(basic('moi', PASSWORD), PASSWORD)).toBe(true);
    expect(checkBasicAuth(basic('', PASSWORD), PASSWORD)).toBe(true);
  });

  test('accepte un mot de passe contenant deux-points', () => {
    expect(checkBasicAuth(basic('moi', 'a:b:c-123456789'), 'a:b:c-123456789')).toBe(true);
  });

  test.each([
    ['mauvais mot de passe', basic('moi', 'autre')],
    ['mot de passe tronqué', basic('moi', PASSWORD.slice(0, -1))],
    ['mot de passe rallongé', basic('moi', PASSWORD + 'x')],
    ['schéma Bearer', `Bearer ${PASSWORD}`],
    ['sans séparateur', 'Basic ' + Buffer.from(PASSWORD).toString('base64')],
    ['en-tête absent', undefined],
    ['en-tête vide', ''],
  ])('refuse : %s', (_label, header) => {
    expect(checkBasicAuth(header, PASSWORD)).toBe(false);
  });
});

describe('resolveListenConfig', () => {
  test('sans mot de passe : écoute uniquement en local', () => {
    expect(resolveListenConfig({})).toEqual({ host: '127.0.0.1', port: 3000, password: undefined });
  });

  test('avec mot de passe : écoute sur le réseau par défaut', () => {
    expect(resolveListenConfig({ QUESTFORGE_PASSWORD: PASSWORD, PORT: '8080' })).toEqual({
      host: '0.0.0.0',
      port: 8080,
      password: PASSWORD,
    });
  });

  test('refuse d\'exposer le réseau sans mot de passe', () => {
    expect(() => resolveListenConfig({ HOST: '0.0.0.0' })).toThrow(/QUESTFORGE_PASSWORD/);
    expect(() => resolveListenConfig({ HOST: '192.168.1.10' })).toThrow(/sans authentification/);
  });

  test('accepte une écoute locale explicite sans mot de passe', () => {
    expect(resolveListenConfig({ HOST: '::1' }).host).toBe('::1');
  });

  test('refuse un mot de passe trop court', () => {
    expect(() => resolveListenConfig({ QUESTFORGE_PASSWORD: 'court' })).toThrow(/au moins 12/);
  });

  test('une chaîne vide équivaut à aucun mot de passe', () => {
    expect(resolveListenConfig({ QUESTFORGE_PASSWORD: '' }).password).toBeUndefined();
  });
});

describe('clientKey', () => {
  test('connexion directe : l\'adresse du client', () => {
    expect(clientKey('203.0.113.9', undefined)).toBe('203.0.113.9');
  });

  test('derrière un relais privé : première adresse de X-Forwarded-For', () => {
    expect(clientKey('172.18.0.3', '198.51.100.7, 172.18.0.3')).toBe('198.51.100.7');
    expect(clientKey('::ffff:127.0.0.1', '198.51.100.7')).toBe('198.51.100.7');
  });

  test('un client public ne peut pas usurper X-Forwarded-For', () => {
    expect(clientKey('203.0.113.9', '198.51.100.7')).toBe('203.0.113.9');
  });
});

describe('FailureLimiter', () => {
  test('bloque après le maximum d\'échecs puis libère après la fenêtre', () => {
    let now = 0;
    const limiter = new FailureLimiter(3, 1000, () => now);
    for (let i = 0; i < 3; i++) {
      expect(limiter.isBlocked('a')).toBe(false);
      limiter.recordFailure('a');
    }
    expect(limiter.isBlocked('a')).toBe(true);
    expect(limiter.isBlocked('b')).toBe(false);
    now = 1001;
    expect(limiter.isBlocked('a')).toBe(false);
  });

  test('une connexion réussie remet le compteur à zéro', () => {
    const limiter = new FailureLimiter(2, 1000, () => 0);
    limiter.recordFailure('a');
    limiter.reset('a');
    limiter.recordFailure('a');
    expect(limiter.isBlocked('a')).toBe(false);
  });
});

describe('isLoopbackHost', () => {
  test.each(['127.0.0.1', '::1', 'localhost'])('%s est local', (h) => expect(isLoopbackHost(h)).toBe(true));
  test.each(['0.0.0.0', '192.168.1.5', ''])('%s n\'est pas local', (h) => expect(isLoopbackHost(h)).toBe(false));
});
