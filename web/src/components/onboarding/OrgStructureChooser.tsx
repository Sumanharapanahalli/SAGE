import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, Check } from 'lucide-react'
import { fetchOrgTemplates, type OrgTemplate, type OrgTemplateRole } from '../../api/client'

// ---------------------------------------------------------------------------
// Individual template card
// ---------------------------------------------------------------------------

interface TemplateCardProps {
  template: OrgTemplate
  selected: boolean
  enabledRoles: Set<string>
  onSelect: (id: string) => void
  onToggleRole: (templateId: string, roleKey: string) => void
}

function TemplateCard({ template, selected, enabledRoles, onSelect, onToggleRole }: TemplateCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      style={{
        backgroundColor: selected ? '#27272a' : '#18181b',
        border: selected ? '1px solid #3f3f46' : '1px solid #27272a',
        borderLeft: selected ? '4px solid #22c55e' : '4px solid transparent',
      }}
    >
      {/* Card header */}
      <div className="p-4 space-y-2">
        {/* Icon + name row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="text-2xl leading-none mt-0.5">{template.icon}</span>
            <div>
              <div className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>
                {template.name}
              </div>
              <div className="text-xs mt-0.5" style={{ color: '#71717a' }}>
                {template.role_count} roles
              </div>
            </div>
          </div>
          {selected && (
            <Check size={16} style={{ color: '#22c55e', flexShrink: 0 }} />
          )}
        </div>

        {/* Description */}
        <p className="text-xs leading-relaxed" style={{ color: '#a1a1aa' }}>
          {template.description}
        </p>

        {/* Compliance badges */}
        {template.compliance_standards.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {template.compliance_standards.map(std => (
              <span
                key={std}
                className="text-xs px-1.5 py-0.5 font-mono"
                style={{ backgroundColor: '#09090b', color: '#71717a', border: '1px solid #27272a' }}
              >
                {std}
              </span>
            ))}
          </div>
        )}

        {/* Action row */}
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => onSelect(template.id)}
            className="flex-1 text-xs font-medium py-1.5 transition-colors"
            style={
              selected
                ? { backgroundColor: '#14532d', color: '#22c55e', border: '1px solid #166534' }
                : { backgroundColor: '#3f3f46', color: '#f4f4f5', border: '1px solid #52525b' }
            }
          >
            {selected ? 'Selected' : 'Select this team'}
          </button>
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex items-center gap-1 text-xs py-1.5 px-2 transition-colors"
            style={{ backgroundColor: '#27272a', color: '#71717a', border: '1px solid #3f3f46' }}
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Hide roles' : 'View roles'}
          </button>
        </div>
      </div>

      {/* Expanded role list */}
      {expanded && (
        <div style={{ borderTop: '1px solid #27272a' }}>
          <div
            className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider"
            style={{ color: '#52525b', backgroundColor: '#09090b' }}
          >
            Roles
          </div>
          {template.roles.map((role: OrgTemplateRole) => {
            const isEnabled = enabledRoles.has(role.key)
            return (
              <div
                key={role.key}
                className="flex items-start gap-3 px-3 py-2"
                style={{ borderTop: '1px solid #27272a' }}
              >
                {selected && (
                  <button
                    onClick={() => onToggleRole(template.id, role.key)}
                    className="mt-0.5 shrink-0 w-4 h-4 flex items-center justify-center transition-colors"
                    style={
                      isEnabled
                        ? { backgroundColor: '#14532d', border: '1px solid #166534' }
                        : { backgroundColor: '#27272a', border: '1px solid #3f3f46' }
                    }
                    title={isEnabled ? 'Click to disable' : 'Click to enable'}
                  >
                    {isEnabled && <Check size={10} style={{ color: '#22c55e' }} />}
                  </button>
                )}
                <div className={selected ? '' : 'ml-0'}>
                  <div className="text-xs font-medium" style={{ color: '#e4e4e7' }}>
                    {role.name}
                  </div>
                  <div className="text-xs" style={{ color: '#52525b' }}>
                    {role.description}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// OrgStructureChooser
// ---------------------------------------------------------------------------

export interface OrgChoice {
  templateId: string
  enabledRoles: string[]
}

interface OrgStructureChooserProps {
  /** Pre-selected template ID (matched from domain analysis) */
  preselectedId?: string
  onChange: (choice: OrgChoice | null) => void
}

export default function OrgStructureChooser({ preselectedId, onChange }: OrgStructureChooserProps) {
  const { data: templates = [], isLoading, isError } = useQuery({
    queryKey: ['org-templates'],
    queryFn: fetchOrgTemplates,
    staleTime: 60_000,
  })

  // Track which template is selected
  const [selectedId, setSelectedId] = useState<string | null>(preselectedId ?? null)

  // Track per-template enabled role sets (default: all enabled)
  const [roleOverrides, setRoleOverrides] = useState<Record<string, Set<string>>>({})

  const getEnabledRoles = (template: OrgTemplate): Set<string> => {
    if (roleOverrides[template.id]) return roleOverrides[template.id]
    // Default: all roles enabled
    return new Set(template.roles.map(r => r.key))
  }

  const handleSelect = (id: string) => {
    const next = selectedId === id ? null : id
    setSelectedId(next)
    if (!next) {
      onChange(null)
      return
    }
    const template = templates.find(t => t.id === id)
    if (!template) return
    const enabled = getEnabledRoles(template)
    onChange({ templateId: id, enabledRoles: Array.from(enabled) })
  }

  const handleToggleRole = (templateId: string, roleKey: string) => {
    const template = templates.find(t => t.id === templateId)
    if (!template) return
    const current = getEnabledRoles(template)
    const updated = new Set(current)
    if (updated.has(roleKey)) {
      updated.delete(roleKey)
    } else {
      updated.add(roleKey)
    }
    setRoleOverrides(prev => ({ ...prev, [templateId]: updated }))
    if (selectedId === templateId) {
      onChange({ templateId, enabledRoles: Array.from(updated) })
    }
  }

  if (isLoading) {
    return (
      <div className="py-8 text-center text-sm" style={{ color: '#52525b' }}>
        Loading team templates…
      </div>
    )
  }

  if (isError || templates.length === 0) {
    return (
      <div className="py-4 text-sm" style={{ color: '#71717a' }}>
        Could not load team templates. You can still proceed — roles will be generated from your description.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>
          Choose your agent team
        </p>
        <p className="text-xs mt-0.5" style={{ color: '#71717a' }}>
          Pick a pre-built structure that matches your domain, or skip to let SAGE generate roles from your description.
        </p>
      </div>

      {/* Template grid */}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}
      >
        {templates.map(template => (
          <TemplateCard
            key={template.id}
            template={template}
            selected={selectedId === template.id}
            enabledRoles={getEnabledRoles(template)}
            onSelect={handleSelect}
            onToggleRole={handleToggleRole}
          />
        ))}
      </div>

      {selectedId && (
        <div
          className="text-xs px-3 py-2"
          style={{ backgroundColor: '#14532d22', color: '#22c55e', border: '1px solid #166534' }}
        >
          {(() => {
            const t = templates.find(t => t.id === selectedId)
            if (!t) return null
            const count = getEnabledRoles(t).size
            return `${t.name} selected — ${count} of ${t.role_count} roles enabled`
          })()}
        </div>
      )}
    </div>
  )
}
