// API configuration and utilities

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Helper function to make authenticated API requests
export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Add timeout to prevent infinite loading (15 seconds for file operations)
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
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
  },
  FILES: {
    LIST: '/files/',
    SYNC: '/files/sync',
    DOWNLOAD_URL: (fileId: string) => `/files/${fileId}/download-url`,
    TILES: (fileId: string) => `/files/${fileId}/tiles`,
    UPLOAD: '/upload/',
    DELETE: (fileId: string) => `/upload/${fileId}`,
  },
  FOLDERS: {
    LIST: '/folders/',
    LIST_WITH_FILES: '/folders/with-files',
    CREATE: '/folders/',
    GET: (folderId: string) => `/folders/${folderId}`,
    UPDATE: (folderId: string) => `/folders/${folderId}`,
    DELETE: (folderId: string) => `/folders/${folderId}`,
    ADD_FILE: (folderId: string, fileId: string) => `/folders/${folderId}/files/${fileId}`,
    REMOVE_FILE: (folderId: string, fileId: string) => `/folders/${folderId}/files/${fileId}`,
  },
} as const;
