import React, { useState } from 'react'
import { api, T, kzt } from '../api.js'
import { Balance, CustomerSelect, Lang, PageTitle, PauseBlock, QuestionBlock, useCustomers, useFlow } from '../shared.jsx'

export default function App() {
  const ctl = useCustomers()
  const flow = useFlow()
  const [lang, setLang] = useState('en')
  const [amount, setAmount] = useState(2000000)
  const [ptype, setPtype] = useState('individual')
  const [tab, setTab] = useState('transfer')
  const [msg, setMsg] = useState('')
  const [contact, setContact] = useState('Daughter Aliya')
  const [consentId, setConsentId] = useState('')
  const t = T[lang]

  const go = () => flow.submit({ customer_id: ctl.cid, channel: 'app', type: 'transfer', amount_kzt: Number(amount), payee_id: 'p_new', payee_type: ptype, payee_known: false })
  const finish = () => { flow.reset(); ctl.reload() }
  const act = async (fn, ok) => { try { const r = await fn(); setMsg(typeof ok === 'function' ? ok(r) : ok) } catch (e) { setMsg(e.message) } }

  return (
    <main>
      <PageTitle accent="Mobile" rest="app"
        sub="Transfers get the same check. The customer can name a trusted person and press “Scammer on the line”." />
      <div className="phone">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <CustomerSelect ctl={ctl} /><Lang lang={lang} setLang={setLang} />
        </div>
        <p><Balance value={ctl.current?.balance} /></p>
        <div className="tabs" role="tablist">
          {[['transfer', 'Transfer'], ['trusted', 'Trusted person'], ['alert', 'Scammer']].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => { setTab(k); setMsg('') }}>{l}</button>
          ))}
        </div>

        {tab === 'transfer' && (
          <div style={{ marginTop: 14 }}>
            {flow.phase === 'form' && (
              <>
                <label>Amount, ₸<input type="number" step="50000" value={amount} onChange={e => setAmount(e.target.value)} /></label>
                <label style={{ marginTop: 8 }}>New recipient
                  <select value={ptype} onChange={e => setPtype(e.target.value)}>
                    <option value="individual">Private person</option><option value="legal">Company</option>
                  </select>
                </label>
                <button disabled={flow.busy} onClick={go}>Transfer {kzt(Number(amount))}</button>
                {flow.err && <p role="alert" className="alert">{flow.err}</p>}
              </>
            )}
            {flow.phase === 'question' && <QuestionBlock lang={lang} flow={flow} />}
            {flow.phase === 'pause' && (
              <PauseBlock lang={lang} dec={flow.dec} extra={<button onClick={() => setMsg('Calling the bank through the app… (simulated)')}>{t.callBank}</button>} />
            )}
            {flow.phase === 'done' && <><h2>✔ {t.doneTransfer}</h2><button onClick={finish}>Back</button></>}
            {flow.phase === 'released' && <><h2>✔ {t.released}</h2><button onClick={finish}>Back</button></>}
            {flow.phase === 'declined' && <><h2>{t.declined}</h2><button onClick={finish}>Back</button></>}
            {flow.phase === 'expired' && <><h2>{t.expired}</h2><button onClick={finish}>Back</button></>}
            {flow.phase === 'nofunds' && <><h2>{t.nofunds}</h2><button onClick={finish}>Back</button></>}
          </div>
        )}

        {tab === 'trusted' && (
          <div style={{ marginTop: 14 }}>
            <h2>Trusted person</h2>
            <p className="muted">If the bank pauses my unusual operation, tell this person. Amount and details are not shared. Off by default.</p>
            <label>Name<input type="text" value={contact} onChange={e => setContact(e.target.value)} /></label>
            <button onClick={() => act(() => api.consent(ctl.cid, contact).then(r => { setConsentId(r.consent_id); return r }), 'Consent saved.')}>I agree, notify this person</button>
            <button className="secondary" disabled={!consentId} onClick={() => act(() => api.revoke(consentId), r => `Withdrawal takes effect at ${new Date(r.revoke_effective_at).toLocaleString()} (24 h delay protects you from a scammer on the phone).`)}>Withdraw consent</button>
          </div>
        )}

        {tab === 'alert' && (
          <div style={{ marginTop: 14 }}>
            <h2>A scammer is on the line</h2>
            <p className="muted">Press this, hang up, and we raise protection on your account for 24 hours.</p>
            <button className="danger" onClick={() => act(() => api.report(ctl.cid), 'Protection is on for 24 hours.')}>Scammer on the line</button>
          </div>
        )}
        {msg && <p role="status" className="hint">{msg}</p>}
      </div>
    </main>
  )
}
