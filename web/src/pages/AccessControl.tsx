import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, ShieldCheck, Key, Users, Trash2, Plus, AlertTriangle, Eye, EyeOff } from 'lucide-react'
import {
  listApiKeys, revokeApiKey, createApiKey, listRoles, assignRole,
  type ApiKey, type UserRole,
} from '../api/auth'
import { useAuth } from '../context/AuthContext'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ROLE_OPTIONS = ['viewer', 'operator', 'approver', 'admin'] as const
type RoleOption = typeof ROLE_OPTIONS[number]

const ROLE_COLORS: Record<RoleOption, string> = {
  viewer:   'bg-gray-100 text-gray-600',
  operator: 'bg-blue-100 text-blue-700',
  approver: 'bg-amber-100 text-amber-700',
  admin:    'bg-red-100 text-red-700',
}

function RoleBadge({ role }: { role: string }) {
  const color = ROLE_COLORS[role as RoleOption] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {role}
    </span>
  )
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// API Keys tab
// ---------------------------------------------------------------------------

function ApiKeysTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [newKeyResult, setNewKeyResult] = useState<{ key: string; name: string } | null>(null)
  const [form, setForm] = useState({ name: '', email: '', role: 'operator' as RoleOption })

  const { data, isLoading, error } = useQuery({
    queryKey: ['auth-api-keys'],
    queryFn: listApiKeys,
  })

  const createMutation = useMutation({
    mutationFn: () => createApiKey({ name: form.name, email: form.email, role: form.role }),
    onSuccess: (res) => {
      setNewKeyResult({ key: res.key, name: res.name })
      setForm({ name: '', email: '', role: 'operator' })
      setShowForm(false)
      qc.invalidateQueries({ queryKey: ['auth-api-keys'] })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeApiKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth-api-keys'] }),
  })

  if (isLoading) return (
    <div className="flex items-center gap-2 text-gray-400 py-8">
      <Loader2 size={16} className="animate-spin" /> Loading API keys…
    </div>
  )

  if (error) return (
    <div className="flex items-center gap-2 text-red-500 py-4">
      <AlertTriangle size={16} /> {(error as Error).message}
    </div>
  )

  const keys: ApiKey[] = data?.api_keys ?? []

  return (
    <div className="space-y-4">
      {/* New key result banner */}
      {newKeyResult && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 space-y-2">
          <p className="text-sm font-semibold text-orange-800">
            API key "{newKeyResult.name}" created — copy it now. It will not be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-white border border-green-300 rounded px-3 py-2 font-mono break-all select-all">
              {newKeyResult.key}
            </code>
            <button
              onClick={() => navigator.clipboard.writeText(newKeyResult.key)}
              className="text-xs text-orange-700 hover:text-orange-900 font-medium px-2 py-1 border border-green-300 rounded"
            >
              Copy
            </button>
          </div>
          <button
            onClick={() => setNewKeyResult(null)}
            className="text-xs text-orange-600 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Create key form */}
      {showForm ? (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">Create API Key</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Key Name</label>
              <input
                type="text"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. CI/CD pipeline"
                className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Owner Email</label>
              <input
                type="email"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="owner@company.com"
                className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Role</label>
              <select
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as RoleOption }))}
                className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {ROLE_OPTIONS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              disabled={!form.name || !form.email || createMutation.isPending}
              onClick={() => createMutation.mutate()}
              className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded font-medium transition-colors flex items-center gap-1.5"
            >
              {createMutation.isPending && <Loader2 size={14} className="animate-spin" />}
              Create Key
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2 rounded border border-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
          {createMutation.isError && (
            <p className="text-xs text-red-500">{(createMutation.error as Error).message}</p>
          )}
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 border border-blue-200 hover:border-blue-400 px-3 py-2 rounded transition-colors"
        >
          <Plus size={14} /> Create API Key
        </button>
      )}

      {/* Keys table */}
      {keys.length === 0 ? (
        <div className="text-sm text-gray-400 py-6 text-center">No API keys yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-200">
                <th className="text-left py-2 pr-4">Name</th>
                <th className="text-left py-2 pr-4">Email</th>
                <th className="text-left py-2 pr-4">Role</th>
                <th className="text-left py-2 pr-4">Created</th>
                <th className="text-left py-2 pr-4">Status</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {keys.map(k => (
                <tr key={k.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 pr-4 font-medium text-gray-800">{k.name}</td>
                  <td className="py-2 pr-4 text-gray-500">{k.email}</td>
                  <td className="py-2 pr-4"><RoleBadge role={k.role} /></td>
                  <td className="py-2 pr-4 text-gray-400 text-xs">{formatDate(k.created_at)}</td>
                  <td className="py-2 pr-4">
                    {k.revoked ? (
                      <span className="text-xs text-red-500 font-medium">Revoked</span>
                    ) : (
                      <span className="text-xs text-orange-600 font-medium">Active</span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    {!k.revoked && (
                      <button
                        onClick={() => revokeMutation.mutate(k.id)}
                        disabled={revokeMutation.isPending}
                        title="Revoke key"
                        className="text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// User Roles tab
// ---------------------------------------------------------------------------

function UserRolesTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ email: '', role: 'operator' as RoleOption })

  const { data, isLoading, error } = useQuery({
    queryKey: ['auth-roles'],
    queryFn: listRoles,
  })

  const assignMutation = useMutation({
    mutationFn: () => assignRole({ email: form.email, role: form.role }),
    onSuccess: () => {
      setForm({ email: '', role: 'operator' })
      setShowForm(false)
      qc.invalidateQueries({ queryKey: ['auth-roles'] })
    },
  })

  if (isLoading) return (
    <div className="flex items-center gap-2 text-gray-400 py-8">
      <Loader2 size={16} className="animate-spin" /> Loading roles…
    </div>
  )

  if (error) return (
    <div className="flex items-center gap-2 text-red-500 py-4">
      <AlertTriangle size={16} /> {(error as Error).message}
    </div>
  )

  const roles: UserRole[] = data?.roles ?? []

  return (
    <div className="space-y-4">
      {/* Assign role form */}
      {showForm ? (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">Assign Role</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="user@company.com"
                className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Role</label>
              <select
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as RoleOption }))}
                className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {ROLE_OPTIONS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              disabled={!form.email || assignMutation.isPending}
              onClick={() => assignMutation.mutate()}
              className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded font-medium transition-colors flex items-center gap-1.5"
            >
              {assignMutation.isPending && <Loader2 size={14} className="animate-spin" />}
              Assign Role
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2 rounded border border-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
          {assignMutation.isError && (
            <p className="text-xs text-red-500">{(assignMutation.error as Error).message}</p>
          )}
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 border border-blue-200 hover:border-blue-400 px-3 py-2 rounded transition-colors"
        >
          <Plus size={14} /> Assign Role
        </button>
      )}

      {/* Roles table */}
      {roles.length === 0 ? (
        <div className="text-sm text-gray-400 py-6 text-center">
          No role assignments yet. All users default to Viewer.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-200">
                <th className="text-left py-2 pr-4">Email</th>
                <th className="text-left py-2 pr-4">Role</th>
                <th className="text-left py-2 pr-4">Granted By</th>
                <th className="text-left py-2">Granted At</th>
              </tr>
            </thead>
            <tbody>
              {roles.map(r => (
                <tr key={r.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 pr-4 font-medium text-gray-800">{r.email}</td>
                  <td className="py-2 pr-4"><RoleBadge role={r.role} /></td>
                  <td className="py-2 pr-4 text-gray-500">{r.granted_by}</td>
                  <td className="py-2 text-gray-400 text-xs">{formatDate(r.granted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type Tab = 'api-keys' | 'user-roles'

export default function AccessControl() {
  const [activeTab, setActiveTab] = useState<Tab>('api-keys')
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-400 py-12">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    )
  }

  // Non-admin users see a notice; the API will enforce 403 anyway
  const isAdmin = !user || user.role === 'admin'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-50 rounded-lg">
          <ShieldCheck size={20} className="text-blue-600" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Access Control</h2>
          <p className="text-sm text-gray-500">Manage API keys and user roles for this solution.</p>
        </div>
      </div>

      {!isAdmin && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-start gap-2">
          <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800">
            You have the <strong>{user?.role}</strong> role. Contact your administrator to manage API keys or assign roles.
          </p>
        </div>
      )}

      {/* Current user card */}
      {user && (
        <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 flex items-center gap-4">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-sm">
            {(user.name?.[0] ?? user.email?.[0] ?? '?').toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-gray-800 truncate">{user.name || user.email}</div>
            <div className="text-xs text-gray-400 truncate">{user.email} · via {user.provider}</div>
          </div>
          <RoleBadge role={user.role} />
        </div>
      )}

      {/* Role hierarchy reference */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Role Hierarchy</p>
        <div className="flex flex-wrap gap-2 text-xs text-gray-600">
          <span><RoleBadge role="viewer" /> — read only</span>
          <span className="text-gray-300">→</span>
          <span><RoleBadge role="operator" /> — submit tasks</span>
          <span className="text-gray-300">→</span>
          <span><RoleBadge role="approver" /> — approve proposals</span>
          <span className="text-gray-300">→</span>
          <span><RoleBadge role="admin" /> — full access</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('api-keys')}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors ${
              activeTab === 'api-keys'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/50'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Key size={15} />
            API Keys
          </button>
          <button
            onClick={() => setActiveTab('user-roles')}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors ${
              activeTab === 'user-roles'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/50'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Users size={15} />
            User Roles
          </button>
        </div>

        <div className="p-5">
          {activeTab === 'api-keys'   && <ApiKeysTab />}
          {activeTab === 'user-roles' && <UserRolesTab />}
        </div>
      </div>
    </div>
  )
}
