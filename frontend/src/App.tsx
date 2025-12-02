import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './pages/Dashboard'
import Positions from './pages/Positions'
import History from './pages/History'
import Strategies from './pages/Strategies'
import Settings from './pages/Settings'
import { useWebSocket } from './hooks/useWebSocket'
import config from './config'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { connected, data } = useWebSocket(config.WS_URL)
  
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
        
        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header 
            connected={connected} 
            account={data?.account}
            onMenuClick={() => setSidebarOpen(!sidebarOpen)} 
          />
          
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/" element={<Dashboard data={data} />} />
              <Route path="/positions" element={<Positions positions={data?.positions || []} />} />
              <Route path="/history" element={<History />} />
              <Route path="/strategies" element={<Strategies />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}

export default App
