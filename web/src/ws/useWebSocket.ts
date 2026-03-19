import { useEffect, useRef, useCallback, useState } from 'react'
import type { WsEvent } from './eventTypes'

type Handler = (event: WsEvent) => void

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

let _ws: WebSocket | null = null
let _wsOpen = false
const _handlers = new Set<Handler>()
const _connListeners = new Set<(open: boolean) => void>()

function _setOpen(open: boolean) {
  _wsOpen = open
  _connListeners.forEach((l) => l(open))
}

function connect() {
  if (_ws && (_ws.readyState === WebSocket.CONNECTING || _ws.readyState === WebSocket.OPEN)) return

  _ws = new WebSocket(WS_URL)

  _ws.onopen = () => _setOpen(true)

  _ws.onmessage = (e) => {
    try {
      const event: WsEvent = JSON.parse(e.data)
      _handlers.forEach((h) => h(event))
    } catch {}
  }

  _ws.onclose = () => {
    _setOpen(false)
    setTimeout(connect, 3000)
  }

  _ws.onerror = () => {
    _ws?.close()
  }
}

export function useWsConnected(): boolean {
  const [open, setOpen] = useState(_wsOpen)
  useEffect(() => {
    _connListeners.add(setOpen)
    return () => { _connListeners.delete(setOpen) }
  }, [])
  return open
}

export function useWebSocket(handler: Handler) {
  const ref = useRef(handler)
  ref.current = handler

  const stable = useCallback((e: WsEvent) => ref.current(e), [])

  useEffect(() => {
    _handlers.add(stable)
    connect() // no-op if already open; first mount triggers connection
    return () => { _handlers.delete(stable) }
  }, [stable])
}
