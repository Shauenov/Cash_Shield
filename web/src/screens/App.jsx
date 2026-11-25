import React, { useEffect, useRef, useState } from 'react'
import { api, kzt } from '../api.js'
import { LANGS, LOCALE, tr, useLang, useT } from '../i18n.jsx'
import { CustomerSelect, Outcome, PageHead, PauseBlock, QuestionBlock, useCustomers, useFlow } from '../shared.jsx'

/* Mobile app: a phone of real proportions (390 x 844) with a bank app inside.
   Main lists the customer's products, Transfers runs the checked transfer, Messages is the
   bank's chat feed, Safety holds the trusted person and the "scammer on the line" button.
   The question and the pause take over the whole screen: nothing else competes with them. */

const I = {
  back: <path d="M15 5l-7 7 7 7" />,
  home: <path d="M4 11l8-6.5 8 6.5V20h-5v-5.5H9V20H4z" />,
  send: <path d="M5 12h12M13 7l5 5-5 5" />,
  chat: <path d="M5 6h14v9H10l-4 3.5V15H5z" />,
  shield: <path d="M12 3.5l7 2.6v5.6c0 4.3-2.9 7.6-7 8.8-4.1-1.2-7-4.5-7-8.8V6.1z" />,
  card: <><rect x="4" y="6.5" width="16" height="11" rx="2" /><path d="M4 10.5h16" /></>,
  loan: <><path d="M8 7h8M8 10.5h8M12 10.5V18" /></>,
  safe: <><rect x="5" y="5" width="14" height="14" rx="2" /><circle cx="12" cy="12" r="2.6" /></>,
  plus: <path d="M12 6v12M6 12h12" />,
  chev: <path d="M10 6l6 6-6 6" />,
}
const Icon = ({ n }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true">{I[n]}</svg>
)

const TABS = [['home', 'app.home', 'home'], ['transfer', 'app.transfers', 'send'],
  ['messages', 'app.messages', 'chat'], ['safety', 'app.safety', 'shield']]
const ENDED = { done: true, released: true, declined: false, expired: false, nofunds: false }

export default function App() {
  const ctl = useCustomers()
  const flow = useFlow()
  const t = useT(), { lang } = useLang()
  const [amount, setAmount] = useState(2000000)
  const [ptype, setPtype] = useState('individual')
  const [tab, setTab] = useState('home')
  // a message is kept as an i18n key (or raw error text) so it follows a language switch
  const [msg, setMsg] = useState(null)
  const [contact, setContact] = useState(() => t('app.contactDefault'))
  const [consentId, setConsentId] = useState('')
  const [trusted, setTrusted] = useState(null)
  const [feed, setFeed] = useState([])
  const sent = useRef(0)
  const cur = ctl.current

  const time = (iso) => new Date(iso).toLocaleTimeString(LOCALE[lang], { hour: '2-digit', minute: '2-digit' })
  const post = (k, v) => setFeed(f => [...f, { k, v, at: new Date().toISOString() }])

  // new customer: fresh app state, and the bank's earlier messages about this customer
  useEffect(() => {
    flow.reset(); setMsg(null); setConsentId(''); setTrusted(null); setTab('home')
    const seed = []
    if (cur?.loan_issued_at) seed.push({ k: 'm.loan', at: cur.loan_issued_at })
    if (cur?.deposit_closed_at) seed.push({ k: 'm.deposit', at: cur.deposit_closed_at })
    setFeed(seed)
  }, [ctl.cid, !!cur]) // eslint-disable-line react-hooks/exhaustive-deps

  // the default contact name follows the language until the person types their own
  useEffect(() => {
    const defaults = LANGS.map(([l]) => tr(l, 'app.contactDefault'))
    setContact(c => (defaults.includes(c) ? tr(lang, 'app.contactDefault') : c))
  }, [lang])

  // every outcome of a transfer also lands in the chat feed
  useEffect(() => {
    const v = { amount: kzt(sent.current) }
    const keys = { done: 'm.done', pause: 'm.paused', released: 'released', declined: 'declined', expired: 'expired', nofunds: 'nofunds' }
    if (keys[flow.phase]) post(keys[flow.phase], v)
  }, [flow.phase]) // eslint-disable-line react-hooks/exhaustive-deps

  const go = () => {
    sent.current = Number(amount)
    flow.submit({ customer_id: ctl.cid, channel: 'app', type: 'transfer', amount_kzt: Number(amount), payee_id: 'p_new', payee_type: ptype, payee_known: false })
  }
  const finish = () => { flow.reset(); ctl.reload(); setTab('home') }
  const act = async (fn, ok) => {
    try { const r = await fn(); const m = typeof ok === 'function' ? ok(r) : { k: ok }; setMsg(m); post(m.k, m) }
    catch (e) { setMsg({ raw: e.message }) }
  }
  const msgText = (m) => {
    if (!m) return ''
    if (m.raw) return m.raw
    if (m.time) return t(m.k, { time: new Date(m.time).toLocaleString(LOCALE[lang]) })
    return t(m.k, m.v)
  }

  const reported = cur?.report_at && Date.now() - new Date(cur.report_at) < 24 * 3600e3
  const takeover = ['question', 'pause'].includes(flow.phase) || flow.phase in ENDED

  const banner = reported
    ? { on: true, title: t('app.bannerOn'), sub: t('app.bannerOnSub') }
    : trusted
      ? { on: true, title: t('app.bannerTrusted', { name: trusted }), sub: t('app.bannerTrustedSub') }
      : { on: false, title: t('app.bannerSet'), sub: t('app.bannerSetSub'), to: 'safety' }

  return (
    <main>
      <PageHead title={t('app.title')} sub={t('app.sub')} />
      <div className="bench">
        <aside className="scenario" aria-label={t('scenario.aria')}>
          <h2>{t('scenario')}</h2>
          <p>{t('scenario.note')}</p>
          <CustomerSelect ctl={ctl} />
          <div className="facts">
            <div><span className="muted">{t('app.recipient')}</span><span>{t('app.recipientV')}</span></div>
          </div>
        </aside>

        <div className="device" role="region" aria-label={t('app.name')}>
          <div className="device-screen">
            <div className="status-bar" aria-hidden="true">
              <span>9:41</span><span className="island" /><span className="status-icons"><i /><i /><i /><b /></span>
            </div>

            {takeover ? (
              <div className="app-sheet">
                {flow.phase === 'question' && <QuestionBlock flow={flow} />}
                {flow.phase === 'pause' && (
                  <PauseBlock dec={flow.dec} extra={<button onClick={() => setMsg({ k: 'app.calling' })}>{t('callBank')}</button>} />
                )}
                {flow.phase in ENDED && (
                  <Outcome ok={ENDED[flow.phase]} action={t('app.back')} onAction={finish}
                    text={t({ done: 'doneTransfer' }[flow.phase] || flow.phase)} />
                )}
                {msg && flow.phase === 'pause' && <p role="status" className="note">{msgText(msg)}</p>}
              </div>
            ) : (
              <>
                <header className="app-bar">
                  {tab !== 'home'
                    ? <button className="app-back" aria-label={t('app.back')} onClick={() => { setTab('home'); setMsg(null) }}><Icon n="back" /></button>
                    : <span aria-hidden="true" />}
                  <span className="app-title"><span className="app-mark"><Icon n="shield" /></span>{tab === 'home' ? t('app.name') : t(TABS.find(x => x[0] === tab)[1])}</span>
                  <span aria-hidden="true" />
                </header>

                <div className="app-scroll">
                  {tab === 'home' && (
                    <>
                      <button className={`app-banner ${banner.on ? 'on' : ''}`} onClick={() => banner.to && setTab(banner.to)}
                        disabled={!banner.to}>
                        <span className="banner-ico"><Icon n="shield" /></span>
                        <span><b>{banner.title}</b><small>{banner.sub}</small></span>
                        {banner.to && <span className="chev"><Icon n="chev" /></span>}
                      </button>

                      <section className="app-group">
                        <div className="prod">
                          <span className="tile acct"><Icon n="card" /></span>
                          <span className="prod-name">{t('app.account')}<small>*4417</small></span>
                          <b className="prod-sum">{kzt(cur?.balance)}</b>
                        </div>
                        <button className="prod add" onClick={() => setTab('transfer')}>
                          <span className="tile ghost"><Icon n="plus" /></span>
                          <span className="prod-name link">{t('app.newTransfer')}</span>
                        </button>
                      </section>

                      {(cur?.loan_issued_at || cur?.deposit_closed_at) && (
                        <section className="app-group">
                          {cur.loan_issued_at && (
                            <div className="prod">
                              <span className="tile loan"><Icon n="loan" /></span>
                              <span className="prod-name">{t('app.loan')}<small>{t('app.loanSub', { time: time(cur.loan_issued_at) })}</small></span>
                            </div>
                          )}
                          {cur.deposit_closed_at && (
                            <div className="prod">
                              <span className="tile dep"><Icon n="safe" /></span>
                              <span className="prod-name">{t('app.deposit')}<small>{t('app.depositSub', { time: time(cur.deposit_closed_at) })}</small></span>
                              <b className="prod-sum muted">{kzt(0)}</b>
                            </div>
                          )}
                        </section>
                      )}
                    </>
                  )}

                  {tab === 'transfer' && (
                    <section className="app-group pad stack">
                      <label className="amount-field">{t('amount')}
                        <input type="number" step="50000" value={amount} onChange={e => setAmount(e.target.value)} />
                      </label>
                      <fieldset className="choice">
                        <legend>{t('app.rtype')}</legend>
                        {[['individual', 'app.private'], ['legal', 'app.company']].map(([v, l]) => (
                          <label key={v} className={ptype === v ? 'on' : ''}>
                            <input type="radio" name="ptype" value={v} checked={ptype === v} onChange={() => setPtype(v)} />{t(l)}
                          </label>
                        ))}
                      </fieldset>
                      <p className="muted small">{t('app.recipient')}: {t('app.recipientV')}</p>
                      <button disabled={flow.busy} onClick={go}>{t('app.transfer', { amount: kzt(Number(amount)) })}</button>
                      {flow.err && <p role="alert" className="alert">{flow.err}</p>}
                    </section>
                  )}

                  {tab === 'messages' && (
                    <div className="chat" aria-live="polite">
                      {feed.length === 0 && <p className="muted small chat-empty">{t('app.noMessages')}</p>}
                      {feed.length > 0 && <span className="chat-day">{t('app.today')}</span>}
                      {feed.map((m, i) => (
                        <div key={i} className="bubble">
                          <span className="bubble-ava"><Icon n="shield" /></span>
                          <p>{msgText(m)}<time>{time(m.at)}</time></p>
                        </div>
                      ))}
                    </div>
                  )}

                  {tab === 'safety' && (
                    <>
                      <section className="app-group pad stack">
                        <h3>{t('app.trusted')}</h3>
                        <p className="muted small">{t('app.trustedNote')}</p>
                        <label>{t('app.contactName')}<input type="text" value={contact} onChange={e => setContact(e.target.value)} /></label>
                        <button onClick={() => act(() => api.consent(ctl.cid, contact).then(r => { setConsentId(r.consent_id); setTrusted(contact); return r }), 'app.saved')}>{t('app.agree')}</button>
                        <button className="secondary" disabled={!consentId} onClick={() => act(() => api.revoke(consentId), r => ({ k: 'app.revoked', time: r.revoke_effective_at }))}>{t('app.revoke')}</button>
                      </section>
                      <section className="app-group pad stack">
                        <h3>{t('app.scamTitle')}</h3>
                        <p className="muted small">{t('app.scamNote')}</p>
                        <button className="danger" onClick={() => act(() => api.report(ctl.cid).then(r => { ctl.reload(); return r }), 'app.scamOn')}>{t('app.scamBtn')}</button>
                      </section>
                      {msg && <p role="status" className="note app-note">{msgText(msg)}</p>}
                    </>
                  )}
                </div>

                <nav className="tabbar" aria-label={t('app.name')}>
                  {TABS.map(([k, l, ic]) => (
                    <button key={k} className={tab === k ? 'on' : ''} aria-current={tab === k ? 'page' : undefined}
                      onClick={() => { setTab(k); setMsg(null) }}>
                      <Icon n={ic} /><span>{t(l)}</span>
                    </button>
                  ))}
                </nav>
              </>
            )}
            <span className="home-ind" aria-hidden="true" />
          </div>
        </div>
      </div>
    </main>
  )
}
