# Frontend

Vue 3 + Vite + TypeScript in `frontend/`.

## API wiring
- `src/api.ts` is the only place that calls `fetch`. It exposes `tasksApi` and `notesApi`, throws `ApiError` with a readable message (FastAPI `detail`, or a generic/network message), and returns `undefined` on 204.
- All calls go to `/api/*`. The Vite dev server proxies `/api` to `http://localhost:8000` and strips the prefix, because the FastAPI routes are mounted without `/api` (`/tasks`, `/notes`).
- Types in `src/types/index.ts` mirror the backend models.

## Panels and modals
- `BaseModal.vue`: shared dialog (teleported to body, closes on Escape or backdrop click). `ConfirmModal.vue` wraps it for destructive confirmations.
- `TasksPanel.vue`: groups tasks into Today (due today or overdue), Upcoming and Completed. "New task" opens `TaskModal.vue` in create mode. Clicking a task title opens the same modal in edit mode (save, mark complete/incomplete, delete). The row checkbox completes quickly and the row Delete button deletes immediately with no confirmation.
- `NotesPanel.vue`: "New note" opens `NoteCreateModal.vue` (title only), then navigates to the new note's page. Each note links to `/notes/:id`. Delete asks for confirmation via `ConfirmModal`.
- `pages/NoteView.vue` (`/notes/:id`): the note's sub page. Editable title and a list of markdown-style text blocks (add, remove), explicit Save with unsaved-change tracking, and delete with confirmation. The API has no single-note endpoint, so the page finds the note in `GET /notes`.
- All views show loading and error states and keep user input if a request fails.

## Running
- Dev: `uvicorn backend.services.api.api:app` on port 8000, then `npm run dev` in `frontend/`.
- Tests: `npm test` (Vitest + Vue Test Utils, API mocked).
