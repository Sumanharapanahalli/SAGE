import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { analyzeLog, type AnalysisResponse } from '../../../api/client'
import { Terminal, Send, Trash2, Download, Loader2, Zap, AlertTriangle } from 'lucide-react'

// ---------------------------------------------------------------------------
// Preset commands for quick access
// ---------------------------------------------------------------------------
const PRESET_COMMANDS = [
  { label: 'Device Info', cmd: 'info', description: 'Read device ID, firmware version, bootloader' },
  { label: 'Status', cmd: 'status', description: 'Current system status and uptime' },
  { label: 'BLE Status', cmd: 'ble status', description: 'BLE connection state and paired devices' },
  { label: 'Flash Info', cmd: 'flash info', description: 'Flash regions, write count, health' },
  { label: 'Task List', cmd: 'task list', description: 'FreeRTOS task list with stack usage' },
  { label: 'Heap Info', cmd: 'heap', description: 'Heap usage and fragmentation' },
  { label: 'Reset', cmd: 'reset', description: 'Soft reset the device' },
  { label: 'Watchdog', cmd: 'wdt status', description: 'Watchdog timer status' },
]

const JLINK_COMMANDS = [
  { label: 'Read RTT', cmd: 'jlink rtt read', description: 'Read SEGGER RTT output buffer' },
  { label: 'Flash Status', cmd: 'jlink flash info', description: 'Flash memory status via SWD' },
  { label: 'Memory Dump', cmd: 'jlink mem 0x08000000 256', description: 'Read 256 bytes from flash start' },
  { label: 'Halt CPU', cmd: 'jlink halt', description: 'Halt CPU for debugging' },
  { label: 'Resume', cmd: 'jlink go', description: 'Resume CPU execution' },
]

interface LogLine {
  timestamp: string
  type: 'cmd' | 'response' | 'error' | 'info'
  text: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function SerialConsole() {
  const [command, setCommand] = useState('')
  const [log, setLog] = useState<LogLine[]>([
    { timestamp: new Date().toISOString(), type: 'info', text: '--- SAGE Serial Console ---' },
    { timestamp: new Date().toISOString(), type: 'info', text: 'Port: not connected (placeholder mode)' },
    { timestamp: new Date().toISOString(), type: 'info', text: 'Type a command or use presets below. Output is simulated in placeholder mode.' },
    { timestamp: new Date().toISOString(), type: 'info', text: 'Connect a real serial port via config/config.yaml → integrations → serial' },
  ])
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log])

  const analyzeMutation = useMutation({
    mutationFn: () => {
      const logText = log.filter(l => l.type !== 'info').map(l => l.text).join('\n')
      return analyzeLog(logText)
    },
    onSuccess: setAnalysisResult,
  })

  const addLog = (type: LogLine['type'], text: string) => {
    setLog(prev => [...prev, { timestamp: new Date().toISOString(), type, text }])
  }

  const sendCommand = (cmd: string) => {
    if (!cmd.trim()) return
    addLog('cmd', `> ${cmd}`)

    // Simulate responses for placeholder mode
    const responses: Record<string, string> = {
      'info': 'Device: DFS-001 (STM32H743)\nFirmware: v2.4.1 (2026-03-10)\nBootloader: v1.2.0\nSerial: DFS-2026-001-A7B3',
      'status': 'Uptime: 14d 7h 23m\nFreeRTOS: Running (7 tasks)\nHeap: 142,384 / 524,288 bytes free\nTemperature: 38.2C\nVoltage: 3.31V',
      'ble status': 'BLE: Connected\nPaired: iPhone-SH (rssi: -42 dBm)\nMTU: 247\nLast sync: 2m ago',
      'flash info': 'Flash: Internal (2MB)\nSector 0-7: Bootloader (locked)\nSector 8-11: Application (v2.4.1)\nSector 12-15: Config + OTA staging\nWrite count: 47\nHealth: OK',
      'task list': 'Task Name       State   Prio  Stack(free)\n-----------------------------------------\nIDLE            Ready   0     240\nTmr Svc         Blocked 2     196\nBLE_Task        Blocked 5     512\nSensor_Task     Running 4     384\nFlash_Task      Blocked 3     448\nUART_Task       Blocked 3     256\nWatchdog        Blocked 6     128',
      'heap': 'Total heap: 524,288 bytes\nFree: 142,384 bytes (27.2%)\nMinimum ever free: 98,512 bytes\nAllocations: 234\nLargest free block: 65,536 bytes\nFragmentation: 12.3%',
      'reset': 'Performing soft reset...\n[OK] System restarting',
      'wdt status': 'Watchdog: Active\nTimeout: 8000ms\nLast kick: 42ms ago\nResets caused: 0',
    }

    // Check for j-link commands
    if (cmd.startsWith('jlink')) {
      const jlinkResponses: Record<string, string> = {
        'jlink rtt read': '[RTT] Channel 0: 1,247 bytes buffered\n[RTT] Sensor_Task: accel_x=0.12 accel_y=-9.78 accel_z=0.34\n[RTT] BLE_Task: notification sent (12 bytes)\n[RTT] Flash_Task: idle',
        'jlink flash info': 'J-Link connected (SN: 123456789)\nTarget: STM32H743 (Cortex-M7)\nFlash: 2048 KB @ 0x08000000\nProtection: RDP Level 0\nOption bytes: default',
        'jlink mem 0x08000000 256': '08000000: 00 40 00 20 C1 04 00 08 D9 04 00 08 DB 04 00 08\n08000010: DD 04 00 08 DF 04 00 08 E1 04 00 08 00 00 00 00\n08000020: 00 00 00 00 00 00 00 00 00 00 00 00 E3 04 00 08\n...(truncated)',
        'jlink halt': 'CPU halted at 0x08004A2C (Sensor_Task)\nRegisters: R0=0x00000012 R1=0x20001A40 PC=0x08004A2C',
        'jlink go': 'CPU resumed.',
      }
      setTimeout(() => {
        const resp = jlinkResponses[cmd] ?? `J-Link: Unknown command '${cmd.replace('jlink ', '')}'`
        addLog('response', resp)
      }, 300)
    } else {
      setTimeout(() => {
        const resp = responses[cmd.toLowerCase()] ?? `Unknown command: ${cmd}\nType 'info' or 'status' for device information.`
        addLog('response', resp)
      }, 150)
    }

    setCommand('')
  }

  const clearLog = () => {
    setLog([{ timestamp: new Date().toISOString(), type: 'info', text: '--- Log cleared ---' }])
    setAnalysisResult(null)
  }

  const exportLog = () => {
    const text = log.map(l => `[${new Date(l.timestamp).toLocaleTimeString()}] ${l.text}`).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `sage-serial-${Date.now()}.log`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Serial Console</h2>
          <p className="text-sm text-gray-500 mt-0.5">UART commands, J-Link operations, and device diagnostics</p>
        </div>
        <div className="flex gap-2">
          <button onClick={clearLog} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors">
            <Trash2 size={14} /> Clear
          </button>
          <button onClick={exportLog} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors">
            <Download size={14} /> Export
          </button>
          <button
            onClick={() => analyzeMutation.mutate()}
            disabled={analyzeMutation.isPending || log.length < 3}
            className="flex items-center gap-1.5 text-xs bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition-colors"
          >
            {analyzeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Analyze Log
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Terminal */}
        <div className="lg:col-span-2 space-y-0">
          <div className="bg-gray-900 rounded-t-xl px-4 py-2 flex items-center gap-2">
            <Terminal size={14} className="text-green-400" />
            <span className="text-xs text-gray-400 font-mono">UART — 115200 baud — placeholder mode</span>
          </div>
          <div className="bg-gray-950 h-80 overflow-y-auto px-4 py-3 font-mono text-sm">
            {log.map((line, i) => (
              <div key={i} className={`leading-relaxed ${
                line.type === 'cmd' ? 'text-green-400' :
                line.type === 'error' ? 'text-red-400' :
                line.type === 'info' ? 'text-gray-500 italic' :
                'text-gray-300'
              }`}>
                {line.text.split('\n').map((l, j) => <div key={j}>{l}</div>)}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
          <div className="bg-gray-900 rounded-b-xl px-4 py-2 flex gap-2">
            <span className="text-green-400 font-mono text-sm">&gt;</span>
            <input
              type="text"
              value={command}
              onChange={e => setCommand(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendCommand(command)}
              placeholder="Type command..."
              className="flex-1 bg-transparent text-gray-200 font-mono text-sm outline-none placeholder-gray-600"
              autoFocus
            />
            <button
              onClick={() => sendCommand(command)}
              disabled={!command.trim()}
              className="text-gray-400 hover:text-green-400 disabled:opacity-30 transition-colors"
            >
              <Send size={16} />
            </button>
          </div>
        </div>

        {/* Presets sidebar */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">UART Commands</h3>
            <div className="space-y-1">
              {PRESET_COMMANDS.map(p => (
                <button
                  key={p.cmd}
                  onClick={() => sendCommand(p.cmd)}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-orange-50 transition-colors group"
                >
                  <div className="text-sm font-medium text-gray-700 group-hover:text-orange-700">{p.label}</div>
                  <div className="text-xs text-gray-400">{p.description}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">J-Link / SWD</h3>
            <div className="space-y-1">
              {JLINK_COMMANDS.map(p => (
                <button
                  key={p.cmd}
                  onClick={() => sendCommand(p.cmd)}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-orange-50 transition-colors group"
                >
                  <div className="text-sm font-medium text-gray-700 group-hover:text-orange-700">{p.label}</div>
                  <div className="text-xs text-gray-400">{p.description}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Analysis result */}
      {analysisResult && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700">AI Analysis of Serial Output</h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
              analysisResult.severity === 'RED' ? 'bg-red-100 text-red-700' :
              analysisResult.severity === 'AMBER' ? 'bg-amber-100 text-amber-700' :
              'bg-green-100 text-green-700'
            }`}>{analysisResult.severity}</span>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">Root Cause</div>
            <p className="text-sm text-gray-800">{analysisResult.root_cause_hypothesis}</p>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">Recommendation</div>
            <p className="text-sm text-gray-800">{analysisResult.recommended_action}</p>
          </div>
          <div className="text-xs text-gray-400 pt-2 border-t border-gray-100">Trace: {analysisResult.trace_id}</div>
        </div>
      )}
    </div>
  )
}
