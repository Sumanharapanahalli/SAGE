import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Dumbbell, Play, Trophy, BookOpen, BarChart3, Clock,
  ChevronRight, RefreshCw, Zap, Star, Filter,
} from 'lucide-react'
import {
  fetchGymRatings, fetchGymCatalog, fetchGymHistory,
  fetchGymLeaderboard, trainAgent, trainAgentBatch,
} from '../api/client'

type Tab = 'leaderboard' | 'catalog' | 'train' | 'history'

export default function AgentGym() {
  const [tab, setTab] = useState<Tab>('leaderboard')
  const [selectedRole, setSelectedRole] = useState('')
  const [difficulty, setDifficulty] = useState('intermediate')
  const queryClient = useQueryClient()

  const { data: ratings } = useQuery({ queryKey: ['gym-ratings'], queryFn: fetchGymRatings, retry: false })
  const { data: catalog } = useQuery({ queryKey: ['gym-catalog'], queryFn: fetchGymCatalog, retry: false })
  const { data: leaderboard } = useQuery({ queryKey: ['gym-leaderboard'], queryFn: fetchGymLeaderboard, retry: false })
  const { data: history } = useQuery({
    queryKey: ['gym-history', selectedRole],
    queryFn: () => fetchGymHistory(selectedRole || undefined, 50),
    retry: false,
  })

  const trainMutation = useMutation({
    mutationFn: (params: { role: string; difficulty: string }) => trainAgent({ role: params.role, difficulty: params.difficulty }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gym-ratings'] })
      queryClient.invalidateQueries({ queryKey: ['gym-history'] })
      queryClient.invalidateQueries({ queryKey: ['gym-leaderboard'] })
    },
  })

  const batchMutation = useMutation({
    mutationFn: (params: { role: string; count: number; difficulty: string }) =>
      trainAgentBatch({ role: params.role, count: params.count, difficulty: params.difficulty }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gym-ratings'] })
      queryClient.invalidateQueries({ queryKey: ['gym-history'] })
    },
  })

  const tabs: { id: Tab; label: string; icon: typeof Trophy }[] = [
    { id: 'leaderboard', label: 'Leaderboard', icon: Trophy },
    { id: 'catalog', label: 'Exercise Catalog', icon: BookOpen },
    { id: 'train', label: 'Train', icon: Play },
    { id: 'history', label: 'History', icon: Clock },
  ]

  const roles = ratings?.roles ?? catalog?.roles ?? []

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7' }}>
            <Dumbbell size={18} className="inline mr-2" style={{ color: '#a78bfa' }} />
            Agent Gym
          </h1>
          <p className="text-xs mt-1" style={{ color: '#71717a' }}>
            Train agents through exercises, track Glicko-2 ratings, browse curriculum
          </p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['gym-ratings'] })}
          className="sage-btn sage-btn-secondary"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="sage-tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`sage-tab ${tab === t.id ? 'sage-tab-active' : ''}`}
          >
            <t.icon size={12} className="inline mr-1.5" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Leaderboard */}
      {tab === 'leaderboard' && (
        <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
            <Trophy size={14} className="inline mr-1.5" style={{ color: '#f59e0b' }} />
            Agent Ratings
          </h2>
          {leaderboard?.entries?.length > 0 ? (
            <table className="sage-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Agent Role</th>
                  <th>Rating</th>
                  <th>RD</th>
                  <th>Wins</th>
                  <th>Losses</th>
                  <th>Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {(leaderboard.entries ?? []).map((entry: any, i: number) => (
                  <tr key={entry.role}>
                    <td style={{ color: i < 3 ? '#f59e0b' : '#71717a', fontWeight: i < 3 ? 600 : 400 }}>
                      {i + 1}
                    </td>
                    <td style={{ color: '#e4e4e7', fontWeight: 500 }}>{entry.role}</td>
                    <td>
                      <span className="sage-tag" style={{ background: 'rgba(139,92,246,0.15)', color: '#a78bfa' }}>
                        {Math.round(entry.rating ?? 1500)}
                      </span>
                    </td>
                    <td style={{ color: '#71717a' }}>{Math.round(entry.rd ?? 350)}</td>
                    <td style={{ color: '#22c55e' }}>{entry.wins ?? 0}</td>
                    <td style={{ color: '#ef4444' }}>{entry.losses ?? 0}</td>
                    <td style={{ color: '#e4e4e7' }}>
                      {entry.wins + entry.losses > 0
                        ? `${Math.round((entry.wins / (entry.wins + entry.losses)) * 100)}%`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="sage-empty">
              <BarChart3 size={32} />
              <p className="text-sm">No ratings yet. Train agents to see their performance.</p>
            </div>
          )}
        </div>
      )}

      {/* Exercise Catalog */}
      {tab === 'catalog' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Filter size={12} style={{ color: '#71717a' }} />
              <select
                value={difficulty}
                onChange={e => setDifficulty(e.target.value)}
                className="text-xs px-2 py-1"
                style={{ background: '#1c1c1e', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 6 }}
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
          </div>
          {catalog?.exercises?.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(catalog.exercises ?? []).map((ex: any) => (
                <div key={ex.id} className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <span className="text-xs font-mono" style={{ color: '#71717a' }}>{ex.id}</span>
                      <h3 className="text-sm font-medium mt-0.5" style={{ color: '#e4e4e7' }}>{ex.role}</h3>
                    </div>
                    <span className="sage-tag">{ex.difficulty}</span>
                  </div>
                  <p className="text-xs mb-2" style={{ color: '#a1a1aa' }}>{ex.description}</p>
                  {ex.tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {ex.tags.map((tag: string) => (
                        <span key={tag} className="sage-tag" style={{ background: 'rgba(59,130,246,0.1)', color: '#60a5fa', fontSize: '10px' }}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="sage-empty">
              <BookOpen size={32} />
              <p className="text-sm">No exercises found. Check runner configuration.</p>
            </div>
          )}
        </div>
      )}

      {/* Train */}
      {tab === 'train' && (
        <div className="max-w-lg">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: '#e4e4e7' }}>
              <Zap size={14} className="inline mr-1.5" style={{ color: '#f59e0b' }} />
              Train an Agent
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Agent Role</label>
                <input
                  value={selectedRole}
                  onChange={e => setSelectedRole(e.target.value)}
                  placeholder="e.g. developer, analyst, firmware_engineer"
                  className="w-full text-sm px-3 py-2"
                  style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Difficulty</label>
                <select
                  value={difficulty}
                  onChange={e => setDifficulty(e.target.value)}
                  className="w-full text-sm px-3 py-2"
                  style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => selectedRole && trainMutation.mutate({ role: selectedRole, difficulty })}
                  disabled={!selectedRole || trainMutation.isPending}
                  className="sage-btn sage-btn-primary"
                >
                  <Play size={12} />
                  {trainMutation.isPending ? 'Training...' : 'Train Once'}
                </button>
                <button
                  onClick={() => selectedRole && batchMutation.mutate({ role: selectedRole, count: 5, difficulty })}
                  disabled={!selectedRole || batchMutation.isPending}
                  className="sage-btn sage-btn-secondary"
                >
                  <Star size={12} />
                  {batchMutation.isPending ? 'Running...' : 'Batch (5x)'}
                </button>
              </div>
              {trainMutation.isSuccess && (
                <div className="text-xs p-2 mt-2" style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', borderRadius: 6 }}>
                  Training complete. Check leaderboard for updated ratings.
                </div>
              )}
              {trainMutation.isError && (
                <div className="text-xs p-2 mt-2" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', borderRadius: 6 }}>
                  {(trainMutation.error as Error).message}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* History */}
      {tab === 'history' && (
        <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
            <Clock size={14} className="inline mr-1.5" style={{ color: '#6366f1' }} />
            Training History
          </h2>
          {history?.sessions?.length > 0 ? (
            <table className="sage-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Role</th>
                  <th>Exercise</th>
                  <th>Score</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {(history.sessions ?? []).map((s: any, i: number) => (
                  <tr key={i}>
                    <td style={{ color: '#71717a', fontSize: '11px' }}>{s.timestamp ?? '—'}</td>
                    <td style={{ color: '#e4e4e7' }}>{s.role}</td>
                    <td style={{ color: '#a1a1aa' }}>{s.exercise_id ?? '—'}</td>
                    <td>
                      <span className="sage-tag">{Math.round(s.score ?? 0)}%</span>
                    </td>
                    <td style={{ color: s.passed ? '#22c55e' : '#ef4444' }}>
                      {s.passed ? 'Pass' : 'Fail'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="sage-empty">
              <Clock size={32} />
              <p className="text-sm">No training sessions recorded yet.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
