import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TodayPanel from '../components/TodayPanel.vue'
import WeekTimeline from '../components/WeekTimeline.vue'
import { useGymWeek } from '../composables/useGymWeek'
import { useTasks } from '../composables/useTasks'
import { localToday, weekDates } from '../utils/dates'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn(), remove: vi.fn() },
    agentsApi: { planDay: vi.fn(), summarizeNote: vi.fn() },
    trainingApi: { week: vi.fn() },
  }
})
import { ApiError, tasksApi, trainingApi } from '../api'

const today = localToday()
const week = weekDates(today)
const other = week.find((d) => d !== today)!
const gym = (o = {}) => ({ date: today, logged: false, lifts: ['Squat'], sets: 3, details: ['Squat 3x5 at 80%'], ...o })

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(tasksApi.list).mockResolvedValue([])
  useTasks().tasks.value = []
  useGymWeek().days.value = []
})

async function mountWeek(days: object[]) {
  vi.mocked(trainingApi.week).mockResolvedValue(days as never)
  const w = mount(WeekTimeline, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return w
}

describe('WeekTimeline gym markers', () => {
  it('marks only the days with a session, naming the lifts', async () => {
    const w = await mountWeek([gym({ lifts: ['Squat', 'Bench'] }), gym({ date: other, lifts: ['Deadlift'] })])
    const markers = w.findAll('[data-testid="gym"]')
    expect(markers).toHaveLength(2)
    expect(w.get(`[data-date="${today}"] [data-testid="gym"]`).text()).toBe('Squat · Bench')
    expect(w.get(`[data-date="${other}"] [data-testid="gym"]`).text()).toBe('Deadlift')
    expect(markers[0]!.attributes('title')).toBe('Squat 3x5 at 80%')
  })

  it('shows a done session differently from a planned one', async () => {
    const w = await mountWeek([gym({ logged: true })])
    const marker = w.get('[data-testid="gym"]')
    expect(marker.classes()).toContain('gym--done')
    expect(marker.text()).toContain('✓')
    const planned = await mountWeek([gym()])
    expect(planned.get('[data-testid="gym"]').classes()).not.toContain('gym--done')
  })

  it('shows no markers when there are no sessions', async () => {
    const w = await mountWeek([])
    expect(w.find('[data-testid="gym"]').exists()).toBe(false)
  })

  it('still shows the week and its tasks when the gym request fails', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([
      { id: 't1', title: 'Call dentist', type: 'PERSONAL', requirement: '', due_date: today, completed: false, date_created: today },
    ] as never)
    vi.mocked(trainingApi.week).mockRejectedValue(new ApiError(500, 'boom'))
    const w = mount(WeekTimeline, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(w.findAll('.day')).toHaveLength(7)
    expect(w.text()).toContain('Call dentist')
    expect(w.find('[data-testid="gym"]').exists()).toBe(false)
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })
})

describe('TodayPanel gym line', () => {
  async function mountToday(days: object[]) {
    vi.mocked(trainingApi.week).mockResolvedValue(days as never)
    const w = mount(TodayPanel)
    await flushPromises()
    return w
  }

  it("shows today's planned exercises", async () => {
    const w = await mountToday([gym({ details: ['Squat 3x5 at 80%', 'Bench 5x3 at 75%'] })])
    const line = w.get('[data-testid="gym-today"]').text()
    expect(line).toContain('Gym today')
    expect(line).toContain('Squat 3x5 at 80% · Bench 5x3 at 75%')
  })

  it('says it is done once the session is logged', async () => {
    const w = await mountToday([gym({ logged: true, details: ['3 sets of Squat, already logged'] })])
    expect(w.get('[data-testid="gym-today"]').text()).toContain('Gym · done')
  })

  it('shows nothing when the gym day is another day or the request fails', async () => {
    expect((await mountToday([gym({ date: other })])).find('[data-testid="gym-today"]').exists()).toBe(false)
    useGymWeek().days.value = []
    vi.mocked(trainingApi.week).mockRejectedValue(new ApiError(0, 'down'))
    const w = mount(TodayPanel)
    await flushPromises()
    expect(w.find('[data-testid="gym-today"]').exists()).toBe(false)
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })
})
