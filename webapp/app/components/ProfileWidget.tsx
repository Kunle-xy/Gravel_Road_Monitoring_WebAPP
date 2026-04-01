"use client";
import Link from "next/link";
import React, { useEffect, useState, useCallback, memo, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";
import { LogOut, RefreshCw, CloudCog, FolderPlus, Upload, ArrowDownUp, FileText, Download, ExternalLink, ChevronDown, ChevronUp, ChevronRight, Info, Trash2 } from "lucide-react";
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

interface VideoInfo {
  id: string;
  filename: string;
  duration_seconds?: number;
  total_frames?: number;
}

interface Folder {
  id: string;
  name: string;
  description?: string;
  color: string;
  is_expanded: boolean;
  files: TiffFile[];
  videos?: VideoInfo[];
}

interface CompletedJob {
  id: string;
  tiff_file_id?: string;
  video_file_id?: string;
  html_plot_url?: string;
  pdf_plot_url?: string;
  completed_at: string;
  total_ruts_detected?: number;
  total_area_sqft?: number;
  dy_freq?: number;
  dx?: number;
  apply_smoothing?: boolean;
  gaussian_sigma?: number;
  polygon_geojson?: any;
  results_json?: any;
  // pothole
  depth_inches?: number;
  width_feet?: number;
  severity?: string;
}

interface GroupedJobs {
  rut: CompletedJob[];
  crown: CompletedJob[];
  corrugation: CompletedJob[];
  pothole: CompletedJob[];
  dust: CompletedJob[];
}

function JobGroup({ groupKey, label, apiKey, color, jobs, onDelete, getDemFilename }: {
  groupKey: string; label: string; apiKey: string; color: string;
  jobs: CompletedJob[]; onDelete: (id: string, date: string, type: any) => void;
  getDemFilename: (id: string) => string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`flex items-center gap-1.5 w-full text-left text-[11px] font-semibold py-1 px-1 rounded hover:bg-white/5 transition-colors ${color}`}
      >
        {expanded ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
        {label} ({jobs.length})
      </button>
      {expanded && (
        <div className="ml-3 mt-1 space-y-1 border-l border-white/10 pl-2">
          {jobs.map((job) => {
            const isOpen = expandedJobId === job.id;
            const dateStr = new Date(job.completed_at).toLocaleDateString();
            // Summary text
            let summary = '';
            if (groupKey === 'rut' && job.total_ruts_detected != null) summary = `${job.total_ruts_detected} ruts`;
            else if (groupKey === 'pothole' && job.severity) summary = job.severity;
            else if (groupKey === 'dust' && job.results_json?.percentages) {
              const p = job.results_json.percentages;
              summary = `H:${p["High Dust"] ?? 0}% L:${p["Low Dust"] ?? 0}% N:${p["No Dust"] ?? 0}%`;
            }
            else if (groupKey === 'crown') summary = 'Crown analysis';
            else if (groupKey === 'corrugation') summary = 'Corrugation analysis';

            return (
              <div key={job.id}>
                <button
                  onClick={() => setExpandedJobId(isOpen ? null : job.id)}
                  className="flex items-center gap-1 w-full text-left text-[10px] text-slate-300 py-0.5 px-1 rounded hover:bg-white/5 transition-colors"
                >
                  {isOpen ? <ChevronDown className="h-2.5 w-2.5 shrink-0" /> : <ChevronRight className="h-2.5 w-2.5 shrink-0" />}
                  <span className="font-medium">{dateStr}</span>
                  {summary && <span className="text-slate-500 ml-1">— {summary}</span>}
                </button>
                {isOpen && (
                  <div className="ml-4 mt-1 mb-1 bg-slate-800/50 rounded p-2 space-y-1.5">
                    {/* DEM info for rut/crown/corrugation/pothole */}
                    {job.tiff_file_id && (
                      <div className="text-[9px] text-slate-400">DEM: {getDemFilename(job.tiff_file_id)}</div>
                    )}
                    {/* Rut details */}
                    {groupKey === 'rut' && (
                      <div className="text-[9px] text-slate-400 space-y-0.5">
                        {job.total_area_sqft != null && <div>Area: {job.total_area_sqft.toFixed(1)} sq ft</div>}
                        {job.dy_freq != null && <div>Sampling: {job.dy_freq}/100px, Width: {job.dx}m</div>}
                      </div>
                    )}
                    {/* Dust details */}
                    {groupKey === 'dust' && job.results_json?.counts && (
                      <div className="text-[9px] text-slate-400 space-y-0.5">
                        <div>High: {job.results_json.counts["High Dust"] ?? 0} frames</div>
                        <div>Low: {job.results_json.counts["Low Dust"] ?? 0} frames</div>
                        <div>None: {job.results_json.counts["No Dust"] ?? 0} frames</div>
                        <div>Total: {job.results_json.total_classified ?? 0} classified</div>
                      </div>
                    )}
                    {/* Pothole details */}
                    {groupKey === 'pothole' && (
                      <div className="text-[9px] text-slate-400 space-y-0.5">
                        {job.depth_inches != null && <div>Depth: {job.depth_inches.toFixed(2)} in</div>}
                        {job.width_feet != null && <div>Width: {job.width_feet.toFixed(2)} ft</div>}
                      </div>
                    )}
                    {/* Action buttons */}
                    <div className="flex gap-1.5">
                      {job.html_plot_url && (
                        <button
                          onClick={() => window.open(job.html_plot_url!, '_blank', 'noopener,noreferrer')}
                          className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-blue-600/30 hover:bg-blue-600/50 rounded text-[9px] transition-colors cursor-pointer text-slate-200"
                        >
                          <ExternalLink className="h-2.5 w-2.5" /> Plot
                        </button>
                      )}
                      {job.pdf_plot_url && (
                        <button
                          onClick={() => window.open(job.pdf_plot_url!, '_blank', 'noopener,noreferrer')}
                          className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-green-600/30 hover:bg-green-600/50 rounded text-[9px] transition-colors cursor-pointer text-slate-200"
                        >
                          <Download className="h-2.5 w-2.5" /> PDF
                        </button>
                      )}
                      <button
                        onClick={() => onDelete(job.id, job.completed_at, apiKey)}
                        className="flex items-center justify-center gap-1 px-2 py-1 bg-red-600/20 hover:bg-red-600/40 rounded text-[9px] transition-colors cursor-pointer text-red-400"
                      >
                        <Trash2 className="h-2.5 w-2.5" /> Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ProfileWidget() {
  const [open, setOpen] = useState(true);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [uncategorizedFiles, setUncategorizedFiles] = useState<TiffFile[]>([]);
  const [completedJobs, setCompletedJobs] = useState<GroupedJobs>({ rut: [], crown: [], corrugation: [], pothole: [], dust: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [sortBy, setSortBy] = useState<'name' | 'fileCount'>('fileCount');
  const [showCompletedJobs, setShowCompletedJobs] = useState(false);
  const { user, logout, isAuthenticated, refreshUser } = useAuth();

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

  // Fetch completed jobs for all distress types
  const fetchCompletedJobs = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const [rutRes, crownRes, corrRes, potholeRes, dustRes] = await Promise.all([
        fetchWithAuth(API_ENDPOINTS.RUT.COMPLETED).catch(() => null),
        fetchWithAuth(API_ENDPOINTS.CROWN.COMPLETED).catch(() => null),
        fetchWithAuth(API_ENDPOINTS.CORRUGATION.COMPLETED).catch(() => null),
        fetchWithAuth(API_ENDPOINTS.POTHOLE.COMPLETED).catch(() => null),
        fetchWithAuth(API_ENDPOINTS.DUST.COMPLETED).catch(() => null),
      ]);

      setCompletedJobs({
        rut: rutRes?.ok ? await rutRes.json() : [],
        crown: crownRes?.ok ? await crownRes.json() : [],
        corrugation: corrRes?.ok ? await corrRes.json() : [],
        pothole: potholeRes?.ok ? await potholeRes.json() : [],
        dust: dustRes?.ok ? await dustRes.json() : [],
      });
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

      if (foldersResponse.ok) {
        const foldersData = await foldersResponse.json();
        setFolders(foldersData);
      }

      if (filesResponse.ok) {
        const filesData = await filesResponse.json();
        const allFiles = filesData.files || [];

        // Filter uncategorized files (files without folder_id)
        const uncategorized = allFiles.filter((f: TiffFile) => !f.folder_id);
        setUncategorizedFiles(uncategorized);

        // Check for failed files and show alert
        const failedFiles = allFiles.filter((f: TiffFile) => f.tile_status === 'failed');
        if (failedFiles.length > 0) {
          const errorMessages = failedFiles.map((f: TiffFile) =>
            `${f.filename}: ${f.tile_error || 'Processing failed'}`
          ).join('\n\n');

          alert(`Tile generation failed for ${failedFiles.length} file(s):\n\n${errorMessages}\n\nPlease delete and re-upload these files.`);
        }
      } else if (filesResponse.status === 401) {
        // handled by fetchWithAuth
      } else if (!foldersResponse.ok && !filesResponse.ok) {
        setError('Unable to reach the server. Please check your connection and try again.');
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

  // Delete file handler (confirmation handled by TiffFileItem)
  const handleDelete = async (fileId: string, filename: string) => {
    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FILES.DELETE(fileId), {
        method: 'DELETE',
      });

      if (response.ok || response.status === 204) {
        await fetchAllFiles();
      } else {
        alert(`Failed to delete file "${filename}". Please try again.`);
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert(`Failed to delete file "${filename}". Please try again.`);
    }
  };

  // Delete job handler
  const handleDeleteJob = async (jobId: string, completedDate: string, type: keyof typeof API_ENDPOINTS = 'RUT') => {
    if (!confirm(`Are you sure you want to delete this ${type.toLowerCase()} analysis job from ${new Date(completedDate).toLocaleDateString()}?`)) {
      return;
    }

    const endpoints: Record<string, (id: string) => string> = {
      RUT: API_ENDPOINTS.RUT.DELETE,
      CROWN: API_ENDPOINTS.CROWN.DELETE,
      CORRUGATION: API_ENDPOINTS.CORRUGATION.DELETE,
      POTHOLE: API_ENDPOINTS.POTHOLE.DELETE,
      DUST: API_ENDPOINTS.DUST.DELETE,
    };
    const deleteFn = endpoints[type];
    if (!deleteFn) return;

    try {
      const response = await fetchWithAuth(deleteFn(jobId), {
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
        <label className="relative cursor-pointer shrink-0 group" title="Click to change profile picture">
          {user?.profile_picture_url ? (
            <img
              src={user.profile_picture_url}
              alt="Profile"
              className="h-10 w-10 rounded-full object-cover ring-2 ring-slate-600 group-hover:ring-blue-400 transition-colors"
            />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-700 text-sm font-semibold ring-2 ring-slate-600 group-hover:ring-blue-400 transition-colors">
              {user ? getInitials(user.first_name, user.last_name) : 'U'}
            </div>
          )}
          <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity">
            <Upload className="h-4 w-4 text-white" />
          </div>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              try {
                const res = await fetchWithAuth(API_ENDPOINTS.AUTH.PROFILE_PICTURE, { method: 'POST' });
                if (!res.ok) throw new Error('Failed to get upload URL');
                const { presigned_url } = await res.json();
                // Convert to JPEG blob for consistency
                const canvas = document.createElement('canvas');
                const img = new Image();
                img.src = URL.createObjectURL(file);
                await new Promise(r => { img.onload = r; });
                const size = Math.min(img.width, img.height, 512);
                canvas.width = size; canvas.height = size;
                const ctx = canvas.getContext('2d')!;
                const sx = (img.width - size) / 2, sy = (img.height - size) / 2;
                ctx.drawImage(img, sx, sy, size, size, 0, 0, size, size);
                const blob = await new Promise<Blob>((resolve) => canvas.toBlob(b => resolve(b!), 'image/jpeg', 0.85));
                // Upload to S3
                await fetch(presigned_url, { method: 'PUT', body: blob, headers: { 'Content-Type': 'image/jpeg' } });
                // Refresh user data to get new URL
                if (refreshUser) await refreshUser();
              } catch (err) {
                alert('Failed to upload profile picture');
              }
              e.target.value = '';
            }}
          />
        </label>
        <div
          className={`transition-all duration-200 overflow-hidden ${
            open ? "opacity-100 w-auto" : "opacity-0 w-0"
          }`}
        >
          {user ? (
            <>
              <div className="text-xs font-semibold">
                {user.first_name} {user.last_name}
              </div>
              <div className="text-[10px] text-slate-300">{user.email}</div>
            </>
          ) : (
            <>
              <div className="text-xs font-semibold">Guest User</div>
              <div className="text-[10px] text-slate-300">Not logged in</div>
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
            className={`w-full rounded-lg border border-dashed border-slate-500 bg-white/5 px-2.5 py-1.5 text-xs hover:bg-white/15 transition-colors flex items-center gap-2 ${
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
            {/* Completed Jobs Section — grouped by distress type */}
            {(() => {
              const totalJobs = Object.values(completedJobs).reduce((s, a) => s + a.length, 0);
              if (totalJobs === 0) return null;

              const groups: { key: keyof GroupedJobs; label: string; apiKey: string; color: string }[] = [
                { key: 'rut', label: 'Rut', apiKey: 'RUT', color: 'text-orange-400' },
                { key: 'crown', label: 'Crown', apiKey: 'CROWN', color: 'text-blue-400' },
                { key: 'corrugation', label: 'Corrugation', apiKey: 'CORRUGATION', color: 'text-purple-400' },
                { key: 'pothole', label: 'Pothole', apiKey: 'POTHOLE', color: 'text-red-400' },
                { key: 'dust', label: 'Dust', apiKey: 'DUST', color: 'text-yellow-400' },
              ];

              return (
                <div className="mb-4">
                  <div className="text-xs uppercase tracking-wide text-slate-400 mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3 w-3" />
                      <span>Completed Jobs ({totalJobs})</span>
                    </div>
                    {open && (
                      <button
                        onClick={() => setShowCompletedJobs(!showCompletedJobs)}
                        className="p-1 hover:bg-white/10 rounded transition-colors"
                        title={showCompletedJobs ? "Hide" : "Show"}
                      >
                        {showCompletedJobs ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      </button>
                    )}
                  </div>
                  {showCompletedJobs && (
                    <div className="space-y-2">
                      {groups.map(({ key, label, apiKey, color }) => {
                        const jobs = completedJobs[key];
                        if (jobs.length === 0) return null;
                        return <JobGroup key={key} groupKey={key} label={label} apiKey={apiKey} color={color} jobs={jobs} onDelete={handleDeleteJob} getDemFilename={getDemFilename} />;
                      })}
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Folders Section */}
            {folders.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-400 mb-2 flex items-center justify-between">
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
            className="w-full rounded-lg border border-dashed border-blue-500/50 bg-blue-500/10 px-2.5 py-1.5 text-xs hover:bg-blue-500/20 transition-colors flex items-center gap-2 text-blue-300"
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
          className={`w-full rounded-lg bg-red-600/40 px-2.5 py-2 text-xs font-semibold hover:bg-red-600/60 transition-all flex items-center gap-2 shadow-lg ${
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
