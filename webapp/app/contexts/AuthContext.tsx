"use client";

import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { User, getCurrentUser, getToken, logout as logoutUtil } from '../lib/auth';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    // Don't set loading if we're just refreshing and already have a token
    const hasToken = !!getToken();
    if (!hasToken) {
      setLoading(true);
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.error('Error refreshing user:', error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Only refresh user once on mount
    refreshUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - run only once on mount

  const logout = useCallback(() => {
    setUser(null);
    logoutUtil();
  }, []);

  const value = useMemo(() => ({
    user,
    loading,
    // If we have a token, consider authenticated even if user data is still loading
    isAuthenticated: loading ? !!getToken() : (!!getToken() && user !== null),
    logout,
    refreshUser,
  }), [user, loading, logout, refreshUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
