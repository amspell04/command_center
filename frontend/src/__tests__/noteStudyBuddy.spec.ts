import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NoteStudyBuddy from '../components/NoteStudyBuddy.vue'
import type { StudyBuddyEvent, WeakPoint } from '../types'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    studyBuddyApi: { stream: vi.fn() },
    weakPointsApi: { ...actual.weakPointsApi, forNote: vi.fn(), setResolved: vi.fn() },
  }
})
import { ApiError, studyBuddyApi, weakPointsApi } from '../api'

const wp = (topic: string, resolved = false): WeakPoint => ({
  id: topic,
  note_id: 'n1',
  topic,
  resolved,
  date_created: '2026-01-01',
})
async function* events(...items: StudyBuddyEvent[]) {
  for (const item of items) yield item
}
const btn = (w: ReturnType<typeof mount>, text: string) => w.findAll('button').find((b) => b.text() === text)!

async function open(points: WeakPoint[] = [], unsaved = false) {
  vi.mocked(weakPointsApi.forNote).mockResolvedValue(points)
  const w = mount(NoteStudyBuddy, { props: { noteId: 'n1', unsaved } })
  await flushPromises()
  return w
}

beforeEach(() => vi.resetAllMocks())

describe('NoteStudyBuddy', () => {
  it('starts a quiz and streams the reply into the chat', async () => {
    vi.mocked(studyBuddyApi.stream).mockReturnValue(
      events({ type: 'token', text: 'What is ' }, { type: 'token', text: 'mitosis?' }, { type: 'done' }),
    )
    const w = await open()
    await btn(w, 'Start quiz').trigger('click')
    await flushPromises()
    expect(studyBuddyApi.stream).toHaveBeenCalledWith(
      'n1',
      'quiz',
      [{ role: 'user', content: 'Start the quiz.' }],
      expect.any(AbortSignal),
    )
    expect(w.find('.msg--assistant').text()).toBe('What is mitosis?')
    expect(w.find('input').exists()).toBe(true)
  })

  it('sends the answer with the whole conversation so far', async () => {
    vi.mocked(studyBuddyApi.stream)
      .mockReturnValueOnce(events({ type: 'token', text: 'Q1?' }))
      .mockReturnValueOnce(events({ type: 'token', text: 'Right.' }))
    const w = await open()
    await btn(w, 'Start quiz').trigger('click')
    await flushPromises()
    await w.get('input').setValue('  An answer ')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(vi.mocked(studyBuddyApi.stream).mock.calls[1][2]).toEqual([
      { role: 'user', content: 'Start the quiz.' },
      { role: 'assistant', content: 'Q1?' },
      { role: 'user', content: 'An answer' },
    ])
    expect(w.findAll('.msg')).toHaveLength(4)
  })

  it('does not send an empty answer', async () => {
    vi.mocked(studyBuddyApi.stream).mockReturnValue(events({ type: 'token', text: 'Q1?' }))
    const w = await open()
    await btn(w, 'Start quiz').trigger('click')
    await flushPromises()
    await w.get('input').setValue('   ')
    await w.get('form').trigger('submit')
    expect(studyBuddyApi.stream).toHaveBeenCalledTimes(1)
    expect(btn(w, 'Send').attributes('disabled')).toBeDefined()
  })

  it('refreshes the weak points when the agent adds one', async () => {
    vi.mocked(studyBuddyApi.stream).mockReturnValue(
      events({ type: 'token', text: 'Wrong.' }, { type: 'weak_point', topic: 'Mitosis' }),
    )
    const w = await open()
    expect(w.get('[data-testid="weak-points"]').text()).toContain('None yet')
    vi.mocked(weakPointsApi.forNote).mockResolvedValue([wp('Mitosis')])
    await btn(w, 'Start quiz').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="weak-points"]').text()).toContain('Mitosis')
  })

  it('runs a review and reflects a resolved topic', async () => {
    vi.mocked(studyBuddyApi.stream).mockReturnValue(
      events({ type: 'token', text: 'Good.' }, { type: 'weak_point_resolved', topic: 'Mitosis' }),
    )
    const w = await open([wp('Mitosis')])
    await btn(w, 'Review weak points').trigger('click')
    vi.mocked(weakPointsApi.forNote).mockResolvedValue([wp('Mitosis', true)])
    await btn(w, 'Start review').trigger('click')
    await flushPromises()
    expect(vi.mocked(studyBuddyApi.stream).mock.calls[0][1]).toBe('review')
    expect(w.get('li').classes()).toContain('is-resolved')
  })

  it('disables review when there are no open weak points', async () => {
    const w = await open([wp('Done', true)])
    expect(btn(w, 'Review weak points').attributes('disabled')).toBeDefined()
  })

  it('shows a stream error event and keeps the partial reply', async () => {
    vi.mocked(studyBuddyApi.stream).mockReturnValue(
      events({ type: 'token', text: 'Part' }, { type: 'error', message: 'The agent timed out' }),
    )
    const w = await open()
    await btn(w, 'Start quiz').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toBe('The agent timed out')
    expect(w.find('.msg--assistant').text()).toBe('Part')
  })

  it('shows a request failure and drops the empty reply', async () => {
    vi.mocked(studyBuddyApi.stream).mockImplementation(async function* () {
      throw new ApiError(400, 'This note is empty')
    })
    const w = await open()
    await btn(w, 'Start quiz').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toBe('This note is empty')
    expect(w.find('.msg--assistant').exists()).toBe(false)
  })

  it('blocks the chat while the note has unsaved edits', async () => {
    const w = await open([], true)
    expect(btn(w, 'Start quiz').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Save your changes first')
  })

  it('lets the user reopen a resolved weak point', async () => {
    const w = await open([wp('Mitosis', true)])
    vi.mocked(weakPointsApi.setResolved).mockResolvedValue(wp('Mitosis', false))
    await btn(w, 'Reopen').trigger('click')
    await flushPromises()
    expect(weakPointsApi.setResolved).toHaveBeenCalledWith('Mitosis', false)
    expect(btn(w, 'Resolve')).toBeDefined()
  })

  it('shows an error when a weak point update fails', async () => {
    const w = await open([wp('Mitosis')])
    vi.mocked(weakPointsApi.setResolved).mockRejectedValue(new ApiError(404, 'Weak point not found'))
    await btn(w, 'Resolve').trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toBe('Weak point not found')
  })

  it('emits close', async () => {
    const w = await open()
    await w.get('[aria-label="Close study buddy"]').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })
})
