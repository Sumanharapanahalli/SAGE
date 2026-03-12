import { Cpu, Wifi, WifiOff, AlertTriangle, CheckCircle2, Zap, HardDrive, Terminal } from 'lucide-react'

/**
 * DFS-specific dashboard widgets — device fleet status,
 * firmware versions, and hardware health overview.
 */
export default function DFSDashboard() {
  // In production, these would come from a device management API
  const fleet = {
    total: 7, online: 3, offline: 1, needsUpdate: 2, error: 1,
  }

  const firmware = {
    latest: 'v2.4.1',
    bootloader: 'v1.2.0',
    devBranch: 'v2.5.0-dev',
    upToDate: 3,
    outdated: 3,
  }

  const hardware = {
    mcu: 'STM32H743',
    interface: 'SWD / J-Link',
    serial: 'UART (115200)',
    bleDevices: 4,
  }

  const recentAlerts = [
    { severity: 'RED', text: 'DFS-005: Flash write failure on last update', time: '5h ago' },
    { severity: 'AMBER', text: 'DFS-003, DFS-004: Firmware update pending', time: '1h ago' },
    { severity: 'GREEN', text: 'DFS-007: Dev firmware v2.5.0-dev flashed OK', time: '20m ago' },
  ]

  return (
    <div className="space-y-4">
      {/* Fleet overview */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <HardDrive size={16} className="text-orange-500" />
          <h3 className="text-sm font-semibold text-gray-700">Device Fleet</h3>
          <span className="text-xs text-gray-400 ml-auto">{fleet.total} devices</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-green-50 rounded-lg p-3 text-center">
            <CheckCircle2 size={14} className="text-green-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800">{fleet.online}</div>
            <div className="text-xs text-gray-500">Online</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <WifiOff size={14} className="text-gray-400 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800">{fleet.offline}</div>
            <div className="text-xs text-gray-500">Offline</div>
          </div>
          <div className="bg-amber-50 rounded-lg p-3 text-center">
            <AlertTriangle size={14} className="text-amber-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800">{fleet.needsUpdate}</div>
            <div className="text-xs text-gray-500">Needs Update</div>
          </div>
          <div className="bg-red-50 rounded-lg p-3 text-center">
            <AlertTriangle size={14} className="text-red-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800">{fleet.error}</div>
            <div className="text-xs text-gray-500">Error</div>
          </div>
        </div>
        <a href="/devices" className="block text-xs text-orange-600 hover:text-orange-700 mt-2 font-medium">View all devices &rarr;</a>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Firmware versions */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Cpu size={16} className="text-orange-500" />
            <h3 className="text-sm font-semibold text-gray-700">Firmware</h3>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
              <span className="text-xs text-gray-600">Latest release</span>
              <span className="text-sm font-bold text-green-600 font-mono">{firmware.latest}</span>
            </div>
            <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
              <span className="text-xs text-gray-600">Bootloader</span>
              <span className="text-sm font-bold text-gray-800 font-mono">{firmware.bootloader}</span>
            </div>
            <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
              <span className="text-xs text-gray-600">Dev branch</span>
              <span className="text-sm font-bold text-blue-600 font-mono">{firmware.devBranch}</span>
            </div>
            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-green-600">{firmware.upToDate} up to date</span>
              <span className="text-xs text-amber-600">{firmware.outdated} outdated</span>
            </div>
          </div>
        </div>

        {/* Hardware info + recent alerts */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Terminal size={16} className="text-orange-500" />
            <h3 className="text-sm font-semibold text-gray-700">Recent Alerts</h3>
          </div>
          <div className="space-y-2">
            {recentAlerts.map((alert, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded shrink-0 mt-0.5 ${
                  alert.severity === 'RED' ? 'bg-red-100 text-red-700' :
                  alert.severity === 'AMBER' ? 'bg-amber-100 text-amber-700' :
                  'bg-green-100 text-green-700'
                }`}>{alert.severity}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-gray-700">{alert.text}</div>
                  <div className="text-xs text-gray-400">{alert.time}</div>
                </div>
              </div>
            ))}
          </div>
          <a href="/serial" className="block text-xs text-orange-600 hover:text-orange-700 mt-2 font-medium">Open Serial Console &rarr;</a>
        </div>
      </div>
    </div>
  )
}
