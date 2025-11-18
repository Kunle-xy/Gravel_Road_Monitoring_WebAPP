"use client";

import { useState } from 'react';
import { ChevronRight, ChevronDown, Folder, FolderOpen, Plus, Trash2, Edit2 } from 'lucide-react';
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

interface FolderTreeItemProps {
  folder: {
    id: string;
    name: string;
    description?: string;
    color: string;
    is_expanded: boolean;
    files: TiffFile[];
  };
  onDelete: (fileId: string, filename: string) => void;
  onRefresh: () => void;
}

export default function FolderTreeItem({ folder, onDelete, onRefresh }: FolderTreeItemProps) {
  const [isExpanded, setIsExpanded] = useState(folder.is_expanded);
  const [isEditingName, setIsEditingName] = useState(false);
  const [newName, setNewName] = useState(folder.name);

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
    if (!confirm(`Delete folder "${folder.name}"? Files will be moved to root level.`)) {
      return;
    }

    try {
      const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.DELETE(folder.id), {
        method: 'DELETE',
      });

      if (response.ok || response.status === 204) {
        onRefresh();
      } else {
        alert('Failed to delete folder');
      }
    } catch (error) {
      console.error('Failed to delete folder:', error);
      alert('Failed to delete folder');
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
        alert('Failed to rename folder');
        setNewName(folder.name);
      }
    } catch (error) {
      console.error('Failed to rename folder:', error);
      alert('Failed to rename folder');
      setNewName(folder.name);
    }
  };

  return (
    <div className="mb-3">
      {/* Folder Header */}
      <div className="flex items-center gap-2 px-2 py-1.5 hover:bg-white/5 rounded-lg group">
        {/* Expand/Collapse Button */}
        <button
          onClick={toggleExpand}
          className="shrink-0 hover:bg-white/10 rounded p-0.5 transition-colors"
          aria-label={isExpanded ? "Collapse folder" : "Expand folder"}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        {/* Folder Icon */}
        <div style={{ color: folder.color }}>
          {isExpanded ? (
            <FolderOpen className="h-4 w-4" />
          ) : (
            <Folder className="h-4 w-4" />
          )}
        </div>

        {/* Folder Name */}
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
            {folder.name} ({folder.files.length})
          </span>
        )}

        {/* Folder Actions */}
        <div className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
          <button
            onClick={() => setIsEditingName(true)}
            className="p-1 hover:bg-white/10 rounded transition-colors"
            title="Rename folder"
            aria-label="Rename folder"
          >
            <Edit2 className="h-3 w-3" />
          </button>
          <button
            onClick={handleDeleteFolder}
            className="p-1 hover:bg-red-500/20 rounded transition-colors"
            title="Delete folder"
            aria-label="Delete folder"
          >
            <Trash2 className="h-3 w-3 text-red-400" />
          </button>
        </div>
      </div>

      {/* Folder Files */}
      {isExpanded && (
        <div className="ml-6 mt-2 space-y-2 border-l border-white/10 pl-3">
          {folder.files.length === 0 ? (
            <div className="text-xs text-slate-400 italic py-2">
              No files in this folder
            </div>
          ) : (
            folder.files.map((file) => (
              <TiffFileItem key={file.id} file={file} onDelete={onDelete} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
