"use client";

import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import type { Map as LeafletMap } from 'leaflet';

interface TiffLayer {
  fileId: string;
  filename: string;
  fileType: string;
  layer: any; // Leaflet TileLayer
  bounds: [[number, number], [number, number]] | null; // Pre-calculated bounds
}

interface MapContextType {
  map: LeafletMap | null;
  setMap: (map: LeafletMap | null) => void;
  // All layers (pre-created)
  allLayers: Map<string, TiffLayer>;
  // Visible layers (just IDs)
  visibleLayers: Set<string>;
  // Add a pre-created layer to the map
  addLayer: (fileId: string, filename: string, fileType: string, layer: any, bounds: [[number, number], [number, number]] | null) => void;
  // Toggle layer visibility (fast CSS toggle)
  toggleLayer: (fileId: string) => void;
  // Check if layer is visible
  isLayerVisible: (fileId: string) => boolean;
}

const MapContext = createContext<MapContextType | undefined>(undefined);

export function MapProvider({ children }: { children: React.ReactNode }) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const [allLayers, setAllLayers] = useState<Map<string, TiffLayer>>(new Map());
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set());

  // Add a layer to the registry (doesn't show it yet)
  const addLayer = useCallback((fileId: string, filename: string, fileType: string, layer: any, bounds: [[number, number], [number, number]] | null) => {
    setAllLayers((prev) => {
      const newLayers = new Map(prev);
      newLayers.set(fileId, { fileId, filename, fileType, layer, bounds });
      return newLayers;
    });
  }, []);

  // Toggle layer visibility
  const toggleLayer = useCallback((fileId: string) => {
    const layerData = allLayers.get(fileId);
    if (!layerData || !map) return;

    setVisibleLayers((prev) => {
      const newVisible = new Set(prev);
      if (newVisible.has(fileId)) {
        // Hide layer
        map.removeLayer(layerData.layer);
        newVisible.delete(fileId);
      } else {
        // Show layer
        layerData.layer.addTo(map);
        newVisible.add(fileId);

        // Fit bounds if available
        if (layerData.bounds) {
          map.fitBounds(layerData.bounds, { padding: [50, 50], animate: true, duration: 0.5 });
        }
      }
      return newVisible;
    });
  }, [allLayers, map]);

  // Check if layer is visible
  const isLayerVisible = useCallback((fileId: string) => {
    return visibleLayers.has(fileId);
  }, [visibleLayers]);

  const value = useMemo(() => ({
    map,
    setMap,
    allLayers,
    visibleLayers,
    addLayer,
    toggleLayer,
    isLayerVisible,
  }), [map, allLayers, visibleLayers, addLayer, toggleLayer, isLayerVisible]);

  return <MapContext.Provider value={value}>{children}</MapContext.Provider>;
}

export function useMap() {
  const context = useContext(MapContext);
  if (context === undefined) {
    throw new Error('useMap must be used within a MapProvider');
  }
  return context;
}
