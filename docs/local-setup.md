# Local setup

These steps target a developer machine and isolated local data. They do not deploy or contact AWS. Do not point tests or migration commands at RDS.

## Requirements

- Python 3.11+ and pip.
- Node.js/npm compatible with `frontend/package-lock.json`.
- Docker Desktop only when local PostgreSQL/Mailpit are needed.

## Backend

From repository root in PowerShell:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Set `DATABASE_URL` to a local database or an isolated SQLite test database and set development-only secrets as required by `backend/app/config.py`. Do not copy production environment files. The backend fails to start if `DATABASE_URL` is empty.

Run from repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the runtime OpenAPI interface and `http://127.0.0.1:8000/health` for the health route.

## Frontend

In a second terminal:

```powershell
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

Vite serves the app at `http://localhost:5173` by default. Use `frontend/.env.example` as the variable reference. Any `VITE_*` value is exposed to the browser bundle; never put secrets there.

## Optional local services

`docker-compose.yml` defines PostgreSQL 16 on host port `5434` and Mailpit on `1025`/`8025`. Start only when needed:

```powershell
docker compose up -d learncloud-db mailpit
```

For a new local database, review `database/migrations/README.md` and the duplicate historical migration versions before applying schema/migrations. Compose's persistent volume may contain local data; do not use `down -v` as routine cleanup.

## Tests and limits

Backend tests have explicit PostgreSQL gates; see [the saved regression report](operations/backend-regression-report.md). It records 463 passing and 69 skipped cases in an offline SQLite-configured run. The skipped PostgreSQL cases remain unverified until run against their isolated test databases.

Frontend commands are `npm.cmd test`, `npm.cmd run build`, `npm.cmd run test:browser` and `npm.cmd run test:auth-browser` from `frontend/`. AI pipeline checks are in `ai_pipeline/tests/`; inspect `ai_pipeline/README.md` for the exact local invocation. No test suite is run by these setup instructions automatically.

## Authentication and safety

Backend auth uses bearer access tokens. Local auth is a separately gated development/test option; it is not an AWS/Cognito substitute for production. Use seeded/local test accounts only. Do not bypass auth with old `X-Demo-User` instructions found in archived notes. Keep `.env`, `frontend/.env`, tokens and test passwords out of Git.
