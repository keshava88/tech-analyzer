import type { Position } from '../ws/eventTypes'

interface Props {
  symbols: string[]
  positions: Position[]
  ltpMap: Record<string, number>
  onSelectSymbol: (s: string) => void
  selectedSymbol: string | null
}

export function SymbolTable({ symbols, positions, ltpMap, onSelectSymbol, selectedSymbol }: Props) {
  const posMap = Object.fromEntries(positions.map((p) => [p.symbol, p]))

  return (
    <div style={{ background: '#1e2530', borderRadius: 8, overflow: 'hidden', marginBottom: 24 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#161c26', color: '#8892a4' }}>
            <th style={th}>Symbol</th>
            <th style={th}>LTP</th>
            <th style={th}>State</th>
            <th style={th}>Entry</th>
            <th style={th}>Target</th>
            <th style={th}>Stop</th>
            <th style={th}>Unreal P&L</th>
          </tr>
        </thead>
        <tbody>
          {symbols.map((sym) => {
            const ltp = ltpMap[sym]
            const pos = posMap[sym]
            const isSelected = sym === selectedSymbol

            let unrealPnl: number | null = null
            if (pos && ltp) {
              unrealPnl = pos.signal === 'bullish'
                ? (ltp - pos.entry_price) * pos.units
                : (pos.entry_price - ltp) * pos.units
            }

            const pnlColor = unrealPnl == null ? '' : unrealPnl >= 0 ? '#26a69a' : '#ef5350'
            const rowBg = isSelected ? '#263040' : pos ? '#1a2535' : 'transparent'

            return (
              <tr
                key={sym}
                onClick={() => onSelectSymbol(sym)}
                style={{ cursor: 'pointer', background: rowBg, borderBottom: '1px solid #263040' }}
              >
                <td style={{ ...td, fontWeight: 600, color: '#c8d0dc' }}>{sym.replace('.NS', '')}</td>
                <td style={{ ...td, fontWeight: 600 }}>{ltp ? ltp.toFixed(2) : '—'}</td>
                <td style={td}>
                  {pos
                    ? <span style={{ color: pos.signal === 'bullish' ? '#26a69a' : '#ef5350', fontWeight: 600 }}>
                        {pos.signal === 'bullish' ? '▲ LONG' : '▼ SHORT'}
                      </span>
                    : <span style={{ color: '#555e6e' }}>watching</span>
                  }
                </td>
                <td style={td}>{pos ? pos.entry_price.toFixed(2) : '—'}</td>
                <td style={{ ...td, color: '#26a69a' }}>{pos ? pos.target_price.toFixed(2) : '—'}</td>
                <td style={{ ...td, color: '#ef5350' }}>{pos ? pos.stoploss_price.toFixed(2) : '—'}</td>
                <td style={{ ...td, color: pnlColor, fontWeight: 600 }}>
                  {unrealPnl != null ? `${unrealPnl >= 0 ? '+' : ''}₹${unrealPnl.toFixed(0)}` : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const th: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 }
const td: React.CSSProperties = { padding: '10px 14px', color: '#c8d0dc' }
