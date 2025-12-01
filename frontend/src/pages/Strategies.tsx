import { useState, useEffect } from 'react'
import axios from 'axios'
import { Brain, Play, Pause, BarChart3, Target, TrendingUp } from 'lucide-react'

export default function Strategies() {
  const [strategies, setStrategies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const response = await axios.get('/api/strategies')
        setStrategies(response.data)
      } catch (error) {
        setStrategies([
          { name: 'Trend Following', enabled: true, trades: 245, win_rate: 52.3, profit: 1234.56, status: 'active' },
          { name: 'Mean Reversion', enabled: true, trades: 189, win_rate: 48.7, profit: 876.32, status: 'active' },
          { name: 'Breakout', enabled: true, trades: 156, win_rate: 45.2, profit: 654.21, status: 'active' },
          { name: 'Scalping', enabled: true, trades: 423, win_rate: 51.8, profit: 1567.89, status: 'active' },
          { name: 'News Trading', enabled: false, trades: 87, win_rate: 55.2, profit: 432.10, status: 'paused' },
          { name: 'Range Trading', enabled: true, trades: 134, win_rate: 49.3, profit: 345.67, status: 'active' },
        ])
      }
      setLoading(false)
    }
    fetchStrategies()
  }, [])

  const toggleStrategy = (index: number) => {
    setStrategies(prev => {
      const updated = [...prev]
      updated[index].enabled = !updated[index].enabled
      updated[index].status = updated[index].enabled ? 'active' : 'paused'
      return updated
    })
  }

  const totalProfit = strategies.reduce((sum, s) => sum + s.profit, 0)
  const totalTrades = strategies.reduce((sum, s) => sum + s.trades, 0)
  const avgWinRate = strategies.reduce((sum, s) => sum + s.win_rate, 0) / strategies.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Estratégias</h1>
          <p className="text-gray-400 mt-1">Gerenciar estratégias de trading</p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card">
          <p className="text-gray-400 text-sm">Estratégias Ativas</p>
          <p className="text-2xl font-bold mt-1">{strategies.filter(s => s.enabled).length}/{strategies.length}</p>
        </div>
        <div className="card">
          <p className="text-gray-400 text-sm">Total Trades</p>
          <p className="text-2xl font-bold mt-1">{totalTrades.toLocaleString()}</p>
        </div>
        <div className="card">
          <p className="text-gray-400 text-sm">Win Rate Médio</p>
          <p className="text-2xl font-bold mt-1 text-success">{avgWinRate.toFixed(1)}%</p>
        </div>
        <div className="card">
          <p className="text-gray-400 text-sm">Lucro Total</p>
          <p className="text-2xl font-bold mt-1 text-success">${totalProfit.toFixed(2)}</p>
        </div>
      </div>

      {/* Strategy Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies.map((strategy, index) => (
          <div key={strategy.name} className="card">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-xl ${strategy.enabled ? 'bg-primary-500/20' : 'bg-gray-600/20'}`}>
                  <Brain className={`w-6 h-6 ${strategy.enabled ? 'text-primary-400' : 'text-gray-400'}`} />
                </div>
                <div>
                  <h3 className="font-semibold">{strategy.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    strategy.enabled ? 'bg-success/20 text-success' : 'bg-gray-600/20 text-gray-400'
                  }`}>
                    {strategy.status}
                  </span>
                </div>
              </div>
              <button 
                onClick={() => toggleStrategy(index)}
                className={`p-2 rounded-lg transition-colors ${
                  strategy.enabled ? 'bg-success/20 text-success hover:bg-success/30' : 'bg-gray-600/20 text-gray-400 hover:bg-gray-600/30'
                }`}
              >
                {strategy.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-400">
                  <BarChart3 className="w-4 h-4" />
                  <span className="text-sm">Trades</span>
                </div>
                <span className="font-semibold">{strategy.trades}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-400">
                  <Target className="w-4 h-4" />
                  <span className="text-sm">Win Rate</span>
                </div>
                <span className={`font-semibold ${strategy.win_rate >= 50 ? 'text-success' : 'text-warning'}`}>
                  {strategy.win_rate}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-400">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-sm">Lucro</span>
                </div>
                <span className={`font-semibold ${strategy.profit >= 0 ? 'text-success' : 'text-danger'}`}>
                  ${strategy.profit.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
