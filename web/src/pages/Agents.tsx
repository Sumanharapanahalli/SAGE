import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchAgentRoles, runAgent } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import { Loader2, ChevronDown, ChevronUp, CheckCircle, Sparkles } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface AgentRole {
  id: string
  name: string
  description: string
  icon: string
}

interface AgentResult {
  trace_id: string
  role_id: string
  role_name: string
  icon: string
  task: string
  summary: string
  analysis: string
  recommendations: string[]
  next_steps: string[]
  severity: string
  confidence: string
  status: string
}

// ---------------------------------------------------------------------------
// Severity styling
// ---------------------------------------------------------------------------
const SEV_STYLES: Record<string, string> = {
  RED:   'bg-red-50 border-red-300 text-red-700',
  AMBER: 'bg-amber-50 border-amber-300 text-amber-700',
  GREEN: 'bg-green-50 border-green-300 text-green-700',
}

const CONF_COLOR: Record<string, string> = {
  HIGH:   'text-green-600',
  MEDIUM: 'text-amber-600',
  LOW:    'text-red-600',
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------
function ResultCard({ result }: { result: AgentResult }) {
  const [expanded, setExpanded] = useState(true)
  const sevStyle = SEV_STYLES[result.severity] ?? SEV_STYLES.GREEN

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-start gap-3 px-5 py-4">
        <span className="text-2xl shrink-0">{result.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-gray-800 text-sm">{result.role_name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${sevStyle}`}>
              {result.severity}
            </span>
            <span className={`text-xs font-medium ${CONF_COLOR[result.confidence] ?? 'text-gray-500'}`}>
              {result.confidence} confidence
            </span>
          </div>
          <p className="text-sm text-gray-700 mt-1 font-medium">{result.summary}</p>
          <p className="text-xs text-gray-400 mt-0.5 font-mono truncate">
            trace: {result.trace_id.slice(0, 16)}…
          </p>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-gray-400 hover:text-gray-600 shrink-0"
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 pb-5 pt-4 space-y-4">
          {/* Analysis */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Analysis</h4>
            <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{result.analysis}</p>
          </div>

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Recommendations</h4>
              <ul className="space-y-1.5">
                {result.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <CheckCircle size={14} className="text-green-500 mt-0.5 shrink-0" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Next steps */}
          {result.next_steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Next Steps</h4>
              <ol className="space-y-1.5 list-none">
                {result.next_steps.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="bg-gray-100 text-gray-600 text-xs font-bold rounded-full w-5 h-5
                                     flex items-center justify-center shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    {s}
                  </li>
                ))}
              </ol>
            </div>
          )}

          <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            ⚠ Pending human review — approve or reject this recommendation before acting on it.
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Role selector card
// ---------------------------------------------------------------------------
function RoleCard({
  role,
  selected,
  onClick,
}: {
  role: AgentRole
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`text-left p-4 rounded-xl border transition-all ${
        selected
          ? 'border-indigo-400 bg-indigo-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50'
      }`}
    >
      <div className="text-2xl mb-2">{role.icon}</div>
      <div className="text-sm font-semibold text-gray-800">{role.name}</div>
      <div className="text-xs text-gray-500 mt-0.5 leading-snug">{role.description}</div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Task templates per role — quick-start prompts
// ---------------------------------------------------------------------------
const TASK_TEMPLATES: Record<string, { label: string; task: string; context?: string }[]> = {
  // PoseEngine roles
  ml_engineer: [
    { label: 'Optimize training config', task: 'Review our training configuration and suggest optimizations for faster convergence and better mAP.', context: 'PyTorch, HRNet-W48, batch_size=32, lr=1e-4, AdamW, cosine annealing, 100 epochs' },
    { label: 'Model size reduction', task: 'How can we reduce model size for mobile deployment while keeping mAP above 0.80?', context: 'Current model: HRNet-W48 (142MB ONNX). Target: under 25MB TFLite.' },
    { label: 'Training loss plateau', task: 'Training loss has plateaued at 0.034 after epoch 60. What should we try next?' },
  ],
  mobile_developer: [
    { label: 'Camera integration', task: 'Design the camera capture pipeline for real-time pose estimation on mobile.', context: 'Flutter app, TFLite model, 30fps target, Android + iOS' },
    { label: 'Performance profiling', task: 'The app drops to 15fps during inference on mid-range Android devices. How do we optimize?' },
    { label: 'Offline mode', task: 'Design an offline-capable architecture for the Flutter app when the API is unreachable.' },
  ],
  data_scientist: [
    { label: 'Dataset quality audit', task: 'What metrics should we track to ensure annotation quality for our pose estimation dataset?' },
    { label: 'Benchmark evaluation', task: 'Design a benchmark suite to compare our model against MediaPipe, OpenPose, and ViTPose.' },
    { label: 'A/B test design', task: 'Design an A/B test to measure if the new model improves user engagement in the app.' },
  ],
  devops_engineer: [
    { label: 'GPU CI pipeline', task: 'Design a GitLab CI pipeline that runs model training validation on GPU runners.', context: 'GitLab CI, NVIDIA T4 runner, PyTorch, ONNX export' },
    { label: 'Model registry setup', task: 'What is the best approach to set up a model registry for versioning and deployment tracking?' },
    { label: 'Deployment automation', task: 'Automate the ONNX → TFLite → CoreML conversion and upload to mobile app releases.' },
  ],
  // DFS roles
  firmware_engineer: [
    { label: 'Flash write failure', task: 'A device is reporting flash write failures during OTA update. What is the likely cause and fix?', context: 'STM32H743, internal flash sector 8-11, error code 0x04 (write protection), flash count: 61' },
    { label: 'BLE sync issues', task: 'BLE pairing succeeds but data sync fails intermittently after 2-3 minutes.', context: 'STM32 BLE stack, MTU 247, connected to iOS device' },
    { label: 'Stack overflow debug', task: 'FreeRTOS stack overflow detected in Sensor_Task. How do we diagnose and fix?' },
  ],
  test_engineer: [
    { label: 'HIL test plan', task: 'Design a hardware-in-the-loop test plan for the bootloader update sequence.' },
    { label: 'Regression test suite', task: 'What test cases should we add after fixing the flash write failure bug?', context: 'STM32H743, bootloader v1.2.0, main firmware v2.4.1' },
    { label: 'J-Link diagnostics', task: 'Create a diagnostic script that validates device state after firmware flash via J-Link.' },
  ],
  production_support: [
    { label: 'Device triage', task: 'A batch of 5 devices from the production line are failing BLE provisioning. Triage and recommend actions.', context: 'All same hardware revision, firmware v2.4.1, provisioning tool v3.1' },
    { label: 'Manufacturing alert', task: 'Production line stopped — flash tool reporting "Target not found" on all devices since 10:30 AM.' },
    { label: 'Provisioning workflow', task: 'Design an improved provisioning workflow that reduces per-device setup time from 3 minutes to under 1 minute.' },
  ],
  systems_architect: [
    { label: 'Memory layout review', task: 'Review our current flash memory layout and suggest improvements for OTA resilience.', context: 'STM32H743, 2MB flash, sectors 0-7 bootloader, 8-11 app, 12-15 config+staging' },
    { label: 'Power management', task: 'Design a low-power mode strategy for battery-operated DFS devices.' },
    { label: 'ISR architecture', task: 'Review our interrupt priority scheme. We have UART, SPI, BLE, and DMA interrupts competing.' },
  ],
  // Startup roles
  product_manager: [
    { label: 'Write a PRD', task: 'Write a Product Requirements Document for our core feature.', context: 'B2B SaaS, early stage, 10 beta customers' },
    { label: 'Prioritize backlog', task: 'Help me prioritize these 8 feature requests using RICE scoring.' },
  ],
  marketing_strategist: [
    { label: 'GTM strategy', task: 'Create a go-to-market strategy for our product launch.', context: 'B2B SaaS, developer tools, $0 marketing budget' },
    { label: 'Content calendar', task: 'Design a 30-day content marketing calendar for LinkedIn and our blog.' },
  ],
  sales_strategist: [
    { label: 'ICP definition', task: 'Help me define our Ideal Customer Profile with precision.' },
    { label: 'Cold outreach', task: 'Write a 3-email cold outreach sequence for our target persona.' },
  ],
  legal_advisor: [
    { label: 'Terms of service', task: 'Draft key clauses for our SaaS terms of service.', context: 'UK-based company, B2B SaaS, processing customer data' },
    { label: 'GDPR compliance', task: 'What do we need to do to be GDPR compliant before launch?' },
  ],
  financial_analyst: [
    { label: 'Unit economics', task: 'Help me calculate and optimize our unit economics.', context: 'SaaS, $49/mo plan, 5% monthly churn, $200 CAC' },
    { label: 'Fundraising readiness', task: 'Are we ready to raise a seed round? What metrics do VCs want to see?' },
  ],
  // Medtech roles
  quality_engineer: [
    { label: 'CAPA investigation', task: 'Initiate a CAPA investigation for a recurring firmware crash in production.', context: 'ISO 13485 QMS, watchdog reset root cause suspected' },
    { label: 'Audit prep', task: 'Prepare a checklist for an upcoming ISO 13485 surveillance audit.' },
  ],
  regulatory_specialist: [
    { label: '510(k) strategy', task: 'What is the regulatory pathway for our software-as-medical-device?', context: 'Class II device, software-only, EU + US markets' },
    { label: 'IEC 62304 classification', task: 'Classify our software change under IEC 62304 and determine required documentation.' },
  ],
  // Kappture roles
  privacy_officer: [
    { label: 'DPIA assessment', task: 'Conduct a Data Protection Impact Assessment for our new tracking feature.', context: 'Retail store, people counting, no face storage, GDPR applies' },
    { label: 'Data retention', task: 'Review our data retention policy for tracking analytics data.' },
  ],
  tracking_analyst: [
    { label: 'Accuracy report', task: 'Analyze our latest tracking accuracy metrics and identify improvement areas.', context: 'MOTA: 0.78, IDF1: 0.82, FP rate: 0.04, 12 cameras' },
    { label: 'False positive spike', task: 'We see a 3x increase in false positives on cameras 7 and 8 since yesterday.' },
  ],
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Agents() {
  const [selectedRole, setSelectedRole] = useState<AgentRole | null>(null)
  const [task, setTask]     = useState('')
  const [context, setContext] = useState('')
  const [results, setResults] = useState<AgentResult[]>([])
  const { data: projectData } = useProjectConfig()

  const { data: rolesData, isLoading: rolesLoading } = useQuery({
    queryKey: ['agent-roles'],
    queryFn: fetchAgentRoles,
  })

  const { mutate, isPending } = useMutation({
    mutationFn: () => runAgent(selectedRole!.id, task, context),
    onSuccess: (result) => {
      setResults(prev => [result, ...prev])
      setTask('')
      setContext('')
    },
  })

  const roles = rolesData?.roles ?? []

  if (rolesLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
        <Loader2 className="animate-spin" size={18} /> Loading agents…
      </div>
    )
  }

  if (roles.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center max-w-xl mx-auto">
        <div className="text-4xl mb-3">🤖</div>
        <div className="font-semibold text-gray-700 mb-1">No agent roles defined</div>
        <p className="text-sm text-gray-400">
          Add a <code className="bg-gray-100 px-1 rounded">roles:</code> section to this solution's{' '}
          <code className="bg-gray-100 px-1 rounded">prompts.yaml</code> to enable multi-role agents.
          <br /><br />
          Switch to the <strong>Startup Workspace</strong> solution to see 9 built-in roles.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-lg font-semibold text-gray-800">AI Agents</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          Select a role, describe your task, and get expert-level analysis with recommendations.
          Every result requires human approval before acting.
        </p>
      </div>

      {/* Role grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {roles.map(role => (
          <RoleCard
            key={role.id}
            role={role}
            selected={selectedRole?.id === role.id}
            onClick={() => setSelectedRole(role)}
          />
        ))}
      </div>

      {/* Task form */}
      {selectedRole && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">{selectedRole.icon}</span>
            <h3 className="font-semibold text-gray-800">{selectedRole.name}</h3>
            <span className="text-xs text-gray-400">— {selectedRole.description}</span>
          </div>

          {/* Task templates */}
          {TASK_TEMPLATES[selectedRole.id] && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Sparkles size={12} className="text-indigo-500" />
                <span className="text-xs font-medium text-gray-500">Quick templates</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {TASK_TEMPLATES[selectedRole.id].map(tmpl => (
                  <button
                    key={tmpl.label}
                    onClick={() => { setTask(tmpl.task); if (tmpl.context) setContext(tmpl.context) }}
                    className="text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-2.5 py-1.5
                               rounded-lg border border-indigo-200 transition-colors"
                  >
                    {tmpl.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Task / Question <span className="text-red-500">*</span>
            </label>
            <textarea
              value={task}
              onChange={e => setTask(e.target.value)}
              placeholder={`Describe what you need from the ${selectedRole.name}…`}
              rows={4}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm
                         resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Additional context <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={context}
              onChange={e => setContext(e.target.value)}
              placeholder="Company stage, constraints, existing work, relevant numbers…"
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                         resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <button
            onClick={() => mutate()}
            disabled={isPending || !task.trim()}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700
                       disabled:opacity-40 text-white text-sm font-medium
                       px-5 py-2.5 rounded-lg transition-colors"
          >
            {isPending
              ? <><Loader2 size={15} className="animate-spin" /> {selectedRole.name} is thinking…</>
              : <><span>{selectedRole.icon}</span> Ask {selectedRole.name}</>
            }
          </button>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
              Results — {results.length}
            </h3>
            <button
              onClick={() => setResults([])}
              className="text-xs text-gray-400 hover:text-red-500 transition-colors"
            >
              Clear all
            </button>
          </div>
          {results.map(r => (
            <ResultCard key={r.trace_id} result={r} />
          ))}
        </div>
      )}
    </div>
  )
}
