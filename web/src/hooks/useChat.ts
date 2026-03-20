import { useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { useProjectConfig } from './useProjectConfig'
import { useChatContext } from '../context/ChatContext'
import { postChat, executeChat } from '../api/client'

function getSessionId(): string {
  try {
    let id = sessionStorage.getItem('sage_chat_session')
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem('sage_chat_session', id) }
    return id
  } catch { return 'anon-session' }
}

function buildPageContext(pathname: string, queryClient: ReturnType<typeof useQueryClient>, solution: string): string {
  const ctx: Record<string, unknown> = { route: pathname, solution }
  try {
    if (pathname === '/approvals' || pathname.startsWith('/approvals')) {
      const proposals = queryClient.getQueryData<{ proposals?: unknown[] }>(['proposals'])
      const pending = (proposals?.proposals ?? []).filter((p: any) => p.status === 'pending')
      ctx.pending_proposals = pending.slice(0, 5).map((p: any) => ({
        trace_id: p.trace_id, description: p.description, action_type: p.action_type,
      }))
    }
    if (pathname === '/queue' || pathname.startsWith('/queue')) {
      const tasks = queryClient.getQueryData<unknown[]>(['queue'])
      ctx.pending_tasks = (tasks ?? []).slice(0, 5)
    }
    const projectData = queryClient.getQueryData<any>(['projectConfig'])
    if (projectData) {
      ctx.domain = projectData.domain ?? ''
      ctx.compliance = projectData.compliance_standards ?? []
    }
  } catch { /* cache miss — non-fatal */ }
  return JSON.stringify(ctx)
}

export function useChat() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const { data: projectData } = useProjectConfig()
  const queryClient = useQueryClient()
  const {
    panelState, messages, isLoading,
    openChat, closeChat, minimiseChat,
    seedMessage, clearSeedMessage,
    addMessage, updateLastAssistantMessage, setMessages, setIsLoading,
    clearUnread, incrementUnread,
    pendingAction, setPendingAction,
  } = useChatContext()

  const userId = (user as any)?.sub ?? 'anonymous'
  const solution = (projectData as any)?.project ?? ''
  const sessionId = getSessionId()

  useEffect(() => {
    if (panelState === 'expanded' && seedMessage) {
      const seed = seedMessage
      clearSeedMessage()
      sendMessage(seed)
    }
  }, [panelState, seedMessage]) // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return
    // Auto-cancel any pending action
    if (pendingAction) setPendingAction(null)

    const userMsg = { id: crypto.randomUUID(), role: 'user' as const, content: text }
    addMessage(userMsg)
    setIsLoading(true)
    addMessage({ id: crypto.randomUUID(), role: 'assistant' as const, content: '', streaming: true })

    try {
      const pageContext = buildPageContext(pathname, queryClient, solution)
      const res = await postChat({
        message: text, user_id: userId, session_id: sessionId,
        page_context: pageContext, solution,
      })

      if (res.response_type === 'action' && res.action !== 'query_knowledge') {
        // Remove streaming bubble, show nothing — confirmation card replaces it
        setMessages(prev => prev.filter(m => !m.streaming))
        setPendingAction({
          action: res.action!,
          params: res.params ?? {},
          confirmation_prompt: res.confirmation_prompt ?? '',
          message_id: res.message_id,
        })
      } else {
        // Plain answer
        updateLastAssistantMessage(res.reply ?? '', true)
        if (panelState !== 'expanded') incrementUnread()
      }
    } catch {
      updateLastAssistantMessage('Sorry, I could not reach the SAGE backend.', true)
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, pendingAction, userId, sessionId, pathname, solution, panelState,
      queryClient, addMessage, setMessages, setIsLoading, updateLastAssistantMessage,
      incrementUnread, setPendingAction])

  const confirmAction = useCallback(async () => {
    if (!pendingAction) return
    setIsLoading(true)
    const action = pendingAction
    setPendingAction(null)
    try {
      const res = await executeChat({
        action: action.action, params: action.params,
        user_id: userId, session_id: sessionId, solution,
      })
      addMessage({
        id: crypto.randomUUID(), role: 'system' as const,
        content: res.message,
      })
      if (panelState !== 'expanded') incrementUnread()
    } catch (err: any) {
      addMessage({
        id: crypto.randomUUID(), role: 'system' as const,
        content: `Error: ${err.message ?? 'Action failed'}`,
      })
    } finally {
      setIsLoading(false)
    }
  }, [pendingAction, userId, sessionId, solution, panelState,
      addMessage, setIsLoading, incrementUnread, setPendingAction])

  const cancelAction = useCallback(() => {
    if (!pendingAction) return
    const action = pendingAction
    setPendingAction(null)
    addMessage({ id: crypto.randomUUID(), role: 'system' as const, content: 'Cancelled.' })
    // Log cancellation to backend for audit trail (fire-and-forget)
    fetch('/api/chat/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: action.action, params: action.params,
        user_id: userId, session_id: sessionId, solution,
      }),
    }).catch(() => {})
  }, [pendingAction, userId, sessionId, solution, addMessage, setPendingAction])

  const clearHistory = useCallback(() => {
    setMessages([])
    setPendingAction(null)
    try {
      const params = new URLSearchParams({ user_id: userId, solution })
      fetch(`/api/chat/history?${params}`, { method: 'DELETE' }).catch(() => {})
    } catch {}
  }, [userId, solution, setMessages, setPendingAction])

  return {
    messages, isLoading, sendMessage, clearHistory,
    panelState, openChat, closeChat, minimiseChat, clearUnread,
    pendingAction, confirmAction, cancelAction,
  }
}
