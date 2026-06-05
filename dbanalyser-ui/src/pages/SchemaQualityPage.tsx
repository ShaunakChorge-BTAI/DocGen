import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api, dbApi, findingsApi } from '../lib/api'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'
import KpiCard from '../components/KpiCard'
import SeverityBadge from '../components/SeverityBadge'

const TABS = [
  { id: 'overview',  label: 'Overview',          icon: 'schema' },
  { id: 'issues',    label: 'Quality Issues',    icon: 'warning' },  // PHASE 1: Merged all issue tabs here
]

const schemaApi = {
  list: (params: Record<string, any>) =>
    api.get('/schema/', { params }).then(r => r.data as { objects: any[]; total: number }),
  summary: () => api.get('/schema/summary').then(r => r.data),
}

export default function SchemaQualityPage() {
  const [tab, setTab]         = useState('overview')
  const [dbFilter, setDbFilter] = useState<string>('')
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [issueTypeFilter, setIssueTypeFilter] = useState<'all' | 'pk' | 'indexes' | 'columns' | 'orphans'>('all')

  // All registered databases for the filter dropdown
  const { data: dbListData } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data),
  })
  const dbList: any[] = dbListData ?? []

  // Resolve selected db name → numeric db_registry_id for schema API
  const selectedDbEntry = dbList.find((d: any) => d.name === dbFilter)
  const dbRegistryId: number | null = selectedDbEntry?.id ?? null

  // Schema summary (object counts) — filtered by db_registry_id
  const { data: effectiveSummary } = useQuery({
    queryKey: ['schema-summary', dbRegistryId],
    queryFn:  () => api.get('/schema/summary', { params: dbRegistryId ? { db_registry_id: dbRegistryId } : {} }).then(r => r.data),
  })

  // All schema objects — pass db_registry_id when filter active
  const { data: schemaData } = useQuery({
    queryKey: ['schema-objects', dbRegistryId],
    queryFn:  () => schemaApi.list({ limit: 2000, ...(dbRegistryId ? { db_registry_id: dbRegistryId } : {}) }),
  })
  const allObjects: any[] = schemaData?.objects ?? []

  // Schema-related findings — use run scoped to dbFilter
  const { data: runData } = useQuery({
    queryKey: ['runs', dbFilter],
    queryFn:  () => api.get<{ runs: any[] }>('/runs', { params: dbFilter ? { db_name: dbFilter } : {} })
                       .then(r => r.data.runs),
  })
  const runs = runData ?? []

  // Auto-select first run if none selected
  useEffect(() => {
    if (runs.length > 0 && selectedRun === null) {
      setSelectedRun(runs[0].id)
    } else if (runs.length === 0 && selectedRun !== null) {
      setSelectedRun(null)
    }
  }, [runs, selectedRun])

  const effectiveRunId = selectedRun ?? runs[0]?.id ?? null

  const { data: findingsData } = useQuery({
    queryKey: ['findings', effectiveRunId],
    queryFn:  () => findingsApi.byRun(effectiveRunId!).then(r => r.data),
    enabled:  !!effectiveRunId,
  })
  const allFindings: any[] = findingsData?.findings ?? []

  // ── Derived data ──────────────────────────────────────────────────────────

  // Tables without PK — schema objects of type 'table' where no column has is_primary_key
  const tableNames = [...new Set(allObjects.filter(o => o.object_type === 'table').map(o => o.object_name))]
  const pkTables   = new Set(allObjects.filter(o => o.is_primary_key).map(o => o.parent_name))
  const tablesNoPK = tableNames.filter(t => !pkTables.has(t))

  // Index / performance findings
  const perfFindings  = allFindings.filter(f => f.category === 'Performance')
  const indexFindings = perfFindings.filter(f =>
    f.rule_id?.startsWith('IDX') || f.issue?.toLowerCase().includes('index')
  )
  const selectStarFindings = perfFindings.filter(f => f.rule_id === 'PER001' || f.issue?.includes('SELECT *'))

  // Column type analysis from schema objects
  const columnObjects = allObjects.filter(o => o.object_type === 'column')
  const typeMap: Record<string, string[]> = {}
  columnObjects.forEach(c => {
    if (!typeMap[c.object_name]) typeMap[c.object_name] = []
    if (c.data_type && !typeMap[c.object_name].includes(c.data_type)) {
      typeMap[c.object_name].push(c.data_type)
    }
  })
  const typeMismatches = Object.entries(typeMap)
    .filter(([, types]) => types.length > 1)
    .map(([col, types]) => ({ column: col, types: types.join(', '), count: types.length }))

  // Orphan detection — objects referenced in findings as orphan/unused
  const orphanFindings = allFindings.filter(f =>
    f.category === 'Maintainability' || f.rule_id?.startsWith('MNT') ||
    f.issue?.toLowerCase().includes('unused') || f.issue?.toLowerCase().includes('orphan')
  )

  // Overview stats
  let objCounts = effectiveSummary?.counts ?? {}
  let objChartData = Object.entries(objCounts).map(([k, v]) => ({ name: k, count: v as number }))

  if (objChartData.length === 0 && allObjects.length > 0) {
    const counts: Record<string, number> = {}
    allObjects.forEach(o => {
      counts[o.object_type] = (counts[o.object_type] || 0) + 1
    })
    objCounts = counts
    objChartData = Object.entries(counts).map(([k, v]) => ({ name: k, count: v }))
  }

  const totalObjects = (effectiveSummary?.total ?? Object.values(objCounts).reduce((a: any, b: any) => a + b, 0)) || allObjects.length

  // Run object count for subtitle (from actual run, more accurate than schema_objects)
  const currentRun = runData?.[0]
  const runObjectCount = currentRun?.total_objects ?? allObjects.length

  return (
    <div>
      <PageHeader
        title="Schema Quality"
        subtitle={`${runObjectCount} objects · ${effectiveRunId ? `Run #${effectiveRunId}` : 'Select a run'}${dbFilter ? ` · ${dbFilter}` : ''}`}
      />

      {/* ── DB & Run Filter dropdowns ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-6 mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xs text-on-surface-variant font-medium uppercase tracking-wide">Database:</span>
          <select
            value={dbFilter}
            onChange={(e) => {
              setDbFilter(e.target.value)
              setSelectedRun(null) // Reset run when DB changes
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
            disabled={!dbFilter}
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

      {tab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-5 gap-4">
            <KpiCard label="Total Objects"   value={totalObjects} icon="layers"     color="#630ed4" />
            <KpiCard label="Tables"          value={objCounts.table ?? 0}                 icon="table_chart" />
            <KpiCard label="Procedures"      value={objCounts.procedure ?? 0}             icon="code" />
            <KpiCard label="Views"           value={objCounts.view ?? 0}                  icon="view_list" />
            <KpiCard label="Functions"       value={objCounts.function ?? 0}              icon="functions" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">Objects by Type</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={objChartData}>
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">Quality Issues Summary</div>
              {!effectiveRunId ? (
                <div className="bg-amber-50 rounded-lg p-4 text-sm text-amber-700">
                  Run an assessment to see quality data.
                </div>
              ) : (
                <div className="space-y-3 mt-2">
                  {[
                    { label: 'Tables without Primary Key', count: tablesNoPK.length, color: '#dc2626', icon: 'key_off' },
                    { label: 'Performance Issues (SELECT *, missing indexes)', count: perfFindings.length, color: '#f59e0b', icon: 'speed' },
                    { label: 'Column Type Mismatches', count: typeMismatches.length, color: '#0284c7', icon: 'table_chart' },
                    { label: 'Maintainability / Orphan Issues', count: orphanFindings.length, color: '#8b5cf6', icon: 'device_hub' },
                  ].map(item => (
                    <div key={item.label} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined" style={{ fontSize: 16, color: item.color }}>{item.icon}</span>
                        <span className="text-sm text-on-surface">{item.label}</span>
                      </div>
                      <span className="text-sm font-bold" style={{ color: item.color }}>{item.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Object browser */}
          <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
            <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
              <div className="text-sm font-semibold text-on-surface">Schema Objects</div>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-low">
                  {['Type','Schema','Object','Parent','Data Type','PK','FK'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allObjects.slice(0, 50).map((o, i) => (
                  <tr key={o.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                    <td className="px-4 py-2">
                      <span className="text-xs px-2 py-0.5 rounded-md font-medium" style={{ background: '#7c3aed18', color: '#7c3aed' }}>{o.object_type}</span>
                    </td>
                    <td className="px-4 py-2 text-xs text-on-surface-variant">{o.schema_name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-on-surface">{o.object_name}</td>
                    <td className="px-4 py-2 text-xs text-on-surface-variant">{o.parent_name || '—'}</td>
                    <td className="px-4 py-2 text-xs text-on-surface-variant">{o.data_type || '—'}</td>
                    <td className="px-4 py-2">
                      {o.is_primary_key && <span className="text-xs text-success font-medium">PK</span>}
                    </td>
                    <td className="px-4 py-2">
                      {o.is_foreign_key && <span className="text-xs text-primary font-medium">FK</span>}
                    </td>
                  </tr>
                ))}
                {allObjects.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-on-surface-variant">No schema objects indexed. Run an assessment first.</td></tr>
                )}
              </tbody>
            </table>
            {allObjects.length > 50 && (
              <div className="px-4 py-2 text-xs text-on-surface-variant bg-surface-low">Showing 50 of {allObjects.length} objects</div>
            )}
          </div>
        </div>
      )}

      {/* PHASE 1: Consolidated Quality Issues tab (merged from pk, indexes, columns, orphans) */}
      {tab === 'issues' && (
        <div className="space-y-4">
          {/* Issue type filter buttons */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setIssueTypeFilter('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                issueTypeFilter === 'all'
                  ? 'text-white'
                  : 'bg-surface-low text-on-surface-variant hover:bg-surface'
              }`}
              style={issueTypeFilter === 'all' ? { background: 'linear-gradient(135deg, #630ed4, #7c3aed)' } : {}}
            >
              All Issues
            </button>
            <button
              onClick={() => setIssueTypeFilter('pk')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                issueTypeFilter === 'pk'
                  ? 'text-white'
                  : 'bg-surface-low text-on-surface-variant hover:bg-surface'
              }`}
              style={issueTypeFilter === 'pk' ? { background: '#dc2626' } : {}}
            >
              Primary Keys ({tablesNoPK.length})
            </button>
            <button
              onClick={() => setIssueTypeFilter('indexes')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                issueTypeFilter === 'indexes'
                  ? 'text-white'
                  : 'bg-surface-low text-on-surface-variant hover:bg-surface'
              }`}
              style={issueTypeFilter === 'indexes' ? { background: '#f59e0b' } : {}}
            >
              Performance ({perfFindings.length})
            </button>
            <button
              onClick={() => setIssueTypeFilter('columns')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                issueTypeFilter === 'columns'
                  ? 'text-white'
                  : 'bg-surface-low text-on-surface-variant hover:bg-surface'
              }`}
              style={issueTypeFilter === 'columns' ? { background: '#8b5cf6' } : {}}
            >
              Column Types ({typeMismatches.length})
            </button>
            <button
              onClick={() => setIssueTypeFilter('orphans')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                issueTypeFilter === 'orphans'
                  ? 'text-white'
                  : 'bg-surface-low text-on-surface-variant hover:bg-surface'
              }`}
              style={issueTypeFilter === 'orphans' ? { background: '#0284c7' } : {}}
            >
              Maintainability ({orphanFindings.length})
            </button>
          </div>

          {/* PK Issues */}
          {(issueTypeFilter === 'all' || issueTypeFilter === 'pk') && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: '#dc2626' }}>key_off</span>
                Primary Key Issues ({tablesNoPK.length})
              </h3>
              {tablesNoPK.length === 0 ? (
                <div className="bg-green-50 rounded-lg p-4 text-sm text-green-700">✓ All tables have primary keys defined.</div>
              ) : (
                <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-surface-low">
                        {['Table','Columns','Recommendation'].map(h => (
                          <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {tablesNoPK.map((t, i) => {
                        const cols = columnObjects.filter(c => c.parent_name === t)
                        return (
                          <tr key={t} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                            <td className="px-4 py-2.5 font-mono text-sm text-on-surface font-medium">{t}</td>
                            <td className="px-4 py-2.5 text-xs text-on-surface-variant">{cols.length} cols</td>
                            <td className="px-4 py-2.5 text-xs text-on-surface-variant">Add PRIMARY KEY constraint or IDENTITY column</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Performance Issues */}
          {(issueTypeFilter === 'all' || issueTypeFilter === 'indexes') && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: '#f59e0b' }}>speed</span>
                Performance Issues ({perfFindings.length})
              </h3>
              {effectiveRunId ? (
                perfFindings.length === 0 ? (
                  <div className="bg-green-50 rounded-lg p-4 text-sm text-green-700">✓ No performance issues detected.</div>
                ) : (
                  <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-surface-low">
                          {['Severity','Rule','Object','Issue'].map(h => (
                            <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {perfFindings.slice(0, 20).map((f, i) => (
                          <tr key={f.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                            <td className="px-4 py-2.5"><SeverityBadge severity={f.severity} /></td>
                            <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{f.rule_id}</td>
                            <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{f.object_name}</td>
                            <td className="px-4 py-2.5 text-xs text-on-surface max-w-xs truncate">{f.issue}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              ) : (
                <div className="bg-amber-50 rounded-lg p-4 text-sm text-amber-700">Select a run from the top bar to see performance findings.</div>
              )}
            </div>
          )}

          {/* Column Type Issues */}
          {(issueTypeFilter === 'all' || issueTypeFilter === 'columns') && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: '#8b5cf6' }}>table_chart</span>
                Column Type Mismatches ({typeMismatches.length})
              </h3>
              {typeMismatches.length === 0 ? (
                <div className="bg-green-50 rounded-lg p-4 text-sm text-green-700">✓ No column type mismatches detected.</div>
              ) : (
                <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-surface-low">
                        {['Column','Types Found','Risk'].map(h => (
                          <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {typeMismatches.map((m, i) => (
                        <tr key={m.column} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                          <td className="px-4 py-2.5 font-mono text-sm text-on-surface font-medium">{m.column}</td>
                          <td className="px-4 py-2.5 text-xs text-on-surface-variant">{m.types}</td>
                          <td className="px-4 py-2.5">
                            <SeverityBadge severity={m.count >= 3 ? 'High' : 'Medium'} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Maintainability Issues */}
          {(issueTypeFilter === 'all' || issueTypeFilter === 'orphans') && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: '#0284c7' }}>device_hub</span>
                Maintainability & Orphan Issues ({orphanFindings.length})
              </h3>
              {effectiveRunId ? (
                orphanFindings.length === 0 ? (
                  <div className="bg-green-50 rounded-lg p-4 text-sm text-green-700">✓ No maintainability issues found.</div>
                ) : (
                  <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-surface-low">
                          {['Severity','Rule','Object','Type','Issue'].map(h => (
                            <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {orphanFindings.slice(0, 20).map((f, i) => (
                          <tr key={f.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                            <td className="px-4 py-2.5"><SeverityBadge severity={f.severity} /></td>
                            <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{f.rule_id}</td>
                            <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{f.object_name}</td>
                            <td className="px-4 py-2.5 text-xs text-on-surface-variant">{f.object_type}</td>
                            <td className="px-4 py-2.5 text-xs text-on-surface max-w-xs truncate">{f.issue}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              ) : (
                <div className="bg-amber-50 rounded-lg p-4 text-sm text-amber-700">Select a run from the top bar to see maintainability findings.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
