import { useState } from 'react'
import { api } from '../api/client'
import type { StartConfig } from '../api/client'
import type { SessionStatus } from '../ws/eventTypes'

interface Props {
  status: SessionStatus
}

const WATCHLISTS = ['nifty_bank', 'nifty50']
const INTERVALS  = ['1m', '5m', '15m', '30m', '1h']

export function SessionControls({ status }: Props) {
  const [cfg, setCfg] = useState<StartConfig>({
    watchlist: 'nifty_bank',
    interval: '15m',
    capital: 200000,
    target_pct: 1.5,
    stoploss_pct: 0.8,
    trend_filter: true,
    fresh: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const isRunning = status === 'running'

  async function handleStart() {
    setLoading(true); setError('')
    try { await api.startSession(cfg) }
    catch (e: unknown) { setError(String(e)) }
    finally { setLoading(false) }
  }

  async function handleStop() {
    setLoading(true)
    try { await api.stopSession() }
    finally { setLoading(false) }
  }

  async function handleReset() {
    if (!confirm('Reset portfolio to starting capital?')) return
    setLoading(true)
    try { await api.resetSession(cfg.capital) }
    finally { setLoading(false) }
  }

  const inp: React.CSSProperties = { background: '#263040', border: '1px solid #344054', borderRadius: 6, color: '#c8d0dc', padding: '6px 10px', width: '100%', fontSize: 13 }
  const lbl: React.CSSProperties = { color: '#8892a4', fontSize: 11, marginBottom: 4, display: 'block', textTransform: 'uppercase', letterSpacing: 0.5 }

  return (
    <div style={{ background: '#1e2530', borderRadius: 8, padding: 20, marginBottom: 24 }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>

        <div style={{ minWidth: 140 }}>
          <label style={lbl}>Watchlist</label>
          <select style={inp} value={cfg.watchlist} onChange={e => setCfg(c => ({ ...c, watchlist: e.target.value }))}>
            {WATCHLISTS.map(w => <option key={w}>{w}</option>)}
          </select>
        </div>

        <div style={{ minWidth: 100 }}>
          <label style={lbl}>Interval</label>
          <select style={inp} value={cfg.interval} onChange={e => setCfg(c => ({ ...c, interval: e.target.value }))}>
            {INTERVALS.map(i => <option key={i}>{i}</option>)}
          </select>
        </div>

        <div style={{ minWidth: 120 }}>
          <label style={lbl}>Capital (₹)</label>
          <input style={inp} type="number" value={cfg.capital} onChange={e => setCfg(c => ({ ...c, capital: +e.target.value }))} />
        </div>

        <div style={{ minWidth: 100 }}>
          <label style={lbl}>Target %</label>
          <input style={inp} type="number" step="0.1" value={cfg.target_pct} onChange={e => setCfg(c => ({ ...c, target_pct: +e.target.value }))} />
        </div>

        <div style={{ minWidth: 100 }}>
          <label style={lbl}>Stop %</label>
          <input style={inp} type="number" step="0.1" value={cfg.stoploss_pct} onChange={e => setCfg(c => ({ ...c, stoploss_pct: +e.target.value }))} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 2 }}>
          <input type="checkbox" id="tf" checked={cfg.trend_filter} onChange={e => setCfg(c => ({ ...c, trend_filter: e.target.checked }))} />
          <label htmlFor="tf" style={{ color: '#c8d0dc', fontSize: 13, cursor: 'pointer' }}>Trend Filter</label>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 2 }}>
          <input type="checkbox" id="fresh" checked={cfg.fresh} onChange={e => setCfg(c => ({ ...c, fresh: e.target.checked }))} />
          <label htmlFor="fresh" style={{ color: '#c8d0dc', fontSize: 13, cursor: 'pointer' }}>Fresh Start</label>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          {!isRunning
            ? <button onClick={handleStart} disabled={loading} style={btn('#26a69a')}>▶ Start</button>
            : <button onClick={handleStop}  disabled={loading} style={btn('#ef5350')}>■ Stop</button>
          }
          <button onClick={handleReset} disabled={loading || isRunning} style={btn('#555e6e')}>↺ Reset</button>
        </div>
      </div>

      {error && <div style={{ color: '#ef5350', marginTop: 10, fontSize: 12 }}>{error}</div>}

      <div style={{ marginTop: 10, fontSize: 12 }}>
        Status:{' '}
        <span style={{ color: statusColor(status), fontWeight: 700 }}>{status.toUpperCase()}</span>
      </div>
    </div>
  )
}

function btn(color: string): React.CSSProperties {
  return { background: color, border: 'none', borderRadius: 6, color: '#fff', padding: '8px 18px', fontWeight: 700, cursor: 'pointer', fontSize: 13 }
}

function statusColor(s: SessionStatus) {
  return s === 'running' ? '#26a69a' : s === 'stopped' ? '#ef5350' : s === 'eod_complete' ? '#ff9800' : '#8892a4'
}
