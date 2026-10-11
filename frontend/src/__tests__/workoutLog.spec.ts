import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkoutLog from '../components/WorkoutLog.vue'
import { localToday } from '../utils/dates'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    trainingApi: { planned: vi.fn(), sessionsBetween: vi.fn(), saveSession: vi.fn(), removeSession: vi.fn() },
  }
})
import { ApiError, trainingApi } from '../api'

const api = vi.mocked(trainingApi)
const today = localToday()

const plan = (o = {}) => ({
  id: 'e1',
  program_id: 'p1',
  week: 2,
  day: 3,
  lift: 'SQUAT',
  sets: 3,
  reps: 5,
  percent: 80,
  weight_lb: 320,
  weight_kg: 145.1,
  date: today,
  ...o,
})
const logged = (o = {}) => ({
  id: 's1',
  date: today,
  notes: 'felt heavy',
  bodyweight_lb: 200,
  bodyweight_kg: 90.7,
  sets: [
    { id: 'x1', lift: 'BENCH', weight_lb: 225, weight_kg: 102.1, reps: 5, set_order: 1, estimated_1rm_lb: 262.5, estimated_1rm_kg: 119.1, program_set_id: null },
  ],
  ...o,
})

async function mountLog(planned: object[] = [], sessions: object[] = []) {
  api.planned.mockResolvedValue(planned as never)
  api.sessionsBetween.mockResolvedValue(sessions as never)
  const w = mount(WorkoutLog, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return w
}
type W = Awaited<ReturnType<typeof mountLog>>
const sets = (w: W) => w.findAll('[data-testid="set"]')
const value = (w: W, label: string, i = 0) => (sets(w)[i]!.get(`[aria-label="${label}"]`).element as HTMLInputElement).value
const submit = async (w: W) => {
  await w.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => vi.resetAllMocks())

describe('WorkoutLog', () => {
  it('loads today by default and asks for that day only', async () => {
    await mountLog()
    expect(api.planned).toHaveBeenCalledWith(today)
    expect(api.sessionsBetween).toHaveBeenCalledWith(today, today)
  })

  it('fills in a planned day: one row per set with the computed weight', async () => {
    const w = await mountLog([plan(), plan({ id: 'e2', lift: 'BENCH', sets: 2, reps: 8, weight_lb: 200 })])
    expect(sets(w)).toHaveLength(5)
    expect(value(w, 'Weight in lb')).toBe('320')
    expect(value(w, 'Reps')).toBe('5')
    expect(value(w, 'Lift', 3)).toBe('BENCH')
    expect(sets(w)[0]!.get('[data-testid="kg"]').text()).toBe('145.1')
    expect(w.text()).toContain('Planned: Week 2 · Day 3')
  })

  it('leaves the weight blank when the lift has no max, and says why', async () => {
    const w = await mountLog([plan({ weight_lb: null, weight_kg: null })])
    expect(value(w, 'Weight in lb')).toBe('')
    expect(w.text()).toContain('no training max yet')
    expect(w.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('starts empty on a day with no program', async () => {
    const w = await mountLog()
    expect(sets(w)).toHaveLength(0)
    expect(w.text()).toContain('No program day for this date')
    expect(w.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('opens an already logged day for editing instead of the plan', async () => {
    const w = await mountLog([plan()], [logged()])
    expect(sets(w)).toHaveLength(1)
    expect(value(w, 'Weight in lb')).toBe('225')
    expect((w.get('[aria-label="Bodyweight in lb"]').element as HTMLInputElement).value).toBe('200')
    expect((w.get('[aria-label="Workout notes"]').element as HTMLTextAreaElement).value).toBe('felt heavy')
    expect(w.text()).toContain('Saving replaces')
    expect(w.get('button[type="submit"]').text()).toBe('Update workout')
  })

  it('saves the sets as typed, linked to the plan, in lb', async () => {
    const w = await mountLog([plan({ sets: 2 })])
    api.saveSession.mockResolvedValue(logged() as never)
    await sets(w)[1]!.get('[aria-label="Weight in lb"]').setValue('325')
    await sets(w)[1]!.get('[aria-label="Reps"]').setValue('4')
    await w.get('[aria-label="Workout notes"]').setValue('grindy')
    await submit(w)
    expect(api.saveSession).toHaveBeenCalledWith({
      date: today,
      notes: 'grindy',
      bodyweight: null,
      sets: [
        { lift: 'SQUAT', weight: 320, reps: 5, program_set_id: 'e1' },
        { lift: 'SQUAT', weight: 325, reps: 4, program_set_id: 'e1' },
      ],
    })
    expect(w.get('[role="status"]').text()).toBe('Saved.')
    expect(w.emitted('saved')).toHaveLength(1)
  })

  it('adds and removes sets; an added set copies the previous one and has no plan link', async () => {
    const w = await mountLog([plan({ sets: 1 })])
    await w.get('.log__add').trigger('click')
    expect(sets(w)).toHaveLength(2)
    expect(value(w, 'Weight in lb', 1)).toBe('320')
    api.saveSession.mockResolvedValue(logged() as never)
    await submit(w)
    expect(api.saveSession.mock.calls[0]![0].sets.map((s) => s.program_set_id)).toEqual(['e1', null])
    await sets(w)[0]!.get('[aria-label="Remove set"]').trigger('click')
    expect(sets(w)).toHaveLength(1)
  })

  it('can log a day from scratch, with bodyweight', async () => {
    const w = await mountLog()
    await w.get('.log__add').trigger('click')
    await sets(w)[0]!.get('[aria-label="Weight in lb"]').setValue('135')
    await w.get('[aria-label="Bodyweight in lb"]').setValue('199.5')
    api.saveSession.mockResolvedValue(logged() as never)
    await submit(w)
    expect(api.saveSession).toHaveBeenCalledWith({
      date: today,
      notes: '',
      bodyweight: 199.5,
      sets: [{ lift: 'SQUAT', weight: 135, reps: 5, program_set_id: null }],
    })
  })

  it('does not save invalid sets and says what is wrong', async () => {
    const w = await mountLog([plan({ sets: 1 })])
    for (const [label, bad, message] of [
      ['Weight in lb', '0', 'weight above 0'],
      ['Weight in lb', '-5', 'weight above 0'],
      ['Weight in lb', 'heavy', 'weight above 0'],
      ['Weight in lb', '2001', 'weight above 0'],
      ['Reps', '0', 'reps from 1 to 30'],
      ['Reps', '2.5', 'reps from 1 to 30'],
      ['Reps', '31', 'reps from 1 to 30'],
    ] as const) {
      await sets(w)[0]!.get(`[aria-label="${label}"]`).setValue(bad)
      expect(w.get('[role="alert"]').text()).toContain(message)
      expect(w.get('button[type="submit"]').attributes('disabled')).toBeDefined()
      await submit(w)
      await sets(w)[0]!.get(`[aria-label="${label}"]`).setValue(label === 'Reps' ? '5' : '320')
    }
    await w.get('[aria-label="Bodyweight in lb"]').setValue('0')
    expect(w.get('[role="alert"]').text()).toContain('Bodyweight')
    await submit(w)
    expect(api.saveSession).not.toHaveBeenCalled()
  })

  it('keeps what was typed and shows the server error when saving fails', async () => {
    const w = await mountLog([plan({ sets: 1 })])
    api.saveSession.mockRejectedValue(new ApiError(422, 'Unknown program set'))
    await sets(w)[0]!.get('[aria-label="Weight in lb"]').setValue('330')
    await submit(w)
    expect(w.get('[role="alert"]').text()).toBe('Unknown program set')
    expect(value(w, 'Weight in lb')).toBe('330')
    expect(w.emitted('saved')).toBeUndefined()
    expect(w.find('[role="status"]').exists()).toBe(false)
  })

  it('reloads the plan when the date changes', async () => {
    const w = await mountLog()
    api.planned.mockResolvedValue([plan({ sets: 2, date: '2026-01-05' })] as never)
    api.sessionsBetween.mockResolvedValue([] as never)
    await w.get('[aria-label="Workout date"]').setValue('2026-01-05')
    await flushPromises()
    expect(api.planned).toHaveBeenLastCalledWith('2026-01-05')
    expect(sets(w)).toHaveLength(2)
  })

  it('does not load when the date is cleared', async () => {
    const w = await mountLog()
    api.planned.mockClear()
    await w.get('[aria-label="Workout date"]').setValue('')
    await flushPromises()
    expect(api.planned).not.toHaveBeenCalled()
  })

  it('shows a load error and no form', async () => {
    api.planned.mockRejectedValue(new ApiError(0, 'Cannot reach the server'))
    api.sessionsBetween.mockResolvedValue([] as never)
    const w = mount(WorkoutLog, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
    expect(w.find('form').exists()).toBe(false)
  })

  it('confirms before deleting a logged day, then shows the plan again', async () => {
    const w = await mountLog([plan({ sets: 2 })], [logged()])
    await w.findAll('button').find((b) => b.text() === 'Delete workout')!.trigger('click')
    expect(api.removeSession).not.toHaveBeenCalled()
    api.removeSession.mockResolvedValue(undefined as never)
    api.sessionsBetween.mockResolvedValue([] as never)
    await w.get('.btn--danger-solid').trigger('click')
    await flushPromises()
    expect(api.removeSession).toHaveBeenCalledWith('s1')
    expect(w.emitted('deleted')).toHaveLength(1)
    expect(sets(w)).toHaveLength(2)
  })

  it('shows the error and keeps the dialog when deleting fails', async () => {
    const w = await mountLog([], [logged()])
    await w.findAll('button').find((b) => b.text() === 'Delete workout')!.trigger('click')
    api.removeSession.mockRejectedValue(new ApiError(404, 'Session not found'))
    await w.get('.btn--danger-solid').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Session not found')
    expect(w.emitted('deleted')).toBeUndefined()
  })

  it('is a modal that asks to close from the close button', async () => {
    const w = await mountLog()
    expect(w.get('[role="dialog"]').attributes('aria-label')).toBe('Log a workout')
    await w.get('[aria-label="Close"]').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })
})
