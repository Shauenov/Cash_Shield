const J = { 'Content-Type': 'application/json' }
const call = async (path, opts = {}) => {
  const r = await fetch('/api' + path, opts)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : r.statusText)
  return data
}
let n = 0
export const api = {
  customers: () => call('/v1/customers'),
  authorize: (b) => call('/mock-host/authorize', { method: 'POST', headers: J, body: JSON.stringify({ operation_id: `op_${Date.now()}_${n++}`, ...b }) }),
  answer: (id, answer) => call(`/v1/decisions/${id}/answer`, { method: 'POST', headers: J, body: JSON.stringify({ answer }) }),
  decision: (id) => call(`/v1/decisions/${id}`),
  override: (id, action, comment, officer = 'o_01') => call(`/v1/decisions/${id}/override`, { method: 'POST', headers: { ...J, 'X-Officer-Id': officer }, body: JSON.stringify({ action, comment }) }),
  report: (customer_id) => call('/v1/reports', { method: 'POST', headers: J, body: JSON.stringify({ customer_id }) }),
  consent: (customer_id, contact_name) => call('/v1/consents', { method: 'POST', headers: J, body: JSON.stringify({ customer_id, contact_name }) }),
  revoke: (id) => call(`/v1/consents/${id}`, { method: 'DELETE' }),
  events: () => call('/v1/events?limit=100'),
  held: () => call('/v1/held'),
  reset: () => call('/v1/demo-reset', { method: 'POST' }),
  skipTime: (hours) => call(`/v1/demo-time-skip?hours=${hours}`, { method: 'POST' }),
  engineDown: (down) => call(`/v1/demo-engine-down?down=${down}`, { method: 'POST' }),
}

export const kzt = (n) => (n == null ? '' : new Intl.NumberFormat('en-US').format(n).replace(/,/g, ' ') + ' ₸')
