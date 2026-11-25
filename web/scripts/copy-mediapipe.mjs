// Copies the MediaPipe WASM runtime from node_modules to public/, so the camera detector works
// without internet. The pose model (pose_landmarker_lite.task) is optional in public/mediapipe/:
// without it the page loads the model from Google's storage (see src/camera/useCamera.js).
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const web = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(web, 'node_modules', '@mediapipe', 'tasks-vision', 'wasm')
const dst = join(web, 'public', 'mediapipe', 'wasm')
if (!existsSync(src)) { console.error('copy-mediapipe: run npm install first'); process.exit(1) }
mkdirSync(dst, { recursive: true })
// only the classic (non-module) runtime is used: FilesetResolver.forVisionTasks(base) loads these two
for (const f of ['vision_wasm_internal.js', 'vision_wasm_internal.wasm']) copyFileSync(join(src, f), join(dst, f))
console.log('copy-mediapipe: WASM runtime copied to public/mediapipe/wasm')
