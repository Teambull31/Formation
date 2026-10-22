import express from 'express';
import { createServer } from 'http';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { createServer as createViteServer } from 'vite';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

async function startServer() {
  const app = express();
  const server = createServer(app);
  const PORT = Number(process.env.PORT) || 3000;
  const BACKEND_PORT = 8000;

  // Lance le backend FastAPI en arrière-plan
  const backendDir = path.resolve('backend');
  const backendProcess = spawn(
    'python3',
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    {
      cwd: backendDir,
      stdio: 'inherit',
    }
  );

  backendProcess.on('error', (err) => {
    console.error('[Backend] Impossible de lancer uvicorn:', err);
  });

  process.on('SIGINT', () => {
    backendProcess.kill();
    process.exit();
  });
  process.on('SIGTERM', () => {
    backendProcess.kill();
    process.exit();
  });

  // Proxy transparent pour /api et /ws
  const apiProxy = createProxyMiddleware({
    target: `http://127.0.0.1:${BACKEND_PORT}`,
    changeOrigin: true,
    ws: true,
    pathFilter: (path: string) => path.startsWith('/api') || path.startsWith('/ws'),
  });

  app.use(apiProxy);

  if (typeof (apiProxy as any).upgrade === 'function') {
    server.on('upgrade', (apiProxy as any).upgrade);
  }

  // Vite en dev / dist en prod
  const isDev = process.env.NODE_ENV !== 'production';

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

  server.listen(PORT, '0.0.0.0', () => {
    console.log(`[QuestForge] Serveur actif sur http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start QuestForge server:', err);
  process.exit(1);
});
