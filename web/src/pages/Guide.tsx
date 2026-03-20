const GUIDE_SECTIONS = [
  {
    id: 'submit-analysis',
    title: 'Submitting a Log Analysis',
    description: 'Go to Log Analyst, paste a log entry or error message, and click Analyze. The AI agent will triage the signal, search the vector knowledge base for similar past events, and produce a structured proposal.',
    gif: '/guide/submit-analysis.gif',
    steps: [
      'Navigate to Intelligence > Analyst',
      'Paste your log entry or error message',
      'Click "Analyze"',
      'Review the AI proposal in the Approvals queue',
    ],
  },
  {
    id: 'approve-proposal',
    title: 'Approving or Rejecting a Proposal',
    description: 'Every AI-generated action waits in the Approvals inbox until a human reviews it. Approve to execute, reject with feedback to teach the agent, or let it expire.',
    gif: '/guide/approve-proposal.gif',
    steps: [
      'Navigate to Work > Approvals',
      'Review the proposal details and risk badge',
      'Click Approve to execute, or Reject with feedback',
      'Rejected feedback is stored in vector memory to improve future proposals',
    ],
  },
  {
    id: 'switch-solution',
    title: 'Switching Solutions',
    description: 'SAGE supports multiple solutions simultaneously. Each solution has its own agent prompts, task types, knowledge base, and audit log. Switch with one click from the solution rail.',
    gif: '/guide/switch-solution.gif',
    steps: [
      'Click a solution avatar in the far-left solution rail',
      'The sidebar labels, agent prompts, and available modules all update',
      'Each solution has its own isolated vector knowledge store',
      'The audit log is per-solution and travels with the solution folder',
    ],
  },
  {
    id: 'configure-llm',
    title: 'Configuring the LLM Provider',
    description: 'SAGE works with Gemini CLI, Claude Code CLI, Ollama, and local GGUF models — no API key required for most providers. Switch providers at runtime with no restart.',
    gif: '/guide/configure-llm.gif',
    steps: [
      'Navigate to Admin > LLM Settings',
      'Select a provider from the dropdown',
      'For Ollama: ensure `ollama serve` is running locally',
      'For Gemini CLI: run `gemini` once to authenticate via browser OAuth',
      'Click Switch — the change takes effect immediately',
    ],
  },
  {
    id: 'knowledge-base',
    title: 'Adding to the Knowledge Base',
    description: 'Agents search the vector knowledge base before every proposal. Add domain documents, past decisions, or correction notes to improve future proposals.',
    gif: '/guide/knowledge-base.gif',
    steps: [
      'Navigate to Knowledge > Vector Store',
      'Click "Add Entry"',
      'Paste text or a document excerpt',
      'Agents will find this context in future analyses via semantic search',
    ],
  },
  {
    id: 'dev-identity',
    title: 'Switching Identities (Dev Mode)',
    description: 'In development, switch between pre-configured user identities to test role-based approvals without real authentication.',
    gif: '/guide/dev-identity.gif',
    steps: [
      'Click your avatar in the top-right header',
      'Open the "Switch Identity" dropdown',
      'Select a different user (admin, approver, viewer)',
      'The role badge updates immediately — different roles see different capabilities',
    ],
  },
]

export default function Guide() {
  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#0f172a', marginBottom: '6px' }}>User Guide</h2>
        <p style={{ fontSize: '13px', color: '#64748b' }}>
          Animated walkthroughs for key SAGE features. Each GIF auto-loops so you can follow along at your own pace.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        {GUIDE_SECTIONS.map(section => (
          <div
            key={section.id}
            style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              overflow: 'hidden',
            }}
          >
            {/* GIF / placeholder */}
            <div style={{ background: '#0f172a', aspectRatio: '16/9', overflow: 'hidden', position: 'relative' }}>
              <img
                src={section.gif}
                alt={section.title}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={e => {
                  // Fallback to placeholder if GIF not yet recorded
                  const el = e.currentTarget
                  el.src = '/guide/placeholder.svg'
                }}
              />
            </div>

            {/* Content */}
            <div style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#0f172a', marginBottom: '8px' }}>
                {section.title}
              </h3>
              <p style={{ fontSize: '13px', color: '#475569', marginBottom: '16px', lineHeight: '1.6' }}>
                {section.description}
              </p>

              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', marginBottom: '8px' }}>
                  Steps
                </div>
                <ol style={{ margin: 0, paddingLeft: '20px' }}>
                  {section.steps.map((step, i) => (
                    <li key={i} style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px', lineHeight: '1.5' }}>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: '32px', padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: '12px', color: '#64748b' }}>
        <strong>Adding GIF recordings:</strong> Record each walkthrough and save as{' '}
        <code style={{ background: '#e2e8f0', padding: '1px 4px' }}>web/public/guide/&lt;id&gt;.gif</code>.
        The page will display it automatically. Recommended tool: LiceCap (Windows/macOS) or Peek (Linux).
      </div>
    </div>
  )
}
