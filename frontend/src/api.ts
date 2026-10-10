import type { DayPlan, NewNote, News, NewTask, Note, NoteCritique, SweepProposal, Task } from './types'

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
  create: (n: NewNote) => request<Note>('/notes', json('POST', n)),
  update: (id: string, changes: Partial<NewNote>) => request<Note>(`/notes/${id}`, json('PATCH', changes)),
  remove: (id: string) => request<void>(`/notes/${id}`, { method: 'DELETE' }),
}

export const newsApi = {
  today: () => request<News[]>('/news/today'),
  refresh: () => request<News>('/news/refresh', { method: 'POST' }),
}

const action = <T>(agent: string, name: string, body: object = {}) =>
  request<T>(`/agents/${agent}/actions/${name}`, json('POST', body))

export const agentsApi = {
  planDay: () => action<DayPlan>('task', 'plan_day'),
  overdueSweep: () => action<{ proposals: SweepProposal[] }>('task', 'overdue_sweep'),
  summarizeNote: (noteId: string) => action<Note>('notes', 'summarize_note', { note_id: noteId }),
  critiqueNote: (noteId: string) => action<NoteCritique>('notes', 'critique_note', { note_id: noteId }),
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'Something went wrong'
}
