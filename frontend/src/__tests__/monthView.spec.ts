import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useTasks } from '../composables/useTasks'
import MonthView from '../pages/MonthView.vue'
import { localToday, monthGrid, shiftMonth } from '../utils/dates'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn(), remove: vi.fn() },
  }
})
import { ApiError, tasksApi } from '../api'

const today = localToday()
const thisMonth = shiftMonth(today, 0)
const day = (n: number) => `${thisMonth.slice(0, 8)}${String(n).padStart(2, '0')}`
const task = (o = {}) => ({
  id: 't1',
  title: 'Call dentist',
  type: 'PERSONAL',
  requirement: '',
  due_date: day(10),
  completed: false,
  date_created: today,
  ...o,
})

async function mountMonth(tasks: object[]) {
  vi.mocked(tasksApi.list).mockResolvedValue(tasks as never)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
  const w = mount(MonthView, { global: { plugins: [router], stubs: { teleport: true } } })
  await flushPromises()
  return w
}

// jsdom has no DataTransfer, so the drag events carry none; the page tracks the dragged task itself.
async function drag(w: Awaited<ReturnType<typeof mountMonth>>, from: string, to: string) {
  await w.get(`[data-date="${from}"] .chip`).trigger('dragstart')
  await w.get(`[data-date="${to}"]`).trigger('drop')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  useTasks().tasks.value = []
})

describe('month helpers', () => {
  it('builds whole Monday-to-Sunday weeks covering the month', () => {
    const grid = monthGrid('2026-10-15')
    expect(grid.every((w) => w.length === 7)).toBe(true)
    expect(grid[0]![0]).toBe('2026-09-28') // Oct 1 2026 is a Thursday
    expect(grid.at(-1)![6]).toBe('2026-11-01')
  })
  it('needs only four rows when February starts on a Monday', () => {
    expect(monthGrid('2027-02-10')).toHaveLength(4)
  })
  it('shifts months across a year boundary', () => {
    expect(shiftMonth('2026-12-20', 1)).toBe('2027-01-01')
    expect(shiftMonth('2026-01-31', -1)).toBe('2025-12-01')
  })
})

describe('MonthView', () => {
  it('renders the month and highlights today', async () => {
    const w = await mountMonth([])
    expect(w.findAll('.cell').length % 7).toBe(0)
    expect(w.get('.cell--today').attributes('data-date')).toBe(today)
  })

  it('places tasks on their due day', async () => {
    const w = await mountMonth([task()])
    expect(w.get(`[data-date="${day(10)}"]`).text()).toContain('Call dentist')
  })

  it('navigates to the next and previous month', async () => {
    const w = await mountMonth([])
    const label = w.get('h1').text()
    await w.get('[aria-label="Next month"]').trigger('click')
    expect(w.get('h1').text()).not.toBe(label)
    await w.get('[aria-label="Previous month"]').trigger('click')
    expect(w.get('h1').text()).toBe(label)
  })

  it('shows tasks due in a later month after navigating to it', async () => {
    const next = shiftMonth(today, 1)
    const w = await mountMonth([task({ due_date: next })])
    expect(w.find(`.cell:not(.cell--outside)[data-date="${next}"]`).exists()).toBe(false)
    await w.get('[aria-label="Next month"]').trigger('click')
    expect(w.get(`.cell:not(.cell--outside)[data-date="${next}"]`).text()).toContain('Call dentist')
  })

  it('opens the task editor when a task is clicked', async () => {
    const w = await mountMonth([task()])
    await w.get('.chip').trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(true)
  })

  it('moves a task to another day when dropped on it', async () => {
    vi.mocked(tasksApi.update).mockResolvedValue(task({ due_date: day(12) }) as never)
    const w = await mountMonth([task()])
    await drag(w, day(10), day(12))
    expect(tasksApi.update).toHaveBeenCalledWith('t1', { due_date: day(12) })
    expect(w.get(`[data-date="${day(12)}"]`).text()).toContain('Call dentist')
    expect(w.get(`[data-date="${day(10)}"]`).text()).not.toContain('Call dentist')
  })

  it('does nothing when dropped on the same day', async () => {
    const w = await mountMonth([task()])
    await drag(w, day(10), day(10))
    expect(tasksApi.update).not.toHaveBeenCalled()
  })

  it('puts the task back and shows an error when the move fails', async () => {
    vi.mocked(tasksApi.update).mockRejectedValue(new ApiError(500, 'Boom'))
    const w = await mountMonth([task()])
    await drag(w, day(10), day(12))
    expect(w.get(`[data-date="${day(10)}"]`).text()).toContain('Call dentist')
    expect(w.get('[role="alert"]').text()).toContain('Boom')
  })

  it('ignores a drop when nothing is being dragged', async () => {
    const w = await mountMonth([task()])
    await w.get(`[data-date="${day(12)}"]`).trigger('drop')
    expect(tasksApi.update).not.toHaveBeenCalled()
  })

  it('shows an error when tasks cannot load', async () => {
    vi.mocked(tasksApi.list).mockRejectedValue(new ApiError(0, 'Cannot reach the server'))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    const w = mount(MonthView, { global: { plugins: [router], stubs: { teleport: true } } })
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Could not load tasks')
  })
})
