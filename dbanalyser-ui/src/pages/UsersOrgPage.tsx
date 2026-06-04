import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, dbApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import PageHeader from '../components/PageHeader'
import KpiCard from '../components/KpiCard'

function Field({ label, placeholder, value, onChange, type = 'text' }: any) {
  return (
    <div>
      <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20" />
    </div>
  )
}

export default function UsersOrgPage() {
  const { user, logout } = useAuth()

  const { data: dbData } = useQuery({
    queryKey: ['databases', false],
    queryFn:  () => dbApi.list(false).then(r => r.data),
  })
  const dbs: any[] = dbData ?? []

  // Invite
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole,  setInviteRole]  = useState('analyst')
  const [inviteMsg,   setInviteMsg]   = useState('')

  const sendInvite = async () => {
    setInviteMsg('')
    try {
      await api.post('/auth/invite', { email: inviteEmail, role: inviteRole })
      setInviteMsg(`Invitation sent to ${inviteEmail}`)
      setInviteEmail('')
    } catch (e: any) {
      setInviteMsg(e?.response?.data?.detail || 'Failed to send invite. Auth may be disabled.')
    }
  }

  // Change password
  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNew,     setPwNew]     = useState('')
  const [pwConfirm, setPwConfirm] = useState('')
  const [pwMsg,     setPwMsg]     = useState('')

  const changePassword = async () => {
    setPwMsg('')
    if (pwNew !== pwConfirm) { setPwMsg('New passwords do not match.'); return }
    try {
      await api.post('/auth/change-password', { current_password: pwCurrent, new_password: pwNew })
      setPwMsg('Password changed successfully.')
      setPwCurrent(''); setPwNew(''); setPwConfirm('')
    } catch (e: any) {
      setPwMsg(e?.response?.data?.detail || 'Failed. Auth may be disabled in config.')
    }
  }

  const authEnabled = user?.username !== 'anonymous'

  return (
    <div>
      <PageHeader
        title="Users & Organisation"
        subtitle="Manage team members, roles, and organisation settings"
      />

      {/* ── Auth-disabled banner ─────────────────────────────────────────── */}
      {!authEnabled && (
        <div className="mb-5 bg-amber-50 rounded-xl px-5 py-4 flex items-start gap-3 border border-amber-200">
          <span className="material-symbols-outlined text-amber-600 mt-0.5" style={{ fontSize: 18 }}>info</span>
          <div className="text-sm text-amber-800">
            Authentication is currently <strong>disabled</strong>.
            Set <code className="bg-amber-100 px-1 rounded">auth.enabled: true</code> in{' '}
            <code className="bg-amber-100 px-1 rounded">analysis_config.yaml</code> and restart the API
            to enable user invitations and password management.
          </div>
        </div>
      )}

      {/* ── KPI row ──────────────────────────────────────────────────────── */}
      <div className="flex gap-4 mb-5">
        <KpiCard label="Auth Mode"    value={authEnabled ? 'JWT Enabled' : 'Disabled'}  icon="lock"    color={authEnabled ? '#10b981' : '#f59e0b'} />
        <KpiCard label="Current Role" value={user?.role ?? 'admin'}                     icon="badge"   color="#630ed4" />
        <KpiCard label="Databases"    value={dbs.length}                                icon="storage" />
      </div>

      {/* ── Current user card ────────────────────────────────────────────── */}
      <div className="bg-surface-lowest rounded-xl p-5 shadow-card mb-4">
        <div className="text-sm font-semibold text-on-surface mb-4">Logged-in User</div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-xl font-bold flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #630ed4, #7c3aed)' }}>
              {(user?.username?.[0] ?? 'A').toUpperCase()}
            </div>
            <div>
              <div className="text-lg font-semibold text-on-surface">{user?.username ?? 'anonymous'}</div>
              <div className="text-sm text-on-surface-variant">{user?.email || 'No email configured'}</div>
              <span className="inline-flex items-center mt-1 px-2 py-0.5 rounded-md text-xs font-medium bg-primary/10 text-primary">
                {user?.role ?? 'admin'}
              </span>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-surface-low text-on-surface hover:bg-red-50 hover:text-error transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>logout</span>
            Sign Out
          </button>
        </div>
      </div>

      {/* ── Invite + Password grid ───────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Invite user */}
        <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>person_add</span>
            <div className="text-sm font-semibold text-on-surface">Invite Team Member</div>
          </div>
          <div className="space-y-3">
            <Field label="Email Address" placeholder="colleague@ltfs.com"
              value={inviteEmail} onChange={setInviteEmail} type="email" />
            <div>
              <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1 block">Role</label>
              <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
                className="w-full bg-surface-low rounded-lg px-3 py-2 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20">
                <option value="viewer">Viewer — read-only access</option>
                <option value="analyst">Analyst — view + run assessments</option>
                <option value="admin">Admin — full access</option>
              </select>
            </div>
            {inviteMsg && (
              <div className={`text-xs px-3 py-2 rounded-lg ${
                inviteMsg.includes('sent') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-error'
              }`}>{inviteMsg}</div>
            )}
            <button onClick={sendInvite} disabled={!inviteEmail || !authEnabled}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}>
              Send Invitation
            </button>
            {!authEnabled && (
              <p className="text-xs text-amber-700 opacity-80 flex items-center gap-1">
                <span className="material-symbols-outlined" style={{ fontSize: 12 }}>lock</span>
                Enable auth in config to use invitations
              </p>
            )}
          </div>
        </div>

        {/* Change password */}
        <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>key</span>
            <div className="text-sm font-semibold text-on-surface">Change Password</div>
          </div>
          <div className="space-y-3">
            <Field label="Current Password" placeholder="••••••••" value={pwCurrent} onChange={setPwCurrent} type="password" />
            <Field label="New Password"      placeholder="••••••••" value={pwNew}     onChange={setPwNew}     type="password" />
            <Field label="Confirm Password"  placeholder="••••••••" value={pwConfirm} onChange={setPwConfirm} type="password" />
            {pwMsg && (
              <div className={`text-xs px-3 py-2 rounded-lg ${
                pwMsg.includes('success') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-error'
              }`}>{pwMsg}</div>
            )}
            <button onClick={changePassword}
              disabled={!pwCurrent || !pwNew || !pwConfirm || !authEnabled}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}>
              Update Password
            </button>
          </div>
        </div>
      </div>

      {/* ── Organisation info ────────────────────────────────────────────── */}
      <div className="bg-surface-lowest rounded-xl p-5 shadow-card">
        <div className="flex items-center gap-2 mb-4">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>domain</span>
          <div className="text-sm font-semibold text-on-surface">Organisation</div>
        </div>
        <div className="grid grid-cols-4 gap-6 text-sm">
          <div>
            <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Org ID</div>
            <div className="font-mono text-on-surface">{user?.org_id ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Auth Mode</div>
            <div className="text-on-surface">{authEnabled ? 'JWT Bearer' : 'Disabled'}</div>
          </div>
          <div>
            <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Registered DBs</div>
            <div className="text-on-surface font-semibold">{dbs.length}</div>
          </div>
          <div>
            <div className="text-xs text-on-surface-variant uppercase tracking-wide mb-1">Product</div>
            <div className="text-on-surface">DBAnalyser v2.0</div>
          </div>
        </div>

        {/* Role matrix */}
        <div className="mt-5 pt-4" style={{ borderTop: '1px solid rgba(74,68,85,0.08)' }}>
          <div className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-3">Role Permissions</div>
          <div className="overflow-x-auto">
            <table className="text-xs w-full">
              <thead>
                <tr className="bg-surface-low">
                  {['Permission', 'Viewer', 'Analyst', 'Admin'].map(h => (
                    <th key={h} className="text-left px-3 py-2 font-medium text-on-surface-variant">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ['View findings & reports',   true,  true,  true ],
                  ['Run assessments',            false, true,  true ],
                  ['Download reports',           false, true,  true ],
                  ['Register / remove databases',false, false, true ],
                  ['Manage schedules',           false, false, true ],
                  ['Invite team members',        false, false, true ],
                  ['System administration',      false, false, true ],
                ].map(([perm, viewer, analyst, admin]) => (
                  <tr key={perm as string} style={{ borderBottom: '1px solid rgba(74,68,85,0.06)' }}>
                    <td className="px-3 py-2 text-on-surface">{perm}</td>
                    {[viewer, analyst, admin].map((v, i) => (
                      <td key={i} className="px-3 py-2">
                        <span className={`material-symbols-outlined ${v ? 'text-success' : 'text-on-surface-variant opacity-30'}`}
                              style={{ fontSize: 14 }}>
                          {v ? 'check_circle' : 'cancel'}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
