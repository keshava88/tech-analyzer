import { useReducer, useCallback } from 'react'
import { useWebSocket } from './ws/useWebSocket'
import type { WsEvent, SessionStatus, Position, PortfolioSummary } from './ws/eventTypes'
import { SessionControls } from './components/SessionControls'
import { PortfolioSummary as PortfolioSummaryCard } from './components/PortfolioSummary'
import { SymbolTable } from './components/SymbolTable'
import { TradeFeed } from './components/TradeFeed'
import type { FeedEvent } from './components/TradeFeed'
import { CandleChart } from './components/CandleChart'

interface AppState {
  status: SessionStatus
  symbols: string[]
  interval: string
  summary: PortfolioSummary
  positions: Position[]
  ltpMap: Record<string, number>
  feedEvents: FeedEvent[]
  selectedSymbol: string | null
  feedCounter: number
  marketOpen: boolean
  marketReason: string
}

const DEFAULT_SUMMARY: PortfolioSummary = {
  capital: 0, cash: 0, open_value: 0, total_value: 0,
  total_pnl: 0, trades: 0, wins: 0, losses: 0, hit_rate: '-', avg_pnl: 0,
}

const initialState: AppState = {
  status: 'idle', symbols: [], interval: '15m',
  summary: DEFAULT_SUMMARY, positions: [],
  ltpMap: {}, feedEvents: [], selectedSymbol: null, feedCounter: 0,
  marketOpen: false, marketReason: '',
}

type Action =
  | { type: 'ws_event'; event: WsEvent }
  | { type: 'select_symbol'; symbol: string }

function fmt(ts?: string) {
  if (!ts) return new Date().toTimeString().slice(0, 8)
  return new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

function reducer(state: AppState, action: Action): AppState {
  if (action.type === 'select_symbol') {
    return { ...state, selectedSymbol: state.selectedSymbol === action.symbol ? null : action.symbol }
  }

  const ev = action.event
  switch (ev.type) {
    case 'session_status':
      return {
        ...state,
        status: ev.status,
        symbols: ev.symbols ?? state.symbols,
        interval: ev.interval ?? state.interval,
        marketOpen: ev.market_open ?? state.marketOpen,
        marketReason: ev.market_reason ?? state.marketReason,
      }

    case 'portfolio_update':
      return { ...state, summary: ev.summary, positions: ev.positions }

    case 'ltp_tick':
      return { ...state, ltpMap: { ...state.ltpMap, ...ev.prices } }

    case 'trade_open': {
      const id = state.feedCounter + 1
      const msg = `OPEN ${ev.signal.toUpperCase()} ${ev.pattern} @ ₹${ev.price} x${ev.units}  tgt=${ev.target}  stop=${ev.stop}`
      const feed: FeedEvent = { id, ts: fmt(ev.ts), type: 'open', symbol: ev.symbol, message: msg, color: ev.signal === 'bullish' ? '#26a69a' : '#ef5350' }
      return { ...state, feedCounter: id, feedEvents: [...state.feedEvents.slice(-99), feed] }
    }

    case 'trade_close': {
      const id = state.feedCounter + 1
      const sign = ev.pnl >= 0 ? '+' : ''
      const msg = `CLOSE ${ev.signal.toUpperCase()} ${ev.pattern} @ ₹${ev.price}  ${ev.reason}  P&L: ${sign}₹${ev.pnl.toFixed(2)} (${sign}${ev.pct}%)`
      const feed: FeedEvent = { id, ts: fmt(ev.ts), type: 'close', symbol: ev.symbol, message: msg, color: ev.pnl >= 0 ? '#26a69a' : '#ef5350' }
      return { ...state, feedCounter: id, feedEvents: [...state.feedEvents.slice(-99), feed] }
    }

    case 'error': {
      const id = state.feedCounter + 1
      const feed: FeedEvent = { id, ts: fmt(ev.ts), type: 'error', symbol: ev.symbol, message: `ERROR: ${ev.message}`, color: '#ff9800' }
      return { ...state, feedCounter: id, feedEvents: [...state.feedEvents.slice(-99), feed] }
    }

    default: return state
  }
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)

  useWebSocket(useCallback((event: WsEvent) => {
    dispatch({ type: 'ws_event', event })
  }, []))

  return (
    <div style={{ minHeight: '100vh', background: '#111722', color: '#c8d0dc', fontFamily: 'Inter, system-ui, sans-serif', padding: 24 }}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <span style={{ fontSize: 22, fontWeight: 800, color: '#e8ecf0' }}>📈 Tech Analyzer</span>
          <span style={{ fontSize: 13, color: '#8892a4' }}>Paper Trading Dashboard</span>
        </div>

        <SessionControls status={state.status} marketOpen={state.marketOpen} marketReason={state.marketReason} />
        <PortfolioSummaryCard summary={state.summary} />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16, marginBottom: 24 }}>
          <SymbolTable
            symbols={state.symbols.length ? state.symbols : []}
            positions={state.positions}
            ltpMap={state.ltpMap}
            onSelectSymbol={(s) => dispatch({ type: 'select_symbol', symbol: s })}
            selectedSymbol={state.selectedSymbol}
          />
          <TradeFeed events={state.feedEvents} />
        </div>

        {state.selectedSymbol && (
          <CandleChart symbol={state.selectedSymbol} interval={state.interval} />
        )}

        {!state.selectedSymbol && state.symbols.length > 0 && (
          <div style={{ color: '#555e6e', textAlign: 'center', padding: 40, background: '#1e2530', borderRadius: 8 }}>
            Click a symbol in the table to view its chart
          </div>
        )}
      </div>
    </div>
  )
}
