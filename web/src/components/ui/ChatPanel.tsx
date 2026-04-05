import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  X, Minus, MessageSquare, Send, Trash2, CheckCircle, XCircle,
  Maximize2, Bot, Search, GitMerge, Activity, Lightbulb, Shield,
  Users, Cpu, Brain, type LucideIcon,
} from 'lucide-react'
import { useChat } from '../../hooks/useChat'
import { useChatContext } from '../../context/ChatContext'

// ---------------------------------------------------------------------------
// Role helpers (shared with Chat.tsx)
// ---------------------------------------------------------------------------
const ROLE_ICONS: Record<string, LucideIcon> = {
  analyst: Search, developer: GitMerge, monitor: Activity,
  planner: Lightbulb, critic: Shield, product_owner: Users,
  systems_engineer: Cpu, universal: Bot, default: Brain,
}
const ROLE_COLORS: Record<string, string> = {
  analyst: '#60a5fa', developer: '#4ade80', monitor: '#f59e0b',
  planner: '#a78bfa', critic: '#f87171', product_owner: '#ec4899',
  systems_engineer: '#06b6d4', universal: '#3b82f6',
}
function getRoleIcon(roleId: string): LucideIcon {
  return ROLE_ICONS[roleId.toLowerCase().replace(/[\s-]/g, '_')] ?? ROLE_ICONS.default
}
function getRoleColor(roleId: string): string {
  return ROLE_COLORS[roleId.toLowerCase().replace(/[\s-]/g, '_')] ?? '#71717a'
}

export default function ChatPanel() {
  const navigate = useNavigate()
  const {
    messages, isLoading, sendMessage, clearHistory,
    panelState, closeChat, minimiseChat,
    pendingAction, confirmAction, cancelAction,
  } = useChat()
  const { openChat, unreadCount, clearUnread } = useChatContext()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (panelState === 'expanded') {
      clearUnread()
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [panelState, clearUnread])

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

  // Minimised tab
  if (panelState === 'minimised') {
    return (
      <div
        onClick={() => openChat()}
        style={{
          position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
          height: 40, width: 180, borderRadius: '10px 10px 0 0',
          backgroundColor: '#ffffff', borderTop: '1px solid #e5e7eb',
          borderLeft: '1px solid #e5e7eb', borderRight: '1px solid #e5e7eb',
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '0 14px', cursor: 'pointer', zIndex: 8000,
          color: '#6b7280', fontSize: 12, fontWeight: 500,
        }}
      >
        <MessageSquare size={13} />
        <span style={{ flex: 1 }}>SAGE Chat</span>
        {unreadCount > 0 && (
          <span style={{
            backgroundColor: '#3b82f6', color: '#fff',
            fontSize: 10, fontWeight: 700,
            padding: '1px 6px', borderRadius: 10, minWidth: 18, textAlign: 'center',
          }}>
            {unreadCount}
          </span>
        )}
      </div>
    )
  }

  // Expanded panel
  return (
    <div style={{
      position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
      width: 520, height: 420,
      backgroundColor: '#0f0f11', borderRadius: '16px 16px 0 0',
      border: '1px solid #e5e7eb', borderBottom: 'none',
      boxShadow: '0 -8px 40px rgba(0,0,0,0.5)',
      display: 'flex', flexDirection: 'column',
      zIndex: 8000,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '10px 16px', borderBottom: '1px solid #1a1a1e', flexShrink: 0,
      }}>
        <MessageSquare size={14} style={{ color: '#3b82f6' }} />
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: '#e4e4e7' }}>
          SAGE Chat
        </span>
        <button
          onClick={() => { closeChat(); navigate('/chat') }}
          title="Open full chat"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', display: 'flex', padding: 2 }}
        >
          <Maximize2 size={13} />
        </button>
        <button onClick={clearHistory} title="Clear" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', display: 'flex', padding: 2 }}>
          <Trash2 size={13} />
        </button>
        <button onClick={minimiseChat} title="Minimise" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', display: 'flex', padding: 2 }}>
          <Minus size={13} />
        </button>
        <button onClick={closeChat} title="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', display: 'flex', padding: 2 }}>
          <X size={13} />
        </button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: 16,
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {messages.length === 0 && (
          <div style={{ color: '#d1d5db', fontSize: 12, textAlign: 'center', marginTop: 40 }}>
            Ask me anything about this solution or the SAGE framework.
            <br />
            <button
              onClick={() => { closeChat(); navigate('/chat') }}
              style={{
                marginTop: 12, fontSize: 12, color: '#3b82f6',
                background: 'none', border: 'none', cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              Open full chat to pick a role
            </button>
          </div>
        )}
        {messages.map(msg => {
          if ((msg.role as string) === 'system') {
            return (
              <div key={msg.id} style={{
                textAlign: 'center', fontSize: 11, color: '#9ca3af',
                padding: '2px 8px', fontStyle: 'italic',
              }}>
                {msg.content}
              </div>
            )
          }
          const isUser = msg.role === 'user'
          return (
            <div key={msg.id} style={{
              display: 'flex', flexDirection: isUser ? 'row-reverse' : 'row',
              alignItems: 'flex-start', gap: 8,
            }}>
              <div style={{
                width: 26, height: 26, borderRadius: 8, flexShrink: 0,
                background: isUser ? '#e5e7eb' : 'rgba(59,130,246,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {isUser ? (
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#6b7280' }}>U</span>
                ) : (
                  <Bot size={13} style={{ color: '#3b82f6' }} />
                )}
              </div>
              <div style={{
                maxWidth: '80%', padding: '8px 12px', borderRadius: 12,
                fontSize: 13, lineHeight: 1.5,
                backgroundColor: isUser ? '#1d4ed8' : '#ffffff',
                color: '#e4e4e7', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {msg.content}
                {msg.streaming && (
                  <span style={{
                    display: 'inline-block', width: 2, height: 14,
                    backgroundColor: '#3b82f6', marginLeft: 2,
                    animation: 'sage-cursor-blink 1s step-end infinite',
                    verticalAlign: 'text-bottom',
                  }} />
                )}
              </div>
            </div>
          )
        })}
        {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
          <div style={{ display: 'flex', gap: 4, padding: '8px 0 0 36px' }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{
                width: 5, height: 5, borderRadius: '50%', background: '#d1d5db',
                animation: `sage-dot-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
              }} />
            ))}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Action confirmation or input */}
      {pendingAction ? (
        <div style={{
          borderTop: '2px solid #d97706', flexShrink: 0,
          padding: '12px 16px', background: '#ffffff',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{
              fontSize: 10, fontWeight: 700, color: '#d97706',
              background: 'rgba(217,119,6,0.1)', padding: '2px 8px', borderRadius: 4,
            }}>
              {pendingAction.action.toUpperCase().replace(/_/g, ' ')}
            </span>
          </div>
          <p style={{ fontSize: 12, color: '#6b7280', margin: '0 0 10px', lineHeight: 1.5 }}>
            {pendingAction.confirmation_prompt}
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={confirmAction} disabled={isLoading}
              style={{
                flex: 1, padding: '7px 0', fontSize: 12, fontWeight: 600,
                background: '#166534', color: '#bbf7d0', border: 'none',
                borderRadius: 8, cursor: isLoading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              }}
            >
              <CheckCircle size={13} /> Confirm
            </button>
            <button
              onClick={cancelAction} disabled={isLoading}
              style={{
                flex: 1, padding: '7px 0', fontSize: 12, fontWeight: 600,
                background: '#e5e7eb', color: '#9ca3af', border: 'none',
                borderRadius: 8, cursor: isLoading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              }}
            >
              <XCircle size={13} /> Cancel
            </button>
          </div>
        </div>
      ) : (
        <div style={{
          display: 'flex', gap: 8, padding: '12px 16px',
          borderTop: '1px solid #1a1a1e', flexShrink: 0,
        }}>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            disabled={isLoading}
            style={{
              flex: 1, background: '#ffffff', border: '1px solid #e5e7eb',
              borderRadius: 10, color: '#e4e4e7', fontSize: 13,
              padding: '8px 12px', outline: 'none',
            }}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            style={{
              width: 36, height: 36, borderRadius: 10,
              backgroundColor: input.trim() && !isLoading ? '#3b82f6' : '#e5e7eb',
              border: 'none', cursor: input.trim() && !isLoading ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <Send size={14} style={{ color: input.trim() && !isLoading ? '#fff' : '#52525b' }} />
          </button>
        </div>
      )}
    </div>
  )
}
