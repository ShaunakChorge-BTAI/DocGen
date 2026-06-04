import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dbApi, runApi, schedulesApi } from '../lib/api'
import PageHeader from '../components/PageHeader'
import KpiCard from '../components/KpiCard'

const CRON_PRESETS = [
  { label: 'Daily at midnight',       cron: '0 0 * * *'   },
  { label: 'Every Monday 9am',        cron: '0 9 * * 1'   },
  { label: 'Every 6 hours',           cron: '0 */6 * * *' },
  { label: 'Every Sunday 2am',        cron: '0 2 * * 0'   },
  { label: 'First of month midnight', cron: '0 0 1 * *'   },
]

function Field({ label, placeholder, value, onChange, type = 'text' }: any) {
  return (
    <div>
      <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20" />
    </div>
  )
}

export default function SchedulesPage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd]         = useState(false)
  const [form, setForm]               = useState({ db_name: '', cron: '0 0 * * *', label: '', run_dmv: false })
  const [triggerMsg, setTriggerMsg]   = useState<Record<number, string>>({})

  const { data: schedData, refetch } = useQuery({
    queryKey: ['schedules'],
    queryFn:  () => schedulesApi.list().then(r => r.data),
  })
  const schedules: any[] = schedData ?? []

  const { data: dbData } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data),
  })
  const dbs: any[] = dbData ?? []

  const { data: runData } = useQuery({
    queryKey: ['runs'],
    queryFn:  () => runApi.list().then(r => r.data.runs),
  })
  const runs: any[] = runData ?? []

  const addMutation = useMutation({
    mutationFn: () => schedulesApi.upsert({
      db_name:  form.db_name,
      schedule: form.cron,
      label:    form.label || `${form.db_name} — scheduled run`,
      enabled:  true,
      run_dmv:  form.run_dmv,
      formats:  ['json'],
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] })
      setShowAdd(false)
      setForm({ db_name: '', cron: '0 0 * * *', label: '', run_dmv: false })
    },
  })

  const toggleSched = async (id: number, enabled: boolean) => {
    await schedulesApi.toggle(id, !enabled)
    refetch(); qc.invalidateQueries({ queryKey: ['schedules'] })
  }
  const deleteSched = async (id: number) => {
    if (!confirm('Delete this schedule?')) return
    await schedulesApi.remove(id)
    refetch(); qc.invalidateQueries({ queryKey: ['schedules'] })
  }
  const triggerNow = async (s: any) => {
    setTriggerMsg(m => ({ ...m, [s.id]: 'Triggering…' }))
    try {
      await schedulesApi.trigger(s.id)
      setTriggerMsg(m => ({ ...m, [s.id]: 'Triggered!' }))
      qc.invalidateQueries({ queryKey: ['runs'] })
    } catch (e: any) {
      setTriggerMsg(m => ({ ...m, [s.id]: e?.response?.data?.detail || 'Failed' }))
    }
    setTimeout(() => setTriggerMsg(m => { const n = { ...m }; delete n[s.id]; return n }), 3000)
  }

  return (
    <div>
      <PageHeader
        title="Schedules"
        subtitle="Automate recurring database assessments with cron-based scheduling"
      />

      {/* ── KPI row ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex gap-4">
          <KpiCard label="Schedules"  value={schedules.length}                                icon="schedule"     color="#630ed4" />
          <KpiCard label="Active"     value={schedules.filter((s: any) => s.enabled).length} icon="check_circle" color="#10b981" />
          <KpiCard label="Total Runs" value={runs.length}                                    icon="history" />
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white"
          style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span>
          New Schedule
        </button>
      </div>

      {/* ── Create form ──────────────────────────────────────────────────── */}
      {showAdd && (
        <div className="bg-surface-lowest rounded-xl p-5 shadow-card mb-4 space-y-4">
          <div className="text-sm font-semibold text-on-surface">Create Schedule</div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">Database</label>
              <select value={form.db_name} onChange={e => setForm(p => ({ ...p, db_name: e.target.value }))}
                className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20">
                <option value="">Select database…</option>
                {dbs.map((db: any) => <option key={db.id} value={db.name}>{db.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">Frequency</label>
              <select value={form.cron} onChange={e => setForm(p => ({ ...p, cron: e.target.value }))}
                className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20">
                {CRON_PRESETS.map(p => <option key={p.cron} value={p.cron}>{p.label}</option>)}
              </select>
            </div>
            <Field label="Label" placeholder="Daily health check"
              value={form.label} onChange={(v: string) => setForm(p => ({ ...p, label: v }))} />
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.run_dmv}
                onChange={e => setForm(p => ({ ...p, run_dmv: e.target.checked }))}
                className="w-4 h-4 rounded accent-primary" />
              <span className="text-sm text-on-surface">Include DMV checks (live metrics)</span>
            </label>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => addMutation.mutate()}
              disabled={!form.db_name || !form.cron || addMutation.isPending}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}>
              {addMutation.isPending ? 'Saving…' : 'Save Schedule'}
            </button>
            <button onClick={() => setShowAdd(false)}
              className="px-4 py-2 rounded-lg text-sm text-on-surface-variant bg-surface-low">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── Schedules table ──────────────────────────────────────────────── */}
      {schedules.length === 0 ? (
        <div className="bg-surface-lowest rounded-xl p-12 shadow-card flex flex-col items-center gap-3 text-center">
          <span className="material-symbols-outlined text-on-surface-variant opacity-30" style={{ fontSize: 52 }}>schedule</span>
          <div className="text-sm font-semibold text-on-surface">No schedules configured</div>
          <div className="text-xs text-on-surface-variant opacity-60">
            Click "New Schedule" to automate recurring assessments for your databases.
          </div>
        </div>
      ) : (
        <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden mb-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-low">
                {['Label','Database','Frequency','DMV','Last Run','Next Run','Status','Actions'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {schedules.map((s: any, i: number) => (
                <tr key={s.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                  <td className="px-4 py-3 font-medium text-on-surface">{s.label || '—'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">{s.db_name}</td>
                  <td className="px-4 py-3 text-xs font-mono text-on-surface-variant">
                    {CRON_PRESETS.find(p => p.cron === s.schedule)?.label ?? s.schedule}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${s.run_dmv ? 'bg-primary/10 text-primary' : 'bg-surface-low text-on-surface-variant'}`}>
                      {s.run_dmv ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-on-surface-variant">
                    {s.last_run ? new Date(s.last_run).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-on-surface-variant">
                    {s.next_run ? new Date(s.next_run).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleSched(s.id, s.enabled)}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${
                        s.enabled ? 'bg-green-100 text-green-700' : 'bg-surface-low text-on-surface-variant'
                      }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${s.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
                      {s.enabled ? 'Active' : 'Paused'}
                    </button>
                  </td>
                  <td className="px-4 py-3 flex items-center gap-3">
                    <button onClick={() => triggerNow(s)} disabled={!!triggerMsg[s.id]}
                      className="flex items-center gap-1 text-xs text-primary hover:underline disabled:opacity-60">
                      <span className="material-symbols-outlined" style={{ fontSize: 13 }}>play_arrow</span>
                      {triggerMsg[s.id] || 'Run Now'}
                    </button>
                    <button onClick={() => deleteSched(s.id)} className="text-xs text-error hover:underline">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Recent runs ──────────────────────────────────────────────────── */}
      <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
        <div className="px-5 py-4 text-sm font-semibold text-on-surface"
             style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}>
          Recent Assessment Runs
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-low">
              {['Run','Database','Date','Health','Findings','Duration'].map(h => (
                <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.slice(0, 10).map((r: any, i) => {
              const h  = r.health_score ?? 0
              const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
              return (
                <tr key={r.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                  <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">{r.label}</td>
                  <td className="px-4 py-2.5 text-on-surface">{r.db_name || '—'}</td>
                  <td className="px-4 py-2.5 text-xs text-on-surface-variant">{new Date(r.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2.5 font-semibold" style={{ color: hc }}>{h}%</td>
                  <td className="px-4 py-2.5 text-on-surface">{r.total_issues}</td>
                  <td className="px-4 py-2.5 text-xs text-on-surface-variant">{r.duration_sec ? `${r.duration_sec}s` : '—'}</td>
                </tr>
              )
            })}
            {runs.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant">No runs yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
