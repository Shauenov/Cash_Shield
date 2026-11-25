import { useCallback, useEffect, useRef, useState } from 'react'
import { COVER, frameStats, isCovered } from './covered.js'
import { EarTimer, handAtEar, LM } from './phoneAtEar.js'

// Everything runs in this browser tab: frames never leave the device and are not stored.
// Only the number of seconds goes to the API, as extra.phone_at_ear_sec of the next operation.

const WASM_BASE = '/mediapipe/wasm'
const LOCAL_MODEL = '/mediapipe/pose_landmarker_lite.task'
const REMOTE_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'
const UI_HZ = 10   // React state updates per second; detection itself runs every video frame
const COVER_MS = 250   // how often the frame brightness is checked for a covered lens

let landmarkerPromise = null   // one model per page, kept across screen changes

async function modelPath() {
  // the dev server and nginx answer unknown paths with index.html, so check the content type
  try {
    const r = await fetch(LOCAL_MODEL, { method: 'HEAD' })
    if (r.ok && !(r.headers.get('content-type') || '').includes('text/html')) return { path: LOCAL_MODEL, source: 'local' }
  } catch { /* fall through */ }
  return { path: REMOTE_MODEL, source: 'remote' }
}

function loadLandmarker() {
  landmarkerPromise ??= (async () => {
    const { FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision')
    const files = await FilesetResolver.forVisionTasks(WASM_BASE)
    const { path, source } = await modelPath()
    const make = (delegate) => PoseLandmarker.createFromOptions(files, {
      baseOptions: { modelAssetPath: path, delegate }, runningMode: 'VIDEO', numPoses: 1,
    })
    let lm
    try { lm = await make('GPU') } catch { lm = await make('CPU') }
    return { lm, source }
  })().catch(e => { landmarkerPromise = null; throw e })
  return landmarkerPromise
}

function errorCode(e) {
  if (!window.isSecureContext) return 'insecure'
  if (e?.name === 'NotAllowedError' || e?.name === 'SecurityError') return 'denied'
  if (e?.name === 'NotFoundError' || e?.name === 'OverconstrainedError') return 'nocamera'
  if (e?.name === 'NotReadableError') return 'busy'
  if (e?.stage === 'model') return 'model'
  return 'other'
}

const KEYPOINTS = [LM.L_EAR, LM.R_EAR, LM.L_SHOULDER, LM.R_SHOULDER, LM.L_WRIST, LM.R_WRIST, LM.L_INDEX, LM.R_INDEX, LM.L_THUMB, LM.R_THUMB]

function draw(canvas, video, landmarks, pose) {
  if (!canvas) return
  const w = video.videoWidth, h = video.videoHeight
  if (canvas.width !== w) canvas.width = w
  if (canvas.height !== h) canvas.height = h
  const g = canvas.getContext('2d')
  g.clearRect(0, 0, w, h)
  if (!landmarks) return
  const css = getComputedStyle(canvas)
  const hit = css.getPropertyValue('--pause').trim() || '#b9442a'
  const dot = css.getPropertyValue('--brand').trim() || '#0f5b54'
  for (const i of KEYPOINTS) {
    const p = landmarks[i]
    if (!p || (p.visibility ?? 1) < 0.5) continue
    const isEar = i === LM.L_EAR || i === LM.R_EAR
    g.beginPath()
    g.arc(p.x * w, p.y * h, isEar ? 9 : 6, 0, Math.PI * 2)
    g.fillStyle = pose.atEar && isEar ? hit : dot
    g.strokeStyle = '#fff'
    g.lineWidth = 2
    g.fill(); g.stroke()
  }
}

/**
 * Live "phone at ear" detection from the webcam.
 * enabled: start or stop the camera. Returns refs for <video> and <canvas>, the status, the latest
 * frame result, the timer ({ current, longest, active }) and reset() for a new operation.
 */
export function useCamera(enabled) {
  const videoRef = useRef(null), canvasRef = useRef(null)
  const timer = useRef(new EarTimer())
  const coverTimer = useRef(new EarTimer(COVER.graceMs))
  const [status, setStatus] = useState('off')   // off | starting | loading | running | error
  const [error, setError] = useState(null)
  const [source, setSource] = useState(null)    // local | remote model file
  const [pose, setPose] = useState({ known: false, atEar: false, side: null, ratio: null })
  const [time, setTime] = useState({ current: 0, longest: 0, active: false })
  // covered lens: now = covered at the moment, longest = longest covered stretch in this operation (s)
  const [cover, setCover] = useState({ now: false, longest: 0 })

  const reset = useCallback(() => {
    timer.current.reset(); coverTimer.current.reset()
    setTime({ current: 0, longest: 0, active: false })
    setCover({ now: false, longest: 0 })
  }, [])

  useEffect(() => {
    if (!enabled) { setStatus('off'); setError(null); return }
    let stream = null, raf = 0, stopped = false, lastVideoTime = -1, lastUi = 0, lastCover = 0
    // usual time between processed frames and between cover checks (moving averages, ms)
    let lastFrame = 0, frameMs = 0, coverMs = 0
    timer.current.reset(); coverTimer.current.reset()
    const small = document.createElement('canvas'); small.width = 32; small.height = 24
    const sg = small.getContext('2d', { willReadFrequently: true })

    ;(async () => {
      try {
        setStatus('starting'); setError(null)
        if (!navigator.mediaDevices?.getUserMedia) throw Object.assign(new Error('no getUserMedia'), { name: 'NotFoundError' })
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }, audio: false })
        if (stopped) return
        const video = videoRef.current
        video.srcObject = stream
        await video.play()
        setStatus('loading')
        let model
        try { model = await loadLandmarker() } catch (e) { e.stage = 'model'; throw e }
        if (stopped) return
        setSource(model.source)
        setStatus('running')

        const loop = () => {
          if (stopped) return
          raf = requestAnimationFrame(loop)
          if (video.readyState < 2 || video.currentTime === lastVideoTime) return
          lastVideoTime = video.currentTime
          const now = performance.now()
          if (lastFrame) frameMs = frameMs ? 0.9 * frameMs + 0.1 * (now - lastFrame) : now - lastFrame
          lastFrame = now
          let res
          try { res = model.lm.detectForVideo(video, now) } catch (e) {
            // e.g. a GPU that accepted the model but fails on frames: stop and say so instead of failing every frame
            stopped = true; cancelAnimationFrame(raf)
            console.warn('camera detector:', e); setError('other'); setStatus('error'); return
          }
          if (now - lastCover >= COVER_MS) {
            if (lastCover) coverMs = coverMs ? 0.8 * coverMs + 0.2 * (now - lastCover) : now - lastCover
            lastCover = now
            sg.drawImage(video, 0, 0, small.width, small.height)
            const c = coverTimer.current.push(now, isCovered(frameStats(sg.getImageData(0, 0, small.width, small.height).data)), coverMs)
            setCover(prev => (prev.now === c.active && prev.longest === c.longest ? prev : { now: c.active, longest: c.longest }))
          }
          const landmarks = res.landmarks?.[0]
          const p = handAtEar(landmarks, video.videoWidth, video.videoHeight)
          const t = timer.current.push(now, p.atEar, frameMs)
          draw(canvasRef.current, video, landmarks, p)
          if (now - lastUi > 1000 / UI_HZ) { lastUi = now; setPose(p); setTime(t) }
        }
        loop()
      } catch (e) {
        if (stopped) return
        console.warn('camera detector:', e)
        setError(errorCode(e)); setStatus('error')
      }
    })()

    return () => {
      stopped = true
      cancelAnimationFrame(raf)
      stream?.getTracks().forEach(t => t.stop())
      if (videoRef.current) videoRef.current.srcObject = null
    }
  }, [enabled])

  return { videoRef, canvasRef, status, error, source, pose, time, cover, reset }
}
