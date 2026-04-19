"use client";

import React, { createContext, useContext, useState, useCallback } from 'react';

export interface DrawnPolygon {
  id: string;
  name: string;
  geoJSON: any; // GeoJSON Polygon
  createdAt: Date;
  bounds?: [[number, number], [number, number]]; // Optional bounds for fitting
}

interface PolygonContextType {
  polygons: DrawnPolygon[];
  addPolygon: (polygon: Omit<DrawnPolygon, 'id' | 'createdAt'>) => DrawnPolygon;
  updatePolygon: (id: string, patch: Partial<Omit<DrawnPolygon, 'id' | 'createdAt'>>) => void;
  removePolygon: (id: string) => void;
  clearPolygons: () => void;
  getPolygon: (id: string) => DrawnPolygon | undefined;
}

const PolygonContext = createContext<PolygonContextType | undefined>(undefined);

export function PolygonProvider({ children }: { children: React.ReactNode }) {
  const [polygons, setPolygons] = useState<DrawnPolygon[]>([]);

  const addPolygon = useCallback((polygon: Omit<DrawnPolygon, 'id' | 'createdAt'>) => {
    const newPolygon: DrawnPolygon = {
      ...polygon,
      id: `polygon_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      createdAt: new Date(),
    };

    setPolygons((prev) => [newPolygon, ...prev]); // Add to beginning
    return newPolygon;
  }, []);

  const updatePolygon = useCallback((id: string, patch: Partial<Omit<DrawnPolygon, 'id' | 'createdAt'>>) => {
    setPolygons((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }, []);

  const removePolygon = useCallback((id: string) => {
    setPolygons((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clearPolygons = useCallback(() => {
    setPolygons([]);
  }, []);

  const getPolygon = useCallback((id: string) => {
    return polygons.find((p) => p.id === id);
  }, [polygons]);

  return (
    <PolygonContext.Provider
      value={{
        polygons,
        addPolygon,
        updatePolygon,
        removePolygon,
        clearPolygons,
        getPolygon,
      }}
    >
      {children}
    </PolygonContext.Provider>
  );
}

export function usePolygons() {
  const context = useContext(PolygonContext);
  if (context === undefined) {
    throw new Error('usePolygons must be used within a PolygonProvider');
  }
  return context;
}
