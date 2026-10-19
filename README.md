# Formation

## Lancement

- Tests backend : `cd backend && uv run pytest`
- Serveur backend : `cd backend && uv run uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000` (variables optionnelles : `FORMATION_DB`, `FORMATION_CONTENT`, `FORMATION_WORKSPACE`, par défaut sous `~/.formation`)
- Frontend : `cd frontend && npm test && npm run build`
