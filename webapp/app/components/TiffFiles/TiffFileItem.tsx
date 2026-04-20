"use client";

import { useState, useEffect } from 'react';
import { Trash2, CheckSquare, Square, Loader2 } from 'lucide-react';
import { useMap } from '../../contexts/MapContext';

interface TiffFileItemProps {
  file: {
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
    tile_min_zoom?: number;
    tile_max_zoom?: number;
  };
  onDelete: (fileId: string, filename: string) => void;
}

export default function TiffFileItem({ file, onDelete }: TiffFileItemProps) {
  const { map, addLayer, toggleLayer, isLayerVisible, allLayers } = useMap();
  const [initializing, setInitializing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const checked = isLayerVisible(file.id);
  const layerExists = allLayers.has(file.id);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Pre-create layer when component mounts and map is ready
  useEffect(() => {
    if (!map || layerExists) return;

    // Check if tiles are ready
    if (file.tile_status !== 'completed') {
      const statusMessage =
        file.tile_status === 'processing' ? `Generating tiles (${file.tile_progress || 0}%)` :
        file.tile_status === 'failed' ? `Tile generation failed: ${file.tile_error || 'Unknown error'}` :
        file.tile_status === 'queued' ? 'Waiting to generate tiles...' :
        'Tiles not ready';

      console.warn(`File ${file.filename} tiles not ready - status: ${file.tile_status}`);
      setError(statusMessage);
      setInitializing(false); // Ensure spinner stops
      return;
    }

    // Check if bounds are available
    if (!file.bounds_south || !file.bounds_west || !file.bounds_north || !file.bounds_east) {
      console.warn(`File ${file.filename} missing bounds - upload may be in progress`);
      setError('Bounds not available');
      setInitializing(false); // Ensure spinner stops
      return;
    }

    let cancelled = false; // Prevent state updates if component unmounts

    const initializeLayer = async () => {
      setInitializing(true);
      setError(null);

      try {
        // Dynamically import Leaflet
        const L = (await import('leaflet')).default;

        // Use the pre-generated static tile URL directly from the file record
        const tileUrl = file.tile_url_template;

        if (!tileUrl) {
          throw new Error('No tile URL available');
        }

        if (cancelled) return; // Don't continue if component unmounted

        // Parse bounds from database (already validated they exist above)
        const bounds: [[number, number], [number, number]] = [
          [parseFloat(file.bounds_south!), parseFloat(file.bounds_west!)],
          [parseFloat(file.bounds_north!), parseFloat(file.bounds_east!)]
        ];
        const tileBounds = L.latLngBounds(bounds);

        // Create the tile layer. Two guards keep Leaflet from 404-ing:
        //   - bounds: don't request tiles outside the DEM footprint
        //   - maxNativeZoom / minNativeZoom: upscale past the deepest generated
        //     tile instead of fetching zooms that were never produced
        const maxNative = file.tile_max_zoom ?? 21;
        const minZoomAllowed = file.tile_min_zoom ?? 12;
        // 1×1 transparent PNG — used when CloudFront 404s a tile (gdal2tiles
        // skips fully-nodata edge tiles), so nothing renders in their place
        // rather than the browser's broken-image icon.
        const TRANSPARENT_PNG =
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";

        const layer = new L.TileLayer(tileUrl, {
          opacity: 0.8,
          bounds: tileBounds,
          maxZoom: 26,
          maxNativeZoom: maxNative,
          minNativeZoom: minZoomAllowed,
          minZoom: Math.min(12, minZoomAllowed),
          attribution: file.filename,
          crossOrigin: 'anonymous',
          tileSize: 256,
          keepBuffer: 2,
          updateWhenIdle: false,
          updateWhenZooming: true,
          errorTileUrl: TRANSPARENT_PNG,
        });
        // Silence console noise from individual tile 404s (they're expected
        // near the DEM edge). Uncomment the console.warn line if you want to
        // log which tiles are missing.
        layer.on('tileerror', (e) => {
          (e as unknown as { tile?: HTMLImageElement }).tile?.style?.setProperty(
            'display', 'none',
          );
          // console.warn('tile missing:', (e as any).coords, (e as any).tile?.src);
        });

        // Register layer with context (doesn't show it yet)
        addLayer(file.id, file.filename, file.file_type, layer, bounds);

        if (!cancelled) {
          console.log(`Layer pre-created for ${file.filename}`);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to initialize layer:', err);
          setError(err instanceof Error ? err.message : 'Failed to initialize');
        }
      } finally {
        if (!cancelled) {
          setInitializing(false);
        }
      }
    };

    initializeLayer();

    // Cleanup function
    return () => {
      cancelled = true;
    };
  }, [map, file.id, file.filename, file.file_type, file.tile_status, file.tile_url_template, file.tile_error, file.tile_progress, file.tile_min_zoom, file.tile_max_zoom, file.bounds_south, file.bounds_west, file.bounds_north, file.bounds_east, layerExists, addLayer]);

  const handleToggle = () => {
    // Instant toggle!
    if (!layerExists) {
      setError('Layer not initialized');
      return;
    }

    toggleLayer(file.id);
    setError(null);
  };

  // Determine button state
  const isReady = layerExists && !initializing;
  const showLoading = initializing || (file.tile_status === 'processing' || file.tile_status === 'queued');

  if (showDeleteConfirm) {
    return (
      <li className="bg-red-900/20 border border-red-500/50 rounded-lg p-2 space-y-1.5">
        <div className="text-[10px] text-white font-semibold">
          Permanently delete &quot;{file.filename}&quot;?
        </div>
        <div className="text-[9px] text-white opacity-80">
          This will remove the file from both the database and cloud storage. Type &quot;permanently delete&quot; to confirm.
        </div>
        <input
          type="text"
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && confirmText === 'permanently delete') { onDelete(file.id, file.filename); setShowDeleteConfirm(false); setConfirmText(''); }
            if (e.key === 'Escape') { setShowDeleteConfirm(false); setConfirmText(''); }
          }}
          placeholder='Type: permanently delete'
          autoFocus
          className="w-full bg-white/10 text-[10px] text-white px-2 py-1 rounded border border-white/20 focus:outline-none focus:border-red-400 placeholder:text-slate-500"
        />
        <div className="flex gap-1.5">
          <button
            onClick={() => { if (confirmText === 'permanently delete') { onDelete(file.id, file.filename); setShowDeleteConfirm(false); setConfirmText(''); } }}
            disabled={confirmText !== 'permanently delete'}
            className="flex-1 bg-red-600/40 hover:bg-red-600/60 disabled:bg-red-900/20 disabled:text-slate-500 disabled:cursor-not-allowed px-2 py-0.5 rounded text-[9px] text-white font-semibold"
          >
            Delete
          </button>
          <button
            onClick={() => { setShowDeleteConfirm(false); setConfirmText(''); }}
            className="flex-1 bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded text-[9px] text-white"
          >
            Cancel
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="group/file flex items-center gap-1.5">
      <button
        type="button"
        onClick={handleToggle}
        disabled={!isReady}
        className="shrink-0 flex items-center justify-center disabled:opacity-50"
        aria-label={checked ? `Hide ${file.filename}` : `Show ${file.filename}`}
        title={checked ? `Hide ${file.filename}` : `Show ${file.filename}`}
      >
        {showLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-400" />
        ) : checked ? (
          <CheckSquare className="h-3.5 w-3.5 text-blue-400" />
        ) : (
          <Square className="h-3.5 w-3.5 text-gray-400" />
        )}
      </button>

      <div className="flex-1 min-w-0">
        <div className="truncate font-medium text-[11px]" title={file.filename}>
          {file.filename}
        </div>
        <div className="text-[10px] text-slate-400">
          <span>{formatFileSize(file.original_size_bytes)}</span>
        </div>
        {error && (
          <div className="text-[10px] text-yellow-400 truncate" title={error}>
            {error}
          </div>
        )}
      </div>

      <button
        onClick={() => setShowDeleteConfirm(true)}
        className="p-0.5 hover:bg-red-500/20 rounded transition-colors shrink-0 opacity-0 pointer-events-none group-hover/file:opacity-100 group-hover/file:pointer-events-auto"
        title="Delete file"
        aria-label={`Delete ${file.filename}`}
      >
        <Trash2 className="h-2.5 w-2.5 text-red-400" />
      </button>
    </li>
  );
}
