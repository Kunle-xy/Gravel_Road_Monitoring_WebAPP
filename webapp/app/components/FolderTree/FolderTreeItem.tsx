"use client";

import { useState } from 'react';
import { ChevronRight, ChevronDown, Folder, FolderOpen, Plus, Trash2, Edit2, Video } from 'lucide-react';
import TiffFileItem from '../TiffFiles/TiffFileItem';
import { fetchWithAuth, API_ENDPOINTS } from '@/app/lib/api';

interface TiffFile {
  id: string;
  filename: string;
  file_type: string;
  original_size_bytes: number;
  bounds_south?: string;
  bounds_west?: string;
  bounds_north?: string;
  bounds_east?: string;
  tile_status?: string;
  tile_url_template?: string;
  tile_error?: string;
  tile_progress?: number;
}

interface VideoFileInfo {
  id: string;
  filename: string;
  duration_seconds?: number;
  total_frames?: number;
}

interface FolderTreeItemProps {
  folder: {
    id: string;
    name: string;
    description?: string;
    color: string;
    is_expanded: boolean;
    files: TiffFile[];
    videos?: VideoFileInfo[];
  };
  onDelete: (fileId: string, filename: string) => void;
  onRefresh: () => void;
}

export default function FolderTreeItem({ folder, onDelete, onRefresh }: FolderTreeItemProps) {
  const [isExpanded, setIsExpanded] = useState(folder.is_expanded);
  const [isEditingName, setIsEditingName] = useState(false);
  const [newName, setNewName] = useState(folder.name);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const toggleExpand = async () => {
    const newState = !isExpanded;
    setIsExpanded(newState);

    // Persist expand/collapse state to backend
    try {
      await fetchWithAuth(API_ENDPOINTS.FOLDERS.UPDATE(folder.id), {
        method: 'PATCH',
        body: JSON.stringify({ is_expanded: newState }),
      });
    } catch (error) {
      console.error('Failed to update folder state:', error);
    }
  };

  const handleDeleteFolder = async () => {
    if (confirmText !== 'I confirm') {
      alert('Please type "I confirm" to delete this project');
      return;
    }

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.DELETE(folder.id), {
        method: 'DELETE',
      });

      if (response.ok || response.status === 204) {
        setShowDeleteConfirm(false);
        setConfirmText('');
        onRefresh();
      } else {
        alert('Failed to delete project');
      }
    } catch (error) {
      console.error('Failed to delete project:', error);
      alert('Failed to delete project');
    }
  };

  const handleRenameFolder = async () => {
    if (newName.trim() === '' || newName === folder.name) {
      setIsEditingName(false);
      setNewName(folder.name);
      return;
    }

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.UPDATE(folder.id), {
        method: 'PATCH',
        body: JSON.stringify({ name: newName }),
      });

      if (response.ok) {
        setIsEditingName(false);
        onRefresh();
      } else {
        alert('Failed to rename project');
        setNewName(folder.name);
      }
    } catch (error) {
      console.error('Failed to rename project:', error);
      alert('Failed to rename project');
      setNewName(folder.name);
    }
  };

  return (
    <div className="mb-3">
      {/* Delete Confirmation Form */}
      {showDeleteConfirm ? (
        <div className="bg-red-900/20 border-2 border-red-500/50 rounded-lg p-3 space-y-2">
          <div className="text-xs text-white font-semibold">
            Delete project "{folder.name}"?
          </div>
          <div className="text-xs text-white opacity-90">
            ⚠️ WARNING: This will PERMANENTLY delete all {folder.files.length} file{folder.files.length !== 1 ? 's' : ''} in this project from both the database and cloud storage. This action cannot be undone. Type "I confirm" to delete.
          </div>
          <input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleDeleteFolder();
              if (e.key === 'Escape') {
                setShowDeleteConfirm(false);
                setConfirmText('');
              }
            }}
            placeholder="Type: I confirm"
            autoFocus
            className="w-full bg-white/10 text-sm text-white px-2 py-1.5 rounded border border-white/20 focus:outline-none focus:border-red-400 placeholder:text-slate-400"
          />
          <div className="flex gap-2">
            <button
              onClick={handleDeleteFolder}
              disabled={confirmText !== 'I confirm'}
              className="flex-1 bg-red-600/40 hover:bg-red-600/60 disabled:bg-red-900/20 disabled:text-slate-500 disabled:cursor-not-allowed px-2 py-1 rounded text-xs transition-colors text-white font-semibold"
            >
              Delete
            </button>
            <button
              onClick={() => {
                setShowDeleteConfirm(false);
                setConfirmText('');
              }}
              className="flex-1 bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-xs transition-colors text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Project Header */}
          <div className="flex items-center gap-2 px-2 py-1.5 hover:bg-white/5 rounded-lg group">
            {/* Expand/Collapse Button */}
            <button
              onClick={toggleExpand}
              className="shrink-0 hover:bg-white/10 rounded p-0.5 transition-colors"
              aria-label={isExpanded ? "Collapse project" : "Expand project"}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>

            {/* Project Icon */}
            <div style={{ color: folder.color }}>
              {isExpanded ? (
                <FolderOpen className="h-4 w-4" />
              ) : (
                <Folder className="h-4 w-4" />
              )}
            </div>

            {/* Project Name */}
            {isEditingName ? (
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onBlur={handleRenameFolder}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRenameFolder();
                  if (e.key === 'Escape') {
                    setIsEditingName(false);
                    setNewName(folder.name);
                  }
                }}
                autoFocus
                className="flex-1 bg-white/10 text-sm px-2 py-0.5 rounded border border-white/20 focus:outline-none focus:border-blue-400"
              />
            ) : (
              <span className="flex-1 text-sm font-medium truncate">
                {folder.name} ({folder.files.length + (folder.videos?.length || 0)})
              </span>
            )}

            {/* Project Actions */}
            <div className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
              <button
                onClick={() => setIsEditingName(true)}
                className="p-1 hover:bg-white/10 rounded transition-colors"
                title="Rename project"
                aria-label="Rename project"
              >
                <Edit2 className="h-3 w-3" />
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="p-1 hover:bg-red-500/20 rounded transition-colors"
                title="Delete project"
                aria-label="Delete project"
              >
                <Trash2 className="h-3 w-3 text-red-400" />
              </button>
            </div>
          </div>
        </>
      )}

      {/* Project Files - Only show when not deleting */}
      {isExpanded && !showDeleteConfirm && (
        <div className="ml-6 mt-2 space-y-3 border-l border-white/10 pl-3">
          {folder.files.length === 0 ? (
            <div className="text-xs text-slate-400 italic py-2">
              No files in this project
            </div>
          ) : (
            <>
              {/* DEM Files Section */}
              {(() => {
                const demFiles = folder.files.filter(f => f.file_type === 'DEM');
                return demFiles.length > 0 && (
                  <div>
                    <div className="text-xs uppercase tracking-wide text-slate-400 mb-2 font-semibold">
                      DEM Files ({demFiles.length})
                    </div>
                    <div className="space-y-2">
                      {demFiles.map((file) => (
                        <TiffFileItem key={file.id} file={file} onDelete={onDelete} />
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Hillshade / Orthophoto Files Section */}
              {(() => {
                const orthoFiles = folder.files.filter(f => f.file_type === 'ORTHOPHOTO' || f.file_type === 'HILLSHADE');
                return orthoFiles.length > 0 && (
                  <div>
                    <div className="text-xs uppercase tracking-wide text-slate-400 mb-2 font-semibold">
                      Hillshade / Orthophoto ({orthoFiles.length})
                    </div>
                    <div className="space-y-2">
                      {orthoFiles.map((file) => (
                        <TiffFileItem key={file.id} file={file} onDelete={onDelete} />
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Videos Section */}
              {folder.videos && folder.videos.length > 0 && (
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-400 mb-2 font-semibold">
                    Videos ({folder.videos.length})
                  </div>
                  <div className="space-y-2">
                    {folder.videos.map((video) => (
                      <div
                        key={video.id}
                        className="flex items-center gap-2 px-2 py-1.5 bg-slate-700/30 rounded text-[12px]"
                      >
                        <Video size={14} className="text-cyan-400 shrink-0" />
                        <span className="flex-1 truncate text-slate-200">{video.filename}</span>
                        {video.duration_seconds && (
                          <span className="text-slate-500 text-[10px] shrink-0">
                            {video.duration_seconds.toFixed(0)}s
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
