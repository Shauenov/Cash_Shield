// "Phone at the ear" from MediaPipe Pose landmarks. Pure functions, no browser APIs, so they are
// unit-tested (phoneAtEar.test.js). What is detected is the posture "a hand is held at the ear",
// not the phone itself: a headset or a phone on speaker is not seen (see docs/camera.md).

// MediaPipe Pose landmark indices
export const LM = {
  L_EAR: 7, R_EAR: 8, L_SHOULDER: 11, R_SHOULDER: 12,
  L_WRIST: 15, R_WRIST: 16, L_PINKY: 17, R_PINKY: 18, L_INDEX: 19, R_INDEX: 20, L_THUMB: 21, R_THUMB: 22,
}
const SIDES = [
  { side: 'left', ear: LM.L_EAR, hand: [LM.L_WRIST, LM.L_PINKY, LM.L_INDEX, LM.L_THUMB] },
  { side: 'right', ear: LM.R_EAR, hand: [LM.R_WRIST, LM.R_PINKY, LM.R_INDEX, LM.R_THUMB] },
]

export const DEFAULTS = {
  minVisibility: 0.5,   // ignore landmarks the model is not sure about
  minEarVisibility: 0.2, // a hand with a phone covers the ear, so its visibility drops; the predicted position is still usable
  maxEarDist: 0.45,     // hand-to-ear distance, as a share of shoulder width
  graceMs: 600,         // a gap shorter than this does not break a continuous stretch
  minShoulderPx: 20,    // a body smaller than this is too far away to judge
}

const seen = (p, o) => p && (p.visibility ?? 1) >= o.minVisibility
const dist = (a, b, w, h) => Math.hypot((a.x - b.x) * w, (a.y - b.y) * h)

/**
 * One frame: is a hand held at the ear on the same side?
 * landmarks: normalized landmarks of one person (x, y in 0..1). width/height: frame size in pixels,
 * so distances are not distorted by the aspect ratio.
 * Returns { known, atEar, side, ratio }: known=false when the shoulders are not visible.
 */
export function handAtEar(landmarks, width, height, opts = {}) {
  const o = { ...DEFAULTS, ...opts }
  const ls = landmarks?.[LM.L_SHOULDER], rs = landmarks?.[LM.R_SHOULDER]
  if (!seen(ls, o) || !seen(rs, o)) return { known: false, atEar: false, side: null, ratio: null }
  const shoulder = dist(ls, rs, width, height)
  if (shoulder < o.minShoulderPx) return { known: false, atEar: false, side: null, ratio: null }

  let best = { side: null, ratio: Infinity }
  for (const s of SIDES) {
    const ear = landmarks[s.ear]
    if (!ear || (ear.visibility ?? 1) < o.minEarVisibility) continue
    for (const i of s.hand) {
      const p = landmarks[i]
      if (!seen(p, o)) continue
      const r = dist(p, ear, width, height) / shoulder
      if (r < best.ratio) best = { side: s.side, ratio: r }
    }
  }
  const ratio = Number.isFinite(best.ratio) ? best.ratio : null
  const atEar = ratio != null && ratio <= o.maxEarDist
  return { known: true, atEar, side: atEar ? best.side : null, ratio }
}

/**
 * Accumulates continuous "phone at ear" time from per-frame results.
 * current: the running stretch in seconds; longest: the longest stretch since reset().
 * The longest stretch is what goes to the engine (phone_at_ear_sec).
 */
export class EarTimer {
  constructor(graceMs = DEFAULTS.graceMs) { this.graceMs = graceMs; this.reset() }

  reset() { this.start = null; this.lastSeen = null; this.longestMs = 0; this.grace = this.graceMs }

  /**
   * t: frame time in ms; atEar: result of handAtEar for that frame.
   * frameMs (optional): the usual time between processed frames. On a slow device (a few frames per
   * second) the allowed gap grows to 2.5 frames, so a slow frame rate does not break every stretch.
   */
  push(t, atEar, frameMs = 0) {
    this.grace = Math.max(this.graceMs, 2.5 * frameMs)
    if (atEar) {
      if (this.start == null || t - this.lastSeen > this.grace) this.start = t
      this.lastSeen = t
      this.longestMs = Math.max(this.longestMs, t - this.start)
    } else if (this.start != null && t - this.lastSeen > this.grace) {
      this.start = null
    }
    return this.snapshot(t)
  }

  snapshot(t) {
    const running = this.start != null && t - this.lastSeen <= this.grace
    return {
      current: running ? (this.lastSeen - this.start) / 1000 : 0,
      longest: this.longestMs / 1000,
      active: running,
    }
  }
}
