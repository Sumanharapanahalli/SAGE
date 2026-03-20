import { useRef, useEffect, useCallback } from 'react'

interface ResizablePanelsProps {
  direction: 'horizontal' | 'vertical'
  first: React.ReactNode
  second: React.ReactNode
  storageKey: string
  defaultSplit?: number
  minFirst?: number
  minSecond?: number
  dividerWidth?: number
  className?: string
  style?: React.CSSProperties
}

export default function ResizablePanels({
  direction,
  first,
  second,
  storageKey,
  defaultSplit = 50,
  minFirst = 200,
  minSecond = 200,
  dividerWidth = 4,
  className,
  style,
}: ResizablePanelsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const firstRef     = useRef<HTMLDivElement>(null)
  const secondRef    = useRef<HTMLDivElement>(null)
  const dragging     = useRef(false)

  const getInitialSplit = (): number => {
    try {
      const stored = localStorage.getItem(`sage_panel_${storageKey}`)
      if (stored) return parseFloat(stored)
    } catch { /* ignore */ }
    return defaultSplit
  }

  const applySplit = useCallback((pct: number) => {
    const firstEl  = firstRef.current
    const secondEl = secondRef.current
    if (!firstEl || !secondEl) return
    const clamped = Math.max(0, Math.min(100, pct))
    if (direction === 'horizontal') {
      firstEl.style.width  = `${clamped}%`
      secondEl.style.width = `${100 - clamped}%`
    } else {
      firstEl.style.height  = `${clamped}%`
      secondEl.style.height = `${100 - clamped}%`
    }
  }, [direction])

  useEffect(() => {
    applySplit(getInitialSplit())
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applySplit])

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      let pct: number
      if (direction === 'horizontal') {
        pct = ((ev.clientX - rect.left) / rect.width) * 100
      } else {
        pct = ((ev.clientY - rect.top) / rect.height) * 100
      }

      const totalPx = direction === 'horizontal' ? rect.width : rect.height
      const minFirstPct  = (minFirst  / totalPx) * 100
      const minSecondPct = (minSecond / totalPx) * 100
      pct = Math.max(minFirstPct, Math.min(100 - minSecondPct, pct))

      applySplit(pct)
    }

    const onUp = () => {
      dragging.current = false
      if (!containerRef.current || !firstRef.current) {
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
        return
      }
      const rect = containerRef.current.getBoundingClientRect()
      const firstEl = firstRef.current
      const firstSize = direction === 'horizontal' ? firstEl.offsetWidth : firstEl.offsetHeight
      const totalSize = direction === 'horizontal' ? rect.width : rect.height
      const pct = (firstSize / totalSize) * 100
      try { localStorage.setItem(`sage_panel_${storageKey}`, pct.toFixed(2)) } catch { /* ignore */ }
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [direction, minFirst, minSecond, storageKey, applySplit])

  const isH = direction === 'horizontal'

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        display: 'flex',
        flexDirection: isH ? 'row' : 'column',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        ...style,
      }}
    >
      <div ref={firstRef} style={{ overflow: 'auto', flexShrink: 0 }}>
        {first}
      </div>

      <div
        onMouseDown={onMouseDown}
        style={{
          flexShrink: 0,
          width:  isH ? dividerWidth : '100%',
          height: isH ? '100%' : dividerWidth,
          background: '#1e293b',
          cursor: isH ? 'col-resize' : 'row-resize',
          transition: 'background 0.1s',
          zIndex: 10,
        }}
        onMouseEnter={e => (e.currentTarget.style.background = '#3b82f6')}
        onMouseLeave={e => (e.currentTarget.style.background = '#1e293b')}
      />

      <div ref={secondRef} style={{ overflow: 'auto', flex: 1, minWidth: 0, minHeight: 0 }}>
        {second}
      </div>
    </div>
  )
}
