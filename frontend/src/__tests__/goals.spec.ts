import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GoalsPanel from '../components/GoalsPanel.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return { ...actual, goalsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() } }
})
import { ApiError, goalsApi } from '../api'

const goal = (o = {}) => ({ id: 'g1', title: 'Ship report', details: 'By Friday', target_date: null, date_created: '2026-10-10', ...o })
const btn = (w: ReturnType<typeof mount>, text: string) => w.findAll('button').find((b) => b.text() === text)!

async function mountPanel(goals: object[] = []) {
  vi.mocked(goalsApi.list).mockResolvedValue(goals as never)
  const w = mount(GoalsPanel, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return w
}

beforeEach(() => vi.resetAllMocks())

describe('GoalsPanel', () => {
  it('lists goals with details', async () => {
    const w = await mountPanel([goal()])
    expect(w.text()).toContain('Ship report')
    expect(w.text()).toContain('By Friday')
  })

  it('shows an empty state', async () => {
    const w = await mountPanel()
    expect(w.text()).toContain('No goals yet')
  })

  it('shows a load error with retry', async () => {
    vi.mocked(goalsApi.list).mockRejectedValueOnce(new ApiError(0, 'Cannot reach the server')).mockResolvedValueOnce([goal()] as never)
    const w = mount(GoalsPanel, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
    await btn(w, 'Retry').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Ship report')
  })

  it('creates a goal', async () => {
    vi.mocked(goalsApi.create).mockResolvedValue(goal({ title: 'Read more', details: '' }) as never)
    const w = await mountPanel()
    await btn(w, 'New goal').trigger('click')
    await w.get('input[aria-label="Goal title"]').setValue('  Read more ')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(goalsApi.create).toHaveBeenCalledWith({ title: 'Read more', details: '' })
    expect(w.text()).toContain('Read more')
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })

  it('does not create a goal with a blank title', async () => {
    const w = await mountPanel()
    await btn(w, 'New goal').trigger('click')
    await w.get('input[aria-label="Goal title"]').setValue('   ')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(goalsApi.create).not.toHaveBeenCalled()
  })

  it('shows the server error and keeps the form open when saving fails', async () => {
    vi.mocked(goalsApi.create).mockRejectedValue(new ApiError(422, 'title: too short'))
    const w = await mountPanel()
    await btn(w, 'New goal').trigger('click')
    await w.get('input[aria-label="Goal title"]').setValue('x')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.get('[role="dialog"] [role="alert"]').text()).toContain('too short')
  })

  it('edits a goal', async () => {
    vi.mocked(goalsApi.update).mockResolvedValue(goal({ title: 'Ship it' }) as never)
    const w = await mountPanel([goal()])
    await w.get('button[aria-label="Edit Ship report"]').trigger('click')
    await w.get('input[aria-label="Goal title"]').setValue('Ship it')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(goalsApi.update).toHaveBeenCalledWith('g1', { title: 'Ship it', details: 'By Friday', target_date: null })
    expect(w.text()).toContain('Ship it')
    expect(w.text()).not.toContain('Ship report')
  })

  it('deletes a goal', async () => {
    vi.mocked(goalsApi.remove).mockResolvedValue(undefined)
    const w = await mountPanel([goal()])
    await w.get('button[aria-label="Edit Ship report"]').trigger('click')
    await btn(w, 'Delete').trigger('click')
    await flushPromises()
    expect(goalsApi.remove).toHaveBeenCalledWith('g1')
    expect(w.text()).toContain('No goals yet')
  })

  it('keeps the goal when deleting fails', async () => {
    vi.mocked(goalsApi.remove).mockRejectedValue(new ApiError(404, 'Goal not found'))
    const w = await mountPanel([goal()])
    await w.get('button[aria-label="Edit Ship report"]').trigger('click')
    await btn(w, 'Delete').trigger('click')
    await flushPromises()
    expect(w.get('[role="dialog"] [role="alert"]').text()).toContain('Goal not found')
    expect(w.text()).toContain('Ship report')
  })

  it('creates a goal with a target date', async () => {
    vi.mocked(goalsApi.create).mockResolvedValue(goal({ title: 'Meet', target_date: '2027-02-13' }) as never)
    const w = await mountPanel()
    await btn(w, 'New goal').trigger('click')
    await w.get('input[aria-label="Goal title"]').setValue('Meet')
    await w.get('input[aria-label="Goal target date"]').setValue('2027-02-13')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(goalsApi.create).toHaveBeenCalledWith({ title: 'Meet', details: '', target_date: '2027-02-13' })
    expect(w.text()).toContain('By Saturday, February 13')
  })

  it('shows the date of a goal that has one and nothing for one that does not', async () => {
    const w = await mountPanel([goal({ target_date: '2027-02-13' }), goal({ id: 'g2', title: 'Read', details: '', target_date: null })])
    expect(w.findAll('.goal')[0]!.text()).toContain('By Saturday, February 13')
    expect(w.findAll('.goal')[1]!.text()).not.toContain('By ')
  })

  it('clears a target date by sending null', async () => {
    vi.mocked(goalsApi.update).mockResolvedValue(goal() as never)
    const w = await mountPanel([goal({ target_date: '2027-02-13' })])
    await w.get('button[aria-label="Edit Ship report"]').trigger('click')
    expect((w.get('input[aria-label="Goal target date"]').element as HTMLInputElement).value).toBe('2027-02-13')
    await w.get('input[aria-label="Goal target date"]').setValue('')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(goalsApi.update).toHaveBeenCalledWith('g1', { title: 'Ship report', details: 'By Friday', target_date: null })
  })
})
