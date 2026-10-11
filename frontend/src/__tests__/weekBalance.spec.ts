import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WeekBalance from '../components/WeekBalance.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return { ...actual, agentsApi: { planDay: vi.fn(), summarizeNote: vi.fn(), balanceWeek: vi.fn() } }
})
import { agentsApi, ApiError } from '../api'

const day = (i: number, o = {}) => ({
  date: `2026-10-${12 + i}`,
  weekday: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][i],
  tasks_due: 0,
  tasks_done: 0,
  task_titles: [],
  gym: null,
  ...o,
})
const gym = (o = {}) => ({ date: '2026-10-12', logged: false, lifts: ['Squat'], sets: 3, details: ['Squat 3x5 at 80%'], ...o })
const result = (o = {}) => ({
  start: '2026-10-12',
  end: '2026-10-18',
  days: [
    day(0, { gym: gym(), tasks_due: 4, tasks_done: 1, task_titles: ['Report', 'Email', 'Deck'] }),
    day(1),
    day(2, { gym: gym({ date: '2026-10-14', logged: true, lifts: ['Bench', 'Deadlift'] }) }),
    day(3),
    day(4),
    day(5),
    day(6),
  ],
  meet: { title: 'State meet', date: '2027-02-13', days_left: 124 },
  program: 'Meet prep, week 1 of 10',
  status: 'TIGHT',
  summary: 'Monday is heavy.',
  suggestions: [{ date: '2026-10-15', action: 'Move the report to Thursday' }],
  ...o,
})

const button = (w: ReturnType<typeof mount>, text: string) => w.findAll('button').find((b) => b.text() === text)!

beforeEach(() => vi.resetAllMocks())

describe('WeekBalance', () => {
  it('asks nothing until you press the button', () => {
    const w = mount(WeekBalance)
    expect(agentsApi.balanceWeek).not.toHaveBeenCalled()
    expect(w.text()).toContain('Checks this week')
  })

  it('shows the status, summary, suggestions and the real day numbers', async () => {
    vi.mocked(agentsApi.balanceWeek).mockResolvedValue(result() as never)
    const w = mount(WeekBalance)
    await button(w, 'Balance my week').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="status"]').text()).toBe('Tight')
    expect(w.text()).toContain('Monday is heavy.')
    expect(w.get('[aria-label="Suggestions"]').text()).toContain('Move the report to Thursday')
    expect(w.get('[data-testid="context"]').text()).toBe('Meet prep, week 1 of 10 · State meet in 124 days')
    const rows = w.findAll('[data-testid="day"]')
    expect(rows).toHaveLength(7)
    expect(rows[0]!.text()).toContain('1 of 4 done')
    expect(rows[0]!.text()).toContain('Squat (planned)')
    expect(rows[0]!.findAll('td')[1]!.attributes('title')).toBe('Report, Email, Deck')
    expect(rows[2]!.text()).toContain('Bench · Deadlift (logged)')
    expect(rows[1]!.text()).toContain('Rest')
  })

  it('explains when there is nothing to balance and shows no suggestions', async () => {
    vi.mocked(agentsApi.balanceWeek).mockResolvedValue(
      result({ status: null, summary: '', suggestions: [], days: [day(0), day(1), day(2), day(3), day(4), day(5), day(6)], meet: null, program: null }) as never,
    )
    const w = mount(WeekBalance)
    await button(w, 'Balance my week').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="no-gym"]').text()).toContain('nothing to balance')
    expect(w.find('[data-testid="status"]').exists()).toBe(false)
    expect(w.find('[aria-label="Suggestions"]').exists()).toBe(false)
    expect(w.find('[data-testid="context"]').exists()).toBe(false)
  })

  it('words a single day to the meet in the singular', async () => {
    vi.mocked(agentsApi.balanceWeek).mockResolvedValue(result({ program: null, meet: { title: 'Meet', date: '2026-10-13', days_left: 1 } }) as never)
    const w = mount(WeekBalance)
    await button(w, 'Balance my week').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="context"]').text()).toBe('Meet in 1 day')
  })

  it('disables the button while running, then shows the server error', async () => {
    let reject!: (e: Error) => void
    vi.mocked(agentsApi.balanceWeek).mockReturnValue(new Promise((_, r) => (reject = r)) as never)
    const w = mount(WeekBalance)
    await button(w, 'Balance my week').trigger('click')
    expect(button(w, 'Balancing…').attributes('disabled')).toBeDefined()
    reject(new ApiError(503, 'Agent unavailable: check that the MCP server and Ollama are running'))
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Agent unavailable')
    expect(button(w, 'Balance my week').attributes('disabled')).toBeUndefined()
    expect(w.find('[data-testid="status"]').exists()).toBe(false)
  })

  it('keeps the earlier result when a rerun fails, and dismiss clears it', async () => {
    vi.mocked(agentsApi.balanceWeek).mockResolvedValueOnce(result() as never).mockRejectedValueOnce(new ApiError(504, 'The agent timed out'))
    const w = mount(WeekBalance)
    await button(w, 'Balance my week').trigger('click')
    await flushPromises()
    await button(w, 'Balance my week').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toBe('The agent timed out')
    expect(w.get('[data-testid="status"]').exists()).toBe(true)
    await button(w, 'Dismiss').trigger('click')
    expect(w.find('[data-testid="status"]').exists()).toBe(false)
    expect(w.text()).toContain('Checks this week')
  })
})
