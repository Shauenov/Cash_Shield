import React from 'react'
import { useT } from '../i18n.jsx'
import { COVER } from './covered.js'

// engine/rules.yaml params.phone_at_ear_min_sec: S10 fires above this many seconds
export const PHONE_MIN_SEC = 3
const fmt = (s) => (Math.round(s * 10) / 10).toFixed(1)

/** Webcam preview with ear and hand points, and the "phone at ear" timer. Bank-side demo view. */
export default function CameraPanel({ cam }) {
  const t = useT()
  const { status, error, pose, time, source, cover } = cam
  const covered = status === 'running' && cover.now
  const pct = Math.min(100, (time.current / PHONE_MIN_SEC) * 100)
  const over = time.longest > PHONE_MIN_SEC
  return (
    <div className="cam">
      {/* data-* attributes: for checking the detector from dev tools (hand-to-ear distance in shoulder widths) */}
      <div className={`cam-view ${(pose.atEar || covered) && status === 'running' ? 'hit' : ''}`}
        data-known={pose.known} data-at-ear={pose.atEar} data-side={pose.side ?? ''} data-ratio={pose.ratio == null ? '' : pose.ratio.toFixed(2)}
        data-current={time.current.toFixed(1)} data-longest={time.longest.toFixed(1)}
        data-covered={cover.now} data-covered-longest={cover.longest.toFixed(1)}>
        <video ref={cam.videoRef} muted playsInline aria-hidden="true" />
        <canvas ref={cam.canvasRef} aria-hidden="true" />
        {status !== 'running' && status !== 'error' && <div className="cam-veil">{t(status === 'loading' ? 'cam.loading' : 'cam.starting')}</div>}
        {status === 'error' && <div className="cam-veil err">{t(`cam.err.${error}`)}</div>}
        {covered && <div className="cam-veil err">{t('cam.covered')}</div>}
      </div>
      {status === 'running' && (
        <div className="cam-stat" aria-live="polite">
          <div className="cam-state">
            <span className={`dot ${pose.atEar ? 'hit' : ''}`} />
            {covered ? t('cam.covered') : !pose.known ? t('cam.noBody') : pose.atEar ? t('cam.atEar') : t('cam.noEar')}
          </div>
          <div className="cam-meter" role="meter" aria-valuemin={0} aria-valuemax={PHONE_MIN_SEC} aria-valuenow={Math.min(time.current, PHONE_MIN_SEC)}
            aria-label={t('cam.current', { s: fmt(time.current) })}>
            <span style={{ width: `${pct}%` }} className={time.current > PHONE_MIN_SEC ? 'over' : ''} />
          </div>
          <div className="cam-nums">
            <span>{t('cam.current', { s: fmt(time.current) })}</span>
            <span className={over ? 'over' : ''}>{t('cam.longest', { s: fmt(time.longest), min: PHONE_MIN_SEC })}</span>
          </div>
          {cover.longest > 0 && (
            <div className={`cam-nums ${cover.longest >= COVER.minSec ? 'cover-hit' : ''}`}>
              <span>{t('cam.coveredFor', { s: fmt(cover.longest), min: COVER.minSec })}</span>
            </div>
          )}
        </div>
      )}
      <p className="cam-note">{t('cam.privacy')}{source === 'remote' ? ` ${t('cam.remote')}` : ''}</p>
    </div>
  )
}
