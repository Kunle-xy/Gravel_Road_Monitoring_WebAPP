"use client";
import Link from "next/link";
import React, { useEffect, useState, useCallback, memo } from "react";
import { useAuth } from "../contexts/AuthContext";
import { LogOut, RefreshCw, CloudCog, FolderPlus } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS } from "../lib/api";
import TiffFileItem from "./TiffFiles/TiffFileItem";
import FolderTreeItem from "./FolderTree/FolderTreeItem";

interface TiffFile {
  id: string;
  filename: string;
  file_type: string;
  original_size_bytes: number;
  created_at: string;
  folder_id?: string;
  // Tile generation fields
  tile_status?: string;
  tile_url_template?: string;
  tile_progress?: number;
  tile_error?: string;
  tiles_generated_at?: string;
  // Bounds fields
  bounds_south?: string;
  bounds_west?: string;
  bounds_north?: string;
  bounds_east?: string;
  // Upload status
  upload_status?: string;
}

interface Folder {
  id: string;
  name: string;
  description?: string;
  color: string;
  is_expanded: boolean;
  files: TiffFile[];
}

function ProfileWidget() {
  const [open, setOpen] = useState(true);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [uncategorizedFiles, setUncategorizedFiles] = useState<TiffFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const { user, logout, isAuthenticated } = useAuth();

  // Fetch folders with files and uncategorized files
  const fetchAllFiles = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    setError(null); // Clear previous errors
    try {
      // Fetch folders with files
      const foldersResponse = await fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST_WITH_FILES);

      // Fetch all files to get uncategorized ones
      const filesResponse = await fetchWithAuth(API_ENDPOINTS.FILES.LIST);

      if (foldersResponse.ok && filesResponse.ok) {
        const foldersData = await foldersResponse.json();
        const filesData = await filesResponse.json();

        const allFiles = filesData.files || [];
        setFolders(foldersData);

        // Filter uncategorized files (files without folder_id)
        const uncategorized = allFiles.filter((f: TiffFile) => !f.folder_id);
        setUncategorizedFiles(uncategorized);

        // Check for failed files and show alert
        const failedFiles = allFiles.filter((f: TiffFile) => f.tile_status === 'failed');
        if (failedFiles.length > 0) {
          const errorMessages = failedFiles.map((f: TiffFile) =>
            `${f.filename}: ${f.tile_error || 'Processing failed'}`
          ).join('\n\n');

          alert(`⚠️ Tile generation failed for ${failedFiles.length} file(s):\n\n${errorMessages}\n\nPlease delete and re-upload these files.`);
        }
      } else if (foldersResponse.status === 401 || filesResponse.status === 401) {
        // Token expired or invalid
        setError('Authentication failed. Please login again.');
        console.error('Authentication failed when fetching files');
      } else {
        setError('Failed to load files. Please try again.');
      }
    } catch (error) {
      console.error('Failed to fetch files:', error);
      if (error instanceof Error && error.name === 'AbortError') {
        setError('Connection timeout. Is the backend running?');
      } else {
        setError('Failed to connect to server.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    // Remove isAuthenticated from deps - we check it inside the function
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch once on mount only
  useEffect(() => {
    if (isAuthenticated) {
      fetchAllFiles();
    }
    // Only run once when component mounts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Manual refresh handler
  const handleRefresh = () => {
    setRefreshing(true);
    fetchAllFiles();
  };

  // Sync with S3 handler
  const handleSync = async () => {
    setRefreshing(true);
    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FILES.SYNC, {
        method: 'POST',
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Sync result:', data);
        // Refresh file list after sync
        await fetchAllFiles();

        // Show notification if files were removed
        if (data.removed_count > 0) {
          alert(`Sync completed: ${data.removed_count} orphaned file(s) removed from database.`);
        }
      }
    } catch (error) {
      console.error('Failed to sync files:', error);
      alert('Failed to sync files with S3. Please try again.');
    } finally {
      setRefreshing(false);
    }
  };

  // Delete file handler
  const handleDelete = async (fileId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? This will remove the file from both the database and S3 storage.`)) {
      return;
    }

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FILES.DELETE(fileId), {
        method: 'DELETE',
      });

      if (response.ok || response.status === 204) {
        // Refresh file list after deletion
        await fetchAllFiles();
        alert(`File "${filename}" deleted successfully.`);
      } else {
        alert(`Failed to delete file "${filename}". Please try again.`);
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert(`Failed to delete file "${filename}". Please try again.`);
    }
  };

  // Create folder handler
  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      alert('Please enter a folder name');
      return;
    }

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.CREATE, {
        method: 'POST',
        body: JSON.stringify({
          name: newFolderName,
          description: '',
          color: '#3b82f6'
        }),
      });

      if (response.ok) {
        setShowCreateFolder(false);
        setNewFolderName('');
        await fetchAllFiles();
      } else {
        alert('Failed to create folder. Please try again.');
      }
    } catch (error) {
      console.error('Failed to create folder:', error);
      alert('Failed to create folder. Please try again.');
    }
  };

  const getInitials = (firstName?: string, lastName?: string) => {
    if (!firstName || !lastName) return 'U';
    return `${firstName[0]}${lastName[0]}`.toUpperCase();
  };

  return (
    <aside
      className={`
        relative h-full p-4 text-slate-100
        transition-all duration-300 ease-in-out
        ${open ? "w-64" : "w-16"}
        bg-gradient-to-b from-slate-900 to-slate-800
        ring-1 ring-inset ring-slate-700/50
        flex flex-col
      `}
      aria-label="Profile widget"
    >
      {/* === PROFILE HEADER === */}
      <div className="flex items-center gap-3 mb-6 shrink-0">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-700 text-sm font-semibold shrink-0">
          {user ? getInitials(user.first_name, user.last_name) : 'U'}
        </div>
        <div
          className={`transition-all duration-200 overflow-hidden ${
            open ? "opacity-100 w-auto" : "opacity-0 w-0"
          }`}
        >
          {user ? (
            <>
              <div className="text-sm font-semibold">
                {user.first_name} {user.last_name}
              </div>
              <div className="text-xs text-slate-300">{user.email}</div>
            </>
          ) : (
            <>
              <div className="text-sm font-semibold">Guest User</div>
              <div className="text-xs text-slate-300">Not logged in</div>
            </>
          )}
        </div>
      </div>

      {/* === MAIN CONTENT === */}
      <div
        className={`flex-1 space-y-4 transition-opacity duration-200 overflow-y-auto min-h-0 ${
          open ? "opacity-100" : "opacity-0"
        }`}
      >
        {/* Upload Button */}
        <Link href="/dashboard/upload">
          <button
            type="button"
            className={`w-full rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/15 transition-colors flex items-center gap-2 ${
              open ? "" : "justify-center"
            }`}
          >
            <UploadIcon />
            {open && <span>Upload Files</span>}
          </button>
        </Link>

        {/* Create Folder Button */}
        {open && !showCreateFolder && (
          <button
            onClick={() => setShowCreateFolder(true)}
            className="w-full rounded-lg bg-blue-500/20 px-3 py-2 text-sm hover:bg-blue-500/30 transition-colors flex items-center gap-2 text-blue-300"
          >
            <FolderPlus className="h-4 w-4" />
            <span>New Folder</span>
          </button>
        )}

        {/* Create Folder Form */}
        {open && showCreateFolder && (
          <div className="bg-white/5 rounded-lg p-3 space-y-2">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateFolder();
                if (e.key === 'Escape') {
                  setShowCreateFolder(false);
                  setNewFolderName('');
                }
              }}
              placeholder="Folder name..."
              autoFocus
              className="w-full bg-white/10 text-sm px-2 py-1.5 rounded border border-white/20 focus:outline-none focus:border-blue-400"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreateFolder}
                className="flex-1 bg-blue-500/30 hover:bg-blue-500/40 px-2 py-1 rounded text-xs transition-colors"
              >
                Create
              </button>
              <button
                onClick={() => {
                  setShowCreateFolder(false);
                  setNewFolderName('');
                }}
                className="flex-1 bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-xs transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        {open && (
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={handleRefresh}
              disabled={refreshing || loading}
              className="p-1 hover:bg-white/10 rounded transition-colors disabled:opacity-50"
              title="Refresh file list"
              aria-label="Refresh file list"
            >
              <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={handleSync}
              disabled={refreshing || loading}
              className="p-1 hover:bg-blue-500/20 bg-blue-500/10 rounded transition-colors disabled:opacity-50"
              title="Sync with S3 (remove orphaned records)"
              aria-label="Sync with S3"
            >
              <CloudCog className={`h-3 w-3 text-blue-400 ${refreshing ? 'animate-pulse' : ''}`} />
            </button>
          </div>
        )}

        {loading ? (
          <div className={`text-sm text-slate-400 ${open ? '' : 'text-center'}`}>
            {open ? 'Loading...' : '...'}
          </div>
        ) : error ? (
          <div className={`text-sm text-red-400 ${open ? '' : 'hidden'}`}>
            <div className="mb-2">{error}</div>
            <button
              onClick={handleRefresh}
              className="text-xs bg-red-500/20 hover:bg-red-500/30 px-2 py-1 rounded transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            {/* Folders Section */}
            {folders.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-3">
                  Projects ({folders.length})
                </div>
                <div className="space-y-1">
                  {folders.map((folder) => (
                    <FolderTreeItem
                      key={folder.id}
                      folder={folder}
                      onDelete={handleDelete}
                      onRefresh={fetchAllFiles}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Uncategorized Files Section */}
            {uncategorizedFiles.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-2 flex items-center gap-2">
                  {open ? (
                    <span>Uncategorized Files ({uncategorizedFiles.length})</span>
                  ) : (
                    <FileIcon className="h-4 w-4" />
                  )}
                </div>
                <ul className="space-y-2 text-sm">
                  {uncategorizedFiles.map((file) => (
                    <TiffFileItem key={file.id} file={file} onDelete={handleDelete} />
                  ))}
                </ul>
              </div>
            )}

            {/* Empty State */}
            {folders.length === 0 && uncategorizedFiles.length === 0 && (
              <div className={`text-sm text-slate-400 text-center py-8 ${open ? '' : 'hidden'}`}>
                <FileIcon className="h-12 w-12 mx-auto mb-2 opacity-20" />
                <p>No files yet</p>
                <p className="text-xs mt-1">Upload files to get started</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* === LOGOUT BUTTON (BOTTOM) === */}
      <div className="pt-3 border-t-2 border-red-500/50 shrink-0 bg-slate-800">
        <button
          type="button"
          onClick={logout}
          className={`w-full rounded-lg bg-red-600/40 px-3 py-2.5 text-sm font-semibold hover:bg-red-600/60 transition-all flex items-center gap-2 shadow-lg ${
            open ? "" : "justify-center px-2"
          }`}
          title="Logout"
          aria-label="Logout"
        >
          <LogOut className="h-5 w-5 shrink-0 text-red-100" />
          {open && <span className="text-red-100">Logout</span>}
        </button>
      </div>

      {/* === TOGGLE BUTTON === */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`
          absolute -right-3 top-1/2 z-10
          flex h-9 w-9 items-center justify-center
          rounded-full bg-slate-700/90 hover:bg-slate-600/90
          ring-1 ring-slate-600/60 transition-all
          shadow-lg
        `}
        aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
      >
        <svg
          className={`h-5 w-5 text-slate-300 transition-transform duration-200 ${
            open ? "" : "rotate-180"
          }`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M12.79 5.23a.75.75 0 0 1 0 1.06L9.08 10l3.71 3.71a.75.75 0 1 1-1.06 1.06l-4.24-4.24a.75.75 0 0 1 0-1.06l4.24-4.24a.75.75 0 0 1 1.06 0z" />
        </svg>
      </button>
    </aside>
  );
}

// === ICONS ===
function UploadIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
      <path d="M10 3.5a.75.75 0 0 1 .75.75v6.5h6.5a.75.75 0 0 1 0 1.5h-6.5v6.5a.75.75 0 0 1-1.5 0v-6.5H3.75a.75.75 0 0 1 0-1.5h6.5v-6.5A.75.75 0 0 1 10 3.5Z" />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M4.5 2A1.5 1.5 0 0 0 3 3.5v13A1.5 1.5 0 0 0 4.5 18h11a1.5 1.5 0 0 0 1.5-1.5V7.621a1.5 1.5 0 0 0-.44-1.06l-4.12-4.122A1.5 1.5 0 0 0 11.378 2H4.5ZM5 3.5a.5.5 0 0 1 .5-.5h5.878L15.5 7.121V16.5a.5.5 0 0 1-.5.5h-9.5a.5.5 0 0 1-.5-.5v-13Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// Export memoized version to prevent unnecessary re-renders
export default memo(ProfileWidget);
