import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Wrench, RefreshCw, Eye, EyeOff, Play, Server,
  ChevronRight, Package, Plug, Settings,
} from 'lucide-react'
import {
  fetchSkills, reloadSkills, setSkillVisibility,
  fetchMCPTools, invokeMCPTool, fetchRunners,
} from '../api/client'

type Tab = 'skills' | 'mcp' | 'runners'

export default function SkillsTools() {
  const [tab, setTab] = useState<Tab>('skills')
  const [mcpTool, setMcpTool] = useState('')
  const [mcpArgs, setMcpArgs] = useState('{}')
  const queryClient = useQueryClient()

  const { data: skills } = useQuery({ queryKey: ['skills'], queryFn: fetchSkills, retry: false })
  const { data: mcpTools } = useQuery({ queryKey: ['mcp-tools'], queryFn: fetchMCPTools, retry: false })
  const { data: runners } = useQuery({ queryKey: ['runners'], queryFn: fetchRunners, retry: false })

  const reloadMutation = useMutation({
    mutationFn: reloadSkills,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['skills'] }),
  })

  const visibilityMutation = useMutation({
    mutationFn: (params: { name: string; visibility: string }) =>
      setSkillVisibility(params.name, params.visibility),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['skills'] }),
  })

  const invokeMutation = useMutation({
    mutationFn: () => {
      try {
        const args = JSON.parse(mcpArgs)
        return invokeMCPTool(mcpTool, args)
      } catch {
        return Promise.reject(new Error('Invalid JSON in arguments'))
      }
    },
  })

  const tabs: { id: Tab; label: string; icon: typeof Wrench }[] = [
    { id: 'skills', label: 'Skills', icon: Package },
    { id: 'mcp', label: 'MCP Tools', icon: Plug },
    { id: 'runners', label: 'Runners', icon: Server },
  ]

  const skillList = Array.isArray(skills?.skills) ? skills.skills : Array.isArray(skills) ? skills : []
  const toolList = Array.isArray(mcpTools?.tools) ? mcpTools.tools : Array.isArray(mcpTools) ? mcpTools : []
  const runnerList = Array.isArray(runners?.runners) ? runners.runners : Array.isArray(runners) ? runners : []

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7' }}>
            <Wrench size={18} className="inline mr-2" style={{ color: '#f59e0b' }} />
            Skills & Tools
          </h1>
          <p className="text-xs mt-1" style={{ color: '#9ca3af' }}>
            Manage skill registry, browse MCP tools, view domain runners
          </p>
        </div>
      </div>

      <div className="sage-tabs">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`sage-tab ${tab === t.id ? 'sage-tab-active' : ''}`}>
            <t.icon size={12} className="inline mr-1.5" />{t.label}
          </button>
        ))}
      </div>

      {/* Skills */}
      {tab === 'skills' && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <button onClick={() => reloadMutation.mutate()} disabled={reloadMutation.isPending} className="sage-btn sage-btn-secondary">
              <RefreshCw size={12} /> {reloadMutation.isPending ? 'Reloading...' : 'Reload Skills'}
            </button>
            <span className="text-xs" style={{ color: '#9ca3af' }}>{skillList.length} skills registered</span>
          </div>
          {skillList.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {skillList.map((skill: any) => (
                <div key={skill.name ?? skill.id} className="sage-card flex items-start gap-3" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '0.75rem 1rem' }}>
                  <Package size={14} style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium" style={{ color: '#e4e4e7' }}>{skill.name ?? skill.id}</span>
                      <span className="sage-tag" style={{
                        background: skill.visibility === 'public' ? 'rgba(34,197,94,0.1)' : skill.visibility === 'disabled' ? 'rgba(239,68,68,0.1)' : 'rgba(139,92,246,0.1)',
                        color: skill.visibility === 'public' ? '#22c55e' : skill.visibility === 'disabled' ? '#ef4444' : '#a78bfa',
                        fontSize: '10px',
                      }}>
                        {skill.visibility ?? 'public'}
                      </span>
                    </div>
                    <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>{skill.description ?? '—'}</p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => visibilityMutation.mutate({ name: skill.name ?? skill.id, visibility: skill.visibility === 'disabled' ? 'public' : 'disabled' })}
                      style={{ color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}
                      title={skill.visibility === 'disabled' ? 'Enable' : 'Disable'}
                    >
                      {skill.visibility === 'disabled' ? <Eye size={12} /> : <EyeOff size={12} />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="sage-empty">
              <Package size={32} />
              <p className="text-sm">No skills registered. Check solution YAML configuration.</p>
            </div>
          )}
        </div>
      )}

      {/* MCP Tools */}
      {tab === 'mcp' && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
            {toolList.length > 0 ? toolList.map((tool: any) => (
              <div key={tool.name ?? tool.id} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '0.75rem 1rem' }}>
                <div className="flex items-center gap-2 mb-1">
                  <Plug size={12} style={{ color: '#3b82f6' }} />
                  <span className="text-sm font-medium" style={{ color: '#e4e4e7' }}>{tool.name}</span>
                </div>
                <p className="text-xs" style={{ color: '#9ca3af' }}>{tool.description ?? '—'}</p>
                {tool.input_schema && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {Object.keys(tool.input_schema?.properties ?? {}).map(k => (
                      <span key={k} className="sage-tag" style={{ fontSize: '10px', background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>{k}</span>
                    ))}
                  </div>
                )}
              </div>
            )) : (
              <div className="sage-empty col-span-2">
                <Plug size={32} />
                <p className="text-sm">No MCP tools available. Configure MCP servers in settings.</p>
              </div>
            )}
          </div>

          {/* Invoke Tool */}
          <div className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
              <Play size={12} className="inline mr-1.5" style={{ color: '#f97316' }} />
              Invoke Tool
            </h3>
            <div className="space-y-2">
              <input
                value={mcpTool}
                onChange={e => setMcpTool(e.target.value)}
                placeholder="Tool name"
                className="w-full text-sm px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #e5e7eb', borderRadius: 8, outline: 'none' }}
              />
              <textarea
                value={mcpArgs}
                onChange={e => setMcpArgs(e.target.value)}
                rows={3}
                placeholder='{"arg": "value"}'
                className="w-full text-xs font-mono px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #e5e7eb', borderRadius: 8, outline: 'none', resize: 'vertical' }}
              />
              <button
                onClick={() => invokeMutation.mutate()}
                disabled={!mcpTool || invokeMutation.isPending}
                className="sage-btn sage-btn-primary"
              >
                <Play size={12} /> {invokeMutation.isPending ? 'Running...' : 'Invoke'}
              </button>
              {invokeMutation.isSuccess && (
                <pre className="text-xs p-3 overflow-auto" style={{ background: '#111113', color: '#6b7280', borderRadius: 6, maxHeight: 200 }}>
                  {JSON.stringify(invokeMutation.data, null, 2)}
                </pre>
              )}
              {invokeMutation.isError && (
                <div className="text-xs p-2" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', borderRadius: 6 }}>
                  {(invokeMutation.error as Error).message}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Runners */}
      {tab === 'runners' && (
        <div>
          {runnerList.length > 0 ? (
            <div className="space-y-2">
              {runnerList.map((runner: any) => (
                <div key={runner.name ?? runner.id} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Server size={14} style={{ color: '#a78bfa' }} />
                    <span className="text-sm font-semibold" style={{ color: '#e4e4e7' }}>{runner.name}</span>
                    {runner.docker_image && (
                      <span className="sage-tag" style={{ fontSize: '10px', background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>
                        {runner.docker_image}
                      </span>
                    )}
                  </div>
                  {runner.roles?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-1">
                      {runner.roles.map((r: string) => (
                        <span key={r} className="sage-tag">{r}</span>
                      ))}
                    </div>
                  )}
                  {runner.tools?.length > 0 && (
                    <p className="text-xs" style={{ color: '#9ca3af' }}>
                      Tools: {runner.tools.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="sage-empty">
              <Server size={32} />
              <p className="text-sm">No runners registered.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
