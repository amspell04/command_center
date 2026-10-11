# AGENTS

How the model-backed features are organised. `backend/ai/` has two kinds of code:

- `llm/`: plain model calls. One call in, one result out; no tools, no DB access. The caller loads the data and saves the result.
- `agents/`: tool-calling agents. The model chooses which tools to call, in a loop. Tools come from the MCP server.

## Flow

```
route / briefing service --> ai/llm (one model call) --> route validates against the DB and writes via crud/
agent (tool loop) --(streamable HTTP)--> MCP server --> crud/ --> Postgres
```

## MCP server (`backend/services/mcp/server.py`)
- FastMCP server, streamable HTTP on `MCP_HOST:MCP_PORT` (default `127.0.0.1:8765`, path `/mcp`). Start with `python -m backend.services.mcp.server`.
- Each tool opens its own session with `get_session()`, calls one `crud/` function and returns plain JSON. Failures raise `ToolError`.
- Tools use flat arguments (not nested models) to suit the 2B model.
- Tools: `create_task`, `list_tasks`, `update_task`, `complete_task`, `create_note`, `search_notes`, `append_note_content`. There are no delete tools.
- `append_note_content` appends a new paragraph to the note's markdown and never replaces it. Tasks have no priority field and notes have no tags field, so the plan's `update_task_priority` and `add_tags` are not implemented.

## LLM calls (`backend/ai/llm/`)
- `client.py`: `get_llm(name)` is the shared `ChatOllama` factory (model and URL from settings, temperature 0, tagged with the call name for tracing). `load_prompt(name)` reads `prompts/<name>.md`.
- Tracing: `config.configure_tracing()` exports the `LANGSMITH_*` settings from `.env` to the environment (pydantic-settings does not do this itself) and runs on import. Tracing is on only when `LANGSMITH_TRACING=true` and an API key is set. Single-shot functions and `run_agent`/`stream_agent` are `@traceable` chain runs, so the model, tool and graph-step runs nest under them. Agent runs are named `<name>_agent` and tagged with the agent name.
- `tasks.plan_day(message, day)`: one structured call that orders due and overdue tasks with a `reason` and an `estimate_minutes` (5 to 480) each, plus a week status update (`ON_TRACK`, `AT_RISK` or `OFF_TRACK`, a short summary, and an on-track check per goal). The route (`services/api/agent_routes.py`) builds the message itself: the due tasks with their ids, the week's numbers (Monday to Sunday: due so far, completed, due later; `overdue_open` counts every open task due before the planned date, including earlier weeks, matching what is planned) and the user's goals, so the model never counts or looks anything up. Tasks have no completion timestamp, so "completed" means a task due this week that is now marked done. The route sets the estimate to null for tasks the model skipped and drops ranked tasks and goal checks with unknown or repeated ids. When nothing is due the model is not run and only the week numbers are returned.
- `notes.summarize_note(title, text)`: returns the summary text. The route strips any leading `Summary:`, rejects an empty reply (502) and stores the result in the note's `summary` columns (`summary`, `summary_generated_at`, `summary_source_hash`), never in `content`. A hash of the title and trimmed content is saved with it. If a summary exists and the hash still matches, the route returns it without calling the model; an edit makes it stale (`summary_stale`) so the next call regenerates, and `force: true` regenerates regardless. A failed run keeps the previous summary.
- `training.balance_week(message, day)`: structured output (status, summary, up to four dated suggestions). The route (`POST /agents/training/actions/balance_week`) builds the message from the week's tasks, gym sessions, program week and the soonest goal date, then keeps only suggestions dated within the week and not before the planned date. It skips the model when the week has no gym days. See `TRAINING.md`.
- `news.summarize_news(articles, sources)`: structured output. Input is capped for the small context window; the briefing service stores the result.

## News briefing (`backend/services/news/`)
`news.py` fetches the RSS URLs in `feeds.json` (a JSON list of full `https://` feed URLs, not web pages), keeps the last 24 hours, at most 10 per feed, and de-duplicates by link. A feed that fails to load is skipped. `briefing.py` runs fetch, summarize and store behind a lock. `POST /news/refresh` creates today's briefing once: 409 if it exists, 502 if no feed returned articles. With `?replace=true` the new briefing is stored first and the old one deleted afterwards, so a failed run keeps the old one.

`plan_day` and `balance_week` take an optional `date` in the request body. The frontend sends the browser's local date, and the same `day` fills `{today}` in the prompt and drives the week maths, so the model and the numbers agree. The server's own date is the fallback.

The action routes keep the URL shape `POST /agents/{agent}/actions/{name}` (`task/plan_day`, `notes/summarize_note`). `guarded()` maps model failures to HTTP errors: timeout 504, unusable output 502, anything else 503; an `HTTPException` raised inside the call passes through unchanged.

## Agents (`backend/ai/agents/`)
- `runner.py`: `load_tools(allowed)` fetches tools from the MCP server and keeps only the allow-listed names, raising if one is missing. `run_agent` runs the tool-calling loop (`langchain.agents.create_agent`). No agent uses it yet.
- `study_buddy/`: quizzes the user on one note over SSE (`POST /agents/notes/study_buddy/stream`). Its `add_weak_point` tool is bound to the note id and records the topic in the `weak_points` table through `crud/weak_points.py`; the note's `content` is never edited. The stream emits a `weak_point` event when a topic is new or re-opened. The route loads the note's open (unresolved) weak points and the system prompt lists up to 20 of them in a `<weak_points>` block, so the agent asks about them early and does not re-add them.

## Dependencies
`mcp` is pinned below 2 because `langchain-mcp-adapters` 0.3.1 does not import against `mcp` 2.x. This also pins `fastmcp` to 3.x.
