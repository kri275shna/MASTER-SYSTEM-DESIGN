import React from 'react'
import { Users, TrendingUp, HelpCircle, AlertCircle, Radio } from 'lucide-react'

export default function StoreOverview({ metrics, wsStatus }) {
  if (!metrics) return null

  const stats = [
    {
      name: 'Conversion Rate',
      value: `${metrics.conversion_rate}%`,
      icon: TrendingUp,
      desc: 'Offline store checkout rate',
      color: 'text-emerald-400 bg-emerald-500/10'
    },
    {
      name: 'Unique Visitors',
      value: metrics.unique_visitors,
      icon: Users,
      desc: 'Total unique foot traffic',
      color: 'text-purplle-400 bg-purplle-500/10'
    },
    {
      name: 'Queue Depth',
      value: metrics.queue_depth,
      icon: HelpCircle,
      desc: 'Active customers waiting to checkout',
      color: metrics.queue_depth >= 7 ? 'text-rose-400 bg-rose-500/10' : 'text-amber-400 bg-amber-500/10'
    },
    {
      name: 'Queue Abandon Rate',
      value: `${metrics.queue_abandonment_rate}%`,
      icon: AlertCircle,
      desc: 'Customers leaving checkout queue',
      color: metrics.queue_abandonment_rate > 20 ? 'text-rose-400 bg-rose-500/10' : 'text-slate-400 bg-slate-500/10'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((s, idx) => {
        const Icon = s.icon
        return (
          <div key={idx} className="glass-panel p-6 relative overflow-hidden group">
            {/* Background Glow */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-purplle-500/10 to-transparent rounded-full filter blur-xl transition-all duration-500 group-hover:scale-125" />
            
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-400">{s.name}</p>
                <h3 className="text-3xl font-bold tracking-tight text-white mt-1 group-hover:scale-105 transition-all duration-300 origin-left">
                  {s.value}
                </h3>
              </div>
              <div className={`p-3 rounded-xl ${s.color}`}>
                <Icon className="w-6 h-6" />
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-4 flex items-center gap-1">
              <span>{s.desc}</span>
            </p>
          </div>
        )
      })}
    </div>
  )
}
