import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentsApi, ApiError, newsApi, studyBuddyApi, tasksApi, trainingApi, weakPointsApi } from '../api'

const respond = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

afterEach(() => vi.unstubAllGlobals())

const sse = (chunks: string[], status = 200) =>
  new Response(
    new ReadableStream({
      start(c) {
        chunks.forEach((x) => c.enqueue(new TextEncoder().encode(x)))
        c.close()
      },
    }),
    { status },
  )
const collect = async (it: AsyncIterable<unknown>) => {
  const out: unknown[] = []
  for await (const e of it) out.push(e)
  return out
}

describe('study buddy stream', () => {
  const msgs = [{ role: 'user' as const, content: 'Start' }]

  it('POSTs the mode and conversation and parses frames split across chunks', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        sse(['data: {"type":"token","te', 'xt":"Hi"}\n\ndata: {"type":"done"}\n\n']),
      )
    vi.stubGlobal('fetch', fetchMock)
    expect(await collect(studyBuddyApi.stream('n1', 'review', msgs))).toEqual([
      { type: 'token', text: 'Hi' },
      { type: 'done' },
    ])
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/agents/notes/study_buddy/stream')
    expect(JSON.parse(init.body)).toEqual({ note_id: 'n1', mode: 'review', messages: msgs })
  })

  it('skips malformed and non-data frames', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sse([': ping\n\ndata: {oops\n\ndata: {"type":"done"}\n\n'])))
    expect(await collect(studyBuddyApi.stream('n1', 'quiz', msgs))).toEqual([{ type: 'done' }])
  })

  it('throws the server detail on a non-2xx response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(400, { detail: 'This note is empty' })))
    await expect(collect(studyBuddyApi.stream('n1', 'quiz', msgs))).rejects.toMatchObject({
      status: 400,
      message: 'This note is empty',
    })
  })

  it('throws a friendly error when the server is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')))
    await expect(collect(studyBuddyApi.stream('n1', 'quiz', msgs))).rejects.toMatchObject({
      message: 'Cannot reach the server',
    })
  })
})

describe('api client', () => {
  it('lists weak points, optionally filtered by resolved', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(respond(200, [])))
    vi.stubGlobal('fetch', fetchMock)
    await weakPointsApi.list()
    await weakPointsApi.list(false)
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(['/api/weak_points', '/api/weak_points?resolved=false'])
  })

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
    await expect(tasksApi.complete('x')).rejects.toMatchObject({
      status: 404,
      message: 'Task not found',
    })
  })

  it('joins validation errors on 422', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(respond(422, { detail: [{ msg: 'bad' }, { msg: 'worse' }] })),
    )
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
    const fetchMock = vi.fn().mockImplementation(async () => respond(status, body))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('POSTs agent actions to /api/agents/<agent>/actions/<name>', async () => {
    const f = stub()
    await agentsApi.planDay('2026-10-14')
    await agentsApi.summarizeNote('n1')
    expect(f.mock.calls.map(([url]) => url)).toEqual([
      '/api/agents/task/actions/plan_day',
      '/api/agents/notes/actions/summarize_note',
    ])
    expect(f.mock.calls.every(([, init]) => init.method === 'POST')).toBe(true)
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ date: '2026-10-14' })
    expect(JSON.parse(f.mock.calls[1][1].body)).toEqual({ note_id: 'n1', force: false })
    await agentsApi.summarizeNote('n1', true)
    expect(JSON.parse(f.mock.calls[2][1].body)).toEqual({ note_id: 'n1', force: true })
  })

  it('POSTs the briefing refresh with no body', async () => {
    const f = stub(201)
    await newsApi.refresh()
    expect(f.mock.calls[0][0]).toBe('/api/news/refresh')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('POSTs the briefing refresh with replace=true when regenerating', async () => {
    const f = stub(201)
    await newsApi.refresh(true)
    expect(f.mock.calls[0][0]).toBe('/api/news/refresh?replace=true')
  })

  it('GETs the latest briefing and a briefing by id', async () => {
    const f = stub()
    await newsApi.latest()
    await newsApi.get('b1')
    expect(f.mock.calls.map(([url]) => url)).toEqual(['/api/news/latest', '/api/news/b1'])
  })

  it('surfaces agent error details', async () => {
    stub(503, { detail: 'Agent unavailable: check that the MCP server and Ollama are running' })
    await expect(agentsApi.planDay('2026-10-14')).rejects.toMatchObject({ status: 503 })
  })

  it('talks to the training endpoints', async () => {
    const f = stub()
    await trainingApi.setMax({ lift: 'SQUAT', weight: 405, effective_date: '2026-10-12' })
    await trainingApi.exercises('p1')
    await trainingApi.updateExercise('e1', { percent: 85 })
    await trainingApi.copyWeek('p1', 1, 2)
    await trainingApi.removeExercise('e1')
    expect(f.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ['/api/training/maxes', 'PUT'],
      ['/api/training/programs/p1/sets', undefined],
      ['/api/training/sets/e1', 'PATCH'],
      ['/api/training/programs/p1/copy_week', 'POST'],
      ['/api/training/sets/e1', 'DELETE'],
    ])
    expect(JSON.parse(f.mock.calls[3][1].body)).toEqual({ from_week: 1, to_week: 2 })
  })

  it('talks to the planned and session endpoints', async () => {
    const f = stub()
    await trainingApi.planned('2026-10-12')
    await trainingApi.sessionsBetween('2026-10-12', '2026-10-12')
    await trainingApi.saveSession({ date: '2026-10-12', notes: '', bodyweight: null, sets: [] })
    await trainingApi.removeSession('s1')
    expect(f.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ['/api/training/planned?date=2026-10-12', undefined],
      ['/api/training/sessions?start=2026-10-12&end=2026-10-12', undefined],
      ['/api/training/sessions', 'PUT'],
      ['/api/training/sessions/s1', 'DELETE'],
    ])
  })

  it('GETs the gym week and POSTs the week balance action', async () => {
    const f = stub()
    await trainingApi.week()
    await agentsApi.balanceWeek('2026-10-14')
    expect(JSON.parse(f.mock.calls[1][1].body)).toEqual({ date: '2026-10-14' })
    expect(f.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ['/api/training/week', undefined],
      ['/api/agents/training/actions/balance_week', 'POST'],
    ])
  })

  it('surfaces training validation errors', async () => {
    stub(422, { detail: 'Week 2 already has exercises' })
    await expect(trainingApi.copyWeek('p1', 1, 2)).rejects.toMatchObject({ status: 422, message: 'Week 2 already has exercises' })
  })
})
