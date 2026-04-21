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

  // Toggle layer visibility. Side effects (addTo / removeLayer / fitBounds)
  // must run OUTSIDE the state updater — React StrictMode invokes the
  // updater twice in dev, which previously fired two competing animated
  // fitBounds and made the layer flicker / not appear on some clicks.
  const toggleLayer = useCallback((fileId: string) => {
    const layerData = allLayers.get(fileId);
    if (!layerData || !map) return;

    const isVisible = visibleLayers.has(fileId);
    if (isVisible) {
      map.removeLayer(layerData.layer);
    } else {
      layerData.layer.addTo(map);
      if (layerData.bounds) {
        // `animate: false` is load-bearing. With `updateWhenIdle: true` on
        // the TileLayer, tiles only load on `moveend`. An animated fitBounds
        // leaves a ~500 ms window where any other event (a stray map click,
        // a second toggle, StrictMode double-fire) can interrupt the
        // animation — moveend never fires for the intended viewport and
        // the layer stays blank. A synchronous jump fires moveend once,
        // immediately, so tile requests happen right away.
        map.fitBounds(layerData.bounds, { padding: [50, 50], animate: false });
      }
    }

    setVisibleLayers((prev) => {
      const newVisible = new Set(prev);
      if (isVisible) newVisible.delete(fileId);
      else newVisible.add(fileId);
      return newVisible;
    });
  }, [allLayers, map, visibleLayers]);

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
