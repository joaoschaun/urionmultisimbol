import { useState, useEffect } from 'react'
import axios from 'axios'
import { History as HistoryIcon, TrendingUp, TrendingDown, Calendar } from 'lucide-react'

export default function History() {
  const [trades, setTrades] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    const fetchTrades = async () => {
      try {
        const response = await axios.get('/api/trades?days=30')
        setTrades(response.data)
      } catch (error) {
        // Mock data
        setTrades([
          { ticket: 1001, symbol: 'EURUSD', type: 'BUY', volume: 0.1, price: 1.0850, profit: 23.50, time: '2024-11-30T10:30:00', commission: -0.50, swap: 0 },
          { ticket: 1002, symbol: 'GBPUSD', type: 'SELL', volume: 0.2, price: 1.2650, profit: -12.30, time: '2024-11-29T14:15:00', commission: -1.00, swap: -0.50 },
          { ticket: 1003, symbol: 'USDJPY', type: 'BUY', volume: 0.15, price: 149.50, profit: 45.20, time: '2024-11-28T09:45:00', commission: -0.75, swap: 0 },
          { ticket: 1004, symbol: 'EURUSD', type: 'SELL', volume: 0.1, price: 1.0820, profit: 18.90, time: '2024-11-27T16:00:00', commission: -0.50, swap: 0 },
          { ticket: 1005, symbol: 'XAUUSD', type: 'BUY', volume: 0.05, price: 2050.00, profit: -8.50, time: '2024-11-26T11:30:00', commission: -1.50, swap: -1.00 },
        ])
      }
      setLoading(false)
    }
    fetchTrades()
  }, [])

  const filteredTrades = filter === 'all' 
    ? trades 
    : filter === 'wins' 
      ? trades.filter(t => t.profit > 0)
      : trades.filter(t => t.profit < 0)

  const totalProfit = trades.reduce((sum, t) => sum + t.profit, 0)
  const wins = trades.filter(t => t.profit > 0).length
  const losses = trades.filter(t => t.profit < 0).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Histórico de Trades</h1>
          <p className="text-gray-400 mt-1">Últimos 30 dias</p>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg ${filter === 'all' ? 'bg-primary-500 text-white' : 'bg-dark-200 text-gray-400'}`}
          >
            Todos ({trades.length})
          </button>
          <button 
            onClick={() => setFilter('wins')}
            className={`px-4 py-2 rounded-lg ${filter === 'wins' ? 'bg-success text-white' : 'bg-dark-200 text-gray-400'}`}
          >
            Wins ({wins})
          </button>
          <button 
            onClick={() => setFilter('losses')}
            className={`px-4 py-2 rounded-lg ${filter === 'losses' ? 'bg-danger text-white' : 'bg-dark-200 text-gray-400'}`}
          >
            Losses ({losses})
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card">
          <p className="text-gray-400 text-sm">Total Trades</p>
          <p className="text-2xl font-bold mt-1">{trades.length}</p>
        </div>
        <div className="card">
          <p className="text-gray-400 text-sm">Win Rate</p>
          <p className="text-2xl font-bold mt-1 text-success">
            {((wins / trades.length) * 100 || 0).toFixed(1)}%
          </p>
        </div>
        <div className="card">
          <p className="text-gray-400 text-sm">Lucro Total</p>
          <p className={`text-2xl font-bold mt-1 ${totalProfit >= 0 ? 'text-success' : 'text-danger'}`}>
            ${totalProfit.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Data/Hora</th>
                <th>Ticket</th>
                <th>Par</th>
                <th>Tipo</th>
                <th>Volume</th>
                <th>Preço</th>
                <th>Comissão</th>
                <th>Swap</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((trade) => (
                <tr key={trade.ticket}>
                  <td className="text-gray-400">
                    {new Date(trade.time).toLocaleString('pt-BR')}
                  </td>
                  <td>#{trade.ticket}</td>
                  <td className="font-medium">{trade.symbol}</td>
                  <td>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.type === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
                    }`}>
                      {trade.type}
                    </span>
                  </td>
                  <td>{trade.volume}</td>
                  <td>{trade.price}</td>
                  <td className="text-gray-400">${trade.commission}</td>
                  <td className="text-gray-400">${trade.swap}</td>
                  <td className={`font-semibold ${trade.profit >= 0 ? 'text-success' : 'text-danger'}`}>
                    {trade.profit >= 0 ? '+' : ''}${trade.profit.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
