// Reusable <pre> wrapper for the Audit log page (and anywhere else that renders
// raw text/JSON). Drop-in: <CodeBlock>{logText}</CodeBlock>. Overlays a hover
// CopyButton that copies the rendered text via the browser Clipboard API.
import CopyButton from './CopyButton'

interface CodeBlockProps {
  /** Raw text rendered inside the <pre>. Also used as the copy payload. */
  children: string
  className?: string
}

export default function CodeBlock({ children, className = '' }: CodeBlockProps) {
  return (
    <div className="relative group">
      <CopyButton text={children} />
      <pre
        className={
          'text-xs bg-gray-900 text-gray-100 rounded p-3 overflow-x-auto ' + className
        }
      >
        {children}
      </pre>
    </div>
  )
}
