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

// Get token from localStorage
export const getToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
};

// Set token to localStorage
export const setToken = (token: string): void => {
  if (typeof window === 'undefined') return;
  localStorage.setItem('access_token', token);
};

// Remove token from localStorage
export const removeToken = (): void => {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('access_token');
};

// Check if user is authenticated
export const isAuthenticated = (): boolean => {
  return !!getToken();
};

// Fetch current user from API
export const getCurrentUser = async (): Promise<User | null> => {
  const token = getToken();
  if (!token) return null;

  try {
    // Add timeout to prevent infinite loading
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    const response = await fetch(`${API_URL}${API_ENDPOINTS.AUTH.ME}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      if (response.status === 401) {
        // Token is invalid or expired
        removeToken();
      }
      throw new Error('Failed to fetch user');
    }

    const user = await response.json();
    return user;
  } catch (error) {
    console.error('Error fetching current user:', error);
    // If the request times out or fails, remove the token and redirect to login
    if (error instanceof Error && error.name === 'AbortError') {
      console.error('Request timed out - backend may not be running');
      removeToken();
    }
    return null;
  }
};

// Logout user
export const logout = (): void => {
  removeToken();
  if (typeof window !== 'undefined') {
    window.location.href = '/';
  }
};
