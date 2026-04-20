// app/components/DistressForms/corrugation.tsx
"use client";
import React, { useState, useEffect, useRef } from "react";
import { CheckSquare, Square, AlertCircle, Loader2, ExternalLink, Eye, EyeOff } from "lucide-react";
import type { GeoJSON as LeafletGeoJSON } from "leaflet";
import { fetchWithAuth, API_ENDPOINTS } from "@/app/lib/api";
import { usePolygons } from "@/app/contexts/PolygonContext";
import { useMap } from "@/app/contexts/MapContext";
import html2canvas from "html2canvas-pro";

const SEVERITY_COLORS: Record<string, string> = {
  LOW: "#16a34a",
  MEDIUM: "#eab308",
  HIGH: "#dc2626",
};

function RowGrid({ label, control }: { label: React.ReactNode; control: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 py-1">
      <label className="font-semibold text-[12px] text-slate-300">{label}</label>
      <div className="flex items-center">{control}</div>
    </div>
  );
}

function CheckboxToggle({ checked, onChange, label, ariaLabel }: {
  checked: boolean; onChange: (c: boolean) => void; label?: string; ariaLabel: string;
}) {
  return (
    <button type="button" onClick={() => onChange(!checked)}
      className="flex items-center gap-2 hover:bg-slate-700/50 px-2 py-1 rounded transition-colors"
      aria-label={ariaLabel} aria-checked={checked} role="checkbox">
      {checked ? <CheckSquare size={16} className="text-blue-400" /> : <Square size={16} className="text-slate-500" />}
      {label && <span className="text-[12px] text-slate-300">{label}</span>}
    </button>
  );
}

interface Toast { id: number; message: string; type: "error" | "success" | "info"; }

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-white text-[13px] font-medium border ${
          t.type === "error" ? "bg-red-600 border-red-500"
            : t.type === "success" ? "bg-green-600 border-green-500"
            : "bg-blue-600 border-blue-500"
        }`}><AlertCircle size={16} /><span>{t.message}</span></div>
      ))}
    </div>
  );
}

interface DemFile {
  id: string; filename: string; file_type: string; folder_name?: string;
  bounds_south?: string; bounds_west?: string; bounds_north?: string; bounds_east?: string;
}

interface AnalysisResults {
  id: string; status: string; progress: number;
  low_area_ft2: number; medium_area_ft2: number; high_area_ft2: number;
  total_area_ft2: number; low_count: number; medium_count: number; high_count: number;
  html_report_url?: string; features_geojson_url?: string; error_message?: string;
}

export default function CorrugationForm() {
  const [demFiles, setDemFiles] = useState<DemFile[]>([]);
  const [selectedDemId, setSelectedDemId] = useState("");
  const [loadingFiles, setLoadingFiles] = useState(true);
  const { polygons } = usePolygons();
  const [selectedPolygonId, setSelectedPolygonId] = useState("");

  const [sampling, setSampling] = useState(20);
  const [lineInterval, setLineInterval] = useState(0.05);
  const [sigma, setSigma] = useState(3.0);
  // Corrugation filters — cut sub-noise drops and unphysical crest-to-crest spans
  const [minDropIn, setMinDropIn] = useState(0.25);
  const [minWavelengthM, setMinWavelengthM] = useState(0.15);
  const [maxWavelengthM, setMaxWavelengthM] = useState(0.6);
  // Wavelength stays auto-derived from DEM resolution + sampling until the
  // user manually edits either field; reset button rearms auto-prefill.
  const [wavelengthDirty, setWavelengthDirty] = useState(false);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResults | null>(null);

  // Map overlay of detected corrugation segments
  const { map } = useMap();
  const overlayLayerRef = useRef<LeafletGeoJSON | null>(null);
  const [overlayOn, setOverlayOn] = useState(false);
  const [overlayLoading, setOverlayLoading] = useState(false);

  const inputBox = "w-28 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-center text-[12px] text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400";

  const clearCorrugationOverlay = React.useCallback(() => {
    if (overlayLayerRef.current && map) {
      map.removeLayer(overlayLayerRef.current);
    }
    overlayLayerRef.current = null;
  }, [map]);

  const handleToggleOverlay = async () => {
    if (overlayOn) {
      clearCorrugationOverlay();
      setOverlayOn(false);
      return;
    }
    if (!map) {
      showToast("Map not ready yet", "error");
      return;
    }
    if (!results?.features_geojson_url) {
      showToast("No corrugation features available for this job", "error");
      return;
    }
    setOverlayLoading(true);
    try {
      const res = await fetch(results.features_geojson_url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const gj = await res.json();
      const L = (await import("leaflet")).default;
      const layer = L.geoJSON(gj, {
        style: (feature) => {
          const sev = feature?.properties?.severity as string | undefined;
          const fill = (sev && SEVERITY_COLORS[sev]) || "#888";
          return {
            weight: 0,
            stroke: false,
            fillColor: fill,
            fillOpacity: 0.65,
          };
        },
        onEachFeature: (feature, lyr) => {
          const p = feature.properties ?? {};
          const sev = String(p.severity ?? "").toUpperCase();
          const color = SEVERITY_COLORS[sev] || "#333";
          const label = sev.charAt(0) + sev.slice(1).toLowerCase();
          lyr.bindPopup(
            `<div style="font-family:Arial,sans-serif;font-size:12px;line-height:1.4;">
              <strong style="color:${color}">${label}</strong><br/>
              Depth: ${typeof p.depth_in === "number" ? p.depth_in.toFixed(2) : "?"} in<br/>
              Area: ${typeof p.area_sqft === "number" ? p.area_sqft.toFixed(2) : "?"} ft²<br/>
              Transect y: ${typeof p.transect_y === "number" ? p.transect_y.toFixed(2) : "?"} m<br/>
              Frequency: ${p.frequency ?? "?"}
            </div>`
          );
        },
      }).addTo(map);
      overlayLayerRef.current = layer;
      try {
        const b = layer.getBounds();
        if (b.isValid()) map.fitBounds(b, { padding: [40, 40] });
      } catch {
        /* no bounds, skip fit */
      }
      setOverlayOn(true);
    } catch (e) {
      console.error("Failed to load corrugation overlay", e);
      showToast("Failed to load corrugation overlay", "error");
    } finally {
      setOverlayLoading(false);
    }
  };

  useEffect(() => () => clearCorrugationOverlay(), [clearCorrugationOverlay]);

  useEffect(() => {
    clearCorrugationOverlay();
    setOverlayOn(false);
  }, [jobId, clearCorrugationOverlay]);

  // Prefill wavelength bounds from DEM resolution + sampling frequency. Skip
  // once the user has touched either input — their edits take precedence.
  useEffect(() => {
    if (!selectedDemId || wavelengthDirty) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchWithAuth(API_ENDPOINTS.CORRUGATION.AUTO_DEFAULTS(selectedDemId, sampling));
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        if (typeof data.min_wavelength_m === "number") setMinWavelengthM(data.min_wavelength_m);
        if (typeof data.max_wavelength_m === "number") setMaxWavelengthM(data.max_wavelength_m);
      } catch {
        /* silent — fall back to whatever's in the form */
      }
    })();
    return () => { cancelled = true; };
  }, [selectedDemId, sampling, wavelengthDirty]);

  const showToast = (message: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((p) => [...p, { id, message, type }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), 4000);
  };

  useEffect(() => {
    const fetchDemFiles = async () => {
      try {
        const res = await fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST_WITH_FILES);
        if (res.ok) {
          const folders = await res.json();
          const allDems: DemFile[] = [];
          folders.forEach((f: any) => {
            f.files.filter((file: any) => file.file_type === "DEM")
              .forEach((file: any) => allDems.push({ ...file, folder_name: f.name }));
          });
          setDemFiles(allDems);
          if (allDems.length > 0) setSelectedDemId(allDems[0].id);
        }
      } catch { showToast("Failed to load DEM files"); }
      finally { setLoadingFiles(false); }
    };
    fetchDemFiles();
  }, []);

  useEffect(() => {
    if (!jobId || !isAnalyzing) return;
    const poll = setInterval(async () => {
      try {
        const res = await fetchWithAuth(`${API_ENDPOINTS.CORRUGATION.BASE}/${jobId}/status`);
        if (res.ok) {
          const data: AnalysisResults = await res.json();
          setResults(data);
          if (data.status === "completed") {
            setIsAnalyzing(false);
            showToast(`Complete! Total area: ${data.total_area_ft2.toFixed(1)} ft2`, "success");
            clearInterval(poll);
          } else if (data.status === "failed") {
            setIsAnalyzing(false);
            showToast(data.error_message || "Analysis failed", "error");
            clearInterval(poll);
          }
        }
      } catch (e) { console.error("Poll error:", e); }
    }, 2000);
    return () => clearInterval(poll);
  }, [jobId, isAnalyzing]);

  const handleRun = async () => {
    if (!selectedDemId) { showToast("Select a DEM file"); return; }
    if (!selectedPolygonId) { showToast("Select a polygon"); return; }
    const polygon = polygons.find(p => p.id === selectedPolygonId);
    if (!polygon) { showToast("Polygon not found"); return; }
    if (sampling <= 0) { showToast("Sampling frequency must be > 0"); return; }
    if (lineInterval <= 0) { showToast("Line interval must be > 0"); return; }
    if (minDropIn < 0) { showToast("Min drop must be >= 0"); return; }
    if (minWavelengthM <= 0) { showToast("Min wavelength must be > 0"); return; }
    if (maxWavelengthM <= minWavelengthM) { showToast("Max wavelength must exceed min"); return; }

    setIsAnalyzing(true); setResults(null); setJobId(null);

    try {
      let screenshot: string | null = null;
      try {
        const canvas = await html2canvas(document.body, { allowTaint: true, useCORS: true, scale: 1 });
        screenshot = canvas.toDataURL("image/png").split(",")[1];
      } catch { /* ok */ }

      const res = await fetchWithAuth(API_ENDPOINTS.CORRUGATION.BASE, {
        method: "POST",
        body: JSON.stringify({
          tiff_file_id: selectedDemId,
          polygon_geojson: polygon.geoJSON,
          dy_freq: sampling,
          line_interval: lineInterval,
          sigma_samples: sigma,
          min_drop_in: minDropIn,
          min_wavelength_m: minWavelengthM,
          max_wavelength_m: maxWavelengthM,
          screenshot_base64: screenshot,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start");
      }

      const job = await res.json();
      setJobId(job.id);
      setResults({
        id: job.id, status: job.status, progress: job.progress,
        low_area_ft2: 0, medium_area_ft2: 0, high_area_ft2: 0,
        total_area_ft2: 0, low_count: 0, medium_count: 0, high_count: 0,
      });
      showToast("Analysis started...", "info");
    } catch (e) {
      setIsAnalyzing(false);
      showToast(e instanceof Error ? e.message : "Failed", "error");
    }
  };

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Corrugation Automatic Detection
        </h2>

        <RowGrid label="Select DEM file" control={
          loadingFiles ? <div className="flex items-center gap-1 text-[12px] text-slate-400"><Loader2 size={14} className="animate-spin" /><span>Loading...</span></div>
          : demFiles.length === 0 ? <span className="text-[12px] text-red-400">No DEM files</span>
          : <select value={selectedDemId} onChange={(e) => setSelectedDemId(e.target.value)}
              className="text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 max-w-60 text-slate-100 focus:outline-none focus:border-blue-400">
              {demFiles.map((f) => <option key={f.id} value={f.id} className="bg-slate-800">
                {f.folder_name ? `${f.folder_name} / ${f.filename}` : f.filename}</option>)}
            </select>
        } />

        <RowGrid label="Select Polygon" control={
          polygons.length === 0
            ? <span className="text-[12px] text-orange-400">Draw a polygon first</span>
            : <select value={selectedPolygonId} onChange={(e) => setSelectedPolygonId(e.target.value)}
                className="text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 max-w-60 text-slate-100 focus:outline-none focus:border-blue-400">
                <option value="">-- Select --</option>
                {polygons.map((p) => <option key={p.id} value={p.id} className="bg-slate-800">
                  {p.name} ({new Date(p.createdAt).toLocaleTimeString()})</option>)}
              </select>
        } />

        <div className="border-t border-slate-700 pt-2 mt-2">
          <RowGrid label="Sampling frequency per 100 pixels" control={
            <input type="number" min="1" step="1" value={sampling} onChange={(e) => setSampling(Number(e.target.value))} className={inputBox} />
          } />
          <RowGrid label="Line interval (meters)" control={
            <input type="number" min="0.01" step="0.01" value={lineInterval} onChange={(e) => setLineInterval(Number(e.target.value))} className={inputBox} />
          } />
          <RowGrid label="Smooth sigma (samples)" control={
            <input type="number" min="0" step="0.5" value={sigma} onChange={(e) => setSigma(Number(e.target.value))} className={inputBox} />
          } />
          <RowGrid label="Min drop (inches)" control={
            <input type="number" min="0" step="0.05" value={minDropIn} onChange={(e) => setMinDropIn(Number(e.target.value))} className={inputBox} />
          } />
          <RowGrid label="Min wavelength (m)" control={
            <div className="flex items-center gap-1.5">
              <input type="number" min="0" step="0.05" value={minWavelengthM}
                onChange={(e) => { setMinWavelengthM(Number(e.target.value)); setWavelengthDirty(true); }}
                className={inputBox} />
              {wavelengthDirty && (
                <button type="button" onClick={() => setWavelengthDirty(false)}
                  className="text-[10px] text-blue-300 hover:text-blue-200" title="Re-compute from DEM resolution">
                  auto
                </button>
              )}
            </div>
          } />
          <RowGrid label="Max wavelength (m)" control={
            <input type="number" min="0" step="0.1" value={maxWavelengthM}
              onChange={(e) => { setMaxWavelengthM(Number(e.target.value)); setWavelengthDirty(true); }}
              className={inputBox} />
          } />
        </div>

        {isAnalyzing && results && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <Loader2 size={16} className="animate-spin text-blue-400" />
                <span className="text-[13px] font-semibold text-blue-300">
                  {results.status === "processing" ? "Processing..." : "Starting..."}
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2.5 overflow-hidden">
                <div className="bg-blue-500 h-2.5 transition-all duration-300" style={{ width: `${results.progress}%` }} />
              </div>
              <div className="text-[11px] text-slate-400 mt-1 text-right">{results.progress}%</div>
            </div>
          </div>
        )}

        {!isAnalyzing && results?.status === "completed" && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-3">
              <div className="text-[13px] font-semibold mb-2 text-green-300">Analysis Complete</div>
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                <div className="text-slate-300">Total area:</div>
                <div className="font-semibold text-slate-100">{results.total_area_ft2.toFixed(1)} ft2</div>
                <div className="text-green-400">Low:</div>
                <div className="font-semibold text-green-400">{results.low_area_ft2.toFixed(1)} ft2 ({results.low_count} seg)</div>
                <div className="text-orange-400">Medium:</div>
                <div className="font-semibold text-orange-400">{results.medium_area_ft2.toFixed(1)} ft2 ({results.medium_count} seg)</div>
                <div className="text-red-400">High:</div>
                <div className="font-semibold text-red-400">{results.high_area_ft2.toFixed(1)} ft2 ({results.high_count} seg)</div>
              </div>
              <div className="flex gap-2 mt-3 flex-wrap">
                {results.html_report_url && (
                  <a href={results.html_report_url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-center gap-1.5 flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-[12px] font-medium hover:bg-blue-700 transition-colors shadow-lg">
                    <ExternalLink size={14} /> View Interactive Report
                  </a>
                )}
                {results.features_geojson_url && (
                  <button
                    type="button"
                    onClick={handleToggleOverlay}
                    disabled={overlayLoading}
                    className={`flex items-center justify-center gap-1.5 flex-1 px-3 py-2 rounded-lg text-[12px] font-medium transition-colors shadow-lg ${
                      overlayOn
                        ? "bg-emerald-600 text-white hover:bg-emerald-700"
                        : "bg-slate-700 text-slate-100 hover:bg-slate-600"
                    } disabled:opacity-60 disabled:cursor-not-allowed`}
                    aria-pressed={overlayOn}
                    title={overlayOn ? "Hide detected segments on the map" : "Show detected segments on the map"}
                  >
                    {overlayLoading ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : overlayOn ? (
                      <EyeOff size={14} />
                    ) : (
                      <Eye size={14} />
                    )}
                    {overlayOn ? "Hide Corrugation on Map" : "Show Corrugation on Map"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {!isAnalyzing && results?.status === "failed" && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-[13px] font-semibold mb-2 text-red-300">
                <AlertCircle size={16} /> Analysis Failed
              </div>
              <div className="text-[12px] text-red-400">{results.error_message || "Unknown error"}</div>
            </div>
          </div>
        )}

        <div className="pt-3 mt-3 border-t border-slate-700">
          <button onClick={handleRun}
            disabled={isAnalyzing || loadingFiles || !demFiles.length || !polygons.length || !selectedPolygonId}
            className={`font-bold py-2.5 px-4 rounded-lg text-[13px] mx-auto block transition-all shadow-lg ${
              isAnalyzing || loadingFiles || !demFiles.length || !polygons.length || !selectedPolygonId
                ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                : "bg-red-700 text-white hover:bg-red-800 hover:shadow-xl"
            }`}>
            {isAnalyzing ? <span className="flex items-center gap-2"><Loader2 size={16} className="animate-spin" />Analyzing...</span> : "Run Analysis"}
          </button>
        </div>
      </div>
    </>
  );
}
