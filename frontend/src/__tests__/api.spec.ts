import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentsApi, ApiError, newsApi, tasksApi } from '../api'

const respond = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('POSTs JSON to /api/tasks', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(201, { id: '1' }))
    vi.stubGlobal('fetch', fetchMock)
    await tasksApi.create({ title: 'a', type: 'WORK', requirement: '', due_date: '2026-01-01' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/tasks')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body).title).toBe('a')
  })

  it('returns undefined on 204', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(204)))
    await expect(tasksApi.remove('1')).resolves.toBeUndefined()
  })

  it('surfaces string detail on 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(404, { detail: 'Task not found' })))
    await expect(tasksApi.complete('x')).rejects.toMatchObject({ status: 404, message: 'Task not found' })
  })

  it('joins validation errors on 422', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(422, { detail: [{ msg: 'bad' }, { msg: 'worse' }] })))
    await expect(tasksApi.list()).rejects.toThrow('bad; worse')
  })

  it('falls back to generic message on non-JSON error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })))
    await expect(tasksApi.list()).rejects.toThrow('Request failed (500)')
  })

  it('wraps network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')))
    await expect(tasksApi.list()).rejects.toBeInstanceOf(ApiError)
  })
})

describe('agent and news endpoints', () => {
  const stub = (status = 200, body: unknown = {}) => {
    const fetchMock = vi.fn().mockResolvedValue(respond(status, body))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('POSTs agent actions to /api/agents/<agent>/actions/<name>', async () => {
    const f = stub()
    await agentsApi.planDay()
    await agentsApi.overdueSweep()
    await agentsApi.summarizeNote('n1')
    await agentsApi.critiqueNote('n1')
    expect(f.mock.calls.map(([url]) => url)).toEqual([
      '/api/agents/task/actions/plan_day',
      '/api/agents/task/actions/overdue_sweep',
      '/api/agents/notes/actions/summarize_note',
      '/api/agents/notes/actions/critique_note',
    ])
    expect(f.mock.calls.every(([, init]) => init.method === 'POST')).toBe(true)
    expect(JSON.parse(f.mock.calls[2][1].body)).toEqual({ note_id: 'n1' })
  })

  it('POSTs the briefing refresh with no body', async () => {
    const f = stub(201)
    await newsApi.refresh()
    expect(f.mock.calls[0][0]).toBe('/api/news/refresh')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('surfaces agent error details', async () => {
    stub(503, { detail: 'Agent unavailable: check that the MCP server and Ollama are running' })
    await expect(agentsApi.planDay()).rejects.toMatchObject({ status: 503 })
  })
})
