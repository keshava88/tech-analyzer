import { useEffect, useRef } from 'react'

export interface FeedEvent {
  id: number
  ts: string
  type: string
  symbol?: string
  message: string
  color: string
}

interface Props { events: FeedEvent[] }

export function TradeFeed({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div style={{ background: '#1e2530', borderRadius: 8, padding: 16, height: 280, overflowY: 'auto', fontFamily: 'monospace', fontSize: 12 }}>
      <div style={{ color: '#8892a4', marginBottom: 8, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 }}>Trade Feed</div>
      {events.length === 0 && <div style={{ color: '#555e6e' }}>Waiting for events...</div>}
      {events.map((ev) => (
        <div key={ev.id} style={{ marginBottom: 4, color: ev.color }}>
          <span style={{ color: '#555e6e', marginRight: 8 }}>{ev.ts}</span>
          {ev.symbol && <span style={{ color: '#c8d0dc', marginRight: 6 }}>{ev.symbol.replace('.NS', '')}</span>}
          {ev.message}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
