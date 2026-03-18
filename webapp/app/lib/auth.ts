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

// Fetch current user from API (cookie is sent automatically)
export const getCurrentUser = async (): Promise<User | null> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(`${API_URL}${API_ENDPOINTS.AUTH.ME}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

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
