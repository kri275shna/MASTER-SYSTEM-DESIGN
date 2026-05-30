import React from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Clock, RefreshCcw } from 'lucide-react'

export default function VisitorMetrics({ metrics }) {
  if (!metrics) return null

  // Format data for chart
  const data = metrics.hourly_traffic && metrics.hourly_traffic.length > 0 
    ? metrics.hourly_traffic.map(item => ({
        ...item,
        // Shorten label for x-axis display
        timeLabel: item.time.split(' ')[1] || item.time
      }))
    : [
        { timeLabel: '09:00', count: 5 },
        { timeLabel: '10:00', count: 12 },
        { timeLabel: '11:00', count: 18 },
        { timeLabel: '12:00', count: 28 },
        { timeLabel: '13:00', count: 22 },
        { timeLabel: '14:00', count: 15 },
        { timeLabel: '15:00', count: 32 }
      ]

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Real-time traffic chart */}
      <div className="glass-panel p-6 lg:col-span-2">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h4 className="text-lg font-semibold text-white">Foot Traffic Trend</h4>
            <p className="text-xs text-slate-400">Visitor entry volumes grouped hourly</p>
          </div>
          <div className="flex items-center gap-2 bg-slate-800/50 rounded-lg px-3 py-1 border border-slate-700/50">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span className="text-xs font-semibold text-slate-300">Live Feed</span>
          </div>
        </div>
        
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#9b5de5" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#9b5de5" stopOpacity={0.01}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="timeLabel" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff', borderRadius: '12px' }}
                labelClassName="text-slate-400 font-medium"
              />
              <Area type="monotone" dataKey="count" name="Visitors" stroke="#9b5de5" strokeWidth={2.5} fillOpacity={1} fill="url(#colorTraffic)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Side stats card */}
      <div className="flex flex-col gap-6">
        <div className="glass-panel p-6 flex-1 flex flex-col justify-between group relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-purplle-500/5 rounded-full filter blur-lg transition-transform group-hover:scale-150" />
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <h5 className="text-sm font-medium text-slate-400">Avg Dwell Time</h5>
              <p className="text-xs text-slate-500">Average time spent inside store</p>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-4xl font-extrabold text-white">
              {Math.round(metrics.avg_dwell_time_seconds / 60)} <span className="text-lg font-medium text-slate-400">mins</span>
            </span>
            <p className="text-xs text-slate-500 mt-2">
              Based on visitor entry-to-exit delta tracking
            </p>
          </div>
        </div>

        <div className="glass-panel p-6 flex-1 flex flex-col justify-between group relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full filter blur-lg transition-transform group-hover:scale-150" />
          <div className="flex items-center gap-4">
            <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400">
              <RefreshCcw className="w-6 h-6" />
            </div>
            <div>
              <h5 className="text-sm font-medium text-slate-400">Repeat Visitors</h5>
              <p className="text-xs text-slate-500">Identified via Re-ID matching</p>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-4xl font-extrabold text-white">
              {metrics.repeat_visitors} <span className="text-lg font-medium text-slate-400">shoppers</span>
            </span>
            <p className="text-xs text-slate-500 mt-2">
              Visitors returning to the store within search bounds
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
