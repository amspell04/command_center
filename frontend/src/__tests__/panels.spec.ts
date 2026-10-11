import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotesPanel from '../components/NotesPanel.vue'
import TasksPanel from '../components/TasksPanel.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    tasksApi: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      complete: vi.fn(),
      remove: vi.fn(),
    },
    notesApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  }
})
import { ApiError, notesApi, tasksApi } from '../api'

const today = (() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})()
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
const note = (o = {}) => ({ id: 'n1', title: 'Idea', content: 'body', date_created: today, ...o })

const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find((b) => b.text() === text)!

async function mountWith(component: object) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/notes/:id', component: { template: '<div />' } },
    ],
  })
  router.push('/')
  await router.isReady()
  const w = mount(component, { global: { plugins: [router], stubs: { teleport: true } } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => vi.resetAllMocks())

describe('TasksPanel', () => {
  const done = (n: number) =>
    Array.from({ length: n }, (_, i) =>
      task({ id: `d${i}`, title: `Done ${i}`, completed: true, due_date: `2025-01-0${i + 1}` }),
    )

  it('shows only the 3 latest completed tasks behind a See more toggle', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue(done(5) as never)
    const { w } = await mountWith(TasksPanel)
    expect(w.text()).toContain('Done 4')
    expect(w.text()).toContain('Done 2')
    expect(w.text()).not.toContain('Done 1')
    await btn(w, 'See more (2)').trigger('click')
    expect(w.text()).toContain('Done 0')
    await btn(w, 'See less').trigger('click')
    expect(w.text()).not.toContain('Done 0')
  })

  it('hides See more when 3 or fewer tasks are completed', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue(done(3) as never)
    const { w } = await mountWith(TasksPanel)
    expect(w.findAll('button').some((b) => b.text().startsWith('See'))).toBe(false)
  })

  it('shows completed vs not completed counts', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([
      ...done(2),
      task({ id: 'a' }),
      task({ id: 'b' }),
      task({ id: 'c' }),
    ] as never)
    const { w } = await mountWith(TasksPanel)
    expect(w.get('[data-testid="score-done"]').text()).toBe('2')
    expect(w.get('[data-testid="score-open"]').text()).toBe('3')
  })

  it('shows zeros with no tasks', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([])
    const { w } = await mountWith(TasksPanel)
    expect(w.get('[data-testid="score-done"]').text()).toBe('0')
    expect(w.get('[data-testid="score-open"]').text()).toBe('0')
  })

  it('loads and shows tasks', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task()])
    const { w } = await mountWith(TasksPanel)
    expect(w.text()).toContain('Call dentist')
  })

  it('opens a create modal and creates a task', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([])
    vi.mocked(tasksApi.create).mockResolvedValue(task({ title: 'New' }) as never)
    const { w } = await mountWith(TasksPanel)
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    await btn(w, 'New task').trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(true)
    await w.get('[aria-label="Task title"]').setValue('New')
    await w.get('[role="dialog"] form').trigger('submit')
    await flushPromises()
    expect(tasksApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'New', type: 'PERSONAL' }),
    )
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(w.text()).toContain('New')
  })

  it('does not create with a blank title', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([])
    const { w } = await mountWith(TasksPanel)
    await btn(w, 'New task').trigger('click')
    await w.get('[aria-label="Task title"]').setValue('   ')
    await w.get('[role="dialog"] form').trigger('submit')
    expect(tasksApi.create).not.toHaveBeenCalled()
  })

  it('keeps the modal open and shows an error when create fails', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([])
    vi.mocked(tasksApi.create).mockRejectedValue(new Error('bad date'))
    const { w } = await mountWith(TasksPanel)
    await btn(w, 'New task').trigger('click')
    await w.get('[aria-label="Task title"]').setValue('x')
    await w.get('[role="dialog"] form').trigger('submit')
    await flushPromises()
    expect(w.get('[role="dialog"] [role="alert"]').text()).toContain('bad date')
  })

  it('opens the edit modal on click and saves changes', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task()])
    vi.mocked(tasksApi.update).mockResolvedValue(task({ title: 'Renamed' }) as never)
    const { w } = await mountWith(TasksPanel)
    await btn(w, 'Call dentist').trigger('click')
    expect((w.get('[aria-label="Task title"]').element as HTMLInputElement).value).toBe(
      'Call dentist',
    )
    await w.get('[aria-label="Task title"]').setValue('Renamed')
    await w.get('[role="dialog"] form').trigger('submit')
    await flushPromises()
    expect(tasksApi.update).toHaveBeenCalledWith(
      't1',
      expect.objectContaining({ title: 'Renamed' }),
    )
    expect(w.text()).toContain('Renamed')
  })

  it('completes and deletes from the edit modal', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task()])
    vi.mocked(tasksApi.complete).mockResolvedValue(task({ completed: true }) as never)
    vi.mocked(tasksApi.remove).mockResolvedValue()
    const { w } = await mountWith(TasksPanel)
    await btn(w, 'Call dentist').trigger('click')
    await btn(w, 'Mark complete').trigger('click')
    await flushPromises()
    expect(tasksApi.complete).toHaveBeenCalledWith('t1')
    expect(w.text()).toContain('Completed')
    await btn(w, 'Call dentist').trigger('click')
    await w
      .get('[role="dialog"]')
      .findAll('button')
      .find((b) => b.text() === 'Delete')!
      .trigger('click')
    await flushPromises()
    expect(tasksApi.remove).toHaveBeenCalledWith('t1')
    expect(w.text()).not.toContain('Call dentist')
  })

  it('completes via checkbox and deletes immediately without a modal', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task()])
    vi.mocked(tasksApi.complete).mockResolvedValue(task({ completed: true }) as never)
    vi.mocked(tasksApi.remove).mockResolvedValue()
    const { w } = await mountWith(TasksPanel)
    await w.get('input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(tasksApi.complete).toHaveBeenCalledWith('t1')
    await w.get('[aria-label="Delete Call dentist"]').trigger('click')
    await flushPromises()
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(tasksApi.remove).toHaveBeenCalledWith('t1')
    expect(w.text()).not.toContain('Call dentist')
  })

  it('shows an error when load fails', async () => {
    vi.mocked(tasksApi.list).mockRejectedValue(new Error('Cannot reach the server'))
    const { w } = await mountWith(TasksPanel)
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
  })

  it('keeps the task and shows an error when delete fails', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue([task()])
    vi.mocked(tasksApi.remove).mockRejectedValue(new Error('Task not found'))
    const { w } = await mountWith(TasksPanel)
    await w.get('[aria-label="Delete Call dentist"]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Call dentist')
    expect(w.get('[role="alert"]').text()).toContain('Task not found')
  })
})

describe('NotesPanel', () => {
  it('shows empty state', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([])
    const { w } = await mountWith(NotesPanel)
    expect(w.text()).toContain('No notes yet.')
  })

  it('links each note to its sub page', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    const { w } = await mountWith(NotesPanel)
    expect(w.get('a').attributes('href')).toBe('/notes/n1')
  })

  it('creates a note in a modal then navigates to its page', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([])
    vi.mocked(notesApi.create).mockResolvedValue(
      note({ id: 'n2', title: 'T', content: '' }) as never,
    )
    const { w, router } = await mountWith(NotesPanel)
    await btn(w, 'New note').trigger('click')
    await w.get('[aria-label="Note title"]').setValue('T')
    await w.get('[role="dialog"] form').trigger('submit')
    await flushPromises()
    expect(notesApi.create).toHaveBeenCalledWith({ title: 'T', content: '' })
    expect(router.currentRoute.value.path).toBe('/notes/n2')
  })

  it('does not create with a blank title', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([])
    const { w } = await mountWith(NotesPanel)
    await btn(w, 'New note').trigger('click')
    await w.get('[aria-label="Note title"]').setValue('  ')
    await w.get('[role="dialog"] form').trigger('submit')
    expect(notesApi.create).not.toHaveBeenCalled()
  })

  it('shows an error and stays on the modal when create fails', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([])
    vi.mocked(notesApi.create).mockRejectedValue(new Error('title too long'))
    const { w } = await mountWith(NotesPanel)
    await btn(w, 'New note').trigger('click')
    await w.get('[aria-label="Note title"]').setValue('T')
    await w.get('[role="dialog"] form').trigger('submit')
    await flushPromises()
    expect(w.get('[role="dialog"] [role="alert"]').text()).toContain('title too long')
  })

  it('asks for confirmation before deleting; cancel keeps the note', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    const { w } = await mountWith(NotesPanel)
    await w.get('[aria-label="Delete Idea"]').trigger('click')
    expect(w.get('[role="dialog"]').text()).toContain('permanently deleted')
    expect(notesApi.remove).not.toHaveBeenCalled()
    await btn(w, 'Cancel').trigger('click')
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(w.text()).toContain('Idea')
  })

  it('deletes after confirmation', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    vi.mocked(notesApi.remove).mockResolvedValue()
    const { w } = await mountWith(NotesPanel)
    await w.get('[aria-label="Delete Idea"]').trigger('click')
    await w
      .get('[role="dialog"]')
      .findAll('button')
      .find((b) => b.text() === 'Delete')!
      .trigger('click')
    await flushPromises()
    expect(notesApi.remove).toHaveBeenCalledWith('n1')
    expect(w.text()).toContain('No notes yet.')
  })

  it('keeps the confirm modal with an error when delete fails', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    vi.mocked(notesApi.remove).mockRejectedValue(new Error('Note not found'))
    const { w } = await mountWith(NotesPanel)
    await w.get('[aria-label="Delete Idea"]').trigger('click')
    await w
      .get('[role="dialog"]')
      .findAll('button')
      .find((b) => b.text() === 'Delete')!
      .trigger('click')
    await flushPromises()
    expect(w.get('[role="dialog"] [role="alert"]').text()).toContain('Note not found')
  })
})
