# Frontend

Vue 3 + Vite + TypeScript in `frontend/`.

## API wiring
- `src/api.ts` is the only place that calls `fetch`. It exposes `tasksApi`, `notesApi`, `goalsApi`, `newsApi` and `agentsApi`, throws `ApiError` with a readable message (FastAPI `detail`, or a generic/network message), and returns `undefined` on 204.
- All calls go to `/api/*`. The Vite dev server proxies `/api` to `http://localhost:8000` and strips the prefix, because the FastAPI routes are mounted without `/api` (`/tasks`, `/notes`).
- Types in `src/types/index.ts` mirror the backend models.

## Panels and modals
- `BaseModal.vue`: shared dialog (teleported to body, closes on Escape or backdrop click). `ConfirmModal.vue` wraps it for destructive confirmations.
- `TasksPanel.vue`: groups tasks into Today (due today or overdue), Upcoming and Completed. "New task" opens `TaskModal.vue` in create mode. Clicking a task title opens the same modal in edit mode (save, mark complete/incomplete, delete). The row checkbox completes quickly and the row Delete button deletes immediately with no confirmation.
- Layout: `HomeView.vue` is one shared surface split by hairlines, not boxed cards. A full-width week timeline sits on top; below it are three columns: Today, Tasks, and a side column (Goals, News, Notes).
- `composables/useTasks.ts`: one task list shared by Today, Tasks and the week timeline, so a change in one panel shows in all. Concurrent loads share a single request.
- `WeekTimeline.vue`: Monday-to-Sunday strip (same week definition as the backend). Each task sits on its due day, coloured by type, struck through when done, red when overdue. Clicking a task opens `TaskModal`. Today's column is highlighted.
- `TodayPanel.vue`: the daily planner. Without a plan it lists what is due today or overdue. "Plan my day" calls the task agent and then shows the week status (on track / at risk / off track, a short summary, the week's numbers, and a check per goal), the agent's order split into Top priorities (first 3) and Also today with time estimates and a total, and a Coming up list for the rest of the week. Dismiss returns to the default list.
- `GoalsPanel.vue` / `GoalModal.vue`: create, edit and delete personal goals. Goals are sent to the plan-my-day agent.
- `NewsBriefing.vue`: the latest briefing's headline, which links to `/news/:id`. If none exists yet today it shows the most recent one and a "Generate briefing" button.
- `NewsView.vue` (`/news/:id`): the full briefing (summary, quiz, sources) with Print.
- `NotesPanel.vue`: "New note" opens `NoteCreateModal.vue` (title only), then navigates to the new note's page. Each note links to `/notes/:id`. Delete asks for confirmation via `ConfirmModal`.
- `pages/NoteView.vue` (`/notes/:id`): the note's sub page. Editable title and one markdown document: a textarea while editing, rendered (marked + DOMPurify sanitized) after clicking Done, with an Edit button to return. Empty notes open in edit mode. Explicit Save with unsaved-change tracking, and delete with confirmation. The API has no single-note endpoint, so the page finds the note in `GET /notes`.
- All views show loading and error states and keep user input if a request fails.

## Running
- Dev: `uvicorn backend.services.api.api:app` on port 8000, then `npm run dev` in `frontend/`.
- Tests: `npm test` (Vitest + Vue Test Utils, API mocked).
