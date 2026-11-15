# LearnCloud

LearnCloud is a video-first learning platform. The repository contains a React/Vite frontend, a FastAPI backend, PostgreSQL schema/migrations, and an AI/video pipeline with local and AWS-oriented adapters.

## Repository map

| Path | Purpose |
|---|---|
| `frontend/` | React/Vite app, authentication/API integration and browser tests. |
| `backend/` | FastAPI routes, services, repositories, adapters and tests. |
| `ai_pipeline/` | Transcript/content processors, schemas, fixtures and tests. |
| `database/` | PostgreSQL bootstrap, migrations, checks and fixtures. |
| `infrastructure/` | AWS templates, Lambda builders and deployment examples. |
| `docs/` | Maintained project, setup and operations documentation. |

## Start locally

See [local setup](docs/local-setup.md) for dependencies, database options and auth configuration. The backend requires `DATABASE_URL`; frontend `VITE_*` settings are public browser configuration and must not contain secrets.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

Run the backend in a second terminal from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

## Documentation

Start at [docs/README.md](docs/README.md) for the document map and evidence conventions. The principal references are [requirements](docs/requirements.md), [architecture](docs/architecture.md), [API contract](docs/api-contract.md), [database](docs/database.md), [AWS deployment](docs/aws-deployment.md) and [demo script](docs/demo-script.md).

## Evidence and safety

Source/configuration presence is not proof of runtime behavior. The [saved backend regression report](docs/operations/backend-regression-report.md) records 463 passed, 0 failed and 69 PostgreSQL-gated skipped cases in its reported offline run; skipped cases are not counted as passing PostgreSQL tests. Current AWS production state has not been verified during the documentation cleanup.

Do not commit `.env`, credentials, tokens, passwords, private keys or presigned URLs. Do not apply migrations or deploy based only on repository examples. Review [migration history and safeguards](database/migrations/README.md) before using SQL.
