# Header User Menu + Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the header Stop button with a user avatar dropdown providing dev-mode identity switching, dual color combo theming, font/density/timezone prefs, keyboard shortcuts modal, and Stop SAGE.

**Architecture:** Extend existing `AuthContext` with `devUsers/switchDevUser/isDevMode`; add new `UserPrefsContext` for localStorage-backed display prefs; create `UserMenu` dropdown component that composes both contexts; write dual-combo CSS vars into index.css and apply them live via `document.documentElement.style`.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide icons, FastAPI (Python), PyYAML, Vitest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `config/dev_users.yaml` | Create | Dev-mode user roster |
| `web/src/api/auth.ts` | Modify | Add `DevUser` type + `getDevUsers()` |
| `web/src/api/client.ts` | Modify | Add `fetchDevUsers()` |
| `web/src/context/AuthContext.tsx` | Modify | Add devUsers, switchDevUser, isDevMode |
| `web/src/context/UserPrefsContext.tsx` | Create | Per-user display prefs + localStorage adapter |
| `web/src/components/layout/UserMenu.tsx` | Create | Avatar button + dropdown panel |
| `web/src/components/ui/KeyboardShortcutsModal.tsx` | Create | Shortcuts reference modal |
| `web/src/components/layout/Header.tsx` | Modify | Remove Stop button, add UserMenu |
| `web/src/App.tsx` | Modify | Wrap in UserPrefsProvider |
| `web/src/index.css` | Modify | Add user pref CSS vars + color combo definitions |
| `web/index.html` | Modify | Add Google Fonts links |
| `src/interface/api.py` | Modify | Add GET /config/dev-users endpoint |
| `solutions/starter/project.yaml` | Modify | Add roles: template block |
| `tests/test_dev_users_endpoint.py` | Create | Backend endpoint tests |
| `web/src/context/__tests__/UserPrefsContext.test.tsx` | Create | Context unit tests |

---

### Task 1: Backend — config/dev_users.yaml + GET /config/dev-users

**Files:**
- Create: `config/dev_users.yaml`
- Modify: `src/interface/api.py`
- Create: `tests/test_dev_users_endpoint.py`

- [ ] **Step 1: Create dev_users.yaml**

```yaml
# config/dev_users.yaml
# Dev-mode user roster. Loaded by GET /config/dev-users.
# Each entry maps to a UserIdentity in the frontend (sub=id, provider='dev').
users:
  - id: suman
    name: Admin User
    email: suman@example.com
    role: admin
    avatar_color: '#6366f1'
  - id: dr_chen
    name: Dr. Chen
    email: chen@example.com
    role: approver
    avatar_color: '#10b981'
  - id: reviewer_2
    name: Priya S.
    email: priya@example.com
    role: approver
    avatar_color: '#f59e0b'
  - id: viewer_1
    name: Guest Viewer
    email: viewer@example.com
    role: viewer
    avatar_color: '#64748b'
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_dev_users_endpoint.py`:

```python
"""Tests for GET /config/dev-users endpoint."""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient


def test_dev_users_returns_list(monkeypatch, tmp_path):
    """Should return users from dev_users.yaml."""
    yaml_content = """
users:
  - id: alice
    name: Alice
    email: alice@example.com
    role: admin
    avatar_color: '#6366f1'
"""
    yaml_file = tmp_path / "dev_users.yaml"
    yaml_file.write_text(yaml_content)

    # Point the endpoint at our temp file
    monkeypatch.setenv("SAGE_DEV_USERS_PATH", str(yaml_file))

    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/config/dev-users")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert len(data["users"]) == 1
    assert data["users"][0]["id"] == "alice"
    assert data["users"][0]["role"] == "admin"


def test_dev_users_missing_file_returns_empty(monkeypatch, tmp_path):
    """Should return empty list when file doesn't exist."""
    monkeypatch.setenv("SAGE_DEV_USERS_PATH", str(tmp_path / "nonexistent.yaml"))

    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/config/dev-users")
    assert resp.status_code == 200
    assert resp.json() == {"users": []}
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/python -m pytest tests/test_dev_users_endpoint.py -v 2>&1 | head -30
```
Expected: FAIL — endpoint does not exist yet.

- [ ] **Step 4: Add the endpoint to api.py**

Find the section near the end of `src/interface/api.py` where other config endpoints live. Add after the last `@app.get` or `@app.post` before the shutdown endpoint:

```python
# ---------------------------------------------------------------------------
# Dev users (dev-mode identity roster)
# ---------------------------------------------------------------------------

@app.get("/config/dev-users")
async def get_dev_users():
    """Return dev-mode user roster from config/dev_users.yaml.
    Returns empty list if file does not exist — graceful degradation.
    """
    import yaml as _yaml
    path = os.environ.get(
        "SAGE_DEV_USERS_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "dev_users.yaml")
    )
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return {"users": []}
    with open(path, "r", encoding="utf-8") as f:
        data = _yaml.safe_load(f) or {}
    return {"users": data.get("users", [])}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/python -m pytest tests/test_dev_users_endpoint.py -v
```
Expected: 2 PASSED.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/python -m pytest tests/ -x -q 2>&1 | tail -10
```
Expected: all pass (1 skipped is OK).

- [ ] **Step 7: Add roles block to starter/project.yaml**

Read `solutions/starter/project.yaml`, then add at the end:

```yaml
# Role assignments for dev-mode identity switching.
# Maps role names to lists of user IDs from config/dev_users.yaml.
# "*" means all users have that role.
roles:
  admin:
    - suman
  approver:
    - suman
    - dr_chen
  viewer:
    - "*"
```

- [ ] **Step 8: Commit**

```bash
cd C:/sandbox/SAGE && git add config/dev_users.yaml tests/test_dev_users_endpoint.py src/interface/api.py solutions/starter/project.yaml
git commit -m "feat(auth): GET /config/dev-users endpoint + dev_users.yaml roster"
```

---

### Task 2: Frontend API layer — DevUser type + fetch functions

**Files:**
- Modify: `web/src/api/auth.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Add DevUser type and getDevUsers to auth.ts**

In `web/src/api/auth.ts`, add after the existing `UserRole` interface:

```typescript
export interface DevUser {
  id:           string
  name:         string
  email:        string
  role:         string
  avatar_color: string
}

export const getDevUsers = () =>
  get<{ users: DevUser[] }>('/config/dev-users')
```

- [ ] **Step 2: Add fetchDevUsers to client.ts**

In `web/src/api/client.ts`, find the end of the exported functions and add:

```typescript
// Dev users
export const fetchDevUsers = () =>
  get<{ users: import('./auth').DevUser[] }>('/config/dev-users')
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/api/auth.ts web/src/api/client.ts
git commit -m "feat(auth): DevUser type + fetchDevUsers API function"
```

---

### Task 3: Extend AuthContext with dev-mode identity switching

**Files:**
- Modify: `web/src/context/AuthContext.tsx`

- [ ] **Step 1: Read the current AuthContext**

Read `web/src/context/AuthContext.tsx` in full.

- [ ] **Step 2: Rewrite AuthContext with dev-mode extensions**

Replace the entire file:

```typescript
/**
 * SAGE AuthContext — provides current user identity throughout the app.
 *
 * Dev-mode extensions:
 *   isDevMode    — true when GET /config/dev-users returns a non-empty list
 *   devUsers     — full roster of switchable identities
 *   switchDevUser(id) — sets active user from roster without an API call;
 *                       maps DevUser → UserIdentity (sub=id, provider='dev')
 */
import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { getMe, getDevUsers, UserIdentity, DevUser } from '../api/auth'

interface AuthContextValue {
  user:            UserIdentity | null
  isAuthenticated: boolean
  isLoading:       boolean
  refresh:         () => void
  // Dev-mode
  isDevMode:       boolean
  devUsers:        DevUser[]
  switchDevUser:   (id: string) => void
}

const AuthContext = createContext<AuthContextValue>({
  user:            null,
  isAuthenticated: false,
  isLoading:       true,
  refresh:         () => {},
  isDevMode:       false,
  devUsers:        [],
  switchDevUser:   () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]         = useState<UserIdentity | null>(null)
  const [isLoading, setLoading] = useState(true)
  const [devUsers, setDevUsers] = useState<DevUser[]>([])

  const fetchIdentity = useCallback(() => {
    setLoading(true)
    getMe()
      .then(identity => setUser(identity))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchIdentity()
    // Load dev roster (fire-and-forget; graceful if endpoint absent)
    getDevUsers()
      .then(data => setDevUsers(data.users ?? []))
      .catch(() => setDevUsers([]))
  }, [fetchIdentity])

  const switchDevUser = useCallback((id: string) => {
    const found = devUsers.find(u => u.id === id)
    if (!found) return
    const identity: UserIdentity = {
      sub:      found.id,
      email:    found.email,
      name:     found.name,
      role:     found.role,
      provider: 'dev',
    }
    setUser(identity)
  }, [devUsers])

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: user !== null,
      isLoading,
      refresh: fetchIdentity,
      isDevMode: devUsers.length > 0,
      devUsers,
      switchDevUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/context/AuthContext.tsx
git commit -m "feat(auth): extend AuthContext with devUsers/switchDevUser/isDevMode"
```

---

### Task 4: CSS vars for user prefs + Google Fonts

**Files:**
- Modify: `web/src/index.css`
- Modify: `web/index.html`

- [ ] **Step 1: Add user pref CSS vars and color combo data to index.css**

Read the current `web/src/index.css`, then add after the existing `:root { }` block:

```css
/* ──────────────────────────────────────────────────────────────────────────
   User Preference CSS Variables
   Written at runtime by UserPrefsContext when user changes display settings.
   ────────────────────────────────────────────────────────────────────────── */

:root {
  --sage-user-accent:     #71717a;   /* overrides --sage-accent if set */
  --sage-content-bg:      #fafafa;
  --sage-font-family:     'Inter', sans-serif;
  --sage-font-size-base:  14px;
  --sage-density:         1rem;
}

/* Apply font family and size globally */
body {
  font-family: var(--sage-font-family);
  font-size:   var(--sage-font-size-base);
}

/* Dark mode class — toggled by UserPrefsContext theme pref */
html.dark body {
  @apply bg-zinc-900 text-zinc-100;
}
html.dark .bg-white { background-color: #18181b !important; }
html.dark .bg-zinc-50 { background-color: #09090b !important; }
html.dark .text-zinc-900 { color: #f4f4f5 !important; }
html.dark .border-zinc-200 { border-color: #27272a !important; }
html.dark .text-zinc-600 { color: #a1a1aa !important; }
html.dark .text-zinc-500 { color: #71717a !important; }
```

- [ ] **Step 2: Add Google Fonts to index.html**

Replace the current `<head>` section of `web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sage[ai] — Manufacturing Intelligence</title>
    <!-- Google Fonts — loaded on demand when user selects font family -->
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Roboto:wght@400;500;700&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Verify TypeScript still compiles and Vite builds**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -10
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/index.css web/index.html
git commit -m "feat(theme): user pref CSS vars + dark mode class + Google Fonts"
```

---

### Task 5: UserPrefsContext

**Files:**
- Create: `web/src/context/UserPrefsContext.tsx`
- Create: `web/src/context/__tests__/UserPrefsContext.test.tsx`

- [ ] **Step 1: Write the test file**

Create `web/src/context/__tests__/UserPrefsContext.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { UserPrefsProvider, useUserPrefs, DEFAULT_PREFS } from '../UserPrefsContext'
import { AuthContext } from '../AuthContext'

// Mock auth context
const mockAuthValue = {
  user: { sub: 'user1', name: 'Test', email: 't@t.com', role: 'admin', provider: 'dev' },
  isAuthenticated: true, isLoading: false, refresh: vi.fn(),
  isDevMode: true, devUsers: [], switchDevUser: vi.fn(),
}

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <AuthContext.Provider value={mockAuthValue}>
      <UserPrefsProvider>{children}</UserPrefsProvider>
    </AuthContext.Provider>
  )
}

describe('UserPrefsContext', () => {
  beforeEach(() => localStorage.clear())

  it('loads default prefs when localStorage is empty', () => {
    let prefs: any
    function Consumer() {
      prefs = useUserPrefs().prefs
      return null
    }
    render(<Consumer />, { wrapper })
    expect(prefs.colorCombo).toBe('zinc')
    expect(prefs.fontFamily).toBe('inter')
  })

  it('updatePref persists to localStorage and updates state', () => {
    let ctx: any
    function Consumer() {
      ctx = useUserPrefs()
      return null
    }
    render(<Consumer />, { wrapper })
    act(() => ctx.updatePref('colorCombo', 'night'))
    expect(ctx.prefs.colorCombo).toBe('night')
    const stored = JSON.parse(localStorage.getItem('sage_user_prefs_user1') ?? '{}')
    expect(stored.colorCombo).toBe('night')
  })

  it('applies dark class to html element when theme=dark', () => {
    let ctx: any
    function Consumer() {
      ctx = useUserPrefs()
      return null
    }
    render(<Consumer />, { wrapper })
    act(() => ctx.updatePref('theme', 'dark'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('removes dark class when theme=light', () => {
    document.documentElement.classList.add('dark')
    let ctx: any
    function Consumer() { ctx = useUserPrefs(); return null }
    render(<Consumer />, { wrapper })
    act(() => ctx.updatePref('theme', 'light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('resetPrefs restores defaults', () => {
    let ctx: any
    function Consumer() { ctx = useUserPrefs(); return null }
    render(<Consumer />, { wrapper })
    act(() => ctx.updatePref('colorCombo', 'rose'))
    act(() => ctx.resetPrefs())
    expect(ctx.prefs.colorCombo).toBe(DEFAULT_PREFS.colorCombo)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/sandbox/SAGE/web && npx vitest run src/context/__tests__/UserPrefsContext.test.tsx 2>&1 | tail -15
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create UserPrefsContext.tsx**

Create `web/src/context/UserPrefsContext.tsx`:

```typescript
import {
  createContext, useContext, useEffect, useState, useCallback, ReactNode
} from 'react'
import { useAuth } from './AuthContext'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Dual color combo definitions
// Each combo: [sidebarBg, sidebarText, contentBg, accent, accentHover]
// ---------------------------------------------------------------------------

export const COLOR_COMBOS: Record<UserPrefs['colorCombo'], {
  label: string
  sidebarBg: string; sidebarText: string; contentBg: string
  accent: string; accentHover: string
}> = {
  zinc:   { label: 'Zinc',   sidebarBg: '#18181b', sidebarText: '#a1a1aa', contentBg: '#fafafa', accent: '#71717a', accentHover: '#52525b' },
  night:  { label: 'Night',  sidebarBg: '#0f172a', sidebarText: '#94a3b8', contentBg: '#ffffff', accent: '#3b82f6', accentHover: '#2563eb' },
  forest: { label: 'Forest', sidebarBg: '#052e16', sidebarText: '#86efac', contentBg: '#fefce8', accent: '#16a34a', accentHover: '#15803d' },
  ocean:  { label: 'Ocean',  sidebarBg: '#042f2e', sidebarText: '#99f6e4', contentBg: '#f0fdfa', accent: '#0d9488', accentHover: '#0f766e' },
  slate:  { label: 'Slate',  sidebarBg: '#1e293b', sidebarText: '#94a3b8', contentBg: '#f8fafc', accent: '#6366f1', accentHover: '#4f46e5' },
  rose:   { label: 'Rose',   sidebarBg: '#1c0a0a', sidebarText: '#fca5a5', contentBg: '#fff1f2', accent: '#e11d48', accentHover: '#be123c' },
}

export const FONT_FAMILIES: Record<UserPrefs['fontFamily'], string> = {
  'inter':          "'Inter', sans-serif",
  'jetbrains-mono': "'JetBrains Mono', monospace",
  'system-ui':      'system-ui, sans-serif',
  'geist':          "'Geist', sans-serif",
  'roboto':         "'Roboto', sans-serif",
}

export const FONT_SIZES: Record<UserPrefs['fontSize'], string> = {
  sm: '13px', md: '14px', lg: '16px',
}

export const DENSITIES: Record<UserPrefs['density'], string> = {
  compact: '0.75rem', comfortable: '1rem',
}

// ---------------------------------------------------------------------------
// localStorage adapter (swap for a backend adapter to sync prefs)
// ---------------------------------------------------------------------------

interface UserPrefsAdapter {
  load(userId: string): UserPrefs | null
  save(userId: string, prefs: UserPrefs): void
}

const localStorageAdapter: UserPrefsAdapter = {
  load: (userId) => {
    try {
      const raw = localStorage.getItem(`sage_user_prefs_${userId}`)
      return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : null
    } catch { return null }
  },
  save: (userId, prefs) => {
    try {
      localStorage.setItem(`sage_user_prefs_${userId}`, JSON.stringify(prefs))
    } catch { /* storage full — ignore */ }
  },
}

// ---------------------------------------------------------------------------
// DOM application
// ---------------------------------------------------------------------------

function applyPrefs(prefs: UserPrefs) {
  const root = document.documentElement

  // Dark / light mode
  if (prefs.theme === 'dark') {
    root.classList.add('dark')
  } else if (prefs.theme === 'light') {
    root.classList.remove('dark')
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.classList.toggle('dark', prefersDark)
  }

  // Color combo — write all 6 sidebar+content vars at once
  const combo = COLOR_COMBOS[prefs.colorCombo]
  root.style.setProperty('--sage-sidebar-bg',    combo.sidebarBg)
  root.style.setProperty('--sage-sidebar-text',  combo.sidebarText)
  root.style.setProperty('--sage-content-bg',    combo.contentBg)
  root.style.setProperty('--sage-user-accent',   combo.accent)
  root.style.setProperty('--sage-accent-hover',  combo.accentHover)

  // Font
  root.style.setProperty('--sage-font-family',    FONT_FAMILIES[prefs.fontFamily])
  root.style.setProperty('--sage-font-size-base', FONT_SIZES[prefs.fontSize])
  root.style.setProperty('--sage-density',        DENSITIES[prefs.density])
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface UserPrefsContextValue {
  prefs:      UserPrefs
  updatePref: <K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => void
  resetPrefs: () => void
}

export const UserPrefsContext = createContext<UserPrefsContextValue>({
  prefs:      DEFAULT_PREFS,
  updatePref: () => {},
  resetPrefs: () => {},
})

export function UserPrefsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const userId = user?.sub ?? 'anonymous'
  const adapter = localStorageAdapter

  const [prefs, setPrefs] = useState<UserPrefs>(() => {
    return adapter.load(userId) ?? DEFAULT_PREFS
  })

  // When identity switches, reload prefs for new user
  useEffect(() => {
    const loaded = adapter.load(userId) ?? DEFAULT_PREFS
    setPrefs(loaded)
    applyPrefs(loaded)
  }, [userId])

  // Apply on first render
  useEffect(() => { applyPrefs(prefs) }, [])

  const updatePref = useCallback(<K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => {
    setPrefs(prev => {
      const next = { ...prev, [key]: value }
      adapter.save(userId, next)
      applyPrefs(next)
      return next
    })
  }, [userId, adapter])

  const resetPrefs = useCallback(() => {
    setPrefs(DEFAULT_PREFS)
    adapter.save(userId, DEFAULT_PREFS)
    applyPrefs(DEFAULT_PREFS)
  }, [userId, adapter])

  return (
    <UserPrefsContext.Provider value={{ prefs, updatePref, resetPrefs }}>
      {children}
    </UserPrefsContext.Provider>
  )
}

export function useUserPrefs(): UserPrefsContextValue {
  return useContext(UserPrefsContext)
}
```

- [ ] **Step 4: Export AuthContext (not just useAuth) so tests can mock it**

In `web/src/context/AuthContext.tsx`, add this line after the `const AuthContext = createContext(...)` line:

```typescript
export { AuthContext }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd C:/sandbox/SAGE/web && npx vitest run src/context/__tests__/UserPrefsContext.test.tsx 2>&1 | tail -15
```
Expected: 5 PASSED.

- [ ] **Step 6: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/context/UserPrefsContext.tsx web/src/context/__tests__/UserPrefsContext.test.tsx web/src/context/AuthContext.tsx
git commit -m "feat(theme): UserPrefsContext with dual color combos + localStorage adapter"
```

---

### Task 6: Wire UserPrefsProvider into App.tsx

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Read App.tsx**

Read `web/src/App.tsx` in full.

- [ ] **Step 2: Add UserPrefsProvider import and wrap**

In `web/src/App.tsx`:

Add import after the `AuthProvider` import:
```typescript
import { UserPrefsProvider } from './context/UserPrefsContext'
```

Wrap `<ThemeProvider>` with `<UserPrefsProvider>` inside `<AuthProvider>`:
```typescript
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <UserPrefsProvider>
          <ThemeProvider>
            <TourProvider>
              <AppShell />
            </TourProvider>
          </ThemeProvider>
        </UserPrefsProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -10
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/App.tsx
git commit -m "feat(app): wire UserPrefsProvider into app tree"
```

---

### Task 7: KeyboardShortcutsModal

**Files:**
- Create: `web/src/components/ui/KeyboardShortcutsModal.tsx`

- [ ] **Step 1: Create the component**

Create `web/src/components/ui/KeyboardShortcutsModal.tsx`:

```typescript
interface KeyboardShortcutsModalProps {
  onClose: () => void
}

const SHORTCUTS = [
  { group: 'Navigation', key: 'Ctrl+K',  action: 'Open command palette' },
  { group: 'Navigation', key: 'G  A',    action: 'Go to Approvals' },
  { group: 'Navigation', key: 'G  Q',    action: 'Go to Task Queue' },
  { group: 'Navigation', key: 'G  D',    action: 'Go to Dashboard' },
  { group: 'Approvals',  key: 'A',       action: 'Approve focused proposal' },
  { group: 'Approvals',  key: 'R',       action: 'Reject focused proposal' },
]

export default function KeyboardShortcutsModal({ onClose }: KeyboardShortcutsModalProps) {
  const groups = [...new Set(SHORTCUTS.map(s => s.group))]

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#18181b', border: '1px solid #27272a',
          padding: '24px', width: '380px', maxHeight: '80vh', overflowY: 'auto',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Keyboard Shortcuts</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#71717a', fontSize: '18px', lineHeight: 1 }}
          >×</button>
        </div>

        {groups.map(group => (
          <div key={group} style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#52525b', marginBottom: '6px' }}>
              {group}
            </div>
            {SHORTCUTS.filter(s => s.group === group).map(s => (
              <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: '#a1a1aa' }}>{s.action}</span>
                <kbd style={{
                  background: '#27272a', border: '1px solid #3f3f46',
                  padding: '2px 6px', fontSize: '11px', color: '#e4e4e7',
                  fontFamily: 'monospace',
                }}>
                  {s.key}
                </kbd>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -10
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/components/ui/KeyboardShortcutsModal.tsx
git commit -m "feat(ui): KeyboardShortcutsModal component"
```

---

### Task 8: UserMenu component

**Files:**
- Create: `web/src/components/layout/UserMenu.tsx`

- [ ] **Step 1: Create UserMenu.tsx**

Create `web/src/components/layout/UserMenu.tsx`:

```typescript
import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useUserPrefs, COLOR_COMBOS, FONT_FAMILIES, UserPrefs } from '../../context/UserPrefsContext'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import KeyboardShortcutsModal from '../ui/KeyboardShortcutsModal'

async function shutdownSage() {
  await fetch('/api/shutdown', { method: 'POST' })
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// Split-circle swatch showing sidebar (left) + content (right) halves
function ComboSwatch({ comboKey, active, onClick }: {
  comboKey: UserPrefs['colorCombo']
  active: boolean
  onClick: () => void
}) {
  const c = COLOR_COMBOS[comboKey]
  return (
    <button
      onClick={onClick}
      title={c.label}
      style={{
        width: 22, height: 22, cursor: 'pointer', padding: 0, border: 'none',
        outline: active ? `2px solid ${c.accent}` : '2px solid transparent',
        outlineOffset: 2, overflow: 'hidden', display: 'inline-block',
        background: 'none', flexShrink: 0,
      }}
    >
      <svg width="22" height="22" viewBox="0 0 22 22">
        {/* left half = sidebar color */}
        <path d="M11 0 A11 11 0 0 0 11 22 Z" fill={c.sidebarBg} />
        {/* right half = content color */}
        <path d="M11 0 A11 11 0 0 1 11 22 Z" fill={c.contentBg} />
        <circle cx="11" cy="11" r="10.5" fill="none" stroke="#3f3f46" strokeWidth="1" />
      </svg>
    </button>
  )
}

export default function UserMenu() {
  const [open, setOpen] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [confirmStop, setConfirmStop] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const navigate = useNavigate()

  const { user, devUsers, switchDevUser, isDevMode } = useAuth()
  const { prefs, updatePref, resetPrefs } = useUserPrefs()
  const { data: projectData } = useProjectConfig()
  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handle(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function handle(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', handle)
    return () => document.removeEventListener('keydown', handle)
  }, [open])

  // Compute panel position from button
  const [panelPos, setPanelPos] = useState({ top: 0, right: 0 })
  const toggleOpen = useCallback(() => {
    if (!open && buttonRef.current) {
      const r = buttonRef.current.getBoundingClientRect()
      setPanelPos({ top: r.bottom + 4, right: window.innerWidth - r.right })
    }
    setOpen(o => !o)
  }, [open])

  const displayName = user?.name ?? 'Guest'
  const displayEmail = user?.email ?? ''
  const displayRole = user?.role ?? 'viewer'
  const avatarBg = devUsers.find(u => u.id === user?.sub)?.avatar_color ?? '#52525b'
  const sageVersion = 'v2.1'
  const llmInfo = healthData?.llm_provider ?? 'unknown'
  const solutionName = projectData?.name ?? 'SAGE Framework'

  const roleBadgeColor: Record<string, string> = {
    admin: '#6366f1', approver: '#10b981', operator: '#f59e0b', viewer: '#64748b',
  }

  const fontFamilyOptions: { value: UserPrefs['fontFamily']; label: string }[] = [
    { value: 'inter',          label: 'Inter' },
    { value: 'jetbrains-mono', label: 'JetBrains Mono' },
    { value: 'system-ui',      label: 'System UI' },
    { value: 'geist',          label: 'Geist' },
    { value: 'roboto',         label: 'Roboto' },
  ]

  const comboKeys = Object.keys(COLOR_COMBOS) as UserPrefs['colorCombo'][]

  const selectStyle: React.CSSProperties = {
    background: '#27272a', border: '1px solid #3f3f46', color: '#e4e4e7',
    fontSize: '11px', padding: '3px 6px', cursor: 'pointer', width: '100%',
  }

  const rowStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: '6px', gap: '8px',
  }

  const labelStyle: React.CSSProperties = {
    fontSize: '11px', color: '#71717a', flexShrink: 0, width: '60px',
  }

  const dividerStyle: React.CSSProperties = {
    borderTop: '1px solid #27272a', margin: '8px 0',
  }

  const sectionStyle: React.CSSProperties = { padding: '10px 14px' }

  const actionRowStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 14px',
    cursor: 'pointer', fontSize: '12px', color: '#a1a1aa',
    transition: 'background 0.1s',
  }

  return (
    <>
      {/* Avatar trigger button */}
      <button
        ref={buttonRef}
        onClick={toggleOpen}
        style={{
          width: 28, height: 28, borderRadius: '50%', border: 'none',
          background: avatarBg, color: '#fff', fontSize: '11px', fontWeight: 700,
          cursor: 'pointer', flexShrink: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', letterSpacing: '0.02em',
        }}
        title={`${displayName} (${displayRole})`}
      >
        {initials(displayName)}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          ref={panelRef}
          style={{
            position: 'fixed', top: panelPos.top, right: panelPos.right,
            width: 300, zIndex: 9999,
            background: '#18181b', border: '1px solid #27272a',
            boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
            overflowY: 'auto', maxHeight: 'calc(100vh - 60px)',
          }}
        >
          {/* Identity section */}
          <div style={{ ...sectionStyle, paddingBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', background: avatarBg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '12px', fontWeight: 700, color: '#fff', flexShrink: 0,
              }}>
                {initials(displayName)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {displayName}
                  </span>
                  <span style={{
                    fontSize: '9px', fontWeight: 700, textTransform: 'uppercase',
                    padding: '1px 5px', letterSpacing: '0.08em',
                    background: `${roleBadgeColor[displayRole] ?? '#52525b'}22`,
                    color: roleBadgeColor[displayRole] ?? '#a1a1aa',
                    border: `1px solid ${roleBadgeColor[displayRole] ?? '#52525b'}44`,
                    flexShrink: 0,
                  }}>
                    {displayRole}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#52525b', marginTop: '1px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {displayEmail}
                </div>
              </div>
            </div>
            <div style={{ fontSize: '10px', color: '#3f3f46', marginTop: '2px', paddingLeft: '42px' }}>
              {solutionName}
            </div>
          </div>

          <div style={dividerStyle} />

          {/* Switch Identity (dev mode only) */}
          {isDevMode && (
            <>
              <div style={sectionStyle}>
                <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#52525b', marginBottom: '6px' }}>
                  Switch Identity
                </div>
                <select
                  style={selectStyle}
                  value={user?.sub ?? ''}
                  onChange={e => switchDevUser(e.target.value)}
                >
                  {devUsers.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.name} — {u.role}
                    </option>
                  ))}
                </select>
              </div>
              <div style={dividerStyle} />
            </>
          )}

          {/* Display settings */}
          <div style={sectionStyle}>
            <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#52525b', marginBottom: '8px' }}>
              Display
            </div>

            <div style={rowStyle}>
              <span style={labelStyle}>Theme</span>
              <select style={selectStyle} value={prefs.theme} onChange={e => updatePref('theme', e.target.value as UserPrefs['theme'])}>
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System</option>
              </select>
            </div>

            <div style={{ marginBottom: '8px' }}>
              <span style={{ ...labelStyle, display: 'block', marginBottom: '6px' }}>Colors</span>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {comboKeys.map(k => (
                  <ComboSwatch key={k} comboKey={k} active={prefs.colorCombo === k} onClick={() => updatePref('colorCombo', k)} />
                ))}
              </div>
              <div style={{ fontSize: '10px', color: '#3f3f46', marginTop: '4px' }}>
                {COLOR_COMBOS[prefs.colorCombo].label}
              </div>
            </div>

            <div style={rowStyle}>
              <span style={labelStyle}>Font</span>
              <select style={selectStyle} value={prefs.fontFamily} onChange={e => updatePref('fontFamily', e.target.value as UserPrefs['fontFamily'])}>
                {fontFamilyOptions.map(f => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>

            <div style={rowStyle}>
              <span style={labelStyle}>Size</span>
              <select style={selectStyle} value={prefs.fontSize} onChange={e => updatePref('fontSize', e.target.value as UserPrefs['fontSize'])}>
                <option value="sm">Small</option>
                <option value="md">Medium</option>
                <option value="lg">Large</option>
              </select>
            </div>

            <div style={rowStyle}>
              <span style={labelStyle}>Density</span>
              <select style={selectStyle} value={prefs.density} onChange={e => updatePref('density', e.target.value as UserPrefs['density'])}>
                <option value="compact">Compact</option>
                <option value="comfortable">Comfortable</option>
              </select>
            </div>

            <div style={rowStyle}>
              <span style={labelStyle}>Timezone</span>
              <select style={selectStyle} value={prefs.timezone} onChange={e => updatePref('timezone', e.target.value)}>
                <option value="UTC">UTC</option>
                <option value="America/New_York">Eastern (ET)</option>
                <option value="America/Chicago">Central (CT)</option>
                <option value="America/Denver">Mountain (MT)</option>
                <option value="America/Los_Angeles">Pacific (PT)</option>
                <option value="Europe/London">London (GMT)</option>
                <option value="Europe/Berlin">Berlin (CET)</option>
                <option value="Asia/Kolkata">India (IST)</option>
                <option value="Asia/Tokyo">Tokyo (JST)</option>
                <option value="Australia/Sydney">Sydney (AEST)</option>
              </select>
            </div>

            <button
              onClick={resetPrefs}
              style={{ fontSize: '10px', color: '#3f3f46', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0', marginTop: '2px' }}
            >
              Reset to defaults
            </button>
          </div>

          <div style={dividerStyle} />

          {/* Keyboard shortcuts */}
          <div
            style={{ ...actionRowStyle }}
            onClick={() => { setShowShortcuts(true); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#27272a')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span style={{ fontSize: '13px' }}>⌨</span>
            <span>Keyboard shortcuts</span>
          </div>

          <div style={dividerStyle} />

          {/* About block */}
          <div style={{ ...sectionStyle, paddingTop: '8px', paddingBottom: '8px' }}>
            <div style={{ fontSize: '10px', color: '#3f3f46' }}>
              SAGE {sageVersion} · {llmInfo}
            </div>
          </div>

          <div style={dividerStyle} />

          {/* Actions */}
          <div
            style={{ ...actionRowStyle }}
            onClick={() => { navigate('/access-control'); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#27272a')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span style={{ fontSize: '12px' }}>⬡</span>
            <span>Access Control</span>
          </div>

          {!confirmStop ? (
            <div
              style={{ ...actionRowStyle }}
              onClick={() => setConfirmStop(true)}
              onMouseEnter={e => (e.currentTarget.style.background = '#27272a')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ fontSize: '12px', color: '#ef4444' }}>■</span>
              <span style={{ color: '#ef4444' }}>Stop SAGE</span>
            </div>
          ) : (
            <div style={{ ...sectionStyle, paddingTop: '6px', paddingBottom: '6px' }}>
              <div style={{ fontSize: '12px', color: '#ef4444', marginBottom: '6px', fontWeight: 600 }}>Stop SAGE?</div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => { shutdownSage(); setConfirmStop(false); setOpen(false) }}
                  style={{ fontSize: '11px', padding: '4px 12px', background: '#ef4444', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
                >
                  Yes
                </button>
                <button
                  onClick={() => setConfirmStop(false)}
                  style={{ fontSize: '11px', padding: '4px 12px', background: '#27272a', color: '#a1a1aa', border: '1px solid #3f3f46', cursor: 'pointer' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div style={dividerStyle} />

          {/* Logout */}
          <div
            style={{ ...actionRowStyle, paddingBottom: '10px' }}
            onClick={() => {
              if (devUsers.length > 0) switchDevUser(devUsers[0].id)
              setOpen(false)
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#27272a')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span>→</span>
            <span>{isDevMode ? `Switch to ${devUsers[0]?.name ?? 'default'}` : 'Logout'}</span>
          </div>
        </div>
      )}

      {/* Keyboard shortcuts modal */}
      {showShortcuts && <KeyboardShortcutsModal onClose={() => setShowShortcuts(false)} />}
    </>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/components/layout/UserMenu.tsx
git commit -m "feat(ui): UserMenu dropdown — identity, color combos, font, Stop SAGE"
```

---

### Task 9: Wire UserMenu into Header, remove Stop button

**Files:**
- Modify: `web/src/components/layout/Header.tsx`

- [ ] **Step 1: Read current Header.tsx**

Read `web/src/components/layout/Header.tsx` in full (already read above — 163 lines).

- [ ] **Step 2: Rewrite Header.tsx**

Replace the entire file:

```typescript
import { useLocation } from 'react-router-dom'
import { Command } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import UserMenu from './UserMenu'

const PAGE_TITLES: Record<string, string> = {
  '/':             'Dashboard',
  '/agents':       'AI Agents',
  '/analyst':      'Log Analyst',
  '/developer':    'Developer',
  '/audit':        'Audit Log',
  '/monitor':      'Monitor',
  '/improvements': 'Improvements',
  '/llm':          'LLM Settings',
  '/settings':     'Settings',
  '/yaml-editor':  'Config Editor',
  '/live-console': 'Live Console',
  '/onboarding':   'New Solution',
  '/queue':          'Task Queue',
  '/access-control': 'Access Control',
  '/costs':          'Cost Tracker',
  '/workflows':      'Workflows',
  '/issues':         'Issues',
  '/activity':       'Activity',
  '/goals':          'Goals',
  '/org':            'Org Chart',
  '/approvals':      'Approvals',
  '/knowledge':      'Knowledge',
}

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
  '/knowledge':     'Knowledge',
  '/issues':        'Knowledge',
  '/org-graph':     'Organization',
  '/onboarding':    'Organization',
  '/llm':           'Admin',
  '/yaml-editor':   'Admin',
  '/access-control':'Admin',
  '/integrations':  'Admin',
  '/settings':      'Admin',
}

interface HeaderProps {
  onOpenPalette?: () => void
}

export default function Header({ onOpenPalette }: HeaderProps) {
  const { pathname } = useLocation()

  const { data: healthData, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const { data: projectData } = useProjectConfig()

  const online = !healthError && !!healthData
  const uiLabels = (projectData as any)?.ui_labels ?? {}
  const UI_LABEL_ROUTES: Record<string, string> = {
    '/analyst':   uiLabels.analyst_page_title,
    '/developer': uiLabels.developer_page_title,
    '/monitor':   uiLabels.monitor_page_title,
  }
  const title = UI_LABEL_ROUTES[pathname] ?? PAGE_TITLES[pathname] ?? 'SAGE[ai]'
  const projectName = projectData?.name ?? 'SAGE Framework'

  return (
    <header
      className="h-14 border-b flex items-center px-4 gap-3 shrink-0 relative"
      style={{ backgroundColor: '#18181b', borderColor: '#27272a' }}
    >
      {/* Breadcrumb + page title */}
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '11px', color: '#64748b' }}>
          {projectName} / {ROUTE_TO_AREA[pathname] ?? 'SAGE'}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', marginTop: '1px' }}>
          {title}
        </div>
      </div>

      {/* Cmd+K command palette trigger */}
      <button
        onClick={onOpenPalette}
        className="flex items-center gap-1.5 text-xs px-2.5 py-1 transition-colors shrink-0"
        style={{ color: '#52525b', border: '1px solid #3f3f46' }}
        title="Open command palette (Cmd+K)"
      >
        <Command size={11} />
        <span>K</span>
      </button>

      {/* API status */}
      <div className="flex items-center gap-1.5 text-xs shrink-0">
        <span
          className="w-1.5 h-1.5"
          style={{ backgroundColor: online ? '#22c55e' : '#ef4444', display: 'inline-block' }}
        />
        <span className="hidden sm:block" style={{ color: '#52525b' }}>
          {online ? healthData?.llm_provider ?? 'Online' : 'API Unreachable'}
        </span>
      </div>

      {/* User menu (replaces Stop button) */}
      <UserMenu />
    </header>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/components/layout/Header.tsx
git commit -m "feat(header): replace Stop button with UserMenu avatar dropdown"
```

---

### Task 10: Run full test suites + git push

- [ ] **Step 1: Run frontend tests**

```bash
cd C:/sandbox/SAGE/web && npx vitest run 2>&1 | tail -20
```
Expected: all pass.

- [ ] **Step 2: Run backend tests**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/python -m pytest tests/ -x -q 2>&1 | tail -10
```
Expected: all pass (1 skipped OK).

- [ ] **Step 3: Fix any TypeScript errors**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1
```
Expected: no errors. If errors, fix them before proceeding.

- [ ] **Step 4: Commit any remaining changes and push**

```bash
cd C:/sandbox/SAGE && git add -A && git status
# Only commit if there are uncommitted changes
git commit -m "feat(sub-project-1): header user menu + auth complete" || true
git push
```

---

## Done

Sub-project 1 is complete when:
- `GET /config/dev-users` returns the 4 dev users
- Avatar button appears in header right side
- Dropdown opens with all 7 sections
- Switching identity changes the avatar initials and role badge
- Switching color combo changes sidebar color and content background live
- Switching font changes typography across the whole app
- Dark/light/system theme toggle works
- Keyboard shortcuts modal opens and closes
- Stop SAGE confirm works from dropdown
- All tests pass
