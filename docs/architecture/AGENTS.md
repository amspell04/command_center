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
- `tasks.plan_day(message)`: one structured call that orders due and overdue tasks with a `reason` and an `estimate_minutes` (5 to 480) each, plus a week status update (`ON_TRACK`, `AT_RISK` or `OFF_TRACK`, a short summary, and an on-track check per goal). The route (`services/api/agent_routes.py`) builds the message itself: the due tasks with their ids, the week's numbers (Monday to Sunday: due so far, completed, overdue and open, due later) and the user's goals, so the model never counts or looks anything up. Tasks have no completion timestamp, so "completed" means a task due this week that is now marked done. The route sets the estimate to null for tasks the model skipped and drops ranked tasks and goal checks with unknown or repeated ids. When nothing is due the model is not run and only the week numbers are returned.
- `notes.summarize_note(title, text)`: returns the summary text. The route strips any leading `Summary:`, rejects an empty reply (502) and appends `Summary: <text>` to the note itself.
- `news.summarize_news(articles, sources)`: structured output. Input is capped for the small context window; the briefing service stores the result.

The action routes keep the URL shape `POST /agents/{agent}/actions/{name}` (`task/plan_day`, `notes/summarize_note`). `guarded()` maps model failures to HTTP errors: timeout 504, unusable output 502, anything else 503.

## Agents (`backend/ai/agents/`)
- `runner.py`: `load_tools(allowed)` fetches tools from the MCP server and keeps only the allow-listed names, raising if one is missing. `run_agent` runs the tool-calling loop (`langchain.agents.create_agent`). No agent uses it yet.
- `study_buddy/`: quizzes the user on one note over SSE (`POST /agents/notes/study_buddy/stream`). Its `add_weak_point` tool is bound to the note id and records the topic in the `weak_points` table through `crud/weak_points.py`; the note's `content` is never edited. The stream emits a `weak_point` event when a topic is new or re-opened. The route loads the note's open (unresolved) weak points and the system prompt lists up to 20 of them in a `<weak_points>` block, so the agent asks about them early and does not re-add them.

## Dependencies
`mcp` is pinned below 2 because `langchain-mcp-adapters` 0.3.1 does not import against `mcp` 2.x. This also pins `fastmcp` to 3.x.
