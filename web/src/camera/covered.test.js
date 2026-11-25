import { describe, expect, it } from 'vitest'
import { COVER, frameStats, isCovered } from './covered.js'
import { EarTimer } from './phoneAtEar.js'

const W = 32, H = 24
// RGBA frame from a function (x, y) -> [r, g, b]
const frame = (f) => {
  const d = new Uint8ClampedArray(W * H * 4)
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const [r, g, b] = f(x, y); const i = (y * W + x) * 4
    d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = 255
  }
  return d
}
// a deterministic "noise" for skin and sensor grain
const n = (x, y, a) => ((x * 73 + y * 151) % 7 - 3) * a / 3

describe('covered frame', () => {
  it('black lens (tape, hand pressed on the camera)', () => {
    expect(isCovered(frameStats(frame(() => [3, 3, 4])))).toBe(true)
  })

  it('finger on the lens in a lit room: flat skin colour with grain', () => {
    expect(isCovered(frameStats(frame((x, y) => [200 + n(x, y, 4), 120 + n(x, y, 4), 100 + n(x, y, 4)])))).toBe(true)
  })

  it('sheet of paper over the lens: bright and flat', () => {
    expect(isCovered(frameStats(frame((x, y) => [235 + n(x, y, 3), 235 + n(x, y, 3), 230 + n(x, y, 3)])))).toBe(true)
  })

  it('ordinary scene: face, background, edges', () => {
    const scene = frame((x, y) => {
      const face = (x - 16) ** 2 + (y - 9) ** 2 < 36
      const body = y > 15 && x > 8 && x < 24
      return face ? [210, 160, 140] : body ? [40, 60, 120] : [150 - y * 2, 150 - y * 2, 145]
    })
    const s = frameStats(scene)
    expect(isCovered(s)).toBe(false)
    expect(s.spread).toBeGreaterThan(COVER.maxSpread * 2)
  })

  it('dim room with a person is not covered', () => {
    const scene = frame((x, y) => ((x - 16) ** 2 + (y - 10) ** 2 < 40 ? [70, 55, 50] : [25, 25, 30]))
    expect(isCovered(frameStats(scene))).toBe(false)
  })

  it('empty data', () => {
    expect(frameStats(new Uint8ClampedArray(0))).toEqual({ mean: 0, spread: 0 })
  })
})

describe('covered for long enough', () => {
  it('2 s covered counts, a 1 s cover does not', () => {
    const t = new EarTimer(COVER.graceMs)
    for (let ms = 0; ms <= 1000; ms += 250) t.push(ms, true)
    expect(t.snapshot(1000).longest).toBeLessThan(COVER.minSec)
    for (let ms = 1250; ms <= 3000; ms += 250) t.push(ms, false)
    for (let ms = 3250; ms <= 5500; ms += 250) t.push(ms, true)
    expect(t.snapshot(5500).longest).toBeGreaterThanOrEqual(COVER.minSec)
  })
})
