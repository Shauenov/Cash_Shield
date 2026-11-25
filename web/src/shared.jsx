import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, kzt } from './api.js'
import { LANGS, reasonText, useLang, useT } from './i18n.jsx'

export function useCustomers() {
  const [list, setList] = useState([])
  const [cid, setCid] = useState('c_gulnar')
  const reload = useCallback(() => api.customers().then(setList).catch(() => {}), [])
  useEffect(() => {
    // the API may still be starting when the screen opens: retry until the customers arrive
    let stop = false, timer
    const tryLoad = () => api.customers().then(l => { if (!stop) setList(l) })
      .catch(() => { if (!stop) timer = setTimeout(tryLoad, 2000) })
    tryLoad()
    return () => { stop = true; clearTimeout(timer) }
  }, [])
  return { list, cid, setCid, reload, current: list.find(c => c.customer_id === cid) }
}

/** Demo customer name in the current language; unknown ids fall back to the name from the API. */
export function useCustomerName() {
  const t = useT()
  return (id, fallback) => { const k = `c.${id}`, v = t(k); return v === k ? (fallback || id) : v }
}

export function CustomerSelect({ ctl }) {
  const t = useT(), name = useCustomerName()
  return (
    <label>{t('customer')}
      <select value={ctl.cid} onChange={e => ctl.setCid(e.target.value)}>
        {ctl.list.map(c => <option key={c.customer_id} value={c.customer_id}>{name(c.customer_id, c.name)}</option>)}
      </select>
    </label>
  )
}

/** Language switch. Without props it changes the language of the whole interface. */
export function Lang({ value, onChange, label }) {
  const g = useLang(), t = useT()
  const cur = value ?? g.lang, set = onChange ?? g.setLang
  return (
    <span className="lang" role="group" aria-label={label || t('language')}>
      {LANGS.map(([k, l]) => <button key={k} className={cur === k ? 'on' : ''} aria-pressed={cur === k} onClick={() => set(k)}>{l}</button>)}
    </span>
  )
}

/** Left-aligned page heading with optional actions on the right. */
export function PageHead({ title, sub, actions }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  )
}

export const Balance = ({ value }) => { const t = useT(); return <span className="balance"><span className="muted">{t('balance')}</span><b>{kzt(value)}</b></span> }

const KNOWN = ['allow', 'ask', 'pause', 'hold']
export const Pill = ({ d }) => { const t = useT(); const k = KNOWN.includes(d); return <span className={`pill ${k ? d : 'other'}`}>{k ? t(`d.${d}`) : d}</span> }

export function Reasons({ reasons }) {
  const t = useT(), { lang } = useLang()
  if (!reasons?.length) return <p className="muted">{t('noSignals')}</p>
  return (
    <ul className="reasons">
      {reasons.map(r => (
        <li key={r.signal}><span className="sig">{r.signal}</span>
          <span className="pts">{r.contribution > 0 ? '+' : ''}{r.contribution}</span>
          <span>{reasonText(r, lang)}</span></li>
      ))}
    </ul>
  )
}

// Decision bands of the frozen v1 rules (engine/rules.yaml). The demo runs on v1.
export const BANDS = [['allow', 0, 40], ['ask', 40, 55], ['pause', 55, 85], ['hold', 85, 100]]

/** Score on the 0-100 scale with the four decision bands; the band the score falls in is solid. */
export function RiskRuler({ score, decision }) {
  const s = Math.max(0, Math.min(100, score ?? 0))
  const t = useT()
  const hit = BANDS.find(([, lo, hi]) => s >= lo && (s < hi || hi === 100))?.[0]
  return (
    <div className="ruler">
      <div className="ruler-head">
        <span className="score">{score}</span>
        <span className="of">{t('scoreOf')}</span>
        {decision && <Pill d={decision} />}
      </div>
      <div className="ruler-track" role="img" aria-label={t('scoreAria', { score })}>
        {BANDS.map(([k, lo, hi]) => <span key={k} className={`band ${k} ${k === hit ? 'hit' : ''}`} style={{ width: `${hi - lo}%` }} />)}
        <span className="ruler-marker" style={{ left: `${s}%` }} />
      </div>
      <div className="ruler-scale" aria-hidden="true">
        {[0, 40, 55, 85, 100].map(v => <span key={v} style={{ left: `${v}%` }}>{v}</span>)}
      </div>
    </div>
  )
}

const ICON = {
  ok: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>,
  stop: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true"><path d="M12 7v6M12 17h.01" /></svg>,
}
/** Final customer-facing state: a mark, one sentence, an optional detail and the next action. */
export function Outcome({ ok, text, children, action, onAction }) {
  return (
    <div className={`outcome ${ok ? 'ok' : 'stop'}`}>
      <span className="mark">{ICON[ok ? 'ok' : 'stop']}</span>
      <span className="big">{text}</span>
      {children}
      {action && <button onClick={onAction}>{action}</button>}
    </div>
  )
}

/** Counts down from the seconds the server reported. The browser clock is only used to tick:
 *  the server's clock may be shifted by the demo "skip time" button. */
export function Countdown({ seconds }) {
  const [left, setLeft] = useState(0)
  useEffect(() => {
    if (seconds == null) return
    const end = Date.now() + seconds * 1000
    const f = () => setLeft(Math.max(0, Math.round((end - Date.now()) / 1000)))
    f(); const t = setInterval(f, 1000); return () => clearInterval(t)
  }, [seconds])
  if (seconds == null) return null
  const m = String(Math.floor(left / 60)).padStart(2, '0'), s = String(left % 60).padStart(2, '0')
  return <div className="timer" aria-live="off">{m}:{s}</div>
}

/** Operation flow shared by ATM, cash desk and app. */
export function useFlow() {
  const [phase, setPhase] = useState('form')   // form | question | pause | done | released | declined | expired | nofunds
  const [dec, setDec] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const poll = useRef(null)

  const stopPoll = () => { clearInterval(poll.current); poll.current = null }
  useEffect(() => stopPoll, [])

  const startPoll = (id) => {
    stopPoll()
    poll.current = setInterval(async () => {
      try {
        const d = await api.decision(id)
        // resync the timer with the server (it moves when the demo skips time)
        setDec(prev => (prev && prev.pause_seconds_left !== d.pause_seconds_left ? { ...prev, pause_seconds_left: d.pause_seconds_left } : prev))
        if (d.status === 'approved') { stopPoll(); setPhase('released') }
        if (d.status === 'declined') { stopPoll(); setPhase('declined') }
        if (d.status === 'expired') { stopPoll(); setPhase('expired') }
      } catch { /* keep polling */ }
    }, 1500)
  }
  const apply = (r, prev) => {
    const d = { ...prev, ...r }
    setDec(d)
    if (r.result === 'approve') setPhase('done')
    else if (r.result === 'ask') setPhase('question')
    else if (r.result === 'decline') setPhase('nofunds')
    else { setPhase('pause'); startPoll(d.decision_id) }
  }
  const submit = async (body) => {
    setErr(''); setBusy(true)
    try { apply(await api.authorize(body), {}) } catch (e) { setErr(e.message) }
    setBusy(false)
  }
  const answer = async (a) => {
    setBusy(true)
    try { apply(await api.answer(dec.decision_id, a), dec) } catch (e) { setErr(e.message) }
    setBusy(false)
  }
  const reset = () => { stopPoll(); setPhase('form'); setDec(null); setErr('') }
  return { phase, dec, err, busy, submit, answer, reset }
}

export function QuestionBlock({ flow }) {
  const t = useT()
  return (
    <>
      <h1>{t('question')}</h1>
      <div className="pair">
        {/* two equal buttons so the screen does not push the customer toward one answer */}
        <button className="secondary" disabled={flow.busy} onClick={() => flow.answer('yes')}>{t('yes')}</button>
        <button className="secondary" disabled={flow.busy} onClick={() => flow.answer('no')}>{t('no')}</button>
      </div>
    </>
  )
}

export function PauseBlock({ dec, extra }) {
  const t = useT()
  return (
    <>
      <h1>{t('pause1')}</h1>
      <Countdown seconds={dec?.pause_seconds_left} />
      <p>{t('pause2')}</p>
      <p>{t('pause3')}</p>
      {extra}
    </>
  )
}

export { kzt }
