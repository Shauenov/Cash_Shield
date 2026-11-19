import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, T, kzt } from './api.js'

export function useCustomers() {
  const [list, setList] = useState([])
  const [cid, setCid] = useState('c_gulnar')
  const reload = useCallback(() => api.customers().then(setList).catch(() => {}), [])
  useEffect(() => { reload() }, [reload])
  return { list, cid, setCid, reload, current: list.find(c => c.customer_id === cid) }
}

export function CustomerSelect({ ctl }) {
  return (
    <label>Customer
      <select value={ctl.cid} onChange={e => ctl.setCid(e.target.value)}>
        {ctl.list.map(c => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
      </select>
    </label>
  )
}

export function Lang({ lang, setLang }) {
  return (
    <span className="lang" role="group" aria-label="Language">
      <button className={lang === 'en' ? 'on' : ''} onClick={() => setLang('en')}>EN</button>
      <button className={lang === 'kz' ? 'on' : ''} onClick={() => setLang('kz')}>KZ</button>
      <button className={lang === 'ru' ? 'on' : ''} onClick={() => setLang('ru')}>RU</button>
    </span>
  )
}

export const Pill = ({ d }) => <span className={`pill ${['allow', 'ask', 'pause', 'hold'].includes(d) ? d : 'other'}`}>{d}</span>

export function Reasons({ reasons }) {
  if (!reasons?.length) return <p className="muted">No risk signals.</p>
  return (
    <ul className="reasons">
      {reasons.map(r => <li key={r.signal}><b>{r.signal}</b> {r.contribution > 0 ? '+' : ''}{r.contribution}: {r.text_en || r.text_ru}</li>)}
    </ul>
  )
}

export function Countdown({ until }) {
  const [left, setLeft] = useState(0)
  useEffect(() => {
    if (!until) return
    const f = () => setLeft(Math.max(0, Math.round((new Date(until) - Date.now()) / 1000)))
    f(); const t = setInterval(f, 1000); return () => clearInterval(t)
  }, [until])
  if (!until) return null
  const m = String(Math.floor(left / 60)).padStart(2, '0'), s = String(left % 60).padStart(2, '0')
  return <div className="timer" aria-live="off">{m}:{s}</div>
}

/** Operation flow shared by ATM, cash desk and app. */
export function useFlow() {
  const [phase, setPhase] = useState('form')   // form | question | pause | done | released | declined
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
        if (d.status === 'approved') { stopPoll(); setPhase('released') }
        if (d.status === 'declined') { stopPoll(); setPhase('declined') }
      } catch { /* keep polling */ }
    }, 1500)
  }
  const apply = (r, prev) => {
    const d = { ...prev, ...r }
    setDec(d)
    if (r.result === 'approve') setPhase('done')
    else if (r.result === 'ask') setPhase('question')
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

export function QuestionBlock({ lang, flow }) {
  const t = T[lang]
  return (
    <>
      <h1>{t.question}</h1>
      <div className="pair">
        {/* two equal buttons so the screen does not push the customer toward one answer */}
        <button className="secondary" disabled={flow.busy} onClick={() => flow.answer('yes')}>{t.yes}</button>
        <button className="secondary" disabled={flow.busy} onClick={() => flow.answer('no')}>{t.no}</button>
      </div>
    </>
  )
}

export function PauseBlock({ lang, dec, extra }) {
  const t = T[lang]
  return (
    <>
      <h1>⏸ {t.pause1}</h1>
      <Countdown until={dec?.pause_until} />
      <p>{t.pause2}</p>
      <p>{t.pause3}</p>
      {extra}
    </>
  )
}

export { kzt }
