import React, { useCallback, useEffect, useState } from 'react'
import { api, kzt } from '../api.js'
import { PageTitle, Pill, Reasons } from '../shared.jsx'

export default function Officer() {
  const [events, setEvents] = useState([])
  const [held, setHeld] = useState([])
  const [comment, setComment] = useState({})
  const [err, setErr] = useState('')
  const [down, setDown] = useState(false)

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
    if (text.length < 3) { setErr('A comment is required (min 3 characters).'); return }
    setErr('')
    try { await api.override(d.decision_id, action, text); await load() } catch (e) { setErr(e.message) }
  }
  const count = (k) => events.filter(e => e.kind === k).length
  const dec = events.filter(e => e.kind === 'decision')
  const falseAlarms = events.filter(e => e.kind === 'override' && e.comment.startsWith('release')).length
  const waiting = held.filter(h => h.status === 'held')

  return (
    <main>
      <PageTitle accent="Officer" rest="console"
        sub="Every pause lands here with its reasons. An officer releases a false alarm or confirms fraud, always with a comment." />
      <div className="toolbar">
        <button className="small secondary" onClick={async () => { await api.engineDown(!down); setDown(!down) }}>{down ? 'Engine: DOWN (click to restore)' : 'Simulate engine outage'}</button>
        <button className="small secondary" onClick={async () => { await api.skipTime(24); load() }}>Demo: skip time +24 h</button>
        <button className="small secondary" onClick={async () => { await api.reset(); setDown(false); load() }}>Reset demo</button>
      </div>

      <div className="stats">
        <div className="stat"><b>{dec.length}</b>decisions</div>
        <div className="stat"><b>{dec.filter(e => e.decision === 'ask').length}</b>questions</div>
        <div className="stat accent"><b>{dec.filter(e => ['pause', 'hold'].includes(e.decision)).length}</b>pauses</div>
        <div className="stat"><b>{falseAlarms}</b>false alarms released</div>
        <div className="stat"><b>{count('notify_sent')}</b>trusted persons notified</div>
      </div>
      {err && <p role="alert" className="alert">{err}</p>}

      <div className="section-h"><h2>On hold</h2><span className="count">{waiting.length}</span></div>
      {waiting.length === 0 && <div className="card empty">Nothing waiting.</div>}
      {waiting.map(d => (
        <div key={d.decision_id} className="card held-card">
          <h2>{d.customer_id} · {d.channel} · {kzt(d.amount)} <span className="muted">score {d.score}</span> <Pill d={d.decision} /></h2>
          <Reasons reasons={d.reasons} />
          <div className="row" style={{ marginTop: 16 }}>
            <label style={{ flex: 1, minWidth: 260 }}>Comment (required)
              <input type="text" value={comment[d.decision_id] || ''} onChange={e => setComment({ ...comment, [d.decision_id]: e.target.value })} placeholder="e.g. called customer, bought a car" />
            </label>
            <button onClick={() => decide(d, 'release')}>Release pause</button>
            <button className="danger" onClick={() => decide(d, 'confirm_fraud')}>Confirm fraud</button>
          </div>
        </div>
      ))}

      <div className="section-h"><h2>Event log</h2><span className="muted">live</span></div>
      <div className="card table-card">
        {events.length === 0 ? <div className="empty">No events yet. Make an operation on the ATM, cash desk or app screen.</div> : (
          <table>
            <thead><tr><th>Time</th><th>Event</th><th>Customer</th><th>Channel</th><th>Score</th><th>Decision</th><th>Actor</th><th>Why / comment</th></tr></thead>
            <tbody>
              {events.map(e => (
                <tr key={e.event_id}>
                  <td>{e.ts?.slice(11, 19)}</td><td><b>{e.kind}</b></td><td>{e.customer_id}</td><td>{e.channel}</td>
                  <td>{e.score ?? ''}</td><td>{e.decision ? <Pill d={e.decision} /> : ''}</td><td>{e.actor}</td>
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
