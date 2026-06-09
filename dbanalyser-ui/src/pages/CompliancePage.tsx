import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis } from 'recharts'
import { runApi, findingsApi, dbApi } from '../lib/api'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'
import KpiCard from '../components/KpiCard'
import SeverityBadge from '../components/SeverityBadge'

const TABS = [
  { id: 'overview',   label: 'Overview',       icon: 'shield' },
  { id: 'sox',        label: 'SOX',            icon: 'account_balance' },
  { id: 'gdpr',       label: 'GDPR',           icon: 'privacy_tip' },
  { id: 'rbi',        label: 'RBI',            icon: 'currency_rupee' },
  { id: 'security',   label: 'Security',       icon: 'lock' },
  { id: 'dangerous',  label: 'Dangerous SQL',  icon: 'dangerous' },
]

const COMPLIANCE_CATEGORIES = ['Compliance-SOX', 'Compliance-GDPR', 'Compliance-RBI', 'Security', 'Dangerous SQL']

const CAT_META: Record<string, { color: string; icon: string; desc: string }> = {
  'Compliance-SOX': { color: '#630ed4', icon: 'account_balance',  desc: 'Sarbanes-Oxley financial audit controls' },
  'Compliance-GDPR':{ color: '#0284c7', icon: 'privacy_tip',      desc: 'General Data Protection Regulation — PII exposure' },
  'Compliance-RBI': { color: '#f59e0b', icon: 'currency_rupee',   desc: 'Reserve Bank of India data security mandates' },
  'Security':       { color: '#dc2626', icon: 'lock',             desc: 'Hardcoded credentials, SQL injection risks' },
  'Dangerous SQL':  { color: '#b91c1c', icon: 'dangerous',        desc: 'DELETE/TRUNCATE without WHERE, DROP statements' },
}

function FindingsTable({ findings, emptyMsg }: { findings: any[]; emptyMsg: string }) {
  const [expanded, setExpanded] = useState<number | null>(null)
  return (
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
          {findings.length === 0 ? (
            <tr><td colSpan={5} className="px-4 py-10 text-center text-on-surface-variant">{emptyMsg}</td></tr>
          ) : findings.map((f, i) => (
            <React.Fragment key={f.id}>
              <tr
                className={`cursor-pointer ${i % 2 === 0 ? '' : 'bg-surface/40'} hover:bg-primary/5`}
                onClick={() => setExpanded(expanded === f.id ? null : f.id)}
              >
                <td className="px-4 py-2.5"><SeverityBadge severity={f.severity} /></td>
                <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{f.rule_id}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-on-surface font-medium">{f.object_name}</td>
                <td className="px-4 py-2.5 text-xs text-on-surface-variant">{f.object_type}</td>
                <td className="px-4 py-2.5 text-xs text-on-surface max-w-sm truncate">{f.issue}</td>
              </tr>
              {expanded === f.id && (
                <tr className="bg-primary/5">
                  <td colSpan={5} className="px-6 py-4">
                    <div className="space-y-2">
                      <div>
                        <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Issue</span>
                        <p className="text-sm text-on-surface mt-1">{f.issue}</p>
                      </div>
                      <div>
                        <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Recommendation</span>
                        <p className="text-sm text-on-surface mt-1">{f.recommendation}</p>
                      </div>
                      {f.snippet && (
                        <div>
                          <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Code Snippet</span>
                          <pre className="text-xs bg-gray-950 text-green-400 rounded-lg p-3 mt-1 overflow-x-auto font-mono">{f.snippet}</pre>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function CompliancePage() {
  const [tab, setTab] = useState('overview')
  const [selectedDb, setSelectedDb] = useState<string>('')
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [selectedSeverity, setSelectedSeverity] = useState<string>('')

  const { data: dbsData } = useQuery({
    queryKey: ['databases'],
    queryFn: () => dbApi.list().then(r => r.data),
  })
  const databases: any[] = dbsData ?? []

  const { data: runData } = useQuery({
    queryKey: ['runs', selectedDb],
    queryFn:  () => runApi.list(selectedDb || undefined).then(r => {
      let data = r.data;
      if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch(e) {}
      }
      return data?.runs || data || [];
    }),
  })
  const runs = Array.isArray(runData) ? runData : []

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
    queryFn:  async () => {
      const res = await findingsApi.byRun(effectiveRunId!)
      let payload = res.data
      if (typeof payload === 'string') {
        try { payload = JSON.parse(payload) } catch (e) {}
      }
      return payload
    },
    enabled:  !!effectiveRunId,
  })

  let allFindingsRaw: any[] = []
  if (findingsData) {
    if (Array.isArray(findingsData.findings)) {
      allFindingsRaw = findingsData.findings
    } else if (Array.isArray(findingsData)) {
      allFindingsRaw = findingsData
    } else if (Array.isArray(findingsData.runs)) {
      // Unlikely, but if findings api returned runs mistakenly, fallback to empty to avoid crash
      allFindingsRaw = []
    }
  }


  // Filter by severity if selected
  const allFindings = selectedSeverity
    ? allFindingsRaw.filter(f => f.severity === selectedSeverity)
    : allFindingsRaw

  // Remap categories for Dangerous SQL and Security
  const compFindings = allFindings.map(f => {
    if (f.rule_id?.startsWith('DNG')) {
      return { ...f, mapped_category: 'Dangerous SQL' }
    }
    if (f.category === 'Security' || f.rule_id?.startsWith('SEC')) {
      return { ...f, mapped_category: 'Security' }
    }
    return { ...f, mapped_category: f.category }
  }).filter(f => COMPLIANCE_CATEGORIES.includes(f.mapped_category))

  const byCategory   = (cat: string) => compFindings.filter(f => f.mapped_category === cat)

  const soxFindings      = byCategory('Compliance-SOX')
  const gdprFindings     = byCategory('Compliance-GDPR')
  const rbiFindings      = byCategory('Compliance-RBI')
  const securityFindings = byCategory('Security')
  const dangerousFindings= byCategory('Dangerous SQL')

  // Overview chart data
  const overviewData = Object.entries(CAT_META).map(([cat, meta]) => ({
    name: cat.replace('Compliance-','').replace(' SQL',''),
    count: byCategory(cat).length,
    color: meta.color,
  }))

  const sevMap: Record<string, number> = { Critical: 0, High: 0, Medium: 0, Low: 0 }
  compFindings.forEach(f => { sevMap[f.severity] = (sevMap[f.severity] || 0) + 1 })
  const sevData = Object.entries(sevMap).map(([k, v]) => ({ name: k, value: v }))
  const SEV_COLORS: Record<string, string> = { Critical: '#dc2626', High: '#f59e0b', Medium: '#0284c7', Low: '#16a34a' }

  const noRunMsg = 'Select a run from the top bar to see compliance findings.'

  return (
    <div>
      <PageHeader
        title="Compliance"
        subtitle={`${compFindings.length} compliance findings · SOX · GDPR · RBI · Security`}
      />
      {/* Removed top DB, Run, Severity Filter dropdowns as per user request */}

      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* Selectors */}
      <div className="bg-surface-lowest rounded-xl shadow-card p-4 mb-6 mt-4 flex gap-4 items-end">
        <div className="flex-1">
          <label className="text-sm font-medium text-on-surface block mb-1">Select Database</label>
          <select
            value={selectedDb ?? ''}
            onChange={(e) => {
              setSelectedDb(e.target.value)
              setSelectedRun(null)
            }}
            className="w-full bg-surface-low border border-surface-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="">All Databases</option>
            {databases.map(db => (
              <option key={db.name || db.id} value={db.name}>{db.name}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-sm font-medium text-on-surface block mb-1">Select Run</label>
          <select
            value={selectedRun ?? ''}
            onChange={(e) => setSelectedRun(e.target.value ? parseInt(e.target.value) : null)}
            className="w-full bg-surface-low border border-surface-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:ring-2 focus:ring-primary/20"
            disabled={!selectedDb}
          >
            <option value="">Choose a run...</option>
            {runs.length === 0 ? (
              <option disabled>{selectedDb ? 'No runs found' : 'Select a database first'}</option>
            ) : (
              runs.map(run => (
                <option key={run.id} value={run.id}>
                  Run #{run.id} - {run.label} ({run.total_issues} findings)
                </option>
              ))
            )}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-sm font-medium text-on-surface block mb-1">Select Severity</label>
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="w-full bg-surface-low border border-surface-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="">All Severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>

      {tab === 'overview' && (
        <div className="space-y-6">
          {/* KPI row — click each card to jump to that compliance tab */}
          <div className="grid grid-cols-5 gap-4">
            <KpiCard label="Total Compliance" value={compFindings.length}       icon="shield"          color="#630ed4" />
            <KpiCard label="SOX"   value={soxFindings.length}        icon="account_balance" color="#630ed4"
              onClick={() => setTab('sox')}   sub="Click to view" />
            <KpiCard label="GDPR"  value={gdprFindings.length}       icon="privacy_tip"     color="#0284c7"
              onClick={() => setTab('gdpr')}  sub="Click to view" />
            <KpiCard label="RBI"   value={rbiFindings.length}        icon="currency_rupee"  color="#f59e0b"
              onClick={() => setTab('rbi')}   sub="Click to view" />
            <KpiCard label="Security / DNG" value={securityFindings.length + dangerousFindings.length} icon="dangerous" color="#dc2626"
              onClick={() => setTab('security')} sub="Click to view" />
          </div>

          {!effectiveRunId && (
            <div className="bg-amber-50 rounded-xl px-5 py-4 flex items-center gap-3 text-sm text-amber-800">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>info</span>
              {noRunMsg}
            </div>
          )}

          {effectiveRunId && compFindings.length === 0 && (
            <div className="bg-green-50 rounded-xl px-5 py-4 flex items-center gap-3 text-sm text-green-800 mb-2">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>check_circle</span>
              Great! No compliance violations or security issues were found for this database. (Note: The Compliance rule packs may not be applicable to this database type).
            </div>
          )}

          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">Findings by Compliance Category</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={overviewData} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {overviewData.map(entry => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">By Severity</div>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={sevData} cx="50%" cy="50%" innerRadius={45} outerRadius={72} dataKey="value" nameKey="name">
                    {sevData.map(e => <Cell key={e.name} fill={SEV_COLORS[e.name] || '#94a3b8'} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 mt-1">
                {sevData.map(d => (
                  <div key={d.name} className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full" style={{ background: SEV_COLORS[d.name] }} />
                    <span className="text-xs text-on-surface-variant">{d.name}: {d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Full compliance findings table */}
          <FindingsTable
            findings={compFindings}
            emptyMsg={effectiveRunId ? 'No compliance violations found in this run.' : noRunMsg}
          />
        </div>
      )}

      {tab === 'sox' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="SOX Findings" value={soxFindings.length}                                      icon="account_balance" color="#630ed4" />
            <KpiCard label="Critical"     value={soxFindings.filter(f => f.severity === 'Critical').length} icon="error"           color="#dc2626" />
            <KpiCard label="High"         value={soxFindings.filter(f => f.severity === 'High').length}     icon="warning"         color="#f59e0b" />
          </div>
          <div className="bg-amber-50 rounded-xl px-5 py-3 text-sm text-amber-800 flex items-start gap-2">
            <span className="material-symbols-outlined mt-0.5" style={{ fontSize: 16 }}>info</span>
            <span>SOX controls require audit trails, segregation of duties, and financial data integrity. Financial tables must have CreatedBy, ModifiedBy, and timestamp columns.</span>
          </div>
          <FindingsTable findings={soxFindings} emptyMsg={soxFindings.length === 0 ? (effectiveRunId ? 'No SOX violations found in this run.' : noRunMsg) : ''} />
        </div>
      )}

      {tab === 'gdpr' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="GDPR Findings" value={gdprFindings.length}                                       icon="privacy_tip" color="#0284c7" />
            <KpiCard label="Critical"      value={gdprFindings.filter(f => f.severity === 'Critical').length}  icon="error"      color="#dc2626" />
            <KpiCard label="High"          value={gdprFindings.filter(f => f.severity === 'High').length}      icon="warning"    color="#f59e0b" />
          </div>
          <div className="bg-blue-50 rounded-xl px-5 py-3 text-sm text-blue-800 flex items-start gap-2">
            <span className="material-symbols-outlined mt-0.5" style={{ fontSize: 16 }}>privacy_tip</span>
            <span>GDPR requires protection of personally identifiable information (PII). SELECT * on customer/user tables exposes PII columns like email, phone, national ID.</span>
          </div>
          <FindingsTable findings={gdprFindings} emptyMsg={gdprFindings.length === 0 ? (effectiveRunId ? 'No GDPR violations found in this run.' : noRunMsg) : ''} />
        </div>
      )}

      {tab === 'rbi' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="RBI Findings" value={rbiFindings.length}                                        icon="currency_rupee" color="#f59e0b" />
            <KpiCard label="Critical"     value={rbiFindings.filter(f => f.severity === 'Critical').length}   icon="error"          color="#dc2626" />
            <KpiCard label="High"         value={rbiFindings.filter(f => f.severity === 'High').length}       icon="warning"        color="#f59e0b" />
          </div>
          <div className="bg-yellow-50 rounded-xl px-5 py-3 text-sm text-yellow-800 flex items-start gap-2">
            <span className="material-symbols-outlined mt-0.5" style={{ fontSize: 16 }}>currency_rupee</span>
            <span>RBI mandates encryption of transaction amounts and sensitive financial data. ENCRYPTBYKEY must be used for monetary columns in NBFC/banking systems.</span>
          </div>
          <FindingsTable findings={rbiFindings} emptyMsg={rbiFindings.length === 0 ? (effectiveRunId ? 'No RBI violations found in this run.' : noRunMsg) : ''} />
        </div>
      )}

      {tab === 'security' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="Security Findings"  value={securityFindings.length}                                        icon="lock"   color="#dc2626" />
            <KpiCard label="Critical"           value={securityFindings.filter(f => f.severity === 'Critical').length}  icon="error"  color="#dc2626" />
            <KpiCard label="High"               value={securityFindings.filter(f => f.severity === 'High').length}      icon="warning" color="#f59e0b" />
          </div>
          <div className="bg-red-50 rounded-xl px-5 py-3 text-sm text-red-800 flex items-start gap-2">
            <span className="material-symbols-outlined mt-0.5" style={{ fontSize: 16 }}>lock</span>
            <span>Security findings include hardcoded connection strings, credentials in procedure bodies, and SQL injection vulnerabilities. These require immediate remediation.</span>
          </div>
          <FindingsTable findings={securityFindings} emptyMsg={securityFindings.length === 0 ? (effectiveRunId ? 'No security findings in this run.' : noRunMsg) : ''} />
        </div>
      )}

      {tab === 'dangerous' && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="Dangerous SQL"  value={dangerousFindings.length}                                         icon="dangerous" color="#b91c1c" />
            <KpiCard label="Critical"       value={dangerousFindings.filter(f => f.severity === 'Critical').length}   icon="error"     color="#dc2626" />
            <KpiCard label="High"           value={dangerousFindings.filter(f => f.severity === 'High').length}       icon="warning"   color="#f59e0b" />
          </div>
          <div className="bg-red-50 rounded-xl px-5 py-3 text-sm text-red-800 flex items-start gap-2">
            <span className="material-symbols-outlined mt-0.5" style={{ fontSize: 16 }}>dangerous</span>
            <span>Dangerous SQL patterns include DELETE/UPDATE without WHERE clauses, TRUNCATE TABLE, DROP statements, and unbounded bulk operations that can cause catastrophic data loss.</span>
          </div>
          <FindingsTable findings={dangerousFindings} emptyMsg={dangerousFindings.length === 0 ? (effectiveRunId ? 'No dangerous SQL patterns found in this run.' : noRunMsg) : ''} />
        </div>
      )}
    </div>
  )
}
