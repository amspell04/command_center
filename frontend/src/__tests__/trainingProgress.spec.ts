import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TrainingProgress from '../components/TrainingProgress.vue'
import { chartPoints, daysBetween, personalRecords } from '../utils/training'

vi.mock('../api', async (orig) => {
  const actual = await orig<typeof import('../api')>()
  return { ...actual, trainingApi: { progress: vi.fn() } }
})
import { ApiError, trainingApi } from '../api'

const pt = (date: string, lb: number) => ({ date, estimated_1rm_lb: lb, estimated_1rm_kg: Math.round((lb / 2.20462262185) * 10) / 10 })

describe('progress utils', () => {
  it('finds the points that beat every earlier one', () => {
    const pts = [pt('2026-01-01', 300), pt('2026-01-08', 290), pt('2026-01-15', 310), pt('2026-01-22', 310), pt('2026-01-29', 320)]
    expect(personalRecords(pts).map((p) => p.estimated_1rm_lb)).toEqual([300, 310, 320])
    expect(personalRecords([])).toEqual([])
  })

  it('counts whole days, across a month end and backwards', () => {
    expect(daysBetween('2026-01-30', '2026-02-02')).toBe(3)
    expect(daysBetween('2026-02-02', '2026-01-30')).toBe(-3)
    expect(daysBetween('2026-10-10', '2026-10-10')).toBe(0)
  })

  it('places chart points by date and value, highest value at the top', () => {
    const c = chartPoints([pt('2026-01-01', 300), pt('2026-01-11', 400), pt('2026-01-21', 350)], 100, 50, 10)
    expect(c.map((p) => p.x)).toEqual([10, 50, 90])
    expect(c[1]!.y).toBe(10)
    expect(c[0]!.y).toBe(40)
    expect(c[2]!.y).toBe(25)
  })

  it('spaces points by calendar gap, not by count', () => {
    const c = chartPoints([pt('2026-01-01', 300), pt('2026-01-02', 310), pt('2026-01-11', 320)], 100, 50, 0)
    expect(c.map((p) => p.x)).toEqual([0, 10, 100])
  })

  it('centres a single point and a flat line', () => {
    expect(chartPoints([pt('2026-01-01', 300)], 100, 50)).toMatchObject([{ x: 50, y: 25 }])
    expect(chartPoints([pt('2026-01-01', 300), pt('2026-01-08', 300)], 100, 50).map((p) => p.y)).toEqual([25, 25])
    expect(chartPoints([], 100, 50)).toEqual([])
  })
})

describe('TrainingProgress', () => {
  const history = (o: Partial<Record<string, object[]>> = {}) =>
    vi.mocked(trainingApi.progress).mockImplementation(async (lift) => (o[lift] ?? []) as never)

  async function mountProgress() {
    const w = mount(TrainingProgress)
    await flushPromises()
    return w
  }

  beforeEach(() => vi.resetAllMocks())

  it('shows the latest estimated 1RM in both units, the change and the records', async () => {
    history({ SQUAT: [pt('2026-09-01', 300), pt('2026-09-08', 290), pt('2026-09-15', 320)] })
    const w = await mountProgress()
    const squat = w.get('[data-testid="lift-SQUAT"]')
    expect(squat.get('[data-testid="latest"]').text()).toContain('320 lb / 145.1 kg')
    expect(squat.get('[data-testid="gain"]').text()).toContain('+20 lb since')
    const records = squat.findAll('[data-testid="records"] li').map((l) => l.text())
    expect(records).toHaveLength(2)
    expect(records[0]).toContain('320 lb') // newest record first
    expect(squat.find('svg polyline').exists()).toBe(true)
    expect(squat.findAll('circle')).toHaveLength(3)
  })

  it('shows a loss as a negative change', async () => {
    history({ BENCH: [pt('2026-09-01', 250), pt('2026-09-08', 240)] })
    const w = await mountProgress()
    expect(w.get('[data-testid="lift-BENCH"] [data-testid="gain"]').text()).toContain('-10 lb')
  })

  it('shows one session as a point with no change line', async () => {
    history({ DEADLIFT: [pt('2026-09-01', 400)] })
    const w = await mountProgress()
    const dl = w.get('[data-testid="lift-DEADLIFT"]')
    expect(dl.find('[data-testid="gain"]').exists()).toBe(false)
    expect(dl.find('polyline').exists()).toBe(false)
    expect(dl.findAll('circle')).toHaveLength(1)
  })

  it('says so when a lift or everything has no data', async () => {
    history({ SQUAT: [pt('2026-09-01', 300)] })
    const w = await mountProgress()
    expect(w.get('[data-testid="lift-BENCH"]').text()).toContain('No sets logged yet')
    expect(w.text()).not.toContain('Log a workout to start')

    vi.resetAllMocks()
    history()
    const empty = await mountProgress()
    expect(empty.text()).toContain('Log a workout to start tracking')
  })

  it('still shows the other lifts when one fails to load', async () => {
    vi.mocked(trainingApi.progress).mockImplementation(async (lift) => {
      if (lift === 'BENCH') throw new ApiError(500, 'boom')
      return (lift === 'SQUAT' ? [pt('2026-09-01', 300)] : []) as never
    })
    const w = await mountProgress()
    expect(w.get('[role="alert"]').text()).toContain('Bench')
    expect(w.get('[data-testid="lift-SQUAT"]').text()).toContain('300 lb')
  })

  it('reloads when the refresh key changes', async () => {
    history({ SQUAT: [pt('2026-09-01', 300)] })
    const w = await mountProgress()
    history({ SQUAT: [pt('2026-09-01', 300), pt('2026-09-08', 310)] })
    await w.setProps({ refreshKey: 1 })
    await flushPromises()
    expect(w.get('[data-testid="lift-SQUAT"] [data-testid="latest"]').text()).toContain('310 lb')
  })
})
