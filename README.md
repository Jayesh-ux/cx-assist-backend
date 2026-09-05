# CX Assist — Backend (Railway deploy copy)

Standalone FastAPI backend for CX Assist. This repo exists solely so Railway can
autodetect and deploy the backend from a single-directory source (the monorepo
`Jayesh-ux/cx-assist` hosts the frontend + full project).

Deploys via Nixpacks (`requirements.txt` at root + `Procfile`).

Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Env vars
See `requirements.txt` + `app/core/config.py`. Required at runtime:
`DATABASE_URL`, `SECRET_KEY`, `ADMIN_API_KEY`, `GEMINI_API_KEY`.
Optional: `REDIS_URL` (in-memory fallback when unreachable).