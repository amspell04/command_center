# Database

Postgres 16 (Docker), SQLAlchemy 2.x ORM, Alembic migrations. Table definitions are in `IMPLEMENTATION_PLAN.md` under Data model; the training tables are in `TRAINING.md`.

## Where things live

| Path | Purpose |
|---|---|
| `backend/db/base.py` | `Base` and constraint naming convention |
| `backend/db/models.py` | ORM models (`Task`, `Note`, `News`, `Goal`, `WeakPoint`, plus the training tables) |
| `backend/db/session.py` | Engine, `get_session()` (agents/jobs), `get_db()` (FastAPI) |
| `backend/models/` | Pydantic models the ORM mirrors (also API response models) |
| `backend/crud/schemas/` | Pydantic request models (`*Create`, `*Update`) |
| `backend/crud/` | All SQL: `tasks.py`, `notes.py`, `news.py`, `goals.py`, `weak_points.py`, `training.py`. Shared by API routes and agents |
| `backend/services/api/` | Routes only (`api.py`, `agent_routes.py`, `study_buddy_routes.py`, `training_routes.py`); call `crud`, map missing rows to 404 |
| `backend/config.py` | Reads `DATABASE_URL` from `.env` |
| `backend/alembic/versions/` | Migration files (`alembic.ini` is in the repo root) |

## Local setup

```bash
cp .env.example .env              # default DATABASE_URL works with docker-compose
docker compose up -d db           # start Postgres on :5432 (plain `up -d` starts the whole stack)
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head              # create tables
```

Reset: `docker compose down -v` drops the `pgdata` volume (all data, including the test DB); then start Postgres and run `alembic upgrade head` again.

Check: `docker compose exec db psql -U command_center -c '\dt'` should list `tasks`, `notes`, `news`, `goals`, `weak_points`, the training tables and `alembic_version`.

## Credentials

User, password and database name all default to `command_center`. Local development only; the port is published on `127.0.0.1:5432` only, but use a real password if other users share the machine.

- `docker-compose.yml` reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` from `.env`, falling back to the defaults.
- The app reads `DATABASE_URL` (default: `postgresql+psycopg://command_center:command_center@localhost:5432/command_center`).
- To change them, set the `POSTGRES_*` variables and update `DATABASE_URL` to match. Postgres only applies them when the volume is first created, so run `docker compose down -v` first (wipes data).

## Changing the schema

1. Edit `backend/db/models.py`.
2. Generate a migration (DB must be running and at `head`):
   ```bash
   alembic revision --autogenerate -m "short description"
   ```
3. Review the generated file in `backend/alembic/versions/`. Autogenerate misses enum changes, renames (seen as drop + add) and server defaults, so edit by hand where needed.
4. Apply: `alembic upgrade head`.
5. Test the rollback: `alembic downgrade -1`, then `alembic upgrade head`.
6. Update the Data model section in `IMPLEMENTATION_PLAN.md`. Never edit a migration that has already been shared; add a new one.

## Common commands

| Command | Effect |
|---|---|
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back the latest migration |
| `alembic downgrade base` | Roll back everything |
| `alembic current` | Show the revision the DB is at |
| `alembic history` | List all revisions |
| `alembic upgrade head --sql` | Print SQL without a DB connection |
| `docker compose up -d db` / `down` | Start / stop Postgres (`down` stops every service), data is kept |
| `docker compose down -v` | Stop and **wipe all data** (named volume `pgdata`) |
| `docker compose exec db psql -U command_center` | Open a SQL shell |

## CRUD layer and endpoints

CRUD functions take a `Session`, commit themselves, and return ORM objects (`None`/`False` when the id is missing). Agents use them via `get_session()`, routes via `get_db()`. Routes do no SQL.

| Route | CRUD function |
|---|---|
| `POST /tasks`, `GET /tasks`, `PATCH /tasks/{id}`, `PATCH /tasks/{id}/complete`, `DELETE /tasks/{id}` | `crud/tasks.py` |
| `POST /notes`, `GET /notes?q=` (case-insensitive; `%` and `_` match literally), `GET /notes/{id}`, `PATCH /notes/{id}`, `DELETE /notes/{id}` | `crud/notes.py` |
| `GET /weak_points?resolved=` (all notes), `GET /notes/{id}/weak_points?resolved=`, `PATCH /weak_points/{id}`, `DELETE /weak_points/{id}` | `crud/weak_points.py` (rows are written by the study buddy agent) |
| `POST /goals`, `GET /goals`, `PATCH /goals/{id}`, `DELETE /goals/{id}` | `crud/goals.py` |
| `/training/*` (maxes, programs, exercises, sessions, progress, week) | `crud/training.py`, see `TRAINING.md` |
| `GET /news/today`, `GET /news/latest` (newest day), `GET /news/{id}`, `POST /news/refresh` (409 if today's briefing exists; `?replace=true` swaps it for a new one) | `crud/news.py` (the news agent writes with `create_news`) |

PATCH bodies must contain at least one field and no nulls, otherwise 422 (the one exception is a goal's `target_date`, which can be set to null to clear it). Unknown ids return 404.

## Tests

Tests run against a separate database so dev data is untouched. Create it once, then run pytest:

```bash
docker compose exec db psql -U command_center -d postgres -c "CREATE DATABASE command_center_test"
pytest
```

The schema is created from the ORM models at session start and dropped at the end. Override the target with `TEST_DATABASE_URL`.

## Reset to a clean database

```bash
docker compose down -v && docker compose up -d db && alembic upgrade head
```

## Notes

- Ids are UUIDs generated by the database (`gen_random_uuid()`), `date_created` defaults to the current date.
- `goals` (`id`, `title`, `details`, `date_created`) is added by migration `0002_goals`; run `alembic upgrade head`.
- Migration `0005_training` adds `goals.target_date` and the training tables (`training_maxes`, `programs`, `program_sets`, `workout_sessions`, `lift_sets`, enum `lift`). Weights are stored in lb. Details are in `TRAINING.md`.
- Migration `0004_note_summary` adds the `notes.summary`, `summary_generated_at` and `summary_source_hash` columns.
- `weak_points` (`id`, `note_id`, `topic`, `resolved`, `date_created`) is added by migration `0003_weak_points`. `note_id` cascades on note delete; `(note_id, lower(topic))` is unique. A repeat miss on an open row changes nothing; on a resolved row it re-opens it.
- `notes.content` is a single markdown `text` column. `news.quiz_section` is a JSONB list; `news.sources` is `text[]`.
- Adding a value to the `task_type` enum needs a hand-written `ALTER TYPE task_type ADD VALUE ...` in the migration.
- Connection errors on `alembic` commands mean the container isn't running or isn't healthy yet (`docker compose ps`).
