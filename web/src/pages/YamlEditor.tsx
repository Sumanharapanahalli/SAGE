import { useState, useCallback, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Editor from '@monaco-editor/react'
import { fetchYamlFile, saveYamlFile, fetchSkillMd, saveSkillMd } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'

type YamlFile = 'project' | 'prompts' | 'tasks'
type ActiveTab = YamlFile | 'skill'

const FILE_META: Record<YamlFile, { label: string; description: string }> = {
  project: {
    label: 'project.yaml',
    description: 'Solution metadata: name, domain, active_modules, integrations, compliance standards',
  },
  prompts: {
    label: 'prompts.yaml',
    description: 'Agent system prompts: analyst, developer, planner, monitor',
  },
  tasks: {
    label: 'tasks.yaml',
    description: 'Valid task types and their human-readable descriptions',
  },
}

const SKILL_META = {
  label: 'SKILL.md',
  description: 'Single-file solution config — YAML frontmatter for structured config + markdown body injected into every agent prompt as domain knowledge.',
}

export default function YamlEditor() {
  const queryClient = useQueryClient()
  const { data: projectData } = useProjectConfig()
  const solutionName = projectData?.project ?? '…'

  const [activeTab, setActiveTab] = useState<ActiveTab>('project')
  const [editorContent, setEditorContent] = useState<string>('')
  const [isDirty, setIsDirty] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [savedBanner, setSavedBanner] = useState(false)

  const isSkillTab = activeTab === 'skill'

  // Load YAML from backend (for project/prompts/tasks tabs)
  const { data: yamlData, isLoading: yamlLoading, isError: yamlError, error: yamlErrorObj } = useQuery({
    queryKey: ['yaml', activeTab, solutionName],
    queryFn: () => fetchYamlFile(activeTab as YamlFile),
    enabled: !isSkillTab && !!solutionName && solutionName !== '…',
    staleTime: Infinity,
  })

  // Load SKILL.md from backend
  const { data: skillData, isLoading: skillLoading, isError: skillError, error: skillErrorObj } = useQuery({
    queryKey: ['skill-md', solutionName],
    queryFn: fetchSkillMd,
    enabled: isSkillTab && !!solutionName && solutionName !== '…',
    staleTime: Infinity,
    retry: false,  // 404 is expected when solution doesn't have SKILL.md yet
  })

  const isLoading = isSkillTab ? skillLoading : yamlLoading
  const isError   = isSkillTab ? skillError   : yamlError
  const errorObj  = isSkillTab ? skillErrorObj : yamlErrorObj

  // Sync editor content when data loads / tab changes
  useEffect(() => {
    if (!isSkillTab && yamlData) {
      setEditorContent(yamlData.content)
      setIsDirty(false)
      setSaveError('')
    }
  }, [yamlData, isSkillTab])

  useEffect(() => {
    if (isSkillTab && skillData) {
      setEditorContent(skillData.content)
      setIsDirty(false)
      setSaveError('')
    }
  }, [skillData, isSkillTab])

  const yamlSaveMutation = useMutation({
    mutationFn: (content: string) => saveYamlFile(activeTab as YamlFile, content),
    onSuccess: () => {
      setSaveError('')
      setIsDirty(false)
      setSavedBanner(true)
      setTimeout(() => setSavedBanner(false), 2500)
      queryClient.invalidateQueries({ queryKey: ['project-config'] })
      queryClient.invalidateQueries({ queryKey: ['yaml', activeTab, solutionName] })
    },
    onError: (e: Error) => setSaveError(e.message),
  })

  const skillSaveMutation = useMutation({
    mutationFn: (content: string) => saveSkillMd(content),
    onSuccess: () => {
      setSaveError('')
      setIsDirty(false)
      setSavedBanner(true)
      setTimeout(() => setSavedBanner(false), 2500)
      queryClient.invalidateQueries({ queryKey: ['project-config'] })
      queryClient.invalidateQueries({ queryKey: ['skill-md', solutionName] })
    },
    onError: (e: Error) => setSaveError(e.message),
  })

  const saveMutation = isSkillTab ? skillSaveMutation : yamlSaveMutation
  const isSaving = saveMutation.isPending

  const handleEditorChange = useCallback((value: string | undefined) => {
    setEditorContent(value ?? '')
    setIsDirty(true)
    setSaveError('')
  }, [])

  const handleTabChange = (tab: ActiveTab) => {
    if (isDirty) {
      if (!window.confirm('You have unsaved changes. Discard and switch file?')) return
    }
    setActiveTab(tab)
    setIsDirty(false)
    setSaveError('')
    setEditorContent('')
  }

  const handleSave = () => {
    saveMutation.mutate(editorContent)
  }

  const editorLanguage = isSkillTab ? 'markdown' : 'yaml'

  const currentDescription = isSkillTab
    ? SKILL_META.description
    : FILE_META[activeTab as YamlFile].description

  // When SKILL.md 404s, show a "create" option
  const skillNotFound = isSkillTab && isError && (errorObj as Error)?.message?.includes('404')

  const handleCreateSkillMd = () => {
    const template = `---
name: "${solutionName}"
domain: "general"
version: "1.0.0"
modules:
  - dashboard
  - analyst
  - developer
  - monitor
  - audit
  - improvements
  - agents
  - llm
  - settings
  - yaml-editor
  - live-console

compliance_standards: []
integrations: []

ui_labels:
  analyst_page_title: "Signal Analyzer"
  developer_page_title: "Code Reviewer"
  monitor_page_title: "Operations Monitor"
  dashboard_subtitle: "Project Health Overview"

dashboard:
  badge_color: "bg-gray-100 text-gray-700"
  context_color: "border-gray-200 bg-gray-50"
  context_items:
    - label: "Domain"
      description: "Add your domain description here"
  quick_actions:
    - { label: "Analyze Signal", route: "/analyst",   description: "Triage an event or log" }
    - { label: "Review Code",    route: "/developer", description: "AI code review" }

tasks:
  - ANALYZE_LOG
  - REVIEW_CODE
  - PLAN_TASK

agent_roles:
  analyst:
    description: "Signal and event analysis"
    system_prompt: |
      You are a Senior Analyst for this project.
      Analyze the provided input carefully.
      Output your analysis in STRICT JSON format with keys:
        severity              : "RED" | "AMBER" | "GREEN" | "UNKNOWN"
        root_cause_hypothesis : string
        recommended_action    : string
      Do not output markdown or text outside the JSON object.

  developer:
    description: "Code review and merge request creation"
    system_prompt: |
      You are a Senior Software Engineer performing a code review.
      Review the provided diff carefully for bugs, security issues, and style violations.
      Return STRICT JSON with keys: summary, issues (list), suggestions (list), approved (bool).

  planner:
    description: "Task decomposition and planning"
    system_prompt: |
      You are a Planning Agent.
      Decompose the user's request into a sequence of atomic tasks.
      Return a JSON array only — no markdown.

  monitor:
    description: "Event classification and monitoring"
    system_prompt: |
      You are a Monitoring Agent.
      Classify incoming events by severity.
      Return STRICT JSON with keys: severity, requires_action (bool), summary.
---

## Domain overview

Describe your domain here. What does this solution do? What problems does it solve?

## Agent skills and context

Provide rich domain knowledge that will be injected into every agent prompt.
Include: key terminology, important workflows, common failure patterns.

## Known patterns

Document recurring issues, escalation rules, and domain-specific conventions here.
`
    setEditorContent(template)
    setIsDirty(true)
    setSaveError('')
  }

  return (
    <div className="flex flex-col h-full space-y-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Solution Config Editor</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Editing <strong className="text-gray-600">{solutionName}</strong> — changes are saved to disk and reloaded immediately.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isDirty && (
            <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-md border border-amber-200">
              Unsaved changes
            </span>
          )}
          {savedBanner && (
            <span className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded-md border border-green-200">
              Saved &amp; reloaded
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className="px-4 py-2 bg-gray-900 hover:bg-gray-700 disabled:opacity-40
                       text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isSaving ? 'Saving…' : 'Save & Reload'}
          </button>
        </div>
      </div>

      {/* File tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-0">
        {(Object.keys(FILE_META) as YamlFile[]).map(file => (
          <button
            key={file}
            onClick={() => handleTabChange(file)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
              activeTab === file
                ? 'border-gray-900 text-gray-900 bg-white'
                : 'border-transparent text-gray-400 hover:text-gray-600 hover:bg-gray-50'
            }`}
          >
            {FILE_META[file].label}
          </button>
        ))}
        {/* SKILL.md tab */}
        <button
          onClick={() => handleTabChange('skill')}
          className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
            activeTab === 'skill'
              ? 'border-indigo-600 text-indigo-700 bg-white'
              : 'border-transparent text-gray-400 hover:text-gray-600 hover:bg-gray-50'
          }`}
        >
          SKILL.md
          <span className="ml-1.5 text-xs bg-indigo-100 text-indigo-600 px-1.5 py-0.5 rounded-full font-medium">
            new
          </span>
        </button>
      </div>

      {/* Description */}
      <div className={`border border-t-0 rounded-b-lg px-4 py-2 mb-3 ${
        isSkillTab
          ? 'bg-indigo-50 border-indigo-200'
          : 'bg-gray-50 border-gray-200'
      }`}>
        <p className="text-xs text-gray-500">{currentDescription}</p>
      </div>

      {/* Error banner */}
      {saveError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 mb-3">
          <p className="text-sm text-red-700"><strong>Save failed:</strong> {saveError}</p>
        </div>
      )}

      {/* SKILL.md not found — offer to create */}
      {skillNotFound && !editorContent && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 mb-3 flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-indigo-800">SKILL.md not found for this solution</p>
            <p className="text-xs text-indigo-600 mt-0.5">
              This solution uses the legacy 3-file format (project.yaml + prompts.yaml + tasks.yaml).
              Click to create a SKILL.md template — the 3 YAML files will remain as fallback.
            </p>
          </div>
          <button
            onClick={handleCreateSkillMd}
            className="shrink-0 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded-lg transition-colors"
          >
            Create SKILL.md
          </button>
        </div>
      )}

      {/* Editor area */}
      <div className="flex-1 rounded-xl border border-gray-200 overflow-hidden" style={{ minHeight: '520px' }}>
        {isLoading && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Loading {isSkillTab ? 'SKILL.md' : FILE_META[activeTab as YamlFile].label}…
          </div>
        )}
        {isError && !skillNotFound && (
          <div className="flex items-center justify-center h-full text-red-500 text-sm">
            Could not load file: {(errorObj as Error)?.message}
          </div>
        )}
        {(!isLoading && (!isError || (skillNotFound && editorContent))) && (
          <Editor
            height="100%"
            defaultLanguage={editorLanguage}
            language={editorLanguage}
            value={editorContent}
            onChange={handleEditorChange}
            theme="vs-dark"
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              lineNumbers: 'on',
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              tabSize: 2,
              formatOnPaste: true,
              renderLineHighlight: 'line',
              smoothScrolling: true,
              padding: { top: 12, bottom: 12 },
            }}
          />
        )}
      </div>

      {/* Footer hint */}
      <p className="text-xs text-gray-400 mt-2">
        <kbd className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-500 font-mono">Ctrl+Z</kbd> to undo &nbsp;·&nbsp;
        {isSkillTab
          ? 'SKILL.md uses YAML frontmatter (between --- delimiters) + markdown body for agent context'
          : 'YAML is validated server-side before saving'} &nbsp;·&nbsp;
        Proprietary solution files are never committed to the SAGE repo.
      </p>
    </div>
  )
}
