# Header User Menu + Auth — Design Spec

**Date:** 2026-03-19
**Sub-project:** 1 of 6
**Branch:** feature/intelligence-layer-proposals

---

## Goal

Replace the bare "Stop SAGE" button in the header with a user avatar dropdown that provides identity management, per-user display customisation, keyboard shortcuts, and framework info — all in one discoverable panel.

---

## Scope

### In scope
- User avatar button in header (right side)
- Fixed-position dropdown panel with 7 sections (see layout below)
- Dev-mode identity switching: config file roster + UI picker, no restart needed
- Per-user display preferences stored in `localStorage`, swappable to backend later
- Display settings: theme (dark/light/system), color accent swatches, font family, font size, density, timezone
- Keyboard shortcuts modal
- About block (SAGE version, LLM provider, active solution)
- Stop SAGE moved from header into dropdown (with inline confirm)
- Per-solution roles declared in `project.yaml`
- New `GET /config/dev-users` backend endpoint to serve the dev user roster
- New `config/dev_users.yaml` file for dev-mode user definitions

### Out of scope
- Real Google OAuth (future sub-project — this spec uses dev-mode only)
- Backend-persisted user preferences (localStorage adapter is designed to be swappable)
- Per-user notification preferences (future)
- Personal API token management (future)

---

## Architecture

### New files
| File | Purpose |
|------|---------|
| `web/src/context/UserContext.tsx` | Active user state, display prefs, localStorage adapter |
| `web/src/components/layout/UserMenu.tsx` | Avatar button + dropdown panel |
| `web/src/components/ui/KeyboardShortcutsModal.tsx` | Keyboard shortcuts reference modal |
| `config/dev_users.yaml` | Dev-mode user roster |

### Modified files
| File | Change |
|------|--------|
| `web/src/components/layout/Header.tsx` | Remove Stop button, add `<UserMenu />` |
| `web/src/App.tsx` | Wrap app in `<UserProvider>` |
| `src/interface/api.py` | Add `GET /config/dev-users` endpoint |
| `solutions/starter/project.yaml` | Add `roles:` block as template |

---

## Data Models

### Dev user (config/dev_users.yaml)
```yaml
users:
  - id: suman
    name: Suman H.
    email: suman@example.com
    role: admin
    avatar_color: '#6366f1'
  - id: dr_chen
    name: Dr. Chen
    email: chen@example.com
    role: approver
    avatar_color: '#10b981'
  - id: viewer_1
    name: Guest Viewer
    email: viewer@example.com
    role: viewer
    avatar_color: '#64748b'
```

### Per-solution roles (project.yaml)
```yaml
roles:
  admin:
    - suman
  approver:
    - suman
    - dr_chen
  viewer:
    - "*"
```

### User display prefs (localStorage key: `sage_user_prefs_<userId>`)
```typescript
interface UserPrefs {
  theme: 'dark' | 'light' | 'system'
  colorCombo: 'zinc' | 'violet' | 'blue' | 'emerald' | 'rose'
  fontFamily: 'inter' | 'jetbrains-mono' | 'system-ui' | 'geist' | 'roboto'
  fontSize: 'sm' | 'md' | 'lg'
  density: 'compact' | 'comfortable'
  timezone: string   // IANA timezone string e.g. 'UTC', 'America/New_York'
}
```

### UserContext shape
```typescript
interface UserContextValue {
  user: DevUser | null
  prefs: UserPrefs
  allUsers: DevUser[]
  switchUser: (id: string) => void
  updatePref: <K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => void
}
```

---

## Dropdown Panel Layout

Panel: `position: fixed`, ~300px wide, anchored top-right below header, `z-index: 9999`.

```
┌─────────────────────────────────┐
│  ◉ Suman H.              Admin  │  avatar (initials) + name + role badge
│    suman@example.com            │
│    iot_medical · Last login 2m  │  active solution + session timestamp
├─────────────────────────────────┤
│  Switch Identity ▾              │  dev-mode picker — lists all dev_users
│  [ Dr. Chen — Approver      ]   │
├─────────────────────────────────┤
│  Display                        │
│  Theme    [ Dark  ▾ ]           │
│  Colors   ● ● ● ● ●             │  5 color accent swatches (live preview)
│  Font     [ Inter ▾ ]           │  font family
│  Size     [ Medium ▾ ]          │  font size
│  Density  [ Comfortable ▾ ]     │
│  Timezone [ UTC ▾ ]             │
├─────────────────────────────────┤
│  ⌨  Keyboard shortcuts          │  opens KeyboardShortcutsModal
├─────────────────────────────────┤
│  ℹ  SAGE v2.1 · gemini · claude │  read-only about block
├─────────────────────────────────┤
│  ⬡  Access Control              │  nav link to /access-control
│  ■  Stop SAGE                   │  inline confirm: "Stop SAGE? Yes / Cancel"
├─────────────────────────────────┤
│  → Logout                       │  clears active user, returns to guest state
└─────────────────────────────────┘
```

---

## Display Settings Behaviour

- Every change applies **immediately** (no Save button)
- Writes to `localStorage['sage_user_prefs_<userId>']` on each `updatePref` call
- On mount, `UserContext` loads prefs for the active user from localStorage
- Switching identity automatically loads that user's stored prefs
- `UserPrefsAdapter` interface: `load(userId)` / `save(userId, prefs)` — localStorage today, API tomorrow

### Font families available
| Value | Display name | CSS |
|-------|-------------|-----|
| `inter` | Inter (default) | `'Inter', sans-serif` |
| `jetbrains-mono` | JetBrains Mono | `'JetBrains Mono', monospace` |
| `system-ui` | System UI | `system-ui, sans-serif` |
| `geist` | Geist | `'Geist', sans-serif` |
| `roboto` | Roboto | `'Roboto', sans-serif` |

### Color accent combos
| Value | Name | Accent hex |
|-------|------|-----------|
| `zinc` | Zinc (default) | `#71717a` |
| `violet` | Violet | `#7c3aed` |
| `blue` | Blue | `#2563eb` |
| `emerald` | Emerald | `#059669` |
| `rose` | Rose | `#e11d48` |

Color accent applies to: active nav item indicator, badge highlights, primary buttons.

---

## Backend: GET /config/dev-users

```
GET /config/dev-users
Response: { "users": [ { "id", "name", "email", "role", "avatar_color" } ] }
```

Reads `config/dev_users.yaml`. Returns empty list if file doesn't exist (graceful degradation). No auth required — this is a dev-mode endpoint.

---

## Stop SAGE Migration

The existing `<button onClick={() => setConfirmStop(true)}>Stop</button>` in `Header.tsx` is removed. The Stop SAGE action moves into the UserMenu dropdown. The confirm state (`confirmStop`, `setConfirmStop`) moves into `UserMenu.tsx`. Behaviour is identical — two-step confirm before calling `POST /api/shutdown`.

---

## Keyboard Shortcuts Modal

Inline modal (not a page). Lists shortcut groups:

| Group | Shortcut | Action |
|-------|---------|--------|
| Navigation | `Ctrl+K` | Open command palette |
| Navigation | `G then A` | Go to Approvals |
| Navigation | `G then Q` | Go to Queue |
| Navigation | `G then D` | Go to Dashboard |
| Approvals | `A` | Approve focused proposal |
| Approvals | `R` | Reject focused proposal |

---

## Testing

- `UserContext` unit tests: load prefs from localStorage, switch identity loads correct prefs, `updatePref` persists
- `UserMenu` render tests: opens on click, closes on outside click, displays correct user name/role
- `GET /config/dev-users` endpoint test: returns users from YAML, returns `[]` when file missing
- Manual: switching identity → display prefs update live → refresh → prefs restored

---

## Non-goals / Future

- Real Google OAuth login (sub-project TBD after this one)
- Backend-synced prefs (`UserPrefsAdapter` makes this a one-file change)
- Per-user notification preferences
- Personal API token generation
