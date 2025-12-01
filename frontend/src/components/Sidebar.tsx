import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Briefcase, 
  History, 
  Brain, 
  Settings,
  ChevronLeft,
  TrendingUp
} from 'lucide-react'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
}

export default function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
    { icon: Briefcase, label: 'Posições', path: '/positions' },
    { icon: History, label: 'Histórico', path: '/history' },
    { icon: Brain, label: 'Estratégias', path: '/strategies' },
    { icon: Settings, label: 'Configurações', path: '/settings' },
  ]

  return (
    <aside 
      className={`bg-dark-300 border-r border-dark-100 transition-all duration-300 ${
        isOpen ? 'w-64' : 'w-20'
      }`}
    >
      {/* Logo */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-dark-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-primary-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          {isOpen && (
            <span className="text-xl font-bold bg-gradient-to-r from-primary-400 to-cyan-300 bg-clip-text text-transparent">
              URION
            </span>
          )}
        </div>
        <button 
          onClick={onToggle}
          className="p-2 rounded-lg hover:bg-dark-200 transition-colors"
        >
          <ChevronLeft className={`w-5 h-5 text-gray-400 transition-transform ${!isOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="p-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => `
              flex items-center gap-3 px-4 py-3 rounded-xl transition-all
              ${isActive 
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30' 
                : 'text-gray-400 hover:bg-dark-200 hover:text-white'
              }
            `}
          >
            <item.icon className="w-5 h-5" />
            {isOpen && <span className="font-medium">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Bot Status */}
      {isOpen && (
        <div className="absolute bottom-4 left-4 right-4">
          <div className="bg-dark-200 rounded-xl p-4 border border-dark-100">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
              <span className="text-sm font-medium text-success">Bot Ativo</span>
            </div>
            <p className="text-xs text-gray-500">
              Elite v2.0 • 6 Estratégias
            </p>
          </div>
        </div>
      )}
    </aside>
  )
}
