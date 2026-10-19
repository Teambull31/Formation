# Formation

## Lancement

- Tests backend : `cd backend && uv run pytest`
- Serveur backend : `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` (`app.main` arrive dans une tâche ultérieure)
- Frontend : `cd frontend && npm test && npm run build`
