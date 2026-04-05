import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runAgent } from '../../../api/client'
import { Cpu, Wifi, WifiOff, AlertTriangle, CheckCircle2, Loader2, Zap, HardDrive } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Device {
  id: string
  name: string
  mcu: string
  firmwareVersion: string
  bootloaderVersion: string
  status: 'online' | 'offline' | 'needs-update' | 'error'
  lastSeen: string
  bleStatus: 'connected' | 'disconnected' | 'pairing'
  flashCount: number
  notes?: string
}

// Placeholder data — in production these come from device management API
const PLACEHOLDER_DEVICES: Device[] = [
  { id: 'DFS-001', name: 'Unit Alpha-1', mcu: 'STM32H743', firmwareVersion: 'v2.4.1', bootloaderVersion: 'v1.2.0', status: 'online', lastSeen: '2026-03-12T14:32:00Z', bleStatus: 'connected', flashCount: 47 },
  { id: 'DFS-002', name: 'Unit Alpha-2', mcu: 'STM32H743', firmwareVersion: 'v2.4.1', bootloaderVersion: 'v1.2.0', status: 'online', lastSeen: '2026-03-12T14:30:00Z', bleStatus: 'connected', flashCount: 45 },
  { id: 'DFS-003', name: 'Unit Beta-1', mcu: 'STM32H743', firmwareVersion: 'v2.3.8', bootloaderVersion: 'v1.2.0', status: 'needs-update', lastSeen: '2026-03-12T14:28:00Z', bleStatus: 'connected', flashCount: 52, notes: 'Pending firmware update to v2.4.1' },
  { id: 'DFS-004', name: 'Unit Beta-2', mcu: 'STM32H743', firmwareVersion: 'v2.4.0', bootloaderVersion: 'v1.1.3', status: 'needs-update', lastSeen: '2026-03-12T13:15:00Z', bleStatus: 'disconnected', flashCount: 39, notes: 'Bootloader update needed' },
  { id: 'DFS-005', name: 'Unit Gamma-1', mcu: 'STM32H743', firmwareVersion: 'v2.4.1', bootloaderVersion: 'v1.2.0', status: 'error', lastSeen: '2026-03-12T09:45:00Z', bleStatus: 'disconnected', flashCount: 61, notes: 'Flash write failure on last update attempt' },
  { id: 'DFS-006', name: 'Unit Gamma-2', mcu: 'STM32H743', firmwareVersion: 'v2.4.1', bootloaderVersion: 'v1.2.0', status: 'offline', lastSeen: '2026-03-11T18:20:00Z', bleStatus: 'disconnected', flashCount: 33 },
  { id: 'DFS-007', name: 'Dev Board', mcu: 'STM32H743', firmwareVersion: 'v2.5.0-dev', bootloaderVersion: 'v1.2.0', status: 'online', lastSeen: '2026-03-12T14:35:00Z', bleStatus: 'pairing', flashCount: 128, notes: 'Development unit — latest firmware' },
]

const STATUS_CONFIG = {
  online:        { label: 'Online',       icon: CheckCircle2, color: 'text-orange-600',  bg: 'bg-orange-50 border-orange-200' },
  offline:       { label: 'Offline',      icon: WifiOff,      color: 'text-gray-500',   bg: 'bg-gray-50 border-gray-200' },
  'needs-update':{ label: 'Needs Update', icon: AlertTriangle,color: 'text-amber-600',  bg: 'bg-amber-50 border-amber-200' },
  error:         { label: 'Error',        icon: AlertTriangle,color: 'text-red-600',    bg: 'bg-red-50 border-red-200' },
}

const BLE_CONFIG = {
  connected:    { label: 'BLE Connected',   color: 'text-blue-600' },
  disconnected: { label: 'BLE Disconnected', color: 'text-gray-400' },
  pairing:      { label: 'BLE Pairing',     color: 'text-amber-500' },
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function DeviceFleet() {
  const [filter, setFilter] = useState<string>('all')
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [diagResult, setDiagResult] = useState<string | null>(null)

  const diagMutation = useMutation({
    mutationFn: (device: Device) =>
      runAgent('firmware_engineer',
        `Diagnose this device: ${device.id} (${device.name}). MCU: ${device.mcu}, Firmware: ${device.firmwareVersion}, Bootloader: ${device.bootloaderVersion}, Status: ${device.status}, BLE: ${device.bleStatus}, Flash count: ${device.flashCount}. ${device.notes ? 'Notes: ' + device.notes : ''}`,
        'Target firmware is v2.4.1 with bootloader v1.2.0. Flash write failures may indicate NAND degradation or power supply issues during write.'),
    onSuccess: (data) => setDiagResult(data.analysis),
  })

  const counts = {
    online: PLACEHOLDER_DEVICES.filter(d => d.status === 'online').length,
    offline: PLACEHOLDER_DEVICES.filter(d => d.status === 'offline').length,
    'needs-update': PLACEHOLDER_DEVICES.filter(d => d.status === 'needs-update').length,
    error: PLACEHOLDER_DEVICES.filter(d => d.status === 'error').length,
  }

  const filtered = filter === 'all' ? PLACEHOLDER_DEVICES : PLACEHOLDER_DEVICES.filter(d => d.status === filter)

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-xl font-semibold text-gray-800">Device Fleet</h2>
        <p className="text-sm text-gray-500 mt-0.5">Monitor firmware versions, device health, and flash history</p>
      </div>

      {/* Status summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {(Object.entries(counts) as [keyof typeof STATUS_CONFIG, number][]).map(([status, count]) => {
          const cfg = STATUS_CONFIG[status]
          const Icon = cfg.icon
          return (
            <button
              key={status}
              onClick={() => setFilter(f => f === status ? 'all' : status)}
              className={`rounded-lg border p-3 text-left transition-colors ${
                filter === status ? cfg.bg + ' border-2' : 'bg-white border-gray-200 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon size={14} className={cfg.color} />
                <span className="text-xs font-medium text-gray-500 uppercase">{cfg.label}</span>
              </div>
              <div className="text-2xl font-bold text-gray-800">{count}</div>
            </button>
          )
        })}
      </div>

      {/* Device list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-600">
            {filter === 'all' ? 'All Devices' : STATUS_CONFIG[filter as keyof typeof STATUS_CONFIG]?.label}
            <span className="text-gray-400 font-normal ml-2">({filtered.length})</span>
          </h3>
          <span className="text-xs text-gray-400">Target: FW v2.4.1 / BL v1.2.0</span>
        </div>

        <div className="divide-y divide-gray-100">
          {filtered.map(device => {
            const cfg = STATUS_CONFIG[device.status]
            const Icon = cfg.icon
            const ble = BLE_CONFIG[device.bleStatus]
            const isSelected = selectedDevice?.id === device.id
            const isOutdatedFW = device.firmwareVersion !== 'v2.4.1' && !device.firmwareVersion.includes('dev')
            const isOutdatedBL = device.bootloaderVersion !== 'v1.2.0'

            return (
              <div
                key={device.id}
                className={`px-5 py-4 hover:bg-gray-50 cursor-pointer transition-colors ${isSelected ? 'bg-orange-50' : ''}`}
                onClick={() => { setSelectedDevice(isSelected ? null : device); setDiagResult(null) }}
              >
                <div className="flex items-center gap-4">
                  <Cpu size={20} className="text-orange-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800">{device.id}</span>
                      <span className="text-xs text-gray-400">{device.name}</span>
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${cfg.bg}`}>
                        <Icon size={10} className={cfg.color} />
                        {cfg.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span className={isOutdatedFW ? 'text-amber-600 font-medium' : ''}>FW {device.firmwareVersion}</span>
                      <span className="text-gray-300">|</span>
                      <span className={isOutdatedBL ? 'text-amber-600 font-medium' : ''}>BL {device.bootloaderVersion}</span>
                      <span className="text-gray-300">|</span>
                      <span className={ble.color}>{ble.label}</span>
                      <span className="text-gray-300">|</span>
                      <span><Zap size={10} className="inline" /> {device.flashCount} flashes</span>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 shrink-0">
                    {new Date(device.lastSeen).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {device.notes && !isSelected && (
                  <div className="ml-9 mt-1 text-xs text-amber-600">{device.notes}</div>
                )}

                {/* Expanded detail */}
                {isSelected && (
                  <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div><span className="text-gray-500">MCU:</span> <span className="font-medium">{device.mcu}</span></div>
                      <div><span className="text-gray-500">Firmware:</span> <span className={`font-medium ${isOutdatedFW ? 'text-amber-600' : 'text-orange-600'}`}>{device.firmwareVersion}</span></div>
                      <div><span className="text-gray-500">Bootloader:</span> <span className={`font-medium ${isOutdatedBL ? 'text-amber-600' : ''}`}>{device.bootloaderVersion}</span></div>
                      <div><span className="text-gray-500">Flash Count:</span> <span className="font-medium">{device.flashCount}</span></div>
                    </div>
                    {device.notes && (
                      <div className="text-xs bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-amber-700">
                        {device.notes}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); diagMutation.mutate(device) }}
                        disabled={diagMutation.isPending}
                        className="flex items-center gap-1.5 text-xs bg-orange-600 hover:bg-orange-700 disabled:opacity-50
                                   text-white px-3 py-1.5 rounded-lg transition-colors"
                      >
                        {diagMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <HardDrive size={12} />}
                        {diagMutation.isPending ? 'Diagnosing...' : 'AI Diagnostics'}
                      </button>
                    </div>
                    {diagResult && isSelected && (
                      <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-xs text-orange-800 whitespace-pre-wrap">
                        {diagResult}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Info */}
      <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 text-xs text-orange-700 space-y-1">
        <p className="font-semibold">Device Fleet</p>
        <p>Devices shown here are placeholders. Connect to your device management system or J-Link server to populate automatically.</p>
        <p>Use <strong>AI Diagnostics</strong> to get firmware engineering analysis for any device issue.</p>
      </div>
    </div>
  )
}
