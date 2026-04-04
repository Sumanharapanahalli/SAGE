import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Send, Plus, Trash2, Bot, Search, GitMerge, Activity,
  Lightbulb, Cpu, Target, Code2, Shield, Brain, Users,
  Loader2, ChevronDown, Sparkles, type LucideIcon,
} from 'lucide-react'
import { fetchAgentRoles, postChat, executeChat } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useProjectConfig } from '../hooks/useProjectConfig'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
  timestamp: number
}

interface Conversation {
  id: string
  title: string
  roleId: string
  roleName: string
  messages: Message[]
  createdAt: number
}

// ---------------------------------------------------------------------------
// Role icon mapping
// ---------------------------------------------------------------------------
const ROLE_ICONS: Record<string, LucideIcon> = {
  analyst: Search, developer: GitMerge, monitor: Activity,
  planner: Lightbulb, critic: Shield, product_owner: Users,
  systems_engineer: Cpu, universal: Bot, default: Brain,
}

function getRoleIcon(roleId: string): LucideIcon {
  const key = roleId.toLowerCase().replace(/[\s-]/g, '_')
  return ROLE_ICONS[key] ?? ROLE_ICONS.default
}

const ROLE_COLORS: Record<string, string> = {
  analyst: '#60a5fa', developer: '#4ade80', monitor: '#f59e0b',
  planner: '#a78bfa', critic: '#f87171', product_owner: '#ec4899',
  systems_engineer: '#06b6d4', universal: '#3b82f6',
}

function getRoleColor(roleId: string): string {
  const key = roleId.toLowerCase().replace(/[\s-]/g, '_')
  return ROLE_COLORS[key] ?? '#71717a'
}

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------
const STORAGE_KEY = 'sage_chat_conversations'

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveConversations(convs: Conversation[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(convs)) } catch {}
}

function getSessionId(): string {
  try {
    let id = sessionStorage.getItem('sage_chat_session')
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem('sage_chat_session', id) }
    return id
  } catch { return 'anon-session' }
}

// ---------------------------------------------------------------------------
// Markdown-lite renderer (bold, code, lists)
// ---------------------------------------------------------------------------
function renderContent(text: string) {
  // Split by code blocks
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('```')) {
      const code = part.replace(/^```\w*\n?/, '').replace(/\n?```$/, '')
      return (
        <pre key={i} style={{
          background: '#111113', padding: '12px 16px', borderRadius: 8,
          fontSize: 12, fontFamily: 'monospace', overflow: 'auto',
          margin: '8px 0', color: '#a1a1aa', border: '1px solid #27272a',
        }}>
          {code}
        </pre>
      )
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} style={{
          background: '#27272a', padding: '2px 6px', borderRadius: 4,
          fontSize: '0.9em', color: '#e4e4e7',
        }}>
          {part.slice(1, -1)}
        </code>
      )
    }
    // Bold
    const boldParts = part.split(/(\*\*[^*]+\*\*)/g)
    return boldParts.map((bp, j) => {
      if (bp.startsWith('**') && bp.endsWith('**')) {
        return <strong key={`${i}-${j}`} style={{ fontWeight: 600 }}>{bp.slice(2, -2)}</strong>
      }
      return <span key={`${i}-${j}`}>{bp}</span>
    })
  })
}

// ---------------------------------------------------------------------------
// Main Chat Page
// ---------------------------------------------------------------------------
export default function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations)
  const [activeId, setActiveId] = useState<string | null>(conversations[0]?.id ?? null)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showRolePicker, setShowRolePicker] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { user } = useAuth()
  const { data: projectData } = useProjectConfig()
  const userId = (user as any)?.sub ?? 'anonymous'
  const solution = (projectData as any)?.project ?? ''
  const sessionId = getSessionId()

  const { data: rolesData } = useQuery({
    queryKey: ['agent-roles'],
    queryFn: fetchAgentRoles,
    staleTime: 60_000,
  })

  const roles = rolesData?.roles ?? [
    { id: 'analyst', name: 'Analyst', description: 'Analyze logs and signals', icon: '🔍' },
    { id: 'developer', name: 'Developer', description: 'Code review and development', icon: '⚙️' },
    { id: 'monitor', name: 'Monitor', description: 'System monitoring and alerts', icon: '📊' },
    { id: 'planner', name: 'Planner', description: 'Strategic planning and decomposition', icon: '📋' },
    { id: 'product_owner', name: 'Product Owner', description: 'Requirements and prioritization', icon: '👤' },
  ]

  const activeConv = conversations.find(c => c.id === activeId)

  // Persist conversations
  useEffect(() => { saveConversations(conversations) }, [conversations])

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeConv?.messages.length])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  const startNewChat = useCallback((roleId: string, roleName: string) => {
    const conv: Conversation = {
      id: crypto.randomUUID(),
      title: 'New conversation',
      roleId, roleName,
      messages: [],
      createdAt: Date.now(),
    }
    setConversations(prev => [conv, ...prev])
    setActiveId(conv.id)
    setShowRolePicker(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [])

  const deleteConversation = useCallback((id: string) => {
    setConversations(prev => {
      const next = prev.filter(c => c.id !== id)
      if (activeId === id) setActiveId(next[0]?.id ?? null)
      return next
    })
  }, [activeId])

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading || !activeConv) return
    const text = input.trim()
    setInput('')

    const userMsg: Message = {
      id: crypto.randomUUID(), role: 'user', content: text, timestamp: Date.now(),
    }
    const assistantMsg: Message = {
      id: crypto.randomUUID(), role: 'assistant', content: '', streaming: true, timestamp: Date.now(),
    }

    setConversations(prev => prev.map(c => {
      if (c.id !== activeId) return c
      const updated = { ...c, messages: [...c.messages, userMsg, assistantMsg] }
      // Set title from first user message
      if (c.messages.filter(m => m.role === 'user').length === 0) {
        updated.title = text.slice(0, 60) + (text.length > 60 ? '…' : '')
      }
      return updated
    }))

    setIsLoading(true)

    try {
      const roleContext = `[Speaking as ${activeConv.roleName} role] `
      const res = await postChat({
        message: roleContext + text,
        user_id: userId,
        session_id: sessionId,
        page_context: JSON.stringify({
          route: '/chat',
          solution,
          role: activeConv.roleId,
          role_name: activeConv.roleName,
        }),
        solution,
      })

      const reply = res.reply ?? res.confirmation_prompt ?? 'No response received.'

      setConversations(prev => prev.map(c => {
        if (c.id !== activeId) return c
        const msgs = [...c.messages]
        const lastIdx = msgs.length - 1
        if (msgs[lastIdx]?.role === 'assistant') {
          msgs[lastIdx] = { ...msgs[lastIdx], content: reply, streaming: false }
        }
        return { ...c, messages: msgs }
      }))
    } catch {
      setConversations(prev => prev.map(c => {
        if (c.id !== activeId) return c
        const msgs = [...c.messages]
        const lastIdx = msgs.length - 1
        if (msgs[lastIdx]?.role === 'assistant') {
          msgs[lastIdx] = { ...msgs[lastIdx], content: 'Sorry, I could not reach the SAGE backend.', streaming: false }
        }
        return { ...c, messages: msgs }
      }))
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, activeConv, activeId, userId, sessionId, solution])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 48px)', margin: '-20px', background: '#0a0a0c' }}>
      {/* Sidebar — conversation history */}
      {sidebarOpen && (
        <div style={{
          width: 260, flexShrink: 0, background: '#0f0f11',
          borderRight: '1px solid #1a1a1e', display: 'flex', flexDirection: 'column',
        }}>
          {/* New chat button */}
          <div style={{ padding: '16px 12px 8px' }}>
            <button
              onClick={() => setShowRolePicker(true)}
              style={{
                width: '100%', padding: '10px 16px', background: '#1c1c1e',
                border: '1px solid #2a2a2e', borderRadius: 10, cursor: 'pointer',
                color: '#e4e4e7', fontSize: 13, fontWeight: 500,
                display: 'flex', alignItems: 'center', gap: 8,
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#27272a')}
              onMouseLeave={e => (e.currentTarget.style.background = '#1c1c1e')}
            >
              <Plus size={15} /> New chat
            </button>
          </div>

          {/* Conversation list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
            {conversations.length === 0 && (
              <div style={{ padding: '32px 12px', textAlign: 'center', color: '#3f3f46', fontSize: 12 }}>
                No conversations yet
              </div>
            )}
            {conversations.map(conv => {
              const isActive = conv.id === activeId
              const RIcon = getRoleIcon(conv.roleId)
              const color = getRoleColor(conv.roleId)
              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveId(conv.id)}
                  style={{
                    padding: '10px 12px', marginBottom: 2, borderRadius: 8,
                    cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 10,
                    background: isActive ? '#1c1c1e' : 'transparent',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#141416' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
                >
                  <RIcon size={14} style={{ color, flexShrink: 0, marginTop: 2 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, color: isActive ? '#e4e4e7' : '#a1a1aa',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {conv.title}
                    </div>
                    <div style={{ fontSize: 11, color: '#52525b', marginTop: 2 }}>
                      {conv.roleName}
                    </div>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); deleteConversation(conv.id) }}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: '#3f3f46', padding: 2, flexShrink: 0, opacity: 0.6,
                    }}
                    title="Delete"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Role picker modal */}
        {showRolePicker && (
          <div
            onClick={() => setShowRolePicker(false)}
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
              backdropFilter: 'blur(4px)', zIndex: 100,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <div
              onClick={e => e.stopPropagation()}
              style={{
                background: '#18181b', border: '1px solid #27272a', borderRadius: 16,
                padding: 24, width: 480, maxHeight: '70vh', overflowY: 'auto',
              }}
            >
              <h2 style={{ fontSize: 16, fontWeight: 600, color: '#e4e4e7', margin: '0 0 4px' }}>
                Choose a role
              </h2>
              <p style={{ fontSize: 12, color: '#52525b', margin: '0 0 16px' }}>
                Select an agent role to start a conversation with
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {roles.map(role => {
                  const Icon = getRoleIcon(role.id)
                  const color = getRoleColor(role.id)
                  return (
                    <button
                      key={role.id}
                      onClick={() => startNewChat(role.id, role.name)}
                      style={{
                        display: 'flex', alignItems: 'flex-start', gap: 12,
                        padding: '14px 16px', background: '#1c1c1e',
                        border: '1px solid #27272a', borderRadius: 12,
                        cursor: 'pointer', textAlign: 'left',
                        transition: 'border-color 0.15s, background 0.15s',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = color
                        e.currentTarget.style.background = '#222225'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = '#27272a'
                        e.currentTarget.style.background = '#1c1c1e'
                      }}
                    >
                      <div style={{
                        width: 36, height: 36, borderRadius: 10,
                        background: `${color}15`, display: 'flex',
                        alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                      }}>
                        <Icon size={18} style={{ color }} />
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#e4e4e7' }}>
                          {role.name}
                        </div>
                        <div style={{ fontSize: 11, color: '#71717a', marginTop: 2 }}>
                          {role.description}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* No conversation selected — welcome screen */}
        {!activeConv ? (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 16,
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: 20,
              background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Sparkles size={28} style={{ color: '#fff' }} />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 600, color: '#e4e4e7', margin: 0 }}>
              SAGE Chat
            </h1>
            <p style={{ fontSize: 14, color: '#52525b', maxWidth: 400, textAlign: 'center', margin: 0 }}>
              Start a conversation with any agent role. Each role brings specialized knowledge and capabilities.
            </p>
            <button
              onClick={() => setShowRolePicker(true)}
              style={{
                padding: '12px 24px', borderRadius: 12, fontSize: 14, fontWeight: 500,
                background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 8,
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#2563eb')}
              onMouseLeave={e => (e.currentTarget.style.background = '#3b82f6')}
            >
              <Plus size={16} /> New conversation
            </button>

            {/* Quick-start role cards */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 8, marginTop: 16, maxWidth: 520,
            }}>
              {roles.slice(0, 6).map(role => {
                const Icon = getRoleIcon(role.id)
                const color = getRoleColor(role.id)
                return (
                  <button
                    key={role.id}
                    onClick={() => startNewChat(role.id, role.name)}
                    style={{
                      padding: '12px 14px', background: '#1c1c1e',
                      border: '1px solid #27272a', borderRadius: 10,
                      cursor: 'pointer', textAlign: 'left',
                      display: 'flex', alignItems: 'center', gap: 8,
                      transition: 'border-color 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = color)}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = '#27272a')}
                  >
                    <Icon size={14} style={{ color }} />
                    <span style={{ fontSize: 12, color: '#a1a1aa' }}>{role.name}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '12px 24px', borderBottom: '1px solid #1a1a1e',
              flexShrink: 0,
            }}>
              {(() => {
                const Icon = getRoleIcon(activeConv.roleId)
                const color = getRoleColor(activeConv.roleId)
                return (
                  <>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: `${color}15`, display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Icon size={14} style={{ color }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#e4e4e7' }}>
                        {activeConv.roleName}
                      </div>
                      <div style={{ fontSize: 11, color: '#52525b' }}>
                        {activeConv.title}
                      </div>
                    </div>
                    <span style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 6,
                      background: `${color}15`, color,
                    }}>
                      {activeConv.roleId}
                    </span>
                  </>
                )
              })()}
            </div>

            {/* Messages */}
            <div style={{
              flex: 1, overflowY: 'auto', padding: '24px 0',
              display: 'flex', flexDirection: 'column',
            }}>
              <div style={{ maxWidth: 720, width: '100%', margin: '0 auto', padding: '0 24px' }}>
                {activeConv.messages.length === 0 && (
                  <div style={{
                    textAlign: 'center', padding: '60px 0', color: '#3f3f46',
                  }}>
                    <Bot size={32} style={{ margin: '0 auto 12px', display: 'block', opacity: 0.3 }} />
                    <p style={{ fontSize: 14, margin: 0 }}>
                      Start your conversation with {activeConv.roleName}
                    </p>
                  </div>
                )}

                {activeConv.messages.map(msg => {
                  if (msg.role === 'system') {
                    return (
                      <div key={msg.id} style={{
                        textAlign: 'center', fontSize: 11, color: '#52525b',
                        padding: '8px 0', fontStyle: 'italic',
                      }}>
                        {msg.content}
                      </div>
                    )
                  }

                  const isUser = msg.role === 'user'
                  const Icon = getRoleIcon(activeConv.roleId)
                  const color = getRoleColor(activeConv.roleId)

                  return (
                    <div key={msg.id} style={{
                      display: 'flex', gap: 12, marginBottom: 24,
                      flexDirection: 'row', alignItems: 'flex-start',
                    }}>
                      {/* Avatar */}
                      <div style={{
                        width: 32, height: 32, borderRadius: 10, flexShrink: 0,
                        background: isUser ? '#27272a' : `${color}15`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        {isUser ? (
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#a1a1aa' }}>
                            {userId.slice(0, 1).toUpperCase()}
                          </span>
                        ) : (
                          <Icon size={15} style={{ color }} />
                        )}
                      </div>

                      {/* Content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 12, fontWeight: 600, marginBottom: 4,
                          color: isUser ? '#a1a1aa' : color,
                        }}>
                          {isUser ? 'You' : activeConv.roleName}
                        </div>
                        <div style={{
                          fontSize: 14, lineHeight: 1.65, color: '#d4d4d8',
                          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                        }}>
                          {msg.content ? renderContent(msg.content) : null}
                          {msg.streaming && !msg.content && (
                            <div style={{ display: 'flex', gap: 4, padding: '4px 0' }}>
                              {[0, 1, 2].map(i => (
                                <div key={i} style={{
                                  width: 6, height: 6, borderRadius: '50%',
                                  background: '#3f3f46',
                                  animation: `sage-dot-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                                }} />
                              ))}
                            </div>
                          )}
                          {msg.streaming && msg.content && (
                            <span style={{
                              display: 'inline-block', width: 2, height: 16,
                              background: color, marginLeft: 1,
                              animation: 'sage-cursor-blink 1s step-end infinite',
                              verticalAlign: 'text-bottom',
                            }} />
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input area */}
            <div style={{
              flexShrink: 0, borderTop: '1px solid #1a1a1e',
              padding: '16px 24px 20px',
            }}>
              <div style={{
                maxWidth: 720, margin: '0 auto',
                background: '#1c1c1e', borderRadius: 16,
                border: '1px solid #2a2a2e', overflow: 'hidden',
                transition: 'border-color 0.15s',
              }}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Message ${activeConv.roleName}...`}
                  disabled={isLoading}
                  rows={1}
                  style={{
                    width: '100%', background: 'transparent', border: 'none',
                    color: '#e4e4e7', fontSize: 14, padding: '14px 16px 4px',
                    outline: 'none', resize: 'none', fontFamily: 'inherit',
                    lineHeight: 1.5, maxHeight: 200,
                  }}
                />
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  alignItems: 'center', padding: '8px 12px',
                }}>
                  <span style={{ fontSize: 11, color: '#3f3f46' }}>
                    {isLoading ? 'Thinking...' : 'Shift+Enter for new line'}
                  </span>
                  <button
                    onClick={sendMessage}
                    disabled={isLoading || !input.trim()}
                    style={{
                      width: 32, height: 32, borderRadius: 10,
                      background: input.trim() && !isLoading ? '#3b82f6' : '#27272a',
                      border: 'none', cursor: input.trim() && !isLoading ? 'pointer' : 'default',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'background 0.15s',
                    }}
                  >
                    {isLoading ? (
                      <Loader2 size={14} style={{ color: '#71717a' }} className="animate-spin" />
                    ) : (
                      <Send size={14} style={{ color: input.trim() ? '#fff' : '#52525b' }} />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
