Action: plan the user's day.
Call list_tasks with completed=false (no other filters). Plan only tasks due on or before the date you are given; overdue tasks come first.
Order them by what to do first. Give one short reason per task.
Also estimate how many minutes each task will take (whole minutes, 5 to 480). Base it on the title and requirement; round to the nearest 5 and prefer realistic over optimistic.
Use only task ids returned by list_tasks. If there are no such tasks, return an empty list.
