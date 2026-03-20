import { useState } from 'react'
import { Pin } from 'lucide-react'

interface SolutionPickerProps {
  solutions: Array<{ id: string; name: string }>
  activeId: string
  pinnedIds: string[]
  onPin: (id: string) => void
  onSwitch: (id: string) => void
  onClose: () => void
}

export default function SolutionPicker({ solutions, activeId, pinnedIds, onPin, onSwitch, onClose }: SolutionPickerProps) {
  const [selectedId, setSelectedId] = useState(activeId)
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const isPinDisabled = selectedId === activeId || pinnedIds.includes(selectedId) || pinnedIds.length >= 5
  const isSwitchDisabled = selectedId === activeId

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.5)',
          zIndex: 9998,
        }}
      />
      {/* Modal panel */}
      <div
        style={{
          position: 'fixed',
          top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '400px',
          maxHeight: '500px',
          background: '#18181b',
          border: '1px solid #27272a',
          borderRadius: '8px',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px 12px',
          borderBottom: '1px solid #27272a',
          flexShrink: 0,
        }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>All Solutions</span>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#64748b', fontSize: '16px', lineHeight: 1,
              padding: '2px 4px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            x
          </button>
        </div>

        {/* Scrollable list */}
        <div style={{ overflowY: 'auto', maxHeight: '360px', flex: 1 }}>
          {solutions.map(sol => {
            const isActive = sol.id === activeId
            const isSelected = sol.id === selectedId
            const isHovered = sol.id === hoveredId
            const isPinned = pinnedIds.includes(sol.id)

            let rowBg = 'transparent'
            if (isActive) rowBg = '#0f172a'
            if (isSelected && !isActive) rowBg = '#1e293b'
            if (isHovered && !isSelected && !isActive) rowBg = '#27272a'

            return (
              <div
                key={sol.id}
                onClick={() => setSelectedId(sol.id)}
                onMouseEnter={() => setHoveredId(sol.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  padding: '10px 14px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: rowBg,
                  borderLeft: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                }}
              >
                {/* Dot indicator */}
                <div style={{
                  width: '8px', height: '8px',
                  borderRadius: '50%',
                  background: isActive ? '#3b82f6' : 'transparent',
                  border: isActive ? 'none' : '1.5px solid #334155',
                  flexShrink: 0,
                }} />
                {/* Solution name */}
                <span style={{
                  fontSize: '13px',
                  color: isActive ? '#e4e4e7' : '#94a3b8',
                  flex: 1,
                }}>
                  {sol.name}
                </span>
                {/* Pin icon if pinned */}
                {isPinned && (
                  <Pin size={12} color="#94a3b8" />
                )}
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', gap: '8px', justifyContent: 'flex-end',
          padding: '12px 16px',
          borderTop: '1px solid #27272a',
          flexShrink: 0,
        }}>
          <button
            onClick={() => onPin(selectedId)}
            disabled={isPinDisabled}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 500,
              cursor: isPinDisabled ? 'not-allowed' : 'pointer',
              background: 'transparent',
              border: '1px solid #334155',
              borderRadius: '4px',
              color: isPinDisabled ? '#334155' : '#94a3b8',
            }}
          >
            Pin to rail
          </button>
          <button
            onClick={() => onSwitch(selectedId)}
            disabled={isSwitchDisabled}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 500,
              cursor: isSwitchDisabled ? 'not-allowed' : 'pointer',
              background: isSwitchDisabled ? '#1e3a5f' : '#3b82f6',
              border: 'none',
              borderRadius: '4px',
              color: isSwitchDisabled ? '#334155' : '#fff',
            }}
          >
            Switch to solution
          </button>
        </div>
      </div>
    </>
  )
}
