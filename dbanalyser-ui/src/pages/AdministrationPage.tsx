import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dbApi, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import PageHeader from '../components/PageHeader'
import TabBar from '../components/TabBar'
import KpiCard from '../components/KpiCard'

const TABS = [
  { id: 'databases', label: 'Databases', icon: 'storage'  },
  { id: 'system',    label: 'System',    icon: 'settings' },
]

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const DB_TYPES = [
  { value: 'mssql', label: 'Microsoft SQL Server' },
  { value: 'oracle', label: 'Oracle Database' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL / MariaDB' },
  { value: 'snowflake', label: 'Snowflake' },
]

function Field({ label, placeholder, value, onChange, type = 'text', required = false }: any) {
  return (
    <div>
      <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">
        {label} {required && <span className="text-error">*</span>}
      </label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20" />
    </div>
  )
}

function Select({ label, value, onChange, options, required = false }: any) {
  return (
    <div>
      <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">
        {label} {required && <span className="text-error">*</span>}
      </label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20">
        {options.map((opt: any) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  )
}

export default function AdministrationPage() {
  const [tab, setTab] = useState('databases')
  const { user }      = useAuth()
  const qc            = useQueryClient()

  // ── Databases ────────────────────────────────────────────────────────────
  const [showAdd,    setShowAdd]    = useState(false)
  const [editingDb,  setEditingDb]  = useState<any | null>(null)
  const [dbForm, setDbForm] = useState({
    id: undefined as number | undefined,
    name: '', db_type: 'mssql', host: '', port: '', username: '', password: '',
    environment: 'development', description: '', use_windows_auth: false,
    oracle_sid_or_service: '', snowflake_warehouse: '', snowflake_role: '',
    database_name: '',
  })
  const [dbError,   setDbError]   = useState('')
  const [dbSuccess, setDbSuccess] = useState('')
  const [testingConnection, setTestingConnection] = useState(false)

  const emptyForm = {
    id: undefined,
    name: '', db_type: 'mssql', host: '', port: '', username: '', password: '',
    environment: 'development', description: '', use_windows_auth: false,
    oracle_sid_or_service: '', snowflake_warehouse: '', snowflake_role: '',
    database_name: '',
  }

  const { data: dbData, refetch: refetchDbs } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data),
  })
  const dbs: any[] = dbData ?? []

  const openEdit = (db: any) => {
    setEditingDb(db)
    setDbForm({
      id:                     db.id,
      name:                   db.name,
      db_type:                db.db_type || 'mssql',
      host:                   db.host,
      port:                   String(db.port || ''),
      username:               db.username || '',
      password:               '',   // never pre-fill; user must re-enter to change
      environment:            db.environment || 'development',
      description:            db.description || '',
      use_windows_auth:       db.use_windows_auth || false,
      oracle_sid_or_service:  db.oracle_sid_or_service || '',
      snowflake_warehouse:    db.snowflake_warehouse || '',
      snowflake_role:         db.snowflake_role || '',
      database_name:          db.database_name || '',
    })
    setShowAdd(true)
    setDbError('')
  }

  const testConnection = async () => {
    setDbError('')
    setTestingConnection(true)
    try {
      const payload: any = {
        name: dbForm.name || 'test',
        db_type: dbForm.db_type,
        host: dbForm.host,
        username: dbForm.username,
        password: dbForm.password,
        environment: dbForm.environment,
        database_name: dbForm.database_name,
        use_windows_auth: dbForm.use_windows_auth,
      }
      if (dbForm.port) payload.port = parseInt(dbForm.port)
      if (dbForm.oracle_sid_or_service) payload.oracle_sid_or_service = dbForm.oracle_sid_or_service
      if (dbForm.snowflake_warehouse) payload.snowflake_warehouse = dbForm.snowflake_warehouse
      if (dbForm.snowflake_role) payload.snowflake_role = dbForm.snowflake_role

      // await api.post('/databases/test-connection', payload)
      await api.post('/databases/validate', payload)
      setDbSuccess('Connection test successful!')
      setTimeout(() => setDbSuccess(''), 4000)
    } catch (e: any) {
      setDbError(e?.response?.data?.detail || 'Connection test failed.')
    } finally {
      setTestingConnection(false)
    }
  }

  const registerDb = async () => {
    setDbError(''); setDbSuccess('')
    try {
      const payload: any = {
        name: dbForm.name,
        db_type: dbForm.db_type,
        host: dbForm.host,
        environment: dbForm.environment,
        description: dbForm.description,
        use_windows_auth: dbForm.use_windows_auth,
        database_name: dbForm.database_name,
      }
      if (dbForm.id) payload.id = dbForm.id
      if (dbForm.port) payload.port = parseInt(dbForm.port)
      if (dbForm.username) payload.username = dbForm.username
      if (dbForm.password) payload.password = dbForm.password
      if (dbForm.oracle_sid_or_service) payload.oracle_sid_or_service = dbForm.oracle_sid_or_service
      if (dbForm.snowflake_warehouse) payload.snowflake_warehouse = dbForm.snowflake_warehouse
      if (dbForm.snowflake_role) payload.snowflake_role = dbForm.snowflake_role

      await api.post('/databases', payload)
      setDbSuccess(`Database "${dbForm.name}" ${editingDb ? 'updated' : 'registered'} successfully.`)
      setShowAdd(false)
      setEditingDb(null)
      setDbForm(emptyForm)
      refetchDbs()
      qc.invalidateQueries({ queryKey: ['databases', false] })
      qc.invalidateQueries({ queryKey: ['databases', true] })
    } catch (e: any) {
      setDbError(e?.response?.data?.detail || 'Registration failed.')
    }
  }

  // Get default port for db_type
  const getDefaultPort = (dbType: string) => {
    const ports: any = {
      'mssql': '1433',
      'oracle': '1521',
      'postgresql': '5432',
      'mysql': '3306',
      'snowflake': '443',
    }
    return ports[dbType] || ''
  }

  const handleDbTypeChange = (newType: string) => {
    const newPort = getDefaultPort(newType)
    setDbForm(p => ({
      ...p,
      db_type: newType,
      port: newPort,
      // Clear type-specific fields when changing db_type
      oracle_sid_or_service: '',
      snowflake_warehouse: '',
      snowflake_role: '',
      use_windows_auth: false,
    }))
  }

  return (
    <div>
      <PageHeader title="Administration" subtitle="Database connections and system configuration" />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* ── Databases ──────────────────────────────────────────────────── */}
      {tab === 'databases' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-4">
              <KpiCard label="Registered" value={dbs.length}                                    icon="storage"      color="#630ed4" />
              <KpiCard label="Active"     value={dbs.filter((d: any) => d.is_active).length}    icon="check_circle" color="#10b981" />
              <KpiCard label="Production" value={dbs.filter((d: any) => d.environment === 'production').length} icon="rocket_launch" color="#dc2626" />
            </div>
            <button
              onClick={() => setShowAdd(!showAdd)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span>
              Register Database
            </button>
          </div>

          {dbSuccess && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-2.5 text-sm text-green-700 flex items-center gap-2">
              <span className="material-symbols-outlined text-success" style={{ fontSize: 16 }}>check_circle</span>
              {dbSuccess}
            </div>
          )}

          {/* Register / Edit form */}
          {showAdd && (
            <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
              <div className="text-sm font-semibold text-on-surface mb-4">{editingDb ? `Edit Database — ${editingDb.name}` : 'Register New Database'}</div>

              {/* DB Type selector */}
              <div className="mb-4">
                <Select
                  label="Database Type"
                  value={dbForm.db_type}
                  onChange={handleDbTypeChange}
                  options={DB_TYPES}
                  required
                />
              </div>

              {/* Basic connection fields */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <Field label="Display Name" placeholder="LTFS"    value={dbForm.name}        onChange={(v: string) => setDbForm(p => ({ ...p, name: v }))} required />
                <Field label="Host / Server" placeholder="localhost"  value={dbForm.host}        onChange={(v: string) => setDbForm(p => ({ ...p, host: v }))} required />
                <Field label="Port" placeholder={getDefaultPort(dbForm.db_type)} value={dbForm.port} onChange={(v: string) => setDbForm(p => ({ ...p, port: v }))} />
              </div>

              {/* MSSQL specific fields */}
              {dbForm.db_type === 'mssql' && (
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <Field label="Database Name" placeholder="master" value={dbForm.database_name} onChange={(v: string) => setDbForm(p => ({ ...p, database_name: v }))} required />
                  <Field label="Username" placeholder="sa" value={dbForm.username} onChange={(v: string) => setDbForm(p => ({ ...p, username: v }))} />
                  <Field label={editingDb ? 'Password (leave blank to keep current)' : 'Password'} placeholder="••••••••" value={dbForm.password} onChange={(v: string) => setDbForm(p => ({ ...p, password: v }))} type="password" />
                  <div className="flex items-end pb-1 col-span-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={dbForm.use_windows_auth}
                        onChange={e => setDbForm(p => ({ ...p, use_windows_auth: e.target.checked }))}
                        className="w-4 h-4 rounded accent-primary" />
                      <span className="text-sm text-on-surface">Use Windows Authentication</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Oracle specific fields */}
              {dbForm.db_type === 'oracle' && (
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <Field label="SID or Service Name" placeholder="ORCL" value={dbForm.oracle_sid_or_service} onChange={(v: string) => setDbForm(p => ({ ...p, oracle_sid_or_service: v }))} required />
                  <Field label="Username" placeholder="sys" value={dbForm.username} onChange={(v: string) => setDbForm(p => ({ ...p, username: v }))} required />
                  <Field label={editingDb ? 'Password (leave blank to keep current)' : 'Password'} placeholder="••••••••" value={dbForm.password} onChange={(v: string) => setDbForm(p => ({ ...p, password: v }))} type="password" required={!editingDb} />
                </div>
              )}

              {/* PostgreSQL specific fields */}
              {dbForm.db_type === 'postgresql' && (
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <Field label="Database Name" placeholder="postgres" value={dbForm.database_name} onChange={(v: string) => setDbForm(p => ({ ...p, database_name: v }))} required />
                  <Field label="Username" placeholder="postgres" value={dbForm.username} onChange={(v: string) => setDbForm(p => ({ ...p, username: v }))} required />
                  <Field label={editingDb ? 'Password (leave blank to keep current)' : 'Password'} placeholder="••••••••" value={dbForm.password} onChange={(v: string) => setDbForm(p => ({ ...p, password: v }))} type="password" />
                </div>
              )}

              {/* MySQL specific fields */}
              {dbForm.db_type === 'mysql' && (
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <Field label="Database Name" placeholder="mysql" value={dbForm.database_name} onChange={(v: string) => setDbForm(p => ({ ...p, database_name: v }))} required />
                  <Field label="Username" placeholder="root" value={dbForm.username} onChange={(v: string) => setDbForm(p => ({ ...p, username: v }))} required />
                  <Field label={editingDb ? 'Password (leave blank to keep current)' : 'Password'} placeholder="••••••••" value={dbForm.password} onChange={(v: string) => setDbForm(p => ({ ...p, password: v }))} type="password" />
                </div>
              )}

              {/* Snowflake specific fields */}
              {dbForm.db_type === 'snowflake' && (
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <Field label="Account ID" placeholder="xy12345" value={dbForm.host} onChange={(v: string) => setDbForm(p => ({ ...p, host: v }))} required />
                  <Field label="Database" placeholder="MY_DATABASE" value={dbForm.database_name} onChange={(v: string) => setDbForm(p => ({ ...p, database_name: v }))} required />
                  <Field label="Warehouse" placeholder="COMPUTE_WH" value={dbForm.snowflake_warehouse} onChange={(v: string) => setDbForm(p => ({ ...p, snowflake_warehouse: v }))} required />
                  <Field label="Username" placeholder="user@company.com" value={dbForm.username} onChange={(v: string) => setDbForm(p => ({ ...p, username: v }))} required />
                  <Field label={editingDb ? 'Password (leave blank to keep current)' : 'Password'} placeholder="••••••••" value={dbForm.password} onChange={(v: string) => setDbForm(p => ({ ...p, password: v }))} type="password" required={!editingDb} />
                  <Field label="Role (optional)" placeholder="ACCOUNTADMIN" value={dbForm.snowflake_role} onChange={(v: string) => setDbForm(p => ({ ...p, snowflake_role: v }))} />
                </div>
              )}

              {/* Environment & description */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <Select
                  label="Environment"
                  value={dbForm.environment}
                  onChange={(v: string) => setDbForm(p => ({ ...p, environment: v }))}
                  options={[
                    { value: 'development', label: 'Development' },
                    { value: 'staging', label: 'Staging' },
                    { value: 'production', label: 'Production' },
                  ]}
                />
                <div className="col-span-2">
                  <Field label="Description" placeholder="e.g., LTFS SQL Server 2022" value={dbForm.description} onChange={(v: string) => setDbForm(p => ({ ...p, description: v }))} />
                </div>
              </div>

              {dbError && (
                <div className="mt-3 text-xs text-error bg-red-50 px-3 py-2 rounded-lg">{dbError}</div>
              )}

              <div className="flex gap-3 mt-4">
                <button onClick={testConnection}
                  disabled={!dbForm.name || !dbForm.host || testingConnection}
                  className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50 bg-blue-600 hover:bg-blue-700">
                  {testingConnection ? 'Testing...' : 'Test Connection'}
                </button>
                <button onClick={registerDb}
                  disabled={!dbForm.name || !dbForm.host}
                  className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}>
                  {editingDb ? 'Save Changes' : 'Register'}
                </button>
                <button onClick={() => { setShowAdd(false); setEditingDb(null); setDbForm(emptyForm); setDbError('') }}
                  className="px-4 py-2 rounded-lg text-sm text-on-surface-variant bg-surface-low">
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* DB table */}
          <div className="bg-surface-lowest rounded-xl shadow-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-low">
                  {['Database','Type','Host','Port','Environment','Status','Health','Last Run','Actions'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-medium text-on-surface-variant uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dbs.map((db: any, i: number) => {
                  const h  = db.last_health ?? 0
                  const hc = h >= 80 ? '#10b981' : h >= 60 ? '#f59e0b' : '#ef4444'
                  const dbType = DB_TYPES.find(t => t.value === (db.db_type || 'mssql'))?.label || db.db_type
                  return (
                    <tr key={db.id} className={i % 2 === 0 ? '' : 'bg-surface/40'}>
                      <td className="px-4 py-3 font-semibold text-on-surface">{db.name}</td>
                      <td className="px-4 py-3 text-xs font-medium text-on-surface-variant">{dbType}</td>
                      <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">{db.host}</td>
                      <td className="px-4 py-3 text-on-surface-variant">{db.port}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs px-2 py-0.5 rounded-md font-medium bg-surface-low text-on-surface-variant capitalize">
                          {db.environment}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                          db.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${db.is_active ? 'bg-green-500' : 'bg-red-500'}`} />
                          {db.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-semibold" style={{ color: hc }}>{h ? `${h}%` : '—'}</td>
                      <td className="px-4 py-3 text-xs text-on-surface-variant">
                        {db.updated_at ? new Date(db.updated_at).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="px-4 py-3 flex items-center gap-2">
                        <button className="text-xs text-primary hover:underline"
                          onClick={() => openEdit(db)}>
                          Edit
                        </button>
                        <button className="text-xs text-error hover:underline"
                          onClick={async () => {
                            if (!confirm(`Remove "${db.name}"? This cannot be undone.`)) return
                            await api.delete(`/databases/${db.name}`)
                            refetchDbs()
                            qc.invalidateQueries({ queryKey: ['databases', false] })
                            qc.invalidateQueries({ queryKey: ['databases', true] })
                          }}>
                          Remove
                        </button>
                        <button className="text-xs text-error hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
                          disabled={db.is_active}
                          title={db.is_active ? 'Activate database first before hard deleting' : 'Permanently delete this database and all its data'}
                          onClick={async () => {
                            if (!confirm(`PERMANENTLY DELETE "${db.name}" and all its data? This action cannot be undone.`)) return
                            try {
                              await api.delete(`/databases/${db.id}/hard-delete`)
                              refetchDbs()
                              qc.invalidateQueries({ queryKey: ['databases', false] })
                              qc.invalidateQueries({ queryKey: ['databases', true] })
                            } catch (e: any) {
                              alert('Failed to delete: ' + (e?.response?.data?.detail || e.message))
                            }
                          }}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {dbs.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-10 text-center">
                      <div className="flex flex-col items-center gap-2 text-on-surface-variant">
                        <span className="material-symbols-outlined opacity-30" style={{ fontSize: 40 }}>storage</span>
                        <span className="text-sm">No databases registered yet.</span>
                        <button onClick={() => setShowAdd(true)} className="text-xs text-primary hover:underline mt-1">
                          Register your first database →
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── System ─────────────────────────────────────────────────────── */}
      {tab === 'system' && (
        <div className="space-y-4">
          {/* Info grid */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'API Backend',         value: API_BASE,                icon: 'api',      color: '#630ed4' },
              { label: 'Application Version', value: '2.0.0',                 icon: 'info',     color: '#0284c7' },
              { label: 'Database Backend',    value: 'PostgreSQL',            icon: 'database', color: '#10b981' },
              { label: 'Auth Mode',           value: user?.username === 'anonymous' ? 'Disabled (open)' : 'JWT Bearer',
                icon: 'lock', color: user?.username === 'anonymous' ? '#f59e0b' : '#10b981' },
              { label: 'Analysis Engine',     value: 'DBAnalyser v2.0',       icon: 'search',   color: '#8b5cf6' },
              { label: 'Rule Engine',         value: 'Custom + Compliance Packs', icon: 'rule', color: '#630ed4' },
            ].map(({ label, value, icon, color }) => (
              <div key={label} className="bg-surface-lowest rounded-xl p-4 shadow-card flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                     style={{ background: `${color}18` }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 20, color }}>{icon}</span>
                </div>
                <div>
                  <div className="text-xs text-on-surface-variant uppercase tracking-wide">{label}</div>
                  <div className="text-sm font-medium text-on-surface mt-0.5 break-all">{value}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Quick actions */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-4">Quick Actions</div>
            <div className="flex flex-wrap gap-3">
              <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-surface-low text-on-surface hover:bg-surface transition-colors">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>open_in_new</span>
                API Swagger Docs
              </a>
              <a href={`${API_BASE}/redoc`} target="_blank" rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-surface-low text-on-surface hover:bg-surface transition-colors">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>description</span>
                ReDoc Reference
              </a>
              <a href={`${API_BASE}/health`} target="_blank" rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-surface-low text-on-surface hover:bg-surface transition-colors">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>monitor_heart</span>
                Health Check
              </a>
              <button onClick={() => { localStorage.clear(); window.location.reload() }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-surface-low text-on-surface hover:bg-surface transition-colors">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>refresh</span>
                Clear Cache & Reload
              </button>
            </div>
          </div>

          {/* Config hints */}
          <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
            <div className="text-sm font-semibold text-on-surface mb-3">Configuration Tips</div>
            <div className="space-y-2 text-xs text-on-surface-variant leading-5">
              <div className="flex items-start gap-2">
                <span className="material-symbols-outlined text-primary mt-0.5" style={{ fontSize: 14 }}>arrow_right</span>
                Multi-DB support: Register Oracle, PostgreSQL, MySQL, and Snowflake databases alongside SQL Server
              </div>
              <div className="flex items-start gap-2">
                <span className="material-symbols-outlined text-primary mt-0.5" style={{ fontSize: 14 }}>arrow_right</span>
                Test connection: Always click "Test Connection" before registering to validate credentials
              </div>
              <div className="flex items-start gap-2">
                <span className="material-symbols-outlined text-primary mt-0.5" style={{ fontSize: 14 }}>arrow_right</span>
                Enable auth: set <code className="bg-surface-low px-1 rounded">auth.enabled: true</code> in <code className="bg-surface-low px-1 rounded">analysis_config.yaml</code>
              </div>
              <div className="flex items-start gap-2">
                <span className="material-symbols-outlined text-primary mt-0.5" style={{ fontSize: 14 }}>arrow_right</span>
                Schedule runner: start the background scheduler with <code className="bg-surface-low px-1 rounded">dbanalyser scheduler</code>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
