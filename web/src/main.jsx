import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import Atm from './screens/Atm.jsx'
import Desk from './screens/Desk.jsx'
import App from './screens/App.jsx'
import Officer from './screens/Officer.jsx'

const I = {
  logo: <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 5 7v8.5C5 22.4 9.7 27.6 16 29c6.3-1.4 11-6.6 11-13.5V7L16 3Z" fill="var(--brand)" /><path d="m11 16 3.5 3.5L21.5 12" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>,
  atm: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><rect x="5" y="4" width="22" height="24" rx="3" /><rect x="9" y="8" width="14" height="8" rx="1.5" /><path d="M10 22h12M13 26v-4M19 26v-4" /></svg>,
  desk: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><circle cx="16" cy="9" r="4" /><path d="M8 20c1.5-3.5 4.4-5 8-5s6.5 1.5 8 5" /><path d="M4 20h24v8H4z" /></svg>,
  app: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><rect x="9" y="3" width="14" height="26" rx="3" /><path d="M14 25h4" /><path d="m12.5 14 2.5 2.5 4.5-4.5" /></svg>,
  officer: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><rect x="3" y="5" width="26" height="17" rx="2.5" /><path d="M12 27h8M16 22v5" /><path d="M8 17l4-4 3 3 6-6" /></svg>,
  glasses: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true"><circle cx="9" cy="19" r="5" /><circle cx="23" cy="19" r="5" /><path d="M14 18.5c1.3-1 2.7-1 4 0M4 19l2-9M28 19l-2-9" /></svg>,
}

// [hash, label, hint, icon, side]
const ROUTES = [
  ['atm', 'ATM', 'Customer screen', 'atm', 'customer', Atm],
  ['desk', 'Cash desk', 'Teller screen', 'desk', 'customer', Desk],
  ['app', 'Mobile app', 'Transfers, consent, alert', 'app', 'customer', App],
  ['officer', 'Officer console', 'Pauses, decisions, log', 'officer', 'bank', Officer],
]

// Per-viewer accessibility settings: kept in this browser only, the page works without them.
const store = {
  get: (k, d) => { try { return localStorage.getItem(k) || d } catch { return d } },
  set: (k, v) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } },
}

function A11yBar({ font, setFont, theme, setTheme, close }) {
  return (
    <section className="panel a11y" aria-label="Accessibility settings">
      <div className="grp"><span>Font size</span>
        <div className="opts">
          {['1', '2', '3'].map((f, i) => (
            <button key={f} className="opt" aria-pressed={font === f} onClick={() => setFont(f)}
              style={{ fontSize: `${0.85 + i * 0.2}rem` }} aria-label={`Font size ${i + 1}`}>A</button>
          ))}
        </div>
      </div>
      <div className="grp"><span>Site colour</span>
        <div className="opts">
          {[['light', 'Light'], ['dark', 'Dark'], ['contrast', 'High contrast']].map(([k, l]) => (
            <button key={k} className={`opt t-${k}`} aria-pressed={theme === k} onClick={() => setTheme(k)} aria-label={l} title={l}>Ц</button>
          ))}
        </div>
      </div>
      <button className="opt normal" onClick={() => { setFont('1'); setTheme('light'); close() }}>Normal version</button>
    </section>
  )
}

function Shell() {
  const [hash, setHash] = useState(location.hash.slice(1) || 'atm')
  const [a11y, setA11y] = useState(false)
  const [font, setFont] = useState(() => store.get('cs-font', '1'))
  const [theme, setTheme] = useState(() => store.get('cs-theme', 'light'))
  useEffect(() => {
    const f = () => { setHash(location.hash.slice(1) || 'atm'); scrollTo({ top: 0 }) }
    addEventListener('hashchange', f)
    return () => removeEventListener('hashchange', f)
  }, [])
  useEffect(() => { document.documentElement.dataset.font = font; store.set('cs-font', font) }, [font])
  useEffect(() => { document.documentElement.dataset.theme = theme; store.set('cs-theme', theme) }, [theme])

  const route = ROUTES.find(r => r[0] === hash) || ROUTES[0]
  const Screen = route[5]
  const side = route[4]
  return (
    <>
      <div className="wrap">
        {a11y && <A11yBar font={font} setFont={setFont} theme={theme} setTheme={setTheme} close={() => setA11y(false)} />}
        <header className="panel hdr">
          <div className="hdr-top">
            <a className="logo" href="#atm">{I.logo}cash shield</a>
            <span className="demo-note">Demo with synthetic data</span>
            <div className="hdr-actions">
              <nav className="seg" aria-label="Side">
                <a href="#atm" className={side === 'customer' ? 'on' : ''}>Customer side</a>
                <a href="#officer" className={side === 'bank' ? 'on' : ''}>Bank side</a>
              </nav>
              <button className="icon-btn" aria-pressed={a11y} aria-label="Accessibility settings" title="Accessibility settings"
                onClick={() => setA11y(!a11y)}>{I.glasses}</button>
            </div>
          </div>
          <nav className="tiles" aria-label="Screens">
            {ROUTES.map(([k, label, hint, icon]) => (
              <a key={k} href={`#${k}`} className={`tile ${hash === k ? 'on' : ''}`} aria-current={hash === k ? 'page' : undefined}>
                <span className="ico">{I[icon]}</span>
                <span>{label}<small>{hint}</small></span>
              </a>
            ))}
          </nav>
        </header>
      </div>
      <Screen />
    </>
  )
}

createRoot(document.getElementById('root')).render(<Shell />)
