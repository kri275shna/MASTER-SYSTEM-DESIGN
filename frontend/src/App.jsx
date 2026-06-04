import React, { useState, useEffect, useCallback } from 'react'
import { Radio, LogOut, Play, Settings, AlertTriangle, ShieldCheck } from 'lucide-react'
import { useWebsocket } from './hooks/useWebsocket'
import StoreOverview from './components/StoreOverview'
import VisitorMetrics from './components/VisitorMetrics'
import FunnelAnalytics from './components/FunnelAnalytics'
import HeatmapView from './components/HeatmapView'
import AnomaliesPanel from './components/AnomaliesPanel'
import FeedHealth from './components/FeedHealth'

const API_HOST = (typeof process !== 'undefined' && process.env && process.env.NEXT_PUBLIC_API_URL) || 
                 (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
                   ? 'https://master-system-design.onrender.com'
                   : 'http://localhost:8000')
const DEFAULT_STORE_ID = 'store-mumbai-01'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token') || '')
  const [userRole, setUserRole] = useState(localStorage.getItem('user_role') || '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [isLoggingIn, setIsLoggingIn] = useState(false)

  // Dashboard Stats States
  const [storeId, setStoreId] = useState(DEFAULT_STORE_ID)
  const [metrics, setMetrics] = useState(null)
  const [funnel, setFunnel] = useState(null)
  const [heatmap, setHeatmap] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [cameras, setCameras] = useState([])
  const [recentEvents, setRecentEvents] = useState([])
  
  // Simulation trigger status
  const [simulationStatus, setSimulationStatus] = useState('Idle')

  // Auth Headers helper
  const getHeaders = useCallback(() => {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    }
  }, [token])

  // Fetch all dashboard stats
  const fetchDashboardData = useCallback(async () => {
    if (!token) return
    try {
      const headers = getHeaders()
      
      // 1. Fetch Store Metrics
      const mResp = await fetch(`${API_HOST}/api/v1/stores/${storeId}/metrics`, { headers })
      if (mResp.ok) setMetrics(await mResp.json())
      
      // 2. Fetch Funnel
      const fResp = await fetch(`${API_HOST}/api/v1/stores/${storeId}/funnel`, { headers })
      if (fResp.ok) setFunnel(await fResp.json())
      
      // 3. Fetch Heatmap
      const hResp = await fetch(`${API_HOST}/api/v1/stores/${storeId}/heatmap`, { headers })
      if (hResp.ok) setHeatmap(await hResp.json())
      
      // 4. Fetch Anomalies
      const aResp = await fetch(`${API_HOST}/api/v1/stores/${storeId}/anomalies`, { headers })
      if (aResp.ok) setAnomalies(await aResp.json())

      // 5. Fetch Cameras
      const cResp = await fetch(`${API_HOST}/api/v1/stores/${storeId}/cameras`, { headers })
      if (cResp.ok) setCameras(await cResp.json())
      
    } catch (err) {
      console.error('Failed to load store data:', err)
    }
  }, [token, storeId, getHeaders])

  useEffect(() => {
    if (token) {
      fetchDashboardData()
    }
  }, [token, fetchDashboardData])

  // Handle Event from WebSocket stream
  const handleWebSocketEvent = useCallback((event) => {
    console.log('Received WebSocket Realtime Event:', event)
    
    // Add to recent event ticker list (keep last 5)
    setRecentEvents(prev => {
      const updated = [event, ...prev]
      return updated.slice(0, 5)
    })

    // If a new anomaly alert is streamed, prepend it to active list
    if (event.event_type === 'ANOMALY_ALERT') {
      const newAnomaly = event.payload
      setAnomalies(prev => {
        if (prev.find(a => a.id === newAnomaly.id)) return prev
        return [newAnomaly, ...prev]
      })
    } else {
      // Re-fetch metrics and funnel to refresh UI with state consistency
      fetchDashboardData()
    }
  }, [fetchDashboardData])

  // Hook up WebSocket
  const { status: wsStatus } = useWebsocket(token ? storeId : null, handleWebSocketEvent)

  // Resolve Anomaly Action Handler
  const handleResolveAnomaly = async (anomalyId, actionTaken) => {
    try {
      const response = await fetch(`${API_HOST}/api/v1/stores/${storeId}/anomalies/${anomalyId}/resolve?action_taken=${encodeURIComponent(actionTaken)}`, {
        method: 'POST',
        headers: getHeaders()
      })
      if (response.ok) {
        // Remove from list
        setAnomalies(prev => prev.filter(a => a.id !== anomalyId))
        fetchDashboardData()
      } else {
        alert('Failed to resolve anomaly. Check role permissions.')
      }
    } catch (err) {
      console.error('Error resolving anomaly:', err)
    }
  }

  // Handle Login form
  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginError('')
    setIsLoggingIn(true)

    try {
      const response = await fetch(`${API_HOST}/api/v1/auth/login-json`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })

      if (response.ok) {
        const data = await response.json()
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('user_role', data.role)
        setToken(data.access_token)
        setUserRole(data.role)
      } else {
        const err = await response.json()
        setLoginError(err.detail || 'Invalid email or password')
      }
    } catch (err) {
      setLoginError('Could not connect to FastAPI server. Make sure it is running on port 8000.')
    } finally {
      setIsLoggingIn(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_role')
    setToken('')
    setUserRole('')
    setMetrics(null)
    setRecentEvents([])
  }

  // Run mock edge simulator (generates entry/zone/checkout mock loops on backend)
  const triggerSimulation = async () => {
    setSimulationStatus('Running...')
    try {
      const timestamp = new Date().toISOString()
      const seedVisitor = `visitor-sim-${Math.floor(Math.random() * 1000)}`
      
      const headers = getHeaders()
      
      // Send Entry Event
      await fetch(`${API_HOST}/api/v1/events/ingest`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          store_id: storeId,
          camera_id: 'cam-entry',
          event_type: 'ENTRY',
          timestamp,
          payload: { visitor_id: seedVisitor, is_staff: false }
        })
      })

      // Send Zone Enter
      await fetch(`${API_HOST}/api/v1/events/ingest`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          store_id: storeId,
          camera_id: 'cam-cosmetics',
          event_type: 'ZONE_ENTER',
          timestamp,
          payload: { visitor_id: seedVisitor, zone_id: heatmap[1]?.zone_id || 'zone-cosmetics' }
        })
      })

      setSimulationStatus('Event Sequence Dispatched!')
      setTimeout(() => setSimulationStatus('Idle'), 2000)
    } catch (err) {
      setSimulationStatus('Failed to run')
      setTimeout(() => setSimulationStatus('Idle'), 2000)
    }
  }

  // Login Screen Render
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 relative">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purplle-500/10 rounded-full filter blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full filter blur-3xl" />

        <div className="w-full max-w-md glass-panel p-8 relative overflow-hidden">
          <div className="flex flex-col items-center mb-8">
            <span className="text-3xl font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
              <span className="text-purplle-400 bg-purplle-500/10 p-2 rounded-xl">P</span>
              Purplle <span className="text-purplle-400">Store Intel</span>
            </span>
            <p className="text-xs text-slate-400 mt-2 text-center">Store Intelligence & Computer Vision Platform</p>
          </div>

          {loginError && (
            <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs p-3 rounded-lg mb-4 text-center">
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Email Address</label>
              <input 
                type="email" 
                placeholder="admin@purplle.com" 
                className="w-full bg-slate-950 border border-slate-800 focus:border-purplle-500/60 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none transition-all"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Access Password</label>
              <input 
                type="password" 
                placeholder="admin123" 
                className="w-full bg-slate-950 border border-slate-800 focus:border-purplle-500/60 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none transition-all"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <button 
              type="submit" 
              disabled={isLoggingIn}
              className="w-full bg-purplle-600 hover:bg-purplle-500 active:scale-95 text-white py-3 rounded-xl text-sm font-semibold tracking-wide shadow-lg shadow-purplle-500/10 hover:shadow-purplle-500/20 transition-all"
            >
              {isLoggingIn ? 'Verifying access credentials...' : 'Enter System Dashboard'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800/60 text-center">
            <p className="text-[10px] text-slate-500">
              * Seed user emails: <span className="text-slate-400 font-mono">admin@purplle.com</span>, <span className="text-slate-400 font-mono">analyst@purplle.com</span>, <span className="text-slate-400 font-mono">viewer@purplle.com</span>. Passwords match username (e.g. <span className="text-slate-400 font-mono">admin123</span>).
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Dashboard Screen Render
  return (
    <div className="min-h-screen pb-12">
      {/* Navigation Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="text-xl font-extrabold text-white tracking-wider flex items-center gap-2">
              <span className="text-purplle-400 bg-purplle-500/10 px-2 py-0.5 rounded-lg border border-purplle-500/25">P</span>
              Purplle
            </span>
            <div className="hidden sm:flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl">
              <span className="text-xs font-semibold text-slate-400">Viewing Store:</span>
              <span className="text-xs font-bold text-white uppercase">{storeId.split('-')[1] || storeId}</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Simulation controls */}
            <button 
              onClick={triggerSimulation}
              disabled={simulationStatus !== 'Idle'}
              className="flex items-center gap-1.5 bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 hover:border-indigo-500/40 text-indigo-400 text-xs font-semibold px-3 py-1.5 rounded-xl transition-all"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{simulationStatus === 'Idle' ? 'Dispatch Mock Entry' : simulationStatus}</span>
            </button>

            {/* Connection Status badge */}
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold ${
              wsStatus === 'CONNECTED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse'
            }`}>
              <Radio className="w-3.5 h-3.5 animate-pulse" />
              <span>{wsStatus}</span>
            </div>

            <div className="border-l border-slate-800 h-6 mx-2" />

            <div className="flex items-center gap-3">
              <div className="hidden md:block text-right">
                <p className="text-xs font-semibold text-white">System User</p>
                <p className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">{userRole}</p>
              </div>
              <button 
                onClick={handleLogout}
                className="p-2 bg-slate-900 border border-slate-800 hover:border-rose-500/30 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 rounded-xl transition-all"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Dashboard Layout */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 space-y-6">
        
        {/* Real-time event feed ticker */}
        {recentEvents.length > 0 && (
          <div className="glass-panel p-4 flex items-center gap-4 overflow-hidden relative border-indigo-500/15">
            <span className="text-[10px] uppercase font-black tracking-widest text-indigo-400 bg-indigo-500/10 px-2 py-1 rounded border border-indigo-500/25 flex-shrink-0 animate-pulse">
              Live Stream Feed
            </span>
            <div className="flex items-center gap-6 overflow-x-auto text-xs whitespace-nowrap scrollbar-none w-full">
              {recentEvents.map((evt, idx) => (
                <div key={idx} className="flex items-center gap-2 bg-slate-900/60 border border-slate-800/80 px-3 py-1 rounded-lg">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" />
                  <span className="font-semibold text-white">{evt.event_type}</span>
                  <span className="text-slate-500">for visitor</span>
                  <span className="font-mono text-slate-300">{evt.payload?.visitor_id || 'unknown'}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 1: Store Overview Cards */}
        {metrics && <StoreOverview metrics={metrics} wsStatus={wsStatus} />}

        {/* Section 2: Charts and Funnel side-by-side */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {metrics && <VisitorMetrics metrics={metrics} />}
          </div>
          <div>
            {funnel && <FunnelAnalytics funnel={funnel} />}
          </div>
        </div>

        {/* Section 3: Heatmap blueprint and Anomalies list */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <HeatmapView heatmap={heatmap} />
          <AnomaliesPanel anomalies={anomalies} onResolve={handleResolveAnomaly} />
        </div>

        {/* Section 4: AI Cameras details */}
        <FeedHealth cameras={cameras} />
        
      </main>
    </div>
  )
}
