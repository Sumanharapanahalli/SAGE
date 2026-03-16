import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  startOnboardingSession, sendOnboardingMessage, generateOnboardingSolution,
  OnboardingMessage, OnboardingInfo, OnboardingSession,
} from '../api/client'
import { Loader2, Send, Sparkles, CheckCircle, ArrowRight, Bot, User } from 'lucide-react'

// ---------------------------------------------------------------------------
// Chat message bubble
// ---------------------------------------------------------------------------
function MessageBubble({ msg }: { msg: OnboardingMessage }) {
  const isAssistant = msg.role === 'assistant'
  return (
    <div className={`flex gap-3 ${isAssistant ? '' : 'flex-row-reverse'}`}>
      {/* Avatar */}
      <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm
        ${isAssistant ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-100 text-gray-600'}`}>
        {isAssistant ? <Bot size={16} /> : <User size={16} />}
      </div>
      {/* Bubble */}
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
        isAssistant
          ? 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'
          : 'bg-indigo-600 text-white rounded-tr-sm'
      }`}>
        {msg.content}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Info summary strip
// ---------------------------------------------------------------------------
function InfoStrip({ info }: { info: OnboardingInfo }) {
  const items = [
    { label: 'Domain', value: info.description },
    { label: 'Name',   value: info.solution_name },
    { label: 'Standards', value: info.compliance_standards.join(', ') },
    { label: 'Integrations', value: info.integrations.join(', ') },
  ].filter(i => i.value)

  if (items.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2 px-4 py-2 bg-indigo-50 border-b border-indigo-100">
      {items.map(({ label, value }) => (
        <span key={label} className="text-xs text-indigo-700">
          <span className="font-medium">{label}:</span> {value.length > 40 ? value.slice(0, 40) + '…' : value}
        </span>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Generation complete card
// ---------------------------------------------------------------------------
function GeneratedCard({
  traceId, solutionName,
}: { traceId: string; solutionName: string }) {
  return (
    <div className="mx-4 mb-4 bg-green-50 border border-green-200 rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <CheckCircle size={18} className="text-green-600" />
        <span className="font-semibold text-green-800">Proposal created</span>
      </div>
      <div className="text-sm text-green-700 space-y-1">
        <p>Solution: <code className="bg-green-100 px-1.5 py-0.5 rounded font-mono">{solutionName}</code></p>
        <p className="font-mono text-xs text-green-500">trace: {traceId.slice(0, 16)}…</p>
      </div>
      <div className="text-xs text-green-600 bg-green-100 rounded-lg px-3 py-2">
        Go to <strong>Proposals &amp; Approvals</strong> in the sidebar to approve this.
        Once approved, the solution files will be written and you can switch to it from the header.
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Onboarding() {
  const [session, setSession]         = useState<OnboardingSession | null>(null)
  const [messages, setMessages]       = useState<OnboardingMessage[]>([])
  const [info, setInfo]               = useState<OnboardingInfo>({
    description: '', solution_name: '', compliance_standards: [], integrations: [], team_context: '',
  })
  const [state, setState]             = useState<string>('idle')
  const [input, setInput]             = useState('')
  const [generated, setGenerated]     = useState<{ traceId: string; solutionName: string } | null>(null)
  const bottomRef                     = useRef<HTMLDivElement>(null)

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Start session
  const startMutation = useMutation({
    mutationFn: startOnboardingSession,
    onSuccess: (sess) => {
      setSession(sess)
      setMessages(sess.messages)
      setInfo(sess.info)
      setState(sess.state)
    },
  })

  // Send message
  const sendMutation = useMutation({
    mutationFn: (msg: string) => sendOnboardingMessage(session!.session_id, msg),
    onSuccess: (res) => {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.reply, ts: Date.now() / 1000 },
      ])
      setInfo(res.info)
      setState(res.state)
    },
  })

  // Generate solution
  const generateMutation = useMutation({
    mutationFn: () => generateOnboardingSolution(session!.session_id),
    onSuccess: (res) => {
      setState('complete')
      setGenerated({ traceId: res.trace_id, solutionName: res.solution_name })
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant' as const,
          content:
            `Your solution **${res.solution_name}** is ready to generate.\n\n` +
            `Approve the proposal in the Proposals panel to create your solution files. ` +
            `Once approved you can switch to it from the header dropdown.`,
          ts: Date.now() / 1000,
        },
      ])
    },
  })

  const handleSend = () => {
    const msg = input.trim()
    if (!msg || sendMutation.isPending) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg, ts: Date.now() / 1000 }])
    sendMutation.mutate(msg)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const isReady     = state === 'ready'
  const isComplete  = state === 'complete'
  const isGenerating = generateMutation.isPending
  const isSending    = sendMutation.isPending

  // ── Not started yet ──────────────────────────────────────────────────────
  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="max-w-lg w-full text-center space-y-6">
          <div className="space-y-2">
            <div className="text-5xl">🚀</div>
            <h2 className="text-2xl font-bold text-gray-800">New Solution Wizard</h2>
            <p className="text-gray-500 text-sm leading-relaxed">
              SAGE will guide you through a short conversation to understand your team
              and domain, then generate a complete tailored configuration — three YAML
              files, domain-specific agent roles, and task types.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3 text-left">
            {[
              { n: '1', t: 'Describe your domain', d: 'Tell SAGE what you build in plain language' },
              { n: '2', t: 'Answer a few questions', d: 'Name, compliance, integrations, team' },
              { n: '3', t: 'Approve & activate', d: 'HITL proposal → approve → switch solution' },
            ].map(({ n, t, d }) => (
              <div key={n} className="bg-white rounded-xl border border-gray-200 p-4 space-y-1">
                <div className="w-6 h-6 bg-indigo-600 text-white rounded-full text-xs font-bold flex items-center justify-center">{n}</div>
                <p className="text-sm font-semibold text-gray-700">{t}</p>
                <p className="text-xs text-gray-400">{d}</p>
              </div>
            ))}
          </div>

          <button
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700
                       disabled:opacity-50 text-white font-medium px-8 py-3 rounded-xl
                       text-sm transition-colors"
          >
            {startMutation.isPending
              ? <><Loader2 size={16} className="animate-spin" /> Starting…</>
              : <><Sparkles size={16} /> Start Conversation</>
            }
          </button>
        </div>
      </div>
    )
  }

  // ── Chat view ─────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto -m-6">
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-gray-200 flex items-center gap-2 shrink-0">
        <Bot size={18} className="text-indigo-600" />
        <div>
          <h2 className="text-sm font-semibold text-gray-800">SAGE Onboarding</h2>
          <p className="text-xs text-gray-400">
            {isComplete ? 'Complete — approve the proposal to activate' :
             isReady    ? 'Ready to generate your solution' :
                         'Gathering information…'}
          </p>
        </div>
        {(isReady || isComplete) && (
          <span className={`ml-auto text-xs font-medium px-2 py-1 rounded-full ${
            isComplete ? 'bg-green-100 text-green-700' : 'bg-indigo-100 text-indigo-700'
          }`}>
            {isComplete ? 'Complete' : 'Ready'}
          </span>
        )}
      </div>

      {/* Info strip */}
      <InfoStrip info={info} />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {isSending && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
              <Bot size={16} className="text-indigo-600" />
            </div>
            <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <Loader2 size={14} className="animate-spin text-indigo-500" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Generated proposal card */}
      {generated && <GeneratedCard traceId={generated.traceId} solutionName={generated.solutionName} />}

      {/* Generate button — shown when ready */}
      {isReady && !isComplete && (
        <div className="px-4 py-3 bg-indigo-50 border-t border-indigo-100">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-indigo-700">
              SAGE has enough information to generate your solution.
            </p>
            <button
              onClick={() => generateMutation.mutate()}
              disabled={isGenerating}
              className="flex items-center gap-2 shrink-0 bg-indigo-600 hover:bg-indigo-700
                         disabled:opacity-50 text-white text-sm font-medium
                         px-4 py-2 rounded-lg transition-colors"
            >
              {isGenerating
                ? <><Loader2 size={14} className="animate-spin" /> Generating…</>
                : <><ArrowRight size={14} /> Generate Solution</>
              }
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      {!isComplete && (
        <div className="px-4 py-3 bg-white border-t border-gray-200 shrink-0">
          <div className="flex gap-2 items-end">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message… (Enter to send)"
              rows={2}
              disabled={isSending}
              className="flex-1 border border-gray-200 rounded-xl px-3 py-2.5 text-sm
                         resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400
                         disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className="flex items-center justify-center w-10 h-10 bg-indigo-600 hover:bg-indigo-700
                         disabled:opacity-40 text-white rounded-xl transition-colors shrink-0"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
