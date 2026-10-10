import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BriefingPanel from '../components/BriefingPanel.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return { ...actual, newsApi: { today: vi.fn(), refresh: vi.fn() } }
})
import { ApiError, newsApi } from '../api'

const news = (o = {}) => ({
  id: 'b1', title: 'Morning briefing', summary: 'Things happened.',
  quiz_section: [{ question: 'What happened?', answer: 'Things.' }],
  sources: ['https://example.com/feed'], date_created: '2026-01-01', ...o,
})
const generate = (w: ReturnType<typeof mount>) => w.findAll('button').find((b) => b.text().includes('enerat'))!

async function mountPanel() {
  const w = mount(BriefingPanel)
  await flushPromises()
  return w
}

beforeEach(() => vi.resetAllMocks())

describe('BriefingPanel', () => {
  it('shows today\'s briefing with quiz and sources, and disables generating', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    const w = await mountPanel()
    expect(w.text()).toContain('Morning briefing')
    expect(w.text()).toContain('What happened?')
    expect(w.text()).toContain('https://example.com/feed')
    expect(generate(w).attributes('disabled')).toBeDefined()
  })

  it('offers to generate when there is no briefing, then locks the button', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.refresh).mockResolvedValue(news() as never)
    const w = await mountPanel()
    expect(w.text()).toContain('No briefing yet today')
    expect(generate(w).attributes('disabled')).toBeUndefined()
    await generate(w).trigger('click')
    await flushPromises()
    expect(newsApi.refresh).toHaveBeenCalledTimes(1)
    expect(w.text()).toContain('Morning briefing')
    expect(generate(w).attributes('disabled')).toBeDefined()
  })

  it('disables the button while generating, so it cannot be double-clicked', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    let resolve!: (v: never) => void
    vi.mocked(newsApi.refresh).mockReturnValue(new Promise((r) => (resolve = r as never)))
    const w = await mountPanel()
    await generate(w).trigger('click')
    expect(generate(w).text()).toBe('Generating…')
    expect(generate(w).attributes('disabled')).toBeDefined()
    await generate(w).trigger('click')
    expect(newsApi.refresh).toHaveBeenCalledTimes(1)
    resolve(news() as never)
    await flushPromises()
    expect(w.text()).toContain('Morning briefing')
  })

  it('on a 400 shows the briefing that already exists', async () => {
    vi.mocked(newsApi.today).mockResolvedValueOnce([]).mockResolvedValueOnce([news()] as never)
    vi.mocked(newsApi.refresh).mockRejectedValue(new ApiError(400, "Today's briefing already exists"))
    const w = await mountPanel()
    await generate(w).trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Morning briefing')
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(generate(w).attributes('disabled')).toBeDefined()
  })

  it('keeps the button enabled after a failed generation so it can be retried', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.refresh).mockRejectedValue(new ApiError(502, 'No recent articles could be fetched'))
    const w = await mountPanel()
    await generate(w).trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('No recent articles')
    expect(generate(w).attributes('disabled')).toBeUndefined()
  })

  it('shows a load error with retry', async () => {
    vi.mocked(newsApi.today).mockRejectedValueOnce(new ApiError(0, 'Cannot reach the server')).mockResolvedValueOnce([news()] as never)
    const w = await mountPanel()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
    await w.findAll('button').find((b) => b.text() === 'Retry')!.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Morning briefing')
  })
})
