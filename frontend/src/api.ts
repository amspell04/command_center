import type {
  DayPlan,
  E1RMPoint,
  Exercise,
  Goal,
  GymDay,
  Lift,
  NewExercise,
  NewGoal,
  NewNote,
  NewProgram,
  NewWorkoutSession,
  News,
  NewTask,
  Note,
  Program,
  Task,
  TrainingMax,
  WeakPoint,
  WeekBalance,
  WorkoutSession,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server')
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) })

export const tasksApi = {
  list: () => request<Task[]>('/tasks'),
  create: (t: NewTask) => request<Task>('/tasks', json('POST', t)),
  update: (id: string, changes: Partial<NewTask> & { completed?: boolean }) =>
    request<Task>(`/tasks/${id}`, json('PATCH', changes)),
  complete: (id: string) => request<Task>(`/tasks/${id}/complete`, { method: 'PATCH' }),
  remove: (id: string) => request<void>(`/tasks/${id}`, { method: 'DELETE' }),
}

export const notesApi = {
  list: () => request<Note[]>('/notes'),
  get: (id: string) => request<Note>(`/notes/${id}`),
  create: (n: NewNote) => request<Note>('/notes', json('POST', n)),
  update: (id: string, changes: Partial<NewNote>) => request<Note>(`/notes/${id}`, json('PATCH', changes)),
  remove: (id: string) => request<void>(`/notes/${id}`, { method: 'DELETE' }),
}

export const goalsApi = {
  list: () => request<Goal[]>('/goals'),
  create: (g: NewGoal) => request<Goal>('/goals', json('POST', g)),
  update: (id: string, changes: Partial<NewGoal>) => request<Goal>(`/goals/${id}`, json('PATCH', changes)),
  remove: (id: string) => request<void>(`/goals/${id}`, { method: 'DELETE' }),
}

export const weakPointsApi = {
  list: (resolved?: boolean) => request<WeakPoint[]>(`/weak_points${resolved === undefined ? '' : `?resolved=${resolved}`}`),
}

export const newsApi = {
  today: () => request<News[]>('/news/today'),
  latest: () => request<News>('/news/latest'),
  get: (id: string) => request<News>(`/news/${id}`),
  refresh: (replace = false) =>
    request<News>(`/news/refresh${replace ? '?replace=true' : ''}`, { method: 'POST' }),
}

export const trainingApi = {
  maxes: () => request<TrainingMax[]>('/training/maxes'),
  setMax: (m: { lift: string; weight: number; effective_date: string }) =>
    request<TrainingMax>('/training/maxes', json('PUT', m)),
  programs: () => request<Program[]>('/training/programs'),
  createProgram: (p: NewProgram) => request<Program>('/training/programs', json('POST', p)),
  updateProgram: (id: string, changes: Partial<NewProgram>) =>
    request<Program>(`/training/programs/${id}`, json('PATCH', changes)),
  removeProgram: (id: string) => request<void>(`/training/programs/${id}`, { method: 'DELETE' }),
  exercises: (programId: string) => request<Exercise[]>(`/training/programs/${programId}/sets`),
  addExercise: (programId: string, e: NewExercise) =>
    request<Exercise>(`/training/programs/${programId}/sets`, json('POST', e)),
  updateExercise: (id: string, changes: Partial<NewExercise>) =>
    request<Exercise>(`/training/sets/${id}`, json('PATCH', changes)),
  removeExercise: (id: string) => request<void>(`/training/sets/${id}`, { method: 'DELETE' }),
  copyWeek: (programId: string, from_week: number, to_week: number) =>
    request<Exercise[]>(`/training/programs/${programId}/copy_week`, json('POST', { from_week, to_week })),
  week: () => request<GymDay[]>('/training/week'),
  planned: (date: string) => request<Exercise[]>(`/training/planned?date=${date}`),
  sessionsBetween: (start: string, end: string) =>
    request<WorkoutSession[]>(`/training/sessions?start=${start}&end=${end}`),
  saveSession: (s: NewWorkoutSession) => request<WorkoutSession>('/training/sessions', json('PUT', s)),
  progress: (lift: Lift) => request<E1RMPoint[]>(`/training/progress/${lift}`),
  removeSession: (id: string) => request<void>(`/training/sessions/${id}`, { method: 'DELETE' }),
}

const action = <T>(agent: string, name: string, body: object = {}) =>
  request<T>(`/agents/${agent}/actions/${name}`, json('POST', body))

export const agentsApi = {
  planDay: (date: string) => action<DayPlan>('task', 'plan_day', { date }),
  balanceWeek: (date: string) => action<WeekBalance>('training', 'balance_week', { date }),
  summarizeNote: (noteId: string, force = false) =>
    action<Note>('notes', 'summarize_note', { note_id: noteId, force }),
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'Something went wrong'
}
