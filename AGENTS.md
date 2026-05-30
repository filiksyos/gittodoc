# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

**Gittodoc** (fork of gitingest) is a single Python app with two entry points:

- **Web**: FastAPI + Uvicorn (`src/server/main.py`), default port **8000**
- **CLI**: `gitingest` package (`src/gitingest/cli.py`) — see known issues below

There is **no Node/npm build**; the UI uses Tailwind via CDN.

### System dependencies

- **Python 3.8+** (VM has 3.12)
- **git** and **curl** on `PATH` (required for cloning and GitHub checks)

### Install dependencies

See `README.md` and CI (`.github/workflows/ci.yml`):

```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Ensure `~/.local/bin` is on `PATH` (pip installs `pytest`, `uvicorn`, `pre-commit` there on this VM).

### Run the web app (development)

From repo root:

```bash
cd src
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

- **Health check**: `GET http://127.0.0.1:8000/health` → `{"status":"healthy"}`
- Optional env: copy `.env.example` to `.env` for `GITHUB_PAT`, S3 (`GITINGEST_S3_BUCKET`, `AWS_*`). S3 and PAT are **not** required for basic public-repo ingestion.

**Note:** As of setup (2026-05), HTML routes can fail with current dependency versions (Starlette/Jinja2 `TemplateResponse` API + `query_processor` partial). The ingestion **library** still works via `PYTHONPATH=src` (see below). Verify UI changes in a browser after dependency or template fixes.

### Run ingestion without the web UI

```bash
cd /workspace
PYTHONPATH=src python3 -c "
import asyncio
from gitingest.entrypoint import ingest_async
asyncio.run(ingest_async('https://github.com/octocat/Hello-World'))
"
```

### Tests and lint

```bash
pytest                    # from repo root; pythonpath=src in pyproject.toml
pre-commit run --all-files  # CI runs this on Python 3.13 + Ubuntu only
```

**Known test gaps (upstream):**

- `tests/test_cli.py` fails collection: `handle_exceptions` is imported in `cli.py` but not defined in `gitingest.utils.exceptions`.
- Some `tests/test_repository_clone.py` tests may fail without network/GitHub access or due to environment mocks.

### Docker alternative

`docker compose up` builds and runs the app on port 8000 (see `Dockerfile`, `docker-compose.yml`). Not required if using local pip + Uvicorn.

### Long-running processes

Use **tmux** for dev servers (e.g. session `gittodoc-server`):

```bash
cd src && uvicorn server.main:app --host 0.0.0.0 --port 8000
```
