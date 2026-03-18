import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
} from 'lightweight-charts'
import type { IChartApi, ISeriesApi, SeriesMarker, Time } from 'lightweight-charts'
import { useWebSocket } from '../ws/useWebSocket'
import { api } from '../api/client'

interface Props {
  symbol: string
  interval: string
}

export function CandleChart({ symbol, interval }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const markersRef = useRef<SeriesMarker<Time>[]>([])

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#161c26' }, textColor: '#8892a4' },
      grid: { vertLines: { color: '#263040' }, horzLines: { color: '#263040' } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#263040' },
      rightPriceScale: { borderColor: '#263040' },
      width: containerRef.current.clientWidth,
      height: 340,
    })

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a', downColor: '#ef5350',
      borderUpColor: '#26a69a', borderDownColor: '#ef5350',
      wickUpColor: '#26a69a', wickDownColor: '#ef5350',
    })

    chartRef.current = chart
    seriesRef.current = series
    markersRef.current = []

    api.getCandles(symbol, interval).then((data) => {
      if (data.candles?.length) {
        series.setData(data.candles)
        chart.timeScale().fitContent()
      }
    })

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.resize(containerRef.current.clientWidth, 340)
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [symbol, interval])

  useWebSocket((event) => {
    const series = seriesRef.current
    if (!series) return

    if (event.type === 'candle_processed' && event.symbol === symbol) {
      const c = event.candle
      series.update({
        time: (new Date(c.time).getTime() / 1000) as Time,
        open: c.open, high: c.high, low: c.low, close: c.close,
      })
    }

    if (event.type === 'ltp_tick' && event.prices[symbol]) {
      const ltp = event.prices[symbol]
      const data = series.data()
      const last = data.length ? data[data.length - 1] as { time: Time; open: number; high: number; low: number; close: number } : null
      if (last) {
        series.update({
          time: last.time,
          open: last.open,
          high: Math.max(last.high, ltp),
          low: Math.min(last.low, ltp),
          close: ltp,
        })
      }
    }

    if (event.type === 'trade_open' && event.symbol === symbol) {
      markersRef.current = [
        ...markersRef.current,
        {
          time: (Date.now() / 1000) as Time,
          position: event.signal === 'bullish' ? 'belowBar' : 'aboveBar',
          color: event.signal === 'bullish' ? '#26a69a' : '#ef5350',
          shape: event.signal === 'bullish' ? 'arrowUp' : 'arrowDown',
          text: `${event.pattern} @ ${event.price}`,
        } as SeriesMarker<Time>,
      ]
      createSeriesMarkers(series, markersRef.current)
    }

    if (event.type === 'trade_close' && event.symbol === symbol) {
      const color = event.pnl >= 0 ? '#26a69a' : '#ef5350'
      markersRef.current = [
        ...markersRef.current,
        {
          time: (Date.now() / 1000) as Time,
          position: 'aboveBar',
          color,
          shape: 'circle',
          text: `${event.reason} ${event.pnl >= 0 ? '+' : ''}₹${event.pnl.toFixed(0)}`,
        } as SeriesMarker<Time>,
      ]
      createSeriesMarkers(series, markersRef.current)
    }
  })

  return (
    <div style={{ background: '#161c26', borderRadius: 8, padding: 16, marginBottom: 24 }}>
      <div style={{ color: '#8892a4', fontSize: 12, marginBottom: 8 }}>
        {symbol} · {interval}
      </div>
      <div ref={containerRef} />
    </div>
  )
}
