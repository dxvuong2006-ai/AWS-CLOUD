# Local demonstration

This is a 3–5 minute local demo. It demonstrates the running app and the API interface without relying on an AWS account or claiming unverified production behavior.

## Preparation

Follow [local setup](local-setup.md), configure a local database/auth mode, and start backend and frontend. Use disposable local data only. Do not project secrets, access tokens or presigned URLs.

## Demo flow

1. Open `http://127.0.0.1:8000/health` and show the local API responds. This confirms only the local backend process.
2. Open `http://127.0.0.1:8000/docs` and show that the live FastAPI OpenAPI is the current API reference.
3. Open `http://localhost:5173` and navigate a flow supported by the local configuration. State whether the page is connected to the local backend or explicitly running in mock mode.
4. If database-backed interaction is prepared, use only a disposable seeded/local test account and show one covered flow. Do not imply an AWS integration or PostgreSQL concurrency gate passed based on SQLite/offline tests.
5. Close by distinguishing current evidence: source and offline tests are available; PostgreSQL-gated suites and current AWS deployment state remain unverified as summarized in [requirements](requirements.md) and the [regression report](operations/backend-regression-report.md).

## Stop and cleanup

Stop Uvicorn/Vite with `Ctrl+C`. Stop local services with `docker compose stop` if they were started. Preserve the Compose volume unless its owner explicitly chooses to remove local data.
