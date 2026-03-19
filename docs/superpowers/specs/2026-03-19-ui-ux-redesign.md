# SAGE UI/UX Redesign — Design Spec
**Date:** 2026-03-19
**Status:** Approved for planning
**Scope:** SAGE Framework (`scope: sage`)

---

## Problem

The current sidebar is a flat alphabetical list of 23 pages with no hierarchy. Agent-specific tools (Analyst, Developer, Monitor) appear as top-level peers of framework controls (Settings, LLM, Access Control). There is no solution context visible while navigating. New users have no guidance. The navigation does not reflect the scope or depth of the framework.

---

## Goal

1. **Restructured navigation** — 5-area hierarchy matching how users actually work, with agent tools nested under Intelligence
2. **Hover tooltips** — every nav item explains itself on hover, reducing the need for documentation
3. **Interactive onboarding tour** — when a new solution is created, a guided walkthrough covers the creation wizard and a post-creation UI tour (skippable at any point)

---

## Architecture

### Layout shell

Three columns, left to right:

1. **Solution Rail** (44px) — solution avatars, org icon, add-solution button
2. **Sidebar** (220px) — solution switcher + live stats strip + 5-area collapsible nav + user footer
3. **Content area** (flex) — breadcrumb header + page content

### Navigation areas (5 top-level, expandable)

| Area | Pages inside | Accent colour |
|---|---|---|
| **Work** | Approvals · Task Queue · Dashboard · Live Console | `#ef4444` (red) |
| **Intelligence** | Agents · Analyst · Developer · Monitor · Improvements · Workflows · Goals | `#a78bfa` (violet) |
| **Knowledge** | Vector Store · Channels · Audit Log · Costs | `#10b981` (green) |
| **Organization** | Org Graph · Onboarding | `#3b82f6` (blue) |
| **Admin** | LLM Settings · Config Editor · Access Control · Integrations · Settings | `#475569` (slate) |

**"Agents" is the existing `/agents` page**, renamed from "AI Agents" to "Agents" and moved under Intelligence. No new page is created.

**"Vector Store"** maps to the existing `/knowledge` route (knowledge base CRUD page). If no `/knowledge` page exists, it maps to `/settings` with the knowledge tab active — implementer should check which route currently serves knowledge base browsing and use that.

**"Goals"** maps to the existing `/goals` route (`web/src/pages/Goals.tsx`). No new page is created.

**Organization area** contains only Org Graph (`/org-graph`) and Onboarding (`/onboarding`). The old OrgChart page (`/org`) is replaced by OrgGraph. No "Solutions" sub-page — that was removed from scope.

One area is open at a time. The accordion open/closed state is **not persisted** — on every page load, Work is open by default. Active page is highlighted within whichever area contains it, and that area is automatically expanded.

---

## Feature 1: Restructured Navigation

### Solution Rail

- Far-left 44px column, `background: #020617`
- Each solution shown as a 28×28px avatar with 2-letter initials (e.g. `BG` for board_games), `background: #3b82f6` for active solution, `background: #1e293b` for others
- Clicking an avatar switches the active solution (calls `POST /config/switch`)
- "+" button at bottom of avatars — opens the OnboardingWizard modal (see Feature 3)
- Org icon (building SVG, lucide `Building2`) fixed at rail bottom — navigates to `/org-graph`
- **Tooltip on each solution avatar:** solution full name only (not agent count — agent count is only available for the active solution)
- **Tooltip on "+":** "Create a new solution"
- **Tooltip on org icon:** "View organization graph"

### Sidebar — Solution switcher

- Sits at top of sidebar, above stats strip
- Shows active solution name + chevrons icon (lucide `ChevronsUpDown`) for switching
- Clicking opens a dropdown listing all loaded solutions (same list as current `CompanyRail`)
- Dropdown also contains a "Restart tour" item at the bottom, separated by a divider line, only visible when `localStorage` contains the current solution in `sage_toured_solutions`
- "Restart tour" clears the solution from `sage_toured_solutions` and re-triggers the TourOverlay
- Solution name truncated with ellipsis if longer than available width

### Sidebar — Stats strip

Three equal tiles below the solution switcher, polling every 10 seconds:

| Tile | API call | Colour |
|---|---|---|
| APPROVALS | reuse existing `fetchPendingProposals()` from `client.ts`, return `.length` | `#ef4444` |
| QUEUED | reuse existing `fetchQueueTasks()` from `client.ts`, count `pending + in_progress` | `#f59e0b` |
| AGENTS | reuse existing `fetchQueueTasks()`, count only `in_progress` | `#10b981` |

Do **not** add new fetch functions. Reuse existing exports from `client.ts`. Clicking a tile navigates to the relevant page (Approvals, Queue, Queue respectively).

### Sidebar — Navigation areas

- Each area row: lucide icon + label + collapsed item count + chevron (`ChevronDown` / `ChevronRight`)
- Click to expand/collapse; only one area open at a time
- When expanded, child pages are indented with a left border in the area's accent colour
- Active page: `background: #172033`, `color: #93c5fd`
- Inactive child: `color: #64748b`, hover `color: #94a3b8`
- Area header rows are not navigation links — click only expands/collapses

### Content header (Header.tsx modification)

`web/src/components/layout/Header.tsx` is modified to show a two-line header on every page:

- Line 1 (small, muted): `{solutionName} / {areaName}` — breadcrumb derived from the current route
- Line 2 (large, bold): page title (existing behaviour, preserved)
- Right side: existing controls preserved (theme, etc.)

A `ROUTE_TO_AREA` map is added in `Header.tsx` mapping each route path to its area name (Work, Intelligence, Knowledge, Organization, Admin).

---

## Feature 2: Hover Tooltips

### Implementation

A `Tooltip` component in `web/src/components/layout/Tooltip.tsx`:

```tsx
interface TooltipProps {
  text: string;
  children: React.ReactNode;
  side?: "right" | "bottom";  // default: "right"
}
```

- Wraps any child element
- 200ms delay on mouseenter before showing; hides immediately on mouseleave
- Positioned to the right of the wrapped element for sidebar items, below for rail icons
- Styles: `background: #1e293b`, `border: 1px solid #334155`, `border-radius: 6px`, `padding: 6px 10px`, `font-size: 11px`, `color: #94a3b8`, `max-width: 220px`, `pointer-events: none`, `z-index: 50`, `position: absolute`
- Implemented with `useState` + `useRef` + `setTimeout` — no external library

### Tooltip content

| Item | Tooltip text |
|---|---|
| Work area | View and act on agent proposals, queued tasks, and live activity |
| Approvals | Agent proposals waiting for your review before execution |
| Task Queue | Tasks currently queued or running across all agents |
| Dashboard | System health, recent activity, and integration status |
| Live Console | Real-time backend log stream |
| Intelligence area | Run agent tasks, review plans, and track improvement goals |
| Agents | Submit a task to an agent role defined in this solution's prompts.yaml |
| Analyst | AI triage of log entries and error signals |
| Developer | Code review and merge request creation via connected GitLab |
| Monitor | Live status of all configured integration polling threads |
| Improvements | Feature request queue and AI-generated implementation plans |
| Workflows | LangGraph workflow definitions and execution history |
| Goals | High-level objectives tracked against in-progress work |
| Knowledge area | Vector knowledge base, shared channels, and compliance records |
| Vector Store | Search and manage entries in this solution's knowledge base |
| Channels | Cross-team knowledge channels shared via org configuration |
| Audit Log | Full compliance audit trail — proposals, approvals, rejections |
| Costs | LLM token usage and budget controls per solution |
| Organization area | Visualize and configure the multi-solution org structure |
| Org Graph | React Flow graph of solutions, knowledge channels, and task routing |
| Onboarding | Generate a new solution from a plain-language description |
| Admin area | Framework-level configuration — not solution-specific |
| LLM Settings | Switch LLM provider and model; view session token usage |
| Config Editor | Edit solution YAML files with live validation |
| Access Control | Manage API keys and user role assignments |
| Integrations | Status and configuration for all connected integrations |
| Settings | Framework-wide settings and display preferences |
| Stats tile: APPROVALS | Proposals waiting for your sign-off |
| Stats tile: QUEUED | Tasks in queue or actively running |
| Stats tile: AGENTS | Agent tasks currently in progress |

---

## Feature 3: Interactive Onboarding Walkthrough

### Trigger conditions

The wizard modal opens when:
- User clicks "+" in the Solution Rail, **or**
- User navigates to `/onboarding` directly

The existing `/onboarding` page (`Onboarding.tsx`) is **replaced** by the new wizard. The existing chat-session-based flow (`startOnboardingSession`, `sendOnboardingMessage`) is removed. The new wizard calls `POST /onboarding/generate` directly (which already exists and returns all three YAML files).

The tour (Part B) starts automatically after a successful solution creation **if** the solution name is not already in `localStorage` key `sage_toured_solutions` (a JSON string array).

### OnboardingWizard — 5-step modal

Rendered as a full-screen modal overlay (`position: fixed`, `inset: 0`, `z-index: 100`, `background: rgba(0,0,0,0.75)`). Inner card is centred, `max-width: 560px`, `background: #0f172a`, `border-radius: 12px`, `border: 1px solid #1e293b`.

Progress bar at top: 5 numbered circles connected by lines. Active step circle is `background: #3b82f6`, completed steps are `background: #10b981` with a checkmark, future steps are `background: #1e293b`.

**Step 1 — Describe your solution**
- `description` textarea (3 rows, required) — label: "What does this solution do?"
- `solution_name` text input — label: "Solution name" — auto-populated from description (snake_case), user-editable
- `parent_solution` select dropdown — label: "Parent solution (optional)" — populated from `GET /solutions` or `GET /config`; first option is "None"
- `org_name` text input (read-only if org.yaml exists, editable otherwise) — label: "Organisation name (optional)"
- "Next" button (disabled until description and solution_name are non-empty)

**Step 2 — Compliance and integrations**
- Multi-select checkboxes: ISO 13485 · IEC 62304 · ISO 9001 · FDA 21 CFR Part 11 · None
- Multi-select checkboxes: GitLab · Slack · GitHub · None
- "Skip" link (right-aligned, proceeds to Step 3 with empty arrays)
- "Next" button

**Step 3 — Generating...**
- Calls `POST /onboarding/generate` with fields from Steps 1–2
- Animated spinner + three status lines that tick as generation progresses: "Generating project.yaml" → "Generating prompts.yaml" → "Generating tasks.yaml"
- On error: red error message with "Try again" button
- Auto-advances to Step 4 on success

**Step 4 — Review generated YAML**
- Three tabs: `project.yaml` · `prompts.yaml` · `tasks.yaml`
- Each tab shows a read-only code block (`font-family: monospace`, `font-size: 12px`, `background: #020617`, `border-radius: 6px`, `padding: 12px`, `overflow-y: auto`, `max-height: 280px`)
- "Open in Config Editor" button per tab — navigates to `/yaml-editor` with the file pre-selected (closes wizard first)
- "Looks good" primary button → Step 5

**Step 5 — Solution ready**
- Summary: solution name, parent (if set), suggested_routes list (if returned), number of task types
- "Start tour" primary button — dismisses wizard, calls `POST /config/switch` to activate new solution, then starts TourOverlay (Part B)
- "Go to dashboard" secondary link — dismisses wizard, activates solution, skips tour

### TourOverlay — 6-stop spotlight tour

Mounted at root level in `App.tsx` alongside the main router. Controlled by `useTour` hook.

**Spotlight implementation:**
- Full-screen fixed overlay, `background: transparent`
- Four black semi-transparent rectangles forming a frame around the highlighted element (computed from `getBoundingClientRect()` of the target element), `background: rgba(0,0,0,0.65)`
- Tooltip card positioned adjacent to the cutout: `background: #0f172a`, `border: 1px solid #334155`, `border-radius: 10px`, `padding: 16px`, `max-width: 280px`, `box-shadow: 0 8px 32px rgba(0,0,0,0.5)`
- Card contains: step counter (e.g. "2 of 6"), heading, body text, Prev / Next / Skip buttons
- "Skip" is a text link (`color: #475569`), Prev/Next are buttons

**Tour stops:**

| Stop | Target selector | Heading | Body |
|---|---|---|---|
| 1 | Stats strip container | "Your live dashboard" | "These counters update every 10 seconds. Red means proposals are waiting for your approval — that is the most important number in this sidebar." |
| 2 | Approvals nav item | "The approval gate" | "Every action your agents propose lands here first. Nothing executes until you approve it. This is the human-in-the-loop guarantee." |
| 3 | Task Queue nav item | "Active work" | "Tasks you have approved move here. You can see what is running, queued, or completed at any time." |
| 4 | Intelligence area header | "Your agents" | "Expand this to run agent tasks, review improvement plans, or track goals. Analyst and Developer live here — not at the top level." |
| 5 | Knowledge area header | "Institutional memory" | "The vector knowledge base for this solution. Everything your agents learn, and everything you import, is stored and retrieved here at query time." |
| 6 | Solution Rail | "Your solutions" | "Each solution gets an avatar here. Switch between them instantly. Use the org graph to see how they connect." |

At stop 6, "Next" becomes "Done". Clicking Done marks the solution as toured (`sage_toured_solutions` in localStorage) and dismisses the overlay.

If any target element is not found in the DOM at tour time (e.g. the area is collapsed), the tour skips that stop silently.

**useTour hook** (`web/src/components/onboarding/useTour.ts`):
```ts
interface TourState {
  active: boolean;
  currentStop: number;        // 0-indexed
  solutionName: string;
}
function useTour(): {
  tourState: TourState;
  startTour: (solutionName: string) => void;
  nextStop: () => void;
  prevStop: () => void;
  skipTour: () => void;
  isToured: (solutionName: string) => boolean;
}
```

### Skip behaviour

- "Skip" dismisses TourOverlay and marks solution as toured in localStorage
- Skipped solutions do not re-trigger the auto-tour
- "Restart tour" in solution switcher dropdown clears the entry and re-triggers

---

## Files

| File | Action | Responsibility |
|---|---|---|
| `web/src/components/layout/Sidebar.tsx` | **Rewrite** | Full new layout: rail + switcher + stats strip + 5-area nav + user footer |
| `web/src/components/layout/Header.tsx` | **Modify** | Add two-line breadcrumb header with `ROUTE_TO_AREA` map |
| `web/src/components/layout/Tooltip.tsx` | **Create** | Lightweight hover tooltip (200ms delay, right/bottom positioning) |
| `web/src/components/layout/StatsStrip.tsx` | **Create** | Three live-polling stat tiles (reuse existing fetch functions) |
| `web/src/components/onboarding/OnboardingWizard.tsx` | **Create** | 5-step creation wizard modal |
| `web/src/components/onboarding/TourOverlay.tsx` | **Create** | 6-stop spotlight tour overlay |
| `web/src/components/onboarding/useTour.ts` | **Create** | Tour state hook + localStorage persistence |
| `web/src/pages/Onboarding.tsx` | **Replace** | Remove chat-session flow; render OnboardingWizard directly |
| `web/src/App.tsx` | **Modify** | Mount TourOverlay at root; remove defunct OrgChart route |

---

## What Does Not Change

- All other page components (`Analyst.tsx`, `Developer.tsx`, `Approvals.tsx`, etc.) are untouched
- All existing routes except `/org` (OrgChart, removed) remain valid
- Module visibility (`active_modules` in project.yaml) still controls which nav items appear
- `MODULE_REGISTRY` in `modules.ts` remains the source of truth — area grouping is defined in `Sidebar.tsx`, not the registry
- `client.ts` is not modified — existing fetch functions are reused

---

## Non-Goals (explicit out of scope)

- Role-based sidebar access control — deferred (no auth system yet)
- Mobile / responsive layout — desktop-only
- Drag-to-reorder nav items — deferred
- Persistent tour progress across page refresh — state resets; tour restarts from stop 1
- Animated sidebar collapse to icon-only mode — deferred
- Per-solution agent count on rail avatars (only active solution count is available) — deferred
