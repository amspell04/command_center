import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProgressTicker from '../components/ProgressTicker.vue'
import { useTasks } from '../composables/useTasks'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn(), remove: vi.fn() },
    goalsApi: { list: vi.fn() },
    weakPointsApi: { list: vi.fn() },
  }
})
import { goalsApi, tasksApi, weakPointsApi } from '../api'

const task = (id: string, completed: boolean) => ({
  id,
  title: id,
  type: 'WORK',
  requirement: '',
  due_date: '2026-10-11',
  completed,
  date_created: '2026-10-01',
})
const goal = (title: string) => ({ id: title, title, details: '', date_created: '2026-10-01' })
const wp = (id: string, resolved: boolean) => ({ id, note_id: 'n', topic: id, resolved, date_created: '2026-10-01' })

async function mountTicker() {
  const w = mount(ProgressTicker)
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.resetAllMocks()
  useTasks().tasks.value = []
})

describe('ProgressTicker', () => {
  it('shows completed tasks, goals and weak points', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task('a', true), task('b', true), task('c', false)] as never)
    vi.mocked(goalsApi.list).mockResolvedValue([goal('Learn Rust'), goal('Run 5k')] as never)
    vi.mocked(weakPointsApi.list).mockResolvedValue([wp('x', true), wp('y', false), wp('z', false)] as never)
    const text = (await mountTicker()).text()
    expect(text).toContain('Tasks completed: 2 of 3')
    expect(text).toContain('Learn Rust · Run 5k')
    expect(text).toContain('Weak points: 3 identified, 1 covered')
  })

  it('handles an empty account', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([])
    vi.mocked(goalsApi.list).mockResolvedValue([])
    vi.mocked(weakPointsApi.list).mockResolvedValue([])
    const w = await mountTicker()
    expect(w.text()).toContain('Tasks completed: 0 of 0')
    expect(w.text()).toContain('No goals set')
    expect(w.text()).toContain('Weak points: 0 identified, 0 covered')
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })

  it('loops by repeating the items, hiding the copy from assistive tech', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([])
    vi.mocked(goalsApi.list).mockResolvedValue([])
    vi.mocked(weakPointsApi.list).mockResolvedValue([])
    const lists = (await mountTicker()).findAll('ul')
    expect(lists.length).toBeGreaterThanOrEqual(4)
    expect(lists[0]!.attributes('aria-hidden')).toBeUndefined()
    expect(lists.slice(1).every((l) => l.attributes('aria-hidden') === 'true')).toBe(true)
  })

  it('still shows what loaded and warns when a source fails', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task('a', true)] as never)
    vi.mocked(goalsApi.list).mockResolvedValue([goal('Run 5k')] as never)
    vi.mocked(weakPointsApi.list).mockRejectedValue(new Error('down'))
    const w = await mountTicker()
    expect(w.text()).toContain('Tasks completed: 1 of 1')
    expect(w.get('[role="alert"]').text()).toContain('could not load')
  })
})
