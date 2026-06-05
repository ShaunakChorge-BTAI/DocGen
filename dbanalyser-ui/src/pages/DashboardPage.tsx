import { useState, useRef } from 'react'
import { useOutletContext, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { dbApi, runApi, findingsApi, api } from '../lib/api'
import KpiCard from '../components/KpiCard'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'

const TABS = [
  { id: 'overview', label: 'Estate Overview', icon: 'dashboard' },
  { id: 'detail',   label: 'Database Detail', icon: 'storage' },
  { id: 'trend',    label: 'Trend Analysis',  icon: 'trending_up' },
  { id: 'history',  label: 'Run History',     icon: 'history' },
]

const SEV_COLORS: Record<string, string> = {
  Critical: '#dc2626', High: '#f59e0b', Medium: '#0284c7', Low: '#16a34a',
}
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Inline Run Button with job-polling progress ───────────────────────────────
function RunButton({
  dbName, onRunComplete,
}: {
  dbName: string
  onRunComplete: (runId: number | null) => void
}) {
  const [status, setStatus]   = useState<string>('')   // queued | running | done | failed
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    setRunning(true)
    setStatus('queued')
    try {
      const r   = await api.post('/runs/trigger', { db_name: dbName })
      const jid = r.data.job_id
      // Poll job status every 2 s
      const poll = setInterval(async () => {
        try {
          const s = await api.get(`/runs/jobs/${jid}`)
          setStatus(s.data.status)
          if (s.data.status === 'done' || s.data.status === 'failed') {
            clearInterval(poll)
            setRunning(false)
            onRunComplete(s.data.status === 'done' ? (s.data.run_id ?? null) : null)
          }
        } catch {
          clearInterval(poll)
          setRunning(false)
          setStatus('failed')
          onRunComplete(null)
        }
      }, 2000)
    } catch {
      setStatus('failed')
      setRunning(false)
      onRunComplete(null)
    }
  }

  const icon   = status === 'done'    ? 'check_circle'
               : status === 'failed'  ? 'error'
               : status === 'running' ? 'hourglass_empty'
               : status === 'queued'  ? 'pending'
               : 'play_arrow'
  const color  = status === 'done'   ? '#10b981'
               : status === 'failed' ? '#dc2626'
               : '#630ed4'
  const label  = status === 'done'   ? 'Done!'
               : status === 'failed' ? 'Failed'
               : status === 'running'? 'Running…'
               : status === 'queued' ? 'Queued…'
               : 'Run'

  return (
    <button
      onClick={handleRun}
      disabled={running}
      title={`Run assessment on ${dbName}`}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all disabled:opacity-70"
      style={{ background: `linear-gradient(135deg, ${color} 0%, ${color}cc 100%)` }}
    >
      <span className={`material-symbols-outlined ${running ? 'animate-spin' : ''}`}
            style={{ fontSize: 13 }}>{icon}</span>
      {label}
    </button>
  )
}

// ── View Runs slide-over panel ────────────────────────────────────────────────
function RunsPanel({
  dbName, onClose, onSelectRun, onNavigate,
}: { dbName: string; onClose: () => void; onSelectRun: (id: number) => void; onNavigate: (id: number) => void }) {
  const { data: runData } = useQuery({
    queryKey: ['runs', dbName],
    queryFn:  () => runApi.list(dbName).then(r => r.data.runs),
  })
  const runs: any[] = runData ?? []

  const downloadRun = async (runId: number) => {
    try {
      const res = await fetch(`${API_BASE}/reports/download/${runId}?fmt=pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = `report_run${runId}.pdf`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) { alert(`Download failed: ${e.message}`) }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end" style={{ background: 'rgba(0,0,0,0.4)' }}
         onClick={onClose}>
      <div className="w-[480px] h-full bg-surface-lowest flex flex-col shadow-float"
           onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4"
             style={{ borderBottom: '1px solid rgba(74,68,85,0.1)' }}>
          <div>
            <div className="text-sm font-semibold text-on-surface">Run History</div>
            <div className="text-xs text-on-surface-variant font-mono mt-0.5">{dbName}</div>
          </div>
          <button onClick={onClose}
                  className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-low">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>

        {/* Run list */}
        <div className="flex-1 overflow-y-auto divide-y" style={{ borderColor: 'rgba(74,68,85,0.06)' }}>
          {runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <span className="material-symbols-outlined text-on-surface-variant opacity-30" style={{ fontSize: 48 }}>
                history
              </span>
              <p className="text-sm text-on-surface-variant">No runs found for {dbName}</p>
            </div>
          ) : runs.map((r: any) => {
            const h  = r.health_score ?? 0
            const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
            return (
              <div key={r.id} className="px-5 py-3.5 hover:bg-surface/50 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-medium text-on-surface truncate">
                        {r.label || `Run #${r.id}`}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 rounded-full font-semibold text-white flex-shrink-0"
                            style={{ background: hc }}>{h}%</span>
                    </div>
                    <div className="text-xs text-on-surface-variant">
                      {new Date(r.timestamp).toLocaleString()} · {r.total_issues ?? 0} findings
                    </div>
                    {/* Mini severity row */}
                    <div className="flex gap-2 mt-1.5">
                      {[['C', r.critical_count, '#dc2626'], ['H', r.high_count, '#f59e0b'],
                        ['M', r.medium_count, '#0284c7'], ['L', r.low_count, '#16a34a']].map(([l, v, c]) => (
                        v ? <span key={l as string} className="text-xs font-semibold"
                                  style={{ color: c as string }}>{l}: {v}</span> : null
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button
                      onClick={() => { onSelectRun(r.id); onClose(); onNavigate(r.id) }}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-white"
                      style={{ background: 'linear-gradient(135deg, #630ed4, #7c3aed)' }}
                    >Select</button>
                    <button
                      onClick={() => downloadRun(r.id)}
                      title="Download PDF report"
                      className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-surface-low text-on-surface-variant"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 15 }}>download</span>
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [tab, setTab]         = useState('overview')
  const [selectedDb, setSelectedDb] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const nav                   = useNavigate()
  const qc                    = useQueryClient()
  const dbSectionRef          = useRef<HTMLDivElement>(null)
  const [runsPanel, setRunsPanel] = useState<string | null>(null) // db name for panel

  const { data: dbData }  = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data),
  })
  const dbs: any[] = dbData ?? []

  const { data: runData } = useQuery({
    queryKey: ['runs', selectedDb],
    queryFn:  () => runApi.list(selectedDb ?? undefined).then(r => r.data.runs),
  })
  const runs: any[] = runData ?? []

  const effectiveRunId = selectedRun ?? runs[0]?.id ?? null
  const { data: summary } = useQuery({
    queryKey: ['summary', effectiveRunId],
    queryFn:  () => findingsApi.summary(effectiveRunId!).then(r => r.data),
    enabled:  !!effectiveRunId,
  })

  const latestRun     = runs[0]
  const health        = latestRun?.health_score ?? 100
  const totalFindings = latestRun?.total_issues ?? 0
  const sevCounts     = {
    Critical: summary?.critical ?? latestRun?.critical_count ?? 0,
    High:     summary?.high     ?? latestRun?.high_count     ?? 0,
    Medium:   summary?.medium   ?? latestRun?.medium_count   ?? 0,
    Low:      summary?.low      ?? latestRun?.low_count      ?? 0,
  }
  const pieData    = Object.entries(sevCounts).map(([k, v]) => ({ name: k, value: v as number }))
  const healthColor = health >= 80 ? '#10b981' : health >= 60 ? '#f59e0b' : '#ef4444'

  const downloadRunReport = async (runId: number) => {
    try {
      const res = await fetch(`${API_BASE}/reports/download/${runId}?fmt=pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = `report_run${runId}.pdf`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) { alert(`Download failed: ${e.message}`) }
  }

  return (
    <div>
      {/* Run history slide-over panel */}
      {runsPanel && (
        <RunsPanel
          dbName={runsPanel}
          onClose={() => setRunsPanel(null)}
          onNavigate={(id) => nav(`/analysis?run_id=${id}`)}
          onSelectRun={(id) => {
            if (typeof setSelectedRun === 'function') setSelectedRun(id)
          }}
        />
      )}

      <PageHeader
        title="Database Estate"
        subtitle="Real-time overview of your SQL Server landscape"
      />

      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* ─── Estate Overview ──────────────────────────────────────────── */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* KPI Row */}
          <div className="grid grid-cols-5 gap-4">
            <KpiCard label="Databases"     value={dbs.length}   icon="storage"   color="#630ed4"
              sub="Click to view list"
              onClick={() => dbSectionRef.current?.scrollIntoView({ behavior: 'smooth' })} />
            <KpiCard label="Overall Health" value={`${health}%`} icon="favorite" color={healthColor}
              sub="Click for trend"
              onClick={() => setTab('trend')} />
            <KpiCard label="Total Findings" value={totalFindings} icon="bug_report" color="#f59e0b"
              sub="Click to explore"
              onClick={() => nav('/analysis', { state: { tab: 'explorer' } })} />
            <KpiCard label="Critical Issues" value={sevCounts.Critical} icon="error" color="#dc2626"
              sub="Click to filter"
              onClick={() => nav('/analysis', { state: { tab: 'explorer', sevFilter: 'Critical' } })} />
            <KpiCard label="Last Run"
              value={latestRun ? new Date(latestRun.timestamp).toLocaleDateString() : '—'}
              icon="schedule"
              sub="Click for history"
              onClick={() => setTab('history')} />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">Health Score by Database</div>
              {dbs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 gap-2 text-on-surface-variant">
                  <span className="material-symbols-outlined opacity-30" style={{ fontSize: 40 }}>storage</span>
                  <span className="text-sm">No databases registered yet</span>
                  <button onClick={() => nav('/administration')}
                          className="text-xs text-primary hover:underline">Register one →</button>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={dbs.map((db: any) => ({
                    name: db.name, score: db.last_health ?? 0,
                  }))}>
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="score" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">Findings by Severity</div>
              {pieData.every(d => d.value === 0) ? (
                <div className="flex flex-col items-center justify-center h-40 gap-2 text-on-surface-variant">
                  <span className="material-symbols-outlined opacity-30" style={{ fontSize: 36 }}>
                    check_circle
                  </span>
                  <span className="text-xs">No findings in selected run</span>
                </div>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={72}
                           dataKey="value" nameKey="name">
                        {pieData.map((entry) => (
                          <Cell key={entry.name} fill={SEV_COLORS[entry.name] || '#94a3b8'} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {pieData.map((d) => (
                      <div key={d.name} className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full" style={{ background: SEV_COLORS[d.name] }} />
                        <span className="text-xs text-on-surface-variant">{d.name}: {d.value}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* DB Cards */}
          <div ref={dbSectionRef}>
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold text-on-surface">Registered Databases</div>
              <button
                onClick={() => nav('/administration')}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>add</span>
                Register Database
              </button>
            </div>

            {dbs.length === 0 ? (
              <div className="bg-surface-lowest rounded-xl p-10 shadow-card flex flex-col items-center gap-3">
                <span className="material-symbols-outlined text-on-surface-variant opacity-30"
                      style={{ fontSize: 52 }}>storage</span>
                <p className="text-sm text-on-surface-variant">No databases registered yet.</p>
                <button
                  onClick={() => nav('/administration')}
                  className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
                  style={{ background: 'linear-gradient(135deg, #630ed4, #7c3aed)' }}
                >Register your first database</button>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                {dbs.map((db: any) => {
                  const h  = db.last_health ?? 0
                  const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                  return (
                    <div key={db.id}
                         className="bg-surface-lowest rounded-xl p-4 shadow-card hover:shadow-float transition-all">
                      {/* Header row */}
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <div className="font-semibold text-sm text-on-surface">{db.name}</div>
                          <div className="text-xs text-on-surface-variant mt-0.5 font-mono">
                            {db.host}:{db.port}
                          </div>
                        </div>
                        <span className="text-xs px-2 py-0.5 rounded-full text-white font-semibold flex-shrink-0"
                              style={{ background: hc }}>
                          {h > 0 ? `${h}%` : '—'}
                        </span>
                      </div>

                      {/* Environment badge */}
                      <span className="text-xs px-2 py-0.5 rounded-md bg-surface-low text-on-surface-variant font-medium">
                        {db.environment}
                      </span>

                      {/* Health bar */}
                      <div className="mt-3 h-1 bg-surface-low rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all"
                             style={{ width: `${h}%`, background: hc }} />
                      </div>

                      {/* Last run info */}
                      <div className="mt-2 text-xs text-on-surface-variant">
                        {db.last_run_at
                          ? `Last run: ${new Date(db.last_run_at).toLocaleDateString()}`
                          : 'Never run'}
                      </div>

                      {/* Action buttons */}
                      <div className="mt-3 flex items-center gap-2">
                        <RunButton
                          dbName={db.name}
                          onRunComplete={(runId) => {
                            qc.invalidateQueries()
                            if (runId) {
                              if (typeof setSelectedDb   === 'function') setSelectedDb(db.name)
                              if (typeof setSelectedRun  === 'function') setSelectedRun(runId)
                            }
                          }}
                        />
                        <button
                          onClick={() => setRunsPanel(db.name)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-low text-on-surface hover:bg-surface transition-colors"
                        >
                          <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                            history
                          </span>
                          View Runs
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Database Detail ──────────────────────────────────────────── */}
      {tab === 'detail' && (
        <div className="bg-surface-lowest rounded-xl p-6 shadow-card">
          {!selectedDb ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <span className="material-symbols-outlined text-on-surface-variant opacity-30"
                    style={{ fontSize: 48 }}>storage</span>
              <p className="text-sm text-on-surface-variant">
                Select a database from the top bar to see detailed metrics.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="text-sm font-semibold text-on-surface">{selectedDb} — Detail</div>
              {dbs.filter((d: any) => d.name === selectedDb).map((db: any) => {
                const h  = db.last_health ?? 0
                const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                return (
                  <div key={db.id} className="grid grid-cols-3 gap-4">
                    <KpiCard label="Health Score" value={h ? `${h}%` : '—'} icon="favorite" color={hc} />
                    <KpiCard label="Environment"  value={db.environment}    icon="dns" />
                    <KpiCard label="Last Run"
                      value={db.last_run_at ? new Date(db.last_run_at).toLocaleDateString() : 'Never'}
                      icon="schedule" />
                  </div>
                )
              })}
              <div className="flex gap-2">
                <button onClick={() => setRunsPanel(selectedDb)}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-surface-low text-on-surface hover:bg-surface">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>history</span>
                  View Runs
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── Trend Analysis ───────────────────────────────────────────── */}
      {tab === 'trend' && (
        <div className="bg-surface-lowest rounded-xl p-6 shadow-card">
          <div className="text-sm font-semibold text-on-surface mb-4">Run History — Health Trend</div>
          {runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-2 text-on-surface-variant">
              <span className="material-symbols-outlined opacity-30" style={{ fontSize: 40 }}>trending_up</span>
              <span className="text-sm">No run history yet. Run an assessment to see trends.</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={[...runs].reverse().slice(-10).map((r: any) => ({
                label: r.label || `Run ${r.id}`, health: r.health_score ?? 0,
              }))}>
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Bar dataKey="health" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* ─── Run History ──────────────────────────────────────────────── */}
      {tab === 'history' && (
        <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-low">
                {['Run', 'Database', 'Date', 'Health', 'Findings', 'Report'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium text-on-surface-variant uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2 text-on-surface-variant">
                      <span className="material-symbols-outlined opacity-30" style={{ fontSize: 40 }}>history</span>
                      <span className="text-sm">No runs found. Trigger an assessment from the database cards above.</span>
                    </div>
                  </td>
                </tr>
              ) : runs.map((r: any, i: number) => {
                const h  = r.health_score ?? 0
                const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                return (
                  <tr key={r.id} className={i % 2 === 0 ? '' : 'bg-surface/50'}>
                    <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                      {r.label || `Run #${r.id}`}
                    </td>
                    <td className="px-4 py-3 text-on-surface">{r.db_name || '—'}</td>
                    <td className="px-4 py-3 text-on-surface-variant text-xs">
                      {new Date(r.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-semibold" style={{ color: hc }}>{h}%</span>
                    </td>
                    <td className="px-4 py-3 text-on-surface">{r.total_issues ?? '—'}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => downloadRunReport(r.id)}
                        title="Download PDF report"
                        className="flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>download</span>
                        PDF
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
