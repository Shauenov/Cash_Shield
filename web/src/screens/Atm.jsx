import React, { useState } from 'react'
import { T, kzt } from '../api.js'
import { Balance, CustomerSelect, Lang, PageTitle, PauseBlock, QuestionBlock, useCustomers, useFlow } from '../shared.jsx'

export default function Atm() {
  const ctl = useCustomers()
  const flow = useFlow()
  const [lang, setLang] = useState('en')
  const [amount, setAmount] = useState(500000)
  const [atm, setAtm] = useState('atm_017')
  const [camera, setCamera] = useState(false)
  const t = T[lang]

  const go = () => flow.submit({
    customer_id: ctl.cid, channel: 'atm', type: 'cash_withdrawal', amount_kzt: Number(amount),
    terminal_id: atm, extra: camera ? { phone_at_ear_sec: 8 } : {},
  })
  const finish = () => { flow.reset(); ctl.reload() }
  const cls = { form: '', question: 'ask', pause: 'pause', done: 'ok', released: 'ok', declined: 'pause', expired: 'pause', nofunds: 'pause' }[flow.phase]
  const done = (text, extra) => (
    <div className="result"><span className="big">{text}</span>{extra}<button onClick={finish}>New operation</button></div>
  )

  return (
    <main>
      <PageTitle accent="ATM" rest="cash withdrawal"
        sub="What the customer sees. The bank's authorization host asks Cash Shield before the cash comes out." />
      <div className={`screen atm ${cls}`}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <Balance value={ctl.current?.balance} />
          <Lang lang={lang} setLang={setLang} />
        </div>
        {flow.phase === 'form' && (
          <>
            <h1>Cash withdrawal</h1>
            <div className="row">
              <CustomerSelect ctl={ctl} />
              <label>Amount, ₸ (ATM limit about 500 000)
                <input type="number" step="10000" value={amount} onChange={e => setAmount(e.target.value)} />
              </label>
              <label>ATM
                <select value={atm} onChange={e => setAtm(e.target.value)}>
                  <option value="atm_017">ATM 017</option><option value="atm_042">ATM 042</option>
                </select>
              </label>
              <label>Camera signal (optional)
                <select value={camera ? 'on' : 'off'} onChange={e => setCamera(e.target.value === 'on')}>
                  <option value="off">Off / no phone seen</option><option value="on">Phone at ear 8 s</option>
                </select>
              </label>
            </div>
            <p style={{ marginTop: 24 }}><button disabled={flow.busy} onClick={go}>Withdraw {kzt(Number(amount))}</button></p>
            {flow.err && <p role="alert" className="alert">{flow.err}</p>}
          </>
        )}
        {flow.phase === 'question' && <QuestionBlock lang={lang} flow={flow} />}
        {flow.phase === 'pause' && <PauseBlock lang={lang} dec={flow.dec} extra={<p className="muted">{t.wait}</p>} />}
        {flow.phase === 'done' && done(`✔ ${t.done}`, <span className="balance"><b>{kzt(flow.dec?.amount_kzt || Number(amount))}</b></span>)}
        {flow.phase === 'released' && done(`✔ ${t.released}`)}
        {flow.phase === 'declined' && done(t.declined)}
        {flow.phase === 'expired' && done(t.expired)}
        {flow.phase === 'nofunds' && done(t.nofunds)}
      </div>
    </main>
  )
}
