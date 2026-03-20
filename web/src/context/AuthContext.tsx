/**
 * SAGE AuthContext — provides current user identity throughout the app.
 *
 * Dev-mode extensions:
 *   isDevMode    — true when GET /config/dev-users returns a non-empty list
 *   devUsers     — full roster of switchable identities
 *   switchDevUser(id) — sets active user from roster without an API call
 */
import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { getMe, getDevUsers, UserIdentity, DevUser } from '../api/auth'

interface AuthContextValue {
  user:            UserIdentity | null
  isAuthenticated: boolean
  isLoading:       boolean
  refresh:         () => void
  isDevMode:       boolean
  devUsers:        DevUser[]
  switchDevUser:   (id: string) => void
}

export const AuthContext = createContext<AuthContextValue>({
  user:            null,
  isAuthenticated: false,
  isLoading:       true,
  refresh:         () => {},
  isDevMode:       false,
  devUsers:        [],
  switchDevUser:   () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]         = useState<UserIdentity | null>(null)
  const [isLoading, setLoading] = useState(true)
  const [devUsers, setDevUsers] = useState<DevUser[]>([])

  const fetchIdentity = useCallback(() => {
    setLoading(true)
    getMe()
      .then(identity => setUser(identity))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchIdentity()
    getDevUsers()
      .then(data => setDevUsers(data.users ?? []))
      .catch(() => setDevUsers([]))
  }, [fetchIdentity])

  const switchDevUser = useCallback((id: string) => {
    const found = devUsers.find(u => u.id === id)
    if (!found) return
    const identity: UserIdentity = {
      sub:      found.id,
      email:    found.email,
      name:     found.name,
      role:     found.role,
      provider: 'dev',
    }
    setUser(identity)
  }, [devUsers])

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: user !== null,
      isLoading,
      refresh: fetchIdentity,
      isDevMode: devUsers.length > 0,
      devUsers,
      switchDevUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}
