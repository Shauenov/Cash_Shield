import React, { useState } from 'react'
import { T, kzt } from '../api.js'
import { CustomerSelect, Lang, PauseBlock, QuestionBlock, useCustomers, useFlow } from '../shared.jsx'

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
  const cls = { form: '', question: 'ask', pause: 'pause', done: 'ok', released: 'ok', declined: 'pause' }[flow.phase]

  return (
    <main>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>ATM</h1><Lang lang={lang} setLang={setLang} />
      </div>
      <div className={`screen atm ${cls}`}>
        {flow.phase === 'form' && (
          <>
            <h1>Cash withdrawal</h1>
            <p className="muted" style={{ fontSize: 18 }}>Balance: {kzt(ctl.current?.balance)}</p>
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
            <p><button disabled={flow.busy} onClick={go}>Withdraw {kzt(Number(amount))}</button></p>
            {flow.err && <p role="alert" style={{ color: 'var(--bad)' }}>{flow.err}</p>}
          </>
        )}
        {flow.phase === 'question' && <QuestionBlock lang={lang} flow={flow} />}
        {flow.phase === 'pause' && (
          <PauseBlock lang={lang} dec={flow.dec} extra={<p className="muted" style={{ fontSize: 18 }}>{t.wait}</p>} />
        )}
        {flow.phase === 'done' && <><h1>✔ {t.done}</h1><p>{kzt(flow.dec?.amount_kzt || Number(amount))}</p><button onClick={finish}>New operation</button></>}
        {flow.phase === 'released' && <><h1>✔ {t.released}</h1><button onClick={finish}>New operation</button></>}
        {flow.phase === 'declined' && <><h1>{t.declined}</h1><button onClick={finish}>New operation</button></>}
      </div>
    </main>
  )
}
