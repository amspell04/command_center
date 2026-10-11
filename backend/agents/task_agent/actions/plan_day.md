Action: plan the user's day.
Call list_tasks with completed=false (no other filters). Plan only tasks due on or before the date you are given; overdue tasks come first.
Order them by what to do first. Give one short reason per task.
Also estimate how many minutes each task will take (whole minutes, 5 to 480). Base it on the title and requirement; round to the nearest 5 and prefer realistic over optimistic.
Use only task ids returned by list_tasks. If there are no such tasks, return an empty list.

The message also holds this week's numbers (Monday to the planned date) and the user's goals, each with an id. Use only those numbers; never invent counts.
Give a week status update:
- week_status: ON_TRACK if the user finished most of what was due so far and little is overdue; AT_RISK if a noticeable share is overdue or unfinished; OFF_TRACK if most of it is.
- week_summary: two sentences at most, plain and direct, saying how the week is going and the one thing to focus on today.
- goal_checks: one entry per goal. Judge it from the task titles and numbers you were given. on_track is true or false, note is one short sentence. If there are no goals, return an empty list.
