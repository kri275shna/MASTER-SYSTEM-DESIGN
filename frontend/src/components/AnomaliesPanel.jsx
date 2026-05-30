import React, { useState } from 'react'
import { AlertOctagon, AlertTriangle, ShieldCheck, CheckCircle2, ChevronRight } from 'lucide-react'

export default function AnomaliesPanel({ anomalies, onResolve }) {
  const [resolvingId, setResolvingId] = useState(null)
  const [actionText, setActionText] = useState('')

  const getSeverityStyle = (severity) => {
    if (severity === 'Critical') {
      return 'border-rose-500/35 bg-rose-500/10 text-rose-400'
    }
    return 'border-amber-500/30 bg-amber-500/5 text-amber-400'
  }

  const getSeverityIcon = (severity) => {
    if (severity === 'Critical') {
      return <AlertOctagon className="w-5 h-5 text-rose-400 animate-pulse" />
    }
    return <AlertTriangle className="w-5 h-5 text-amber-400" />
  }

  const handleSubmitResolve = (e, anomalyId) => {
    e.preventDefault()
    if (!actionText.trim()) return
    onResolve(anomalyId, actionText)
    setActionText('')
    setResolvingId(null)
  }

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="text-lg font-semibold text-white">Active Operational Anomalies</h4>
          <p className="text-xs text-slate-400">Triggered dynamically by store tracking metrics</p>
        </div>
        <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
          anomalies.length > 0 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
        }`}>
          {anomalies.length > 0 ? (
            <>
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{anomalies.length} Alerts Active</span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Operations Secure</span>
            </>
          )}
        </div>
      </div>

      {anomalies.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 border border-dashed border-slate-800 rounded-xl bg-slate-900/10">
          <CheckCircle2 className="w-12 h-12 text-emerald-500/40 mb-3" />
          <p className="text-sm font-medium text-slate-300">All store systems normal</p>
          <p className="text-xs text-slate-500 mt-1">No anomalies flagged in this period</p>
        </div>
      ) : (
        <div className="space-y-4">
          {anomalies.map((a) => (
            <div 
              key={a.id} 
              className={`p-4 rounded-xl border flex flex-col md:flex-row justify-between gap-4 items-start md:items-center transition-all ${getSeverityStyle(a.severity)}`}
            >
              <div className="flex gap-3 items-start">
                <div className="mt-0.5">{getSeverityIcon(a.severity)}</div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase font-extrabold tracking-wider bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800/40">
                      {a.anomaly_type.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(a.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-white mt-1.5">{a.message}</p>
                </div>
              </div>

              {/* Action buttons */}
              <div className="w-full md:w-auto">
                {resolvingId === a.id ? (
                  <form onSubmit={(e) => handleSubmitResolve(e, a.id)} className="flex items-center gap-2 w-full">
                    <input 
                      type="text" 
                      placeholder="Resolution action..." 
                      className="bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purplle-500/60"
                      value={actionText}
                      onChange={(e) => setActionText(e.target.value)}
                      required
                    />
                    <button 
                      type="submit"
                      className="bg-purplle-600 hover:bg-purplle-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
                    >
                      Log
                    </button>
                    <button 
                      type="button"
                      className="text-slate-400 hover:text-white text-xs px-2"
                      onClick={() => setResolvingId(null)}
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <button 
                    className="w-full md:w-auto flex items-center justify-center gap-1.5 bg-slate-950/60 hover:bg-slate-950 border border-slate-800 text-xs font-semibold px-4 py-2 rounded-lg text-slate-300 hover:text-white transition-all"
                    onClick={() => setResolvingId(a.id)}
                  >
                    <span>Acknowledge</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
