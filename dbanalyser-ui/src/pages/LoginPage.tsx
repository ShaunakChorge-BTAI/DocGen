import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { authApi } from '../lib/api'

type Tab = 'signin' | 'register'

export default function LoginPage() {
  const { login, loginAsGuest, isAuthDisabled } = useAuth()
  const nav = useNavigate()
  const [tab, setTab] = useState<Tab>('signin')

  // Sign in state
  const [username, setUsername]   = useState('')
  const [password, setPassword]   = useState('')

  // Register state
  const [orgName, setOrgName]     = useState('')
  const [regUser, setRegUser]     = useState('')
  const [regEmail, setRegEmail]   = useState('')
  const [regPass, setRegPass]     = useState('')
  const [regPass2, setRegPass2]   = useState('')

  const [error, setError]         = useState('')
  const [success, setSuccess]     = useState('')
  const [loading, setLoading]     = useState(false)

  const handleGuestLogin = () => {
    loginAsGuest()
    nav('/dashboard')
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      nav('/dashboard')
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(detail || 'Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (regPass !== regPass2) { setError('Passwords do not match.'); return }
    if (!orgName || !regUser || !regEmail || !regPass) { setError('All fields are required.'); return }
    setLoading(true)
    try {
      const r = await authApi.register(orgName, regUser, regEmail, regPass)
      // Auto-login with returned token
      localStorage.setItem('token', r.data.access_token)
      window.location.href = '/dashboard'
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(detail || 'Registration failed. Organisation may already exist.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      {/* Background gradient blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #7c3aed, transparent)' }} />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #630ed4, transparent)' }} />
      </div>

      <div className="w-full max-w-sm relative">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex w-14 h-14 rounded-2xl items-center justify-center mb-4"
            style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}>
            <span className="material-symbols-outlined text-white" style={{ fontSize: 28 }}>database</span>
          </div>
          <h1 className="text-2xl font-bold text-on-surface" style={{ letterSpacing: '-0.02em' }}>DBAnalyser</h1>
          <p className="text-sm text-on-surface-variant mt-1">SQL Server Intelligence Platform</p>
        </div>

        {/* Card */}
        <div className="bg-surface-lowest rounded-2xl shadow-float overflow-hidden">
          {/* Tab switcher */}
          <div className="flex border-b" style={{ borderColor: 'rgba(74,68,85,0.10)' }}>
            {(['signin', 'register'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(''); setSuccess('') }}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === t
                    ? 'border-primary text-primary'
                    : 'border-transparent text-on-surface-variant hover:text-on-surface'
                }`}
              >
                {t === 'signin' ? 'Sign In' : 'New Organisation'}
              </button>
            ))}
          </div>

          <div className="p-8">
            {/* ── SIGN IN ── */}
            {tab === 'signin' && (
              <form onSubmit={handleLogin} className="space-y-4">

                {/* Auth-disabled dev-mode banner */}
                {isAuthDisabled && (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 space-y-3">
                    <div className="flex items-start gap-2">
                      <span className="material-symbols-outlined text-amber-600 flex-shrink-0" style={{ fontSize: 18 }}>
                        warning
                      </span>
                      <div>
                        <p className="text-xs font-semibold text-amber-800">Authentication is disabled</p>
                        <p className="text-xs text-amber-700 mt-0.5">
                          <code className="font-mono">auth.enabled: false</code> is set in config.
                          You may proceed without credentials or enable auth for production use.
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleGuestLogin}
                      className="w-full py-2 rounded-lg text-xs font-semibold text-white flex items-center justify-center gap-2"
                      style={{ background: 'linear-gradient(135deg, #d97706 0%, #f59e0b 100%)' }}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 15 }}>shield_person</span>
                      Continue as Admin (Dev Mode)
                    </button>
                  </div>
                )}

                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Username</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter username"
                    autoFocus={!isAuthDisabled}
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                {error && <div className="text-xs text-error bg-red-50 rounded-lg px-3 py-2">{error}</div>}

                <button
                  type="submit"
                  disabled={loading || !username || !password}
                  className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
                >
                  {loading ? 'Signing in…' : 'Sign In'}
                </button>

                <p className="text-xs text-on-surface-variant text-center opacity-60 pt-1">
                  First time? Use the <button type="button" onClick={() => setTab('register')} className="text-primary underline">New Organisation</button> tab to create an account.
                </p>
              </form>
            )}

            {/* ── REGISTER ── */}
            {tab === 'register' && (
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Organisation Name</label>
                  <input
                    type="text"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="LTFS"
                    autoFocus
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Username</label>
                  <input
                    type="text"
                    value={regUser}
                    onChange={(e) => setRegUser(e.target.value)}
                    placeholder="admin"
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Email</label>
                  <input
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="admin@ltfs.com"
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Password</label>
                  <input
                    type="password"
                    value={regPass}
                    onChange={(e) => setRegPass(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-1.5 block">Confirm Password</label>
                  <input
                    type="password"
                    value={regPass2}
                    onChange={(e) => setRegPass2(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-surface-low rounded-lg px-3 py-2.5 text-sm text-on-surface border-0 outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                {error   && <div className="text-xs text-error   bg-red-50   rounded-lg px-3 py-2">{error}</div>}
                {success && <div className="text-xs text-success bg-green-50 rounded-lg px-3 py-2">{success}</div>}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #630ed4 0%, #7c3aed 100%)' }}
                >
                  {loading ? 'Creating account…' : 'Create Organisation & Admin'}
                </button>

                <p className="text-xs text-on-surface-variant text-center opacity-60 pt-1">
                  Already have an account? <button type="button" onClick={() => setTab('signin')} className="text-primary underline">Sign in</button>
                </p>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
