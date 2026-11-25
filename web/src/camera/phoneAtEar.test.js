import { describe, expect, it } from 'vitest'
import { EarTimer, handAtEar, LM } from './phoneAtEar.js'

const W = 640, H = 480
// A person facing the camera: shoulders 200 px apart, ears above them, hands down at the hips.
function body(over = {}) {
  const lm = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.95, z: 0, visibility: 0.9 }))
  const set = (i, x, y, v = 0.9) => { lm[i] = { x: x / W, y: y / H, z: 0, visibility: v } }
  set(LM.L_SHOULDER, 420, 300); set(LM.R_SHOULDER, 220, 300)
  set(LM.L_EAR, 360, 160); set(LM.R_EAR, 280, 160)
  for (const i of [LM.L_WRIST, LM.L_PINKY, LM.L_INDEX, LM.L_THUMB]) set(i, 440, 470)
  for (const i of [LM.R_WRIST, LM.R_PINKY, LM.R_INDEX, LM.R_THUMB]) set(i, 200, 470)
  for (const [i, p] of Object.entries(over)) set(Number(i), ...p)
  return lm
}

describe('handAtEar', () => {
  it('hands down: not at the ear', () => {
    const r = handAtEar(body(), W, H)
    expect(r.known).toBe(true)
    expect(r.atEar).toBe(false)
  })

  it('left hand at the left ear (phone call)', () => {
    const r = handAtEar(body({ [LM.L_WRIST]: [380, 200], [LM.L_INDEX]: [365, 165], [LM.L_THUMB]: [370, 175] }), W, H)
    expect(r.atEar).toBe(true)
    expect(r.side).toBe('left')
  })

  it('right hand at the right ear', () => {
    const r = handAtEar(body({ [LM.R_WRIST]: [265, 205], [LM.R_INDEX]: [282, 170] }), W, H)
    expect(r.atEar).toBe(true)
    expect(r.side).toBe('right')
  })

  it('hand at the chin, between the ears, is not counted', () => {
    // chin is about 130 px from each ear here; the limit is 0.45 * 200 = 90 px
    const r = handAtEar(body({ [LM.L_WRIST]: [320, 250], [LM.L_INDEX]: [320, 245] }), W, H)
    expect(r.atEar).toBe(false)
  })

  it('ear covered by the hand (low visibility) still counts', () => {
    const r = handAtEar(body({ [LM.L_EAR]: [360, 160, 0.3], [LM.L_WRIST]: [380, 200], [LM.L_INDEX]: [365, 165] }), W, H)
    expect(r.atEar).toBe(true)
  })

  it('an ear the model does not see at all is skipped', () => {
    const r = handAtEar(body({ [LM.L_EAR]: [360, 160, 0.05], [LM.L_WRIST]: [380, 200], [LM.L_INDEX]: [365, 165] }), W, H)
    expect(r.atEar).toBe(false)
  })

  it('a hand point the model is unsure about is ignored', () => {
    const r = handAtEar(body({ [LM.L_INDEX]: [362, 162, 0.2] }), W, H)
    expect(r.atEar).toBe(false)
  })

  it('no shoulders visible: no decision', () => {
    const r = handAtEar(body({ [LM.L_SHOULDER]: [420, 300, 0.1] }), W, H)
    expect(r.known).toBe(false)
    expect(r.atEar).toBe(false)
  })

  it('works the same for a person far from the camera (distances scale with shoulders)', () => {
    // the same pose shrunk to a third around the centre
    const near = body({ [LM.L_WRIST]: [380, 200], [LM.L_INDEX]: [365, 165] })
    const far = near.map(p => ({ ...p, x: 0.5 + (p.x - 0.5) / 3, y: 0.5 + (p.y - 0.5) / 3 }))
    expect(handAtEar(far, W, H).atEar).toBe(true)
  })

  it('no landmarks at all', () => {
    expect(handAtEar(undefined, W, H)).toMatchObject({ known: false, atEar: false })
  })
})

describe('EarTimer', () => {
  const feed = (timer, from, to, atEar, step = 100) => {
    let s
    for (let t = from; t <= to; t += step) s = timer.push(t, atEar)
    return s
  }

  it('counts a continuous stretch', () => {
    const tm = new EarTimer()
    const s = feed(tm, 0, 4000, true)
    expect(s.current).toBeCloseTo(4, 5)
    expect(s.longest).toBeCloseTo(4, 5)
    expect(s.active).toBe(true)
  })

  it('a short dropout (< grace) does not break the stretch', () => {
    const tm = new EarTimer(600)
    feed(tm, 0, 2000, true)
    feed(tm, 2100, 2400, false)          // 400 ms of missed frames
    const s = feed(tm, 2500, 4000, true)
    expect(s.current).toBeCloseTo(4, 5)
  })

  it('a long dropout starts a new stretch, longest is kept', () => {
    const tm = new EarTimer(600)
    feed(tm, 0, 3000, true)
    feed(tm, 3100, 5000, false)
    const s = feed(tm, 5100, 6100, true)
    expect(s.current).toBeCloseTo(1, 5)
    expect(s.longest).toBeCloseTo(3, 5)
  })

  it('separate short touches do not add up', () => {
    const tm = new EarTimer(600)
    for (let k = 0; k < 5; k++) { feed(tm, k * 3000, k * 3000 + 1000, true); feed(tm, k * 3000 + 1100, k * 3000 + 2900, false) }
    expect(tm.snapshot(15000).longest).toBeCloseTo(1, 5)
  })

  it('a slow device (1.5 frames per second) still counts a stretch when the frame time is given', () => {
    const tm = new EarTimer(600)
    let s
    for (let t = 0; t <= 4000; t += 667) s = tm.push(t, true, 667)
    expect(s.longest).toBeGreaterThan(3)
    const plain = new EarTimer(600)
    for (let t = 0; t <= 4000; t += 667) s = plain.push(t, true)
    expect(s.longest).toBe(0)   // without the frame time every gap breaks the stretch
  })

  it('reset clears everything', () => {
    const tm = new EarTimer()
    feed(tm, 0, 5000, true)
    tm.reset()
    expect(tm.snapshot(5000)).toEqual({ current: 0, longest: 0, active: false })
  })

  it('current drops to 0 once the hand is down longer than the grace period', () => {
    const tm = new EarTimer(600)
    feed(tm, 0, 2000, true)
    const s = feed(tm, 2100, 3000, false)
    expect(s.active).toBe(false)
    expect(s.current).toBe(0)
    expect(s.longest).toBeCloseTo(2, 5)
  })
})
