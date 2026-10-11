import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import NoteView from '../pages/NoteView.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    notesApi: { get: vi.fn(), list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  }
})
import { ApiError, notesApi } from '../api'

const note = (o = {}) => ({
  id: 'n1',
  title: 'Idea',
  content: 'body',
  date_created: '2026-01-01',
  summary: null,
  summary_generated_at: null,
  summary_stale: false,
  ...o,
})
const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find((b) => b.text() === text)!

async function open(id = 'n1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/notes/:id', component: NoteView },
    ],
  })
  router.push(`/notes/${id}`)
  await router.isReady()
  const w = mount(NoteView, { global: { plugins: [router], stubs: { teleport: true } } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => vi.resetAllMocks())

describe('NoteView', () => {
  it('shows a stored summary without running the agent', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note({ summary: 'Stored.' }) as never)
    const { w } = await open()
    expect(w.get('[data-testid="note-summary"]').text()).toContain('Stored.')
    expect(w.text()).not.toContain('changed since')
    expect(btn(w, 'Regenerate summary')).toBeDefined()
  })

  it('shows no summary section when there is none', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note() as never)
    const { w } = await open()
    expect(w.find('[data-testid="note-summary"]').exists()).toBe(false)
    expect(btn(w, 'Summarize')).toBeDefined()
  })

  it('flags a stale summary', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note({ summary: 'Old.', summary_stale: true }) as never)
    const { w } = await open()
    expect(w.get('[data-testid="note-summary"]').text()).toContain('The note changed since')
    expect(btn(w, 'Summarize')).toBeDefined()
  })

  it('renders summary text as plain text, not HTML', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note({ summary: '<img src=x onerror="x()">hi' }) as never)
    const { w } = await open()
    expect(w.get('[data-testid="note-summary"]').find('img').exists()).toBe(false)
  })

  it('loads the note title and shows content as rendered markdown, not a textarea', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note({ content: '# Head\n\n**bold**' }) as never)
    const { w } = await open()
    expect((w.get('[aria-label="Note title"]').element as HTMLInputElement).value).toBe('Idea')
    expect(w.find('textarea').exists()).toBe(false)
    const html = w.get('[data-testid="note-rendered"]')
    expect(html.find('h1').text()).toBe('Head')
    expect(html.find('strong').text()).toBe('bold')
  })

  it('sanitizes script and event handlers in rendered content', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(
      note({ content: '<script>x()</script><img src=x onerror="x()">hi' }) as never,
    )
    const { w } = await open()
    const html = w.get('[data-testid="note-rendered"]')
    expect(html.find('script').exists()).toBe(false)
    expect(html.html()).not.toContain('onerror')
  })

  it('starts in edit mode for an empty note', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note({ content: '' }) as never)
    const { w } = await open()
    expect(w.find('textarea').exists()).toBe(true)
    expect(w.find('[data-testid="note-rendered"]').exists()).toBe(false)
  })

  it('shows not found for an unknown id', async () => {
    vi.mocked(notesApi.get).mockRejectedValue(new ApiError(404, 'Note not found'))
    const { w } = await open('missing')
    expect(notesApi.get).toHaveBeenCalledWith('missing')
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(w.text()).toContain('Note not found.')
  })

  it('shows an error when load fails', async () => {
    vi.mocked(notesApi.get).mockRejectedValue(new Error('Cannot reach the server'))
    const { w } = await open()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
  })

  it('edits in a textarea, returns to rendered view on Done, and saves', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note() as never)
    vi.mocked(notesApi.update).mockResolvedValue(note({ content: '## new' }) as never)
    const { w } = await open()
    expect(btn(w, 'Saved').attributes('disabled')).toBeDefined()
    await btn(w, 'Edit').trigger('click')
    await w.get('textarea').setValue('## new')
    await btn(w, 'Done').trigger('click')
    expect(w.find('textarea').exists()).toBe(false)
    expect(w.get('[data-testid="note-rendered"] h2').text()).toBe('new')
    await btn(w, 'Save').trigger('click')
    await flushPromises()
    expect(notesApi.update).toHaveBeenCalledWith('n1', { title: 'Idea', content: '## new' })
    expect(btn(w, 'Saved').attributes('disabled')).toBeDefined()
  })

  it('rejects a blank title without calling the API', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note() as never)
    const { w } = await open()
    await w.get('[aria-label="Note title"]').setValue('  ')
    await btn(w, 'Save').trigger('click')
    expect(notesApi.update).not.toHaveBeenCalled()
    expect(w.get('[role="alert"]').text()).toContain('Title is required')
  })

  it('keeps unsaved edits and shows an error when save fails', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note() as never)
    vi.mocked(notesApi.update).mockRejectedValue(new Error('boom'))
    const { w } = await open()
    await btn(w, 'Edit').trigger('click')
    await w.get('textarea').setValue('changed')
    await btn(w, 'Save').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('boom')
    expect(btn(w, 'Save')).toBeTruthy()
  })

  it('deletes only after confirmation and returns home', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note() as never)
    vi.mocked(notesApi.remove).mockResolvedValue()
    const { w, router } = await open()
    await btn(w, 'Delete note').trigger('click')
    expect(notesApi.remove).not.toHaveBeenCalled()
    await w
      .get('[role="dialog"]')
      .findAll('button')
      .find((b) => b.text() === 'Delete')!
      .trigger('click')
    await flushPromises()
    expect(notesApi.remove).toHaveBeenCalledWith('n1')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('opens and closes the study buddy drawer', async () => {
    vi.mocked(notesApi.get).mockResolvedValue(note() as never)
    const { w } = await open()
    expect(w.find('[aria-label="Study buddy"]').exists()).toBe(false)
    await btn(w, 'Study buddy').trigger('click')
    expect(w.find('[aria-label="Study buddy"]').exists()).toBe(true)
    await w.get('[aria-label="Close study buddy"]').trigger('click')
    expect(w.find('[aria-label="Study buddy"]').exists()).toBe(false)
  })
})
