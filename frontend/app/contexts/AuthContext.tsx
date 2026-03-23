'use client'

import { createContext, useContext, useState, type ReactNode } from 'react'
import type { MembershipInfo } from '@/lib/api'

interface User {
  id?: number
  name?: string
  displayName?: string
  email?: string
  avatar?: string
}

interface AuthContextType {
  user: User | null
  loading: boolean
  authEnabled: boolean
  membership: MembershipInfo | null
  membershipLoading: boolean
  setUser: (user: User | null) => void
  logout: () => void
  refreshMembership: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const loading = false
  const authEnabled = false
  const [membership, setMembership] = useState<MembershipInfo | null>(null)
  const membershipLoading = false

  // Function to refresh membership data
  const refreshMembership = async () => {
    setMembership(null)
  }

  const logout = async () => {
    setUser(null)
    setMembership(null)
  }

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      authEnabled,
      membership,
      membershipLoading,
      setUser,
      logout,
      refreshMembership
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
