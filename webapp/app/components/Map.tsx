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

  React.useEffect(() => {
    const LabelsControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.title = showLabels ? "Hide labels" : "Show labels";
        btn.setAttribute("aria-label", btn.title);
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";

        btn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="${
            showLabels ? "#2563eb" : "#111827"
          }" viewBox="0 0 24 24">
            <path d="M4 4h16v2H4V4zm0 5h16v2H4V9zm0 5h16v2H4v-2zm0 5h10v2H4v-2z"/>
          </svg>
        `;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          setShowLabels(!showLabels);
        });

        return container;
      },
    });

    const control = new LabelsControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, showLabels, setShowLabels]);

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

  React.useEffect(() => {
    const DrawControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.title = mode === "draw" ? "Stop drawing" : "Draw polygon";
        btn.setAttribute("aria-label", btn.title);
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";

        btn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="${
            mode === "draw" ? "#2563eb" : "#111827"
          }" viewBox="0 0 24 24">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        `;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          setMode(mode === "draw" ? "pan" : "draw");
        });

        return container;
      },
    });

    const control = new DrawControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, mode, setMode]);

  return null;
}

/* Control to cancel/clear drawn polygons */
function ClearPolygonsControl({
  onClear,
}: {
  onClear: () => void;
}) {
  const leafletMap = useLeafletMap();

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
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="#dc2626" viewBox="0 0 24 24">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        `;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          onClear();
        });

        return container;
      },
    });

    const control = new ClearControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, onClear]);

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

  React.useEffect(() => {
    const PanControl = L.Control.extend({
      options: { position: "topleft" as L.ControlPosition },
      onAdd: () => {
        const container = L.DomUtil.create("div", "leaflet-bar");

        // button element, styled like native controls
        const btn = L.DomUtil.create("a", "", container);
        btn.href = "#";
        btn.title = mode === "pan" ? "Turn off pan" : "Turn on pan";
        btn.setAttribute("aria-label", btn.title);
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.width = "30px";
        btn.style.height = "30px";

        // simple svg icon
        btn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="${
            mode === "pan" ? "#2563eb" : "#111827"
          }" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2a1 1 0 0 1 1 1v6.586l1.293-1.293a1 1 0 1 1 1.414 1.414L13 12l2.707 2.293a1 1 0 1 1-1.414 1.414L13 14.414V21a1 1 0 1 1-2 0v-6.586l-1.293 1.293a1 1 0 1 1-1.414-1.414L11 12 8.293 9.707a1 1 0 1 1 1.414-1.414L11 9.586V3a1 1 0 0 1 1-1z"/>
          </svg>
        `;

        // stop map drag when clicking the control
        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.stop(e);
          setMode(mode === "pan" ? "none" : "pan");
        });

        return container;
      },
    });

    const control = new PanControl();
    leafletMap.addControl(control);

    return () => {
      leafletMap.removeControl(control);
    };
  }, [leafletMap, mode, setMode]);

  return null;
}

export default function Map() {
  const [mode, setMode] = React.useState<Mode>("pan");
  const [showLabels, setShowLabels] = React.useState(true);
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
        {/* Base layer - with or without labels */}
        {showLabels ? (
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={26}
            maxNativeZoom={19}
            minZoom={1}
          />
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://www.esri.com">Esri</a>'
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
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
        <LabelsToggleControl showLabels={showLabels} setShowLabels={setShowLabels} />
        <DrawPolygonControl mode={mode} setMode={setMode} />
        <ClearPolygonsControl onClear={handleClearPolygons} />
        <PolygonDrawing mode={mode} onPolygonComplete={handlePolygonComplete} />
      </MapContainer>
    </div>
  );
}
