import { useState, useEffect, useCallback, useRef } from 'react'

interface WebSocketData {
  account?: {
    balance: number
    equity: number
    profit: number
    margin: number
    free_margin: number
    leverage: number
  }
  positions?: any[]
  trades?: any[]
}

export function useWebSocket(url: string) {
  const [connected, setConnected] = useState(false)
  const [data, setData] = useState<WebSocketData>({})
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          
          if (message.type === 'account_update') {
            setData(prev => ({ ...prev, account: message.data }))
          } else if (message.type === 'positions_update') {
            setData(prev => ({ ...prev, positions: message.data }))
          }
        } catch (e) {
          console.error('Error parsing message:', e)
        }
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setConnected(false)
        
        // Reconectar após 5 segundos
        reconnectTimeout.current = setTimeout(connect, 5000)
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to connect:', error)
      reconnectTimeout.current = setTimeout(connect, 5000)
    }
  }, [url])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  const send = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return { connected, data, send }
}
