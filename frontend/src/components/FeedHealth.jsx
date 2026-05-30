import React from 'react'
import { Camera, CheckCircle, AlertTriangle, Link2 } from 'lucide-react'

export default function FeedHealth({ cameras }) {
  // Setup default mock cameras if list is empty
  const cameraList = cameras && cameras.length > 0 ? cameras : [
    { id: '1', name: 'Main Entrance Cam', ip_address: '192.168.1.50', stream_url: 'rtsp://192.168.1.50:554/live', status: 'Active' },
    { id: '2', name: 'Cosmetics Lane Cam', ip_address: '192.168.1.51', stream_url: 'rtsp://192.168.1.51:554/live', status: 'Active' },
    { id: '3', name: 'Billing Desk 1 Cam', ip_address: '192.168.1.52', stream_url: 'rtsp://192.168.1.52:554/live', status: 'Active' },
    { id: '4', name: 'Checkout Queue Cam', ip_address: '192.168.1.53', stream_url: 'rtsp://192.168.1.53:554/live', status: 'Active' }
  ]

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="text-lg font-semibold text-white">CCTV Feed & Camera Health</h4>
          <p className="text-xs text-slate-400">Status logs of Edge AI tracking nodes</p>
        </div>
        <div className="p-2 bg-slate-800/40 border border-slate-700/50 rounded-lg text-slate-400">
          <Camera className="w-5 h-5" />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-900/50 text-slate-400 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-800">
            <tr>
              <th className="py-3 px-4 rounded-tl-lg">Feed Name</th>
              <th className="py-3 px-4">IP Address</th>
              <th className="py-3 px-4">Stream RTSP Address</th>
              <th className="py-3 px-4 rounded-tr-lg">AI Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {cameraList.map((cam) => (
              <tr key={cam.id} className="hover:bg-slate-900/30 transition-all">
                <td className="py-3 px-4 font-semibold text-white flex items-center gap-2">
                  <Camera className="w-3.5 h-3.5 text-slate-500" />
                  {cam.name}
                </td>
                <td className="py-3 px-4 text-slate-400 font-mono">{cam.ip_address}</td>
                <td className="py-3 px-4 text-slate-500 font-mono flex items-center gap-1.5 max-w-xs truncate">
                  <Link2 className="w-3 h-3 text-slate-600 flex-shrink-0" />
                  <span className="truncate">{cam.stream_url}</span>
                </td>
                <td className="py-3 px-4">
                  <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                    cam.status === 'Active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                  }`}>
                    {cam.status === 'Active' ? (
                      <>
                        <CheckCircle className="w-2.5 h-2.5" />
                        <span>ACTIVE</span>
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-2.5 h-2.5" />
                        <span>OFFLINE</span>
                      </>
                    )}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
