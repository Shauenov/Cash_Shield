import React, { useCallback, useEffect, useState } from 'react'
import { api, kzt } from '../api.js'
import { useT } from '../i18n.jsx'
import { PageHead, Pill, Reasons, RiskRuler, useCustomerName } from '../shared.jsx'

export default function Officer() {
  const [events, setEvents] = useState([])
  const [held, setHeld] = useState([])
  const [comment, setComment] = useState({})
  const [err, setErr] = useState('')
  const [down, setDown] = useState(false)
  const t = useT(), name = useCustomerName()

  const load = useCallback(async () => {
    try { setEvents(await api.events()); setHeld(await api.held()) } catch (e) { setErr(e.message) }
  }, [])

  useEffect(() => {
    load()
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/api/v1/events/stream`)
    ws.onmessage = () => load()
    const keep = setInterval(() => ws.readyState === 1 && ws.send('ping'), 20000)
    const poll = setInterval(load, 4000)   // fallback if the socket drops
    return () => { ws.close(); clearInterval(keep); clearInterval(poll) }
  }, [load])

  const decide = async (d, action) => {
    const text = (comment[d.decision_id] || '').trim()
    if (text.length < 3) { setErr(t('off.needComment')); return }
    setErr('')
    try { await api.override(d.decision_id, action, text); await load() } catch (e) { setErr(e.message) }
  }
  const count = (k) => events.filter(e => e.kind === k).length
  const dec = events.filter(e => e.kind === 'decision')
  const falseAlarms = events.filter(e => e.kind === 'override' && e.comment.startsWith('release')).length
  const waiting = held.filter(h => h.status === 'held')

  const ch = (c) => (c ? t(`ch.${c}`) : '')
  const kind = (k) => { const v = t(`ev.${k}`); return v === `ev.${k}` ? k : v }
  const actor = (a = '') => (a.startsWith('officer:') ? t('actor.officer', { id: a.slice(8) }) : ['engine', 'customer', 'host'].includes(a) ? t(`actor.${a}`) : a)

  return (
    <main>
      <PageHead title={t('off.title')} sub={t('off.sub')}
        actions={<>
          <button className={`small secondary ${down ? 'on-state' : ''}`} aria-pressed={down} onClick={async () => { await api.engineDown(!down); setDown(!down) }}>{down ? t('off.restore') : t('off.outage')}</button>
          <button className="small secondary" onClick={async () => { await api.skipTime(24); load() }}>{t('off.skip')}</button>
          <button className="small secondary" onClick={async () => { await api.reset(); setDown(false); load() }}>{t('off.reset')}</button>
        </>} />

      <div className="stats">
        <div className="stat"><b>{dec.length}</b>{t('off.sDecisions')}</div>
        <div className="stat"><b>{dec.filter(e => e.decision === 'ask').length}</b>{t('off.sQuestions')}</div>
        <div className="stat accent"><b>{dec.filter(e => ['pause', 'hold'].includes(e.decision)).length}</b>{t('off.sPauses')}</div>
        <div className="stat"><b>{falseAlarms}</b>{t('off.sReleased')}</div>
        <div className="stat"><b>{count('notify_sent')}</b>{t('off.sNotified')}</div>
      </div>
      {err && <p role="alert" className="alert">{err}</p>}

      <div className="section-h"><h2>{t('off.waiting')}</h2><span className="count">{waiting.length}</span></div>
      {waiting.length === 0 && <div className="surface empty">{t('off.none')}</div>}
      {waiting.map(d => (
        <section key={d.decision_id} className={`surface held ${d.decision}`} aria-label={t('off.opAria', { name: name(d.customer_id) })}>
          <div className="who">
            <span className="amount">{kzt(d.amount)}</span>
            <dl>
              <dt>{t('customer')}</dt><dd>{name(d.customer_id)}</dd>
              <dt>{t('channel')}</dt><dd>{ch(d.channel)}</dd>
            </dl>
          </div>
          <div className="stack">
            <RiskRuler score={d.score} decision={d.decision} />
            <Reasons reasons={d.reasons} />
          </div>
          <div className="act">
            <label>{t('off.comment')}
              <input type="text" value={comment[d.decision_id] || ''} onChange={e => setComment({ ...comment, [d.decision_id]: e.target.value })} placeholder={t('off.placeholder')} />
            </label>
            <button onClick={() => decide(d, 'release')}>{t('off.release')}</button>
            <button className="danger" onClick={() => decide(d, 'confirm_fraud')}>{t('off.fraud')}</button>
          </div>
        </section>
      ))}

      <div className="section-h"><h2>{t('off.log')}</h2><span className="count live">{t('off.live')}</span></div>
      <div className="surface table-wrap">
        {events.length === 0 ? <div className="empty">{t('off.noEvents')}</div> : (
          <table>
            <thead><tr><th>{t('th.time')}</th><th>{t('th.event')}</th><th>{t('customer')}</th><th>{t('channel')}</th><th>{t('th.score')}</th><th>{t('th.decision')}</th><th>{t('th.actor')}</th><th>{t('th.why')}</th></tr></thead>
            <tbody>
              {events.map(e => (
                <tr key={e.event_id}>
                  <td className="t">{e.ts?.slice(11, 19)}</td><td className="kind">{kind(e.kind)}</td><td>{e.customer_id ? name(e.customer_id) : ''}</td><td>{ch(e.channel)}</td>
                  <td className="num">{e.score ?? ''}</td><td>{e.decision ? <Pill d={e.decision} /> : ''}</td><td>{actor(e.actor)}</td>
                  <td>{e.reasons?.length ? e.reasons.map(r => r.signal).join(' ') + ' ' : ''}{e.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  )
}
