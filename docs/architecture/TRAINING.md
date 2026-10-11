# TRAINING

Powerlifting tracking: a percentage-based program, a log of what was lifted, progress per lift, and an agent that balances the week's tasks against gym days. Only squat, bench and deadlift are tracked.

## Units
Weights are stored and entered in lb. kg is always derived (`lb / 2.20462`, one decimal) and shown next to lb so both units are learned side by side. Working weights round to the nearest 5 lb, halves up (`PLATE_INCREMENT_LB` in `crud/training.py`).

## Data (migration `0005_training`)
- `training_maxes`: the max a program's percentages come from. History is kept, one row per lift and date (setting one again replaces it atomically with an upsert); the latest row on or before a date applies to that date. Changing a max never rewrites past sessions.
- `programs`: name, `start_date` (week 1, day 1), `weeks`, `active`. A partial unique index allows one active program; creating or activating one switches the other off.
- `program_sets`: one prescribed exercise (week, day 1 to 7, lift, sets, reps, percent). Its calendar date is `start_date + (week - 1) * 7 + (day - 1)`, so shifting the start date moves the whole program. Working weight is `percent * training max in force that day`; it is null until the lift has a max.
- `workout_sessions`: one per date, with optional bodyweight and notes. `lift_sets`: the sets lifted (lift, weight, reps, order) with an optional link to the `program_sets` row they were done for. Deleting a program row keeps the logged set and clears the link.
- `goals.target_date`: optional deadline. The meet is a goal with a date; per-lift targets stay as text in its details.
- Estimated 1RM, volume-style numbers and records are computed, never stored (Epley: `weight * (1 + reps / 30)`, a single is itself).

## Backend
- `crud/training.py`: all SQL plus the unit and 1RM maths. Domain refusals (week past the program end, copying into a non-empty week, unknown program set, losing a race to activate a program or save a session) raise `TrainingError`, which the API returns as 422 with a readable message.
- `services/api/training_routes.py` (`/training`): maxes, programs, exercises (including `copy_week`), `planned?date=` (what the program prescribes for a day), sessions (a PUT for a date replaces that day's sets), `progress/{lift}` (best estimated 1RM per date) and `week?date=` (the week's gym days, logged or planned).
- `gym_day` prefers a logged session over the plan, so the same lookup feeds the timeline markers and the agent.

## Balance my week (agent action)
`POST /agents/training/actions/balance_week` follows the `plan_day` pattern: one structured model call, no tools. It takes the browser's date (`date` in the body), which sets the week and the prompt's "today". The route builds the Monday to Sunday week itself: tasks due and done per day, the gym session per day, the program week, and the soonest upcoming goal date as the meet. The model only returns a status (`BALANCED`, `TIGHT`, `OVERLOADED`), a short summary and up to four dated suggestions. The route drops suggestions outside the week or before the planned date, blank or repeated ones, and skips the model when the week has no gym days. The prompt forbids moving or skipping sessions because the program is fixed. Tasks have no stored time estimate, so load is judged from task counts. The prompt also asks for food, water and caffeine guidance on gym days, scaled to the session and the task load (for example caffeine later in the day and extra sleep after a crowded day before a heavy lift), with a caffeine cap. That guidance is returned as dated suggestions, so it shares the four-suggestion limit.

## Frontend (`/training`)
- The page opens with `TrainingMaxes`, then progress, week balance and the program editor. A `Log a workout` button in the page bar opens `WorkoutLog` in a modal.
- `WorkoutLog` (modal): pick a date; a planned day is prefilled with one row per set and computed weights, a logged day opens for editing. Saving a logged date replaces its sets.
- `TrainingProgress`: per lift the latest estimated 1RM, change since the first session, a chart placed by calendar date and the most recent records (a record is a session whose best set beat every earlier one).
- `WeekBalance`: runs the agent action (sending today's local date) and shows its result beside the server's own day table.
- `TrainingMaxes`: one large block per lift showing the current max in lb and kg, with an Edit button that opens a modal for that lift. Saving records a new dated max and keeps history.
- `ProgramEditor`: edit the program as a table per week where each cell saves on change, with week copy.
- `WeekTimeline` and `TodayPanel` show gym days through `useGymWeek`. A failed load shows no markers and no error.
- `GoalModal` has the optional target date; clearing it sends null (`target_date` is the only nullable PATCH field).

## Limits
- One session per date; the log has no RPE or fatigue by design.
- Balance quality depends on the small local model; the numbers it is shown are always computed by the server.
