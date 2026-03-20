import { useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useProjectConfig } from './useProjectConfig'
import { useChatContext } from '../context/ChatContext'
import { postChat } from '../api/client'

// Stable session ID for this browser tab
function getSessionId(): string {
  try {
    let id = sessionStorage.getItem('sage_chat_session')
    if (!id) {
      id = crypto.randomUUID()
      sessionStorage.setItem('sage_chat_session', id)
    }
    return id
  } catch {
    return 'anon-session'
  }
}

export function useChat() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const { data: projectData } = useProjectConfig()
  const {
    panelState, messages, isLoading,
    openChat, closeChat, minimiseChat,
    seedMessage, clearSeedMessage,
    addMessage, updateLastAssistantMessage, setMessages, setIsLoading,
    clearUnread, incrementUnread,
  } = useChatContext()

  const userId = (user as any)?.sub ?? 'anonymous'
  const solution = (projectData as any)?.project ?? ''
  const sessionId = getSessionId()

  // Auto-send seed message when panel opens with one
  useEffect(() => {
    if (panelState === 'expanded' && seedMessage) {
      const seed = seedMessage
      clearSeedMessage()
      sendMessage(seed)
    }
  }, [panelState, seedMessage]) // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg = { id: crypto.randomUUID(), role: 'user' as const, content: text }
    addMessage(userMsg)
    setIsLoading(true)

    addMessage({ id: crypto.randomUUID(), role: 'assistant', content: '', streaming: true })

    try {
      const res = await postChat({
        message: text,
        user_id: userId,
        session_id: sessionId,
        page_context: pathname,
        solution,
      })
      updateLastAssistantMessage(res.reply, true)
      if (panelState !== 'expanded') {
        incrementUnread()
      }
    } catch {
      updateLastAssistantMessage('Sorry, I could not reach the SAGE backend. Please check that the server is running.', true)
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, userId, sessionId, pathname, solution, panelState, addMessage, setIsLoading, updateLastAssistantMessage, incrementUnread])

  const clearHistory = useCallback(() => {
    setMessages([])
    try {
      const params = new URLSearchParams({ user_id: userId, solution })
      fetch(`/api/chat/history?${params}`, { method: 'DELETE' }).catch(() => {})
    } catch {}
  }, [userId, solution, setMessages])

  return {
    messages,
    isLoading,
    sendMessage,
    clearHistory,
    panelState,
    openChat,
    closeChat,
    minimiseChat,
    clearUnread,
  }
}
