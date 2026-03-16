import { useState } from 'react'
import { HelpCircle } from 'lucide-react'

interface TooltipProps {
  content: string
  children?: React.ReactNode
  icon?: boolean
  position?: 'top' | 'bottom' | 'left' | 'right'
}

export function Tooltip({ content, children, icon = false, position = 'top' }: TooltipProps) {
  const [visible, setVisible] = useState(false)

  const posClasses: Record<string, string> = {
    top:    'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left:   'right-full top-1/2 -translate-y-1/2 mr-2',
    right:  'left-full top-1/2 -translate-y-1/2 ml-2',
  }

  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {icon ? (
        <HelpCircle size={13} className="text-gray-400 hover:text-gray-600 cursor-help" />
      ) : (
        children
      )}
      {visible && (
        <span
          className={`absolute z-50 w-64 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-xl pointer-events-none ${posClasses[position]}`}
        >
          {content}
        </span>
      )}
    </span>
  )
}
