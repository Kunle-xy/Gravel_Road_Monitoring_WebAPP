"use client";

import React, { createContext, useContext, useState, useSyncExternalStore } from 'react';
import { createPolygonStore } from '../lib/polygonStore';
export type { DrawnPolygon } from '../lib/polygonStore';

const PolygonContext = createContext<ReturnType<typeof createPolygonStore> | undefined>(undefined);

export function PolygonProvider({ children }: { children: React.ReactNode }) {
  const [store] = useState(createPolygonStore);
  return <PolygonContext.Provider value={store}>{children}</PolygonContext.Provider>;
}

export function usePolygons() {
  const store = useContext(PolygonContext);
  if (!store) throw new Error('usePolygons must be used within a PolygonProvider');
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  return { ...store, ...state };
}
