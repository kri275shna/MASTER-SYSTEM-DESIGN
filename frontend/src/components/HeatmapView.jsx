import React from 'react'
import { LayoutGrid, Users, Clock } from 'lucide-react'

export default function HeatmapView({ heatmap }) {
  // Ensure we have some default layout elements if heatmap is empty
  const zones = heatmap && heatmap.length > 0 ? heatmap : [
    { zone_id: '1', zone_name: 'Entrance Zone', visitor_count: 120, avg_dwell_time_seconds: 15.2 },
    { zone_id: '2', zone_name: 'Cosmetics Section', visitor_count: 96, avg_dwell_time_seconds: 320.5 },
    { zone_id: '3', zone_name: 'Billing Queue Zone', visitor_count: 48, avg_dwell_time_seconds: 180.1 },
    { zone_id: '4', zone_name: 'Skin Care Section', visitor_count: 75, avg_dwell_time_seconds: 245.3 }
  ]

  // Get max visitor count to compute relative density color
  const maxVisitorCount = Math.max(...zones.map(z => z.visitor_count), 1)

  // Returns tailwind color classes based on density
  const getDensityColor = (count) => {
    const ratio = count / maxVisitorCount
    if (ratio > 0.8) return 'bg-purplle-500/25 border-purplle-500/60 shadow-purplle-500/10'
    if (ratio > 0.5) return 'bg-indigo-500/20 border-indigo-500/50 shadow-indigo-500/5'
    if (ratio > 0.2) return 'bg-slate-800/60 border-slate-700/50'
    return 'bg-slate-900/30 border-slate-800/30'
  }

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="text-lg font-semibold text-white">Zone Heatmap & Dwell Analysis</h4>
          <p className="text-xs text-slate-400">Visitor volume densities and average attention span per zone</p>
        </div>
        <div className="p-2 bg-slate-800/40 border border-slate-700/50 rounded-lg text-slate-400">
          <LayoutGrid className="w-5 h-5" />
        </div>
      </div>

      {/* Visual Map Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {zones.map((zone, idx) => {
          const densityClass = getDensityColor(zone.visitor_count)
          
          return (
            <div 
              key={zone.zone_id || idx} 
              className={`p-5 rounded-xl border flex flex-col justify-between h-36 relative overflow-hidden transition-all duration-300 ${densityClass}`}
            >
              {/* Density indicator dot */}
              <div className="absolute top-4 right-4 flex items-center gap-1.5">
                <span className={`w-2.5 h-2.5 rounded-full ${
                  zone.visitor_count / maxVisitorCount > 0.7 ? 'bg-rose-500 animate-pulse' :
                  zone.visitor_count / maxVisitorCount > 0.4 ? 'bg-amber-500' : 'bg-slate-600'
                }`} />
                <span className="text-[10px] text-slate-400 font-semibold uppercase">
                  {zone.visitor_count / maxVisitorCount > 0.7 ? 'Hot' :
                   zone.visitor_count / maxVisitorCount > 0.4 ? 'Warm' : 'Cool'}
                </span>
              </div>

              <div>
                <h5 className="font-semibold text-white text-sm">{zone.zone_name}</h5>
                <p className="text-[10px] text-slate-400 mt-0.5">Layout Area #{idx + 1}</p>
              </div>

              <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-800/30">
                <div className="flex items-center gap-2">
                  <Users className="w-3.5 h-3.5 text-slate-500" />
                  <div>
                    <p className="text-[9px] text-slate-500 uppercase font-medium">Visitors</p>
                    <p className="text-sm font-bold text-white leading-none mt-0.5">{zone.visitor_count}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-slate-500" />
                  <div>
                    <p className="text-[9px] text-slate-500 uppercase font-medium">Avg Dwell</p>
                    <p className="text-sm font-bold text-white leading-none mt-0.5">
                      {Math.round(zone.avg_dwell_time_seconds)}s
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="bg-slate-900/30 border border-slate-800/50 p-4 rounded-xl flex items-center justify-between">
        <p className="text-xs text-slate-400">
          * Heat intensities are computed dynamically from active Re-ID cameras.
        </p>
        <span className="text-[10px] font-semibold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
          4 Zones Active
        </span>
      </div>
    </div>
  )
}
