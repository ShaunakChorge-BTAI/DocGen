import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid,
} from 'recharts'
import { api, dbApi, runApi, findingsApi, metadataApi, liveMetricsApi } from '../lib/api'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'
import KpiCard from '../components/KpiCard'
import SeverityBadge from '../components/SeverityBadge'
import DeleteRunModal from '../components/DeleteRunModal'

const TABS = [
  { id: 'overview',  label: 'Overview',        icon: 'monitor_heart' },
  { id: 'perf',      label: 'Performance',     icon: 'speed' },
  { id: 'indexes',   label: 'Index Analysis',  icon: 'filter_list' },
  { id: 'safety',    label: 'Data Safety',      icon: 'shield' },
  { id: 'metadata',  label: 'Schema Metadata',  icon: 'table_chart' },
  { id: 'live-metrics', label: 'Live Metrics',  icon: 'trending_up' },
  { id: 'trigger',   label: 'Run Live Scan',   icon: 'play_circle' },
]

const RULE_DESCS: Record<string, string> = {
  PERF001: 'SELECT * — fetches all columns unnecessarily',
  PERF004: 'Function in WHERE clause prevents index seek (ISNULL/CONVERT)',
  PERF007: 'View without SCHEMABINDING — tables can change without warning',
  BP001:   'Missing SET NOCOUNT ON — sends extra result sets to client',
  BP002:   'sp_ prefix on procedure — conflicts with system stored procedures',
  BP003:   'Missing schema prefix — causes recompilation and ambiguity',
  DS001:   'NULL comparison using = NULL instead of IS NULL',
  DS002:   'Implicit data type conversion — may cause index scans',
  DS003:   'Division without zero check — potential runtime error',
  DS006:   'String truncation risk — no length validation before INSERT',
  REL001:  'No TRY/CATCH — DML errors propagate unhandled',
}

export default function LiveDbPage() {
  const [tab, setTab]           = useState('overview')
  const [kpiFilter, setKpiFilter] = useState<string | null>(null)
  const [triggerDb, setTriggerDb] = useState('')
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState<any>(null)
  const [triggerError, setTriggerError]   = useState('')
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [selectedRunToDelete, setSelectedRunToDelete] = useState<any>(null)
  const [refreshingMetadata, setRefreshingMetadata] = useState(false)
  const [metadataError, setMetadataError] = useState('')
  const [metadataSuccess, setMetadataSuccess] = useState('')
  const [capturingMetrics, setCapturingMetrics] = useState(false)
  const [metricsError, setMetricsError] = useState('')
  const [metricsSuccess, setMetricsSuccess] = useState('')
  const [selectedMetricTypes, setSelectedMetricTypes] = useState<string[]>([
    'index_usage', 'unused_indexes', 'missing_indexes', 'slow_queries', 'blocking_sessions', 'wait_statistics', 'table_sizes'
  ])
  const [liveStatus, setLiveStatus] = useState<any>(null)

  const queryClient = useQueryClient()
  const { selectedDb, selectedRun } = useOutletContext<{ selectedDb: string | null; selectedRun: number | null }>()

  // Databases
  const { data: dbList = [] } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data as any[]),
  })

  // Runs
  const { data: runData } = useQuery({
    queryKey: ['runs', selectedDb],
    queryFn:  () => runApi.list(selectedDb ?? undefined).then(r => r.data.runs),
  })
  const runs: any[] = runData ?? []

  // Use live_db runs preferentially
  const liveRuns  = runs.filter(r => r.source_mode === 'live_db')
  const effectiveRunId = selectedRun ?? liveRuns[0]?.id ?? runs[0]?.id ?? null
  const selectedRunObj = runs.find(r => r.id === effectiveRunId)

  // Findings for selected run
  const { data: findingsData, isLoading } = useQuery({
    queryKey: ['findings', effectiveRunId],
    queryFn:  () => findingsApi.byRun(effectiveRunId!).then(r => r.data),
    enabled:  !!effectiveRunId,
  })
  const allFindings: any[] = findingsData?.findings ?? []

  // ── Derived ──────────────────────────────────────────────────────────────
  const perfFindings   = allFindings.filter(f => f.category === 'Performance')
  const safetyFindings = allFindings.filter(f => f.category === 'Data Safety')
  const bpFindings     = allFindings.filter(f => f.category === 'Best Practices')

  // Filter findings based on KPI filter
  const displayFindings = kpiFilter
    ? allFindings.filter(f => f.category === kpiFilter)
    : allFindings

  // Rule breakdown chart
  const ruleMap: Record<string, number> = {}
  displayFindings.forEach(f => { ruleMap[f.rule_id] = (ruleMap[f.rule_id] || 0) + 1 })
  const ruleChart = Object.entries(ruleMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([rule, count]) => ({ rule, count, desc: RULE_DESCS[rule] ?? rule }))

  // Object type breakdown
  const typeMap: Record<string, number> = {}
  displayFindings.forEach(f => { typeMap[f.object_type] = (typeMap[f.object_type] || 0) + 1 })
  const typeChart = Object.entries(typeMap).map(([name, count]) => ({ name, count }))

  // Trend across runs
  const trendData = [...runs].reverse().slice(-8).map(r => ({
    label: r.label?.split(' ').slice(-2).join(' ') || `#${r.id}`,
    health: r.health_score ?? 0,
    issues: r.total_issues ?? 0,
  }))

  // Index-related findings (PERF004 = non-SARGable, SELECT * = PERF001)
  const indexFindings = allFindings.filter(f =>
    ['PERF004', 'PERF001', 'PERF007'].includes(f.rule_id) || f.category === 'Performance'
  )

  // Metadata
  const { data: metadataData } = useQuery({
    queryKey: ['metadata', selectedDb],
    queryFn:  () => selectedDb ? metadataApi.get(selectedDb).then(r => r.data) : null,
    enabled:  !!selectedDb && tab === 'metadata',
  })

  // Trigger live scan
  const handleTrigger = async () => {
    if (!triggerDb) return
    setTriggering(true); setTriggerResult(null); setTriggerError('')
    try {
      const r = await api.post('/runs/trigger', { db_name: triggerDb, run_dmv: true })
      setTriggerResult(r.data)
    } catch (e: any) {
      setTriggerError(e?.response?.data?.detail || 'Trigger failed. Check API logs.')
    } finally {
      setTriggering(false)
    }
  }

  // Refresh metadata
  const handleRefreshMetadata = async () => {
    if (!selectedDb) return
    setRefreshingMetadata(true); setMetadataError(''); setMetadataSuccess('')
    try {
      await metadataApi.refresh(selectedDb)
      setMetadataSuccess(`Metadata refreshed for ${selectedDb}`)
      queryClient.invalidateQueries({ queryKey: ['metadata', selectedDb] })
      setTimeout(() => setMetadataSuccess(''), 4000)
    } catch (e: any) {
      setMetadataError(e?.response?.data?.detail || 'Metadata refresh failed.')
    } finally {
      setRefreshingMetadata(false)
    }
  }

  // Capture live metrics
  const handleCaptureLiveMetrics = async () => {
    if (!selectedDb) return
    setCapturingMetrics(true); setMetricsError(''); setMetricsSuccess('')
    try {
      const result = await liveMetricsApi.scan(selectedDb, selectedMetricTypes)
      setMetricsSuccess(`Live metrics captured: ${result.data.message}`)
      // Fetch live status to show immediately
      const status = await liveMetricsApi.getLiveStatus(selectedDb)
      setLiveStatus(status.data)
      setTimeout(() => setMetricsSuccess(''), 5000)
    } catch (e: any) {
      setMetricsError(e?.response?.data?.detail || 'Live metrics capture failed.')
    } finally {
      setCapturingMetrics(false)
    }
  }

  // Toggle metric type selection
  const toggleMetricType = (type: string) => {
    if (selectedMetricTypes.includes(type)) {
      setSelectedMetricTypes(selectedMetricTypes.filter(t => t !== type))
    } else {
      setSelectedMetricTypes([...selectedMetricTypes, type])
    }
  }

  const noRunMsg = (
    <div className="bg-amber-50 rounded-xl px-5 py-4 flex items-center gap-3 text-sm text-amber-800">
      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>info</span>
      <span>Select a run from the top bar, or use <strong>Run Live Scan</strong> tab to trigger a new DMV assessment.</span>
    </div>
  )

  return (
    <div>
      <PageHeader
        title="Live DB"
        subtitle={selectedRunObj
          ? `${selectedRunObj.label} · ${selectedRunObj.source_mode} · ${allFindings.length} findings`
          : 'Performance, index analysis, and data safety findings from live database scans'}
      />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* ── OVERVIEW ─────────────────────────────────────────────────── */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* KPIs */}
          <div className="grid grid-cols-5 gap-4">
            <KpiCard label="Health Score"    value={selectedRunObj ? `${selectedRunObj.health_score}%` : '—'}
              icon="favorite" color={(selectedRunObj?.health_score ?? 0) >= 80 ? '#10b981' : '#f59e0b'} />
            <KpiCard label="Total Findings"  value={allFindings.length}    icon="bug_report"    color="#630ed4"
              onClick={() => setKpiFilter(kpiFilter === null ? null : null)} />
            <KpiCard label="Performance"     value={perfFindings.length}   icon="speed"         color="#f59e0b"
              onClick={() => setKpiFilter(kpiFilter === 'Performance' ? null : 'Performance')} />
            <KpiCard label="Data Safety"     value={safetyFindings.length} icon="shield"        color="#0284c7"
              onClick={() => setKpiFilter(kpiFilter === 'Data Safety' ? null : 'Data Safety')} />
            <KpiCard label="Best Practices"  value={bpFindings.length}     icon="check_circle"  color="#10b981"
              onClick={() => setKpiFilter(kpiFilter === 'Best Practices' ? null : 'Best Practices')} />
          </div>

          {/* Active filter indicator */}
          {kpiFilter && (
            <div className="flex items-center gap-2 px-4 py-2 bg-primary/10 rounded-lg text-sm text-on-surface">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>filter_alt</span>
              Filtering by: <strong>{kpiFilter}</strong>
              <button onClick={() => setKpiFilter(null)} className="ml-auto opacity-60 hover:opacity-100">
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
              </button>
            </div>
          )}

          {!effectiveRunId && noRunMsg}

          {effectiveRunId && (
            <div className="grid grid-cols-3 gap-4">
              {/* Top rules chart */}
              <div className="col-span-2 bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-4">Top Issues by Rule</div>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={ruleChart} layout="vertical">
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="rule" type="category" width={70} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: any, name: any, props: any) => [v, props.payload.desc || name]} />
                    <Bar dataKey="count" fill="#7c3aed" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Object type breakdown */}
              <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-4">By Object Type</div>
                <div className="space-y-3">
                  {typeChart.sort((a, b) => b.count - a.count).map((t, i) => {
                    const colors = ['#7c3aed','#10b981','#f59e0b','#0284c7','#ef4444']
                    const pct = Math.round((t.count / (allFindings.length || 1)) * 100)
                    return (
                      <div key={t.name}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-on-surface capitalize">{t.name}</span>
                          <span className="text-xs font-bold" style={{ color: colors[i % colors.length] }}>{t.count}</span>
                        </div>
                        <div className="h-1.5 bg-surface-low rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: colors[i % colors.length] }} />
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* Run info */}
                {selectedRunObj && (
                  <div className="mt-5 pt-4 space-y-2" style={{ borderTop: '1px solid rgba(74,68,85,0.08)' }}>
                    <div className="flex justify-between text-xs">
                      <span className="text-on-surface-variant">Source mode</span>
                      <span className="font-mono font-medium text-on-surface">{selectedRunObj.source_mode}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-on-surface-variant">Objects scanned</span>
                      <span className="font-medium text-on-surface">{selectedRunObj.total_objects}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-on-surface-variant">Duration</span>
                      <span className="font-medium text-on-surface">{selectedRunObj.duration_sec}s</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Health trend */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-4">Health Score Trend</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,68,85,0.08)" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: any) => [`${v}%`, 'Health']} />
                <Line type="monotone" dataKey="health" stroke="#7c3aed" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── PERFORMANCE ──────────────────────────────────────────────── */}
      {tab === 'perf' && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <KpiCard label="Performance Issues" value={perfFindings.length}  icon="speed"      color="#f59e0b"
              onClick={() => setKpiFilter(kpiFilter === 'Performance' ? null : 'Performance')} />
            <KpiCard label="High Severity"       value={perfFindings.filter(f => f.severity === 'High').length}   icon="warning" color="#dc2626" />
            <KpiCard label="SELECT * Issues"     value={allFindings.filter(f => f.rule_id === 'PERF001').length}  icon="table_rows" color="#f59e0b" />
            <KpiCard label="Non-SARGable WHERE"  value={allFindings.filter(f => f.rule_id === 'PERF004').length}  icon="filter_alt" color="#0284c7" />
          </div>

          {!effectiveRunId ? noRunMsg : (
            <>
              {/* Best practices - sp_ prefix, nocount, schema */}
              <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-3">Best Practices Summary</div>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { rule: 'BP001', label: 'Missing SET NOCOUNT ON', color: '#f59e0b' },
                    { rule: 'BP002', label: 'sp_ prefix on procedures', color: '#dc2626' },
                    { rule: 'BP003', label: 'Missing schema prefix', color: '#0284c7' },
                  ].map(({ rule, label, color }) => {
                    const count = allFindings.filter(f => f.rule_id === rule).length
                    return (
                      <div key={rule} className="bg-surface-low rounded-xl p-4">
                        <div className="text-2xl font-bold" style={{ color }}>{count}</div>
                        <div className="text-xs text-on-surface mt-1">{label}</div>
                        <div className="text-xs font-mono text-on-surface-variant opacity-60 mt-0.5">{rule}</div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Performance findings table */}
              <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                  Performance Findings ({perfFindings.length})
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-low">
                      {['Severity','Rule','Object','Type','Issue','Recommendation'].map(h => (
                        <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading ? (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant">Loading…</td></tr>
                    ) : perfFindings.slice(0, 50).map((f, i) => (
                      <tr key={f.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                        <td className="px-4 py-2.5"><SeverityBadge severity={f.severity} /></td>
                        <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{f.rule_id}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{f.object_name}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface-variant">{f.object_type}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface max-w-xs truncate">{f.issue}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface-variant max-w-xs truncate">{f.recommendation}</td>
                      </tr>
                    ))}
                    {perfFindings.length === 0 && !isLoading && (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant">No performance findings in this run.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── INDEX ANALYSIS ───────────────────────────────────────────── */}
      {tab === 'indexes' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="Index-Related Issues" value={indexFindings.length}                                    icon="filter_list"  color="#630ed4" />
            <KpiCard label="Non-SARGable Queries"  value={allFindings.filter(f=>f.rule_id==='PERF004').length}   icon="search_off"   color="#dc2626" />
            <KpiCard label="SELECT * Usage"         value={allFindings.filter(f=>f.rule_id==='PERF001').length}   icon="table_rows"   color="#f59e0b" />
          </div>

          {!effectiveRunId ? noRunMsg : (
            <>
              {/* Rule legend */}
              <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-3">Index & Query Pattern Analysis</div>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { rule: 'PERF004', label: 'Non-SARGable WHERE',    desc: 'ISNULL/CONVERT/function on indexed column prevents index seek', color: '#dc2626' },
                    { rule: 'PERF001', label: 'SELECT * Usage',         desc: 'Fetches all columns — prevents index-only scans', color: '#f59e0b' },
                    { rule: 'PERF007', label: 'View without SCHEMABINDING', desc: 'Underlying tables can change — may cause incorrect plans', color: '#0284c7' },
                  ].map(({ rule, label, desc, color }) => {
                    const cnt = allFindings.filter(f => f.rule_id === rule).length
                    return (
                      <div key={rule} className="bg-surface-low rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-mono text-xs text-on-surface-variant">{rule}</span>
                          <span className="text-xl font-bold" style={{ color }}>{cnt}</span>
                        </div>
                        <div className="text-sm font-medium text-on-surface">{label}</div>
                        <div className="text-xs text-on-surface-variant mt-1">{desc}</div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                  Index & Query Findings ({indexFindings.length})
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-low">
                      {['Severity','Rule','Object','Type','Issue'].map(h => (
                        <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {indexFindings.slice(0, 60).map((f, i) => (
                      <tr key={f.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                        <td className="px-4 py-2.5"><SeverityBadge severity={f.severity} /></td>
                        <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{f.rule_id}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{f.object_name}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface-variant">{f.object_type}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface max-w-md truncate">{f.issue}</td>
                      </tr>
                    ))}
                    {indexFindings.length === 0 && (
                      <tr><td colSpan={5} className="px-4 py-8 text-center text-on-surface-variant">No index-related findings in this run.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── DATA SAFETY ──────────────────────────────────────────────── */}
      {tab === 'safety' && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <KpiCard label="Data Safety Issues"  value={safetyFindings.length}  icon="shield"        color="#0284c7" />
            <KpiCard label="High / Critical"      value={safetyFindings.filter(f => ['High','Critical'].includes(f.severity)).length} icon="error" color="#dc2626" />
            <KpiCard label="Null Comparison"      value={allFindings.filter(f => f.rule_id === 'DS001').length} icon="do_not_disturb" color="#f59e0b" />
            <KpiCard label="Type Conversion"      value={allFindings.filter(f => f.rule_id === 'DS002').length} icon="swap_horiz"     color="#8b5cf6" />
          </div>

          {!effectiveRunId ? noRunMsg : (
            <>
              {/* Safety rules breakdown */}
              <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-3">Data Safety Rules</div>
                <div className="grid grid-cols-4 gap-3">
                  {[
                    { rule: 'DS001', label: '= NULL comparison',    desc: 'Always evaluates to false; use IS NULL', color: '#f59e0b' },
                    { rule: 'DS002', label: 'Implicit conversion',  desc: 'Type mismatch causes full table scans',  color: '#0284c7' },
                    { rule: 'DS003', label: 'Division by zero risk', desc: 'No zero-check before division',         color: '#dc2626' },
                    { rule: 'DS006', label: 'String truncation',    desc: 'No length check before string INSERT',  color: '#8b5cf6' },
                  ].map(({ rule, label, desc, color }) => {
                    const cnt = allFindings.filter(f => f.rule_id === rule).length
                    return (
                      <div key={rule} className="bg-surface-low rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-mono text-xs text-on-surface-variant">{rule}</span>
                          <span className="text-xl font-bold" style={{ color }}>{cnt}</span>
                        </div>
                        <div className="text-sm font-medium text-on-surface">{label}</div>
                        <div className="text-xs text-on-surface-variant mt-1">{desc}</div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                  Data Safety Findings ({safetyFindings.length})
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-low">
                      {['Severity','Rule','Object','Type','Issue','Recommendation'].map(h => (
                        <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {safetyFindings.slice(0, 60).map((f, i) => (
                      <tr key={f.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                        <td className="px-4 py-2.5"><SeverityBadge severity={f.severity} /></td>
                        <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{f.rule_id}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{f.object_name}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface-variant">{f.object_type}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface max-w-xs truncate">{f.issue}</td>
                        <td className="px-4 py-2.5 text-xs text-on-surface-variant max-w-xs truncate">{f.recommendation}</td>
                      </tr>
                    ))}
                    {safetyFindings.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant">No data safety findings in this run.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── SCHEMA METADATA ──────────────────────────────────────────── */}
      {tab === 'metadata' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-on-surface">Database Schema Metadata</h2>
              {metadataData?.last_updated && (
                <p className="text-xs text-on-surface-variant mt-1">
                  Last updated: {new Date(metadataData.last_updated).toLocaleString()}
                </p>
              )}
            </div>
            <button
              onClick={handleRefreshMetadata}
              disabled={!selectedDb || refreshingMetadata}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50 bg-blue-600 hover:bg-blue-700"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>refresh</span>
              {refreshingMetadata ? 'Refreshing...' : 'Refresh Metadata'}
            </button>
          </div>

          {metadataSuccess && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-2.5 text-sm text-green-700 flex items-center gap-2">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check_circle</span>
              {metadataSuccess}
            </div>
          )}

          {metadataError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700 flex items-center gap-2">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>error</span>
              {metadataError}
            </div>
          )}

          {!selectedDb ? (
            <div className="bg-amber-50 rounded-xl px-5 py-4 flex items-center gap-3 text-sm text-amber-800">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>info</span>
              <span>Select a database using the <strong>"All Databases"</strong> dropdown in the top bar to view its schema metadata. (QW-7 improved messaging)</span>
            </div>
          ) : metadataData && Object.keys(metadataData.objects || {}).length > 0 ? (
            <div className="grid grid-cols-1 gap-4">
              {Object.entries(metadataData.objects).map(([objType, objects]: [string, any]) => (
                <div key={objType} className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                  <div className="px-5 py-4 text-sm font-semibold text-on-surface flex items-center justify-between"
                       style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                    <span>{objType}s</span>
                    <span className="text-xs font-mono text-on-surface-variant bg-surface-low px-2 py-1 rounded">
                      {objects?.length || 0}
                    </span>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-surface-low">
                        {['Name', 'Schema', 'Last Updated'].map(h => (
                          <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(objects || []).slice(0, 100).map((obj: any, i: number) => (
                        <tr key={`${objType}-${obj.name}`} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                          <td className="px-4 py-2.5 font-mono text-sm text-on-surface">{obj.name}</td>
                          <td className="px-4 py-2.5 text-xs text-on-surface-variant">{obj.schema || 'public'}</td>
                          <td className="px-4 py-2.5 text-xs text-on-surface-variant">
                            {obj.fetched_at ? new Date(obj.fetched_at).toLocaleDateString() : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(objects?.length || 0) > 100 && (
                    <div className="px-5 py-3 text-xs text-on-surface-variant bg-surface-low">
                      Showing 100 of {objects?.length} items
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-surface-lowest rounded-xl p-10 text-center">
              <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 40 }}>table_chart</span>
              <p className="text-sm text-on-surface-variant mt-3">No metadata fetched yet.</p>
              <p className="text-xs text-on-surface-variant mt-1">Click "Refresh Metadata" to fetch schema information from the database.</p>
            </div>
          )}
        </div>
      )}

      {/* ── LIVE METRICS ─────────────────────────────────────────────── */}
      {tab === 'live-metrics' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-on-surface">Real-Time Performance Metrics</h2>
              <p className="text-xs text-on-surface-variant mt-1">
                Capture live metrics: index usage, missing indexes, slow queries, blocking sessions, wait statistics, and table sizes.
              </p>
            </div>
            <button
              onClick={handleCaptureLiveMetrics}
              disabled={!selectedDb || capturingMetrics}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50 bg-blue-600 hover:bg-blue-700"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span>
              {capturingMetrics ? 'Capturing...' : 'Capture Metrics'}
            </button>
          </div>

          {metricsSuccess && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-2.5 text-sm text-green-700 flex items-center gap-2">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check_circle</span>
              {metricsSuccess}
            </div>
          )}

          {metricsError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700 flex items-center gap-2">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>error</span>
              {metricsError}
            </div>
          )}

          {!selectedDb ? (
            <div className="bg-amber-50 rounded-xl px-5 py-4 flex items-center gap-3 text-sm text-amber-800">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>info</span>
              <span>Select a database using the <strong>"All Databases"</strong> dropdown in the top bar to capture live metrics.</span>
            </div>
          ) : (
            <>
              {/* Metric types selector */}
              <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-4">Metric Types to Capture</div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: 'index_usage', label: 'Index Usage', icon: 'filter_list' },
                    { id: 'unused_indexes', label: 'Unused Indexes', icon: 'search_off' },
                    { id: 'missing_indexes', label: 'Missing Indexes', icon: 'add_location' },
                    { id: 'slow_queries', label: 'Slow Queries', icon: 'speed' },
                    { id: 'blocking_sessions', label: 'Blocking Sessions', icon: 'lock' },
                    { id: 'wait_statistics', label: 'Wait Statistics', icon: 'schedule' },
                    { id: 'table_sizes', label: 'Table Sizes', icon: 'table_chart' },
                  ].map(({ id, label, icon }) => (
                    <button
                      key={id}
                      onClick={() => toggleMetricType(id)}
                      className={`flex items-center gap-3 px-4 py-3 rounded-lg border-2 transition ${
                        selectedMetricTypes.includes(id)
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-surface-low bg-surface-low hover:border-surface-low'
                      }`}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                        {selectedMetricTypes.includes(id) ? 'check_circle' : icon}
                      </span>
                      <span className="text-sm font-medium text-on-surface">{label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Live status summary */}
              {liveStatus && !liveStatus.not_supported && (
                <div className="grid grid-cols-3 gap-4">
                  {/* Blocking sessions */}
                  <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-sm font-semibold text-on-surface">Blocking Sessions</div>
                      <span className="text-lg font-bold text-red-600">{liveStatus.blocking_sessions?.length || 0}</span>
                    </div>
                    {liveStatus.blocking_sessions && liveStatus.blocking_sessions.length > 0 ? (
                      <div className="space-y-2 text-xs">
                        {liveStatus.blocking_sessions.slice(0, 5).map((s: any, i: number) => (
                          <div key={i} className="bg-surface-low rounded px-2 py-1.5">
                            <div className="font-mono text-on-surface">Session {s.session_id}</div>
                            <div className="text-on-surface-variant">{s.user_name} • {s.wait_duration_ms}ms</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-on-surface-variant">No blocking sessions detected</p>
                    )}
                  </div>

                  {/* Slow queries */}
                  <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-sm font-semibold text-on-surface">Slow Queries</div>
                      <span className="text-lg font-bold text-amber-600">{liveStatus.slow_queries?.length || 0}</span>
                    </div>
                    {liveStatus.slow_queries && liveStatus.slow_queries.length > 0 ? (
                      <div className="space-y-2 text-xs">
                        {liveStatus.slow_queries.slice(0, 5).map((q: any, i: number) => (
                          <div key={i} className="bg-surface-low rounded px-2 py-1.5">
                            <div className="text-on-surface truncate">{q.query_text}</div>
                            <div className="text-on-surface-variant">{Math.round(q.total_duration_ms)}ms • {q.execution_count}x</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-on-surface-variant">No slow queries detected</p>
                    )}
                  </div>

                  {/* Largest tables */}
                  <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-sm font-semibold text-on-surface">Largest Tables</div>
                      <span className="text-lg font-bold text-blue-600">{liveStatus.largest_tables?.length || 0}</span>
                    </div>
                    {liveStatus.largest_tables && liveStatus.largest_tables.length > 0 ? (
                      <div className="space-y-2 text-xs">
                        {liveStatus.largest_tables.slice(0, 5).map((t: any, i: number) => (
                          <div key={i} className="bg-surface-low rounded px-2 py-1.5">
                            <div className="font-mono text-on-surface">{t.table_name}</div>
                            <div className="text-on-surface-variant">{t.row_count.toLocaleString()} rows • {t.used_mb}MB</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-on-surface-variant">No tables fetched</p>
                    )}
                  </div>
                </div>
              )}

              {liveStatus?.not_supported && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-amber-800 flex items-start gap-3">
                  <span className="material-symbols-outlined" style={{ fontSize: 24 }}>warning</span>
                  <div>
                    <h3 className="font-semibold text-sm">⚠ Not applicable for PostgreSQL</h3>
                    <p className="text-sm mt-1">{liveStatus.reason}</p>
                  </div>
                </div>
              )}

              {!liveStatus && (
                <div className="bg-surface-lowest rounded-xl p-10 text-center">
                  <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 40 }}>trending_up</span>
                  <p className="text-sm text-on-surface-variant mt-3">No metrics captured yet.</p>
                  <p className="text-xs text-on-surface-variant mt-1">Click "Capture Metrics" to fetch real-time performance data from the database.</p>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── TRIGGER LIVE SCAN ────────────────────────────────────────── */}
      {tab === 'trigger' && (
        <div className="space-y-4">
          <div className="grid grid-cols-12 gap-6">
            {/* Config */}
            <div className="col-span-5 space-y-4">
              <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
                <div className="text-sm font-semibold text-on-surface mb-4">Live DMV Scan</div>
                <p className="text-xs text-on-surface-variant mb-4">
                  Triggers a real-time assessment against the selected database using
                  SQL Server DMVs (Dynamic Management Views). Results are saved and appear in the Analysis page.
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Target Database</label>
                    <select
                      value={triggerDb}
                      onChange={e => setTriggerDb(e.target.value)}
                      className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      <option value="">Select database…</option>
                      {dbList.map((db: any) => (
                        <option key={db.id} value={db.name}>{db.name} — {db.host}:{db.port}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-2">
                    {[
                      { label: 'Run DMV checks',       desc: 'Missing indexes, wait stats, top queries', checked: true,  disabled: true  },
                      { label: 'Persist results',       desc: 'Save findings to PostgreSQL',             checked: true,  disabled: true  },
                      { label: 'Generate JSON report',  desc: 'Output report file alongside findings',   checked: true,  disabled: false },
                    ].map(({ label, desc, checked }) => (
                      <label key={label} className="flex items-start gap-3 cursor-pointer">
                        <input type="checkbox" defaultChecked={checked} className="mt-0.5 w-4 h-4 rounded accent-primary" />
                        <div>
                          <div className="text-sm font-medium text-on-surface">{label}</div>
                          <div className="text-xs text-on-surface-variant">{desc}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              <button
                onClick={handleTrigger}
                disabled={!triggerDb || triggering}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-semibold text-white disabled:opacity-50 transition-opacity"
                style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                  {triggering ? 'hourglass_empty' : 'play_arrow'}
                </span>
                {triggering ? 'Triggering scan…' : 'Start Live Scan'}
              </button>

              {triggerResult && (
                <div className="bg-green-50 rounded-xl p-4 space-y-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-success">
                    <span className="material-symbols-outlined" style={{ fontSize: 18 }}>check_circle</span>
                    Scan triggered successfully
                  </div>
                  <div className="text-xs text-on-surface-variant">
                    Job ID: <span className="font-mono">{triggerResult.job_id ?? triggerResult.run_id ?? '—'}</span>
                  </div>
                  <div className="text-xs text-on-surface-variant">
                    Navigate to <strong>Analysis</strong> and select the new run to view results.
                  </div>
                </div>
              )}
              {triggerError && (
                <div className="bg-red-50 rounded-xl p-4 text-sm text-error">{triggerError}</div>
              )}
            </div>

            {/* Recent live runs */}
            <div className="col-span-7 bg-surface-lowest rounded-xl shadow-card overflow-hidden">
              <div className="px-5 py-4 text-sm font-semibold text-on-surface" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                Recent Live Scans
              </div>
              {liveRuns.length === 0 ? (
                <div className="px-5 py-10 text-center">
                  <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 40 }}>sensors</span>
                  <div className="text-sm text-on-surface-variant mt-2">No live DMV scans yet.</div>
                  <div className="text-xs text-on-surface-variant mt-1 opacity-60">File-based runs are shown in Analysis. Trigger a live scan above.</div>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-low">
                      {['Run','Database','Date','Health','Findings','Duration',''].map(h => (
                        <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {liveRuns.map((r: any, i) => {
                      const h  = r.health_score ?? 0
                      const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                      return (
                        <tr key={r.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                          <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">{r.label}</td>
                          <td className="px-4 py-3 text-on-surface">{r.db_name || '—'}</td>
                          <td className="px-4 py-3 text-xs text-on-surface-variant">{new Date(r.timestamp).toLocaleString()}</td>
                          <td className="px-4 py-3 font-semibold" style={{ color: hc }}>{h}%</td>
                          <td className="px-4 py-3 text-on-surface">{r.total_issues}</td>
                          <td className="px-4 py-3 text-xs text-on-surface-variant">{r.duration_sec}s</td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => {
                                setSelectedRunToDelete(r)
                                setDeleteModalOpen(true)
                              }}
                              className="text-on-surface-variant hover:text-error transition-colors p-1"
                              title="Delete run"
                            >
                              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>delete</span>
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {selectedRunToDelete && (
        <DeleteRunModal
          run={selectedRunToDelete}
          isOpen={deleteModalOpen}
          onClose={() => setDeleteModalOpen(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['runs', selectedDb] })
            setSelectedRunToDelete(null)
          }}
        />
      )}
    </div>
  )
}
