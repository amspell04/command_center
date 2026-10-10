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

export interface NoteBlock {
  content: string
}

export interface Note {
  id: string
  title: string
  content_blocks: NoteBlock[]
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
}

export interface DayPlan {
  date: string
  items: PlannedTask[]
}

export interface SweepProposal {
  task_id: string
  title: string
  current_due_date: string
  new_due_date: string
  reason: string
}

export interface CritiquePoint {
  point: string
  quote: string
}

export interface NoteCritique {
  gaps: CritiquePoint[]
  unclear_claims: CritiquePoint[]
  questions: string[]
}
