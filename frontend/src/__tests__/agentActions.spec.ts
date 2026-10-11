import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NoteAgentActions from '../components/NoteAgentActions.vue'
import TaskAgentActions from '../components/TaskAgentActions.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    agentsApi: { planDay: vi.fn(), summarizeNote: vi.fn() },
  }
})
import { agentsApi, ApiError } from '../api'

const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find((b) => b.text() === text)!
const deferred = <T>() => {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => (resolve = r))
  return { promise, resolve }
}

beforeEach(() => vi.resetAllMocks())

describe('TaskAgentActions', () => {
  it('shows the plan with reasons', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue({
      date: '2026-01-02',
      items: [
        { task_id: 't1', title: 'Call dentist', due_date: '2026-01-02', reason: 'closes early', estimate_minutes: 30 },
        { task_id: 't2', title: 'Write report', due_date: '2026-01-02', reason: 'big', estimate_minutes: 90 },
        { task_id: 't3', title: 'Unranked', due_date: '2026-01-01', reason: '', estimate_minutes: null },
      ],
    })
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    await flushPromises()
    expect(w.get('[aria-label="Day plan"]').text()).toContain('Call dentist')
    expect(w.text()).toContain('closes early')
  })

  it('shows each estimate and the total, ignoring tasks without one', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue({
      date: '2026-01-02',
      items: [
        { task_id: 't1', title: 'A', due_date: '2026-01-02', reason: 'r', estimate_minutes: 30 },
        { task_id: 't2', title: 'B', due_date: '2026-01-02', reason: 'r', estimate_minutes: 90 },
        { task_id: 't3', title: 'C', due_date: '2026-01-01', reason: '', estimate_minutes: null },
      ],
    })
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    await flushPromises()
    const items = w.findAll('li').map((li) => li.text())
    expect(items[0]).toContain('~30 min')
    expect(items[1]).toContain('~1 h 30 min')
    expect(items[2]).not.toContain('~')
    expect(w.text()).toContain('Estimated total: 2 h')
  })

  it('omits the total when no task has an estimate', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue({
      date: '2026-01-02',
      items: [{ task_id: 't3', title: 'C', due_date: '2026-01-01', reason: '', estimate_minutes: null }],
    })
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    await flushPromises()
    expect(w.text()).not.toContain('Estimated total')
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

  it('disables the action while it is running', async () => {
    const d = deferred<{ date: string; items: [] }>()
    vi.mocked(agentsApi.planDay).mockReturnValue(d.promise)
    const w = mount(TaskAgentActions)
    await btn(w, 'Plan my day').trigger('click')
    expect(btn(w, 'Planning…').attributes('disabled')).toBeDefined()
    d.resolve({ date: 'x', items: [] })
    await flushPromises()
    expect(btn(w, 'Plan my day').attributes('disabled')).toBeUndefined()
  })
})

describe('NoteAgentActions', () => {
  const mountIt = (unsaved = false) => mount(NoteAgentActions, { props: { noteId: 'n1', unsaved } })

  it('is disabled while the note has unsaved changes', async () => {
    const w = mountIt(true)
    expect(btn(w, 'Summarize').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Save your changes first')
    await btn(w, 'Summarize').trigger('click')
    expect(agentsApi.summarizeNote).not.toHaveBeenCalled()
  })

  it('emits the updated note after summarizing', async () => {
    const updated = { id: 'n1', title: 'T', content: 'a\n\nSummary: x', date_created: 'd' }
    vi.mocked(agentsApi.summarizeNote).mockResolvedValue(updated)
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    await flushPromises()
    expect(w.emitted('summarized')![0]).toEqual([updated])
  })

  it('shows an error and keeps the note unchanged when summarizing fails', async () => {
    vi.mocked(agentsApi.summarizeNote).mockRejectedValue(new ApiError(400, 'Note has no content'))
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Note has no content')
    expect(w.emitted('summarized')).toBeUndefined()
    expect(btn(w, 'Summarize').attributes('disabled')).toBeUndefined()
  })
})
