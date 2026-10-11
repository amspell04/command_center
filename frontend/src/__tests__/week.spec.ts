import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WeekTimeline from '../components/WeekTimeline.vue'
import { useTasks } from '../composables/useTasks'
import { localToday, weekDates } from '../utils/dates'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn(), remove: vi.fn() },
  }
})
import { ApiError, tasksApi } from '../api'

const today = localToday()
const days = weekDates(today)
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

async function mountWeek(tasks: object[]) {
  vi.mocked(tasksApi.list).mockResolvedValue(tasks as never)
  const w = mount(WeekTimeline, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.resetAllMocks()
  useTasks().tasks.value = []
})

describe('weekDates', () => {
  it('runs Monday to Sunday around the given day', () => {
    expect(weekDates('2026-10-14')).toHaveLength(7)
    expect(weekDates('2026-10-14')[0]).toBe('2026-10-12')
    expect(weekDates('2026-10-14')[6]).toBe('2026-10-18')
  })
  it('puts Sunday at the end of its week, not the start of the next', () => {
    expect(weekDates('2026-10-18')[0]).toBe('2026-10-12')
    expect(weekDates('2026-10-12')[0]).toBe('2026-10-12')
  })
  it('crosses a month boundary', () => {
    expect(weekDates('2026-10-30')).toEqual([
      '2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01',
    ])
  })
})

describe('WeekTimeline', () => {
  it('renders seven days and highlights today', async () => {
    const w = await mountWeek([])
    expect(w.findAll('.day')).toHaveLength(7)
    expect(w.findAll('.day--today')).toHaveLength(1)
    expect(w.get('.day--today').attributes('data-date')).toBe(today)
  })

  it('places each task on its due day and omits tasks outside the week', async () => {
    const other = days[0] === today ? days[1] : days[0]
    const w = await mountWeek([
      task(),
      task({ id: 't2', title: 'Other day', due_date: other }),
      task({ id: 't3', title: 'Next month', due_date: '2099-01-01' }),
    ])
    expect(w.get(`[data-date="${today}"]`).text()).toContain('Call dentist')
    expect(w.get(`[data-date="${other}"]`).text()).toContain('Other day')
    expect(w.text()).not.toContain('Next month')
  })

  it('marks completed tasks as done', async () => {
    const w = await mountWeek([task({ completed: true })])
    expect(w.get('.chip').classes()).toContain('chip--done')
  })

  it('marks open tasks from earlier days as overdue', async () => {
    const earlier = days.find((d) => d < today)
    if (!earlier) return // today is Monday: nothing earlier in the week
    const w = await mountWeek([task({ due_date: earlier })])
    expect(w.get('.chip').classes()).toContain('chip--overdue')
  })

  it('opens the task editor when a task is clicked', async () => {
    const w = await mountWeek([task()])
    await w.get('.chip').trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(true)
  })

  it('shows an error when the week cannot load', async () => {
    vi.mocked(tasksApi.list).mockRejectedValue(new ApiError(0, 'Cannot reach the server'))
    const w = mount(WeekTimeline, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Could not load the week')
  })
})
