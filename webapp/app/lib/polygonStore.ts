export type RoadDirection = 'horizontal' | 'vertical';
export interface PolygonGeometry {
  type: 'Polygon';
  coordinates: number[][][];
  horizontal_edge_index?: number;
}
export interface DrawnPolygon {
  id: string;
  name: string;
  geoJSON: PolygonGeometry;
  roadDirection: RoadDirection;
  createdAt: Date;
  bounds?: [[number, number], [number, number]];
}
type PolygonInput = Omit<DrawnPolygon, 'id' | 'createdAt' | 'roadDirection'> & {
  roadDirection?: RoadDirection;
};
type PolygonPatch = Partial<Omit<DrawnPolygon, 'id' | 'createdAt'>>;
export interface PolygonState {
  polygons: DrawnPolygon[];
  selectedPolygonId: string;
  editingPolygonId: string | null;
}

export function polygonSelectionKey(polygon: DrawnPolygon | undefined, demId: string) {
  return JSON.stringify([demId, polygon?.id, polygon?.roadDirection, polygon?.geoJSON]);
}

// Publish synchronously: clicks and async callbacks read current geometry and
// direction without waiting for a React render or using an old closure.
export function createPolygonStore() {
  let state: PolygonState = { polygons: [], selectedPolygonId: '', editingPolygonId: null };
  const listeners = new Set<() => void>();
  const publish = (next: PolygonState) => {
    state = next;
    listeners.forEach(listener => listener());
  };
  const getPolygon = (id: string) => state.polygons.find(p => p.id === id);
  const updatePolygon = (id: string, patch: PolygonPatch) => {
    publish({ ...state, polygons: state.polygons.map(p => p.id === id ? { ...p, ...patch } : p) });
  };
  return {
    getSnapshot: () => state,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    getPolygon,
    updatePolygon,
    addPolygon: (input: PolygonInput): DrawnPolygon => {
      const polygon: DrawnPolygon = {
        ...input, roadDirection: input.roadDirection ?? 'horizontal',
        id: `polygon_${globalThis.crypto.randomUUID()}`, createdAt: new Date(),
      };
      publish({ ...state, polygons: [polygon, ...state.polygons], selectedPolygonId: polygon.id });
      return polygon;
    },
    setSelectedPolygonId: (id: string) => {
      if (id && !getPolygon(id)) return;
      if (state.selectedPolygonId !== id) publish({ ...state, selectedPolygonId: id });
    },
    updatePolygonGeometry: (id: string, coordinates: number[][][], bounds: DrawnPolygon['bounds']) => {
      const polygon = getPolygon(id);
      if (!polygon) return;
      // Preserve the stable edge and latest radio selection, not an old render.
      updatePolygon(id, { geoJSON: { ...polygon.geoJSON, coordinates }, bounds });
    },
    beginPolygonEdit: (id: string) => {
      if (getPolygon(id)) publish({ ...state, editingPolygonId: id });
    },
    finishPolygonEdit: (id: string) => {
      if (state.editingPolygonId === id) publish({ ...state, editingPolygonId: null });
    },
    isAnalysisSelectionCurrent: (key: string | null, demId: string) => {
      const polygon = getPolygon(state.selectedPolygonId);
      return !!polygon && state.editingPolygonId !== polygon.id && key === polygonSelectionKey(polygon, demId);
    },
    getAnalysisSelection: (demId: string) => {
      const polygon = getPolygon(state.selectedPolygonId);
      if (!polygon) throw new Error('Select a polygon first.');
      if (state.editingPolygonId === polygon.id) throw new Error('Finish dragging the polygon before running analysis.');
      return {
        key: polygonSelectionKey(polygon, demId),
        polygon_geojson: structuredClone(polygon.geoJSON),
        road_direction: polygon.roadDirection,
      };
    },
    removePolygon: (id: string) => publish({
      polygons: state.polygons.filter(p => p.id !== id),
      selectedPolygonId: state.selectedPolygonId === id ? '' : state.selectedPolygonId,
      editingPolygonId: state.editingPolygonId === id ? null : state.editingPolygonId,
    }),
    clearPolygons: () => publish({ polygons: [], selectedPolygonId: '', editingPolygonId: null }),
  };
}
