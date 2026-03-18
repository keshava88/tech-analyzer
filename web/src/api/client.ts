const BASE = '/api'

async function post(path: string, body?: unknown) {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

async function get(path: string) {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export interface StartConfig {
  symbols?: string[]
  watchlist?: string
  interval: string
  capital: number
  target_pct: number
  stoploss_pct: number
  trend_filter: boolean
  fresh: boolean
}

export const api = {
  startSession: (cfg: StartConfig) => post('/session/start', cfg),
  stopSession:  ()                  => post('/session/stop'),
  resetSession: (capital: number)   => post(`/session/reset?capital=${capital}`),
  getStatus:    ()                  => get('/session/status'),
  getPortfolio: ()                  => get('/portfolio'),
  getTrades:    (date?: string)     => get(`/portfolio/trades${date ? `?date=${date}` : ''}`),
  getCandles:   (symbol: string, interval = '15m') =>
    get(`/portfolio/candles/${encodeURIComponent(symbol)}?interval=${interval}`),
}
