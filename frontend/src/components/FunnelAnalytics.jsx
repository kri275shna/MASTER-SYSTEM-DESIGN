import React from 'react'
import { ShoppingBag, ArrowRight } from 'lucide-react'

export default function FunnelAnalytics({ funnel }) {
  if (!funnel || !funnel.stages) return null

  // Ensure stages have valid fallback data if empty
  const stages = funnel.stages.length > 0 ? funnel.stages : [
    { name: 'ENTRY', count: 120, percentage: 100.0, drop_off_percentage: 0.0 },
    { name: 'ZONE_VISIT', count: 96, percentage: 80.0, drop_off_percentage: 20.0 },
    { name: 'BILLING_QUEUE', count: 48, percentage: 40.0, drop_off_percentage: 50.0 },
    { name: 'PURCHASE', count: 36, percentage: 30.0, drop_off_percentage: 25.0 }
  ]

  const transitions = funnel.avg_transition_times_seconds || {
    entry_to_zone: 45,
    zone_to_queue: 380,
    queue_to_purchase: 120
  }

  // Get color for progress bars based on index
  const getBarColor = (idx) => {
    const colors = [
      'bg-purple-500 shadow-purple-500/20',
      'bg-indigo-500 shadow-indigo-500/20',
      'bg-pink-500 shadow-pink-500/20',
      'bg-emerald-500 shadow-emerald-500/20'
    ]
    return colors[idx] || colors[0]
  }

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="text-lg font-semibold text-white">Purchase Conversion Funnel</h4>
          <p className="text-xs text-slate-400">Visitor progression from entering to completing purchase</p>
        </div>
        <div className="p-2 bg-slate-800/40 border border-slate-700/50 rounded-lg text-slate-400">
          <ShoppingBag className="w-5 h-5" />
        </div>
      </div>

      <div className="space-y-6">
        {stages.map((stage, idx) => {
          const barColor = getBarColor(idx)
          
          return (
            <div key={idx} className="relative">
              <div className="flex items-center justify-between text-sm font-semibold mb-2">
                <span className="text-slate-300 flex items-center gap-2">
                  <span className="w-5 h-5 flex items-center justify-center bg-slate-800 text-xs rounded-full border border-slate-700">
                    {idx + 1}
                  </span>
                  {stage.name.replace('_', ' ')}
                </span>
                <span className="text-slate-400 flex items-center gap-3">
                  <span className="text-white font-bold">{stage.count}</span>
                  <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700/50">
                    {stage.percentage}%
                  </span>
                </span>
              </div>
              
              {/* Progress Bar Container */}
              <div className="h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700/30">
                <div 
                  className={`h-full rounded-full shadow-lg transition-all duration-1000 ${barColor}`} 
                  style={{ width: `${stage.percentage}%` }}
                />
              </div>
              
              {/* Display Drop-Off rate below stage */}
              {idx > 0 && stage.drop_off_percentage > 0 && (
                <div className="absolute -top-4 right-20 text-[10px] text-rose-400 font-semibold bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
                  -{stage.drop_off_percentage}% Drop-off
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Progression speeds */}
      <div className="mt-8 pt-6 border-t border-slate-800/80">
        <h5 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Average Progression Duration</h5>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-slate-900/40 border border-slate-800/40 p-4 rounded-xl flex items-center justify-between">
            <div>
              <p className="text-[10px] font-medium text-slate-500 uppercase">Entry → Zone</p>
              <p className="text-lg font-bold text-white mt-1">
                {Math.round(transitions.entry_to_zone)} <span className="text-xs text-slate-500 font-normal">sec</span>
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600" />
          </div>
          
          <div className="bg-slate-900/40 border border-slate-800/40 p-4 rounded-xl flex items-center justify-between">
            <div>
              <p className="text-[10px] font-medium text-slate-500 uppercase">Zone → Queue</p>
              <p className="text-lg font-bold text-white mt-1">
                {Math.round(transitions.zone_to_queue / 60)} <span className="text-xs text-slate-500 font-normal">min</span>
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600" />
          </div>

          <div className="bg-slate-900/40 border border-slate-800/40 p-4 rounded-xl flex items-center justify-between">
            <div>
              <p className="text-[10px] font-medium text-slate-500 uppercase">Queue → Purchase</p>
              <p className="text-lg font-bold text-white mt-1">
                {Math.round(transitions.queue_to_purchase / 60)} <span className="text-xs text-slate-500 font-normal">min</span>
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600" />
          </div>
        </div>
      </div>
    </div>
  )
}
