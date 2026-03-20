import { useState, useRef, useCallback, type ReactNode } from 'react'

interface TooltipProps {
  text: string
  children: ReactNode
  side?: 'right' | 'bottom'
}

export default function Tooltip({ text, children, side = 'right' }: TooltipProps) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const triggerRef = useRef<HTMLDivElement>(null)

  const handleMouseEnter = useCallback(() => {
    timerRef.current = setTimeout(() => {
      if (!triggerRef.current) return
      const r = triggerRef.current.getBoundingClientRect()
      if (side === 'bottom') {
        setPos({ x: r.left + r.width / 2, y: r.bottom + 6 })
      } else {
        setPos({ x: r.right + 8, y: r.top + r.height / 2 })
      }
    }, 200)
  }, [side])

  const handleMouseLeave = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setPos(null)
  }, [])

  const tooltipStyle: React.CSSProperties =
    side === 'bottom'
      ? { position: 'fixed', left: pos?.x ?? 0, top: pos?.y ?? 0, transform: 'translateX(-50%)' }
      : { position: 'fixed', left: pos?.x ?? 0, top: pos?.y ?? 0, transform: 'translateY(-50%)' }

  return (
    <div
      ref={triggerRef}
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {pos && (
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
            zIndex: 9999,
            whiteSpace: 'nowrap',
          }}
        >
          {text}
        </div>
      )}
    </div>
  )
}
