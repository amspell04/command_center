# Frontend

Vue 3 + Vite + TypeScript in `frontend/`.

## API wiring
- `src/api.ts` is the only place that calls `fetch`. It exposes `tasksApi`, `notesApi`, `goalsApi`, `newsApi`, `weakPointsApi`, `trainingApi` and `agentsApi` (`planDay(date)` and `balanceWeek(date)` send the local date), throws `ApiError` with a readable message (FastAPI `detail`, or a generic/network message), and returns `undefined` on 204.
- All calls go to `/api/*`. The Vite dev server proxies `/api` to `http://localhost:8000` and strips the prefix, because the FastAPI routes are mounted without `/api` (`/tasks`, `/notes`).
- Types in `src/types/index.ts` mirror the backend models.

## Panels and modals
- `BaseModal.vue`: shared dialog (teleported to body, closes on Escape or backdrop click). `ConfirmModal.vue` wraps it for destructive confirmations.
- `TasksPanel.vue`: groups tasks into Overdue, Today, Upcoming and Completed. Overdue and Today always show in full; Upcoming shows the next 5 and Completed the latest 3, each behind a "See more (N)" toggle, so the home page height stays bounded. "New task" opens `TaskModal.vue` in create mode. Clicking a task title opens the same modal in edit mode (save, mark complete/incomplete, delete). The row checkbox completes quickly and the row Delete button deletes immediately with no confirmation.
- Layout: `HomeView.vue` is one shared surface split by hairlines, not boxed cards. A full-width week timeline sits on top; below it are three columns: Today, Tasks, and a side column (Goals, News, Notes).
- `composables/useTasks.ts`: one task list shared by Today, Tasks and the week timeline, so a change in one panel shows in all. Concurrent loads share a single request.
- `WeekTimeline.vue`: Monday-to-Sunday strip (same week definition as the backend). Each task sits on its due day, coloured by type, struck through when done, red when overdue. Clicking a task opens `TaskModal`. Today's column is highlighted.
- `ProgressTicker.vue`: thin bar above the home page. A looping marquee (pauses on hover, static and scrollable under reduced-motion) of tasks completed vs total, current goal titles, and weak points identified vs covered (resolved). Tasks come from the shared `useTasks` list; goals and weak points (`GET /weak_points`) load once on mount, so goal edits show on next page load. If a source fails the rest still show with a warning.
- `pages/MonthView.vue` (`/calendar`): full-month grid (Monday start, padded with neighbouring-month days), reached from "Open month calendar" above the week strip. Previous/next/Today navigation. Tasks use the same chips and `TaskModal` as the week. Dragging a task onto another day updates its `due_date` immediately and rolls back with an error message if the request fails. Grid maths lives in `utils/dates.ts` (`monthGrid`, `shiftMonth`, `monthLabel`).
- `TodayPanel.vue`: the daily planner. Without a plan it lists what is due today or overdue. "Plan my day" calls the task agent with the browser's local date (refreshed when the tab becomes visible again, so a tab left open past midnight moves to the new day) and then shows the week status (on track / at risk / off track, a short summary, the week's numbers, and a check per goal), the agent's order split into Top priorities (first 3) and Also today with time estimates and a total, and a Coming up list for the rest of the week. Dismiss returns to the default list.
- `GoalsPanel.vue` / `GoalModal.vue`: create, edit and delete personal goals. Goals are sent to the plan-my-day agent.
- `NewsBriefing.vue`: the latest briefing's headline, which links to `/news/:id`. If none exists yet today it shows the most recent one and a "Generate briefing" button. When today's briefing exists it shows "Regenerate", which replaces it. A 409 on generate (made in another tab) just loads the existing briefing.
- `NewsView.vue` (`/news/:id`): the full briefing (summary, quiz, sources) with Print.
- `NotesPanel.vue`: "New note" opens `NoteCreateModal.vue` (title only), then navigates to the new note's page. Each note links to `/notes/:id`. Delete asks for confirmation via `ConfirmModal`.
- `pages/NoteView.vue` (`/notes/:id`): the note's sub page. Editable title and one markdown document: a textarea while editing, rendered (marked + DOMPurify sanitized) after clicking Done, with an Edit button to return. Empty notes open in edit mode. The stored AI summary shows under the note (with a notice when the note changed since), and the button reads Summarize or Regenerate summary. Explicit Save with unsaved-change tracking, and delete with confirmation. The page loads the note with `GET /notes/{id}`; a 404 shows "Note not found", any other failure shows the error. `NoteAgentActions.vue` is the Summarize button (disabled while there are unsaved edits, since the agent reads the saved note).
- `pages/TrainingView.vue` (`/training`, linked from the home page): progress, week balance, workout log, training maxes and the program editor. `composables/useGymWeek.ts` feeds gym markers into `WeekTimeline` and `TodayPanel`. `trainingApi` in `api.ts` wraps `/training/*`. See `TRAINING.md` for how these pieces work.
- All views show loading and error states and keep user input if a request fails.

## Running
- Dev: `make up` from the repo root, or `uvicorn backend.services.api.api:app` on port 8000 then `npm run dev` in `frontend/`. The proxy target is `http://localhost:8000`, or `API_PROXY_TARGET` (set by Docker Compose).
- The study buddy endpoint (`POST /agents/notes/study_buddy/stream`) has no UI yet.
- Tests: `npm test` (Vitest + Vue Test Utils, API mocked).

## UI conventions

Shared primitives live in `src/assets/styles/global.css`; components should use them instead of re-styling controls in scoped CSS.

- **Buttons**: default (secondary), `btn--primary`, `btn--danger` (outlined), `btn--danger-solid` (confirm dialogs), `btn--ghost` (borderless, row actions; pair with `btn--danger` for Delete/Remove). Sizes: 32px default, `btn--sm` 28px. `btn--icon` is a square glyph button; `btn-group` joins buttons (month prev/today/next).
- **Navigation**: `nav-link` is the one style for text controls that go to another page, on `RouterLink` or `button`. Plain `a` links are accent-coloured with underline on hover. `page-bar` is the top row of sub pages: `← Home`, title, then right-aligned controls (`page-bar__end`).
- **Task chips**: `chip`, `chip--done`, `chip--overdue` and `dot--*` are global and shared by the week and month views.
- **Sub page blocks**: `section` (hairline-separated block with an uppercase `h2`; `section__head` adds a right-side action slot), `field` (stacked label + control), `data-table` (hairline table), and `badge--ok/warn/danger`.
- **Training page**: Progress cards across the top, then a two-column row (workout log left; week balance and training maxes right), then the program editor. Progress cards show the estimated 1RM as the headline figure with a gain badge and collapsed records.
- **Note page**: single 800px column. Borderless title, a sticky toolbar (Edit/Done, Summarize, Delete, Save), the summary in a tinted card, then the note. Markdown typography is styled under `.markdown` in `NoteView.vue`.
- **News page**: single 760px column matching the Note page. Date label, large title and Print button in the header, the summary as body text, quiz questions as numbered expandable cards, and sources as a hairline list (http(s) sources are links).
