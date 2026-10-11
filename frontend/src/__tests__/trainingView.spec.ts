import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TrainingView from '../pages/TrainingView.vue'

const stub = (name: string) => ({ name, template: `<div data-testid="${name}" />` })
const WorkoutLogStub = { name: 'WorkoutLog', emits: ['close', 'saved', 'deleted'], template: '<div data-testid="log"><button class="close" @click="$emit(\'close\')" /></div>' }

function mountPage() {
  return mount(TrainingView, {
    global: {
      stubs: {
        RouterLink: true,
        ProgramEditor: stub('program'),
        TrainingMaxes: stub('maxes'),
        TrainingProgress: stub('progress'),
        WeekBalance: stub('balance'),
        WorkoutLog: WorkoutLogStub,
      },
    },
  })
}

beforeEach(() => vi.resetAllMocks())

describe('TrainingView', () => {
  it('keeps the workout form hidden until Log a workout is pressed, and closes it again', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.find('[data-testid="log"]').exists()).toBe(false)
    expect(w.find('[data-testid="maxes"]').exists()).toBe(true)
    await w.findAll('button').find((b) => b.text() === 'Log a workout')!.trigger('click')
    expect(w.find('[data-testid="log"]').exists()).toBe(true)
    await w.get('.close').trigger('click')
    expect(w.find('[data-testid="log"]').exists()).toBe(false)
  })
})
