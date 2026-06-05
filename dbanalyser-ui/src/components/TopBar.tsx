import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../lib/auth'

export default function TopBar() {
  const { user, logout } = useAuth()
  const qc = useQueryClient()

  return (
    <header
      className="h-14 bg-surface-lowest flex items-center px-6 gap-4 flex-shrink-0"
      style={{ borderBottom: '1px solid rgba(74,68,85,0.08)' }}
    >
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
