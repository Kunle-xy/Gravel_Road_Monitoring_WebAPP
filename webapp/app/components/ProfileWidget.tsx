"use client";
import Link from "next/link";
import React, { useEffect, useState, useCallback, memo, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";
import { LogOut, RefreshCw, CloudCog, FolderPlus, Upload, ArrowDownUp, FileText, Download, ExternalLink, ChevronDown, ChevronUp, Info, Trash2 } from "lucide-react";
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

interface CompletedJob {
  id: string;
  tiff_file_id: string;
  html_plot_url: string;
  pdf_plot_url: string;
  completed_at: string;
  total_ruts_detected: number;
  total_area_sqft: number;
  dy_freq?: number;
  dx?: number;
  apply_smoothing?: boolean;
  gaussian_sigma?: number;
  polygon_geojson?: any;
}

function ProfileWidget() {
  const [open, setOpen] = useState(true);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [uncategorizedFiles, setUncategorizedFiles] = useState<TiffFile[]>([]);
  const [completedJobs, setCompletedJobs] = useState<CompletedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [sortBy, setSortBy] = useState<'name' | 'fileCount'>('fileCount');
  const [showCompletedJobs, setShowCompletedJobs] = useState(false);
  const { user, logout, isAuthenticated } = useAuth();

  // Resizable width state
  const [isResizing, setIsResizing] = useState(false);
  const [width, setWidth] = useState(256); // Default: w-64 = 16rem = 256px
  const [resizeStartX, setResizeStartX] = useState(0);
  const [resizeStartWidth, setResizeStartWidth] = useState(256);
  const widgetRef = useRef<HTMLElement>(null);

  // Resize handlers
  const handleResizeStart = (e: React.MouseEvent) => {
    setIsResizing(true);
    setResizeStartX(e.clientX);
    setResizeStartWidth(width);
  };

  const handleResizeMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return;

    // Calculate new width based on mouse movement
    const deltaX = e.clientX - resizeStartX;
    const newWidth = resizeStartWidth + deltaX;

    // Set min/max constraints (min: 64px for collapsed, max: 600px)
    const constrainedWidth = Math.max(64, Math.min(600, newWidth));
    setWidth(constrainedWidth);
  }, [isResizing, resizeStartX, resizeStartWidth]);

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
  }, []);

  // Add/remove mouse event listeners for resizing
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
      return () => {
        document.removeEventListener('mousemove', handleResizeMove);
        document.removeEventListener('mouseup', handleResizeEnd);
      };
    }
  }, [isResizing, handleResizeMove, handleResizeEnd]);

  // Fetch completed rut analysis jobs
  const fetchCompletedJobs = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.RUT.COMPLETED);
      if (response.ok) {
        const data = await response.json();
        setCompletedJobs(data);
      }
    } catch (error) {
      console.error('Failed to fetch completed jobs:', error);
    }
  }, [isAuthenticated]);

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
        // Token expired or invalid - clear token and redirect to homepage
        console.error('Authentication failed when fetching files');
        localStorage.removeItem('access_token');
        setError('Authentication failed. Redirecting to login...');
        setTimeout(() => {
          window.location.href = '/';
        }, 1000);
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
      fetchCompletedJobs();
    }
    // Only run once when component mounts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Manual refresh handler
  const handleRefresh = () => {
    setRefreshing(true);
    fetchAllFiles();
    fetchCompletedJobs();
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
      alert('Failed to sync files with cloud storage. Please try again.');
    } finally {
      setRefreshing(false);
    }
  };

  // Delete file handler
  const handleDelete = async (fileId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? This will remove the file from both the database and cloud storage.`)) {
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

  // Delete job handler
  const handleDeleteJob = async (jobId: string, completedDate: string) => {
    if (!confirm(`Are you sure you want to delete the rut analysis job from ${new Date(completedDate).toLocaleDateString()}?`)) {
      return;
    }

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.RUT.DELETE(jobId), {
        method: 'DELETE',
      });

      if (response.ok || response.status === 204) {
        // Refresh completed jobs list after deletion
        await fetchCompletedJobs();
      } else {
        alert('Failed to delete job. Please try again.');
      }
    } catch (error) {
      console.error('Failed to delete job:', error);
      alert('Failed to delete job. Please try again.');
    }
  };

  // Helper function to get DEM filename from tiff_file_id
  const getDemFilename = (tiffFileId: string): string => {
    // Search in all folders
    for (const folder of folders) {
      const file = folder.files.find(f => f.id === tiffFileId);
      if (file) return file.filename;
    }
    // Search in uncategorized files
    const file = uncategorizedFiles.find(f => f.id === tiffFileId);
    if (file) return file.filename;
    return 'Unknown DEM';
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
        const errorData = await response.json().catch(() => ({}));
        console.error('Failed to create folder:', response.status, errorData);
        alert(`Failed to create folder: ${errorData.detail || response.statusText}`);
      }
    } catch (error) {
      console.error('Failed to create folder:', error);
      alert(`Failed to create folder: ${error instanceof Error ? error.message : 'Network error'}`);
    }
  };

  const getInitials = (firstName?: string, lastName?: string) => {
    if (!firstName || !lastName) return 'U';
    return `${firstName[0]}${lastName[0]}`.toUpperCase();
  };

  return (
    <aside
      ref={widgetRef}
      style={{
        width: open ? `${width}px` : '64px',
        transition: isResizing ? 'none' : 'width 300ms ease-in-out'
      }}
      className={`
        relative h-full p-4 text-slate-100
        bg-linear-to-b from-slate-900 to-slate-800
        ring-1 ring-inset ring-slate-700/50
        flex flex-col
        ${isResizing ? 'select-none' : ''}
      `}
      aria-label="Profile widget"
    >
      {/* === RESIZE HANDLE === */}
      {open && (
        <div
          onMouseDown={handleResizeStart}
          className="absolute top-0 right-0 bottom-0 w-2 cursor-ew-resize hover:bg-blue-500/20 active:bg-blue-500/30 transition-colors group"
          title="Drag to resize sidebar"
        >
          <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-12 bg-slate-600 group-hover:bg-blue-400 rounded-full transition-colors" />
        </div>
      )}

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
            <Upload className="h-4 w-4" />
            {open && <span>Upload Files</span>}
          </button>
        </Link>

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
              title="Sync with cloud storage (remove orphaned records)"
              aria-label="Sync with cloud storage"
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
            {/* Completed Jobs Section */}
            {completedJobs.length > 0 && (
              <div className="mb-4">
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3 w-3" />
                    <span>Completed Jobs ({completedJobs.length})</span>
                  </div>
                  {open && (
                    <button
                      onClick={() => setShowCompletedJobs(!showCompletedJobs)}
                      className="p-1 hover:bg-white/10 rounded transition-colors"
                      title={showCompletedJobs ? "Hide completed jobs" : "Show completed jobs"}
                    >
                      {showCompletedJobs ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : (
                        <ChevronDown className="h-3 w-3" />
                      )}
                    </button>
                  )}
                </div>
                {showCompletedJobs && (
                  <div className="space-y-2">
                    {completedJobs.map((job) => {
                      const demFilename = getDemFilename(job.tiff_file_id);
                      const tooltipContent = `DEM: ${demFilename}\nSampling: ${job.dy_freq || 3} per 100px\nRutting Width: ${job.dx || 0.1}m\nSmoothing: ${job.apply_smoothing ? `Yes (σ=${job.gaussian_sigma || 1.0})` : 'No'}`;

                      return (
                        <div
                          key={job.id}
                          className="bg-green-900/20 border border-green-700/30 rounded-lg p-2 text-xs"
                        >
                          <div className="text-slate-300 mb-1 flex items-center justify-between gap-1">
                            <div className="flex items-center gap-1">
                              <span className="font-medium">
                                {new Date(job.completed_at).toLocaleDateString()}
                              </span>
                              <div className="group relative">
                                <Info className="h-3 w-3 text-slate-400 hover:text-blue-400 cursor-help transition-colors" />
                                <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-50 w-48 bg-slate-900 border border-slate-700 rounded-lg p-2 text-[10px] shadow-xl">
                                  <div className="space-y-1 whitespace-pre-line">
                                    <div><span className="text-slate-400">DEM:</span> <span className="text-slate-200">{demFilename}</span></div>
                                    <div><span className="text-slate-400">Sampling:</span> <span className="text-slate-200">{job.dy_freq || 3} per 100px</span></div>
                                    <div><span className="text-slate-400">Width:</span> <span className="text-slate-200">{job.dx || 0.1}m</span></div>
                                    <div><span className="text-slate-400">Smoothing:</span> <span className="text-slate-200">{job.apply_smoothing ? `Yes (σ=${job.gaussian_sigma || 1.0})` : 'No'}</span></div>
                                  </div>
                                </div>
                              </div>
                              <span className="text-slate-500">•</span>
                              <span className="text-green-400">{job.total_ruts_detected} ruts</span>
                            </div>
                            <button
                              onClick={() => handleDeleteJob(job.id, job.completed_at)}
                              className="p-1 hover:bg-red-600/30 rounded transition-colors"
                              title="Delete this job"
                            >
                              <Trash2 className="h-3 w-3 text-red-400 hover:text-red-300" />
                            </button>
                          </div>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => window.open(job.html_plot_url, '_blank', 'noopener,noreferrer')}
                              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-blue-600/30 hover:bg-blue-600/50 rounded text-[10px] transition-colors cursor-pointer"
                              title="View interactive plot"
                            >
                              <ExternalLink className="h-3 w-3" />
                              <span>Plot</span>
                            </button>
                            <button
                              onClick={() => window.open(job.pdf_plot_url, '_blank', 'noopener,noreferrer')}
                              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-green-600/30 hover:bg-green-600/50 rounded text-[10px] transition-colors cursor-pointer"
                              title="View PDF report"
                            >
                              <Download className="h-3 w-3" />
                              <span>PDF</span>
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Folders Section */}
            {folders.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-3 flex items-center justify-between">
                  <span>Projects ({folders.length})</span>
                  <button
                    onClick={() => setSortBy(sortBy === 'name' ? 'fileCount' : 'name')}
                    className="p-1 hover:bg-white/10 rounded transition-colors"
                    title={sortBy === 'name' ? 'Sort by file count' : 'Sort by name'}
                  >
                    <ArrowDownUp className="h-3 w-3" />
                  </button>
                </div>
                <div className="space-y-1">
                  {[...folders]
                    .sort((a, b) => {
                      if (sortBy === 'name') {
                        return a.name.localeCompare(b.name);
                      } else {
                        // Sort by file count (descending - most files first)
                        return b.files.length - a.files.length;
                      }
                    })
                    .map((folder) => (
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

      {/* === NEW PROJECT SECTION (ABOVE LOGOUT) === */}
      <div className="px-4 pb-3 shrink-0">
        {/* Create Project Button */}
        {open && !showCreateFolder && (
          <button
            onClick={() => setShowCreateFolder(true)}
            className="w-full rounded-lg bg-blue-500/20 px-3 py-2 text-sm hover:bg-blue-500/30 transition-colors flex items-center gap-2 text-blue-300"
          >
            <FolderPlus className="h-4 w-4" />
            <span>New Project</span>
          </button>
        )}

        {/* Create Project Form */}
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
              placeholder="Project name..."
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
