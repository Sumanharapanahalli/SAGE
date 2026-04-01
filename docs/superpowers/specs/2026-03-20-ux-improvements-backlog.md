# UX Improvements Backlog — 2026-03-20

Pending features to implement. All are UI-only or light backend changes.
Priority order listed within each section.

---

## 1. User Guide + Help → UserMenu (top-right avatar dropdown)

**Current:** Guide link is buried in the Sidebar under Solutions.
**Requested:** Move it to the UserMenu dropdown (the avatar button, top-right).
**Also add:** A "Help" option that opens the Contextual Chat Panel pre-seeded with
"I want to understand the SAGE framework — where do I start?"

### UserMenu additions (between Keyboard Shortcuts and About sections):

```
├─────────────────────────────────────────────┤
│  ◻  User Guide                              │  → navigates to /guide
│  ?  Help & Ask SAGE                         │  → opens ChatPanel with framework help prompt
├─────────────────────────────────────────────┤
```

### Files to modify:
- `web/src/components/layout/UserMenu.tsx` — add two new action rows
- `web/src/components/layout/Sidebar.tsx` — remove Guide link from sidebar nav
- `web/src/App.tsx` — keep `/guide` route, just remove sidebar entry

---

## 2. Solution Rail — Show Only Active Solution by Default

**Current:** All ~18 solutions appear as 2-letter avatar buttons in the left rail.
**Problem:** Cluttered, confusing for users who only work on one solution.
**Requested:** Only the ACTIVE solution is shown by default. Other solutions are hidden
behind a "Browse solutions" button (the "+" icon area or a new "..." button).

### Behaviour:
- On load: rail shows only the active solution avatar (highlighted/active state)
- "+" button (existing) opens OnboardingWizard as before
- New "..." or grid icon opens a **Solution Picker** modal showing all available solutions
- User can **pin** up to 5 additional solutions to the rail (persisted in localStorage key `sage_pinned_solutions`)
- Pinned solutions appear as avatars below the active one

### Solution Picker modal:
```
┌─────────────────────────────────────────┐
│  All Solutions                    [x]   │
│  ──────────────────────────────────     │
│  ● iot_medical          IoT Medical     │
│  ○ medtech_sample     Acme Med.   │
│  ○ medtech_team         MedTech Team    │
│  ... (scrollable list)                  │
│                                         │
│  [Pin to rail]  [Switch to selected]    │
└─────────────────────────────────────────┘
```

### Files to modify:
- `web/src/components/layout/SolutionRail.tsx` (or equivalent in Sidebar.tsx)
- New: `web/src/components/ui/SolutionPicker.tsx`
- `web/src/App.tsx` — pass pinned solutions state

---

## 3. Contextual Chat Window (see full spec)

See: `docs/superpowers/specs/2026-03-20-contextual-chat-window.md`

**Summary:** Persistent collapsible chat panel (bottom-centre, 520×380px) for
users to ask the LLM about current proposals, analyses, or the framework.
Context is per-user, persisted in SQLite. Streams responses token-by-token.

---

## 4. Solution Rail Color Themes (minor)

**Current:** All solution avatars use the same color scheme.
**Requested:** Each solution avatar uses its `theme.badge_text` color as the avatar background,
so Acme MedTech shows in its navy blue, iot_medical in its own color, etc.

### Files to modify:
- `web/src/components/layout/Sidebar.tsx` — read project theme when building rail avatars
- Requires fetching all project configs briefly; can be lazy-loaded

---

## 5. Color Combo Improvements (already partially done)

**Done:** Split-circle swatches replaced with top/bottom rectangles showing sidebarBg + accent.
**Still to do:**
- Ensure the CSS vars applied by UserPrefsContext actually affect sidebar background
  (currently only `--sage-sidebar-bg` is set; need to verify Sidebar reads it)
- Add a "Preview" mode: hovering a combo shows a live preview before clicking

---

## Implementation Order Recommendation

1. **Solution Rail simplification** (2) — most visible UX impact, pure frontend
2. **UserMenu Guide + Help** (1) — quick 30-min change
3. **Contextual Chat Window** (3) — largest feature, needs backend + frontend
4. **Solution Rail colors** (4) — nice to have, low effort
5. **Color combo preview** (5) — polish

---

## Notes

- The chat window (3) depends on the ChatPanel being available before Help (1) can open it
- Solution rail changes (2) should NOT break the existing solution-switch flow
- All changes should maintain 100% Python test pass rate and frontend vitest pass
