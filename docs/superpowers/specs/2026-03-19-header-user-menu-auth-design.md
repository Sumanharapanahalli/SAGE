# Header User Menu + Auth — Design Spec

**Date:** 2026-03-19
**Sub-project:** 1 of 6
**Branch:** feature/intelligence-layer-proposals

---

## Goal

Replace the bare "Stop SAGE" button in the header with a user avatar dropdown providing identity management, per-user display customisation (dual color combos, font family/size, density, timezone), keyboard shortcuts, and framework info.

---

## Scope

### In scope
- User avatar button replacing Stop SAGE in header right side
- Fixed-position dropdown panel (7 sections — see layout)
- Dev-mode identity switching via extended `AuthContext` — no new context, no restart
- Per-user display preferences in `localStorage`, adapter-swappable to backend
- **Dual color combos** — full sidebar+content theme pairs (not single accent colors)
- Font family (Inter, JetBrains Mono, System UI, Geist, Roboto) + font size
- Density + timezone
- Keyboard shortcuts modal
- About block (SAGE version, LLM provider from `/health`)
- Stop SAGE moved from header into dropdown (inline confirm)
- Per-solution `roles:` block in `project.yaml`
- `GET /config/dev-users` backend endpoint + `config/dev_users.yaml`
- Google Fonts loading for non-default fonts

### Out of scope
- Real Google OAuth (future)
- Backend-synced preferences
- Notification preferences
- Personal API token generation

---

## Architecture

### Relationship to existing AuthContext

`AuthContext` already calls `GET /auth/me` → `UserIdentity`. This spec **extends** it with three new fields — no new context, no breaking changes:

```typescript
// additions to AuthContextValue
isDevMode:     boolean       // true when devUsers.length > 0
devUsers:      DevUser[]     // from GET /config/dev-users
switchDevUser: (id: string) => void  // sets user state from roster, no API call
```

`switchDevUser` maps `DevUser → UserIdentity`: `sub=id`, `provider='dev'`, rest direct. All existing `useAuth().user` consumers work unchanged.

### UserPrefsContext — separate, subscribes to auth

New `UserPrefsContext` handles display prefs only. It calls `useAuth()` internally to know the active userId and loads that user's prefs from localStorage on every identity switch.

### ThemeProvider — no conflict

`ThemeProvider` writes `--sage-*` CSS vars from `project.yaml` (solution branding).
`UserPrefsContext` writes **separate** vars: `--sage-user-accent`, `--sage-font-family`, `--sage-font-size-base`, `--sage-density`.
Dark/light mode adds/removes `dark` class on `<html>`.
Priority: user preference → solution theme → `:root` default.

---

## Dual Color Combos

Each combo is a full paired theme (dark sidebar half + light content half):

| Value | Name | Sidebar bg | Sidebar text | Content bg | Accent |
|-------|------|-----------|-------------|-----------|--------|
| `zinc` | Zinc (default) | `#18181b` | `#a1a1aa` | `#fafafa` | `#71717a` |
| `night` | Night | `#0f172a` | `#94a3b8` | `#ffffff` | `#3b82f6` |
| `forest` | Forest | `#052e16` | `#86efac` | `#fefce8` | `#16a34a` |
| `ocean` | Ocean | `#042f2e` | `#99f6e4` | `#f0fdfa` | `#0d9488` |
| `slate` | Slate | `#1e293b` | `#94a3b8` | `#f8fafc` | `#6366f1` |
| `rose` | Rose | `#1c0a0a` | `#fca5a5` | `#fff1f2` | `#e11d48` |

Applying a combo writes all six `--sage-sidebar-bg`, `--sage-sidebar-text`, `--sage-content-bg`, `--sage-user-accent`, etc. CSS vars at once. The sidebar reflects the dark half immediately; page content backgrounds use the light half.

---

## Data Models

### config/dev_users.yaml
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

### DevUser (added to web/src/api/auth.ts)
```typescript
export interface DevUser {
  id:           string   // maps to UserIdentity.sub
  name:         string
  email:        string
  role:         string
  avatar_color: string
}
```

### Per-solution roles (project.yaml)
```yaml
roles:
  admin:    [suman]
  approver: [suman, dr_chen]
  viewer:   ["*"]
```

### UserPrefs
```typescript
export interface UserPrefs {
  theme:      'dark' | 'light' | 'system'
  colorCombo: 'zinc' | 'night' | 'forest' | 'ocean' | 'slate' | 'rose'
  fontFamily: 'inter' | 'jetbrains-mono' | 'system-ui' | 'geist' | 'roboto'
  fontSize:   'sm' | 'md' | 'lg'
  density:    'compact' | 'comfortable'
  timezone:   string
}

export const DEFAULT_PREFS: UserPrefs = {
  theme: 'dark', colorCombo: 'zinc', fontFamily: 'inter',
  fontSize: 'md', density: 'comfortable', timezone: 'UTC',
}
```

### UserPrefsAdapter interface
```typescript
export interface UserPrefsAdapter {
  load(userId: string): UserPrefs | null
  save(userId: string, prefs: UserPrefs): void
}
// localStorage implementation — swap this for a backend adapter later
export const localStorageAdapter: UserPrefsAdapter = {
  load: (userId) => {
    try {
      const raw = localStorage.getItem(`sage_user_prefs_${userId}`)
      return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : null
    } catch { return null }
  },
  save: (userId, prefs) => {
    localStorage.setItem(`sage_user_prefs_${userId}`, JSON.stringify(prefs))
  },
}
```

### UserPrefsContext shape
```typescript
interface UserPrefsContextValue {
  prefs:      UserPrefs
  updatePref: <K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => void
  resetPrefs: () => void
}
```

---

## New & Modified Files

| File | Action |
|------|--------|
| `config/dev_users.yaml` | Create |
| `web/src/context/UserPrefsContext.tsx` | Create |
| `web/src/components/layout/UserMenu.tsx` | Create |
| `web/src/components/ui/KeyboardShortcutsModal.tsx` | Create |
| `web/src/context/AuthContext.tsx` | Modify — add devUsers, switchDevUser, isDevMode |
| `web/src/api/auth.ts` | Modify — add DevUser type + getDevUsers() |
| `web/src/api/client.ts` | Modify — add fetchDevUsers() |
| `web/src/components/layout/Header.tsx` | Modify — remove Stop button, add UserMenu |
| `web/src/App.tsx` | Modify — wrap in UserPrefsProvider |
| `web/src/index.css` | Modify — add --sage-user-accent, --sage-content-bg, --sage-font-family, --sage-font-size-base, --sage-density CSS vars |
| `web/index.html` | Modify — add Google Fonts links |
| `src/interface/api.py` | Modify — add GET /config/dev-users |
| `solutions/starter/project.yaml` | Modify — add roles: template block |

---

## Dropdown Panel Layout

Panel: `position: fixed`, 300px wide, anchored below avatar button, `z-index: 9999`. Closes on outside click / `Escape`.

```
┌─────────────────────────────────┐
│  ◉ Suman H.              Admin  │  initials avatar (avatar_color bg) + role badge
│    suman@example.com            │
│    iot_medical                  │  from useProjectConfig().name
├─────────────────────────────────┤
│  Switch Identity ▾              │  only when isDevMode === true
│  [ Dr. Chen — Approver      ]   │
├─────────────────────────────────┤
│  Display                        │
│  Theme    [ Dark  ▾ ]           │
│  Colors   ●zinc ●night ●forest  │  dual combo swatches — show sidebar+content halves
│           ●ocean ●slate ●rose   │
│  Font     [ Inter ▾ ]           │
│  Size     [ Medium ▾ ]          │
│  Density  [ Comfortable ▾ ]     │
│  Timezone [ UTC ▾ ]             │
├─────────────────────────────────┤
│  ⌨  Keyboard shortcuts          │  opens KeyboardShortcutsModal
├─────────────────────────────────┤
│  ℹ  SAGE v2.1 · gemini · claude │  from /health response
├─────────────────────────────────┤
│  ⬡  Access Control              │  link → /access-control
│  ■  Stop SAGE                   │  "Stop SAGE? Yes / Cancel" inline confirm
├─────────────────────────────────┤
│  → Logout                       │  dev mode: switchDevUser(devUsers[0].id)
└─────────────────────────────────┘
```

Color combo swatches: each swatch is a split circle (left half = sidebar color, right half = content color) so the user can see both halves of the pair at a glance.

---

## Display Pref DOM Effects

| Pref | DOM effect |
|------|-----------|
| `theme: dark` | `document.documentElement.classList.add('dark')` |
| `theme: light` | `document.documentElement.classList.remove('dark')` |
| `theme: system` | Match `prefers-color-scheme` |
| `colorCombo` | Write all 6 combo CSS vars to `document.documentElement.style` |
| `fontFamily` | Set `--sage-font-family` CSS var |
| `fontSize` | Set `--sage-font-size-base` (`sm=13px`, `md=14px`, `lg=16px`) |
| `density` | Set `--sage-density` (`compact=0.75rem`, `comfortable=1rem`) |
| `timezone` | Stored only — used by date display utilities |

On identity switch: load new user's prefs → re-apply all DOM effects.

---

## Backend: GET /config/dev-users

```
GET /config/dev-users
→ { "users": [ { "id", "name", "email", "role", "avatar_color" } ] }
→ { "users": [] }  if config/dev_users.yaml missing
```

No auth required. Reads YAML with `yaml.safe_load`.

---

## Stop SAGE Migration

Remove from `Header.tsx`: `confirmStop` state, Stop button JSX, confirm overlay. Move all into `UserMenu.tsx`. Identical behaviour.

---

## Keyboard Shortcuts Modal

| Group | Shortcut | Action |
|-------|---------|--------|
| Navigation | `Ctrl+K` | Command palette |
| Navigation | `G A` | Go to Approvals |
| Navigation | `G Q` | Go to Queue |
| Navigation | `G D` | Go to Dashboard |
| Approvals | `A` | Approve focused proposal |
| Approvals | `R` | Reject focused proposal |

---

## Testing

**Unit:**
- `UserPrefsContext`: load from localStorage on mount; `updatePref` persists; identity switch loads new prefs and re-applies CSS vars; `resetPrefs` restores defaults
- `AuthContext` extensions: `switchDevUser` sets `user` to mapped `UserIdentity`; `isDevMode` true when devUsers > 0
- `UserMenu`: opens on click; closes on outside click + Escape; Switch Identity only shown when `isDevMode`
- `GET /config/dev-users`: returns list from YAML; returns `[]` when file missing

**Manual:**
- Switch identity → prefs update live; refresh → prefs restored
- Switch color combo → sidebar color changes immediately, content bg changes
- Switch font family → text changes across whole app without reload
- Stop SAGE confirm works from dropdown
