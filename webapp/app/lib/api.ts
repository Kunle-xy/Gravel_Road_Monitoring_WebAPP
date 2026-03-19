// API configuration and utilities

// Use same-origin proxy (/api) so cookies work across all environments
export const API_URL = '/api';

// Prevent multiple concurrent refresh attempts
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (isRefreshing && refreshPromise) return refreshPromise;

  isRefreshing = true;
  refreshPromise = fetch(`${API_URL}${API_ENDPOINTS.AUTH.REFRESH}`, {
    method: 'POST',
    credentials: 'include',
  }).then((res) => {
    isRefreshing = false;
    refreshPromise = null;
    return res.ok;
  }).catch(() => {
    isRefreshing = false;
    refreshPromise = null;
    return false;
  });

  return refreshPromise;
}

// Helper function to make authenticated API requests (cookie sent automatically)
export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  // Add timeout to prevent infinite loading (15 seconds for file operations)
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    let response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // On 401, try refreshing the access token once
    if (response.status === 401) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        // Retry the original request with a new timeout
        const retryController = new AbortController();
        const retryTimeout = setTimeout(() => retryController.abort(), 15000);
        response = await fetch(`${API_URL}${endpoint}`, {
          ...options,
          headers,
          credentials: 'include',
          signal: retryController.signal,
        });
        clearTimeout(retryTimeout);
      }

      // If still 401 after refresh attempt, redirect to login
      if (response.status === 401 && typeof window !== 'undefined') {
        console.error('Session expired - redirecting to login');
        setTimeout(() => {
          window.location.href = '/';
        }, 500);
      }
    }

    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

// API endpoints
export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: '/auth/login',
    REGISTER: '/auth/register',
    ME: '/auth/me',
    REFRESH: '/auth/refresh',
    LOGOUT: '/auth/logout',
  },
  FILES: {
    LIST: '/files',
    SYNC: '/files/sync',
    DOWNLOAD_URL: (fileId: string) => `/files/${fileId}/download-url`,
    TILES: (fileId: string) => `/files/${fileId}/tiles`,
    UPLOAD: '/upload',
    DELETE: (fileId: string) => `/upload/${fileId}`,
  },
  FOLDERS: {
    LIST: '/folders',
    LIST_WITH_FILES: '/folders/with-files',
    CREATE: '/folders',
    GET: (folderId: string) => `/folders/${folderId}`,
    UPDATE: (folderId: string) => `/folders/${folderId}`,
    DELETE: (folderId: string) => `/folders/${folderId}`,
    ADD_FILE: (folderId: string, fileId: string) => `/folders/${folderId}/files/${fileId}`,
    REMOVE_FILE: (folderId: string, fileId: string) => `/folders/${folderId}/files/${fileId}`,
  },
  RUT: {
    BASE: '/rut',
    GET: (jobId: string) => `/rut/${jobId}`,
    STATUS: (jobId: string) => `/rut/${jobId}/status`,
    BY_FILE: (tiffFileId: string) => `/rut/file/${tiffFileId}`,
    DELETE: (jobId: string) => `/rut/${jobId}`,
    COMPLETED: '/rut/completed',
  },
} as const;
