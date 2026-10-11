import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TodayPanel from '../components/TodayPanel.vue'
import { useTasks } from '../composables/useTasks'
import { localToday } from '../utils/dates'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn(), remove: vi.fn() },
    agentsApi: { planDay: vi.fn(), summarizeNote: vi.fn() },
  }
})
import { agentsApi, ApiError, tasksApi } from '../api'

const today = localToday()
const shift = (days: number) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const task = (o = {}) => ({
  id: 't1',
  title: 'Call dentist',
  type: 'PERSONAL',
  requirement: '',
  due_date: today,
  completed: false,
  date_created: today,
  ...o,
})
const week = { start: today, end: shift(6), due_so_far: 4, completed_so_far: 3, overdue_open: 1, due_remaining: 2 }
const planned = (id: string, title: string, minutes: number | null, reason = 'why') => ({
  task_id: id,
  title,
  due_date: today,
  reason,
  estimate_minutes: minutes,
})
const plan = (o = {}) => ({
  date: today,
  items: [planned('t1', 'Call dentist', 30)],
  week,
  status: 'ON_TRACK',
  summary: 'Solid week.',
  goals: [],
  ...o,
})

const btn = (w: ReturnType<typeof mount>, text: string) => w.findAll('button').find((b) => b.text() === text)

async function mountPanel(tasks: object[] = [task()]) {
  vi.mocked(tasksApi.list).mockResolvedValue(tasks as never)
  const w = mount(TodayPanel)
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.resetAllMocks()
  useTasks().tasks.value = []
})

describe('TodayPanel before planning', () => {
  it('lists what is due today and overdue, ordered by due date, and hides future and done tasks', async () => {
    const w = await mountPanel([
      task({ id: 'a', title: 'Late', due_date: shift(-2) }),
      task({ id: 'b', title: 'Now' }),
      task({ id: 'c', title: 'Later', due_date: shift(1) }),
      task({ id: 'd', title: 'Finished', completed: true }),
    ])
    const rows = w.findAll('.agenda li').map((li) => li.text())
    expect(rows).toHaveLength(2)
    expect(rows[0]).toContain('Late')
    expect(rows[0]).toContain('Overdue')
    expect(rows[1]).toContain('Now')
    expect(w.text()).not.toContain('Finished')
  })

  it('splits the agenda into top priorities and the rest', async () => {
    const w = await mountPanel([1, 2, 3, 4, 5].map((n) => task({ id: `t${n}`, title: `Task ${n}` })))
    expect(w.findAll('.slot--top')).toHaveLength(3)
    expect(w.text()).toContain('Also today')
    expect(w.findAll('.agenda li')).toHaveLength(5)
  })

  it('shows an empty state with no due tasks and lists upcoming ones', async () => {
    const w = await mountPanel([task({ title: 'Next week-ish', due_date: shift(1) })])
    expect(w.text()).toContain('Nothing due')
    expect(w.get('.upcoming').text()).toContain('Next week-ish')
  })

  it('completing a task from the agenda removes it', async () => {
    vi.mocked(tasksApi.complete).mockResolvedValue(task({ completed: true }) as never)
    const w = await mountPanel()
    await w.get('input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(tasksApi.complete).toHaveBeenCalledWith('t1')
    expect(w.find('.agenda').exists()).toBe(false)
  })

  it('shows an error when completing fails and keeps the task', async () => {
    vi.mocked(tasksApi.complete).mockRejectedValue(new ApiError(500, 'db down'))
    const w = await mountPanel()
    await w.get('input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('db down')
    expect(w.text()).toContain('Call dentist')
  })

  it('shows a load error', async () => {
    vi.mocked(tasksApi.list).mockRejectedValue(new ApiError(0, 'Cannot reach the server'))
    const w = mount(TodayPanel)
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
  })
})

describe('TodayPanel plan my day', () => {
  it('shows the plan in the agent order with reasons, estimates and a total', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue(
      plan({
        items: [planned('t2', 'Write report', 90, 'big'), planned('t1', 'Call dentist', 30, 'closes early')],
      }) as never,
    )
    const w = await mountPanel([task(), task({ id: 't2', title: 'Write report' })])
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    const rows = w.findAll('.agenda li').map((li) => li.text())
    expect(rows[0]).toContain('Write report')
    expect(rows[0]).toContain('big')
    expect(rows[0]).toContain('~1 h 30 min')
    expect(rows[1]).toContain('~30 min')
    expect(w.text()).toContain('Estimated total: 2 h')
  })

  it("sends the browser's date, and the new day once the tab is shown after midnight", async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue(plan() as never)
    const w = await mountPanel([task()])
    await btn(w, 'Plan my day')!.trigger('click')
    expect(agentsApi.planDay).toHaveBeenLastCalledWith(today)

    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(new Date().getFullYear() + 1, 0, 2, 9))
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    await btn(w, 'Plan my day')!.trigger('click')
    expect(agentsApi.planDay).toHaveBeenLastCalledWith(localToday())
    expect(localToday()).not.toBe(today)
    vi.useRealTimers()
    w.unmount()
  })

  it('ignores missing estimates in the total and omits it when none exist', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue(
      plan({ items: [planned('t1', 'Call dentist', null, '')] }) as never,
    )
    const w = await mountPanel()
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    expect(w.text()).not.toContain('Estimated total')
    expect(w.text()).not.toContain('~')
  })

  it('shows the week status, summary, numbers and goal checks', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue(
      plan({
        status: 'AT_RISK',
        summary: 'Falling behind on work.',
        goals: [
          { goal_id: 'g1', title: 'Ship report', on_track: true, note: 'Drafted' },
          { goal_id: 'g2', title: 'Exercise', on_track: false, note: 'No tasks logged' },
        ],
      }) as never,
    )
    const w = await mountPanel()
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    const status = w.get('[aria-label="Week status"]')
    expect(status.text()).toContain('At risk')
    expect(status.text()).toContain('Falling behind on work.')
    expect(status.text()).toContain('3 of 4 due so far done · 1 overdue · 2 later this week')
    const goals = w.findAll('.goals li')
    expect(goals[0].classes()).toContain('goal--ok')
    expect(goals[1].classes()).toContain('goal--off')
    expect(goals[1].text()).toContain('No tasks logged')
  })

  it('shows week numbers but no status line when the agent was skipped', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue(plan({ items: [], status: null, summary: '' }) as never)
    const w = await mountPanel([])
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Nothing to plan.')
    expect(w.find('.pill').exists()).toBe(false)
    expect(w.text()).toContain('3 of 4 due so far done')
  })

  it('dismissing returns to the default agenda', async () => {
    vi.mocked(agentsApi.planDay).mockResolvedValue(plan() as never)
    const w = await mountPanel()
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    await btn(w, 'Dismiss')!.trigger('click')
    expect(w.find('[aria-label="Week status"]').exists()).toBe(false)
    expect(w.text()).toContain('Call dentist')
  })

  it('shows an error and re-enables the button when the agent fails', async () => {
    vi.mocked(agentsApi.planDay).mockRejectedValue(new ApiError(503, 'Agent unavailable'))
    const w = await mountPanel()
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Agent unavailable')
    expect(w.find('[aria-label="Week status"]').exists()).toBe(false)
    expect(btn(w, 'Plan my day')!.attributes('disabled')).toBeUndefined()
  })

  it('disables the button while planning', async () => {
    let resolve!: (v: never) => void
    vi.mocked(agentsApi.planDay).mockReturnValue(new Promise((r) => (resolve = r as never)))
    const w = await mountPanel()
    await btn(w, 'Plan my day')!.trigger('click')
    expect(btn(w, 'Planning…')!.attributes('disabled')).toBeDefined()
    resolve(plan() as never)
    await flushPromises()
    expect(btn(w, 'Plan my day')!.attributes('disabled')).toBeUndefined()
  })
})
