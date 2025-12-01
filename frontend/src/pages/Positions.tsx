import { Briefcase, TrendingUp, TrendingDown, X } from 'lucide-react'

interface PositionsProps {
  positions: any[]
}

export default function Positions({ positions }: PositionsProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Posições Abertas</h1>
          <p className="text-gray-400 mt-1">Gerenciar trades ativos</p>
        </div>
        <button className="btn btn-danger flex items-center gap-2">
          <X className="w-4 h-4" />
          Fechar Todas
        </button>
      </div>

      {positions.length > 0 ? (
        <div className="grid gap-4">
          {positions.map((pos) => (
            <div key={pos.ticket} className="card">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`p-3 rounded-xl ${pos.type === 'BUY' ? 'bg-success/20' : 'bg-danger/20'}`}>
                    {pos.type === 'BUY' ? (
                      <TrendingUp className="w-6 h-6 text-success" />
                    ) : (
                      <TrendingDown className="w-6 h-6 text-danger" />
                    )}
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg">{pos.symbol}</h3>
                    <p className="text-gray-400 text-sm">Ticket: #{pos.ticket}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-8">
                  <div className="text-center">
                    <p className="text-xs text-gray-400">Volume</p>
                    <p className="font-semibold">{pos.volume}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-400">Entrada</p>
                    <p className="font-semibold">{pos.price_open}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-400">Atual</p>
                    <p className="font-semibold">{pos.price_current}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-400">SL</p>
                    <p className="font-semibold text-danger">{pos.sl || '-'}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-400">TP</p>
                    <p className="font-semibold text-success">{pos.tp || '-'}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-400">P/L</p>
                    <p className={`font-bold text-lg ${pos.profit >= 0 ? 'text-success' : 'text-danger'}`}>
                      ${pos.profit?.toFixed(2)}
                    </p>
                  </div>
                  <button className="btn btn-danger">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card flex flex-col items-center justify-center py-16">
          <Briefcase className="w-16 h-16 text-gray-600 mb-4" />
          <h3 className="text-xl font-semibold mb-2">Nenhuma posição aberta</h3>
          <p className="text-gray-400">O bot está analisando o mercado...</p>
        </div>
      )}
    </div>
  )
}
