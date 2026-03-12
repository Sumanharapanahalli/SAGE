import { useState, useCallback, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Editor from '@monaco-editor/react'
import { fetchYamlFile, saveYamlFile } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'

type YamlFile = 'project' | 'prompts' | 'tasks'

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

export default function YamlEditor() {
  const queryClient = useQueryClient()
  const { data: projectData } = useProjectConfig()
  const solutionName = projectData?.project ?? '…'

  const [activeFile, setActiveFile] = useState<YamlFile>('project')
  const [editorContent, setEditorContent] = useState<string>('')
  const [isDirty, setIsDirty] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [savedBanner, setSavedBanner] = useState(false)

  // Load YAML from backend
  const { data: yamlData, isLoading, isError, error } = useQuery({
    queryKey: ['yaml', activeFile, solutionName],
    queryFn: () => fetchYamlFile(activeFile),
    enabled: !!solutionName && solutionName !== '…',
    staleTime: Infinity,   // don't refetch unless we explicitly invalidate
  })

  // Sync editor content when data loads / file tab changes
  useEffect(() => {
    if (yamlData) {
      setEditorContent(yamlData.content)
      setIsDirty(false)
      setSaveError('')
    }
  }, [yamlData])

  const saveMutation = useMutation({
    mutationFn: (content: string) => saveYamlFile(activeFile, content),
    onSuccess: () => {
      setSaveError('')
      setIsDirty(false)
      setSavedBanner(true)
      setTimeout(() => setSavedBanner(false), 2500)
      // Reload project config so sidebar/header reflect YAML changes
      queryClient.invalidateQueries({ queryKey: ['project-config'] })
      queryClient.invalidateQueries({ queryKey: ['yaml', activeFile, solutionName] })
    },
    onError: (e: Error) => setSaveError(e.message),
  })

  const handleEditorChange = useCallback((value: string | undefined) => {
    setEditorContent(value ?? '')
    setIsDirty(true)
    setSaveError('')
  }, [])

  const handleTabChange = (file: YamlFile) => {
    if (isDirty) {
      if (!window.confirm('You have unsaved changes. Discard and switch file?')) return
    }
    setActiveFile(file)
    setIsDirty(false)
    setSaveError('')
  }

  const handleSave = () => {
    saveMutation.mutate(editorContent)
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
              Saved & reloaded ✓
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={!isDirty || saveMutation.isPending}
            className="px-4 py-2 bg-gray-900 hover:bg-gray-700 disabled:opacity-40
                       text-white text-sm font-medium rounded-lg transition-colors"
          >
            {saveMutation.isPending ? 'Saving…' : 'Save & Reload'}
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
              activeFile === file
                ? 'border-gray-900 text-gray-900 bg-white'
                : 'border-transparent text-gray-400 hover:text-gray-600 hover:bg-gray-50'
            }`}
          >
            {FILE_META[file].label}
          </button>
        ))}
      </div>

      {/* Description */}
      <div className="bg-gray-50 border border-gray-200 border-t-0 rounded-b-lg px-4 py-2 mb-3">
        <p className="text-xs text-gray-500">{FILE_META[activeFile].description}</p>
      </div>

      {/* Error banner */}
      {saveError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 mb-3">
          <p className="text-sm text-red-700"><strong>Save failed:</strong> {saveError}</p>
        </div>
      )}

      {/* Editor area */}
      <div className="flex-1 rounded-xl border border-gray-200 overflow-hidden" style={{ minHeight: '520px' }}>
        {isLoading && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Loading {FILE_META[activeFile].label}…
          </div>
        )}
        {isError && (
          <div className="flex items-center justify-center h-full text-red-500 text-sm">
            Could not load file: {(error as Error)?.message}
          </div>
        )}
        {!isLoading && !isError && (
          <Editor
            height="100%"
            defaultLanguage="yaml"
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
        YAML is validated server-side before saving &nbsp;·&nbsp;
        Proprietary solution files are never committed to the SAGE repo.
      </p>
    </div>
  )
}
