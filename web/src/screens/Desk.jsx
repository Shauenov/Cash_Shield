import React, { useEffect, useState } from 'react'
import { kzt } from '../api.js'
import { tr, useLang, useT } from '../i18n.jsx'
import { CustomerSelect, Lang, PageHead, Reasons, RiskRuler, useCustomers, useFlow } from '../shared.jsx'

export default function Desk() {
  const ctl = useCustomers()
  const flow = useFlow()
  const t = useT(), { lang } = useLang()
  const [amount, setAmount] = useState(2500000)
  // the teller reads the question in the customer's language, which may differ from the interface
  const [scriptLang, setScriptLang] = useState(lang)
  useEffect(() => setScriptLang(lang), [lang])
  const [handed, setHanded] = useState(false)
  const d = flow.dec
  const busy = flow.phase !== 'form'
  const amt = (v) => ({ amount: kzt(v) })

  const go = () => { setHanded(false); setScriptLang(lang); flow.submit({ customer_id: ctl.cid, channel: 'cash_desk', type: 'cash_withdrawal', amount_kzt: Number(amount), terminal_id: 'desk_01' }) }
  const finish = () => { flow.reset(); ctl.reload() }
  const ended = ['done', 'released', 'declined', 'expired', 'nofunds'].includes(flow.phase)

  return (
    <main>
      <PageHead title={t('desk.title')} sub={t('desk.sub')} />
      <div className="desk">
        <section className="surface stack" aria-label={t('desk.request')}>
          <h2>{t('desk.request')}</h2>
          <CustomerSelect ctl={ctl} />
          <label>{t('amount')}<input type="number" step="50000" value={amount} disabled={busy} onChange={e => setAmount(e.target.value)} /></label>
          <div className="facts muted">{t('balance')} <b className="num" style={{ color: 'var(--ink)' }}>{kzt(ctl.current?.balance)}</b></div>
          <button disabled={flow.busy || busy} onClick={go}>{t('desk.check', amt(Number(amount)))}</button>
          {flow.err && <p role="alert" className="alert">{flow.err}</p>}
        </section>

        <section className="surface stack" aria-label={t('desk.decision')} aria-live="polite">
          {!d && (
            <div className="waiting">
              <h3 style={{ color: 'var(--ink)' }}>{t('desk.idle')}</h3>
              <p>{t('desk.idleHint')}</p>
            </div>
          )}
          {d && (
            <>
              {d.score != null && <RiskRuler score={d.score} decision={d.decision} />}
              {d.score != null && <Reasons reasons={d.reasons} />}
              {flow.phase === 'done' && <p className="note ok">{t('desk.ok', amt(d.amount_kzt))}</p>}
              {flow.phase === 'question' && (
                <>
                  <div className="note script">
                    <span lang={scriptLang === 'kz' ? 'kk' : scriptLang}>{tr(scriptLang, 'desk.script')}</span>
                    <Lang value={scriptLang} onChange={setScriptLang} label={t('desk.scriptLang')} />
                  </div>
                  <div className="pair">
                    <button className="secondary" onClick={() => flow.answer('yes')}>{t('desk.yes')}</button>
                    <button className="secondary" onClick={() => flow.answer('no')}>{t('desk.no')}</button>
                  </div>
                </>
              )}
              {flow.phase === 'pause' && (
                <>
                  <div className="note stop">{t('desk.stop')}</div>
                  <div className="row" style={{ alignItems: 'center' }}>
                    <button className="secondary" disabled={handed} onClick={() => setHanded(true)}>{handed ? t('desk.passed') : t('desk.pass')}</button>
                    <span className="muted">{t('desk.waiting')}</span>
                  </div>
                </>
              )}
              {flow.phase === 'released' && <p className="note ok">{t('desk.released', amt(d.amount_kzt))}</p>}
              {flow.phase === 'declined' && <p className="note stop">{t('desk.declined')}</p>}
              {flow.phase === 'expired' && <p className="note stop">{t('desk.expired')}</p>}
              {flow.phase === 'nofunds' && <p className="note stop">{t('desk.nofunds')}</p>}
              {ended && <div><button onClick={finish}>{t('desk.next')}</button></div>}
            </>
          )}
        </section>
      </div>
    </main>
  )
}
