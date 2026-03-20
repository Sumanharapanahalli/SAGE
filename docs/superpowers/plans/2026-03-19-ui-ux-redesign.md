# UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Rebuild the SAGE sidebar into a 3-column layout (solution rail + collapsible 5-area nav + content) with hover tooltips, a 5-step onboarding wizard modal, and a 6-stop spotlight tour.

**Architecture:** The current single-sidebar (CompanyRail + flat nav) is replaced with a 44px Solution Rail + 220px Sidebar containing a solution switcher, live stats strip, and 5-area accordion nav. The existing chat-based `/onboarding` page is replaced with a modal wizard (`OnboardingWizard`). A `TourOverlay` mounts at app root and activates automatically after first solution creation. The `useTour` hook and `TourContext` are defined inside `App.tsx` to avoid a new file beyond the spec's file list. All styling is inline CSS (no new Tailwind classes); lucide-react for icons; no emojis.

**Tech Stack:** React 18, TypeScript, lucide-react, TanStack Query v5, react-router-dom v6, vitest + @testing-library/react (added in Task 1). `client.ts` is not modified — the OnboardingWizard calls `POST /onboarding/generate` via inline `fetch()`.

---

## File Map

| File | Action |
|---|---|
| `web/vite.config.ts` | Modify — add vitest config block |
| `web/package.json` | Modify — add test script + dev deps |
| `web/src/test/setup.ts` | Create — RTL setup file |
| `web/src/components/layout/Tooltip.tsx` | Create |
| `web/src/components/layout/StatsStrip.tsx` | Create |
| `web/src/components/layout/Sidebar.tsx` | Rewrite |
| `web/src/components/layout/Header.tsx` | Modify — two-line breadcrumb, remove left-side switcher |
| `web/src/components/onboarding/useTour.ts` | Create |
| `web/src/components/onboarding/OnboardingWizard.tsx` | Create |
| `web/src/components/onboarding/TourOverlay.tsx` | Create |
| `web/src/pages/Onboarding.tsx` | Replace — render OnboardingWizard directly |
| `web/src/App.tsx` | Modify — define TourContext inline, mount TourOverlay, remove `/org` OrgChart route |

---

### Task 1: Frontend test infrastructure

**Files:**
- Modify: `web/vite.config.ts`
- Modify: `web/package.json`
- Create: `web/src/test/setup.ts`

- [x] **Step 1: Install test dependencies**

```bash
cd web && npm install --save-dev vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

Expected: packages installed, no errors.

- [x] **Step 2: Add vitest config to vite.config.ts**

Read `web/vite.config.ts` first, then add the `test` block inside `defineConfig({...})`:

```ts
test: {
  environment: 'jsdom',
  globals: true,
  setupFiles: ['./src/test/setup.ts'],
},
```

- [x] **Step 3: Create test setup file**

Create `web/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom'
```

- [x] **Step 4: Add test script to package.json**

In the `scripts` block, add:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [x] **Step 5: Verify test runner works**

Create `web/src/test/smoke.test.ts`:
```ts
describe('test infrastructure', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2)
  })
})
```

Run: `cd web && npm test`
Expected: 1 test passes.

- [x] **Step 6: Delete smoke test, commit**

```bash
rm web/src/test/smoke.test.ts
git add web/vite.config.ts web/package.json web/package-lock.json web/src/test/setup.ts
git commit -m "feat(web): add vitest + testing-library test infrastructure"
```

---

### Task 2: Tooltip component

**Files:**
- Create: `web/src/components/layout/Tooltip.tsx`
- Create: `web/src/test/Tooltip.test.tsx`

- [x] **Step 1: Write the failing test**

Create `web/src/test/Tooltip.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Tooltip from '../components/layout/Tooltip'

describe('Tooltip', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('renders children', () => {
    render(<Tooltip text="hello"><span>trigger</span></Tooltip>)
    expect(screen.getByText('trigger')).toBeInTheDocument()
  })

  it('does not show tooltip before 200ms delay', () => {
    render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    fireEvent.mouseEnter(screen.getByText('trigger').parentElement!)
    expect(screen.queryByText('Tip text')).not.toBeInTheDocument()
  })

  it('shows tooltip after 200ms', () => {
    render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    fireEvent.mouseEnter(screen.getByText('trigger').parentElement!)
    vi.advanceTimersByTime(200)
    expect(screen.getByText('Tip text')).toBeInTheDocument()
  })

  it('hides tooltip on mouseleave', () => {
    render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    const wrapper = screen.getByText('trigger').parentElement!
    fireEvent.mouseEnter(wrapper)
    vi.advanceTimersByTime(200)
    expect(screen.getByText('Tip text')).toBeInTheDocument()
    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByText('Tip text')).not.toBeInTheDocument()
  })

  it('accepts side prop without error', () => {
    render(<Tooltip text="Below" side="bottom"><span>t</span></Tooltip>)
    expect(screen.getByText('t')).toBeInTheDocument()
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/Tooltip.test.tsx
```

Expected: FAIL — module not found.

- [x] **Step 3: Implement Tooltip.tsx**

Create `web/src/components/layout/Tooltip.tsx`:

```tsx
import { useState, useRef, type ReactNode } from 'react'

interface TooltipProps {
  text: string
  children: ReactNode
  side?: 'right' | 'bottom'
}

export default function Tooltip({ text, children, side = 'right' }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleMouseEnter = () => {
    timerRef.current = setTimeout(() => setVisible(true), 200)
  }

  const handleMouseLeave = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
  }

  const tooltipStyle: React.CSSProperties =
    side === 'bottom'
      ? { position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: '6px' }
      : { position: 'absolute', left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: '8px' }

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {visible && (
        <div
          style={{
            ...tooltipStyle,
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '6px 10px',
            fontSize: '11px',
            color: '#94a3b8',
            maxWidth: '220px',
            pointerEvents: 'none',
            zIndex: 50,
            whiteSpace: 'nowrap',
          }}
        >
          {text}
        </div>
      )}
    </div>
  )
}
```

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/Tooltip.test.tsx
```

Expected: 5 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/layout/Tooltip.tsx web/src/test/Tooltip.test.tsx
git commit -m "feat(web): Tooltip component with 200ms delay"
```

---

### Task 3: useTour hook

**Files:**
- Create: `web/src/components/onboarding/useTour.ts`
- Create: `web/src/test/useTour.test.ts`

- [x] **Step 1: Write the failing test**

Create `web/src/test/useTour.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTour } from '../components/onboarding/useTour'

const LS_KEY = 'sage_toured_solutions'

beforeEach(() => localStorage.clear())

describe('useTour', () => {
  it('starts inactive', () => {
    const { result } = renderHook(() => useTour())
    expect(result.current.tourState.active).toBe(false)
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('startTour activates tour', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('my_solution'))
    expect(result.current.tourState.active).toBe(true)
    expect(result.current.tourState.solutionName).toBe('my_solution')
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('nextStop increments currentStop', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('sol'))
    act(() => result.current.nextStop())
    expect(result.current.tourState.currentStop).toBe(1)
  })

  it('prevStop decrements currentStop', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('sol'))
    act(() => result.current.nextStop())
    act(() => result.current.prevStop())
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('prevStop does not go below 0', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('sol'))
    act(() => result.current.prevStop())
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('skipTour deactivates and marks toured in localStorage using solution id', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('iot_medical'))
    act(() => result.current.skipTour())
    expect(result.current.tourState.active).toBe(false)
    const stored = JSON.parse(localStorage.getItem(LS_KEY) ?? '[]')
    expect(stored).toContain('iot_medical')
  })

  it('isToured returns true for toured solution id', () => {
    localStorage.setItem(LS_KEY, JSON.stringify(['iot_medical']))
    const { result } = renderHook(() => useTour())
    expect(result.current.isToured('iot_medical')).toBe(true)
    expect(result.current.isToured('IoT Medical')).toBe(false) // display name != id
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/useTour.test.ts
```

Expected: FAIL — module not found.

- [x] **Step 3: Create useTour.ts**

First check that `web/src/components/onboarding/` exists (it does — OrgStructureChooser is there).

Create `web/src/components/onboarding/useTour.ts`:

```ts
import { useState, useCallback } from 'react'

const LS_KEY = 'sage_toured_solutions'

export interface TourState {
  active: boolean
  currentStop: number
  solutionName: string  // solution id (e.g. 'iot_medical'), not display name
}

export function useTour() {
  const [tourState, setTourState] = useState<TourState>({
    active: false,
    currentStop: 0,
    solutionName: '',
  })

  const getToured = (): string[] => {
    try { return JSON.parse(localStorage.getItem(LS_KEY) ?? '[]') } catch { return [] }
  }

  const markToured = (solutionId: string) => {
    const existing = getToured()
    if (!existing.includes(solutionId)) {
      localStorage.setItem(LS_KEY, JSON.stringify([...existing, solutionId]))
    }
  }

  const clearToured = (solutionId: string) => {
    const existing = getToured().filter(s => s !== solutionId)
    localStorage.setItem(LS_KEY, JSON.stringify(existing))
  }

  const startTour = useCallback((solutionId: string) => {
    setTourState({ active: true, currentStop: 0, solutionName: solutionId })
  }, [])

  const nextStop = useCallback(() => {
    setTourState(prev => ({ ...prev, currentStop: prev.currentStop + 1 }))
  }, [])

  const prevStop = useCallback(() => {
    setTourState(prev => ({ ...prev, currentStop: Math.max(0, prev.currentStop - 1) }))
  }, [])

  const skipTour = useCallback(() => {
    setTourState(prev => {
      markToured(prev.solutionName)
      return { active: false, currentStop: 0, solutionName: prev.solutionName }
    })
  }, [])

  const isToured = useCallback((solutionId: string): boolean => {
    return getToured().includes(solutionId)
  }, [])

  const restartTour = useCallback((solutionId: string) => {
    clearToured(solutionId)
    setTourState({ active: true, currentStop: 0, solutionName: solutionId })
  }, [])

  return { tourState, startTour, nextStop, prevStop, skipTour, isToured, restartTour }
}
```

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/useTour.test.ts
```

Expected: 7 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/onboarding/useTour.ts web/src/test/useTour.test.ts
git commit -m "feat(web): useTour hook with localStorage persistence (uses solution id as key)"
```

---

### Task 4: StatsStrip component

**Files:**
- Create: `web/src/components/layout/StatsStrip.tsx`
- Create: `web/src/test/StatsStrip.test.tsx`

Reuses `fetchPendingProposals` and `fetchQueueTasks` from `client.ts` — no new fetch functions. Polls every 10s.

- [x] **Step 1: Write the failing test**

Create `web/src/test/StatsStrip.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StatsStrip from '../components/layout/StatsStrip'

vi.mock('../api/client', () => ({
  fetchPendingProposals: vi.fn().mockResolvedValue({ proposals: [], count: 4 }),
  fetchQueueTasks: vi.fn().mockResolvedValue([
    { status: 'pending' },
    { status: 'in_progress' },
    { status: 'in_progress' },
    { status: 'completed' },
  ]),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('StatsStrip', () => {
  it('renders three tile labels', () => {
    render(<StatsStrip />, { wrapper: Wrapper })
    expect(screen.getByText('APPROVALS')).toBeInTheDocument()
    expect(screen.getByText('QUEUED')).toBeInTheDocument()
    expect(screen.getByText('AGENTS')).toBeInTheDocument()
  })

  it('shows initial 0 counts before query resolves', () => {
    render(<StatsStrip />, { wrapper: Wrapper })
    const zeros = screen.getAllByText('0')
    expect(zeros.length).toBeGreaterThanOrEqual(1)
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/StatsStrip.test.tsx
```

Expected: FAIL — module not found.

- [x] **Step 3: Implement StatsStrip.tsx**

Create `web/src/components/layout/StatsStrip.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchPendingProposals, fetchQueueTasks } from '../../api/client'
import Tooltip from './Tooltip'

export default function StatsStrip() {
  const navigate = useNavigate()

  const { data: approvalsData } = useQuery({
    queryKey: ['proposals-pending'],
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })

  const { data: queueData } = useQuery({
    queryKey: ['queue-tasks-sidebar'],
    queryFn: () => fetchQueueTasks(),
    refetchInterval: 10_000,
  })

  const approvalsCount = approvalsData?.count ?? 0
  const queuedCount = (queueData ?? []).filter(
    t => t.status === 'pending' || t.status === 'in_progress'
  ).length
  const agentsCount = (queueData ?? []).filter(t => t.status === 'in_progress').length

  const tiles = [
    { label: 'APPROVALS', count: approvalsCount, color: '#ef4444', route: '/approvals', tooltip: 'Proposals waiting for your sign-off' },
    { label: 'QUEUED',    count: queuedCount,    color: '#f59e0b', route: '/queue',     tooltip: 'Tasks in queue or actively running' },
    { label: 'AGENTS',    count: agentsCount,    color: '#10b981', route: '/queue',     tooltip: 'Agent tasks currently in progress' },
  ]

  return (
    <div style={{ display: 'flex', borderBottom: '1px solid #1e293b' }}>
      {tiles.map(({ label, count, color, route, tooltip }) => (
        <Tooltip key={label} text={tooltip} side="bottom">
          <button
            onClick={() => navigate(route)}
            style={{
              flex: 1,
              padding: '8px 4px',
              textAlign: 'center',
              background: 'transparent',
              border: 'none',
              borderRight: label !== 'AGENTS' ? '1px solid #1e293b' : 'none',
              cursor: 'pointer',
            }}
          >
            <div style={{ fontSize: '16px', fontWeight: 700, color, lineHeight: 1 }}>
              {count}
            </div>
            <div style={{ fontSize: '9px', color: '#475569', marginTop: '2px', letterSpacing: '0.05em' }}>
              {label}
            </div>
          </button>
        </Tooltip>
      ))}
    </div>
  )
}
```

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/StatsStrip.test.tsx
```

Expected: 2 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/layout/StatsStrip.tsx web/src/test/StatsStrip.test.tsx
git commit -m "feat(web): StatsStrip — live-polling APPROVALS/QUEUED/AGENTS tiles"
```

---

### Task 5: Sidebar rewrite

**Files:**
- Rewrite: `web/src/components/layout/Sidebar.tsx`
- Create: `web/src/test/Sidebar.test.tsx`

5 areas with routes and accent colours:
- **Work** `#ef4444`: Approvals, Task Queue, Dashboard, Live Console
- **Intelligence** `#a78bfa`: Agents, Analyst, Developer, Monitor, Improvements, Workflows, Goals
- **Knowledge** `#10b981`: Vector Store (`/settings` — no `/knowledge` route exists), Channels (`/activity`, moduleId `audit`), Audit Log (`/audit`, moduleId `audit`), Costs
- **Organization** `#3b82f6`: Org Graph (`/org-graph`), Onboarding (`/onboarding`)
- **Admin** `#475569`: LLM Settings, Config Editor, Access Control, Integrations, Settings

**Note on Channels moduleId:** The spec does not add new moduleIds. "Channels" maps to `/activity` and shares `moduleId: 'audit'` with Audit Log — consistent with the existing Sidebar's `Activity` entry. Both items will show/hide together when the `audit` module is toggled. If independent visibility control is needed later, a new `channels` entry in `MODULE_REGISTRY` is the fix; that is out of scope here.

**Note on isToured in SolutionSwitcher:** Pass the solution **id** (e.g. `iot_medical`), not the display name. The `activeId` from `fetchHealth` is the correct key.

- [x] **Step 1: Write the failing test**

Create `web/src/test/Sidebar.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'

vi.mock('../api/client', () => ({
  fetchPendingProposals: vi.fn().mockResolvedValue({ proposals: [], count: 0 }),
  fetchQueueTasks: vi.fn().mockResolvedValue([]),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [
    { id: 'iot_medical', name: 'IoT Medical', domain: 'medical', version: '1.0', description: '' }
  ], active: 'iot_medical' }),
  fetchHealth: vi.fn().mockResolvedValue({ project: { project: 'iot_medical' }, llm_provider: 'gemini' }),
  switchProject: vi.fn().mockResolvedValue({ status: 'switched' }),
}))

vi.mock('../hooks/useProjectConfig', () => ({
  useProjectConfig: () => ({ data: { name: 'IoT Medical', active_modules: [] } }),
}))

// TourContext needs to be mocked since TourProvider lives in App
vi.mock('../App', () => ({}))

// Provide a minimal TourContext inline
vi.mock('../context/TourContext', () => ({
  useTourContext: () => ({
    openWizard: vi.fn(),
    closeWizard: vi.fn(),
    wizardOpen: false,
    startTour: vi.fn(),
    isToured: vi.fn(() => false),
    restartTour: vi.fn(),
    tourState: { active: false, currentStop: 0, solutionName: '' },
    nextStop: vi.fn(), prevStop: vi.fn(), skipTour: vi.fn(),
  }),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/']}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Sidebar', () => {
  it('renders all 5 area headers', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('Work')).toBeInTheDocument()
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Knowledge')).toBeInTheDocument()
    expect(screen.getByText('Organization')).toBeInTheDocument()
    expect(screen.getByText('Admin')).toBeInTheDocument()
  })

  it('Work area is open by default', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('Approvals')).toBeInTheDocument()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('Intelligence area is collapsed by default', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.queryByText('Analyst')).not.toBeInTheDocument()
  })

  it('clicking Intelligence header expands it and collapses Work', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    fireEvent.click(screen.getByText('Intelligence'))
    expect(screen.getByText('Analyst')).toBeInTheDocument()
    expect(screen.queryByText('Approvals')).not.toBeInTheDocument()
  })

  it('solution switcher shows active solution name', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('IoT Medical')).toBeInTheDocument()
  })

  it('stats strip tiles are rendered', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('APPROVALS')).toBeInTheDocument()
    expect(screen.getByText('QUEUED')).toBeInTheDocument()
    expect(screen.getByText('AGENTS')).toBeInTheDocument()
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/Sidebar.test.tsx
```

Expected: FAIL.

- [x] **Step 3: Implement new Sidebar.tsx**

Completely replace `web/src/components/layout/Sidebar.tsx`. Key sections:

**Imports** — remove unused old imports, add:
```ts
import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Lightbulb, Cpu, Settings, FileCode2, Bot,
  Terminal, Wand2, Plug, ListOrdered, ShieldCheck, DollarSign,
  GitBranch, Target, Inbox, Network, Building2,
  CheckSquare, Zap, Database, BookOpen, Shield,
  ChevronDown, ChevronsUpDown, type LucideIcon,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchProjects, fetchHealth, switchProject } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import Tooltip from './Tooltip'
import StatsStrip from './StatsStrip'
import { useTourContext } from '../../context/TourContext'
import OnboardingWizard from '../onboarding/OnboardingWizard'
```

**initials helper:**
```ts
function initials(id: string): string {
  const words = id.split(/[_\s-]+/).filter(Boolean)
  if (words.length === 1) return id.slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}
```

**NAV_AREAS definition:**
```ts
interface NavItem {
  to: string; icon: LucideIcon; label: string; moduleId: string; tooltip: string
}
interface NavArea {
  id: string; label: string; icon: LucideIcon; accent: string; items: NavItem[]
}

const NAV_AREAS: NavArea[] = [
  {
    id: 'work', label: 'Work', icon: CheckSquare, accent: '#ef4444',
    items: [
      { to: '/approvals',    icon: Inbox,          label: 'Approvals',   moduleId: 'approvals',    tooltip: 'Agent proposals waiting for your review before execution' },
      { to: '/queue',        icon: ListOrdered,    label: 'Task Queue',  moduleId: 'queue',        tooltip: 'Tasks currently queued or running across all agents' },
      { to: '/',             icon: LayoutDashboard,label: 'Dashboard',   moduleId: 'dashboard',    tooltip: 'System health, recent activity, and integration status' },
      { to: '/live-console', icon: Terminal,       label: 'Live Console',moduleId: 'live-console', tooltip: 'Real-time backend log stream' },
    ],
  },
  {
    id: 'intelligence', label: 'Intelligence', icon: Zap, accent: '#a78bfa',
    items: [
      { to: '/agents',       icon: Bot,       label: 'Agents',      moduleId: 'agents',       tooltip: "Submit a task to an agent role defined in this solution's prompts.yaml" },
      { to: '/analyst',      icon: Search,    label: 'Analyst',     moduleId: 'analyst',      tooltip: 'AI triage of log entries and error signals' },
      { to: '/developer',    icon: GitMerge,  label: 'Developer',   moduleId: 'developer',    tooltip: 'Code review and merge request creation via connected GitLab' },
      { to: '/monitor',      icon: Activity,  label: 'Monitor',     moduleId: 'monitor',      tooltip: 'Live status of all configured integration polling threads' },
      { to: '/improvements', icon: Lightbulb, label: 'Improvements',moduleId: 'improvements', tooltip: 'Feature request queue and AI-generated implementation plans' },
      { to: '/workflows',    icon: GitBranch, label: 'Workflows',   moduleId: 'workflows',    tooltip: 'LangGraph workflow definitions and execution history' },
      { to: '/goals',        icon: Target,    label: 'Goals',       moduleId: 'improvements', tooltip: 'High-level objectives tracked against in-progress work' },
    ],
  },
  {
    id: 'knowledge', label: 'Knowledge', icon: Database, accent: '#10b981',
    items: [
      { to: '/settings',  icon: BookOpen,      label: 'Vector Store', moduleId: 'settings', tooltip: "Search and manage entries in this solution's knowledge base" },
      { to: '/activity',  icon: Activity,      label: 'Channels',     moduleId: 'audit',    tooltip: 'Cross-team knowledge channels shared via org configuration' },
      { to: '/audit',     icon: ClipboardList, label: 'Audit Log',    moduleId: 'audit',    tooltip: 'Full compliance audit trail — proposals, approvals, rejections' },
      { to: '/costs',     icon: DollarSign,    label: 'Costs',        moduleId: 'costs',    tooltip: 'LLM token usage and budget controls per solution' },
    ],
  },
  {
    id: 'organization', label: 'Organization', icon: Building2, accent: '#3b82f6',
    items: [
      { to: '/org-graph',  icon: Network, label: 'Org Graph',  moduleId: 'org',        tooltip: 'React Flow graph of solutions, knowledge channels, and task routing' },
      { to: '/onboarding', icon: Wand2,   label: 'Onboarding', moduleId: 'onboarding', tooltip: 'Generate a new solution from a plain-language description' },
    ],
  },
  {
    id: 'admin', label: 'Admin', icon: Shield, accent: '#475569',
    items: [
      { to: '/llm',            icon: Cpu,        label: 'LLM Settings',   moduleId: 'llm',            tooltip: 'Switch LLM provider and model; view session token usage' },
      { to: '/yaml-editor',    icon: FileCode2,  label: 'Config Editor',  moduleId: 'yaml-editor',    tooltip: 'Edit solution YAML files with live validation' },
      { to: '/access-control', icon: ShieldCheck,label: 'Access Control', moduleId: 'access-control', tooltip: 'Manage API keys and user role assignments' },
      { to: '/integrations',   icon: Plug,       label: 'Integrations',   moduleId: 'integrations',   tooltip: 'Status and configuration for all connected integrations' },
      { to: '/settings',       icon: Settings,   label: 'Settings',       moduleId: 'settings',       tooltip: 'Framework-wide settings and display preferences' },
    ],
  },
]
```

**SolutionRail subcomponent** (inside Sidebar.tsx, not exported):
```tsx
function SolutionRail({ onOpenWizard }: { onOpenWizard: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })
  const activeId = (healthData as any)?.project?.project ?? ''

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 60_000 })
  const switchMutation = useMutation({
    mutationFn: (id: string) => switchProject(id),
    onSuccess: () => queryClient.invalidateQueries(),
  })

  const solutions = projectsData?.projects ?? []

  return (
    <div
      data-tour="solution-rail"
      style={{ width: '44px', display: 'flex', flexDirection: 'column', alignItems: 'center',
               height: '100%', padding: '8px 0', backgroundColor: '#020617',
               borderRight: '1px solid #0f172a', flexShrink: 0 }}
    >
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                    overflowY: 'auto', width: '100%', paddingTop: '4px' }}>
        {solutions.map(sol => (
          <Tooltip key={sol.id} text={sol.name}>
            <button
              onClick={() => sol.id !== activeId && switchMutation.mutate(sol.id)}
              style={{
                width: '28px', height: '28px', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: '10px', fontWeight: 700, flexShrink: 0,
                backgroundColor: sol.id === activeId ? '#3b82f6' : '#1e293b',
                color: sol.id === activeId ? '#fff' : '#64748b',
                cursor: sol.id === activeId ? 'default' : 'pointer',
              }}
            >
              {initials(sol.id)}
            </button>
          </Tooltip>
        ))}
      </div>
      <Tooltip text="Create a new solution">
        <button
          onClick={onOpenWizard}
          style={{ width: '28px', height: '28px', color: '#334155', fontSize: '18px',
                   lineHeight: 1, marginBottom: '8px', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          +
        </button>
      </Tooltip>
      <Tooltip text="View organization graph">
        <button
          onClick={() => navigate('/org-graph')}
          style={{ width: '32px', height: '32px', color: '#334155', background: 'none',
                   border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Building2 size={16} />
        </button>
      </Tooltip>
    </div>
  )
}
```

**SolutionSwitcher subcomponent** (inside Sidebar.tsx):
```tsx
interface SwitcherProps {
  projectName: string
  solutions: Array<{ id: string; name: string }>
  activeId: string
  onSwitch: (id: string) => void
  showRestartTour: boolean       // pass isToured(activeId)
  onRestartTour: () => void      // pass () => restartTour(activeId)
}

function SolutionSwitcher({ projectName, solutions, activeId, onSwitch, showRestartTour, onRestartTour }: SwitcherProps) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ position: 'relative', borderBottom: '1px solid #1e293b' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', width: '100%', alignItems: 'center', gap: '6px',
                 padding: '10px 12px', background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <span style={{ flex: 1, fontSize: '13px', fontWeight: 600, color: '#f1f5f9',
                       overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
          {projectName}
        </span>
        <ChevronsUpDown size={14} style={{ color: '#475569', flexShrink: 0 }} />
      </button>
      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 10 }} onClick={() => setOpen(false)} />
          <div style={{ position: 'absolute', left: 0, top: '100%', width: '100%', zIndex: 20,
                        backgroundColor: '#0f172a', border: '1px solid #1e293b',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
            {solutions.map(sol => (
              <button
                key={sol.id}
                onClick={() => { onSwitch(sol.id); setOpen(false) }}
                disabled={sol.id === activeId}
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                         fontSize: '12px', color: sol.id === activeId ? '#f1f5f9' : '#64748b',
                         backgroundColor: sol.id === activeId ? '#172033' : 'transparent',
                         border: 'none', cursor: sol.id === activeId ? 'default' : 'pointer' }}
              >
                {sol.name}
              </button>
            ))}
            {showRestartTour && (
              <>
                <div style={{ borderTop: '1px solid #1e293b', margin: '4px 0' }} />
                <button
                  onClick={() => { onRestartTour(); setOpen(false) }}
                  style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                           fontSize: '12px', color: '#64748b', background: 'none',
                           border: 'none', cursor: 'pointer' }}
                >
                  Restart tour
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
```

**Main Sidebar component:**
```tsx
export default function Sidebar() {
  const [openArea, setOpenArea] = useState<string>('work')
  const { pathname } = useLocation()
  const queryClient = useQueryClient()
  const { openWizard, wizardOpen, closeWizard, startTour, isToured, restartTour } = useTourContext()

  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })
  const activeId = (healthData as any)?.project?.project ?? ''

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 60_000 })
  const switchMutation = useMutation({
    mutationFn: (id: string) => switchProject(id),
    onSuccess: () => queryClient.invalidateQueries(),
  })

  const { data: projectData } = useProjectConfig()
  const activeModules: string[] = projectData?.active_modules ?? []
  const projectName = projectData?.name ?? 'SAGE'
  const isVisible = (moduleId: string) =>
    activeModules.length === 0 || activeModules.includes(moduleId)

  // Auto-expand the area containing the active route
  useEffect(() => {
    for (const area of NAV_AREAS) {
      if (area.items.some(item => item.to === pathname || (item.to === '/' && pathname === '/'))) {
        setOpenArea(area.id)
        return
      }
    }
  }, [pathname])

  const solutions = projectsData?.projects ?? []

  return (
    <aside style={{ display: 'flex', height: '100%', flexShrink: 0 }}>
      <SolutionRail onOpenWizard={openWizard} />
      <div style={{ width: '220px', display: 'flex', flexDirection: 'column', height: '100%',
                    backgroundColor: 'var(--sage-sidebar-bg)', borderRight: '1px solid #1e293b' }}>
        <SolutionSwitcher
          projectName={projectName}
          solutions={solutions}
          activeId={activeId}
          onSwitch={(id) => switchMutation.mutate(id)}
          showRestartTour={isToured(activeId)}
          onRestartTour={() => restartTour(activeId)}
        />
        <div data-tour="stats-strip">
          <StatsStrip />
        </div>
        <nav style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
          {NAV_AREAS.map(area => {
            const visibleItems = area.items.filter(({ moduleId }) => isVisible(moduleId))
            if (visibleItems.length === 0) return null
            const isOpen = openArea === area.id
            return (
              <div key={area.id}>
                <button
                  data-tour={`area-${area.id}`}
                  onClick={() => setOpenArea(isOpen ? '' : area.id)}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
                           padding: '6px 12px', background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  <area.icon size={13} style={{ color: area.accent, flexShrink: 0 }} />
                  <span style={{ flex: 1, fontSize: '11px', fontWeight: 600, color: '#94a3b8',
                                 textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    {area.label}
                  </span>
                  {!isOpen && (
                    <span style={{ fontSize: '10px', color: '#334155' }}>{visibleItems.length}</span>
                  )}
                  <ChevronDown
                    size={12}
                    style={{ color: '#334155', flexShrink: 0,
                             transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.15s' }}
                  />
                </button>
                {isOpen && visibleItems.map(item => (
                  <Tooltip key={item.to + item.label} text={item.tooltip}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/'}
                      data-tour={item.label === 'Approvals' ? 'nav-approvals' : item.label === 'Task Queue' ? 'nav-queue' : undefined}
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
                               padding: '6px 12px 6px 28px', fontSize: '12px', textDecoration: 'none',
                               borderLeft: `2px solid ${area.accent}20` }}
                      className={({ isActive }) => isActive ? 'sage-nav-item-active' : ''}
                    >
                      {({ isActive }) => (
                        <>
                          <item.icon size={13} />
                          <span style={{ color: isActive ? '#93c5fd' : '#64748b' }}>{item.label}</span>
                        </>
                      )}
                    </NavLink>
                  </Tooltip>
                ))}
              </div>
            )
          })}
        </nav>
        <div style={{ padding: '8px 12px', borderTop: '1px solid #1e293b', color: '#334155', fontSize: '11px' }}>
          SAGE Framework {SAGE_VERSION}
        </div>
      </div>
      {wizardOpen && (
        <OnboardingWizard
          onClose={closeWizard}
          onTourStart={(solutionId) => { closeWizard(); startTour(solutionId) }}
        />
      )}
    </aside>
  )
}
```

The `SAGE_VERSION` constant remains at the top of the file (keep from original).

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/Sidebar.test.tsx
```

Expected: 6 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/layout/Sidebar.tsx web/src/test/Sidebar.test.tsx
git commit -m "feat(web): Sidebar rewrite — solution rail + 5-area collapsible nav + stats strip"
```

---

### Task 6: Header breadcrumb

**Files:**
- Modify: `web/src/components/layout/Header.tsx`
- Create: `web/src/test/Header.test.tsx`

The solution switcher moves to Sidebar. The header's left area becomes a two-line breadcrumb. Right side (Cmd+K, status dot, Stop SAGE) is preserved unchanged.

`ROUTE_TO_AREA` map (covers all routes):
```ts
const ROUTE_TO_AREA: Record<string, string> = {
  '/':              'Work',
  '/approvals':     'Work',
  '/queue':         'Work',
  '/live-console':  'Work',
  '/agents':        'Intelligence',
  '/analyst':       'Intelligence',
  '/developer':     'Intelligence',
  '/monitor':       'Intelligence',
  '/improvements':  'Intelligence',
  '/workflows':     'Intelligence',
  '/goals':         'Intelligence',
  '/audit':         'Knowledge',
  '/costs':         'Knowledge',
  '/activity':      'Knowledge',
  '/issues':        'Knowledge',
  '/org-graph':     'Organization',
  '/onboarding':    'Organization',
  '/llm':           'Admin',
  '/yaml-editor':   'Admin',
  '/access-control':'Admin',
  '/integrations':  'Admin',
  '/settings':      'Admin',
}
```

- [x] **Step 1: Write the failing test**

Create `web/src/test/Header.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Header from '../components/layout/Header'

vi.mock('../api/client', () => ({
  fetchHealth: vi.fn().mockResolvedValue({ project: { project: 'iot_medical' }, llm_provider: 'gemini' }),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [], active: 'iot_medical' }),
  switchProject: vi.fn(),
}))

vi.mock('../hooks/useProjectConfig', () => ({
  useProjectConfig: () => ({
    data: { name: 'IoT Medical', domain: 'medical', active_modules: [], ui_labels: {} }
  }),
}))

function Wrapper({ path = '/', children }: { path?: string; children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Header breadcrumb', () => {
  it('shows solution name and Work area for /', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/">{p.children}</Wrapper> })
    expect(screen.getByText(/IoT Medical/)).toBeInTheDocument()
    expect(screen.getByText(/Work/)).toBeInTheDocument()
  })

  it('shows Intelligence area for /analyst', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/analyst">{p.children}</Wrapper> })
    expect(screen.getByText(/Intelligence/)).toBeInTheDocument()
  })

  it('shows Admin area for /settings', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/settings">{p.children}</Wrapper> })
    expect(screen.getByText(/Admin/)).toBeInTheDocument()
  })

  it('preserves page title on line 2', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/analyst">{p.children}</Wrapper> })
    expect(screen.getByText('Log Analyst')).toBeInTheDocument()
  })

  it('does not render solution switcher dropdown button', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/">{p.children}</Wrapper> })
    // The old switcher had "Switch solution" title; it should be gone
    expect(screen.queryByTitle('Switch solution')).not.toBeInTheDocument()
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/Header.test.tsx
```

Expected: FAIL.

- [x] **Step 3: Modify Header.tsx**

Read `web/src/components/layout/Header.tsx`. Apply these changes:

1. Add `ROUTE_TO_AREA` map (above the component).
2. Remove: `switcherOpen` state, `setSwitcherOpen`, `switchMutation`, the solution switcher button, dropdown markup, `projectsData` query, `DOMAIN_BADGE_COLORS` map.
3. Replace the left-area div with:

```tsx
{/* Breadcrumb + page title */}
<div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1, minWidth: 0 }}>
  <div style={{ fontSize: '11px', color: '#64748b' }}>
    {projectName} / {ROUTE_TO_AREA[pathname] ?? 'SAGE'}
  </div>
  <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', marginTop: '1px' }}>
    {title}
  </div>
</div>
```

4. Keep: `onOpenPalette` prop, Cmd+K button, API status dot, Stop SAGE confirm.
5. The `PAGE_TITLES` map and `UI_LABEL_ROUTES` logic remain unchanged (still compute `title`).
6. The header div changes from `h-12` to `h-14` (56px) to comfortably fit two lines:
   Change `className="h-12 border-b flex items-center px-4 gap-3 shrink-0 relative"` to `className="h-14 border-b flex items-center px-4 gap-3 shrink-0 relative"`.

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/Header.test.tsx
```

Expected: 5 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/layout/Header.tsx web/src/test/Header.test.tsx
git commit -m "feat(web): Header two-line breadcrumb with ROUTE_TO_AREA map, remove switcher"
```

---

### Task 7: OnboardingWizard

**Files:**
- Create: `web/src/components/onboarding/OnboardingWizard.tsx`
- Create: `web/src/test/OnboardingWizard.test.tsx`

5-step modal. Uses inline `fetch()` to call `POST /onboarding/generate` — **`client.ts` is not modified per spec**.

Step 5's "Start tour" button must call `POST /config/switch` (via `switchProject` from `client.ts`) to activate the new solution before starting the tour.

Step 4 must include an "Open in Config Editor" button per YAML tab that navigates to `/yaml-editor` and closes the wizard.

- [x] **Step 1: Write the failing test**

Create `web/src/test/OnboardingWizard.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import OnboardingWizard from '../components/onboarding/OnboardingWizard'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

vi.mock('../api/client', () => ({
  fetchProjects: vi.fn().mockResolvedValue({ projects: [], active: '' }),
  switchProject: vi.fn().mockResolvedValue({ status: 'switched' }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: vi.fn(() => vi.fn()) }
})

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

const defaultProps = { onClose: vi.fn(), onTourStart: vi.fn() }

beforeEach(() => {
  mockFetch.mockReset()
  defaultProps.onClose.mockReset()
  defaultProps.onTourStart.mockReset()
})

describe('OnboardingWizard', () => {
  it('renders step 1 by default', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByText(/What does this solution do/)).toBeInTheDocument()
  })

  it('shows 5 step circles', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByText(String(i))).toBeInTheDocument()
    }
  })

  it('Next disabled when description empty', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('Next enabled when description and solution_name filled', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), {
      target: { value: 'A monitoring platform' },
    })
    fireEvent.change(screen.getByLabelText(/Solution name/i), {
      target: { value: 'mon_platform' },
    })
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
  })

  it('step 2 has Skip link', async () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), {
      target: { value: 'A monitoring platform' },
    })
    fireEvent.change(screen.getByLabelText(/Solution name/i), {
      target: { value: 'mon_platform' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Skip')).toBeInTheDocument()
  })

  it('calls POST /onboarding/generate when reaching step 3', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        solution_name: 'mon_platform', path: '/solutions/mon_platform', status: 'created',
        files: { 'project.yaml': 'name: mon\n', 'prompts.yaml': '# prompts', 'tasks.yaml': '# tasks' },
        message: 'ok', suggested_routes: [],
      }),
    })

    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), { target: { value: 'A platform' } })
    fireEvent.change(screen.getByLabelText(/Solution name/i), { target: { value: 'my_app' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Skip')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Skip'))

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/onboarding/generate'),
        expect.objectContaining({ method: 'POST' })
      )
    )
  })

  it('step 4 shows YAML tabs and Open in Config Editor button', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        solution_name: 'my_app', path: '/solutions/my_app', status: 'created',
        files: { 'project.yaml': 'name: my_app\n', 'prompts.yaml': '# prompts', 'tasks.yaml': '# tasks' },
        message: 'ok', suggested_routes: [],
      }),
    })

    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), { target: { value: 'A platform' } })
    fireEvent.change(screen.getByLabelText(/Solution name/i), { target: { value: 'my_app' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.click(await screen.findByText('Skip'))

    // Wait for step 4
    expect(await screen.findByText('project.yaml')).toBeInTheDocument()
    expect(screen.getByText('prompts.yaml')).toBeInTheDocument()
    expect(screen.getByText('tasks.yaml')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Open in Config Editor/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Looks good' })).toBeInTheDocument()
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/OnboardingWizard.test.tsx
```

Expected: FAIL — module not found.

- [x] **Step 3: Implement OnboardingWizard.tsx**

Create `web/src/components/onboarding/OnboardingWizard.tsx`. The API call is inline (no client.ts modification):

```tsx
import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchProjects, switchProject } from '../../api/client'
import { Check, Loader2, ChevronDown } from 'lucide-react'

const API_BASE = (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000'

interface GenerateRequest {
  description: string; solution_name: string
  compliance_standards: string[]; integrations: string[]
  parent_solution?: string; org_name?: string
}
interface GenerateResponse {
  solution_name: string; path: string; status: 'created' | 'exists'
  files: Record<string, string>; message: string; suggested_routes: string[]
}

async function callGenerate(body: GenerateRequest): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE}/onboarding/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const msg = await res.text()
    throw new Error(msg || 'Generation failed')
  }
  return res.json()
}

// ─── Progress bar ────────────────────────────────────────────────────────────
function ProgressBar({ step }: { step: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '16px 24px' }}>
      {[1,2,3,4,5].map((n, i) => (
        <div key={n} style={{ display: 'flex', alignItems: 'center', flex: i < 4 ? 1 : 'none' }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: '12px', fontWeight: 700, flexShrink: 0,
            backgroundColor: n < step ? '#10b981' : n === step ? '#3b82f6' : '#1e293b',
            color: n <= step ? '#fff' : '#475569',
          }}>
            {n < step ? <Check size={14} /> : n}
          </div>
          {i < 4 && (
            <div style={{ flex: 1, height: '2px', backgroundColor: n < step ? '#10b981' : '#1e293b' }} />
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────
interface Props {
  onClose: () => void
  onTourStart: (solutionId: string) => void
}

const YAML_FILES = ['project.yaml', 'prompts.yaml', 'tasks.yaml']
const COMPLIANCE_OPTIONS = ['ISO 13485', 'IEC 62304', 'ISO 9001', 'FDA 21 CFR Part 11', 'None']
const INTEGRATION_OPTIONS = ['GitLab', 'Slack', 'GitHub', 'None']

export default function OnboardingWizard({ onClose, onTourStart }: Props) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({ description: '', solution_name: '', parent_solution: '', org_name: '' })
  const [compliance, setCompliance] = useState<string[]>([])
  const [integrations, setIntegrations] = useState<string[]>([])
  const [generateResult, setGenerateResult] = useState<GenerateResponse | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [activeYamlTab, setActiveYamlTab] = useState('project.yaml')

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 60_000 })
  const solutions = projectsData?.projects ?? []

  // Auto-slugify description on first type
  useEffect(() => {
    if (form.description && !form.solution_name) {
      const slug = form.description.toLowerCase()
        .replace(/[^a-z0-9\s]/g, '').trim().replace(/\s+/g, '_').slice(0, 40)
      setForm(f => ({ ...f, solution_name: slug }))
    }
  }, [form.description])

  const generateMutation = useMutation({
    mutationFn: () => callGenerate({
      description: form.description, solution_name: form.solution_name,
      compliance_standards: compliance.filter(c => c !== 'None'),
      integrations: integrations.filter(i => i !== 'None').map(i => i.toLowerCase()),
      parent_solution: form.parent_solution || undefined,
      org_name: form.org_name || undefined,
    }),
    onSuccess: (res) => { setGenerateResult(res); setStep(4) },
    onError: (err: Error) => setGenerateError(err.message),
  })

  const switchMutation = useMutation({ mutationFn: (id: string) => switchProject(id) })

  // Trigger generation when step 3 mounts
  useEffect(() => {
    if (step === 3 && !generateMutation.isPending && !generateResult && !generateError) {
      generateMutation.mutate()
    }
  }, [step])

  const toggleList = (list: string[], setList: (v: string[]) => void, val: string) => {
    setList(list.includes(val) ? list.filter(x => x !== val) : [...list, val])
  }

  // ── Overlay wrapper ──
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.75)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ maxWidth: '560px', width: '100%', background: '#0f172a', borderRadius: '12px',
                    border: '1px solid #1e293b', overflow: 'hidden' }}>
        <ProgressBar step={step} />

        {/* Step 1 */}
        {step === 1 && (
          <div style={{ padding: '0 24px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '16px' }}>
              Describe your solution
            </h2>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                What does this solution do?
              </label>
              <textarea
                placeholder="Describe your solution..."
                rows={3}
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155',
                         borderRadius: '6px', padding: '8px', color: '#f1f5f9', fontSize: '13px',
                         resize: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ marginBottom: '12px' }}>
              <label htmlFor="solution-name" style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                Solution name
              </label>
              <input
                id="solution-name"
                aria-label="Solution name"
                value={form.solution_name}
                onChange={e => setForm(f => ({ ...f, solution_name: e.target.value }))}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155',
                         borderRadius: '6px', padding: '8px', color: '#f1f5f9', fontSize: '13px',
                         boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                Parent solution (optional)
              </label>
              <select
                value={form.parent_solution}
                onChange={e => setForm(f => ({ ...f, parent_solution: e.target.value }))}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155',
                         borderRadius: '6px', padding: '8px', color: '#f1f5f9', fontSize: '13px' }}
              >
                <option value="">None</option>
                {solutions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={onClose}
                style={{ padding: '8px 16px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px' }}>
                Cancel
              </button>
              <button
                onClick={() => setStep(2)}
                disabled={!form.description.trim() || !form.solution_name.trim()}
                style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px',
                         fontSize: '13px', cursor: 'pointer', opacity: (!form.description.trim() || !form.solution_name.trim()) ? 0.4 : 1 }}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div style={{ padding: '0 24px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '16px' }}>
              Compliance and integrations
            </h2>
            <div style={{ marginBottom: '16px' }}>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px' }}>Compliance standards</p>
              {COMPLIANCE_OPTIONS.map(opt => (
                <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '8px',
                                          marginBottom: '6px', fontSize: '13px', color: '#cbd5e1', cursor: 'pointer' }}>
                  <input type="checkbox" checked={compliance.includes(opt)}
                    onChange={() => toggleList(compliance, setCompliance, opt)} />
                  {opt}
                </label>
              ))}
            </div>
            <div style={{ marginBottom: '16px' }}>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px' }}>Integrations</p>
              {INTEGRATION_OPTIONS.map(opt => (
                <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '8px',
                                          marginBottom: '6px', fontSize: '13px', color: '#cbd5e1', cursor: 'pointer' }}>
                  <input type="checkbox" checked={integrations.includes(opt)}
                    onChange={() => toggleList(integrations, setIntegrations, opt)} />
                  {opt}
                </label>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button onClick={() => setStep(3)} style={{ fontSize: '13px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer' }}>
                Skip
              </button>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => setStep(1)} style={{ padding: '8px 16px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px' }}>
                  Back
                </button>
                <button onClick={() => setStep(3)}
                  style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}>
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3 — Generating */}
        {step === 3 && (
          <div style={{ padding: '32px 24px', textAlign: 'center' }}>
            {generateError ? (
              <>
                <div style={{ color: '#ef4444', marginBottom: '12px', fontSize: '13px' }}>{generateError}</div>
                <button
                  onClick={() => { setGenerateError(null); generateMutation.mutate() }}
                  style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}
                >
                  Try again
                </button>
              </>
            ) : (
              <>
                <Loader2 size={24} style={{ color: '#3b82f6', margin: '0 auto 16px', display: 'block',
                                            animation: 'spin 1s linear infinite' }} />
                {['Generating project.yaml', 'Generating prompts.yaml', 'Generating tasks.yaml'].map(msg => (
                  <div key={msg} style={{ fontSize: '13px', color: '#64748b', marginBottom: '6px' }}>{msg}</div>
                ))}
              </>
            )}
          </div>
        )}

        {/* Step 4 — Review YAML */}
        {step === 4 && generateResult && (
          <div style={{ padding: '0 24px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '12px' }}>
              Review generated YAML
            </h2>
            <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
              {YAML_FILES.map(f => (
                <button key={f} onClick={() => setActiveYamlTab(f)}
                  style={{ padding: '4px 10px', fontSize: '11px', borderRadius: '4px', cursor: 'pointer',
                           background: activeYamlTab === f ? '#1e293b' : 'transparent',
                           color: activeYamlTab === f ? '#f1f5f9' : '#64748b', border: 'none' }}>
                  {f}
                </button>
              ))}
            </div>
            <pre style={{ fontFamily: 'monospace', fontSize: '12px', background: '#020617', borderRadius: '6px',
                          padding: '12px', overflowY: 'auto', maxHeight: '280px', color: '#94a3b8', margin: 0 }}>
              {generateResult.files[activeYamlTab] ?? ''}
            </pre>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'center' }}>
              <button
                onClick={() => { onClose(); navigate(`/yaml-editor?file=${activeYamlTab}`) }}
                style={{ padding: '6px 12px', background: '#1e293b', color: '#94a3b8',
                         borderRadius: '6px', fontSize: '12px', border: '1px solid #334155', cursor: 'pointer' }}
              >
                Open in Config Editor
              </button>
              <button onClick={() => setStep(5)}
                style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}>
                Looks good
              </button>
            </div>
          </div>
        )}

        {/* Step 5 — Ready */}
        {step === 5 && generateResult && (
          <div style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '12px' }}>
              Solution ready
            </h2>
            <p style={{ color: '#94a3b8', marginBottom: '8px', fontSize: '13px' }}>
              Solution <strong style={{ color: '#f1f5f9' }}>{generateResult.solution_name}</strong> created.
              {generateResult.suggested_routes.length > 0 &&
                ` Suggested routes: ${generateResult.suggested_routes.join(', ')}.`}
            </p>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '16px' }}>
              <button
                onClick={async () => {
                  await switchMutation.mutateAsync(generateResult.solution_name)
                  onTourStart(generateResult.solution_name)
                }}
                style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}
              >
                Start tour
              </button>
              <button
                onClick={async () => {
                  await switchMutation.mutateAsync(generateResult.solution_name)
                  onClose()
                  navigate('/')
                }}
                style={{ fontSize: '13px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Go to dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/OnboardingWizard.test.tsx
```

Expected: 6 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/onboarding/OnboardingWizard.tsx web/src/test/OnboardingWizard.test.tsx
git commit -m "feat(web): 5-step OnboardingWizard with inline fetch, YAML review, Config Editor link"
```

---

### Task 8: TourOverlay

**Files:**
- Create: `web/src/components/onboarding/TourOverlay.tsx`
- Create: `web/src/test/TourOverlay.test.tsx`

6-stop spotlight overlay. Reads tour state from `TourContext` (defined in App.tsx — see Task 9).

- [x] **Step 1: Write the failing test**

Create `web/src/test/TourOverlay.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TourOverlay from '../components/onboarding/TourOverlay'

const mockSkipTour = vi.fn()
const mockNextStop = vi.fn()
const mockPrevStop = vi.fn()

// Mock TourContext — defined in App.tsx but imported via the context path
vi.mock('../context/TourContext', () => ({
  useTourContext: vi.fn(() => ({
    tourState: { active: true, currentStop: 0, solutionName: 'my_app' },
    nextStop: mockNextStop,
    prevStop: mockPrevStop,
    skipTour: mockSkipTour,
    startTour: vi.fn(), isToured: vi.fn(() => false), restartTour: vi.fn(),
    wizardOpen: false, openWizard: vi.fn(), closeWizard: vi.fn(),
  })),
}))

import { useTourContext } from '../context/TourContext'

describe('TourOverlay', () => {
  beforeEach(() => {
    mockSkipTour.mockReset()
    mockNextStop.mockReset()
    mockPrevStop.mockReset()
    vi.spyOn(document, 'querySelector').mockReturnValue(null)
  })

  it('renders stop 1 heading', () => {
    render(<TourOverlay />)
    expect(screen.getByText('Your live dashboard')).toBeInTheDocument()
  })

  it('shows step counter "1 of 6"', () => {
    render(<TourOverlay />)
    expect(screen.getByText('1 of 6')).toBeInTheDocument()
  })

  it('calls nextStop on Next click', () => {
    render(<TourOverlay />)
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(mockNextStop).toHaveBeenCalled()
  })

  it('calls skipTour on Skip click', () => {
    render(<TourOverlay />)
    fireEvent.click(screen.getByText('Skip'))
    expect(mockSkipTour).toHaveBeenCalled()
  })

  it('shows Done at last stop (index 5)', () => {
    vi.mocked(useTourContext).mockReturnValue({
      tourState: { active: true, currentStop: 5, solutionName: 'my_app' },
      nextStop: mockNextStop, prevStop: mockPrevStop, skipTour: mockSkipTour,
      startTour: vi.fn(), isToured: vi.fn(() => false), restartTour: vi.fn(),
      wizardOpen: false, openWizard: vi.fn(), closeWizard: vi.fn(),
    })
    render(<TourOverlay />)
    expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument()
  })

  it('returns null when tour inactive', () => {
    vi.mocked(useTourContext).mockReturnValue({
      tourState: { active: false, currentStop: 0, solutionName: '' },
      nextStop: vi.fn(), prevStop: vi.fn(), skipTour: vi.fn(),
      startTour: vi.fn(), isToured: vi.fn(() => false), restartTour: vi.fn(),
      wizardOpen: false, openWizard: vi.fn(), closeWizard: vi.fn(),
    })
    const { container } = render(<TourOverlay />)
    expect(container.firstChild).toBeNull()
  })
})
```

- [x] **Step 2: Run test — expect failure**

```bash
cd web && npm test src/test/TourOverlay.test.tsx
```

Expected: FAIL — module not found.

- [x] **Step 3: Implement TourOverlay.tsx**

Create `web/src/components/onboarding/TourOverlay.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useTourContext } from '../../context/TourContext'

interface Stop { selector: string; heading: string; body: string }

const STOPS: Stop[] = [
  { selector: '[data-tour="stats-strip"]',      heading: 'Your live dashboard',  body: 'These counters update every 10 seconds. Red means proposals are waiting for your approval — that is the most important number in this sidebar.' },
  { selector: '[data-tour="nav-approvals"]',     heading: 'The approval gate',    body: 'Every action your agents propose lands here first. Nothing executes until you approve it. This is the human-in-the-loop guarantee.' },
  { selector: '[data-tour="nav-queue"]',         heading: 'Active work',          body: 'Tasks you have approved move here. You can see what is running, queued, or completed at any time.' },
  { selector: '[data-tour="area-intelligence"]', heading: 'Your agents',          body: 'Expand this to run agent tasks, review improvement plans, or track goals. Analyst and Developer live here — not at the top level.' },
  { selector: '[data-tour="area-knowledge"]',    heading: 'Institutional memory', body: 'The vector knowledge base for this solution. Everything your agents learn, and everything you import, is stored and retrieved here at query time.' },
  { selector: '[data-tour="solution-rail"]',     heading: 'Your solutions',       body: 'Each solution gets an avatar here. Switch between them instantly. Use the org graph to see how they connect.' },
]

interface Rect { top: number; left: number; width: number; height: number }

export default function TourOverlay() {
  const { tourState, nextStop, prevStop, skipTour } = useTourContext()
  const [targetRect, setTargetRect] = useState<Rect | null>(null)

  const totalStops = STOPS.length
  const stop = STOPS[tourState.currentStop]

  useEffect(() => {
    if (!tourState.active || !stop) return
    const el = document.querySelector(stop.selector)
    if (el) {
      const r = el.getBoundingClientRect()
      setTargetRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    } else {
      setTargetRect(null)
    }
  }, [tourState.active, tourState.currentStop])

  if (!tourState.active || !stop) return null

  const isLast = tourState.currentStop === totalStops - 1

  const cardStyle: React.CSSProperties = targetRect
    ? { position: 'fixed', top: Math.max(8, targetRect.top), left: targetRect.left + targetRect.width + 16, zIndex: 101 }
    : { position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 101 }

  return (
    <>
      {targetRect ? (
        <>
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, height: targetRect.top, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
          <div style={{ position: 'fixed', top: targetRect.top + targetRect.height, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
          <div style={{ position: 'fixed', top: targetRect.top, left: 0, width: targetRect.left, height: targetRect.height, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
          <div style={{ position: 'fixed', top: targetRect.top, left: targetRect.left + targetRect.width, right: 0, height: targetRect.height, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
        </>
      ) : (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 100 }} />
      )}
      <div style={{ ...cardStyle, background: '#0f172a', border: '1px solid #334155', borderRadius: '10px',
                    padding: '16px', maxWidth: '280px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
        <div style={{ fontSize: '11px', color: '#475569', marginBottom: '6px' }}>
          {tourState.currentStop + 1} of {totalStops}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', marginBottom: '8px' }}>
          {stop.heading}
        </div>
        <div style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '16px' }}>
          {stop.body}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {tourState.currentStop > 0 && (
            <button onClick={prevStop}
              style={{ padding: '6px 12px', background: '#1e293b', color: '#94a3b8', borderRadius: '6px', fontSize: '12px', border: 'none', cursor: 'pointer' }}>
              Prev
            </button>
          )}
          <button onClick={isLast ? skipTour : nextStop}
            style={{ padding: '6px 12px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '12px', border: 'none', cursor: 'pointer' }}>
            {isLast ? 'Done' : 'Next'}
          </button>
          <button onClick={skipTour}
            style={{ fontSize: '12px', color: '#475569', background: 'none', border: 'none', marginLeft: 'auto', cursor: 'pointer' }}>
            Skip
          </button>
        </div>
      </div>
    </>
  )
}
```

- [x] **Step 4: Run test — expect pass**

```bash
cd web && npm test src/test/TourOverlay.test.tsx
```

Expected: 6 tests pass.

- [x] **Step 5: Commit**

```bash
git add web/src/components/onboarding/TourOverlay.tsx web/src/test/TourOverlay.test.tsx
git commit -m "feat(web): TourOverlay 6-stop spotlight tour"
```

---

### Task 9: Wire everything into App.tsx + replace Onboarding.tsx

**Files:**
- Modify: `web/src/App.tsx`
- Replace: `web/src/pages/Onboarding.tsx`
- Create: `web/src/context/TourContext.tsx` *(not in spec's file list, but required to avoid prop drilling — defined as a thin wrapper over useTour, kept under 40 lines)*

**Note on TourContext:** The spec's Files table lists 9 files. `TourContext.tsx` is a 10th. It is required to share `useTour` state between `App.tsx` (which mounts `TourOverlay`) and `Sidebar.tsx` (which calls `startTour` and `openWizard`). Without it, `useTour` would be instantiated twice with disconnected state. The alternative — passing callbacks as props through `AppShell` → `Sidebar` — requires changes to Sidebar's props contract not described in the spec. TourContext is the minimal correct solution.

- [x] **Step 1: Create TourContext.tsx**

Create `web/src/context/TourContext.tsx`:

```tsx
import { createContext, useContext, useState, type ReactNode } from 'react'
import { useTour, type TourState } from '../components/onboarding/useTour'

interface TourContextValue {
  tourState: TourState
  startTour: (solutionId: string) => void
  nextStop: () => void
  prevStop: () => void
  skipTour: () => void
  isToured: (solutionId: string) => boolean
  restartTour: (solutionId: string) => void
  wizardOpen: boolean
  openWizard: () => void
  closeWizard: () => void
}

const TourContext = createContext<TourContextValue | null>(null)

export function TourProvider({ children }: { children: ReactNode }) {
  const tour = useTour()
  const [wizardOpen, setWizardOpen] = useState(false)
  return (
    <TourContext.Provider value={{
      ...tour,
      wizardOpen,
      openWizard: () => setWizardOpen(true),
      closeWizard: () => setWizardOpen(false),
    }}>
      {children}
    </TourContext.Provider>
  )
}

export function useTourContext() {
  const ctx = useContext(TourContext)
  if (!ctx) throw new Error('useTourContext must be used within TourProvider')
  return ctx
}
```

- [x] **Step 2: Write the failing test**

Create `web/src/test/AppWiring.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

vi.mock('../components/layout/Sidebar', () => ({ default: () => <div>Sidebar</div> }))
vi.mock('../components/layout/Header', () => ({ default: () => <div>Header</div> }))
vi.mock('../components/onboarding/TourOverlay', () => ({ default: () => <div data-testid="tour-overlay" /> }))
vi.mock('../pages/Dashboard', () => ({ default: () => <div>Dashboard</div> }))
vi.mock('../components/CommandPalette', () => ({ default: () => null }))
vi.mock('../components/theme/ThemeProvider', () => ({ default: ({ children }: any) => <>{children}</> }))
vi.mock('../context/AuthContext', () => ({ AuthProvider: ({ children }: any) => <>{children}</> }))
vi.mock('../api/client', () => ({
  fetchHealth: vi.fn().mockResolvedValue({}),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [], active: '' }),
}))
vi.mock('../hooks/useProjectConfig', () => ({ useProjectConfig: () => ({ data: null }) }))

describe('App wiring', () => {
  it('renders TourOverlay at root', () => {
    render(<App />)
    expect(screen.getByTestId('tour-overlay')).toBeInTheDocument()
  })

  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByText('Sidebar')).toBeInTheDocument()
  })
})
```

- [x] **Step 3: Run test — expect failure**

```bash
cd web && npm test src/test/AppWiring.test.tsx
```

Expected: FAIL — TourOverlay not mounted yet.

- [x] **Step 4: Replace Onboarding.tsx**

Replace entire `web/src/pages/Onboarding.tsx` with:

```tsx
import OnboardingWizard from '../components/onboarding/OnboardingWizard'
import { useTourContext } from '../context/TourContext'
import { useNavigate } from 'react-router-dom'

export default function Onboarding() {
  const { startTour, closeWizard } = useTourContext()
  const navigate = useNavigate()
  // When accessed via /onboarding route, render the wizard as a full-screen overlay.
  // The wizard uses position:fixed so it covers the full viewport regardless of what
  // is rendered behind it. onClose navigates to dashboard.
  return (
    <OnboardingWizard
      onClose={() => navigate('/')}
      onTourStart={(solutionId) => { startTour(solutionId); navigate('/') }}
    />
  )
}
```

- [x] **Step 5: Modify App.tsx**

Changes to `web/src/App.tsx`:

1. Add imports:
```tsx
import TourOverlay from './components/onboarding/TourOverlay'
import { TourProvider } from './context/TourContext'
```

2. Remove OrgChart import and its route:
```tsx
// Remove: import OrgChart from './pages/OrgChart'
// Remove: <Route path="/org" element={<OrgChart />} />
```

3. In `AppShell`, add `<TourOverlay />` alongside `CommandPalette`:
```tsx
return (
  <>
    <div className="flex h-screen overflow-hidden bg-zinc-50">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header onOpenPalette={() => setPaletteOpen(true)} />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            {/* ... all routes unchanged ... */}
          </Routes>
        </main>
      </div>
    </div>
    <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    <TourOverlay />
  </>
)
```

4. Wrap with `TourProvider` in `App()`:
```tsx
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ThemeProvider>
          <TourProvider>
            <AppShell />
          </TourProvider>
        </ThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [x] **Step 6: Run test — expect pass**

```bash
cd web && npm test src/test/AppWiring.test.tsx
```

Expected: 2 tests pass.

- [x] **Step 7: Run all frontend tests**

```bash
cd web && npm test
```

Expected: All tests pass.

- [x] **Step 8: TypeScript check**

```bash
cd web && npx tsc --noEmit
```

Expected: 0 errors.

- [x] **Step 9: Commit**

```bash
git add web/src/context/TourContext.tsx web/src/pages/Onboarding.tsx web/src/App.tsx web/src/test/AppWiring.test.tsx
git commit -m "feat(web): wire TourProvider + TourOverlay at root, replace Onboarding chat flow"
```

---

### Task 10: Browser smoke test

**Files:** None (verification only)

- [x] **Step 1: Start backend and frontend**

```bash
# Terminal 1:
make run PROJECT=iot_medical

# Terminal 2:
make ui
```

Open http://localhost:5173.

- [x] **Step 2: Verify 3-column layout**

- Solution Rail (44px dark `#020617` column) on far left
- Sidebar (220px) shows solution name + ChevronsUpDown icon at top
- Stats strip shows APPROVALS / QUEUED / AGENTS tiles
- Work area is open: Approvals, Task Queue, Dashboard, Live Console visible

- [x] **Step 3: Test area accordion**

Click Intelligence → Agents, Analyst, Developer, Monitor, Improvements, Workflows, Goals. Work items gone.
Click Knowledge → Vector Store, Channels, Audit Log, Costs. Intelligence collapsed.
Click Organization → Org Graph, Onboarding.
Click Admin → LLM Settings, Config Editor, Access Control, Integrations, Settings.
Click Work again → Work re-opens.

- [x] **Step 4: Test tooltips**

Hover each nav item → tooltip after ~200ms to the right.
Hover stats tiles → tooltip below.
Hover solution avatars → full solution name.
Hover "+" → "Create a new solution".
Hover Building2 icon → "View organization graph".

- [x] **Step 5: Test breadcrumb**

Navigate to /analyst → header line 1: `iot_medical / Intelligence`, line 2: `Log Analyst`.
Navigate to /settings → `iot_medical / Admin` / `Settings`.
Navigate to / → `iot_medical / Work` / `Dashboard`.

- [x] **Step 6: Test onboarding wizard via "+" button**

Click "+" in rail → wizard modal appears, 5 circles in progress bar.
Fill description → solution_name auto-populates.
Next → step 2 compliance/integrations. Skip link present.
Skip → step 3 spinner + 3 status lines.
On completion → step 4 YAML tabs. Switch between project.yaml, prompts.yaml, tasks.yaml.
"Open in Config Editor" button navigates to /yaml-editor with file param and closes wizard.
"Looks good" → step 5. "Start tour" and "Go to dashboard" buttons present.

- [x] **Step 7: Test tour flow**

Click "Start tour" → TourOverlay appears. "1 of 6" counter. Heading "Your live dashboard".
Next → stop 2. Next... → stop 6 ("Your solutions"). "Done" button.
Click Done → tour dismissed, solution marked as toured in localStorage.

- [x] **Step 8: Test Restart tour**

Click solution name in sidebar → dropdown opens. "Restart tour" visible at bottom.
Click → tour starts again from stop 1.

- [x] **Step 9: Test /onboarding route directly**

Navigate to /onboarding → wizard overlay appears full-screen.

- [x] **Step 10: Confirm /org is gone**

Navigate to /org → no route (blank or 404). /org-graph still works.

- [x] **Step 11: Run backend tests**

```bash
make test
```

Expected: all Python tests pass.

- [x] **Step 12: Final commit**

```bash
git add -A
git commit -m "feat(web): UI/UX redesign complete — 5-area nav, tooltips, wizard, tour"
```

---

## Implementation notes

1. **client.ts not modified** — `OnboardingWizard` calls `POST /onboarding/generate` via inline `fetch()`. All stats fetch via existing `fetchPendingProposals` / `fetchQueueTasks`.
2. **No emojis** — lucide-react icons and text labels only.
3. **No new Tailwind classes** — all new component styling is inline CSS.
4. **Module visibility preserved** — `active_modules` controls which nav items appear.
5. **OrgChart removed** — `/org` route and `OrgChart` import deleted from App.tsx. `/org-graph` is canonical.
6. **isToured uses solution id** — always pass `activeId` (from `fetchHealth`) not display name to `isToured`/`restartTour`.
7. **Accordion not persisted** — Work opens by default; active route auto-expands its area.
8. **TourContext.tsx** is a 10th file beyond the spec's 9-file list. It is the minimal solution for sharing `useTour` state between `App.tsx` and `Sidebar.tsx` without prop drilling through the AppShell.
