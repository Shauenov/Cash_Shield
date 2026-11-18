import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import Atm from './screens/Atm.jsx'
import Desk from './screens/Desk.jsx'
import App from './screens/App.jsx'
import Officer from './screens/Officer.jsx'

const ROUTES = [
  ['atm', 'ATM', Atm],
  ['desk', 'Cash desk', Desk],
  ['app', 'Mobile app', App],
  ['officer', 'Officer console', Officer],
]

function Shell() {
  const [hash, setHash] = useState(location.hash.slice(1) || 'atm')
  useEffect(() => {
    const f = () => setHash(location.hash.slice(1) || 'atm')
    addEventListener('hashchange', f)
    return () => removeEventListener('hashchange', f)
  }, [])
  const [, , Screen] = ROUTES.find(r => r[0] === hash) || ROUTES[0]
  return (
    <>
      <nav className="topnav" aria-label="Screens">
        <b>Cash Shield</b>
        {ROUTES.map(([k, label]) => (
          <a key={k} href={`#${k}`} className={hash === k ? 'on' : ''}>{label}</a>
        ))}
        <span className="muted">Demo with synthetic data</span>
      </nav>
      <Screen />
    </>
  )
}

createRoot(document.getElementById('root')).render(<Shell />)
