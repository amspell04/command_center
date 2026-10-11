# AGENTS

How the LLM agents reach the data. Tasks and notes agents go through an MCP server; the news agent never touches it.

## Flow

```
tasks / notes agent --(streamable HTTP)--> MCP server --> crud/ --> Postgres
daily job --> news agent (summarize only, structured output) --> daily job writes via crud/
```

## MCP server (`backend/services/mcp/server.py`)
- FastMCP server, streamable HTTP on `MCP_HOST:MCP_PORT` (default `127.0.0.1:8765`, path `/mcp`). Start with `python -m backend.services.mcp.server`.
- Each tool opens its own session with `get_session()`, calls one `crud/` function and returns plain JSON. Failures raise `ToolError`.
- Tools use flat arguments (not nested models) to suit the 2B model.
- Tools: `create_task`, `list_tasks`, `update_task`, `complete_task`, `create_note`, `search_notes`, `append_note_content`. There are no delete tools.
- `append_note_content` appends a new paragraph to the note's markdown and never replaces it. Tasks have no priority field and notes have no tags field, so the plan's `update_task_priority` and `add_tags` are not implemented.

## Agents (`backend/agents/`)
- `llm.py`: shared `ChatOllama` factory (model and URL from settings, temperature 0, tagged with the agent name for tracing).
- `runner.py`: `load_tools(allowed)` fetches tools from the MCP server and keeps only the allow-listed names, raising if one is missing. `run_agent` runs the tool-calling loop (`langchain.agents.create_agent`).
- `task_agent`, `notes_agent`: a system prompt plus a per-agent tool allow-list.
- `task` / `plan_day`: orders due and overdue tasks and returns a `reason` and an `estimate_minutes` (5 to 480) per task, plus a week status update (`ON_TRACK`, `AT_RISK` or `OFF_TRACK`, a short summary, and an on-track check per goal), in one model call. The route computes the week's numbers itself (Monday to Sunday: tasks due so far, completed, overdue and open, due later) and passes them with the user's goals in the message, so the model never counts. Tasks have no completion timestamp, so "completed" means a task due this week that is now marked done. The route sets the estimate to null for tasks the model skipped and drops goal checks for unknown or repeated goal ids. When nothing is due the model is not run and only the week numbers are returned.
- `news_agent`: `summarize_news(articles, sources)`. No tools and no DB access. Input is capped for the small context window; the caller stores the result.

## Dependencies
`mcp` is pinned below 2 because `langchain-mcp-adapters` 0.3.1 does not import against `mcp` 2.x. This also pins `fastmcp` to 3.x.
