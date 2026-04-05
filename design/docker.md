# design/docker.md v1.0

## 1. Objective
Provide a production-grade Docker deployment for ClawBrain. Goal: single-command startup (`docker compose up -d`), data persistence, all runtime parameters injected via env vars, zero hard-coded paths or secrets.

## 2. Architecture Decisions

### 2.1 Dockerfile
- **Base image**: `python:3.12-slim` — minimal attack surface, aligned with host Python 3.12.3.
- **Working directory**: `/app`.
- **Dependency installation**: Copy `requirements.txt` first, install before copying source — exploits Docker layer caching (source changes do not re-trigger installs).
- **Non-root user**: Create user `clawbrain` (uid=1000); run with least privilege.
- **Start command**: `uvicorn src.main:app --host 0.0.0.0 --port 11435 --workers 1`
  - `workers=1`: Ensures the in-process WorkingMemory session state is consistent (multiple workers would not share WM). Horizontal scaling requires migrating L1 to Redis first.

### 2.2 docker-compose.yml
- **Service**: Single `clawbrain` service.
- **Port mapping**: `11435:11435` (aligned with README promise).
- **Volume**: `./data:/app/data` — SQLite DB and blobs persisted to the host; container restarts do not lose data.
- **env_file**: `.env` — user configures API keys and sensitive settings here; never baked into the image.
- **Restart policy**: `unless-stopped` — auto-restart on host reboot.
- **Healthcheck**: `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:11435/health')"` (no curl in slim image), 30 s interval, 3 retries.

### 2.3 Environment Variable Reference (Full)
| Variable | Default | Description |
|----------|---------|-------------|
| `CLAWBRAIN_DB_DIR` | `/app/data` | SQLite DB and blobs directory (in-container path) |
| `CLAWBRAIN_MAX_CONTEXT_CHARS` | `2000` | Total context budget (chars) injected per request |
| `CLAWBRAIN_TRACE_TTL_DAYS` | `30` | Trace expiry in days (`0` = disabled) |
| `CLAWBRAIN_EXTRA_PROVIDERS` | _(empty)_ | JSON string to inject additional providers |
| `CLAWBRAIN_LOCAL_MODELS` | _(empty)_ | JSON string to whitelist additional local model IDs |

### 2.4 .env.example
Provide a `.env.example` template listing all configurable variables with placeholder values. `.env` is already in `.gitignore`.

### 2.5 .dockerignore
Exclude: `venv/`, `__pycache__/`, `tests/`, `data/`, `.env`, `*.pyc`, `.git/`.
Purpose: Minimise build context. The `data/` directory is mounted as a volume at runtime — it must not be baked into the image.

## 3. Output Targets
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.dockerignore`
