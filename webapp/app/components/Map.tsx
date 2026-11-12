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
  showLabelsRef.current = showLabels;

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
  modeRef.current = mode;

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
  onClearRef.current = onClear;

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
  modeRef.current = mode;

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

/** Marker offset (pixels) above the polygon center for the rotate handle. */
const ROTATE_HANDLE_OFFSET_PX = 38;

function rotateLatLngsAroundCenterPx(
  map: L.Map,
  centerPt: L.Point,
  corners: L.LatLng[],
  deltaRad: number,
): L.LatLng[] {
  const cos = Math.cos(deltaRad);
  const sin = Math.sin(deltaRad);
  return corners.map((ll) => {
    const p = map.latLngToLayerPoint(ll);
    const dx = p.x - centerPt.x;
    const dy = p.y - centerPt.y;
    const rx = dx * cos - dy * sin;
    const ry = dx * sin + dy * cos;
    return map.layerPointToLatLng(L.point(centerPt.x + rx, centerPt.y + ry));
  });
}

function RotationHandle({
  map,
  polygon,
  onCommit,
  onDismiss,
}: {
  map: L.Map;
  polygon: DrawnLayer;
  onCommit: (corners: L.LatLng[]) => void;
  onDismiss: () => void;
}) {
  React.useEffect(() => {
    const computeHandleLatLng = () => {
      const centerPt = map.latLngToLayerPoint(polygon.getBounds().getCenter());
      return map.layerPointToLatLng(L.point(centerPt.x, centerPt.y - ROTATE_HANDLE_OFFSET_PX));
    };

    const handle = L.marker(computeHandleLatLng(), {
      icon: L.divIcon({
        className: 'rotate-handle',
        html: `<div class="rotate-handle-inner" style="
          width: 26px; height: 26px; border-radius: 50%;
          background: white; border: 2px solid #2563eb;
          display: flex; align-items: center; justify-content: center;
          box-shadow: 0 2px 6px rgba(0,0,0,0.25);
          cursor: grab;
        "><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
          fill="none" stroke="#2563eb" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"
          style="pointer-events: none;">
          <path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/>
        </svg></div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      }),
      interactive: true,
      bubblingMouseEvents: false,
      keyboard: false,
      zIndexOffset: 1000,
    }).addTo(map);

    const handleEl = handle.getElement() as HTMLElement | null;
    if (!handleEl) {
      return () => { map.removeLayer(handle); };
    }
    handleEl.style.cursor = 'grab';
    handleEl.style.pointerEvents = 'auto';
    L.DomEvent.disableClickPropagation(handleEl);
    L.DomEvent.disableScrollPropagation(handleEl);

    let moveHandler: ((ev: MouseEvent) => void) | null = null;
    let upHandler: (() => void) | null = null;

    const onPointerDown = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      map.dragging.disable();
      map.boxZoom.disable();
      handleEl.style.cursor = 'grabbing';
      document.body.style.cursor = 'grabbing';

      const centerPt = map.latLngToLayerPoint(polygon.getBounds().getCenter());
      const startPt = map.mouseEventToLayerPoint(e);
      const startAngle = Math.atan2(startPt.y - centerPt.y, startPt.x - centerPt.x);
      const snapshot = ((polygon.getLatLngs()[0] as unknown) as L.LatLng[]).map((ll) => L.latLng(ll.lat, ll.lng));
      const labelSnapshot = polygon.label?.getLatLng();

      moveHandler = (ev: MouseEvent) => {
        ev.preventDefault();
        const p = map.mouseEventToLayerPoint(ev);
        const nowAngle = Math.atan2(p.y - centerPt.y, p.x - centerPt.x);
        const delta = nowAngle - startAngle;
        const rotated = rotateLatLngsAroundCenterPx(map, centerPt, snapshot, delta);
        polygon.setLatLngs([rotated]);

        if (labelSnapshot && polygon.label) {
          const [newLabelLatLng] = rotateLatLngsAroundCenterPx(map, centerPt, [labelSnapshot], delta);
          polygon.label.setLatLng(newLabelLatLng);
        }
        handle.setLatLng(computeHandleLatLng());
      };

      upHandler = () => {
        if (moveHandler) document.removeEventListener('mousemove', moveHandler);
        if (upHandler) document.removeEventListener('mouseup', upHandler);
        document.body.style.cursor = '';
        handleEl.style.cursor = 'grab';
        map.dragging.enable();
        map.boxZoom.enable();
        const committed = ((polygon.getLatLngs()[0] as unknown) as L.LatLng[]);
        onCommit(committed);
        moveHandler = null;
        upHandler = null;
      };

      document.addEventListener('mousemove', moveHandler);
      document.addEventListener('mouseup', upHandler);
    };

    handleEl.addEventListener('mousedown', onPointerDown);

    const onZoomOrMove = () => {
      if (!moveHandler) handle.setLatLng(computeHandleLatLng());
    };
    map.on('zoomend moveend', onZoomOrMove);

    // Edge-resize fires this on the polygon — keep the rotate handle
    // anchored to the polygon center as the rectangle stretches.
    const onPolygonReshape = () => {
      if (!moveHandler) handle.setLatLng(computeHandleLatLng());
    };
    polygon.on('reshape', onPolygonReshape);

    const onDocKey = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') onDismiss();
    };
    document.addEventListener('keydown', onDocKey);

    return () => {
      handleEl.removeEventListener('mousedown', onPointerDown);
      if (moveHandler) document.removeEventListener('mousemove', moveHandler);
      if (upHandler) document.removeEventListener('mouseup', upHandler);
      map.removeLayer(handle);
      map.off('zoomend moveend', onZoomOrMove);
      polygon.off('reshape', onPolygonReshape);
      document.removeEventListener('keydown', onDocKey);
      document.body.style.cursor = '';
    };
  }, [map, polygon, onCommit, onDismiss]);

  return null;
}

/**
 * Select-first edge resize. Each of the rectangle's four edges is a wide,
 * transparent polyline "hit zone" that picks up clicks on the edge line.
 * Clicking an edge selects it — we draw a visible blue highlight on top
 * and a draggable grip at its midpoint. Dragging the grip moves both
 * corners of that edge along its outward normal (only that side stretches,
 * rotation is preserved). Clicking another edge switches selection;
 * Escape clears it.
 */
function EdgeResizeHandles({
  map,
  polygon,
  onCommit,
}: {
  map: L.Map;
  polygon: DrawnLayer;
  onCommit: (corners: L.LatLng[]) => void;
}) {
  const [selectedEdge, setSelectedEdge] = React.useState<number | null>(null);

  // Reset selection whenever the polygon changes.
  React.useEffect(() => {
    setSelectedEdge(null);
  }, [polygon]);

  const cornersLL = React.useCallback(
    (): L.LatLng[] => (polygon.getLatLngs()[0] as unknown) as L.LatLng[],
    [polygon],
  );

  // Transparent wide polyline per edge — the click target.
  React.useEffect(() => {
    const hitZones: L.Polyline[] = [];

    const buildZones = () => {
      const corners = cornersLL();
      for (let i = 0; i < 4; i++) {
        const a = corners[i];
        const b = corners[(i + 1) % 4];
        const zone = L.polyline([a, b], {
          color: '#2563eb',
          opacity: 0,
          weight: 18,
          interactive: true,
          bubblingMouseEvents: false,
        }).addTo(map);
        const el = (zone as unknown as { getElement?: () => SVGElement | null })
          .getElement?.();
        if (el) {
          (el as SVGElement & { style: CSSStyleDeclaration }).style.cursor = 'pointer';
        }
        zone.on('click', (evt: L.LeafletMouseEvent) => {
          L.DomEvent.stopPropagation(evt.originalEvent);
          setSelectedEdge(i);
        });
        hitZones.push(zone);
      }
    };

    const refreshZones = () => {
      const corners = cornersLL();
      hitZones.forEach((z, i) => {
        z.setLatLngs([corners[i], corners[(i + 1) % 4]]);
      });
    };

    buildZones();
    polygon.on('reshape', refreshZones);

    return () => {
      polygon.off('reshape', refreshZones);
      hitZones.forEach((z) => map.removeLayer(z));
    };
  }, [map, polygon, cornersLL]);

  // Highlight + draggable grip for the currently selected edge.
  React.useEffect(() => {
    if (selectedEdge === null) return;

    const edgeIndex = selectedEdge;
    const cornersPx = (): L.Point[] =>
      cornersLL().map((ll) => map.latLngToLayerPoint(ll));

    const midLatLng = (a: L.Point, b: L.Point): L.LatLng =>
      map.layerPointToLatLng(L.point((a.x + b.x) / 2, (a.y + b.y) / 2));

    const cursorForEdge = (a: L.Point, b: L.Point): string => {
      const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
      const d = ((angle % 180) + 180) % 180;
      if (d < 22.5 || d >= 157.5) return 'ns-resize';
      if (d < 67.5) return 'nesw-resize';
      if (d < 112.5) return 'ew-resize';
      return 'nwse-resize';
    };

    const corners = cornersLL();
    const highlight = L.polyline(
      [corners[edgeIndex], corners[(edgeIndex + 1) % 4]],
      { color: '#2563eb', weight: 4, opacity: 0.95, interactive: false },
    ).addTo(map);

    const ptsAtStart = cornersPx();
    const grip = L.marker(
      midLatLng(ptsAtStart[edgeIndex], ptsAtStart[(edgeIndex + 1) % 4]),
      {
        icon: L.divIcon({
          className: 'edge-resize-grip',
          html: `<div style="
            width: 14px; height: 14px;
            background: #2563eb; border: 2px solid white;
            border-radius: 3px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.3);
          "></div>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        }),
        interactive: true,
        bubblingMouseEvents: false,
        keyboard: false,
        zIndexOffset: 1100,
      },
    ).addTo(map);

    const gripEl = grip.getElement() as HTMLElement | null;
    let moveHandler: ((ev: MouseEvent) => void) | null = null;
    let upHandler: (() => void) | null = null;

    const repositionOverlay = () => {
      const llCurrent = cornersLL();
      highlight.setLatLngs([llCurrent[edgeIndex], llCurrent[(edgeIndex + 1) % 4]]);
      const pts = cornersPx();
      grip.setLatLng(midLatLng(pts[edgeIndex], pts[(edgeIndex + 1) % 4]));
      if (gripEl) gripEl.style.cursor = cursorForEdge(pts[edgeIndex], pts[(edgeIndex + 1) % 4]);
    };

    if (gripEl) {
      gripEl.style.pointerEvents = 'auto';
      gripEl.style.cursor = cursorForEdge(
        ptsAtStart[edgeIndex],
        ptsAtStart[(edgeIndex + 1) % 4],
      );
      L.DomEvent.disableClickPropagation(gripEl);
      L.DomEvent.disableScrollPropagation(gripEl);

      const pointerDown = (e: MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        map.dragging.disable();
        map.boxZoom.disable();
        document.body.style.cursor = gripEl.style.cursor;

        const startPt = map.mouseEventToLayerPoint(e);
        const snapshotLL = cornersLL().map((ll) => L.latLng(ll.lat, ll.lng));
        const snapshotPts = snapshotLL.map((ll) => map.latLngToLayerPoint(ll));
        const labelSnapshot = polygon.label?.getLatLng();

        const i0 = edgeIndex;
        const i1 = (edgeIndex + 1) % 4;
        const ex = snapshotPts[i1].x - snapshotPts[i0].x;
        const ey = snapshotPts[i1].y - snapshotPts[i0].y;
        const len = Math.hypot(ex, ey) || 1;
        const nx = -ey / len;
        const ny = ex / len;

        moveHandler = (ev: MouseEvent) => {
          ev.preventDefault();
          const p = map.mouseEventToLayerPoint(ev);
          const proj = (p.x - startPt.x) * nx + (p.y - startPt.y) * ny;
          const tx = proj * nx;
          const ty = proj * ny;

          const newPts = snapshotPts.map((pt, idx) =>
            idx === i0 || idx === i1 ? L.point(pt.x + tx, pt.y + ty) : pt,
          );
          const newCorners = newPts.map((pt) => map.layerPointToLatLng(pt));
          polygon.setLatLngs([newCorners]);

          if (labelSnapshot && polygon.label) {
            const labelPt = map.latLngToLayerPoint(labelSnapshot);
            polygon.label.setLatLng(
              map.layerPointToLatLng(L.point(labelPt.x + tx / 2, labelPt.y + ty / 2)),
            );
          }

          highlight.setLatLngs([newCorners[i0], newCorners[i1]]);
          grip.setLatLng(midLatLng(newPts[i0], newPts[i1]));
          polygon.fire('reshape');
        };

        upHandler = () => {
          if (moveHandler) document.removeEventListener('mousemove', moveHandler);
          if (upHandler) document.removeEventListener('mouseup', upHandler);
          document.body.style.cursor = '';
          map.dragging.enable();
          map.boxZoom.enable();
          onCommit(cornersLL());
          moveHandler = null;
          upHandler = null;
        };

        document.addEventListener('mousemove', moveHandler);
        document.addEventListener('mouseup', upHandler);
      };

      gripEl.addEventListener('mousedown', pointerDown);

      const onZoomOrMove = () => {
        if (!moveHandler) repositionOverlay();
      };
      map.on('zoomend moveend', onZoomOrMove);

      const onReshape = () => {
        if (!moveHandler) repositionOverlay();
      };
      polygon.on('reshape', onReshape);

      const onKey = (ev: KeyboardEvent) => {
        if (ev.key === 'Escape') setSelectedEdge(null);
      };
      document.addEventListener('keydown', onKey);

      return () => {
        gripEl.removeEventListener('mousedown', pointerDown);
        if (moveHandler) document.removeEventListener('mousemove', moveHandler);
        if (upHandler) document.removeEventListener('mouseup', upHandler);
        map.off('zoomend moveend', onZoomOrMove);
        polygon.off('reshape', onReshape);
        document.removeEventListener('keydown', onKey);
        map.removeLayer(highlight);
        map.removeLayer(grip);
        document.body.style.cursor = '';
      };
    }

    return () => {
      map.removeLayer(highlight);
      map.removeLayer(grip);
    };
  }, [map, polygon, onCommit, selectedEdge, cornersLL]);

  return null;
}

export default function Map() {
  const [mode, setMode] = React.useState<Mode>("pan");
  const [showSatellite, setShowSatellite] = React.useState(false);
  const [polygons, setPolygons] = React.useState<DrawnLayer[]>([]);
  const [selectedPolygon, setSelectedPolygon] = React.useState<DrawnLayer | null>(null);
  const [mapInstance, setMapInstance] = React.useState<L.Map | null>(null);
  const { addPolygon, updatePolygon, clearPolygons: clearPolygonsContext, polygons: savedPolygons } = usePolygons();
  const center: [number, number] = [41.878, -93.097];

  // Click on the map outside any polygon → deselect
  React.useEffect(() => {
    if (!mapInstance) return;
    const handler = () => setSelectedPolygon(null);
    mapInstance.on('click', handler);
    return () => {
      mapInstance.off('click', handler);
    };
  }, [mapInstance]);

  const handleRotationDismiss = React.useCallback(() => setSelectedPolygon(null), []);

  const handleRotationCommit = React.useCallback((corners: L.LatLng[]) => {
    if (!selectedPolygon?.polygonId) return;
    const coordinates = corners.map((ll) => [ll.lng, ll.lat]);
    coordinates.push([...coordinates[0]]);
    const previous = savedPolygons.find(p => p.id === selectedPolygon.polygonId);
    const geoJSON = { ...previous?.geoJSON, type: "Polygon" as const, coordinates: [coordinates] };
    const b = selectedPolygon.getBounds();
    const bounds: [[number, number], [number, number]] = [
      [b.getSouth(), b.getWest()],
      [b.getNorth(), b.getEast()],
    ];
    updatePolygon(selectedPolygon.polygonId, { geoJSON, bounds });
  }, [selectedPolygon, updatePolygon, savedPolygons]);

  const handlePolygonComplete = React.useCallback((polygon: L.Polygon) => {
    if (mapInstance) {
      polygon.addTo(mapInstance);
      const tagged = polygon as DrawnLayer;
      setPolygons(prev => [...prev, tagged]);
      setMode("pan");

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
        setSelectedPolygon(tagged);
      });
    }
  }, [mapInstance, addPolygon, savedPolygons.length]);

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
      setSelectedPolygon(null);
      clearPolygonsContext();
    }
  }, [mapInstance, polygons, clearPolygonsContext]);

  // Don't keep a selection active while the user is drawing a new rectangle
  React.useEffect(() => {
    if (mode === "draw") setSelectedPolygon(null);
  }, [mode]);

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
        {mapInstance && selectedPolygon && (
          <>
            <EdgeResizeHandles
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
    </div>
  );
}
