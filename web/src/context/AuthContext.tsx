/**
 * SAGE AuthContext — provides current user identity throughout the app.
 *
 * When auth.enabled is false the backend returns an anonymous identity
 * with role="admin", so all UI features remain fully accessible.
 *
 * Usage:
 *   const { user, isAuthenticated, isLoading } = useAuth()
 */

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { getMe, UserIdentity } from '../api/auth'

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface AuthContextValue {
  user:            UserIdentity | null
  isAuthenticated: boolean
  isLoading:       boolean
  /** Re-fetch the current user identity (call after login/logout flows). */
  refresh:         () => void
}

const AuthContext = createContext<AuthContextValue>({
  user:            null,
  isAuthenticated: false,
  isLoading:       true,
  refresh:         () => {},
})

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]         = useState<UserIdentity | null>(null)
  const [isLoading, setLoading] = useState(true)

  const fetchIdentity = () => {
    setLoading(true)
    getMe()
      .then(identity => {
        setUser(identity)
      })
      .catch(() => {
        // 401 means not authenticated; any other error → treat as unauthenticated
        setUser(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    fetchIdentity()
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        refresh: fetchIdentity,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}
