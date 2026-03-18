export type SessionStatus = 'idle' | 'running' | 'stopped' | 'eod_complete'

export interface Position {
  symbol: string
  signal: string
  pattern: string
  entry_price: number
  units: number
  target_price: number
  stoploss_price: number
  entry_date: string
}

export interface PortfolioSummary {
  capital: number
  cash: number
  open_value: number
  total_value: number
  total_pnl: number
  trades: number
  wins: number
  losses: number
  hit_rate: string
  avg_pnl: number
}

export interface ClosedTrade {
  symbol: string
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  units: number
  signal: string
  pattern: string
  exit_reason: string
  pnl: number
  pct: number
}

export type WsEvent =
  | { type: 'session_status'; status: SessionStatus; symbols?: string[]; interval?: string; capital?: number; market_open?: boolean; market_reason?: string }
  | { type: 'portfolio_update'; summary: PortfolioSummary; positions: Position[]; ts?: string }
  | { type: 'ltp_tick'; prices: Record<string, number>; ts?: string }
  | { type: 'candle_processed'; symbol: string; candle: { time: string; open: number; high: number; low: number; close: number }; ts?: string }
  | { type: 'trade_open'; symbol: string; signal: string; pattern: string; price: number; units: number; target: number; stop: number; ts?: string }
  | { type: 'trade_close'; symbol: string; signal: string; pattern: string; price: number; units: number; reason: string; pnl: number; pct: number; ts?: string }
  | { type: 'error'; symbol?: string; message: string; ts?: string }
