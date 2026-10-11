// Mirrors backend/models/*.py. Dates are ISO strings (YYYY-MM-DD) over the wire.

export type TaskType = 'WORK' | 'PERSONAL'

export interface Task {
  id: string
  title: string
  type: TaskType
  requirement: string
  due_date: string
  completed: boolean
  date_created: string
}

export type NewTask = Omit<Task, 'id' | 'completed' | 'date_created'>

export interface Note {
  id: string
  title: string
  content: string
  date_created: string
}

export type NewNote = Omit<Note, 'id' | 'date_created'>

export interface NewsQuizQuestion {
  question: string
  answer: string
}

export interface News {
  id: string
  title: string
  summary: string
  quiz_section: NewsQuizQuestion[]
  sources: string[]
  date_created: string
}

// Agent action results (backend/services/api/agent_routes.py)

export interface PlannedTask {
  task_id: string
  title: string
  due_date: string
  reason: string
  estimate_minutes: number | null
}

export type WeekStatus = 'ON_TRACK' | 'AT_RISK' | 'OFF_TRACK'

export interface WeekStats {
  start: string
  end: string
  due_so_far: number
  completed_so_far: number
  overdue_open: number
  due_remaining: number
}

export interface GoalStatus {
  goal_id: string
  title: string
  on_track: boolean
  note: string
}

// status is null when the model was not run (nothing was due).
export interface DayPlan {
  date: string
  items: PlannedTask[]
  week: WeekStats
  status: WeekStatus | null
  summary: string
  goals: GoalStatus[]
}

export interface Goal {
  id: string
  title: string
  details: string
  date_created: string
}

export type NewGoal = Omit<Goal, 'id' | 'date_created'>
