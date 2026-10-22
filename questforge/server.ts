import express from 'express';
import { createServer, IncomingMessage } from 'http';
import { randomBytes } from 'crypto';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { createServer as createViteServer } from 'vite';
import { spawn } from 'child_process';
import path from 'path';
import {
  FailureLimiter,
  INTERNAL_HEADER,
  checkBasicAuth,
  clientKey,
  resolveListenConfig,
} from './server/auth';

async function startServer() {
  let config;
  try {
    config = resolveListenConfig(process.env);
  } catch (err: any) {
    console.error(`[QuestForge] ${err.message}`);
    process.exit(1);
  }
  const { host: HOST, port: PORT, password } = config;
  const BACKEND_PORT = Number(process.env.BACKEND_PORT) || 8000;
  const isDev = process.env.NODE_ENV !== 'production';

  const app = express();
  const server = createServer(app);
  // Derrière un relais privé (Caddy, Docker) : req.ip doit être le vrai client.
  app.set('trust proxy', ['loopback', 'linklocal', 'uniquelocal']);
  app.disable('x-powered-by');

  // Secret connu du seul relais et du backend : il prouve qu'une requête a passé l'authentification.
  const internalSecret = randomBytes(32).toString('hex');

  // Lance le backend FastAPI en arrière-plan (jamais exposé : il n'écoute que sur 127.0.0.1)
  const backendDir = path.resolve('backend');
  const backendProcess = spawn(
    'python3',
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    {
      cwd: backendDir,
      stdio: 'inherit',
      env: { ...process.env, QUESTFORGE_INTERNAL_SECRET: internalSecret },
    }
  );

  backendProcess.on('error', (err) => {
    console.error('[Backend] Impossible de lancer uvicorn:', err);
  });
  backendProcess.on('exit', (code) => {
    if (!isDev) {
      console.error(`[Backend] uvicorn s'est arrêté (code ${code}) : arrêt du serveur.`);
      process.exit(1);
    }
  });

  process.on('SIGINT', () => {
    backendProcess.kill();
    process.exit();
  });
  process.on('SIGTERM', () => {
    backendProcess.kill();
    process.exit();
  });

  // Sonde de santé (aucune donnée), avant l'authentification. Elle n'est « ok » que si le backend répond aussi.
  app.get('/healthz', async (_req, res) => {
    try {
      const backend = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/modules`, {
        signal: AbortSignal.timeout(2000),
      });
      if (!backend.ok) throw new Error(`backend HTTP ${backend.status}`);
      res.type('text/plain').send('ok');
    } catch {
      res.status(503).type('text/plain').send('backend indisponible');
    }
  });

  // En-têtes de sécurité : le terminal ne doit pas pouvoir être affiché dans une iframe tierce.
  app.use((_req, res, next) => {
    res.set({
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'same-origin',
    });
    next();
  });

  // Authentification (HTTP Basic) pour tout le reste, API et WebSocket compris.
  const limiter = new FailureLimiter();
  if (password) {
    app.use((req, res, next) => {
      const key = clientKey(req.socket.remoteAddress, req.headers['x-forwarded-for'] as string | undefined);
      if (limiter.isBlocked(key)) {
        res.status(429).type('text/plain').send('Trop de tentatives, réessayez plus tard.');
        return;
      }
      if (checkBasicAuth(req.headers.authorization, password)) {
        limiter.reset(key);
        next();
        return;
      }
      if (req.headers.authorization) limiter.recordFailure(key);
      res
        .status(401)
        .set('WWW-Authenticate', 'Basic realm="QuestForge", charset="UTF-8"')
        .type('text/plain')
        .send('Authentification requise');
    });
  }

  // Proxy transparent pour /api et /ws : il ajoute le secret interne (et écrase celui d'un client malveillant).
  const apiProxy = createProxyMiddleware({
    target: `http://127.0.0.1:${BACKEND_PORT}`,
    changeOrigin: true,
    ws: true,
    xfwd: true,
    pathFilter: (p: string) => p.startsWith('/api') || p.startsWith('/ws'),
    on: {
      proxyReq: (proxyReq) => proxyReq.setHeader(INTERNAL_HEADER, internalSecret),
      proxyReqWs: (proxyReq) => proxyReq.setHeader(INTERNAL_HEADER, internalSecret),
    },
  });

  app.use(apiProxy);

  if (typeof (apiProxy as any).upgrade === 'function') {
    server.on('upgrade', (req: IncomingMessage, socket, head) => {
      if (password) {
        const key = clientKey(req.socket.remoteAddress, req.headers['x-forwarded-for'] as string | undefined);
        const allowed = !limiter.isBlocked(key) && checkBasicAuth(req.headers.authorization, password);
        if (!allowed) {
          if (req.headers.authorization) limiter.recordFailure(key);
          socket.write('HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="QuestForge"\r\nConnection: close\r\n\r\n');
          socket.destroy();
          return;
        }
        limiter.reset(key);
      }
      (apiProxy as any).upgrade(req, socket, head);
    });
  }

  // Vite en dev / dist en prod
  if (isDev) {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve('dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.resolve(distPath, 'index.html'));
    });
  }

  server.listen(PORT, HOST, () => {
    const access = password ? 'protégé par mot de passe' : 'local uniquement (aucun mot de passe)';
    console.log(`[QuestForge] Serveur actif sur http://${HOST}:${PORT} — ${access}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start QuestForge server:', err);
  process.exit(1);
});
