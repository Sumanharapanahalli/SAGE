import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}

export interface PendingAction {
  action: string
  params: Record<string, unknown>
  confirmation_prompt: string
  message_id: string
}

interface ChatContextValue {
  panelState: 'closed' | 'minimised' | 'expanded'
  messages: ChatMessage[]
  isLoading: boolean
  unreadCount: number
  openChat: (seedMessage?: string) => void
  closeChat: () => void
  minimiseChat: () => void
  seedMessage: string | undefined
  clearSeedMessage: () => void
  addMessage: (msg: ChatMessage) => void
  updateLastAssistantMessage: (content: string, done: boolean) => void
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
  setIsLoading: (v: boolean) => void
  clearUnread: () => void
  incrementUnread: () => void
  pendingAction: PendingAction | null
  setPendingAction: (a: PendingAction | null) => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [panelState, setPanelState] = useState<'closed' | 'minimised' | 'expanded'>('closed')
  const [seedMessage, setSeedMessage] = useState<string | undefined>(undefined)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)

  const openChat = useCallback((seed?: string) => {
    setSeedMessage(seed)
    setPanelState('expanded')
    setUnreadCount(0)
  }, [])

  const closeChat = useCallback(() => setPanelState('closed'), [])
  const minimiseChat = useCallback(() => setPanelState('minimised'), [])
  const clearSeedMessage = useCallback(() => setSeedMessage(undefined), [])

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => [...prev, msg])
  }, [])

  const updateLastAssistantMessage = useCallback((content: string, done: boolean) => {
    setMessages(prev => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.role === 'assistant') {
        next[next.length - 1] = { ...last, content, streaming: !done }
      }
      return next
    })
  }, [])

  const clearUnread = useCallback(() => setUnreadCount(0), [])
  const incrementUnread = useCallback(() => setUnreadCount(n => n + 1), [])

  return (
    <ChatContext.Provider value={{
      panelState, messages, isLoading, unreadCount,
      openChat, closeChat, minimiseChat, seedMessage, clearSeedMessage,
      addMessage, updateLastAssistantMessage, setMessages, setIsLoading,
      clearUnread, incrementUnread,
      pendingAction, setPendingAction,
    }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider')
  return ctx
}
