import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProgramEditor from '../components/ProgramEditor.vue'
import TrainingMaxes from '../components/TrainingMaxes.vue'
import { localToday } from '../utils/dates'
import { lbToKg, sortExercises, weightLabel } from '../utils/training'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    trainingApi: {
      maxes: vi.fn(),
      setMax: vi.fn(),
      programs: vi.fn(),
      createProgram: vi.fn(),
      updateProgram: vi.fn(),
      removeProgram: vi.fn(),
      exercises: vi.fn(),
      addExercise: vi.fn(),
      updateExercise: vi.fn(),
      removeExercise: vi.fn(),
      copyWeek: vi.fn(),
    },
  }
})
import { ApiError, trainingApi } from '../api'

const api = vi.mocked(trainingApi)

const program = (o = {}) => ({ id: 'p1', name: 'Meet prep', start_date: '2026-10-12', weeks: 4, active: true, ...o })
const exercise = (o = {}) => ({
  id: 'e1',
  program_id: 'p1',
  week: 1,
  day: 1,
  lift: 'SQUAT',
  sets: 3,
  reps: 5,
  percent: 80,
  weight_lb: 320,
  weight_kg: 145.1,
  date: '2026-10-12',
  ...o,
})
const max = (o = {}) => ({ id: 'm1', lift: 'SQUAT', weight_lb: 400, weight_kg: 181.4, effective_date: '2020-01-01', ...o })

beforeEach(() => vi.resetAllMocks())

describe('training utils', () => {
  it('converts lb to kg to one decimal', () => {
    expect(lbToKg(225)).toBe(102.1)
    expect(lbToKg(0)).toBe(0)
  })

  it('labels a weight in both units, or a dash when unknown', () => {
    expect(weightLabel(315, 142.9)).toBe('315 lb / 142.9 kg')
    expect(weightLabel(null, null)).toBe('–')
  })

  it('sorts by day, then lift, then heaviest first', () => {
    const rows = [
      exercise({ id: 'a', day: 3, lift: 'SQUAT' }),
      exercise({ id: 'b', day: 1, lift: 'DEADLIFT' }),
      exercise({ id: 'c', day: 1, lift: 'BENCH', percent: 70 }),
      exercise({ id: 'd', day: 1, lift: 'BENCH', percent: 80 }),
    ] as never[]
    expect(sortExercises(rows).map((r: { id: string }) => r.id)).toEqual(['d', 'c', 'b', 'a'])
  })
})

describe('TrainingMaxes', () => {
  async function mountMaxes(maxes: object[] = [max()]) {
    api.maxes.mockResolvedValue(maxes as never)
    const w = mount(TrainingMaxes)
    await flushPromises()
    return w
  }

  it('prefills the current max and shows kg as you type', async () => {
    const w = await mountMaxes()
    const squat = w.get('[aria-label="Squat max in lb"]')
    expect((squat.element as HTMLInputElement).value).toBe('400')
    await squat.setValue('405')
    expect(w.get('[data-testid="kg-SQUAT"]').text()).toBe('183.7 kg')
  })

  it('uses the newest max already in force, not a future one', async () => {
    const w = await mountMaxes([max({ weight_lb: 400 }), max({ id: 'm2', weight_lb: 420, effective_date: '2021-01-01' }), max({ id: 'm3', weight_lb: 999, effective_date: '2999-01-01' })])
    expect((w.get('[aria-label="Squat max in lb"]').element as HTMLInputElement).value).toBe('420')
  })

  it('saves only the lifts that changed, dated today, and tells the page', async () => {
    const w = await mountMaxes()
    api.setMax.mockResolvedValue(max({ weight_lb: 405 }) as never)
    await w.get('[aria-label="Squat max in lb"]').setValue('405')
    await w.get('[aria-label="Bench max in lb"]').setValue('275')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(api.setMax.mock.calls).toEqual([
      [{ lift: 'SQUAT', weight: 405, effective_date: localToday() }],
      [{ lift: 'BENCH', weight: 275, effective_date: localToday() }],
    ])
    expect(w.emitted('saved')).toHaveLength(1)
  })

  it('blocks saving when nothing changed or a value is not a valid weight', async () => {
    const w = await mountMaxes()
    const button = w.get('button[type="submit"]')
    expect(button.attributes('disabled')).toBeDefined()
    for (const bad of ['abc', '0', '-5', '2500']) {
      await w.get('[aria-label="Squat max in lb"]').setValue(bad)
      expect(button.attributes('disabled')).toBeDefined()
      expect(w.text()).toContain('Enter a weight')
    }
    expect(api.setMax).not.toHaveBeenCalled()
  })

  it('shows the server error and does not announce a save when saving fails', async () => {
    const w = await mountMaxes()
    api.setMax.mockRejectedValue(new ApiError(422, 'Nope'))
    await w.get('[aria-label="Squat max in lb"]').setValue('405')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toBe('Nope')
    expect(w.emitted('saved')).toBeUndefined()
  })

  it('shows a load error', async () => {
    api.maxes.mockRejectedValue(new ApiError(0, 'down'))
    const w = mount(TrainingMaxes)
    await flushPromises()
    expect(w.text()).toContain('Could not load training maxes')
  })
})

describe('ProgramEditor', () => {
  async function mountEditor(programs: object[] = [program()], rows: object[] = [exercise()]) {
    api.programs.mockResolvedValue(programs as never)
    api.exercises.mockResolvedValue(rows as never)
    const w = mount(ProgramEditor, { global: { stubs: { teleport: true } } })
    await flushPromises()
    return w
  }
  const row = (w: Awaited<ReturnType<typeof mountEditor>>, i = 0) => w.findAll('[data-testid="row"]')[i]!

  it('shows the active program, its first week and computed weights in both units', async () => {
    const w = await mountEditor([program({ id: 'p0', name: 'Old', active: false }), program()])
    expect(api.exercises).toHaveBeenCalledWith('p1')
    expect(w.findAll('[data-testid="row"]')).toHaveLength(1)
    expect(row(w).get('[data-testid="weight"]').text()).toBe('320 lb / 145.1 kg')
    expect((row(w).get('[aria-label="Percent"]').element as HTMLInputElement).value).toBe('80')
  })

  it('shows a dash for the weight until the lift has a max', async () => {
    const w = await mountEditor([program()], [exercise({ weight_lb: null, weight_kg: null })])
    expect(row(w).get('[data-testid="weight"]').text()).toBe('–')
  })

  it('labels days with the weekday they fall on', async () => {
    const w = await mountEditor()
    const days = row(w).findAll('[aria-label="Day"] option').map((o) => o.text())
    expect(days[0]).toMatch(/^Day 1 · /)
    expect(days).toHaveLength(7)
  })

  it('shows only the selected week and empty weeks say so', async () => {
    const w = await mountEditor([program()], [exercise(), exercise({ id: 'e2', week: 2 })])
    expect(w.findAll('[data-testid="row"]')).toHaveLength(1)
    await w.get('[aria-label="Week 3"]').trigger('click')
    expect(w.findAll('[data-testid="row"]')).toHaveLength(0)
    expect(w.text()).toContain('Week 3 is empty')
  })

  it('saves a cell on change and shows the recomputed weight', async () => {
    const w = await mountEditor()
    api.updateExercise.mockResolvedValue(exercise({ percent: 85, weight_lb: 340, weight_kg: 154.2 }) as never)
    await row(w).get('[aria-label="Percent"]').setValue('85')
    await flushPromises()
    expect(api.updateExercise).toHaveBeenCalledWith('e1', { percent: 85 })
    expect(row(w).get('[data-testid="weight"]').text()).toBe('340 lb / 154.2 kg')
  })

  it('changes lift through the lift select', async () => {
    const w = await mountEditor()
    api.updateExercise.mockResolvedValue(exercise({ lift: 'BENCH' }) as never)
    await row(w).get('[aria-label="Lift"]').setValue('BENCH')
    await flushPromises()
    expect(api.updateExercise).toHaveBeenCalledWith('e1', { lift: 'BENCH' })
  })

  it('refuses invalid cell values without calling the server', async () => {
    const w = await mountEditor()
    const bad: [string, string][] = [['Percent', '0'], ['Percent', '151'], ['Percent', ''], ['Sets', '0'], ['Sets', '2.5'], ['Reps', '31'], ['Reps', 'abc']]
    for (const [label, value] of bad) {
      await row(w).get(`[aria-label="${label}"]`).setValue(value)
      expect(w.get('[role="alert"]').exists()).toBe(true)
    }
    expect(api.updateExercise).not.toHaveBeenCalled()
  })

  it('does not call the server when a cell is left unchanged', async () => {
    const w = await mountEditor()
    await row(w).get('[aria-label="Sets"]').setValue('3')
    expect(api.updateExercise).not.toHaveBeenCalled()
  })

  it('shows the server error on the row and restores the saved value', async () => {
    const w = await mountEditor()
    api.updateExercise.mockRejectedValue(new ApiError(422, 'Week 9 is past the end'))
    await row(w).get('[aria-label="Reps"]').setValue('8')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toBe('Week 9 is past the end')
    expect((row(w).get('[aria-label="Reps"]').element as HTMLInputElement).value).toBe('5')
  })

  it('adds an exercise to the current week', async () => {
    const w = await mountEditor()
    await w.get('[aria-label="Week 2"]').trigger('click')
    api.addExercise.mockResolvedValue(exercise({ id: 'e9', week: 2, lift: 'BENCH', percent: 75 }) as never)
    await w.get('[aria-label="New exercise lift"]').setValue('BENCH')
    await w.get('[aria-label="New exercise percent"]').setValue('75')
    await w.get('.grid__add .btn--primary').trigger('click')
    await flushPromises()
    expect(api.addExercise).toHaveBeenCalledWith('p1', { week: 2, day: 1, lift: 'BENCH', sets: 3, reps: 5, percent: 75 })
    expect(w.findAll('[data-testid="row"]')).toHaveLength(1)
  })

  it('refuses to add an invalid exercise and shows add errors from the server', async () => {
    const w = await mountEditor()
    await w.get('[aria-label="New exercise percent"]').setValue('0')
    await w.get('.grid__add .btn--primary').trigger('click')
    expect(api.addExercise).not.toHaveBeenCalled()
    expect(w.text()).toContain('Percent must be above 0')

    await w.get('[aria-label="New exercise percent"]').setValue('70')
    api.addExercise.mockRejectedValue(new ApiError(422, 'Week 5 is past the end of a 4 week program'))
    await w.get('.grid__add .btn--primary').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('past the end')
    expect(w.findAll('[data-testid="row"]')).toHaveLength(1)
  })

  it('removes an exercise', async () => {
    const w = await mountEditor()
    api.removeExercise.mockResolvedValue(undefined as never)
    await row(w).get('.btn--danger').trigger('click')
    await flushPromises()
    expect(api.removeExercise).toHaveBeenCalledWith('e1')
    expect(w.findAll('[data-testid="row"]')).toHaveLength(0)
  })

  it('copies a week into an empty one and jumps to it', async () => {
    const w = await mountEditor()
    api.copyWeek.mockResolvedValue([exercise({ id: 'e5', week: 2 })] as never)
    expect(w.get('[aria-label="Copy to week"]').findAll('option').map((o) => o.text())).not.toContain('Week 1')
    expect(w.get('.editor__copy button').attributes('disabled')).toBeDefined()
    await w.get('[aria-label="Copy to week"]').setValue(2)
    await w.get('.editor__copy button').trigger('click')
    await flushPromises()
    expect(api.copyWeek).toHaveBeenCalledWith('p1', 1, 2)
    expect(w.get('[aria-label="Week 2"]').attributes('aria-pressed')).toBe('true')
    expect(w.findAll('[data-testid="row"]')).toHaveLength(1)
  })

  it('only offers empty weeks as copy targets', async () => {
    const w = await mountEditor([program()], [exercise(), exercise({ id: 'e2', week: 2 })])
    expect(w.get('[aria-label="Copy to week"]').findAll('option').map((o) => o.text())).toEqual(['Choose an empty week', 'Week 3', 'Week 4'])
  })

  it('shows copy errors from the server', async () => {
    const w = await mountEditor()
    api.copyWeek.mockRejectedValue(new ApiError(422, 'Week 2 already has exercises'))
    await w.get('[aria-label="Copy to week"]').setValue(2)
    await w.get('.editor__copy button').trigger('click')
    await flushPromises()
    expect(w.get('.editor__copy .error').text()).toBe('Week 2 already has exercises')
  })

  it('creates a program and switches to it', async () => {
    const w = await mountEditor([])
    expect(w.text()).toContain('No program yet')
    await w.findAll('button').find((b) => b.text() === 'New program')!.trigger('click')
    api.createProgram.mockResolvedValue(program({ id: 'p2', name: 'Peak' }) as never)
    api.programs.mockResolvedValue([program({ id: 'p2', name: 'Peak' })] as never)
    api.exercises.mockResolvedValue([] as never)
    await w.get('[aria-label="New program name"]').setValue('  Peak ')
    await w.get('.editor__new').trigger('submit')
    await flushPromises()
    expect(api.createProgram).toHaveBeenCalledWith({ name: 'Peak', start_date: localToday(), weeks: 10, active: true })
    expect(api.exercises).toHaveBeenLastCalledWith('p2')
  })

  it('does not create a program with a blank name', async () => {
    const w = await mountEditor([])
    await w.findAll('button').find((b) => b.text() === 'New program')!.trigger('click')
    await w.get('[aria-label="New program name"]').setValue('   ')
    await w.get('.editor__new').trigger('submit')
    expect(api.createProgram).not.toHaveBeenCalled()
  })

  it('makes an inactive program active and refreshes the list', async () => {
    const w = await mountEditor([program({ active: false })])
    api.updateProgram.mockResolvedValue(program({ active: true }) as never)
    api.programs.mockResolvedValue([program({ active: true })] as never)
    await w.findAll('button').find((b) => b.text() === 'Make active')!.trigger('click')
    await flushPromises()
    expect(api.updateProgram).toHaveBeenCalledWith('p1', { active: true })
    expect(w.text()).toContain('Active program')
  })

  it('rejects bad program settings without calling the server', async () => {
    const w = await mountEditor()
    for (const bad of ['0', '53', '2.5', '']) await w.get('[aria-label="Weeks"]').setValue(bad)
    await w.get('[aria-label="Program name"]').setValue('  ')
    expect(api.updateProgram).not.toHaveBeenCalled()
  })

  it('shows the server error when shortening a program is refused', async () => {
    const w = await mountEditor()
    api.updateProgram.mockRejectedValue(new ApiError(422, 'Week 4 already has exercises, remove them before shortening the program'))
    await w.get('[aria-label="Weeks"]').setValue('2')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Week 4 already has exercises')
    expect((w.get('[aria-label="Weeks"]').element as HTMLInputElement).value).toBe('4')
  })

  it('refetches exercises when the training maxes change', async () => {
    const w = await mountEditor()
    api.exercises.mockResolvedValue([exercise({ weight_lb: 340, weight_kg: 154.2 })] as never)
    await w.setProps({ refreshKey: 1 })
    await flushPromises()
    expect(row(w).get('[data-testid="weight"]').text()).toBe('340 lb / 154.2 kg')
  })

  it('confirms before deleting a program, then falls back to another', async () => {
    const w = await mountEditor([program(), program({ id: 'p2', name: 'Other', active: false })])
    await w.findAll('button').find((b) => b.text() === 'Delete program')!.trigger('click')
    expect(api.removeProgram).not.toHaveBeenCalled()
    api.removeProgram.mockResolvedValue(undefined as never)
    api.exercises.mockResolvedValue([] as never)
    await w.get('.btn--danger-solid').trigger('click')
    await flushPromises()
    expect(api.removeProgram).toHaveBeenCalledWith('p1')
    expect(api.exercises).toHaveBeenLastCalledWith('p2')
  })

  it('keeps the delete dialog open and shows the error when deleting fails', async () => {
    const w = await mountEditor()
    await w.findAll('button').find((b) => b.text() === 'Delete program')!.trigger('click')
    api.removeProgram.mockRejectedValue(new ApiError(500, 'Boom'))
    await w.get('.btn--danger-solid').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Boom')
    expect(w.text()).toContain('Delete “Meet prep”')
  })

  it('shows a load error', async () => {
    api.programs.mockRejectedValue(new ApiError(0, 'down'))
    const w = mount(ProgramEditor)
    await flushPromises()
    expect(w.text()).toContain('Could not load programs')
  })
})

afterEach(() => vi.unstubAllGlobals())
