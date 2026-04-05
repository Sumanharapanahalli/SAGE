/**
 * Skeleton — Loading placeholder component.
 *
 * Usage:
 *   <Skeleton />                    — single line
 *   <Skeleton width="60%" />        — partial-width line
 *   <Skeleton height="8rem" />      — tall block (e.g., card)
 *   <Skeleton rows={5} />           — multiple lines
 *   <SkeletonCard />                — card-shaped placeholder
 */

interface SkeletonProps {
  width?: string
  height?: string
  rows?: number
  className?: string
}

export default function Skeleton({ width = '100%', height = '1rem', rows = 1, className = '' }: SkeletonProps) {
  return (
    <div className={className} role="status" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{
            width: i === rows - 1 && rows > 1 ? '60%' : width,
            height,
            borderRadius: '0.375rem',
            background: 'linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
            marginBottom: i < rows - 1 ? '0.5rem' : 0,
          }}
        />
      ))}
      <style>{`
        @keyframes skeleton-shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  )
}

export function SkeletonCard() {
  return (
    <div
      style={{
        padding: '1.25rem',
        borderRadius: '0.75rem',
        border: '1px solid #e5e7eb',
        background: '#ffffff',
      }}
    >
      <Skeleton width="40%" height="1.25rem" />
      <div style={{ marginTop: '1rem' }}>
        <Skeleton rows={3} />
      </div>
      <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
        <Skeleton width="4rem" height="1.5rem" />
        <Skeleton width="4rem" height="1.5rem" />
      </div>
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div role="status" aria-busy="true" aria-label="Loading table">
      {/* Header */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid #e5e7eb' }}>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} width={i === 0 ? '30%' : '20%'} height="0.875rem" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: 'flex', gap: '1rem', marginBottom: '0.75rem' }}>
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} width={c === 0 ? '30%' : '20%'} height="0.875rem" />
          ))}
        </div>
      ))}
    </div>
  )
}
