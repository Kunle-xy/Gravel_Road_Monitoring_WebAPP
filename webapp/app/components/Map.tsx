// app/components/Map.tsx
"use client";

import React from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap as useLeafletMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useMap } from "../contexts/MapContext";
import { usePolygons } from "../contexts/PolygonContext";
import { attachPointerDrag, rotatePoints, resizeEdge, samplingPreview } from "../lib/polygonEditing";

// fix default marker assets in Next
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";

L.Icon.Default.mergeOptions({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
});

type Mode = "pan" | "draw" | "none";

/* Register map instance with MapContext */
function MapInstanceRegistration() {
  const leafletMap = useLeafletMap();
  const { setMap } = useMap();

  React.useEffect(() => {
    setMap(leafletMap);
    return () => setMap(null);
  }, [leafletMap, setMap]);

  return null;
}

/* Control to toggle map labels */
function LabelsToggleControl({
  showLabels,
  setShowLabels,
}: {
  showLabels: boolean;
  setShowLabels: (show: boolean) => void;
}) {
  const leafletMap = useLeafletMap();
  const btnRef = React.useRef<HTMLAnchorElement | null>(null);
  const showLabelsRef = React.useRef(showLabels);
  React.useLayoutEffect(() => { showLabelsRef.current = showLabels; }, [showLabels]);

  // Create control once
  React.useEffect(() => {
    const LabelsControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";
        btnRef.current = btn;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          setShowLabels(!showLabelsRef.current);
        });

        return container;
      },
    });

    const control = new LabelsControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, setShowLabels]);

  // Update appearance without removing/re-adding
  React.useEffect(() => {
    const btn = btnRef.current;
    if (!btn) return;
    btn.title = showLabels ? "Map view" : "Satellite view";
    btn.setAttribute("aria-label", btn.title);
    btn.style.backgroundColor = showLabels ? "#e0e7ff" : "";
    btn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="${showLabels ? "#2563eb" : "#111827"}" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>
        <line x1="8" y1="2" x2="8" y2="18"/>
        <line x1="16" y1="6" x2="16" y2="22"/>
      </svg>
    `;
  }, [showLabels]);

  return null;
}

/* Control to toggle polygon drawing */
function DrawPolygonControl({
  mode,
  setMode,
}: {
  mode: Mode;
  setMode: (m: Mode) => void;
}) {
  const leafletMap = useLeafletMap();
  const btnRef = React.useRef<HTMLAnchorElement | null>(null);
  const modeRef = React.useRef(mode);
  React.useLayoutEffect(() => { modeRef.current = mode; }, [mode]);

  // Create control once
  React.useEffect(() => {
    const DrawControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";
        btnRef.current = btn;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          setMode(modeRef.current === "draw" ? "pan" : "draw");
        });

        return container;
      },
    });

    const control = new DrawControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, setMode]);

  // Update appearance on mode change without removing/re-adding
  React.useEffect(() => {
    const btn = btnRef.current;
    if (!btn) return;
    const active = mode === "draw";
    btn.title = active ? "Stop drawing" : "Draw rectangle (top-left, then bottom-right)";
    btn.setAttribute("aria-label", btn.title);
    btn.style.backgroundColor = active ? "#e0e7ff" : "";
    btn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="${active ? "#2563eb" : "#111827"}" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="1"/>
        <circle cx="3" cy="3" r="2.5" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
        <circle cx="21" cy="3" r="2.5" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
        <circle cx="21" cy="21" r="2.5" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
        <circle cx="3" cy="21" r="2.5" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
      </svg>
    `;
  }, [mode]);

  return null;
}

/* Control to cancel/clear drawn polygons */
function ClearPolygonsControl({
  onClear,
}: {
  onClear: () => void;
}) {
  const leafletMap = useLeafletMap();
  const onClearRef = React.useRef(onClear);
  React.useLayoutEffect(() => { onClearRef.current = onClear; }, [onClear]);

  React.useEffect(() => {
    const ClearControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.title = "Clear polygons";
        btn.setAttribute("aria-label", "Clear polygons");
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";

        btn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
            fill="none" stroke="#dc2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6"/>
            <path d="M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        `;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          onClearRef.current();
        });

        return container;
      },
    });

    const control = new ClearControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap]);

  return null;
}

/* Handle rectangle drawing — two clicks (top-left + bottom-right) */
function PolygonDrawing({
  mode,
  onPolygonComplete,
}: {
  mode: Mode;
  onPolygonComplete: (polygon: L.Polygon) => void;
}) {
  const leafletMap = useLeafletMap();

  React.useEffect(() => {
    if (mode !== "draw") return;

    let firstCorner: L.LatLng | null = null;
    let firstMarker: L.Marker | null = null;
    let previewRect: L.Rectangle | null = null;

    const cornerIcon = L.divIcon({
      className: 'polygon-vertex',
      html: '<div style="width: 10px; height: 10px; background: #2563eb; border: 2px solid white; border-radius: 50%;"></div>',
      iconSize: [10, 10],
    });

    const cleanup = () => {
      if (firstMarker) leafletMap.removeLayer(firstMarker);
      if (previewRect) leafletMap.removeLayer(previewRect);
      firstCorner = null;
      firstMarker = null;
      previewRect = null;
    };

    const handleClick = (e: L.LeafletMouseEvent) => {
      if (!firstCorner) {
        // First click — anchor the top-left (or any first) corner
        firstCorner = e.latlng;
        firstMarker = L.marker(e.latlng, { icon: cornerIcon }).addTo(leafletMap);
        return;
      }

      // Second click — build the final rectangle from the two opposite corners
      const rect = L.rectangle(L.latLngBounds(firstCorner, e.latlng), {
        color: '#2563eb',
        fillColor: '#3b82f6',
        fillOpacity: 0.3,
        weight: 2,
        bubblingMouseEvents: false,  // polygon click must not bubble to map
      });

      cleanup();
      onPolygonComplete(rect as unknown as L.Polygon);
    };

    const handleMouseMove = (e: L.LeafletMouseEvent) => {
      if (!firstCorner) return;
      const bounds = L.latLngBounds(firstCorner, e.latlng);
      if (previewRect) {
        previewRect.setBounds(bounds);
      } else {
        previewRect = L.rectangle(bounds, {
          color: '#2563eb',
          weight: 2,
          dashArray: '5, 5',
          fill: false,
        }).addTo(leafletMap);
      }
    };

    leafletMap.on('click', handleClick);
    leafletMap.on('mousemove', handleMouseMove);
    leafletMap.getContainer().style.cursor = 'crosshair';

    return () => {
      leafletMap.off('click', handleClick);
      leafletMap.off('mousemove', handleMouseMove);
      leafletMap.getContainer().style.cursor = '';
      cleanup();
    };
  }, [leafletMap, mode, onPolygonComplete]);

  return null;
}

/* enable or disable map interactions based on mode */
function MapInteractions({ mode }: { mode: Mode }) {
  const leafletMap = useLeafletMap();

  React.useEffect(() => {
    const enable = mode === "pan";
    leafletMap.dragging[enable ? "enable" : "disable"]();
    leafletMap.scrollWheelZoom[enable ? "enable" : "disable"]();
    leafletMap.doubleClickZoom[enable ? "enable" : "disable"]();
    leafletMap.boxZoom[enable ? "enable" : "disable"]();
    leafletMap.keyboard[enable ? "enable" : "disable"]();
    leafletMap.touchZoom[enable ? "enable" : "disable"]();
  }, [leafletMap, mode]);

  return null;
}

/* leaflets native control so it stacks directly under the zoom control */
function PanToggleControl({
  mode,
  setMode,
}: {
  mode: Mode;
  setMode: (m: Mode) => void;
}) {
  const leafletMap = useLeafletMap();
  const btnRef = React.useRef<HTMLAnchorElement | null>(null);
  const modeRef = React.useRef(mode);
  React.useLayoutEffect(() => { modeRef.current = mode; }, [mode]);

  // Create control once
  React.useEffect(() => {
    const PanControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";
        btnRef.current = btn;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          setMode(modeRef.current === "pan" ? "none" : "pan");
        });

        return container;
      },
    });

    const control = new PanControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, setMode]);

  // Update appearance on mode change without removing/re-adding
  React.useEffect(() => {
    const btn = btnRef.current;
    if (!btn) return;
    const active = mode === "pan";
    btn.title = active ? "Turn off pan" : "Turn on pan";
    btn.setAttribute("aria-label", btn.title);
    btn.style.backgroundColor = active ? "#e0e7ff" : "";
    btn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="${active ? "#2563eb" : "#111827"}" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/>
        <path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/>
        <path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/>
        <path d="M18 8a2 2 0 0 1 2 2v7.4a2 2 0 0 1-.6 1.4l-3 2.9a1 1 0 0 1-.7.3H11a2 2 0 0 1-1.7-1l-4-6.1"/>
      </svg>
    `;
  }, [mode]);

  return null;
}

type DrawnLayer = L.Polygon & { polygonId?: string; label?: L.Marker };

function projectedCorners(map: L.Map, polygon: DrawnLayer): L.Point[] {
  return (polygon.getLatLngs()[0] as L.LatLng[]).map(ll => map.project(ll));
}

function polygonCenter(map: L.Map, polygon: DrawnLayer): L.Point {
  const points = projectedCorners(map, polygon);
  return L.point(points.reduce((sum, p) => sum + p.x, 0) / points.length,
    points.reduce((sum, p) => sum + p.y, 0) / points.length);
}

function pauseMapEditing(map: L.Map): () => void {
  const handlers = [map.dragging, map.boxZoom, map.scrollWheelZoom,
    map.doubleClickZoom, map.touchZoom, map.keyboard];
  const previous = handlers.map(handler => handler.enabled());
  handlers.forEach(handler => handler.disable());
  return () => handlers.forEach((handler, i) => {
    if (previous[i]) handler.enable();
  });
}

function RotationHandle({ map, polygon, onCommit, onDismiss }: {
  map: L.Map; polygon: DrawnLayer;
  onCommit: (polygon: DrawnLayer) => void; onDismiss: () => void;
}) {
  const { beginPolygonEdit, finishPolygonEdit } = usePolygons();
  React.useEffect(() => {
    const position = () => {
      const center = polygonCenter(map, polygon);
      return map.unproject(L.point(center.x, center.y - 38));
    };
    const handle = L.marker(position(), {
      icon: L.divIcon({
        className: 'rotate-handle',
        html: '<div style="width:26px;height:26px;border-radius:50%;background:white;border:2px solid #2563eb;display:flex;align-items:center;justify-content:center;color:#2563eb;cursor:grab;font-size:22px" title="Rotate polygon">↻</div>',
        iconSize: [26, 26], iconAnchor: [13, 13],
      }),
      interactive: true, bubblingMouseEvents: false, keyboard: false, zIndexOffset: 1000,
    }).addTo(map);
    const element = handle.getElement();
    if (!element) return () => { map.removeLayer(handle); };
    L.DomEvent.disableClickPropagation(element);
    L.DomEvent.disableScrollPropagation(element);
    let dragging = false;
    const detach = attachPointerDrag(element, event => {
      if (!polygon.polygonId) return;
      const id = polygon.polygonId;
      const restore = pauseMapEditing(map);
      const snapshot = projectedCorners(map, polygon);
      const center = polygonCenter(map, polygon);
      const start = map.project(map.mouseEventToLatLng(event));
      const startAngle = Math.atan2(start.y - center.y, start.x - center.x);
      dragging = true;
      beginPolygonEdit(id);
      document.body.style.cursor = 'grabbing';
      return {
        move: ev => {
          const point = map.project(map.mouseEventToLatLng(ev));
          const angle = Math.atan2(point.y - center.y, point.x - center.x) - startAngle;
          const corners = rotatePoints(snapshot, center, angle).map(p => map.unproject(L.point(p.x, p.y)));
          polygon.setLatLngs([corners]);
          polygon.label?.setLatLng(map.unproject(center));
          handle.setLatLng(position());
          polygon.fire('reshape');
        },
        finish: () => {
          dragging = false;
          document.body.style.cursor = '';
          restore();
          try { onCommit(polygon); } finally { finishPolygonEdit(id); }
        },
      };
    });
    map.on('zoomstart movestart', detach.finish);
    const refresh = () => { if (!dragging) handle.setLatLng(position()); };
    map.on('zoomend moveend', refresh);
    polygon.on('reshape', refresh);
    const onKey = (ev: KeyboardEvent) => { if (ev.key === 'Escape') onDismiss(); };
    document.addEventListener('keydown', onKey);
    return () => {
      detach();
      map.off('zoomstart movestart', detach.finish);
      map.off('zoomend moveend', refresh);
      polygon.off('reshape', refresh);
      document.removeEventListener('keydown', onKey);
      map.removeLayer(handle);
    };
  }, [map, polygon, onCommit, onDismiss, beginPolygonEdit, finishPolygonEdit]);
  return null;
}

function EdgeResizeHandles({ map, polygon, onCommit }: {
  map: L.Map; polygon: DrawnLayer; onCommit: (polygon: DrawnLayer) => void;
}) {
  const [selectedEdge, setSelectedEdge] = React.useState<number | null>(null);
  const { beginPolygonEdit, finishPolygonEdit } = usePolygons();
  React.useEffect(() => {
    const zones = Array.from({ length: 4 }, (_, i) => {
      const corners = polygon.getLatLngs()[0] as L.LatLng[];
      const zone = L.polyline([corners[i], corners[(i + 1) % 4]], {
        opacity: 0, weight: 18, interactive: true, bubblingMouseEvents: false,
      }).addTo(map);
      zone.on('click', (event: L.LeafletMouseEvent) => {
        L.DomEvent.stopPropagation(event.originalEvent);
        setSelectedEdge(i);
      });
      return zone;
    });
    const refresh = () => {
      const corners = polygon.getLatLngs()[0] as L.LatLng[];
      zones.forEach((zone, i) => zone.setLatLngs([corners[i], corners[(i + 1) % 4]]));
    };
    polygon.on('reshape', refresh);
    return () => {
      polygon.off('reshape', refresh);
      zones.forEach(zone => map.removeLayer(zone));
    };
  }, [map, polygon]);

  React.useEffect(() => {
    if (selectedEdge === null) return;
    const corners = polygon.getLatLngs()[0] as L.LatLng[];
    const i = selectedEdge, j = (i + 1) % 4;
    const highlight = L.polyline([corners[i], corners[j]], {
      color: '#2563eb', weight: 4, interactive: false,
    }).addTo(map);
    const midpoint = () => {
      const points = projectedCorners(map, polygon);
      return map.unproject(L.point((points[i].x + points[j].x) / 2, (points[i].y + points[j].y) / 2));
    };
    const grip = L.marker(midpoint(), {
      icon: L.divIcon({
        className: 'edge-resize-grip',
        html: '<div style="width:14px;height:14px;background:#2563eb;border:2px solid white;border-radius:3px;cursor:move" title="Resize polygon edge"></div>',
        iconSize: [14, 14], iconAnchor: [7, 7],
      }),
      interactive: true, bubblingMouseEvents: false, keyboard: false, zIndexOffset: 1100,
    }).addTo(map);
    const refresh = () => {
      const current = polygon.getLatLngs()[0] as L.LatLng[];
      highlight.setLatLngs([current[i], current[j]]);
      grip.setLatLng(midpoint());
    };
    const element = grip.getElement();
    const detach = element ? attachPointerDrag(element, event => {
      if (!polygon.polygonId) return;
      const id = polygon.polygonId;
      const restore = pauseMapEditing(map);
      const snapshot = projectedCorners(map, polygon);
      const start = map.project(map.mouseEventToLatLng(event));
      beginPolygonEdit(id);
      return {
        move: ev => {
          const point = map.project(map.mouseEventToLatLng(ev));
          const points = resizeEdge(snapshot, i, { x: point.x - start.x, y: point.y - start.y });
          polygon.setLatLngs([points.map(p => map.unproject(L.point(p.x, p.y)))]);
          polygon.label?.setLatLng(map.unproject(polygonCenter(map, polygon)));
          polygon.fire('reshape');
        },
        finish: () => {
          restore();
          try { onCommit(polygon); } finally { finishPolygonEdit(id); }
        },
      };
    }) : Object.assign(() => {}, { finish: () => {} });
    map.on('zoomstart movestart', detach.finish);
    if (element) {
      L.DomEvent.disableClickPropagation(element);
      L.DomEvent.disableScrollPropagation(element);
    }
    polygon.on('reshape', refresh);
    map.on('zoomend moveend', refresh);
    const onKey = (ev: KeyboardEvent) => { if (ev.key === 'Escape') setSelectedEdge(null); };
    document.addEventListener('keydown', onKey);
    return () => {
      detach();
      map.off('zoomstart movestart', detach.finish);
      polygon.off('reshape', refresh);
      map.off('zoomend moveend', refresh);
      document.removeEventListener('keydown', onKey);
      map.removeLayer(highlight);
      map.removeLayer(grip);
    };
  }, [map, polygon, onCommit, selectedEdge, beginPolygonEdit, finishPolygonEdit]);
  return null;
}

function SamplingPreview({ map, polygon, direction, edge }: {
  map: L.Map; polygon: DrawnLayer; direction: 'horizontal' | 'vertical'; edge: number;
}) {
  React.useEffect(() => {
    const layer = L.layerGroup().addTo(map);
    const colors = { across: '#fbbf24', along: '#22d3ee' };
    const guides = Object.fromEntries(Object.entries(colors).map(([kind, color]) => [kind,
      Array.from({ length: 4 }, () => L.polyline([], {
        color, weight: 1.5, dashArray: '5 5', interactive: false,
      }).addTo(layer)),
    ]));
    const refresh = () => {
      const lines = samplingPreview(projectedCorners(map, polygon), edge, direction);
      for (const kind of ['across', 'along'] as const) {
        lines[kind].forEach((points, i) => guides[kind][i].setLatLngs(
          points.map(p => map.unproject(L.point(p.x, p.y))),
        ));
      }
    };
    refresh();
    polygon.on('reshape', refresh);
    map.on('zoomend', refresh);
    return () => {
      polygon.off('reshape', refresh);
      map.off('zoomend', refresh);
      map.removeLayer(layer);
    };
  }, [map, polygon, direction, edge]);
  return null;
}

export default function Map() {
  const [mode, setMode] = React.useState<Mode>("pan");
  const [showSatellite, setShowSatellite] = React.useState(false);
  const [polygons, setPolygons] = React.useState<DrawnLayer[]>([]);
  const [dismissedPolygonId, setDismissedPolygonId] = React.useState<string | null>(null);
  const [mapInstance, setMapInstance] = React.useState<L.Map | null>(null);
  const { addPolygon, updatePolygonGeometry, clearPolygons: clearPolygonsContext,
    polygons: savedPolygons, selectedPolygonId, setSelectedPolygonId } = usePolygons();
  const activePolygon = polygons.find(p => p.polygonId === selectedPolygonId);
  const selectedPolygon = selectedPolygonId === dismissedPolygonId ? null : activePolygon;
  const selectedSettings = savedPolygons.find(p => p.id === selectedPolygonId);
  const center: [number, number] = [41.878, -93.097];

  // Hide editing handles without losing the shared analysis selection/settings.
  React.useEffect(() => {
    if (!mapInstance) return;
    const handler = () => setDismissedPolygonId(selectedPolygonId);
    mapInstance.on('click', handler);
    return () => {
      mapInstance.off('click', handler);
    };
  }, [mapInstance, selectedPolygonId]);

  const handleRotationDismiss = React.useCallback(() => setDismissedPolygonId(selectedPolygonId), [selectedPolygonId]);

  const handleRotationCommit = React.useCallback((polygon: DrawnLayer) => {
    if (!polygon.polygonId) return;
    const coordinates = (polygon.getLatLngs()[0] as L.LatLng[]).map(ll => [ll.lng, ll.lat]);
    coordinates.push([...coordinates[0]]);
    const b = polygon.getBounds();
    updatePolygonGeometry(polygon.polygonId, [coordinates], [
      [b.getSouth(), b.getWest()], [b.getNorth(), b.getEast()],
    ]);
  }, [updatePolygonGeometry]);

  const handlePolygonComplete = React.useCallback((polygon: L.Polygon) => {
    if (mapInstance) {
      polygon.addTo(mapInstance);
      const tagged = polygon as DrawnLayer;
      setMode("pan");
      setDismissedPolygonId(null);

      // Convert Leaflet polygon to GeoJSON and save to context
      const latLngs = polygon.getLatLngs()[0] as L.LatLng[];
      const coordinates = latLngs.map(ll => [ll.lng, ll.lat]);
      // Close the polygon if not already closed
      if (coordinates[0][0] !== coordinates[coordinates.length - 1][0] ||
          coordinates[0][1] !== coordinates[coordinates.length - 1][1]) {
        coordinates.push(coordinates[0]);
      }

      const geoJSON = {
        type: "Polygon" as const,
        coordinates: [coordinates],
        // Leaflet rectangles use SW, NW, NE, SE: edge 1 is horizontal.
        // Keep this index stable through rotation and resizing, even for squares.
        horizontal_edge_index: 1,
      };

      // Get bounds for the polygon
      const bounds = polygon.getBounds();
      const polygonBounds: [[number, number], [number, number]] = [
        [bounds.getSouth(), bounds.getWest()],
        [bounds.getNorth(), bounds.getEast()]
      ];

      // Save to context with auto-generated name
      const polygonCount = savedPolygons.length + 1;
      const polygonName = `Polygon ${polygonCount}`;

      const saved = addPolygon({
        name: polygonName,
        geoJSON,
        bounds: polygonBounds,
      });
      tagged.polygonId = saved.id;
      setPolygons(prev => [...prev, tagged]);

      // Add label to polygon center
      const labelCenter = polygon.getBounds().getCenter();
      const label = L.marker(labelCenter, {
        icon: L.divIcon({
          className: 'polygon-label',
          html: `<div style="
            background: rgba(37, 99, 235, 0.9);
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            white-space: nowrap;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            pointer-events: none;
          ">${polygonName}</div>`,
          iconSize: [60, 20],
        }),
        interactive: false,  // label must not eat clicks meant for the polygon
        keyboard: false,
      }).addTo(mapInstance);

      // Store label with polygon for later removal
      tagged.label = label;

      // Clicking the polygon selects it for rotation
      tagged.on('click', (evt: L.LeafletMouseEvent) => {
        L.DomEvent.stopPropagation(evt.originalEvent);
        if (tagged.polygonId) setSelectedPolygonId(tagged.polygonId);
        setDismissedPolygonId(null);
      });
    }
  }, [mapInstance, addPolygon, savedPolygons.length, setSelectedPolygonId]);

  const handleClearPolygons = React.useCallback(() => {
    if (mapInstance) {
      polygons.forEach(polygon => {
        // Remove the polygon itself
        mapInstance.removeLayer(polygon);

        // Remove the label if it exists
        if (polygon.label) {
          mapInstance.removeLayer(polygon.label);
        }
      });
      setPolygons([]);
      setDismissedPolygonId(null);
      clearPolygonsContext();
    }
  }, [mapInstance, polygons, clearPolygonsContext]);

  // Don't keep a selection active while the user is drawing a new rectangle
  React.useEffect(() => {
    if (mode === "draw") setDismissedPolygonId(selectedPolygonId);
  }, [mode, selectedPolygonId]);

  return (
    <div className="relative h-screen w-full overflow-hidden rounded-xl z-0">
      <MapContainer
        center={center}
        zoom={7}
        className="h-full w-full"
        zoomAnimation
        markerZoomAnimation
        maxZoom={26}
        minZoom={1}
        ref={(map) => {
          if (map) setMapInstance(map);
        }}
      >
        {/* Base layer - map or satellite */}
        {showSatellite ? (
          <TileLayer
            attribution='&copy; <a href="https://www.esri.com">Esri</a>'
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxZoom={26}
            maxNativeZoom={19}
            minZoom={1}
          />
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={26}
            maxNativeZoom={19}
            minZoom={1}
          />
        )}

        <Marker position={center}>
          <Popup>Gravel Road Iowa, map is ready</Popup>
        </Marker>

        <MapInstanceRegistration />
        <MapInteractions mode={mode} />
        <PanToggleControl mode={mode} setMode={setMode} />
        <LabelsToggleControl showLabels={showSatellite} setShowLabels={setShowSatellite} />
        <DrawPolygonControl mode={mode} setMode={setMode} />
        <ClearPolygonsControl onClear={handleClearPolygons} />
        <PolygonDrawing mode={mode} onPolygonComplete={handlePolygonComplete} />
        {mapInstance && activePolygon && selectedSettings && (
          <SamplingPreview map={mapInstance} polygon={activePolygon}
            direction={selectedSettings.roadDirection} edge={selectedSettings.geoJSON.horizontal_edge_index ?? 1} />
        )}
        {mapInstance && selectedPolygon && (
          <>
            <EdgeResizeHandles
              key={selectedPolygon.polygonId}
              map={mapInstance}
              polygon={selectedPolygon}
              onCommit={handleRotationCommit}
            />
            <RotationHandle
              map={mapInstance}
              polygon={selectedPolygon}
              onCommit={handleRotationCommit}
              onDismiss={handleRotationDismiss}
            />
          </>
        )}
      </MapContainer>
      {selectedSettings && (
        <div className="absolute bottom-8 left-12 z-[500] pointer-events-none rounded bg-slate-900/90 px-3 py-2 text-xs text-white">
          <div>{selectedSettings.name} · {selectedSettings.roadDirection === 'vertical' ? 'Vertical' : 'Horizontal'} road</div>
          <div className="text-amber-300">Dashed amber: rut / crown sampling</div>
          <div className="text-cyan-300">Dashed cyan: corrugation sampling</div>
          <div className="text-slate-300">Direction preview only; run analysis for results.</div>
        </div>
      )}
    </div>
  );
}
