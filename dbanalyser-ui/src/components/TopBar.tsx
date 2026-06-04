import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dbApi, runApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLocation } from 'react-router-dom'

interface Props {
  selectedDb:    string | null
  setSelectedDb: (v: string | null) => void
  selectedRun:   number | null
  setSelectedRun:(v: number | null) => void
}

export default function TopBar({ selectedDb, setSelectedDb, selectedRun, setSelectedRun }: Props) {
  const { user, logout } = useAuth()
  const qc = useQueryClient()
  const location = useLocation()

  // Hide DB/Run selectors on Dashboard (QW-2 UX improvement)
  const showSelectors = !location.pathname.includes('/dashboard')

  const { data: dbData } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data),
  })
  const dbs = dbData ?? []

  const { data: runData, isLoading: runsLoading } = useQuery({
    queryKey: ['runs', selectedDb],
    queryFn:  () => runApi.list(selectedDb ?? undefined).then(r => r.data.runs),
    staleTime: 30000, // 30 seconds
  })
  const runs = runData ?? []

  return (
    <header
      className="h-14 bg-surface-lowest flex items-center px-6 gap-4 flex-shrink-0"
      style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}
    >
      {/* DB selector — hidden on Dashboard (QW-2) */}
      {showSelectors && (
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 16 }}>storage</span>
          <select
            className="text-sm font-mono bg-surface-low rounded-lg px-3 py-1.5 text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20 min-w-36"
            value={selectedDb ?? ''}
            onChange={(e) => { setSelectedDb(e.target.value || null); setSelectedRun(null) }}
          >
            <option value="">All Databases</option>
            {dbs.map((db: any) => (
              <option key={db.id} value={db.name}>{db.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Run selector — hidden on Dashboard (QW-2) */}
      {showSelectors && (
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 16 }}>history</span>
          <select
            className="text-sm font-mono bg-surface-low rounded-lg px-3 py-1.5 text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20 min-w-52"
            value={selectedRun ?? ''}
            onChange={(e) => setSelectedRun(e.target.value ? Number(e.target.value) : null)}
            disabled={runsLoading}
          >
            <option value="">{runsLoading ? 'Loading runs...' : `Latest Run${runs.length > 0 ? ` (${runs.length} available)` : ''}`}</option>
            {runs.map((r: any) => (
              <option key={r.id} value={r.id}>
                {r.label || `Run #${r.id}`} — {new Date(r.timestamp).toLocaleDateString()}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex-1" />

      {/* Refresh */}
      <button
        className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-low transition-colors"
        title="Refresh data"
        onClick={() => qc.invalidateQueries()}
      >
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 18 }}>refresh</span>
      </button>

      {/* User pill */}
      <div className="flex items-center gap-2 bg-surface-low rounded-full px-3 py-1.5">
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-semibold"
          style={{ background: 'linear-gradient(135deg, #630ed4, #7c3aed)' }}
        >
          {(user?.username?.[0] ?? 'A').toUpperCase()}
        </div>
        <span className="text-sm font-medium text-on-surface">{user?.username || 'Admin'}</span>
        {user?.role && user.username !== 'anonymous' && (
          <span className="text-xs text-on-surface-variant opacity-60">{user.role}</span>
        )}
      </div>

      {/* Logout — only show if not in open-auth mode */}
      {user?.username !== 'anonymous' && (
        <button
          className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-low transition-colors"
          title="Logout"
          onClick={logout}
        >
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 18 }}>logout</span>
        </button>
      )}
    </header>
  )
}
