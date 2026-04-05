interface KeyboardShortcutsModalProps {
  onClose: () => void
}

const SHORTCUTS = [
  { group: 'Navigation', key: 'Ctrl+K', action: 'Open command palette' },
  { group: 'Navigation', key: 'G  A',   action: 'Go to Approvals' },
  { group: 'Navigation', key: 'G  Q',   action: 'Go to Task Queue' },
  { group: 'Navigation', key: 'G  D',   action: 'Go to Dashboard' },
  { group: 'Approvals',  key: 'A',      action: 'Approve focused proposal' },
  { group: 'Approvals',  key: 'R',      action: 'Reject focused proposal' },
]

export default function KeyboardShortcutsModal({ onClose }: KeyboardShortcutsModalProps) {
  const groups = [...new Set(SHORTCUTS.map(s => s.group))]

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#ffffff', border: '1px solid #e5e7eb',
          padding: '24px', width: '380px', maxHeight: '80vh', overflowY: 'auto',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>Keyboard Shortcuts</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: '18px', lineHeight: 1 }}
          >x</button>
        </div>
        {groups.map(group => (
          <div key={group} style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '6px' }}>
              {group}
            </div>
            {SHORTCUTS.filter(s => s.group === group).map(s => (
              <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: '#6b7280' }}>{s.action}</span>
                <kbd style={{
                  background: '#e5e7eb', border: '1px solid #d1d5db',
                  padding: '2px 6px', fontSize: '11px', color: '#e4e4e7',
                  fontFamily: 'monospace',
                }}>
                  {s.key}
                </kbd>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
