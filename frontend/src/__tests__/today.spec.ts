import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import TodayPanel from '../components/TodayPanel.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    newsApi: { today: vi.fn(), latest: vi.fn(), get: vi.fn(), refresh: vi.fn() },
    agentsApi: { planDay: vi.fn(), summarizeNote: vi.fn() },
  }
})
import { agentsApi, ApiError, newsApi } from '../api'

const news = (o = {}) => ({
  id: 'b1',
  title: 'Morning briefing',
  summary: 'Things happened.',
  quiz_section: [],
  sources: [],
  date_created: '2026-01-02',
  ...o,
})
const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find((b) => b.text() === text)

async function mountPanel() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/news/:id', component: { template: '<div />' } },
    ],
  })
  router.push('/')
  await router.isReady()
  const w = mount(TodayPanel, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

beforeEach(() => vi.resetAllMocks())

describe('TodayPanel', () => {
  it("links today's headline to its briefing page and does not offer to generate", async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    const w = await mountPanel()
    const link = w.get('a.headline')
    expect(link.text()).toBe('Morning briefing')
    expect(link.attributes('href')).toBe('/news/b1')
    expect(btn(w, 'Generate briefing')).toBeUndefined()
    expect(newsApi.latest).not.toHaveBeenCalled()
  })

  it('does not render the full briefing on the home page', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([
      news({ quiz_section: [{ question: 'Q1?', answer: 'A1' }], sources: ['https://x.test'] }),
    ] as never)
    const w = await mountPanel()
    expect(w.text()).not.toContain('Things happened.')
    expect(w.text()).not.toContain('Q1?')
    expect(w.text()).not.toContain('https://x.test')
  })

  it('falls back to the latest older briefing and still offers to generate today', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockResolvedValue(news({ id: 'old', title: 'Old news' }) as never)
    const w = await mountPanel()
    expect(w.get('a.headline').attributes('href')).toBe('/news/old')
    expect(w.text()).toContain('From 2026-01-02')
    expect(btn(w, 'Generate briefing')!.attributes('disabled')).toBeUndefined()
  })

  it('shows an empty state when no briefing has ever been made, then generates one', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(404, 'Briefing not found'))
    vi.mocked(newsApi.refresh).mockResolvedValue(news() as never)
    const w = await mountPanel()
    expect(w.text()).toContain('No briefing yet.')
    expect(w.find('[role="alert"]').exists()).toBe(false)
    await btn(w, 'Generate briefing')!.trigger('click')
    await flushPromises()
    expect(newsApi.refresh).toHaveBeenCalledTimes(1)
    expect(w.get('a.headline').text()).toBe('Morning briefing')
    expect(btn(w, 'Generate briefing')).toBeUndefined()
  })

  it('disables the button while generating', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(404, 'x'))
    let resolve!: (v: never) => void
    vi.mocked(newsApi.refresh).mockReturnValue(new Promise((r) => (resolve = r as never)))
    const w = await mountPanel()
    await btn(w, 'Generate briefing')!.trigger('click')
    expect(btn(w, 'Generating…')!.attributes('disabled')).toBeDefined()
    await btn(w, 'Generating…')!.trigger('click')
    expect(newsApi.refresh).toHaveBeenCalledTimes(1)
    resolve(news() as never)
    await flushPromises()
    expect(w.get('a.headline').text()).toBe('Morning briefing')
  })

  it('on a 400 shows the briefing that already exists', async () => {
    vi.mocked(newsApi.today).mockResolvedValueOnce([]).mockResolvedValueOnce([news()] as never)
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(404, 'x'))
    vi.mocked(newsApi.refresh).mockRejectedValue(new ApiError(400, 'exists'))
    const w = await mountPanel()
    await btn(w, 'Generate briefing')!.trigger('click')
    await flushPromises()
    expect(w.get('a.headline').text()).toBe('Morning briefing')
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })

  it('keeps the button enabled after a failed generation', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(404, 'x'))
    vi.mocked(newsApi.refresh).mockRejectedValue(new ApiError(502, 'No recent articles'))
    const w = await mountPanel()
    await btn(w, 'Generate briefing')!.trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('No recent articles')
    expect(btn(w, 'Generate briefing')!.attributes('disabled')).toBeUndefined()
  })

  it('shows a load error with retry', async () => {
    vi.mocked(newsApi.today)
      .mockRejectedValueOnce(new ApiError(0, 'Cannot reach the server'))
      .mockResolvedValueOnce([news()] as never)
    const w = await mountPanel()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
    await btn(w, 'Retry')!.trigger('click')
    await flushPromises()
    expect(w.get('a.headline').text()).toBe('Morning briefing')
  })

  it('surfaces a latest-lookup failure other than 404', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(500, 'db down'))
    const w = await mountPanel()
    expect(w.get('[role="alert"]').text()).toContain('db down')
  })

  it('hosts the Plan my day button', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    vi.mocked(agentsApi.planDay).mockResolvedValue({ date: '2026-01-02', items: [] })
    const w = await mountPanel()
    await btn(w, 'Plan my day')!.trigger('click')
    await flushPromises()
    expect(agentsApi.planDay).toHaveBeenCalledTimes(1)
  })
})
