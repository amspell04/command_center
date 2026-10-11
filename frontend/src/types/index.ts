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
  summary: string | null
  summary_generated_at: string | null
  summary_stale: boolean // the note changed after the summary was written
}

export type NewNote = Pick<Note, 'title' | 'content'>

export interface NewsQuizQuestion {
  question: string
  answer: string
}

export interface NewsArticleLink {
  title: string
  url: string
}

export interface News {
  id: string
  title: string
  summary: string
  body: string
  quiz_section: NewsQuizQuestion[]
  sources: string[]
  articles: NewsArticleLink[]
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
  target_date: string | null // optional deadline, e.g. the meet
  date_created: string
}

export type NewGoal = Pick<Goal, 'title' | 'details'> & { target_date?: string | null }

export interface WeakPoint {
  id: string
  note_id: string
  topic: string
  resolved: boolean
  date_created: string
}

// Study buddy stream (backend/services/api/study_buddy_routes.py)

export type StudyMode = 'quiz' | 'review'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export type StudyBuddyEvent =
  | { type: 'token'; text: string }
  | { type: 'weak_point'; topic: string }
  | { type: 'weak_point_resolved'; topic: string }
  | { type: 'done' }
  | { type: 'error'; message: string }

// Training (backend/models/training.py). Weights are stored in lb; kg is derived by the backend.

export type Lift = 'SQUAT' | 'BENCH' | 'DEADLIFT'

export interface TrainingMax {
  id: string
  lift: Lift
  weight_lb: number
  weight_kg: number
  effective_date: string
}

export interface Program {
  id: string
  name: string
  start_date: string // week 1, day 1
  weeks: number
  active: boolean
}

export type NewProgram = Omit<Program, 'id'>

// One prescribed exercise, e.g. 3 x 5 at 80% of the training max.
export interface Exercise {
  id: string
  program_id: string
  week: number
  day: number // 1 to 7, counted from the program's start date
  lift: Lift
  sets: number
  reps: number
  percent: number
  weight_lb: number | null // null until the lift has a training max
  weight_kg: number | null
  date: string
}

export type NewExercise = Pick<Exercise, 'week' | 'day' | 'lift' | 'sets' | 'reps' | 'percent'>

// Logged workouts

export interface WorkoutSet {
  id: string
  lift: Lift
  weight_lb: number
  weight_kg: number
  reps: number
  set_order: number
  estimated_1rm_lb: number
  estimated_1rm_kg: number
  program_set_id: string | null // the prescription this set was done for
}

export interface WorkoutSession {
  id: string
  date: string
  notes: string
  bodyweight_lb: number | null
  bodyweight_kg: number | null
  sets: WorkoutSet[]
}

export interface NewWorkoutSet {
  lift: Lift
  weight: number // lb
  reps: number
  program_set_id: string | null
}

export interface NewWorkoutSession {
  date: string
  notes: string
  bodyweight: number | null // lb
  sets: NewWorkoutSet[]
}

export interface E1RMPoint {
  date: string
  estimated_1rm_lb: number
  estimated_1rm_kg: number
}

// Training week balance (backend/services/api/agent_routes.py)

export interface GymDay {
  date: string
  logged: boolean // true once the session happened, false while it is only planned
  lifts: string[]
  sets: number
  details: string[]
}

export type BalanceStatus = 'BALANCED' | 'TIGHT' | 'OVERLOADED'

export interface BalanceDay {
  date: string
  weekday: string
  tasks_due: number
  tasks_done: number
  task_titles: string[]
  gym: GymDay | null
}

export interface WeekBalance {
  start: string
  end: string
  days: BalanceDay[]
  meet: { title: string; date: string; days_left: number } | null
  program: string | null
  status: BalanceStatus | null // null when the model was not run
  summary: string
  suggestions: { date: string; action: string }[]
}
