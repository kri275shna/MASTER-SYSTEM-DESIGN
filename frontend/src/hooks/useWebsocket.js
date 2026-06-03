import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebsocket(storeId, onEventReceived) {
  const [status, setStatus] = useState('CONNECTING')
  const socketRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)

  const connect = useCallback(() => {
    if (!storeId || typeof window === 'undefined') return

    // Clean up existing connections
    if (socketRef.current) {
      socketRef.current.close()
    }

    setStatus('CONNECTING')
    
    // Resolve ws/wss protocol and host dynamically from backend URL configuration
    const apiHost = (typeof process !== 'undefined' && process.env && process.env.NEXT_PUBLIC_API_URL) || 
                    (typeof window !== 'undefined' ? window.location.protocol + '//' + window.location.hostname + ':8000' : 'http://localhost:8000')
    
    const protocol = apiHost.startsWith('https:') ? 'wss:' : 'ws:'
    const host = apiHost.replace(/^https?:\/\//, '')
    const wsUrl = `${protocol}//${host}/api/v1/events/stores/${storeId}/events/stream`

    console.log(`Connecting to WebSocket: ${wsUrl}`)
    const ws = new WebSocket(wsUrl)
    socketRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket Connection Established')
      setStatus('CONNECTED')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (onEventReceived) {
          onEventReceived(data)
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err)
      }
    }

    ws.onclose = (event) => {
      console.log('WebSocket Connection Closed:', event.reason)
      setStatus('DISCONNECTED')
      
      // Schedule reconnection with exponential backoff (max 30s)
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000)
      reconnectAttemptsRef.current += 1
      
      console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current})`)
      reconnectTimeoutRef.current = setTimeout(() => {
        connect()
      }, delay)
    }

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err)
      ws.close()
    }
  }, [storeId, onEventReceived])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (socketRef.current) {
        socketRef.current.close()
      }
    }
  }, [connect])

  return { status }
}
