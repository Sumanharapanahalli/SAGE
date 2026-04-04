import { useToast, type ToastType } from '../../context/ToastContext'
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react'

const ICONS: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const COLORS: Record<ToastType, { bg: string; border: string; icon: string; text: string }> = {
  success: { bg: '#0a1f0a', border: '#166534', icon: '#4ade80', text: '#bbf7d0' },
  error:   { bg: '#1f0a0a', border: '#7f1d1d', icon: '#f87171', text: '#fecaca' },
  warning: { bg: '#1f1a0a', border: '#713f12', icon: '#fbbf24', text: '#fef08a' },
  info:    { bg: '#0a0f1f', border: '#1e3a5f', icon: '#60a5fa', text: '#bfdbfe' },
}

export default function ToastContainer() {
  const { toasts, removeToast } = useToast()

  if (toasts.length === 0) return null

  return (
    <div style={{
      position: 'fixed', top: 16, right: 16, zIndex: 9999,
      display: 'flex', flexDirection: 'column', gap: 8,
      maxWidth: 380, width: '100%',
    }}>
      {toasts.map(toast => {
        const Icon = ICONS[toast.type]
        const colors = COLORS[toast.type]
        return (
          <div
            key={toast.id}
            style={{
              background: colors.bg, border: `1px solid ${colors.border}`,
              borderRadius: 12, padding: '12px 16px',
              display: 'flex', alignItems: 'flex-start', gap: 10,
              boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
              animation: 'sage-page-enter 0.2s ease-out',
            }}
          >
            <Icon size={16} style={{ color: colors.icon, flexShrink: 0, marginTop: 1 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: colors.text }}>
                {toast.title}
              </div>
              {toast.message && (
                <div style={{ fontSize: 12, color: colors.text, opacity: 0.75, marginTop: 2 }}>
                  {toast.message}
                </div>
              )}
              {toast.action && (
                <button
                  onClick={toast.action.onClick}
                  style={{
                    marginTop: 8, fontSize: 12, fontWeight: 500,
                    color: colors.icon, background: 'rgba(255,255,255,0.08)',
                    border: 'none', borderRadius: 6, padding: '4px 12px',
                    cursor: 'pointer',
                  }}
                >
                  {toast.action.label}
                </button>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: colors.text, opacity: 0.4, padding: 2, flexShrink: 0,
              }}
            >
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
