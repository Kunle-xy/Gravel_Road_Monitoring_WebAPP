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
    btn.title = active ? "Stop drawing" : "Draw polygon";
    btn.setAttribute("aria-label", btn.title);
    btn.style.backgroundColor = active ? "#e0e7ff" : "";
    btn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="${active ? "#2563eb" : "#111827"}" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <polygon points="5 3 19 12 5 21 5 3"/>
        <rect x="2" y="2" width="5" height="5" rx="1" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
        <rect x="17" y="9.5" width="5" height="5" rx="1" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
        <rect x="2" y="17" width="5" height="5" rx="1" fill="${active ? "#2563eb" : "#111827"}" stroke="none"/>
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

/* Handle polygon drawing */
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

    const points: L.LatLng[] = [];
    let tempPolyline: L.Polyline | null = null;
    let tempMarkers: L.Marker[] = [];

    const completePolygon = () => {
      if (points.length < 3) {
        alert('Please add at least 3 points to create a polygon');
        return;
      }

      // Create final polygon with color overlay
      const polygon = L.polygon(points, {
        color: '#2563eb',
        fillColor: '#3b82f6',
        fillOpacity: 0.3,
        weight: 2,
      });

      // Clean up temp layers
      if (tempPolyline) leafletMap.removeLayer(tempPolyline);
      tempMarkers.forEach(m => leafletMap.removeLayer(m));

      // Reset points array
      points.length = 0;
      tempPolyline = null;
      tempMarkers = [];

      onPolygonComplete(polygon);
    };

    const handleClick = (e: L.LeafletMouseEvent) => {
      // Check if clicking near the first point to close polygon
      if (points.length >= 3) {
        const firstPoint = points[0];
        const distance = leafletMap.distance(e.latlng, firstPoint);
        const pixelDistance = distance / (40075016.686 / (256 * Math.pow(2, leafletMap.getZoom())));

        // If within 15 pixels of first point, close the polygon
        if (pixelDistance < 15) {
          completePolygon();
          return;
        }
      }

      points.push(e.latlng);

      // Add marker at click point
      const marker = L.marker(e.latlng, {
        icon: L.divIcon({
          className: 'polygon-vertex',
          html: '<div style="width: 10px; height: 10px; background: #2563eb; border: 2px solid white; border-radius: 50%;"></div>',
          iconSize: [10, 10],
        }),
      }).addTo(leafletMap);
      tempMarkers.push(marker);

      // Update polyline
      if (tempPolyline) {
        leafletMap.removeLayer(tempPolyline);
      }
      tempPolyline = L.polyline(points, {
        color: '#2563eb',
        weight: 2,
        dashArray: '5, 5',
      }).addTo(leafletMap);
    };

    const handleDblClick = () => {
      completePolygon();
    };

    leafletMap.on('click', handleClick);
    leafletMap.on('dblclick', handleDblClick);
    leafletMap.getContainer().style.cursor = 'crosshair';

    return () => {
      leafletMap.off('click', handleClick);
      leafletMap.off('dblclick', handleDblClick);
      leafletMap.getContainer().style.cursor = '';
      if (tempPolyline) leafletMap.removeLayer(tempPolyline);
      tempMarkers.forEach(m => leafletMap.removeLayer(m));
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

export default function Map() {
  const [mode, setMode] = React.useState<Mode>("pan");
  const [showSatellite, setShowSatellite] = React.useState(false);
  const [polygons, setPolygons] = React.useState<L.Polygon[]>([]);
  const [mapInstance, setMapInstance] = React.useState<L.Map | null>(null);
  const { addPolygon, clearPolygons: clearPolygonsContext, polygons: savedPolygons } = usePolygons();
  const center: [number, number] = [41.878, -93.097];

  const handlePolygonComplete = React.useCallback((polygon: L.Polygon) => {
    if (mapInstance) {
      polygon.addTo(mapInstance);
      setPolygons(prev => [...prev, polygon]);
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

      addPolygon({
        name: polygonName,
        geoJSON,
        bounds: polygonBounds,
      });

      // Add label to polygon center
      const center = polygon.getBounds().getCenter();
      const label = L.marker(center, {
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
          ">${polygonName}</div>`,
          iconSize: [60, 20],
        }),
      }).addTo(mapInstance);

      // Store label with polygon for later removal
      (polygon as L.Polygon & { label?: L.Marker }).label = label;
    }
  }, [mapInstance, addPolygon, savedPolygons.length]);

  const handleClearPolygons = React.useCallback(() => {
    if (mapInstance) {
      polygons.forEach(polygon => {
        // Remove the polygon itself
        mapInstance.removeLayer(polygon);

        // Remove the label if it exists
        const label = (polygon as L.Polygon & { label?: L.Marker }).label;
        if (label) {
          mapInstance.removeLayer(label);
        }
      });
      setPolygons([]);
      clearPolygonsContext();
    }
  }, [mapInstance, polygons, clearPolygonsContext]);

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
      </MapContainer>
    </div>
  );
}
