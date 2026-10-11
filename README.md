# command_center

Personal dashboard: daily news briefing, tasks and notes, with local LLM agents on top. See `docs/IMPLEMENTATION_PLAN.md` for the plan and `docs/architecture/` for how each part works (`AGENTS.md`, `DATABASE.md`, `FRONTEND.md`, `TRAINING.md`).

## Prerequisites
- Python 3.10+, Node 20+, Docker
- [Ollama](https://ollama.com) with `ollama pull gemma4:e2b`, only for the manual steps below (`make up` runs Ollama in Docker)

## Setup
```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

## Start everything with one command
```bash
make up      # db, Ollama (+ model pull), migrations, API, MCP server, frontend
```
Frontend http://localhost:5173, API http://localhost:8000/docs, MCP http://localhost:8765/mcp. First run downloads the Ollama model. `make down` stops, `make reset` also deletes the database and models. Code is bind-mounted, so API and frontend reload on edit. This stack is for local development only: the API runs with `--reload`, source is bind-mounted into the containers, and Postgres is published on localhost with a default password. Do not expose it as is. Ollama runs in Docker (CPU only on macOS); for GPU speed, run native Ollama instead and use the manual steps below.

## Start manually (run each in its own terminal, from the repo root)

**1. Database**
```bash
docker compose up -d db
alembic upgrade head
```

**2. API** (http://localhost:8000, docs at `/docs`)
```bash
uvicorn backend.services.api.api:app --reload --port 8000
```

**3. MCP server** (streamable HTTP at http://127.0.0.1:8765/mcp). Must be running before the tasks or notes agents are called.
```bash
python -m backend.services.mcp.server
```
Host and port come from `MCP_HOST` / `MCP_PORT`; agents find it through `MCP_URL`.

**4. LLM calls and agents**

`backend/ai/llm/` holds plain model calls (news briefing, note summary, day plan, week balance). They need only Ollama (`ollama serve` if it is not already running) and are reached through `/api/agents/<agent>/actions/<name>` and the briefing service. `backend/ai/agents/` holds the tool-calling study buddy (note quiz), which records weak points directly in the database; the MCP server (step 3) exposes task and note tools for agents built with `run_agent`, which no feature uses yet.

**5. Frontend** (http://localhost:5173, proxies `/api` to the API on port 8000)
```bash
cd frontend
npm run dev
```

## Reset the database
Stops the container and deletes the `pgdata` volume. This erases all data, including the test database; rerun the `CREATE DATABASE` step under Tests afterwards.
```bash
docker compose down -v
docker compose up -d db
alembic upgrade head
```

## Tests
```bash
# one-time: create the throwaway test database
docker compose exec db psql -U command_center -c "CREATE DATABASE command_center_test"
pytest                      # backend
cd frontend && npm test     # frontend
```

## Configuration (`.env`)
| Variable | Default |
|---|---|
| `DATABASE_URL` | local Postgres from `docker-compose.yml` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `gemma4:e2b` |
| `AGENT_TIMEOUT_SECONDS` | `180`, how long a model call or stream may run before the API gives up |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `command_center` (read by `docker-compose.yml`; keep `DATABASE_URL` in step) |
| `MCP_HOST` / `MCP_PORT` / `MCP_URL` | `127.0.0.1` / `8765` / `http://127.0.0.1:8765/mcp` |
| `LANGSMITH_*` | tracing for agent runs (optional) |
