import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Brain, Search, Plus, Trash2, RefreshCw,
  FileText, ChevronRight, AlertCircle,
} from 'lucide-react'
import {
  fetchKnowledgeEntries, searchKnowledge,
  deleteKnowledgeEntry, addKnowledge,
} from '../api/client'

type Tab = 'browse' | 'search' | 'add'

export default function KnowledgeBrowser() {
  const [tab, setTab] = useState<Tab>('browse')
  const [searchQuery, setSearchQuery] = useState('')
  const [newContent, setNewContent] = useState('')
  const [newMetaKey, setNewMetaKey] = useState('')
  const [newMetaVal, setNewMetaVal] = useState('')
  const queryClient = useQueryClient()

  const { data: entries, isLoading, isError } = useQuery({
    queryKey: ['knowledge-entries'],
    queryFn: () => fetchKnowledgeEntries(100),
    retry: false,
  })

  const searchMutation = useMutation({
    mutationFn: (query: string) => searchKnowledge(query, 20),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteKnowledgeEntry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-entries'] }),
  })

  const addMutation = useMutation({
    mutationFn: () => {
      const metadata: Record<string, string> = {}
      if (newMetaKey && newMetaVal) metadata[newMetaKey] = newMetaVal
      return addKnowledge(newContent, Object.keys(metadata).length > 0 ? metadata : undefined)
    },
    onSuccess: () => {
      setNewContent('')
      setNewMetaKey('')
      setNewMetaVal('')
      queryClient.invalidateQueries({ queryKey: ['knowledge-entries'] })
    },
  })

  const handleSearch = () => {
    if (searchQuery.trim()) searchMutation.mutate(searchQuery)
  }

  const tabs: { id: Tab; label: string; icon: typeof Brain }[] = [
    { id: 'browse', label: 'Browse', icon: FileText },
    { id: 'search', label: 'Search', icon: Search },
    { id: 'add', label: 'Add Entry', icon: Plus },
  ]

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7' }}>
            <Brain size={18} className="inline mr-2" style={{ color: '#10b981' }} />
            Knowledge Base
          </h1>
          <p className="text-xs mt-1" style={{ color: '#71717a' }}>
            Search, browse, and manage vector knowledge base entries
          </p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['knowledge-entries'] })}
          className="sage-btn sage-btn-secondary"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      <div className="sage-tabs">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`sage-tab ${tab === t.id ? 'sage-tab-active' : ''}`}>
            <t.icon size={12} className="inline mr-1.5" />{t.label}
          </button>
        ))}
      </div>

      {/* Browse */}
      {tab === 'browse' && (
        <div className="space-y-2">
          {isLoading && <p className="text-xs" style={{ color: '#71717a' }}>Loading entries...</p>}
          {isError && (
            <div className="sage-card flex items-center gap-2" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
              <AlertCircle size={14} style={{ color: '#f59e0b' }} />
              <span className="text-xs" style={{ color: '#a1a1aa' }}>
                Knowledge base not available. Ensure ChromaDB is running.
              </span>
            </div>
          )}
          {entries?.entries?.length > 0 ? (
            entries.entries.map((entry: any, i: number) => (
              <div key={entry.id ?? i} className="sage-card flex items-start gap-3" style={{ background: '#1c1c1e', borderColor: '#2a2a2e', padding: '0.75rem 1rem' }}>
                <FileText size={14} style={{ color: '#52525b', flexShrink: 0, marginTop: 2 }} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs truncate" style={{ color: '#e4e4e7' }}>
                    {typeof entry.content === 'string' ? entry.content.slice(0, 200) : JSON.stringify(entry).slice(0, 200)}
                  </p>
                  {entry.metadata && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {Object.entries(entry.metadata).slice(0, 4).map(([k, v]) => (
                        <span key={k} className="sage-tag" style={{ fontSize: '10px', background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>
                          {k}: {String(v).slice(0, 30)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => entry.id && deleteMutation.mutate(entry.id)}
                  className="shrink-0"
                  style={{ color: '#71717a', background: 'none', border: 'none', cursor: 'pointer' }}
                  title="Delete entry"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          ) : !isLoading && !isError && (
            <div className="sage-empty">
              <Brain size={32} />
              <p className="text-sm">Knowledge base is empty. Add entries or sync from integrations.</p>
            </div>
          )}
          {entries?.total != null && (
            <p className="text-xs mt-2" style={{ color: '#52525b' }}>
              Showing {entries.entries?.length ?? 0} of {entries.total} entries
            </p>
          )}
        </div>
      )}

      {/* Search */}
      {tab === 'search' && (
        <div>
          <div className="flex gap-2 mb-4">
            <div className="flex-1 relative">
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#52525b' }} />
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Search knowledge base..."
                className="w-full text-sm pl-8 pr-3 py-2"
                style={{ background: '#1c1c1e', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none' }}
              />
            </div>
            <button onClick={handleSearch} disabled={!searchQuery.trim() || searchMutation.isPending} className="sage-btn sage-btn-primary">
              {searchMutation.isPending ? 'Searching...' : 'Search'}
            </button>
          </div>

          {searchMutation.isSuccess && searchMutation.data?.results?.length > 0 ? (
            <div className="space-y-2">
              {searchMutation.data.results.map((r: any, i: number) => (
                <div key={i} className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e', padding: '0.75rem 1rem' }}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="sage-tag">{Math.round((r.score ?? r.similarity ?? 0) * 100)}% match</span>
                  </div>
                  <p className="text-xs" style={{ color: '#e4e4e7' }}>
                    {typeof r.content === 'string' ? r.content.slice(0, 300) : JSON.stringify(r).slice(0, 300)}
                  </p>
                </div>
              ))}
            </div>
          ) : searchMutation.isSuccess && (
            <div className="sage-empty">
              <Search size={32} />
              <p className="text-sm">No matching entries found.</p>
            </div>
          )}
        </div>
      )}

      {/* Add Entry */}
      {tab === 'add' && (
        <div className="max-w-lg">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
              <Plus size={14} className="inline mr-1.5" style={{ color: '#10b981' }} />
              Add Knowledge Entry
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Content</label>
                <textarea
                  value={newContent}
                  onChange={e => setNewContent(e.target.value)}
                  rows={5}
                  placeholder="Enter knowledge content..."
                  className="w-full text-sm px-3 py-2"
                  style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none', resize: 'vertical' }}
                />
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Metadata Key</label>
                  <input value={newMetaKey} onChange={e => setNewMetaKey(e.target.value)} placeholder="e.g. source" className="w-full text-xs px-2 py-1.5" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 6, outline: 'none' }} />
                </div>
                <div className="flex-1">
                  <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Metadata Value</label>
                  <input value={newMetaVal} onChange={e => setNewMetaVal(e.target.value)} placeholder="e.g. user-feedback" className="w-full text-xs px-2 py-1.5" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 6, outline: 'none' }} />
                </div>
              </div>
              <button
                onClick={() => addMutation.mutate()}
                disabled={!newContent.trim() || addMutation.isPending}
                className="sage-btn sage-btn-primary"
              >
                <Plus size={12} /> {addMutation.isPending ? 'Adding...' : 'Add Entry'}
              </button>
              {addMutation.isSuccess && (
                <div className="text-xs p-2" style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', borderRadius: 6 }}>
                  Entry added successfully.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
