import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { X, Minus, MessageSquare, Send, Trash2 } from 'lucide-react'
import { useChat } from '../../hooks/useChat'
import { useChatContext } from '../../context/ChatContext'

export default function ChatPanel() {
  const { messages, isLoading, sendMessage, clearHistory, panelState, closeChat, minimiseChat } = useChat()
  const { openChat, unreadCount, clearUnread } = useChatContext()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when panel opens
  useEffect(() => {
    if (panelState === 'expanded') {
      clearUnread()
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [panelState, clearUnread])

  // Close on Escape
  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape' && panelState === 'expanded') closeChat()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [panelState, closeChat])

  const handleSend = () => {
    if (!input.trim()) return
    sendMessage(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (panelState === 'closed') return null

  // Minimised state — tab at bottom-centre
  if (panelState === 'minimised') {
    return (
      <div
        onClick={() => openChat()}
        style={{
          position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
          height: '44px', width: '200px',
          backgroundColor: '#0f172a', borderTop: '1px solid #1e293b',
          borderLeft: '1px solid #1e293b', borderRight: '1px solid #1e293b',
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '0 14px', cursor: 'pointer', zIndex: 8000,
          color: '#94a3b8', fontSize: '12px', fontWeight: 500,
        }}
      >
        <MessageSquare size={14} />
        <span style={{ flex: 1 }}>SAGE Chat</span>
        {unreadCount > 0 && (
          <span style={{
            backgroundColor: '#3b82f6', color: '#fff',
            fontSize: '10px', fontWeight: 700,
            padding: '1px 6px', minWidth: '18px', textAlign: 'center',
          }}>
            {unreadCount}
          </span>
        )}
      </div>
    )
  }

  // Expanded state
  return (
    <div
      style={{
        position: 'fixed', bottom: 0,
        left: '50%', transform: 'translateX(-50%)',
        width: '520px', height: '380px',
        backgroundColor: '#0f172a',
        border: '1px solid #1e293b',
        borderBottom: 'none',
        boxShadow: '0 -4px 32px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column',
        zIndex: 8000,
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '8px 12px',
        backgroundColor: 'var(--sage-sidebar-bg, #0f172a)',
        borderBottom: '1px solid #1e293b',
        flexShrink: 0,
      }}>
        <MessageSquare size={13} style={{ color: '#3b82f6' }} />
        <span style={{ flex: 1, fontSize: '12px', fontWeight: 600, color: '#e2e8f0' }}>
          SAGE Chat
        </span>
        <button
          onClick={clearHistory}
          title="Clear history"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#475569',
                   display: 'flex', alignItems: 'center', padding: '2px' }}
        >
          <Trash2 size={13} />
        </button>
        <button
          onClick={minimiseChat}
          title="Minimise"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#475569',
                   display: 'flex', alignItems: 'center', padding: '2px' }}
        >
          <Minus size={13} />
        </button>
        <button
          onClick={closeChat}
          title="Close"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#475569',
                   display: 'flex', alignItems: 'center', padding: '2px' }}
        >
          <X size={13} />
        </button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '12px',
        display: 'flex', flexDirection: 'column', gap: '10px',
        backgroundColor: '#020617',
      }}>
        {messages.length === 0 && (
          <div style={{ color: '#334155', fontSize: '12px', textAlign: 'center', marginTop: '40px' }}>
            Ask me anything about this solution, proposals, or the SAGE framework.
          </div>
        )}
        {messages.map(msg => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              alignItems: 'flex-start',
              gap: '8px',
            }}
          >
            <div style={{
              maxWidth: '80%',
              padding: '7px 11px',
              fontSize: '12px', lineHeight: 1.5,
              backgroundColor: msg.role === 'user' ? '#1d4ed8' : '#1e293b',
              color: '#e2e8f0',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {msg.content}
              {msg.streaming && (
                <span style={{
                  display: 'inline-block', width: '6px', height: '12px',
                  backgroundColor: '#60a5fa', marginLeft: '2px',
                  animation: 'sage-cursor-blink 1s step-end infinite',
                }} />
              )}
            </div>
          </div>
        ))}
        {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
          <div style={{ display: 'flex', gap: '4px', padding: '8px 0', paddingLeft: '4px' }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{
                width: '6px', height: '6px',
                backgroundColor: '#334155',
                animation: `sage-dot-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
              }} />
            ))}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        display: 'flex', gap: '8px', padding: '10px 12px',
        borderTop: '1px solid #1e293b', flexShrink: 0,
        backgroundColor: '#0f172a',
      }}>
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          disabled={isLoading}
          style={{
            flex: 1, background: '#020617', border: '1px solid #1e293b',
            color: '#e2e8f0', fontSize: '12px', padding: '6px 10px',
            outline: 'none',
          }}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          style={{
            backgroundColor: '#1d4ed8', border: 'none', color: '#fff',
            cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer',
            opacity: isLoading || !input.trim() ? 0.5 : 1,
            padding: '6px 10px', display: 'flex', alignItems: 'center',
          }}
        >
          <Send size={13} />
        </button>
      </div>
    </div>
  )
}
