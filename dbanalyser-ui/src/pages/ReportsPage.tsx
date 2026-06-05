import { useState, useEffect } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'
import { api, runApi } from '../lib/api'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'
import KpiCard from '../components/KpiCard'

const TABS = [
  { id: 'download', label: 'Download Report',  icon: 'download' },
  { id: 'gate',     label: 'Health Gate',      icon: 'verified_user' },
  { id: 'trend',    label: 'Trend Analysis',   icon: 'trending_up' },
  { id: 'audit',    label: 'Audit Log',        icon: 'history' },
]

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function ReportsPage() {
  const [tab, setTab]       = useState('download')
  const [fmt, setFmt]       = useState('pdf')
  const [downloading, setDownloading] = useState(false)
  
  const [selectedDb, setSelectedDb] = useState<string>('')
  const [selectedRun, setSelectedRun] = useState<number | null>(null)

  const { selectedDb: ctxDb } = useOutletContext<{ selectedDb: string | null }>()

  // Sync DB from context
  useEffect(() => {
    if (ctxDb && !selectedDb) setSelectedDb(ctxDb)
  }, [ctxDb, selectedDb])

  // Databases
  const { data: dbList = [] } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => api.get('/db-registry/').then(r => r.data as any[]),
  })

  // Runs list
  const { data: runData } = useQuery({
    queryKey: ['runs', selectedDb],
    queryFn:  () => api.get('/runs', { params: selectedDb ? { db_name: selectedDb } : {} }).then(r => r.data.runs),
  })
  const runs: any[] = runData ?? []

  useEffect(() => {
    if (runs.length > 0 && selectedRun === null) {
      setSelectedRun(runs[0].id)
    } else if (runs.length === 0 && selectedRun !== null) {
      setSelectedRun(null)
    }
  }, [runs, selectedRun])

  const effectiveRunId = selectedRun ?? runs[0]?.id ?? null
  const selectedRunObj = runs.find(r => r.id === effectiveRunId)

  // Health gate for selected run
  const { data: gate, isLoading: gateLoading } = useQuery({
    queryKey: ['health-gate', effectiveRunId],
    queryFn:  () => api.get(`/reports/health-gate/${effectiveRunId}`).then(r => r.data),
    enabled:  !!effectiveRunId,
  })

  // Trend data
  const { data: trendData } = useQuery({
    queryKey: ['trend-all'],
    queryFn:  () => api.get('/trend/all').then(r => r.data),
  })
  const trends: any[] = trendData ?? []

  // Build unified trend chart (merge all DB points by timestamp)
  const trendChartData = (() => {
    if (!trends.length) return []
    const pointMap: Record<string, any> = {}
    trends.forEach((db: any) => {
      db.points?.forEach((pt: any) => {
        const date = new Date(pt.timestamp).toLocaleDateString()
        if (!pointMap[date]) pointMap[date] = { date }
        pointMap[date][db.db_name] = pt.health_score
      })
    })
    return Object.values(pointMap).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  })()
  const dbNames: string[] = trends.map((t: any) => t.db_name)
  const LINE_COLORS = ['#7c3aed', '#10b981', '#f59e0b', '#0284c7', '#ef4444']

  // Audit log
  const { data: auditData } = useQuery({
    queryKey: ['audit'],
    queryFn:  () => api.get('/audit/?limit=50').then(r => r.data),
  })
  const auditLogs: any[] = auditData?.logs ?? []

  // Download handler
  const handleDownload = async () => {
    if (!effectiveRunId) return
    setDownloading(true)
    try {
      const res = await fetch(`${API_BASE}/reports/download/${effectiveRunId}?fmt=${fmt}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob   = await res.blob()
      const ext    = fmt === 'excel' ? 'xlsx' : fmt === 'pdf' ? 'pdf' : fmt
      const url    = URL.createObjectURL(blob)
      const a      = document.createElement('a')
      a.href       = url
      a.download   = `dbanalyser_report_run${effectiveRunId}.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      alert(`Download failed: ${e.message}`)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div>
      <PageHeader title="Reports" subtitle="Download reports, check health gates, and view trend analysis" />

      {/* ── DB & Run Filter dropdowns ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-6 mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xs text-on-surface-variant font-medium uppercase tracking-wide">Database:</span>
          <select
            value={selectedDb}
            onChange={(e) => {
              setSelectedDb(e.target.value)
              setSelectedRun(null)
            }}
            className="text-sm bg-surface-low rounded-lg px-3 py-1.5 text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="">All Databases</option>
            {dbList.map((db: any) => (
              <option key={db.name} value={db.name}>{db.name}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-on-surface-variant font-medium uppercase tracking-wide">Run:</span>
          <select
            value={selectedRun ?? ''}
            onChange={(e) => setSelectedRun(e.target.value ? parseInt(e.target.value) : null)}
            className="text-sm bg-surface-low rounded-lg px-3 py-1.5 text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
            disabled={!selectedDb}
          >
            <option value="">Latest Run</option>
            {runs.map((r: any) => (
              <option key={r.id} value={r.id}>
                Run #{r.id} - {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* ── Download Report ────────────────────────────────────────────── */}
      {tab === 'download' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="Total Runs"     value={runs.length}                                     icon="history" />
            <KpiCard label="Selected Run"   value={selectedRunObj?.label ?? 'Latest'}              icon="flag" color="#630ed4" />
            <KpiCard label="Run Health"     value={selectedRunObj ? `${selectedRunObj.health_score}%` : '—'} icon="favorite"
              color={selectedRunObj?.health_score >= 80 ? '#10b981' : '#f59e0b'} />
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Config card */}
            <div className="bg-surface-lowest rounded-xl p-6 shadow-card space-y-5">
              <div className="text-sm font-semibold text-on-surface">Report Configuration</div>

              <div>
                <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-2 block">Run</label>
                <div className="flex items-center gap-2 bg-surface-low rounded-lg px-3 py-2.5">
                  <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 16 }}>history</span>
                  <span className="text-sm text-on-surface font-mono">
                    {selectedRunObj?.label ?? (effectiveRunId ? `Run #${effectiveRunId}` : 'Select a run from the top bar')}
                  </span>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-2 block">Format</label>
                <div className="grid grid-cols-5 gap-2">
                  {[
                    { value: 'excel', icon: 'table_chart',  label: 'Excel'  },
                    { value: 'pdf',   icon: 'picture_as_pdf', label: 'PDF'  },
                    { value: 'html',  icon: 'html',         label: 'HTML'   },
                    { value: 'json',  icon: 'data_object',  label: 'JSON'   },
                    { value: 'csv',   icon: 'csv',          label: 'CSV'    },
                  ].map(f => (
                    <button
                      key={f.value}
                      onClick={() => setFmt(f.value)}
                      className={`flex flex-col items-center gap-1 py-3 rounded-lg text-xs font-medium transition-all ${
                        fmt === f.value
                          ? 'text-white'
                          : 'bg-surface-low text-on-surface-variant hover:bg-surface'
                      }`}
                      style={fmt === f.value ? { background: 'linear-gradient(135deg, #630ed4, #7c3aed)' } : {}}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{f.icon}</span>
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={handleDownload}
                disabled={downloading || !effectiveRunId}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-semibold text-white disabled:opacity-50 transition-opacity"
                style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                  {downloading ? 'hourglass_empty' : 'download'}
                </span>
                {downloading ? 'Generating…' : `Download ${fmt.toUpperCase()} Report`}
              </button>
            </div>

            {/* Run list */}
            <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
              <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                Available Runs
              </div>
              <div className="divide-y" style={{ borderColor: 'rgba(74,68,85,0.06)' }}>
                {runs.slice(0, 10).map((r: any) => {
                  const h  = r.health_score ?? 0
                  const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                  const isSelected = r.id === effectiveRunId
                  return (
                    <div key={r.id}
                      className={`px-5 py-3 flex items-center gap-3 ${isSelected ? 'bg-primary/5' : 'hover:bg-surface/60'}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-on-surface truncate">{r.label}</div>
                        <div className="text-xs text-on-surface-variant mt-0.5">{r.db_name} · {new Date(r.timestamp).toLocaleString()}</div>
                      </div>
                      <div className="text-sm font-semibold" style={{ color: hc }}>{h}%</div>
                      <button
                        className="text-xs text-primary hover:underline"
                        title="Download JSON report for this run"
                        onClick={async () => {
                          try {
                            const res = await fetch(`${API_BASE}/reports/download/${r.id}?fmt=pdf`, {
                              headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
                            })
                            if (!res.ok) throw new Error(`HTTP ${res.status}`)
                            const blob = await res.blob()
                            const url  = URL.createObjectURL(blob)
                            const a    = document.createElement('a')
                            a.href     = url
                            a.download = `report_run${r.id}.pdf`
                            a.click()
                            URL.revokeObjectURL(url)
                          } catch (e: any) { alert(`Download failed: ${e.message}`) }
                        }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>download</span>
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Health Gate ───────────────────────────────────────────────── */}
      {tab === 'gate' && (
        <div className="space-y-4">
          {!effectiveRunId ? (
            <div className="bg-surface-lowest rounded-xl p-6 shadow-card text-sm text-on-surface-variant">
              Select a run from the top bar to check the health gate.
            </div>
          ) : gateLoading ? (
            <div className="bg-surface-lowest rounded-xl p-6 shadow-card text-sm text-on-surface-variant">Loading…</div>
          ) : (
            <>
              {/* Gate status banner */}
              <div className={`rounded-xl px-6 py-5 flex items-start gap-4 ${gate?.detail?.gate === 'PASSED' ? 'bg-green-50' : 'bg-red-50'}`}>
                <span className="material-symbols-outlined mt-0.5" style={{ fontSize: 32, color: gate?.detail?.gate === 'PASSED' ? '#10b981' : '#dc2626' }}>
                  {gate?.detail?.gate === 'PASSED' ? 'check_circle' : 'cancel'}
                </span>
                <div>
                  <div className="font-bold text-lg" style={{ color: gate?.detail?.gate === 'PASSED' ? '#10b981' : '#dc2626' }}>
                    Health Gate {gate?.detail?.gate ?? 'UNKNOWN'}
                  </div>
                  <div className="text-sm mt-1" style={{ color: gate?.detail?.gate === 'PASSED' ? '#065f46' : '#7f1d1d' }}>
                    {gate?.detail?.gate === 'PASSED'
                      ? 'All thresholds are within acceptable limits. This run is safe to promote.'
                      : 'One or more thresholds exceeded. Review and remediate before promoting to production.'}
                  </div>
                </div>
              </div>

              {/* Gate metrics */}
              <div className="grid grid-cols-3 gap-4">
                <KpiCard label="Health Score" value={`${gate?.detail?.health ?? 0}%`} icon="favorite"
                  color={gate?.detail?.health >= 80 ? '#10b981' : '#f59e0b'} />
                <KpiCard label="Critical Issues" value={gate?.detail?.critical ?? 0} icon="error"    color="#dc2626" />
                <KpiCard label="High Issues"     value={gate?.detail?.high    ?? 0} icon="warning"  color="#f59e0b" />
              </div>

              {/* Failure reasons */}
              {gate?.detail?.reasons?.length > 0 && (
                <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                  <div className="text-sm font-semibold text-on-surface mb-3">Gate Failure Reasons</div>
                  <div className="space-y-2">
                    {gate.detail.reasons.map((r: string, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-sm text-error">
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                        {r}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Run details */}
              {selectedRunObj && (
                <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                  <div className="text-sm font-semibold text-on-surface mb-4">Run Details — {selectedRunObj.label}</div>
                  <div className="grid grid-cols-4 gap-4">
                    <KpiCard label="Total Issues" value={selectedRunObj.total_issues}  icon="bug_report" />
                    <KpiCard label="High"         value={selectedRunObj.high_count}    icon="warning"    color="#f59e0b" />
                    <KpiCard label="Medium"       value={selectedRunObj.medium_count}  icon="info"       color="#0284c7" />
                    <KpiCard label="Low"          value={selectedRunObj.low_count}     icon="low_priority" color="#16a34a" />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Trend Analysis ─────────────────────────────────────────────── */}
      {tab === 'trend' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {trends.slice(0, 3).map((t: any) => {
              const latest = t.points?.[t.points.length - 1]
              const h = latest?.health_score ?? 0
              const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
              return (
                <KpiCard key={t.db_name} label={t.db_name} value={`${h}%`} icon="storage" color={hc}
                  sub={`${t.points?.length ?? 0} data points`} />
              )
            })}
          </div>

          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-4">Health Score Trend — All Databases</div>
            {trendChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,68,85,0.08)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: any) => [`${v}%`, '']} />
                  <Legend />
                  {dbNames.map((name, i) => (
                    <Line key={name} type="monotone" dataKey={name} stroke={LINE_COLORS[i % LINE_COLORS.length]}
                      strokeWidth={2} dot={{ r: 4 }} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-sm text-on-surface-variant">No trend data available yet.</div>
            )}
          </div>

          {/* Per-DB trend tables */}
          {trends.map((t: any) => (
            <div key={t.db_name} className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
              <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                {t.db_name} — Run History
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-low">
                    {['Date','Health','Total Issues','Critical','High','Medium','Low'].map(h => (
                      <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(t.points ?? []).slice(0, 5).map((pt: any, i: number) => {
                    const h  = pt.health_score ?? 0
                    const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                    return (
                      <tr key={i} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                        <td className="px-4 py-2.5 text-xs text-on-surface-variant">{new Date(pt.timestamp).toLocaleString()}</td>
                        <td className="px-4 py-2.5 font-semibold" style={{ color: hc }}>{h}%</td>
                        <td className="px-4 py-2.5 text-on-surface">{pt.total_issues}</td>
                        <td className="px-4 py-2.5 text-error font-medium">{pt.critical_count}</td>
                        <td className="px-4 py-2.5 text-warning font-medium">{pt.high_count}</td>
                        <td className="px-4 py-2.5 text-on-surface-variant">{pt.medium_count}</td>
                        <td className="px-4 py-2.5 text-on-surface-variant">{pt.low_count}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {/* ── Audit Log ─────────────────────────────────────────────────── */}
      {tab === 'audit' && (
        <div className="space-y-4">
          <KpiCard label="Audit Events" value={auditData?.total ?? auditLogs.length} icon="history" color="#630ed4" />
          <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
            <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
              System Audit Log
            </div>
            {auditLogs.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-on-surface-variant">No audit events recorded yet.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-low">
                    {['Timestamp','Action','Entity','User','Details'].map(h => (
                      <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log: any, i: number) => (
                    <tr key={log.id ?? i} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                      <td className="px-4 py-2.5 text-xs text-on-surface-variant font-mono">
                        {new Date(log.timestamp || log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-xs px-2 py-0.5 rounded-md font-medium bg-primary/10 text-primary">{log.action}</span>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-on-surface">{log.entity_type} #{log.entity_id}</td>
                      <td className="px-4 py-2.5 text-xs text-on-surface-variant">{log.username || 'system'}</td>
                      <td className="px-4 py-2.5 text-xs text-on-surface-variant max-w-xs truncate">{log.detail || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
