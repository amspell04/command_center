import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import NewsView from '../pages/NewsView.vue'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return { ...actual, newsApi: { today: vi.fn(), latest: vi.fn(), get: vi.fn(), refresh: vi.fn() } }
})
import { ApiError, newsApi } from '../api'

const news = (o = {}) => ({
  id: 'b1',
  title: 'Morning briefing',
  summary: 'Things happened.',
  quiz_section: [{ question: 'What happened?', answer: 'Things.' }],
  sources: ['https://example.com/feed'],
  date_created: '2026-01-01',
  ...o,
})

async function open(id = 'b1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/news/:id', component: NewsView },
    ],
  })
  router.push(`/news/${id}`)
  await router.isReady()
  const w = mount(NewsView, { global: { plugins: [router] } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => vi.resetAllMocks())

describe('NewsView', () => {
  it('shows the full briefing with quiz and sources, fetched by route id', async () => {
    vi.mocked(newsApi.get).mockResolvedValue(news() as never)
    const { w } = await open('b1')
    expect(newsApi.get).toHaveBeenCalledWith('b1')
    expect(w.text()).toContain('Morning briefing')
    expect(w.text()).toContain('Things happened.')
    expect(w.text()).toContain('What happened?')
    expect(w.text()).toContain('https://example.com/feed')
  })

  it('omits quiz and sources sections when empty', async () => {
    vi.mocked(newsApi.get).mockResolvedValue(news({ quiz_section: [], sources: [] }) as never)
    const { w } = await open()
    expect(w.text()).not.toContain('Quiz')
    expect(w.text()).not.toContain('Sources')
  })

  it.each([404, 422])('shows not found on a %i', async (status) => {
    vi.mocked(newsApi.get).mockRejectedValue(new ApiError(status, 'nope'))
    const { w } = await open('missing')
    expect(w.text()).toContain('Briefing not found')
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })

  it('shows other errors with retry', async () => {
    vi.mocked(newsApi.get)
      .mockRejectedValueOnce(new ApiError(0, 'Cannot reach the server'))
      .mockResolvedValueOnce(news() as never)
    const { w } = await open()
    expect(w.get('[role="alert"]').text()).toContain('Cannot reach the server')
    await w.findAll('button').find((b) => b.text() === 'Retry')!.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Morning briefing')
  })

  it('prints and goes back home', async () => {
    vi.mocked(newsApi.get).mockResolvedValue(news() as never)
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { w, router } = await open()
    await w.findAll('button').find((b) => b.text() === 'Print')!.trigger('click')
    expect(print).toHaveBeenCalledTimes(1)
    await w.findAll('button').find((b) => b.text() === '← Back')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/')
  })
})
