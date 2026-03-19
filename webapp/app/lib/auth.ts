// Authentication utility functions
import { API_URL, API_ENDPOINTS } from './api';

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  organization?: string;
  is_active: boolean;
  created_at: string;
}

// Fetch current user from API
// Uses a simple fetch (not fetchWithAuth) to avoid redirect loops on the login page.
// Attempts one token refresh if the access token is expired.
export const getCurrentUser = async (): Promise<User | null> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    let response = await fetch(`${API_URL}${API_ENDPOINTS.AUTH.ME}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // If 401, try refreshing the token once
    if (response.status === 401) {
      const refreshRes = await fetch(`${API_URL}${API_ENDPOINTS.AUTH.REFRESH}`, {
        method: 'POST',
        credentials: 'include',
      });
      if (refreshRes.ok) {
        response = await fetch(`${API_URL}${API_ENDPOINTS.AUTH.ME}`, {
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching current user:', error);
    return null;
  }
};

// Logout user (clears HttpOnly cookie server-side)
export const logout = async (): Promise<void> => {
  try {
    await fetch(`${API_URL}${API_ENDPOINTS.AUTH.LOGOUT}`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch (error) {
    console.error('Error during logout:', error);
  }
  if (typeof window !== 'undefined') {
    window.location.href = '/';
  }
};
