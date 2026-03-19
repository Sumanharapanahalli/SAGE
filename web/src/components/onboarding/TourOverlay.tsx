import { useEffect, useState } from 'react'
import { useTourContext } from '../../context/TourContext'

interface Stop { selector: string; heading: string; body: string }

const STOPS: Stop[] = [
  { selector: '[data-tour="stats-strip"]',      heading: 'Your live dashboard',  body: 'These counters update every 10 seconds. Red means proposals are waiting for your approval — that is the most important number in this sidebar.' },
  { selector: '[data-tour="nav-approvals"]',     heading: 'The approval gate',    body: 'Every action your agents propose lands here first. Nothing executes until you approve it. This is the human-in-the-loop guarantee.' },
  { selector: '[data-tour="nav-queue"]',         heading: 'Active work',          body: 'Tasks you have approved move here. You can see what is running, queued, or completed at any time.' },
  { selector: '[data-tour="area-intelligence"]', heading: 'Your agents',          body: 'Expand this to run agent tasks, review improvement plans, or track goals. Analyst and Developer live here — not at the top level.' },
  { selector: '[data-tour="area-knowledge"]',    heading: 'Institutional memory', body: 'The vector knowledge base for this solution. Everything your agents learn, and everything you import, is stored and retrieved here at query time.' },
  { selector: '[data-tour="solution-rail"]',     heading: 'Your solutions',       body: 'Each solution gets an avatar here. Switch between them instantly. Use the org graph to see how they connect.' },
]

interface Rect { top: number; left: number; width: number; height: number }

export default function TourOverlay() {
  const { tourState, nextStop, prevStop, skipTour } = useTourContext()
  const [targetRect, setTargetRect] = useState<Rect | null>(null)

  const totalStops = STOPS.length
  const stop = STOPS[tourState.currentStop]

  useEffect(() => {
    if (!tourState.active || !stop) return
    const el = document.querySelector(stop.selector)
    if (el) {
      const r = el.getBoundingClientRect()
      setTargetRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    } else {
      setTargetRect(null)
    }
  }, [tourState.active, tourState.currentStop])

  if (!tourState.active || !stop) return null

  const isLast = tourState.currentStop === totalStops - 1

  const cardStyle: React.CSSProperties = targetRect
    ? { position: 'fixed', top: Math.max(8, targetRect.top), left: targetRect.left + targetRect.width + 16, zIndex: 101 }
    : { position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 101 }

  return (
    <>
      {targetRect ? (
        <>
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, height: targetRect.top, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
          <div style={{ position: 'fixed', top: targetRect.top + targetRect.height, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
          <div style={{ position: 'fixed', top: targetRect.top, left: 0, width: targetRect.left, height: targetRect.height, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
          <div style={{ position: 'fixed', top: targetRect.top, left: targetRect.left + targetRect.width, right: 0, height: targetRect.height, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
        </>
      ) : (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
      )}
      <div style={{ ...cardStyle, background: '#0f172a', border: '1px solid #334155', borderRadius: '10px',
                    padding: '16px', maxWidth: '280px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
        <div style={{ fontSize: '11px', color: '#475569', marginBottom: '6px' }}>
          {tourState.currentStop + 1} of {totalStops}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', marginBottom: '8px' }}>
          {stop.heading}
        </div>
        <div style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '16px' }}>
          {stop.body}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {tourState.currentStop > 0 && (
            <button onClick={prevStop}
              style={{ padding: '6px 12px', background: '#1e293b', color: '#94a3b8', borderRadius: '6px', fontSize: '12px', border: 'none', cursor: 'pointer' }}>
              Prev
            </button>
          )}
          <button onClick={isLast ? skipTour : nextStop}
            style={{ padding: '6px 12px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '12px', border: 'none', cursor: 'pointer' }}>
            {isLast ? 'Done' : 'Next'}
          </button>
          <button onClick={skipTour}
            style={{ fontSize: '12px', color: '#475569', background: 'none', border: 'none', marginLeft: 'auto', cursor: 'pointer' }}>
            Skip
          </button>
        </div>
      </div>
    </>
  )
}
