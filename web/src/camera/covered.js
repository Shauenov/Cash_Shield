// "Camera covered" (signal S15) from the brightness of a small copy of the frame. Pure functions,
// unit-tested in covered.test.js. A hand, a finger, tape or paper on the lens gives a frame that is
// almost one colour (low spread) or almost black; an ordinary scene, even a dim room, has edges and
// shadows, so its spread stays well above the threshold.

export const COVER = {
  maxSpread: 12,     // standard deviation of luminance (0-255) below this: the frame is one flat colour
  maxDark: 18,       // mean luminance below this: the lens is blacked out
  minSec: 2,         // covered for at least this long counts as covered
  graceMs: 400,      // a short flicker does not break a covered stretch
}

/** Mean and standard deviation of luminance over RGBA pixel data (ImageData.data). */
export function frameStats(rgba) {
  const n = rgba.length / 4
  if (!n) return { mean: 0, spread: 0 }
  let sum = 0, sq = 0
  for (let i = 0; i < rgba.length; i += 4) {
    const y = 0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2]
    sum += y; sq += y * y
  }
  const mean = sum / n
  return { mean, spread: Math.sqrt(Math.max(0, sq / n - mean * mean)) }
}

/** Is this frame covered? */
export const isCovered = ({ mean, spread }, o = COVER) => spread < o.maxSpread || mean < o.maxDark
