import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NoteAgentActions from '../components/NoteAgentActions.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    agentsApi: { planDay: vi.fn(), summarizeNote: vi.fn() },
  }
})
import { agentsApi, ApiError } from '../api'

const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find((b) => b.text() === text)!

beforeEach(() => vi.resetAllMocks())

describe('NoteAgentActions', () => {
  const mountIt = (unsaved = false, hasSummary = false, stale = false) =>
    mount(NoteAgentActions, { props: { noteId: 'n1', unsaved, hasSummary, stale } })

  it('is disabled while the note has unsaved changes', async () => {
    const w = mountIt(true)
    expect(btn(w, 'Summarize').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Save your changes first')
    await btn(w, 'Summarize').trigger('click')
    expect(agentsApi.summarizeNote).not.toHaveBeenCalled()
  })

  it('emits the updated note after summarizing', async () => {
    const updated = {
      id: 'n1',
      title: 'T',
      content: 'a',
      date_created: 'd',
      summary: 'x',
      summary_generated_at: 'ts',
      summary_stale: false,
    }
    vi.mocked(agentsApi.summarizeNote).mockResolvedValue(updated)
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    await flushPromises()
    expect(w.emitted('summarized')![0]).toEqual([updated])
  })

  it('shows an error and keeps the note unchanged when summarizing fails', async () => {
    vi.mocked(agentsApi.summarizeNote).mockRejectedValue(new ApiError(400, 'Note has no content'))
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('Note has no content')
    expect(w.emitted('summarized')).toBeUndefined()
    expect(btn(w, 'Summarize').attributes('disabled')).toBeUndefined()
  })

  it('asks for a first summary without force', async () => {
    vi.mocked(agentsApi.summarizeNote).mockResolvedValue({} as never)
    const w = mountIt()
    await btn(w, 'Summarize').trigger('click')
    expect(agentsApi.summarizeNote).toHaveBeenCalledWith('n1', false)
  })

  it('offers Regenerate when a current summary exists and forces it', async () => {
    vi.mocked(agentsApi.summarizeNote).mockResolvedValue({} as never)
    const w = mountIt(false, true, false)
    expect(w.findAll('button').some((b) => b.text() === 'Summarize')).toBe(false)
    await btn(w, 'Regenerate summary').trigger('click')
    expect(agentsApi.summarizeNote).toHaveBeenCalledWith('n1', true)
  })

  it('offers Summarize for a stale summary without force', async () => {
    vi.mocked(agentsApi.summarizeNote).mockResolvedValue({} as never)
    const w = mountIt(false, true, true)
    await btn(w, 'Summarize').trigger('click')
    expect(agentsApi.summarizeNote).toHaveBeenCalledWith('n1', false)
  })
})
