import type { AuditEntry } from '../../api/client'
import { X } from 'lucide-react'
import CodeBlock from '../ui/CodeBlock'

interface Props { entry: AuditEntry; onClose: () => void }

export default function TraceDetailModal({ entry, onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-white/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <div className="font-semibold text-gray-800">{entry.action_type}</div>
            <div className="text-xs text-gray-400 font-mono">{entry.id}</div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Actor / Timestamp</div>
            <p className="text-sm text-gray-700">{entry.actor} · {new Date(entry.timestamp).toLocaleString()}</p>
          </div>
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Input Context</div>
            <CodeBlock className="whitespace-pre-wrap">{entry.input_context}</CodeBlock>
          </div>
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Output Content</div>
            <CodeBlock className="whitespace-pre-wrap">{entry.output_content}</CodeBlock>
          </div>
          {entry.metadata && (
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Metadata</div>
              <CodeBlock className="whitespace-pre-wrap">{entry.metadata}</CodeBlock>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
