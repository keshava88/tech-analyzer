import type { PortfolioSummary as PS } from '../ws/eventTypes'

interface Props { summary: PS }

function Card({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: '#1e2530', borderRadius: 8, padding: '12px 20px', minWidth: 130 }}>
      <div style={{ fontSize: 11, color: '#8892a4', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || '#e8ecf0' }}>{value}</div>
    </div>
  )
}

export function PortfolioSummary({ summary: s }: Props) {
  const pnlColor = s.total_pnl >= 0 ? '#26a69a' : '#ef5350'
  const sign = s.total_pnl >= 0 ? '+' : ''

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
      <Card label="Capital"    value={`₹${s.capital.toLocaleString('en-IN')}`} />
      <Card label="Cash"       value={`₹${s.cash.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
      <Card label="Open Value" value={`₹${s.open_value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
      <Card label="Total P&L"  value={`${sign}₹${Math.abs(s.total_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} color={pnlColor} />
      <Card label="Trades"     value={`${s.trades}`} />
      <Card label="Hit Rate"   value={s.hit_rate} color={s.wins > s.losses ? '#26a69a' : '#ef5350'} />
      <Card label="Avg P&L"    value={`₹${s.avg_pnl.toFixed(0)}`} color={s.avg_pnl >= 0 ? '#26a69a' : '#ef5350'} />
    </div>
  )
}
