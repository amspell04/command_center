import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import NewsBriefing from '../components/NewsBriefing.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return {
    ...actual,
    newsApi: { today: vi.fn(), latest: vi.fn(), refresh: vi.fn() },
  }
})
import { ApiError, newsApi } from '../api'

const news = (o = {}) => ({
  id: 'b1',
  title: 'Morning briefing',
  summary: 'Things happened.',
  body: 'Long details of the events.',
  quiz_section: [],
  sources: [],
  articles: [{ title: 'Big story', url: 'https://x.test/1' }],
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
    ],
  })
  router.push('/')
  await router.isReady()
  const w = mount(NewsBriefing, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

beforeEach(() => vi.resetAllMocks())

describe('NewsBriefing', () => {
  it("shows today's briefing inline and does not offer to generate", async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    const w = await mountPanel()
    expect(w.get('h3.headline').text()).toBe('Morning briefing')
    expect(w.find('a.headline').exists()).toBe(false)
    expect(btn(w, 'Generate briefing')).toBeUndefined()
    expect(newsApi.latest).not.toHaveBeenCalled()
  })

  it("offers Regenerate when today's briefing exists and replaces it", async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    vi.mocked(newsApi.refresh).mockResolvedValue(news({ id: 'b2', title: 'Fresh briefing' }) as never)
    const w = await mountPanel()
    await btn(w, 'Regenerate')!.trigger('click')
    await flushPromises()
    expect(newsApi.refresh).toHaveBeenCalledWith(true)
  })

  it('keeps the existing briefing and shows the error when regenerating fails', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    vi.mocked(newsApi.refresh).mockRejectedValue(new ApiError(502, 'No recent articles'))
    const w = await mountPanel()
    await btn(w, 'Regenerate')!.trigger('click')
    await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('No recent articles')
    expect(w.get('h3.headline').text()).toBe('Morning briefing')
    expect(btn(w, 'Regenerate')!.attributes('disabled')).toBeUndefined()
  })

  it('shows summary, body and quiz answers inline on the home page', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([
      news({ quiz_section: [{ question: 'Q1?', answer: 'A1' }] }),
    ] as never)
    const w = await mountPanel()
    expect(w.get('[data-testid="briefing-summary"]').text()).toBe('Things happened.')
    expect(w.get('[data-testid="briefing-body"]').text()).toBe('Long details of the events.')
    expect(w.get('[data-testid="briefing-quiz"]').text()).toContain('Q1?')
    expect(w.get('[data-testid="briefing-quiz"]').text()).toContain('A1')
  })

  it('omits the quiz section when there are no questions', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news({ quiz_section: [] })] as never)
    expect((await mountPanel()).find('[data-testid="briefing-quiz"]').exists()).toBe(false)
  })

  it('links the covered articles in a new tab', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news()] as never)
    const a = (await mountPanel()).get('[data-testid="briefing-links"] a')
    expect(a.text()).toBe('Big story')
    expect(a.attributes()).toMatchObject({ href: 'https://x.test/1', target: '_blank', rel: 'noopener noreferrer' })
  })

  it('shows no links when there are no articles, and never links a non-http url', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([news({ articles: [] })] as never)
    expect((await mountPanel()).find('[data-testid="briefing-links"]').exists()).toBe(false)
    vi.mocked(newsApi.today).mockResolvedValue([
      news({ articles: [{ title: 'Bad', url: 'javascript:alert(1)' }] }),
    ] as never)
    expect((await mountPanel()).find('[data-testid="briefing-links"] a').exists()).toBe(false)
  })

  it('shows no summary when there is no briefing', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(404, 'none'))
    const w = await mountPanel()
    expect(w.find('[data-testid="briefing-summary"]').exists()).toBe(false)
  })

  it('falls back to the latest older briefing and still offers to generate today', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockResolvedValue(news({ id: 'old', title: 'Old news' }) as never)
    const w = await mountPanel()
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
    expect(w.get('h3.headline').text()).toBe('Morning briefing')
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
    expect(w.get('h3.headline').text()).toBe('Morning briefing')
  })

  it('on a 409 shows the briefing that already exists', async () => {
    vi.mocked(newsApi.today).mockResolvedValueOnce([]).mockResolvedValueOnce([news()] as never)
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(404, 'x'))
    vi.mocked(newsApi.refresh).mockRejectedValue(new ApiError(409, 'exists'))
    const w = await mountPanel()
    await btn(w, 'Generate briefing')!.trigger('click')
    await flushPromises()
    expect(w.get('h3.headline').text()).toBe('Morning briefing')
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
    expect(w.get('h3.headline').text()).toBe('Morning briefing')
  })

  it('surfaces a latest-lookup failure other than 404', async () => {
    vi.mocked(newsApi.today).mockResolvedValue([])
    vi.mocked(newsApi.latest).mockRejectedValue(new ApiError(500, 'db down'))
    const w = await mountPanel()
    expect(w.get('[role="alert"]').text()).toContain('db down')
  })
})
