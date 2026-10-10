# Parallel Work Plan

Companion to `PLAN.md`. While **you** build the LangChain agents, **Claude** builds the database, migrations and API service. The two tracks only meet at a small, agreed interface, defined below so neither side blocks the other.

## Split

| Track | Owner | Directories (only this owner edits these) |
|---|---|---|
| A: Agents | You | `backend/agents/`, `backend/services/news_service/`, `scripts/` (smoke tests) |
| B: Data + API | Claude | `backend/db/`, `backend/crud/`, `backend/schemas/`, `backend/services/api_service/`, `alembic/`, `alembic.ini`, `docker-compose.yml`, `.env.example` |

Shared and edited by agreement only: `requirements.txt`, `docs/`, `.env`.

Frontend (Vite + Vue) is unassigned for now. It depends on Track B's API, so it is best started once Track B's Phase B2 is done.

## The interface between tracks

The seam is a **CRUD layer**: plain Python functions that take a SQLAlchemy `Session` and return ORM objects or Pydantic schemas. API routes and agent tools both call it, so there is one source of truth for DB access and agents never write SQL.

### What Track B provides to Track A
```python
# backend/db/session.py
get_session() -> contextmanager yielding Session   # for agents/jobs (scripts, tools)
get_db()      -> FastAPI dependency                # used by routes only

# backend/crud/tasks.py
create_task(db, title, due_date=None, priority="medium") -> Task
list_tasks(db, date=None, status=None)                   -> list[Task]
update_task(db, task_id, **fields)                       -> Task | None

# backend/crud/notes.py
create_note(db, title, body, tags=None)  -> Note
search_notes(db, query, limit=10)        -> list[Note]   # ILIKE on title/body to start
add_tags(db, note_id, tags)              -> Note | None
list_notes(db)                           -> list[Note]

# backend/crud/briefings.py
upsert_briefing(db, date, summary_md, sources) -> Briefing
get_briefing(db, date)                         -> Briefing | None
```
There is no delete in the crud functions Track A needs. Deletes exist only behind API routes (Principle 2: agents can't delete).

### What Track A provides to Track B
```python
# backend/agents/__init__.py: one entrypoint per agent
class AgentResult(BaseModel):
    output: str                  # text to show the user
    tool_calls: list[dict] = []  # [{name, args, result}], for the UI and debugging
    error: str | None = None

run_tasks_agent(text: str)      -> AgentResult
run_notes_agent(text: str)      -> AgentResult
run_news_agent(articles: list)  -> AgentResult   # output = markdown briefing
```
Track B will wire `POST /api/agents/tasks`, `POST /api/agents/notes` and `POST /api/briefing/refresh` to these. Until Track A lands them, Track B uses **stub implementations** in `backend/agents/_stubs.py` (or a try/except import) that return a canned `AgentResult`, so the API and frontend can be built and tested without an LLM. Please overwrite the stubs, not rename the functions.

### Contract rules
1. Signatures above are frozen unless either side asks to change them in the "Change requests" section below.
2. Models (`Task`, `Note`, `Briefing`) are defined by Track B. If an agent needs a new field, request it; Track B adds a migration.
3. Neither track edits the other's directories. Open a change request instead.
4. Both tracks run against the same Postgres container (`docker compose up -d`).

## Track B tasks (Claude)

### B0: Environment (~30 min)
- [ ] `docker-compose.yml`: Postgres 16, named volume, healthcheck, port 5432
- [ ] `.env.example`: `DATABASE_URL=postgresql+psycopg://...`, plus Ollama and LangSmith placeholders (Track A owns their values)
- [ ] `.gitignore`: `.venv`, `.env`, `__pycache__`, `frontend/dist`, `node_modules`
- [ ] Add `sqlalchemy`, `psycopg[binary]`, `alembic`, `pydantic-settings`, `fastapi`, `uvicorn` to `requirements.txt` (appended; Track A appends its own)
- [ ] Settings module (`backend/config.py`) reading `.env`

### B1: Models and migrations (~1 hr)
- [ ] `db/base.py`, `db/session.py` (engine, `SessionLocal`, `get_db`, `get_session`)
- [ ] `db/models.py`: `Task`, `Note`, `Briefing` (and `Article`, if we keep it); naming convention for constraints so Alembic autogenerate is stable
- [ ] `alembic init` with `env.py` reading `DATABASE_URL` and `Base.metadata`
- [ ] Initial migration (`0001_initial`) generated, then **hand-reviewed**
- [ ] Verify: `alembic upgrade head`, `alembic downgrade base`, `alembic upgrade head` all succeed on a fresh DB
- [ ] Seed script (`scripts/seed.py`, Track B) with a few sample tasks and notes for UI and agent testing
- [ ] Notify Track A that the DB is ready (**Milestone M1**)

### B2: CRUD layer and schemas (~1 hr)
- [ ] `schemas/`: Pydantic `Create`/`Update`/`Read` models for tasks, notes and briefings
- [ ] `crud/tasks.py`, `crud/notes.py`, `crud/briefings.py` with the signatures above
- [ ] Small pytest suite against a throwaway test database (CRUD happy paths, `search_notes`, `upsert_briefing` idempotence)
- [ ] Notify Track A that the CRUD layer is importable (**Milestone M2**; this is when agent tools can switch from fake data to the real DB)

### B3: API service (~1.5 hrs)
- [ ] `api.py`: app factory, lifespan, `/api/health` (includes a DB ping), error handlers (consistent JSON errors)
- [ ] Routers: `tasks`, `notes`, `briefing`, `agents`, each in its own module under `api_service/routers/`
- [ ] Tasks: `GET/POST /api/tasks`, `PATCH/DELETE /api/tasks/{id}`; `?date=` and `?status=` filters
- [ ] Notes: `GET/POST /api/notes`, `PATCH/DELETE /api/notes/{id}`; `?q=` search
- [ ] Briefing: `GET /api/briefing/today`, `POST /api/briefing/refresh` (calls Track A's `run_news_agent` via the stub-able import)
- [ ] Agents: `POST /api/agents/tasks`, `POST /api/agents/notes` returning `AgentResult`; per-call timeout so a slow LLM returns a clean error, not a hung request
- [ ] Static mount of `frontend/dist` if it exists (skipped otherwise)
- [ ] Route tests with FastAPI `TestClient`
- [ ] Notify Track A that the API is up (**Milestone M3**; Track A can now test agents end to end from `/docs`)

### B4: Hardening (~30 min, only if time allows)
- [ ] CORS settings for the Vite dev server (a fallback if the proxy is not used)
- [ ] Pagination on list endpoints
- [ ] Request logging with a request ID that can be attached to LangSmith metadata
- [ ] Update `PLAN.md` and the README to say migrations use Alembic

## Track A tasks (you), for reference
These are from `PLAN.md`; nothing here is a commitment from Track B.
- [ ] Phase 0 smoke test and model decision gate
- [ ] `agents/llm.py`, LangSmith tracing, one module per agent
- [ ] Tool definitions that wrap the `crud` functions (once M2 lands, until then fake in-memory data)
- [ ] Implement `run_*_agent` entrypoints returning `AgentResult`
- [ ] `news.py` and `daily_job.py` (calls `crud.briefings.upsert_briefing`)

## Timeline and sync points

| Milestone | Target | Unblocks |
|---|---|---|
| M0: contract agreed (this document) | Now | Both tracks start |
| M1: DB + migrations ready | ~1.5 hrs in | Track A can connect a real DB and seed data |
| M2: CRUD layer importable | ~2.5 hrs in | Tool functions use real CRUD |
| M3: API up, agent endpoints stubbed | ~4 hrs in | End-to-end test from `/docs`; frontend can start |
| M4: Track A entrypoints replace stubs | Track A's pace | Real agents behind the API |

A short check-in at each milestone is enough: pull, run `alembic upgrade head`, and run the tests.

## Working agreements
- **Git:** one branch per track (`track-a-agents`, `track-b-api`), merged into `main` at milestones. Conflicts should be limited to `requirements.txt` and `docs/`.
- **Migrations:** only Track B creates them. A model change request from Track A comes with the field name, type and reason.
- **Database resets:** `docker compose down -v` wipes data. Do it freely in dev but say so, since the other track's seeded data goes too.
- **Secrets:** `.env` is never committed; `.env.example` always matches the variables in use.

## Change requests
Add entries here to propose changes to the contract. Format: `[date] [track] request: reason: status`.

- (none yet)

## Open questions
- [ ] Is a plain `ILIKE` search on notes enough for `search_notes`, or do you want Postgres full-text search (a `tsvector` column plus a GIN index) from the start?
- [ ] Should agent tools use `get_session()` directly, or should Track B expose async CRUD? (Assumed sync; the LangChain tools run synchronously.)
- [ ] Is the `Article` table needed, or are the briefing's `sources` (jsonb) enough?
- [ ] Do you want the tests (pytest) in the plan at all, given the one-day limit? They are scoped small but can be cut.
