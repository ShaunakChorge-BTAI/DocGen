import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { authApi } from './api'

interface AuthCtx {
  user: any | null
  token: string | null
  isAuthDisabled: boolean        // true when backend has auth.enabled: false
  login: (u: string, p: string) => Promise<void>
  loginAsGuest: () => void       // explicit guest login when auth is disabled
  logout: () => void
  loading: boolean
}

const Ctx = createContext<AuthCtx>(null!)
export const useAuth = () => useContext(Ctx)

const GUEST_KEY = 'dba_guest_session'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]             = useState<any | null>(null)
  const [token, setToken]           = useState<string | null>(localStorage.getItem('token'))
  const [loading, setLoading]       = useState(true)
  const [isAuthDisabled, setIsAuthDisabled] = useState(false)

  useEffect(() => {
    // Probe /auth/me on mount and whenever token changes.
    // When auth is DISABLED the backend returns { username:"anonymous", role:"admin" } → 200
    // We do NOT auto-login in that case — the user must make an explicit choice on the
    // login page (click "Continue as Admin").  We only skip the login step if they have
    // already made that choice this browser session (guestSession flag in sessionStorage).
    authApi.me()
      .then((r) => {
        if (r.data.username === 'anonymous') {
          setIsAuthDisabled(true)
          // If user already clicked "Continue as Admin" this session, restore them
          if (sessionStorage.getItem(GUEST_KEY) === '1') {
            setUser(r.data)
          }
        } else {
          setUser(r.data)
        }
      })
      .catch(() => {
        // 401 — auth IS enabled and no valid token
        localStorage.removeItem('token')
        sessionStorage.removeItem(GUEST_KEY)
        setToken(null)
        setUser(null)
      })
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const login = async (username: string, password: string) => {
    const r  = await authApi.login(username, password)
    const tk = r.data.access_token
    localStorage.setItem('token', tk)
    setToken(tk)
    setUser({ username: r.data.username, role: r.data.role })
  }

  /** Used when auth is disabled — user consciously proceeds as anonymous admin */
  const loginAsGuest = () => {
    sessionStorage.setItem(GUEST_KEY, '1')
    setUser({ username: 'anonymous', role: 'admin' })
  }

  const logout = () => {
    localStorage.removeItem('token')
    sessionStorage.removeItem(GUEST_KEY)
    setToken(null)
    setUser(null)
  }

  return (
    <Ctx.Provider value={{ user, token, isAuthDisabled, login, loginAsGuest, logout, loading }}>
      {children}
    </Ctx.Provider>
  )
}
