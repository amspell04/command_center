import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import NoteView from '../pages/NoteView.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return { ...actual, notesApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() } }
})
import { notesApi } from '../api'

const note = (o = {}) => ({ id: 'n1', title: 'Idea', content_blocks: [{ content: 'body' }], date_created: '2026-01-01', ...o })
const btn = (w: ReturnType<typeof mount>, text: string) => w.findAll('button').find((b) => b.text() === text)!

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
  it('loads the note title and blocks', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    const { w } = await open()
    expect((w.get('[aria-label="Note title"]').element as HTMLInputElement).value).toBe('Idea')
    expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('body')
  })

  it('shows not found for an unknown id', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    const { w } = await open('missing')
    expect(w.text()).toContain('Note not found.')
  })

  it('shows an error when load fails', async () => {
    vi.mocked(notesApi.list).mockRejectedValue(new Error('Cannot reach the server'))
    const { w } = await open()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
  })

  it('adds a block, saves, and drops empty blocks', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    vi.mocked(notesApi.update).mockResolvedValue(note({ content_blocks: [{ content: 'body' }, { content: 'more' }] }) as never)
    const { w } = await open()
    expect(btn(w, 'Saved').attributes('disabled')).toBeDefined()
    await btn(w, '+ Add block').trigger('click')
    await btn(w, '+ Add block').trigger('click')
    const areas = w.findAll('textarea')
    await areas[1].setValue('more')
    await btn(w, 'Save').trigger('click')
    await flushPromises()
    expect(notesApi.update).toHaveBeenCalledWith('n1', {
      title: 'Idea',
      content_blocks: [{ content: 'body' }, { content: 'more' }],
    })
    expect(btn(w, 'Saved').attributes('disabled')).toBeDefined()
  })

  it('rejects a blank title without calling the API', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    const { w } = await open()
    await w.get('[aria-label="Note title"]').setValue('  ')
    await btn(w, 'Save').trigger('click')
    expect(notesApi.update).not.toHaveBeenCalled()
    expect(w.get('[role="alert"]').text()).toContain('Title is required')
  })

  it('keeps unsaved edits and shows an error when save fails', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    vi.mocked(notesApi.update).mockRejectedValue(new Error('boom'))
    const { w } = await open()
    await w.get('textarea').setValue('changed')
    await btn(w, 'Save').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('boom')
    expect(btn(w, 'Save')).toBeTruthy()
  })

  it('deletes only after confirmation and returns home', async () => {
    vi.mocked(notesApi.list).mockResolvedValue([note()] as never)
    vi.mocked(notesApi.remove).mockResolvedValue()
    const { w, router } = await open()
    await btn(w, 'Delete note').trigger('click')
    expect(notesApi.remove).not.toHaveBeenCalled()
    await w.get('[role="dialog"]').findAll('button').find((b) => b.text() === 'Delete')!.trigger('click')
    await flushPromises()
    expect(notesApi.remove).toHaveBeenCalledWith('n1')
    expect(router.currentRoute.value.path).toBe('/')
  })
})
