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

// Customer-facing texts. Kazakh/Russian texts come from the plan and still need a native-speaker review.
export const T = {
  en: {
    question: 'Is someone asking you by phone to withdraw or transfer this money?',
    yes: 'Yes, they are asking me', no: 'No, this is my own decision',
    pause1: 'We paused this operation. Your money is in your account and safe.',
    pause2: 'Bank, police and National Bank staff never ask you to withdraw money and give it to a courier.',
    pause3: 'The bank will contact you only through the app. Do not trust other calls.',
    callBank: 'Call the bank from the app', released: 'Approved by the bank officer. Your operation is going through.',
    declined: 'The operation was cancelled to protect you.', done: 'Done. Please take your cash.',
    doneTransfer: 'Transfer sent.', wait: 'Waiting for a bank officer…',
    nofunds: 'Not enough money in the account.',
    expired: 'The pause has ended. The operation was cancelled and your money is still in your account. You can start a new operation.',
  },
  ru: {
    // Question, buttons and the three pause lines are from the plan. The other lines were
    // translated by the team and, like all texts here, need a native-speaker review.
    question: 'Вас по телефону просят снять или перевести деньги?',
    yes: 'Да, просят', no: 'Нет, это моё решение',
    pause1: 'Мы приостановили операцию на 30 минут. Ваши деньги на счёте и в безопасности.',
    pause2: 'Сотрудники банка, полиции и Нацбанка никогда не просят снимать деньги и отдавать их курьеру.',
    pause3: 'Банк свяжется с вами только через приложение. Не верьте другим звонкам.',
    callBank: 'Позвонить в банк из приложения', released: 'Сотрудник банка подтвердил операцию. Она проводится.',
    declined: 'Операция отменена для вашей защиты.', done: 'Готово. Заберите наличные.',
    doneTransfer: 'Перевод отправлен.', wait: 'Ждём решения сотрудника банка…',
    nofunds: 'Недостаточно средств на счёте.',
    expired: 'Пауза закончилась. Операция отменена, деньги остались на счёте. Можно начать новую операцию.',
  },
  kz: {
    question: 'Сізден телефон арқылы ақша шешуді немесе аударуды сұрап жатыр ма?',
    yes: 'Иә, сұрап жатыр', no: 'Жоқ, бұл өз шешімім',
    pause1: 'Операцияны тоқтаттық. Ақшаңыз шотыңызда, қауіпсіз жерде.',
    pause2: 'Банк, полиция және Ұлттық банк қызметкерлері ешқашан ақша шешіп, курьерге беруді сұрамайды.',
    pause3: 'Банк сізбен тек қосымша арқылы байланысады. Басқа қоңырауларға сенбеңіз.',
    callBank: 'Қосымшадан банкке қоңырау шалу', released: 'Банк қызметкері растады. Операция өтіп жатыр.',
    declined: 'Сізді қорғау үшін операция тоқтатылды.', done: 'Дайын. Қолма-қол ақшаңызды алыңыз.',
    doneTransfer: 'Аударым жіберілді.', wait: 'Банк қызметкерін күтіңіз…',
    nofunds: 'Шотта қаражат жеткіліксіз.',
    expired: 'Үзіліс аяқталды. Операция тоқтатылды, ақшаңыз шотта қалды. Жаңа операция бастауға болады.',
  },
}
