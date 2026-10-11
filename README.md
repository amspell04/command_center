# command_center

Personal dashboard: daily news briefing, tasks and notes, with local LLM agents on top. See `docs/PLAN.md` for the plan and `docs/AGENTS.md` for how the agents reach the data.

## Prerequisites
- Python 3.10+, Node 20+, Docker, [Ollama](https://ollama.com) with `ollama pull qwen3.5:2b`

## Setup
```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

## Start (run each in its own terminal, from the repo root)

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

`backend/ai/llm/` holds plain model calls (news briefing, note summary, day plan). They need only Ollama (`ollama serve` if it is not already running) and are reached through `/api/agents/<agent>/actions/<name>` and the briefing service. `backend/ai/agents/` holds tool-calling agents, which also connect to the MCP server, so start it (step 3) first.

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
| `OLLAMA_MODEL` | `qwen3.5:2b` |
| `MCP_HOST` / `MCP_PORT` / `MCP_URL` | `127.0.0.1` / `8765` / `http://127.0.0.1:8765/mcp` |
| `LANGSMITH_*` | tracing for agent runs (optional) |
