import React, { useState } from 'react'
import { kzt } from '../api.js'
import { Balance, CustomerSelect, PageTitle, Pill, Reasons, useCustomers, useFlow } from '../shared.jsx'

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
  const ended = ['done', 'released', 'declined', 'expired', 'nofunds'].includes(flow.phase)

  return (
    <main>
      <PageTitle accent="Cash desk" rest="teller screen"
        sub="Large sums go through the cash desk. The same engine gives the teller the reasons and the words to say." />
      {flow.phase === 'form' && (
        <div className="card">
          <h2>Cash payout</h2>
          <p className="card-sub">Customer at the counter asks for cash.</p>
          <div className="row">
            <CustomerSelect ctl={ctl} />
            <label>Amount, ₸<input type="number" step="50000" value={amount} onChange={e => setAmount(e.target.value)} /></label>
            <button disabled={flow.busy} onClick={go}>Pay out {kzt(Number(amount))}</button>
          </div>
          <p style={{ marginTop: 16 }}><Balance value={ctl.current?.balance} /></p>
          {flow.err && <p role="alert" className="alert">{flow.err}</p>}
        </div>
      )}
      {flow.phase !== 'form' && d && (
        <div className="card">
          {d.score != null && <><h2>Risk score {d.score} <Pill d={d.decision} /></h2>
            <Reasons reasons={d.reasons} /></>}
          {flow.phase === 'done' && <p className="ok-note">✔ Payout completed: {kzt(d.amount_kzt)}.</p>}
          {flow.phase === 'question' && (
            <>
              <div className="hint">
                {SCRIPT[lang]}
                <span style={{ marginLeft: 12 }}><button className="small secondary" onClick={() => setLang(lang === 'en' ? 'kz' : 'en')}>EN / KZ</button></span>
              </div>
              <div className="pair">
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
          {flow.phase === 'released' && <p className="ok-note">✔ Officer released the operation. Pay out {kzt(d.amount_kzt)}.</p>}
          {flow.phase === 'declined' && <p className="hint">✖ Officer confirmed fraud. Operation cancelled.</p>}
          {flow.phase === 'expired' && <p className="hint">The pause ended without an officer decision. Operation cancelled; nothing was paid out.</p>}
          {flow.phase === 'nofunds' && <p className="hint">✖ Not enough money in the account. Nothing was paid out.</p>}
          {ended && <p style={{ marginTop: 18 }}><button onClick={finish}>Next customer</button></p>}
        </div>
      )}
    </main>
  )
}
