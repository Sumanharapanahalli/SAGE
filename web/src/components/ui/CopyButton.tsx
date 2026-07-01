import { useEffect, useRef, useState } from 'react'
import { Copy, Check } from 'lucide-react'

interface CopyButtonProps {
  /** Text to copy to the clipboard. */
  text: string
  /** Optional extra classes for positioning/styling within the parent. */
  className?: string
}

/**
 * Small clipboard button intended to overlay a <pre> block.
 *
 * Place inside a `relative group` container; the button stays hidden until the
 * container is hovered/focused, then copies `text` via the browser Clipboard
 * API and flips to a check mark for 2 seconds. Icon-only, but always carries an
 * aria-label. No external dependencies.
 */
export default function CopyButton({ text, className = '' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clean up the pending timer if the component unmounts mid-countdown.
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const handleCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        // Fallback for non-secure contexts / older browsers.
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      timeoutRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // Silently ignore copy failures (e.g. permission denied).
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? 'Copied' : 'Copy to clipboard'}
      title={copied ? 'Copied' : 'Copy'}
      className={
        'absolute top-2 right-2 p-1.5 rounded bg-gray-800/80 text-gray-300 ' +
        'hover:bg-gray-700 hover:text-white focus:outline-none focus:ring-1 focus:ring-gray-400 ' +
        'opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity ' +
        className
      }
    >
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
    </button>
  )
}
