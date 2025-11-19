"use client";

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { fetchWithAuth, API_ENDPOINTS } from '../lib/api';

interface TiffMapViewerProps {
  fileId: string;
  className?: string;
}

interface TileInfo {
  tile_url: string;
  tile_type?: 'static' | 'dynamic';
  tile_status?: string;
  bounds?: number[][];
  min_zoom?: number;
  max_zoom?: number;
  bounds_url?: string;
  info_url?: string;
  filename: string;
  file_type: string;
  is_cog?: boolean;
}

interface TileStatus {
  tile_status: string;
  tile_progress: number;
  tile_error?: string;
}

/**
 * Component to fit map to the raster bounds
 */
function FitBounds({ bounds }: { bounds: number[][] | null }) {
  const map = useMap();

  useEffect(() => {
    if (bounds && bounds.length === 2) {
      // bounds format: [[south, west], [north, east]]
      const leafletBounds = L.latLngBounds(
        [bounds[0][1], bounds[0][0]], // southwest: [lat, lon]
        [bounds[1][1], bounds[1][0]]  // northeast: [lat, lon]
      );
      map.fitBounds(leafletBounds);
    }
  }, [bounds, map]);

  return null;
}

/**
 * TiffMapViewer displays a TIFF file on a Leaflet map using TiTiler
 */
export default function TiffMapViewer({ fileId, className = 'h-96 w-full' }: TiffMapViewerProps) {
  const [tileInfo, setTileInfo] = useState<TileInfo | null>(null);
  const [bounds, setBounds] = useState<number[][] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tileStatus, setTileStatus] = useState<TileStatus | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Fetch tile info
  useEffect(() => {
    const fetchTileInfo = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch tile info from backend
        const response = await fetchWithAuth(API_ENDPOINTS.FILES.TILES(fileId));

        if (!response.ok) {
          throw new Error('Failed to fetch tile information');
        }

        const data = await response.json();
        setTileInfo(data);

        // Set bounds if available in response (new API includes bounds directly)
        if (data.bounds) {
          setBounds(data.bounds);
        } else if (data.bounds_url) {
          // Fallback to fetching bounds separately (old API)
          const boundsResponse = await fetch(data.bounds_url);
          if (boundsResponse.ok) {
            const boundsData = await boundsResponse.json();
            if (boundsData.bounds) {
              setBounds(boundsData.bounds);
            }
          }
        }

        // Check if tiles are still being generated
        if (data.tile_status && ['queued', 'processing'].includes(data.tile_status)) {
          setIsGenerating(true);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load map');
        console.error('Error loading tile info:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchTileInfo();
  }, [fileId]);

  // Poll for tile generation status
  useEffect(() => {
    if (!isGenerating) return;

    const pollStatus = async () => {
      try {
        const response = await fetchWithAuth(`/api/tiles-status/${fileId}`);
        if (response.ok) {
          const status: TileStatus = await response.json();
          setTileStatus(status);

          // If completed or failed, stop polling and refresh tile info
          if (status.tile_status === 'completed' || status.tile_status === 'failed') {
            setIsGenerating(false);
            // Refresh tile info to get new static tile URLs
            const tilesResponse = await fetchWithAuth(API_ENDPOINTS.FILES.TILES(fileId));
            if (tilesResponse.ok) {
              const data = await tilesResponse.json();
              setTileInfo(data);
              if (data.bounds) {
                setBounds(data.bounds);
              }
            }
          }
        }
      } catch (err) {
        console.error('Error polling tile status:', err);
      }
    };

    // Poll every 2 seconds
    const intervalId = setInterval(pollStatus, 2000);

    // Initial poll
    pollStatus();

    return () => clearInterval(intervalId);
  }, [isGenerating, fileId]);

  if (loading) {
    return (
      <div className={`${className} flex items-center justify-center bg-slate-100 rounded-lg`}>
        <div className="text-slate-600">Loading map...</div>
      </div>
    );
  }

  if (error || !tileInfo) {
    return (
      <div className={`${className} flex items-center justify-center bg-red-50 rounded-lg`}>
        <div className="text-red-600">{error || 'Failed to load map'}</div>
      </div>
    );
  }

  // Default center (will be adjusted by FitBounds if bounds are available)
  const defaultCenter: [number, number] = [41.878, -93.097];

  // Determine tile attribution and max zoom
  const isStaticTiles = tileInfo.tile_type === 'static';
  const tileAttribution = isStaticTiles
    ? 'Static tiles (cloud/CDN)'
    : 'Dynamic tiles (rio-tiler)';
  const maxZoom = tileInfo.max_zoom || 18;

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between text-sm text-slate-600">
        <div>
          <span className="font-semibold">{tileInfo.filename}</span>
          <span className="ml-2 text-xs text-slate-500">
            ({tileInfo.file_type})
            {tileInfo.is_cog && <span className="ml-1 text-green-600">COG</span>}
          </span>
        </div>
        <div className="text-xs">
          {isStaticTiles && (
            <span className="px-2 py-1 bg-green-100 text-green-800 rounded">
              ⚡ Static Tiles
            </span>
          )}
          {tileInfo.tile_type === 'dynamic' && (
            <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded">
              Dynamic
            </span>
          )}
        </div>
      </div>

      {/* Tile generation progress indicator */}
      {isGenerating && tileStatus && (
        <div className="mb-2 p-2 bg-blue-50 border border-blue-200 rounded text-sm">
          <div className="flex items-center justify-between mb-1">
            <span className="text-blue-700 font-medium">
              Generating static tiles...
            </span>
            <span className="text-blue-600">{tileStatus.tile_progress}%</span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${tileStatus.tile_progress}%` }}
            />
          </div>
          <div className="text-xs text-blue-600 mt-1">
            Map is using dynamic tiles. Static tiles will load automatically when ready.
          </div>
        </div>
      )}

      {/* Error indicator */}
      {tileStatus?.tile_error && (
        <div className="mb-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          Tile generation failed: {tileStatus.tile_error}
        </div>
      )}

      <div className="h-full w-full rounded-lg overflow-hidden border border-slate-300">
        <MapContainer
          center={defaultCenter}
          zoom={10}
          className="h-full w-full"
          scrollWheelZoom={true}
        >
          {/* Base map layer */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* TIFF/COG tile layer */}
          <TileLayer
            url={tileInfo.tile_url}
            attribution={tileAttribution}
            maxZoom={maxZoom}
            minZoom={tileInfo.min_zoom}
            opacity={0.8}
          />

          {/* Fit map to raster bounds */}
          <FitBounds bounds={bounds} />
        </MapContainer>
      </div>
    </div>
  );
}
