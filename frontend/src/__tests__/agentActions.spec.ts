import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NoteAgentActions from '../components/NoteAgentActions.vue'
import TaskAgentActions from '../components/TaskAgentActions.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: { update: vi.fn() },
    agentsApi: { planDay: vi.fn(), overdueSweep: vi.fn(), summarizeNote: vi.fn(), critiqueNote: vi.fn() },
  }
})
import { agentsApi, ApiError, tasksApi } from '../api'

const btn = (w: ReturnType<typeof mount>, text: string) => w.findAll('button').find((b) => b.text() === text)!
const proposal = (o = {}) => ({
  task_id: 't1', title: 'File taxes', current_due_date: '2026-01-01', new_due_date: '2026-01-05', reason: 'busy week', ...o,
})
const deferred = <T,>() => {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => (resolve = r))
  return { promise, resolve }
}

beforeEach(() => vi.resetAllMocks())

describe('TaskAgentActions', () => {
  it('shows the plan with reasons', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue({
      date: '2026-01-02',
      items: [{ task_id: 't1', title: 'Call dentist', due_date: '2026-01-02', reason: 'closes early' }],
    })
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    await flushPromises()
    expect(w.get('[aria-label="Day plan"]').text()).toContain('Call dentist')
    expect(w.text()).toContain('closes early')
  })

  it('says so when there is nothing to plan, and can dismiss', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue({ date: '2026-01-02', items: [] })
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Nothing to plan')
    await btn(w, 'Dismiss').trigger('click')
    expect(w.find('[aria-label="Day plan"]').exists()).toBe(false)
  })

  it('shows an error and re-enables the buttons when the agent fails', async () => {
    vi.mocked(agentsApi.planDay).mockRejectedValue(new ApiError(503, 'Agent unavailable'))
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Agent unavailable')
    expect(w.find('[aria-label="Day plan"]').exists()).toBe(false)
    expect(btn(w, 'Plan my day').attributes('disabled')).toBeUndefined()
  })

  it('disables both actions while one is running', async () => {
    const d = deferred<{ date: string; items: [] }>()
    vi.mocked(agentsApi.planDay).mockReturnValue(d.promise)
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    expect(btn(w, 'Planning…').attributes('disabled')).toBeDefined()
    expect(btn(w, 'Overdue sweep').attributes('disabled')).toBeDefined()
    d.resolve({ date: 'x', items: [] })
    await flushPromises()
    expect(btn(w, 'Overdue sweep').attributes('disabled')).toBeUndefined()
  })

  it('accepting a proposal updates the task and emits it', async () => {
    vi.mocked(agentsApi.overdueSweep).mockResolvedValue({ proposals: [proposal(), proposal({ task_id: 't2', title: 'Other' })] })
    vi.mocked(tasksApi.update).mockResolvedValue({ id: 't1', due_date: '2026-01-05' } as never)
    const w = mount(TaskAgentActions)
    await btn(w, 'Overdue sweep').trigger('click')
    await flushPromises()
    await w.get('[aria-label="Accept File taxes"]').trigger('click')
    await flushPromises()
    expect(tasksApi.update).toHaveBeenCalledWith('t1', { due_date: '2026-01-05' })
    expect(w.emitted('updated')).toHaveLength(1)
    expect(w.text()).not.toContain('File taxes')
    expect(w.text()).toContain('Other')
  })

  it('rejecting a proposal changes nothing', async () => {
    vi.mocked(agentsApi.overdueSweep).mockResolvedValue({ proposals: [proposal()] })
    const w = mount(TaskAgentActions)
    await btn(w, 'Overdue sweep').trigger('click')
    await flushPromises()
    await w.get('[aria-label="Reject File taxes"]').trigger('click')
    expect(tasksApi.update).not.toHaveBeenCalled()
    expect(w.emitted('updated')).toBeUndefined()
    expect(w.text()).toContain('No overdue tasks to reschedule')
  })

  it('keeps a proposal when accepting fails so it can be retried', async () => {
    vi.mocked(agentsApi.overdueSweep).mockResolvedValue({ proposals: [proposal()] })
    vi.mocked(tasksApi.update).mockRejectedValue(new ApiError(404, 'Task not found'))
    const w = mount(TaskAgentActions)
    await btn(w, 'Overdue sweep').trigger('click')
    await flushPromises()
    await w.get('[aria-label="Accept File taxes"]').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Task not found')
    expect(w.text()).toContain('File taxes')
    expect(w.emitted('updated')).toBeUndefined()
  })
})

describe('NoteAgentActions', () => {
  const mountIt = (unsaved = false) => mount(NoteAgentActions, { props: { noteId: 'n1', unsaved } })

  it('is disabled while the note has unsaved changes', async () => {
    const w = mountIt(true)
    expect(btn(w, 'Summarize').attributes('disabled')).toBeDefined()
    expect(btn(w, 'Critique').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Save your changes first')
    await btn(w, 'Critique').trigger('click')
    expect(agentsApi.critiqueNote).not.toHaveBeenCalled()
  })

  it('shows the critique with quotes', async () => {
    vi.mocked(agentsApi.critiqueNote).mockResolvedValue({
      gaps: [{ point: 'No pressure mentioned', quote: 'Water boils at 100C' }],
      unclear_claims: [{ point: 'Vague', quote: 'it is fast' }],
      questions: ['Why does salt matter?'],
    })
    const w = mountIt()
    await btn(w, 'Critique').trigger('click')
    await flushPromises()
    expect(agentsApi.critiqueNote).toHaveBeenCalledWith('n1')
    const text = w.get('[aria-label="Critique"]').text()
    for (const s of ['No pressure mentioned', 'Water boils at 100C', 'Vague', 'it is fast', 'Why does salt matter?']) {
      expect(text).toContain(s)
    }
  })

  it('shows an empty state when there is nothing to flag', async () => {
    vi.mocked(agentsApi.critiqueNote).mockResolvedValue({ gaps: [], unclear_claims: [], questions: [] })
    const w = mountIt()
    await btn(w, 'Critique').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Nothing to flag')
  })

  it('emits the updated note after summarizing', async () => {
    const updated = { id: 'n1', title: 'T', content_blocks: [{ content: 'a' }, { content: 'Summary: x' }], date_created: 'd' }
    vi.mocked(agentsApi.summarizeNote).mockResolvedValue(updated)
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    await flushPromises()
    expect(w.emitted('summarized')![0]).toEqual([updated])
  })

  it('shows errors from either action', async () => {
    vi.mocked(agentsApi.summarizeNote).mockRejectedValue(new ApiError(400, 'Note has no content'))
    vi.mocked(agentsApi.critiqueNote).mockRejectedValue(new ApiError(502, 'The agent returned an unusable response, try again'))
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Note has no content')
    expect(w.emitted('summarized')).toBeUndefined()
    await btn(w, 'Critique').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('unusable response')
    expect(w.find('[aria-label="Critique"]').exists()).toBe(false)
  })
})
