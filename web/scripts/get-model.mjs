// Downloads the MediaPipe pose model (pose_landmarker_lite.task, about 5-6 MB, Apache 2.0, Google)
// into public/mediapipe/, so the camera detector works without internet on the demo laptop.
// Run once: npm run get-model. Without it the page loads the same file from Google's storage.
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'
const dst = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'mediapipe', 'pose_landmarker_lite.task')

const r = await fetch(URL)
if (!r.ok) { console.error(`get-model: ${r.status} ${r.statusText}`); process.exit(1) }
const buf = Buffer.from(await r.arrayBuffer())
mkdirSync(dirname(dst), { recursive: true })
writeFileSync(dst, buf)
console.log(`get-model: ${(buf.length / 1e6).toFixed(1)} MB saved to public/mediapipe/pose_landmarker_lite.task`)
