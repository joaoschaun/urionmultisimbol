import { Menu, Bell, Wifi, WifiOff, DollarSign, TrendingUp, TrendingDown } from 'lucide-react'

interface HeaderProps {
  connected: boolean
  account?: {
    balance: number
    equity: number
    profit: number
  }
  onMenuClick: () => void
}

export default function Header({ connected, account, onMenuClick }: HeaderProps) {
  const formatMoney = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value)
  }

  return (
    <header className="h-16 bg-dark-300 border-b border-dark-100 flex items-center justify-between px-6">
      {/* Left */}
      <div className="flex items-center gap-4">
        <button 
          onClick={onMenuClick}
          className="lg:hidden p-2 rounded-lg hover:bg-dark-200"
        >
          <Menu className="w-5 h-5 text-gray-400" />
        </button>
        
        {/* Account Info */}
        {account && (
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-400">Balance</p>
                <p className="text-sm font-semibold">{formatMoney(account.balance)}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-400">Equity</p>
                <p className="text-sm font-semibold">{formatMoney(account.equity)}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {account.profit >= 0 ? (
                <TrendingUp className="w-4 h-4 text-success" />
              ) : (
                <TrendingDown className="w-4 h-4 text-danger" />
              )}
              <div>
                <p className="text-xs text-gray-400">P/L</p>
                <p className={`text-sm font-semibold ${account.profit >= 0 ? 'text-success' : 'text-danger'}`}>
                  {formatMoney(account.profit)}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        {/* Connection Status */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
          connected ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
        }`}>
          {connected ? (
            <>
              <Wifi className="w-4 h-4" />
              <span className="text-xs font-medium">Conectado</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4" />
              <span className="text-xs font-medium">Desconectado</span>
            </>
          )}
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-dark-200 transition-colors">
          <Bell className="w-5 h-5 text-gray-400" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-danger rounded-full"></span>
        </button>
        
        {/* User */}
        <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center">
          <span className="text-sm font-bold">U</span>
        </div>
      </div>
    </header>
  )
}
