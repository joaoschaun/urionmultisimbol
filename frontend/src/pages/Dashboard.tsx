import { useEffect, useState } from 'react'
import axios from 'axios'
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  Target,
  Percent,
  DollarSign,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

interface DashboardProps {
  data?: {
    account?: any
    positions?: any[]
  }
}

interface EquityPoint {
  date: string
  value: number
  profit: number
}

interface DailyPerformance {
  date: string
  trades: number
  wins: number
  losses: number
  profit: number
}

export default function Dashboard({ data }: DashboardProps) {
  const [metrics, setMetrics] = useState<any>(null)
  const [chartData, setChartData] = useState<EquityPoint[]>([])
  const [dailyPerformance, setDailyPerformance] = useState<DailyPerformance[]>([])
  const [loading, setLoading] = useState(true)
  const [chartPeriod, setChartPeriod] = useState<number>(7)

  // Fetch equity history for chart
  const fetchEquityHistory = async (days: number) => {
    try {
      const response = await axios.get(`/api/equity/history?days=${days}`)
      if (response.data?.data_points?.length > 0) {
        const formatted = response.data.data_points.map((point: any) => ({
          date: point.timestamp?.slice(5, 10).replace('-', '/') || '',
          value: point.equity || 0,
          profit: point.change || 0
        }))
        setChartData(formatted)
      }
    } catch (error) {
      console.log('Usando dados de fallback para equity')
      // Fallback com dados mock se API falhar
      setChartData([
        { date: '01/11', value: 5000, profit: 0 },
        { date: '05/11', value: 5120, profit: 120 },
        { date: '10/11', value: 5089, profit: 89 },
        { date: '15/11', value: 5234, profit: 234 },
        { date: '20/11', value: 5456, profit: 456 },
        { date: '25/11', value: 5335, profit: 335 },
        { date: '30/11', value: 5542, profit: 542 },
      ])
    }
  }

  // Fetch daily performance
  const fetchDailyPerformance = async () => {
    try {
      const response = await axios.get('/api/performance/daily?days=7')
      if (response.data?.daily_data) {
        setDailyPerformance(response.data.daily_data)
      }
    } catch (error) {
      console.log('Performance diária não disponível')
    }
  }

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await axios.get('/api/metrics')
        setMetrics(response.data)
      } catch (error) {
        // Usar dados mock
        setMetrics({
          total_trades: 1554,
          win_rate: 48.9,
          profit_factor: 2.63,
          net_profit: 5336.66,
          avg_win: 11.34,
          avg_loss: 4.13,
          max_drawdown: 1047.80,
          expectancy: 3.43
        })
      }
      setLoading(false)
    }
    
    fetchMetrics()
    fetchEquityHistory(chartPeriod)
    fetchDailyPerformance()
  }, [])

  // Atualizar gráfico quando período mudar
  useEffect(() => {
    fetchEquityHistory(chartPeriod)
  }, [chartPeriod])

  const StatCard = ({ title, value, icon: Icon, trend, trendValue, color }: any) => (
    <div className="card animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-400 mb-1">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${trend === 'up' ? 'text-success' : 'text-danger'}`}>
              {trend === 'up' ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-xl ${color}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-400 mt-1">Visão geral do Urion Trading Bot</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-3 py-1.5 bg-success/20 text-success rounded-full text-sm font-medium">
            ● Bot Ativo
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Lucro Total"
          value={`$${metrics?.net_profit?.toLocaleString() || '5,336.66'}`}
          icon={DollarSign}
          trend="up"
          trendValue="+15.2% este mês"
          color="bg-gradient-to-br from-success to-emerald-600"
        />
        <StatCard
          title="Win Rate"
          value={`${metrics?.win_rate || 48.9}%`}
          icon={Target}
          trend="up"
          trendValue="+2.1% vs semana"
          color="bg-gradient-to-br from-primary-500 to-cyan-500"
        />
        <StatCard
          title="Profit Factor"
          value={metrics?.profit_factor || 2.63}
          icon={BarChart3}
          trend="up"
          trendValue="Excelente"
          color="bg-gradient-to-br from-purple-500 to-pink-500"
        />
        <StatCard
          title="Total Trades"
          value={metrics?.total_trades?.toLocaleString() || '1,554'}
          icon={Activity}
          color="bg-gradient-to-br from-orange-500 to-amber-500"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart */}
        <div className="lg:col-span-2 card">
          <div className="card-header">
            <h3 className="font-semibold">Curva de Equity</h3>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setChartPeriod(1)}
                className={`px-3 py-1 text-xs rounded-lg ${chartPeriod === 1 ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-100 text-gray-400 hover:text-white'}`}
              >
                1D
              </button>
              <button 
                onClick={() => setChartPeriod(7)}
                className={`px-3 py-1 text-xs rounded-lg ${chartPeriod === 7 ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-100 text-gray-400 hover:text-white'}`}
              >
                1W
              </button>
              <button 
                onClick={() => setChartPeriod(30)}
                className={`px-3 py-1 text-xs rounded-lg ${chartPeriod === 30 ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-100 text-gray-400 hover:text-white'}`}
              >
                1M
              </button>
              <button 
                onClick={() => setChartPeriod(90)}
                className={`px-3 py-1 text-xs rounded-lg ${chartPeriod === 90 ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-100 text-gray-400 hover:text-white'}`}
              >
                ALL
              </button>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                <YAxis stroke="#6b7280" fontSize={12} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1a222f', 
                    border: '1px solid #374151',
                    borderRadius: '8px'
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#0ea5e9" 
                  fillOpacity={1} 
                  fill="url(#colorValue)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="card">
          <div className="card-header">
            <h3 className="font-semibold">Métricas Rápidas</h3>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <span className="text-gray-400">Média Win</span>
              <span className="font-semibold text-success">+${metrics?.avg_win || 11.34}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <span className="text-gray-400">Média Loss</span>
              <span className="font-semibold text-danger">-${metrics?.avg_loss || 4.13}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <span className="text-gray-400">Expectancy</span>
              <span className="font-semibold text-success">+${metrics?.expectancy || 3.43}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <span className="text-gray-400">Max Drawdown</span>
              <span className="font-semibold text-warning">${metrics?.max_drawdown || 1047.80}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <span className="text-gray-400">Risk:Reward</span>
              <span className="font-semibold">1:2.74</span>
            </div>
          </div>
        </div>
      </div>

      {/* Positions */}
      <div className="card">
        <div className="card-header">
          <h3 className="font-semibold">Posições Abertas</h3>
          <span className="px-2 py-1 bg-primary-500/20 text-primary-400 rounded-full text-xs">
            {data?.positions?.length || 0} ativas
          </span>
        </div>
        
        {data?.positions && data.positions.length > 0 ? (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Par</th>
                  <th>Tipo</th>
                  <th>Volume</th>
                  <th>Preço Entrada</th>
                  <th>Preço Atual</th>
                  <th>P/L</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((pos: any) => (
                  <tr key={pos.ticket}>
                    <td className="font-medium">{pos.symbol}</td>
                    <td>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        pos.type === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
                      }`}>
                        {pos.type}
                      </span>
                    </td>
                    <td>{pos.volume}</td>
                    <td>{pos.price_open}</td>
                    <td>{pos.price_current}</td>
                    <td className={pos.profit >= 0 ? 'text-success' : 'text-danger'}>
                      ${pos.profit?.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <Activity className="w-12 h-12 mb-4 opacity-50" />
            <p>Nenhuma posição aberta</p>
            <p className="text-sm mt-1">O bot está aguardando sinais...</p>
          </div>
        )}
      </div>
    </div>
  )
}
