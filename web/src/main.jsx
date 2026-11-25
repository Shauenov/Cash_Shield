import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/unbounded/400.css'
import '@fontsource/unbounded/500.css'
import '@fontsource/unbounded/600.css'
import '@fontsource/golos-text/400.css'
import '@fontsource/golos-text/500.css'
import '@fontsource/golos-text/600.css'
import '@fontsource/golos-text/700.css'
import './style.css'
import Atm from './screens/Atm.jsx'
import Desk from './screens/Desk.jsx'
import App from './screens/App.jsx'
import Officer from './screens/Officer.jsx'
import { HTML_LANG, LangCtx, useT } from './i18n.jsx'
import { Lang } from './shared.jsx'

const I = {
  logo: <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 5 7v8.5C5 22.4 9.7 27.6 16 29c6.3-1.4 11-6.6 11-13.5V7L16 3Z" fill="var(--brand)" /><path d="m11 16 3.5 3.5L21.5 12" fill="none" stroke="var(--brand-ink)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>,
  atm: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><rect x="5" y="4" width="22" height="24" rx="3" /><rect x="9" y="8" width="14" height="8" rx="1.5" /><path d="M10 22h12M13 26v-4M19 26v-4" /></svg>,
  desk: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><circle cx="16" cy="9" r="4" /><path d="M8 20c1.5-3.5 4.4-5 8-5s6.5 1.5 8 5" /><path d="M4 20h24v8H4z" /></svg>,
  app: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><rect x="9" y="3" width="14" height="26" rx="3" /><path d="M14 25h4" /><path d="m12.5 14 2.5 2.5 4.5-4.5" /></svg>,
  officer: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><rect x="3" y="5" width="26" height="17" rx="2.5" /><path d="M12 27h8M16 22v5" /><path d="M8 17l4-4 3 3 6-6" /></svg>,
  glasses: <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true"><circle cx="9" cy="19" r="5" /><circle cx="23" cy="19" r="5" /><path d="M14 18.5c1.3-1 2.7-1 4 0M4 19l2-9M28 19l-2-9" /></svg>,
}

// [hash, icon, side, screen]; labels come from i18n (route.<hash>)
const ROUTES = [
  ['atm', 'atm', 'customer', Atm],
  ['desk', 'desk', 'customer', Desk],
  ['app', 'app', 'customer', App],
  ['officer', 'officer', 'bank', Officer],
]

// Per-viewer settings (language, text size, colours): kept in this browser only, the page works without them.
const store = {
  get: (k, d) => { try { return localStorage.getItem(k) || d } catch { return d } },
  set: (k, v) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } },
}

function A11yBar({ font, setFont, theme, setTheme, close }) {
  const t = useT()
  return (
    <section className="a11y" aria-label={t('a11y')}>
      <div className="topbar-in">
        <div className="grp"><span>{t('a11y.size')}</span>
          <div className="opts">
            {['1', '2', '3'].map((f, i) => (
              <button key={f} className="opt" aria-pressed={font === f} onClick={() => setFont(f)}
                style={{ fontSize: `${0.85 + i * 0.2}rem` }} aria-label={t('a11y.sizeN', { n: i + 1 })}>A</button>
            ))}
          </div>
        </div>
        <div className="grp"><span>{t('a11y.colours')}</span>
          <div className="opts">
            {['light', 'dark', 'contrast'].map(k => (
              <button key={k} className={`opt t-${k}`} aria-pressed={theme === k} onClick={() => setTheme(k)} aria-label={t(`a11y.${k}`)} title={t(`a11y.${k}`)}>Aa</button>
            ))}
          </div>
        </div>
        <button className="secondary small normal" onClick={() => { setFont('1'); setTheme('light'); close() }}>{t('a11y.back')}</button>
      </div>
    </section>
  )
}

function Shell() {
  const [hash, setHash] = useState(location.hash.slice(1) || 'atm')
  const [a11y, setA11y] = useState(false)
  const [font, setFont] = useState(() => store.get('cs-font', '1'))
  const [theme, setTheme] = useState(() => store.get('cs-theme', 'light'))
  const [lang, setLang] = useState(() => store.get('cs-lang', 'en'))
  useEffect(() => {
    const f = () => { setHash(location.hash.slice(1) || 'atm'); scrollTo({ top: 0 }) }
    addEventListener('hashchange', f)
    return () => removeEventListener('hashchange', f)
  }, [])
  useEffect(() => { document.documentElement.dataset.font = font; store.set('cs-font', font) }, [font])
  useEffect(() => { document.documentElement.dataset.theme = theme; store.set('cs-theme', theme) }, [theme])
  useEffect(() => { document.documentElement.lang = HTML_LANG[lang] || 'en'; store.set('cs-lang', lang) }, [lang])

  return (
    <LangCtx.Provider value={{ lang, setLang }}>
      <Page hash={hash} a11y={a11y} setA11y={setA11y} font={font} setFont={setFont} theme={theme} setTheme={setTheme} />
    </LangCtx.Provider>
  )
}

function Page({ hash, a11y, setA11y, font, setFont, theme, setTheme }) {
  const t = useT()
  const route = ROUTES.find(r => r[0] === hash) || ROUTES[0]
  const Screen = route[3]
  const link = ([k, icon]) => (
    <a key={k} href={`#${k}`} aria-current={route[0] === k ? 'page' : undefined}>{I[icon]}<span>{t(`route.${k}`)}</span></a>
  )
  return (
    <>
      <header className="topbar">
        <div className="topbar-in">
          <a className="logo" href="#atm">{I.logo}Cash Shield</a>
          <nav className="nav" aria-label="Screens">
            <div className="nav-grp"><span>{t('nav.customer')}</span>{ROUTES.filter(r => r[2] === 'customer').map(link)}</div>
            <i className="nav-sep" aria-hidden="true" />
            <div className="nav-grp"><span>{t('nav.bank')}</span>{ROUTES.filter(r => r[2] === 'bank').map(link)}</div>
          </nav>
          <div className="top-right">
            <span className="demo-note">{t('demoNote')}</span>
            <Lang />
            <button className="icon-btn" aria-pressed={a11y} aria-label={t('a11y')} title={t('a11y')}
              onClick={() => setA11y(!a11y)}>{I.glasses}</button>
          </div>
        </div>
      </header>
      {a11y && <A11yBar font={font} setFont={setFont} theme={theme} setTheme={setTheme} close={() => setA11y(false)} />}
      <Screen />
    </>
  )
}

createRoot(document.getElementById('root')).render(<Shell />)
