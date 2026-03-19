import { useState, useRef, type ReactNode } from 'react'

interface TooltipProps {
  text: string
  children: ReactNode
  side?: 'right' | 'bottom'
}

export default function Tooltip({ text, children, side = 'right' }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleMouseEnter = () => {
    timerRef.current = setTimeout(() => setVisible(true), 200)
  }

  const handleMouseLeave = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
  }

  const tooltipStyle: React.CSSProperties =
    side === 'bottom'
      ? { position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: '6px' }
      : { position: 'absolute', left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: '8px' }

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {visible && (
        <div
          style={{
            ...tooltipStyle,
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '6px 10px',
            fontSize: '11px',
            color: '#94a3b8',
            maxWidth: '220px',
            pointerEvents: 'none',
            zIndex: 50,
            whiteSpace: 'nowrap',
          }}
        >
          {text}
        </div>
      )}
    </div>
  )
}
