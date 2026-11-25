import React, { useState } from 'react'
import { kzt } from '../api.js'
import { useT } from '../i18n.jsx'
import CameraPanel from '../camera/CameraPanel.jsx'
import { useCamera } from '../camera/useCamera.js'
import { COVER } from '../camera/covered.js'
import { Balance, CustomerSelect, Lang, Outcome, PageHead, PauseBlock, QuestionBlock, useCustomers, useFlow } from '../shared.jsx'

const QUICK = [100000, 300000, 500000]

export default function Atm() {
  const ctl = useCustomers()
  const flow = useFlow()
  const [amount, setAmount] = useState(500000)
  const [atm, setAtm] = useState('atm_017')
  // camera signal: off | sim (phone at ear 8 s) | simCover (lens covered) | live (webcam detector, see camera/)
  const [camMode, setCamMode] = useState('off')
  const cam = useCamera(camMode === 'live')
  const [sent, setSent] = useState(null)   // camera fields sent with the last operation
  const t = useT()

  const cameraExtra = () => {
    if (camMode === 'sim') return { phone_at_ear_sec: 8 }
    if (camMode === 'simCover') return { camera_blocked: true }
    if (camMode === 'live' && cam.status === 'running') {
      const x = { phone_at_ear_sec: Math.round(cam.time.longest * 10) / 10 }
      if (cam.cover.longest >= COVER.minSec) x.camera_blocked = true
      return x
    }
    return {}
  }

  const go = () => {
    const extra = cameraExtra()
    setSent(Object.keys(extra).length ? extra : null)
    flow.submit({ customer_id: ctl.cid, channel: 'atm', type: 'cash_withdrawal', amount_kzt: Number(amount), terminal_id: atm, extra })
  }
  // a new operation measures the phone time again
  const finish = () => { flow.reset(); ctl.reload(); cam.reset(); setSent(null) }
  const cls = { form: '', question: 'ask', pause: 'pause', done: 'ok', released: 'ok', declined: 'pause', expired: 'pause', nofunds: 'pause' }[flow.phase]
  const end = (ok, text, extra) => <Outcome ok={ok} text={text} action={t('atm.new')} onAction={finish}>{extra}</Outcome>

  return (
    <main>
      <PageHead title={t('atm.title')} sub={t('atm.sub')} />
      <div className="bench">
        <aside className="scenario" aria-label={t('scenario.aria')}>
          <h2>{t('scenario')}</h2>
          <p>{t('scenario.note')}</p>
          <CustomerSelect ctl={ctl} />
          <label>{t('atm.atm')}
            <select value={atm} onChange={e => setAtm(e.target.value)}>
              <option value="atm_017">{t('atm.n', { n: '017' })}</option><option value="atm_042">{t('atm.n', { n: '042' })}</option>
            </select>
          </label>
          <label>{t('atm.camera')}
            <select value={camMode} onChange={e => { setCamMode(e.target.value); cam.reset() }}>
              <option value="off">{t('atm.camOff')}</option>
              <option value="sim">{t('atm.camOn')}</option>
              <option value="simCover">{t('atm.camCover')}</option>
              <option value="live">{t('atm.camLive')}</option>
            </select>
          </label>
          {camMode === 'live' && <CameraPanel cam={cam} />}
          {sent?.phone_at_ear_sec != null && <p className="cam-sent">{t('cam.sent', { s: sent.phone_at_ear_sec })}</p>}
          {sent?.camera_blocked && <p className="cam-sent">{t('cam.sentCover')}</p>}
          <div className="facts">
            <div><span className="muted">{t('balance')}</span><b>{kzt(ctl.current?.balance)}</b></div>
            <div><span className="muted">{t('atm.limit')}</span><span>{t('atm.limitV')}</span></div>
          </div>
        </aside>

        <div className="atm-device">
          <div className={`atm-screen ${cls}`}>
            <div className="atm-top">
              <Balance value={ctl.current?.balance} />
              {camMode === 'live' && cam.status === 'running' && <span className="cam-on">{t('cam.indicator')}</span>}
              <Lang />
            </div>
            {flow.phase === 'form' && (
              <>
                <h1>{t('atm.how')}</h1>
                <div className="quick" role="group" aria-label={t('atm.quick')}>
                  {QUICK.map(v => (
                    <button key={v} className="secondary" aria-pressed={Number(amount) === v} onClick={() => setAmount(v)}>{kzt(v)}</button>
                  ))}
                </div>
                <label className="amount-field">{t('atm.other')}
                  <input type="number" step="10000" value={amount} onChange={e => setAmount(e.target.value)} />
                </label>
                <button disabled={flow.busy} onClick={go}>{t('atm.withdraw', { amount: kzt(Number(amount)) })}</button>
                {flow.err && <p role="alert" className="alert">{flow.err}</p>}
              </>
            )}
            {flow.phase === 'question' && <QuestionBlock flow={flow} />}
            {flow.phase === 'pause' && <PauseBlock dec={flow.dec} extra={<p className="muted">{t('wait')}</p>} />}
            {flow.phase === 'done' && end(true, t('done'), <span className="balance"><b>{kzt(flow.dec?.amount_kzt || Number(amount))}</b></span>)}
            {flow.phase === 'released' && end(true, t('released'))}
            {flow.phase === 'declined' && end(false, t('declined'))}
            {flow.phase === 'expired' && end(false, t('expired'))}
            {flow.phase === 'nofunds' && end(false, t('nofunds'))}
          </div>
          <div className="slot" aria-hidden="true" />
        </div>
      </div>
    </main>
  )
}
