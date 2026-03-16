/**
 * SAGE Auth API — typed fetch wrappers for T1-001 auth endpoints.
 *
 * All functions delegate to the same BASE/get/post/del helpers used
 * throughout the SAGE codebase to keep the fetch layer consistent.
 */

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.statusText}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.statusText}`)
  // 204 No Content has no body
  if (res.status === 204) return undefined as unknown as T
  return res.json()
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserIdentity {
  sub:      string
  email:    string
  name:     string
  role:     string    // viewer | operator | approver | admin
  provider: string    // oidc | api_key | anonymous
}

export interface ApiKey {
  id:         string
  name:       string
  email:      string
  solution:   string
  role:       string
  created_at: string
  revoked:    number  // 0 = active, 1 = revoked
}

export interface UserRole {
  id:         string
  email:      string
  solution:   string
  role:       string
  granted_by: string
  granted_at: string
}

export interface CreateApiKeyBody {
  name:     string
  email:    string
  solution?: string
  role:     string
}

export interface AssignRoleBody {
  email:    string
  solution?: string
  role:     string
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const getMe = () =>
  get<UserIdentity>('/auth/me')

export const createApiKey = (body: CreateApiKeyBody) =>
  post<{ id: string; key: string; name: string }>('/auth/api-keys', body)

export const listApiKeys = () =>
  get<{ api_keys: ApiKey[]; count: number }>('/auth/api-keys')

export const revokeApiKey = (id: string) =>
  del<{ revoked: boolean; id: string }>(`/auth/api-keys/${id}`)

export const listRoles = () =>
  get<{ roles: UserRole[]; count: number }>('/auth/roles')

export const assignRole = (body: AssignRoleBody) =>
  post<{ assigned: boolean; email: string; solution: string; role: string }>('/auth/roles', body)
