import React, { useState } from 'react'
import { kzt } from '../api.js'
import { CustomerSelect, Pill, Reasons, useCustomers, useFlow } from '../shared.jsx'

const SCRIPT = {
  en: 'Ask: "Has anyone asked you to withdraw this money and not tell anyone?"',
  kz: 'Сұраңыз: «Сізден біреу осы ақшаны шешіп, ешкімге айтпауды сұрады ма?»',
}

export default function Desk() {
  const ctl = useCustomers()
  const flow = useFlow()
  const [amount, setAmount] = useState(2500000)
  const [lang, setLang] = useState('en')
  const [handed, setHanded] = useState(false)
  const d = flow.dec

  const go = () => { setHanded(false); flow.submit({ customer_id: ctl.cid, channel: 'cash_desk', type: 'cash_withdrawal', amount_kzt: Number(amount), terminal_id: 'desk_01' }) }
  const finish = () => { flow.reset(); ctl.reload() }

  return (
    <main>
      <h1>Cash desk: teller screen</h1>
      {flow.phase === 'form' && (
        <div className="card">
          <div className="row">
            <CustomerSelect ctl={ctl} />
            <label>Amount, ₸<input type="number" step="50000" value={amount} onChange={e => setAmount(e.target.value)} /></label>
            <button disabled={flow.busy} onClick={go}>Pay out {kzt(Number(amount))}</button>
          </div>
          <p className="muted">Balance: {kzt(ctl.current?.balance)}</p>
          {flow.err && <p role="alert" style={{ color: 'var(--bad)' }}>{flow.err}</p>}
        </div>
      )}
      {flow.phase !== 'form' && d && (
        <div className="card">
          <h2>Risk score {d.score} <Pill d={d.decision} /></h2>
          <Reasons reasons={d.reasons} />
          {flow.phase === 'done' && <p>✔ Payout completed: {kzt(d.amount_kzt)}.</p>}
          {flow.phase === 'question' && (
            <>
              <div className="hint">
                {SCRIPT[lang]}
                <span style={{ marginLeft: 12 }}><button className="small secondary" onClick={() => setLang(lang === 'en' ? 'kz' : 'en')}>EN / KZ</button></span>
              </div>
              <div className="row" style={{ marginTop: 14 }}>
                <button className="secondary" onClick={() => flow.answer('yes')}>Customer: yes, they asked me</button>
                <button className="secondary" onClick={() => flow.answer('no')}>Customer: no, own decision</button>
              </div>
            </>
          )}
          {flow.phase === 'pause' && (
            <>
              <div className="hint">Do not pay out. Say: "We need a short check. The bank will call you through the app."</div>
              <p><button className="secondary" disabled={handed} onClick={() => setHanded(true)}>{handed ? 'Passed to officer ✔' : 'Pass to officer'}</button></p>
              <p className="muted">Waiting for the officer's decision…</p>
            </>
          )}
          {flow.phase === 'released' && <p>✔ Officer released the operation. Pay out {kzt(d.amount_kzt)}.</p>}
          {flow.phase === 'declined' && <p>✖ Officer confirmed fraud. Operation cancelled.</p>}
          {['done', 'released', 'declined'].includes(flow.phase) && <button onClick={finish}>Next customer</button>}
        </div>
      )}
    </main>
  )
}
