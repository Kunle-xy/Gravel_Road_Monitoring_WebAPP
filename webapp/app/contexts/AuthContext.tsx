"use client";

import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { User, getCurrentUser, logout as logoutUtil } from '../lib/auth';
import { API_URL, API_ENDPOINTS } from '../lib/api';

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
    refreshUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Silently refresh the access token every 12 minutes (token expires at 15)
  useEffect(() => {
    if (!user) return;

    const interval = setInterval(async () => {
      try {
        await fetch(`${API_URL}${API_ENDPOINTS.AUTH.REFRESH}`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch {
        // refresh failed — fetchWithAuth will handle 401 on next request
      }
    }, 12 * 60 * 1000);

    return () => clearInterval(interval);
  }, [user]);

  const logout = useCallback(() => {
    setUser(null);
    logoutUtil();
  }, []);

  const value = useMemo(() => ({
    user,
    loading,
    isAuthenticated: !loading && user !== null,
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
