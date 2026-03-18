import { useEffect, useRef, useCallback } from 'react'
import type { WsEvent } from './eventTypes'

type Handler = (event: WsEvent) => void

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

let _ws: WebSocket | null = null
const _handlers = new Set<Handler>()
function connect() {
  if (_ws && (_ws.readyState === WebSocket.CONNECTING || _ws.readyState === WebSocket.OPEN)) return

  _ws = new WebSocket(WS_URL)

  _ws.onmessage = (e) => {
    try {
      const event: WsEvent = JSON.parse(e.data)
      _handlers.forEach((h) => h(event))
    } catch {}
  }

  _ws.onclose = () => {
    setTimeout(connect, 3000)
  }

  _ws.onerror = () => {
    _ws?.close()
  }
}

connect()

export function useWebSocket(handler: Handler) {
  const ref = useRef(handler)
  ref.current = handler

  const stable = useCallback((e: WsEvent) => ref.current(e), [])

  useEffect(() => {
    _handlers.add(stable)
    return () => { _handlers.delete(stable) }
  }, [stable])
}
