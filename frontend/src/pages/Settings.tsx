import { useState } from 'react'
import { Settings as SettingsIcon, Save, RefreshCw, Shield, Bell, Zap, Database } from 'lucide-react'

export default function Settings() {
  const [settings, setSettings] = useState({
    risk_per_trade: 1.0,
    max_daily_loss: 5.0,
    max_positions: 5,
    use_trailing_stop: true,
    telegram_notifications: true,
    auto_trade: true,
    use_ml: true,
  })

  const handleChange = (key: string, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Configurações</h1>
          <p className="text-gray-400 mt-1">Ajustar parâmetros do bot</p>
        </div>
        <button className="btn btn-primary flex items-center gap-2">
          <Save className="w-4 h-4" />
          Salvar
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Management */}
        <div className="card">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-danger/20">
              <Shield className="w-5 h-5 text-danger" />
            </div>
            <h3 className="font-semibold">Gerenciamento de Risco</h3>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Risco por Trade (%)</label>
              <input 
                type="number" 
                value={settings.risk_per_trade}
                onChange={(e) => handleChange('risk_per_trade', parseFloat(e.target.value))}
                className="w-full px-4 py-2 bg-dark-100 border border-dark-100 rounded-lg focus:border-primary-500 focus:outline-none"
                step="0.1"
                min="0.1"
                max="5"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Loss Máximo Diário (%)</label>
              <input 
                type="number" 
                value={settings.max_daily_loss}
                onChange={(e) => handleChange('max_daily_loss', parseFloat(e.target.value))}
                className="w-full px-4 py-2 bg-dark-100 border border-dark-100 rounded-lg focus:border-primary-500 focus:outline-none"
                step="0.5"
                min="1"
                max="10"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Máximo de Posições</label>
              <input 
                type="number" 
                value={settings.max_positions}
                onChange={(e) => handleChange('max_positions', parseInt(e.target.value))}
                className="w-full px-4 py-2 bg-dark-100 border border-dark-100 rounded-lg focus:border-primary-500 focus:outline-none"
                min="1"
                max="20"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-gray-400">Trailing Stop</label>
              <button 
                onClick={() => handleChange('use_trailing_stop', !settings.use_trailing_stop)}
                className={`w-12 h-6 rounded-full transition-colors ${settings.use_trailing_stop ? 'bg-success' : 'bg-gray-600'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.use_trailing_stop ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="card">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-primary-500/20">
              <Bell className="w-5 h-5 text-primary-400" />
            </div>
            <h3 className="font-semibold">Notificações</h3>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <div>
                <p className="font-medium">Telegram</p>
                <p className="text-sm text-gray-400">Notificações de trades</p>
              </div>
              <button 
                onClick={() => handleChange('telegram_notifications', !settings.telegram_notifications)}
                className={`w-12 h-6 rounded-full transition-colors ${settings.telegram_notifications ? 'bg-success' : 'bg-gray-600'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.telegram_notifications ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Trading */}
        <div className="card">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-success/20">
              <Zap className="w-5 h-5 text-success" />
            </div>
            <h3 className="font-semibold">Trading</h3>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <div>
                <p className="font-medium">Auto Trade</p>
                <p className="text-sm text-gray-400">Executar trades automaticamente</p>
              </div>
              <button 
                onClick={() => handleChange('auto_trade', !settings.auto_trade)}
                className={`w-12 h-6 rounded-full transition-colors ${settings.auto_trade ? 'bg-success' : 'bg-gray-600'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.auto_trade ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
            <div className="flex items-center justify-between p-3 bg-dark-100 rounded-lg">
              <div>
                <p className="font-medium">Machine Learning</p>
                <p className="text-sm text-gray-400">Usar modelos de ML</p>
              </div>
              <button 
                onClick={() => handleChange('use_ml', !settings.use_ml)}
                className={`w-12 h-6 rounded-full transition-colors ${settings.use_ml ? 'bg-success' : 'bg-gray-600'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.use_ml ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </div>
        </div>

        {/* System */}
        <div className="card">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <Database className="w-5 h-5 text-purple-400" />
            </div>
            <h3 className="font-semibold">Sistema</h3>
          </div>

          <div className="space-y-4">
            <div className="p-3 bg-dark-100 rounded-lg">
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">Versão</span>
                <span className="font-medium">2.0.0 Elite</span>
              </div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">Redis</span>
                <span className="text-success">● Conectado</span>
              </div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">InfluxDB</span>
                <span className="text-success">● Conectado</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">MT5</span>
                <span className="text-success">● Conectado</span>
              </div>
            </div>
            <button className="w-full btn bg-dark-100 hover:bg-dark-300 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4" />
              Reiniciar Bot
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
