// app/components/DistressForms/crown.tsx
"use client";
import React, { useState, useEffect } from "react";
import { CheckSquare, Square, AlertCircle, Loader2, ExternalLink } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS } from "@/app/lib/api";
import { usePolygons } from "@/app/contexts/PolygonContext";
import html2canvas from "html2canvas";

function RowGrid({ label, control }: { label: React.ReactNode; control: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 py-1">
      <label className="font-semibold text-[12px] text-slate-300">{label}</label>
      <div className="flex items-center">{control}</div>
    </div>
  );
}

function CheckboxToggle({ checked, onChange, label, ariaLabel }: {
  checked: boolean; onChange: (checked: boolean) => void; label?: string; ariaLabel: string;
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
      {toasts.map((toast) => (
        <div key={toast.id} className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-white text-[13px] font-medium border ${
          toast.type === "error" ? "bg-red-600 border-red-500"
            : toast.type === "success" ? "bg-green-600 border-green-500"
            : "bg-blue-600 border-blue-500"
        }`}>
          <AlertCircle size={16} /><span>{toast.message}</span>
        </div>
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
  low_severity_ft: number; medium_severity_ft: number; high_severity_ft: number;
  total_linear_ft: number; low_count: number; medium_count: number; high_count: number;
  html_report_url?: string; error_message?: string;
}

export default function CrownForm() {
  const [demFiles, setDemFiles] = useState<DemFile[]>([]);
  const [selectedDemId, setSelectedDemId] = useState<string>("");
  const [loadingFiles, setLoadingFiles] = useState(true);
  const { polygons } = usePolygons();
  const [selectedPolygonId, setSelectedPolygonId] = useState<string>("");

  // Parameters
  const [spacing, setSpacing] = useState(0.2);
  const [sampling, setSampling] = useState(10);
  const [gaussian, setGaussian] = useState(false);
  const [sigma, setSigma] = useState(1.0);
  const [neighborEval, setNeighborEval] = useState(false);
  const [neighborRange, setNeighborRange] = useState(2);

  // State
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResults | null>(null);

  const inputBox = "w-28 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-center text-[12px] text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400";

  const showToast = (message: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  // Fetch DEM files
  useEffect(() => {
    const fetchDemFiles = async () => {
      try {
        const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST_WITH_FILES);
        if (response.ok) {
          const folders = await response.json();
          const allDems: DemFile[] = [];
          folders.forEach((folder: any) => {
            const folderDems = folder.files
              .filter((f: any) => f.file_type === "DEM")
              .map((f: any) => ({ ...f, folder_name: folder.name }));
            allDems.push(...folderDems);
          });
          setDemFiles(allDems);
          if (allDems.length > 0) setSelectedDemId(allDems[0].id);
        }
      } catch { showToast("Failed to load DEM files", "error"); }
      finally { setLoadingFiles(false); }
    };
    fetchDemFiles();
  }, []);

  // Poll for job status
  useEffect(() => {
    if (!jobId || !isAnalyzing) return;
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetchWithAuth(`${API_ENDPOINTS.CROWN.BASE}/${jobId}/status`);
        if (response.ok) {
          const data: AnalysisResults = await response.json();
          setResults(data);
          if (data.status === "completed") {
            setIsAnalyzing(false);
            showToast(`Analysis complete! Total: ${data.total_linear_ft.toFixed(1)} linear feet.`, "success");
            clearInterval(pollInterval);
          } else if (data.status === "failed") {
            setIsAnalyzing(false);
            showToast(data.error_message || "Analysis failed", "error");
            clearInterval(pollInterval);
          }
        }
      } catch (error) { console.error("Polling error:", error); }
    }, 2000);
    return () => clearInterval(pollInterval);
  }, [jobId, isAnalyzing]);

  const validateForm = (): boolean => {
    if (!selectedDemId) { showToast("Please select a DEM file"); return false; }
    if (!selectedPolygonId) { showToast("Please select a polygon"); return false; }
    const polygon = polygons.find(p => p.id === selectedPolygonId);
    if (!polygon) { showToast("Selected polygon not found"); return false; }

    const selectedDem = demFiles.find(f => f.id === selectedDemId);
    if (selectedDem?.bounds_south && selectedDem?.bounds_west && selectedDem?.bounds_north && selectedDem?.bounds_east) {
      const demBounds = {
        south: parseFloat(selectedDem.bounds_south), west: parseFloat(selectedDem.bounds_west),
        north: parseFloat(selectedDem.bounds_north), east: parseFloat(selectedDem.bounds_east),
      };
      const coords = polygon.geoJSON.coordinates[0];
      const lngs = coords.map((c: number[]) => c[0]);
      const lats = coords.map((c: number[]) => c[1]);
      const polyBounds = { west: Math.min(...lngs), east: Math.max(...lngs), south: Math.min(...lats), north: Math.max(...lats) };

      if (polyBounds.east < demBounds.west || polyBounds.west > demBounds.east ||
          polyBounds.north < demBounds.south || polyBounds.south > demBounds.north) {
        showToast("Selected polygon is outside the DEM bounds.");
        return false;
      }
    }
    if (spacing <= 0) { showToast("Line spacing must be greater than 0"); return false; }
    if (sampling <= 0) { showToast("Sampling frequency must be greater than 0"); return false; }
    return true;
  };

  const handleRunAnalysis = async () => {
    if (!validateForm()) return;
    setIsAnalyzing(true); setResults(null); setJobId(null);

    try {
      let screenshotBase64 = null;
      try {
        const canvas = await html2canvas(document.body, { allowTaint: true, useCORS: true, scale: 1 });
        screenshotBase64 = canvas.toDataURL("image/png").split(",")[1];
      } catch { /* continue without screenshot */ }

      const selectedPolygon = polygons.find(p => p.id === selectedPolygonId);
      if (!selectedPolygon) throw new Error("Selected polygon not found");

      const response = await fetchWithAuth(API_ENDPOINTS.CROWN.BASE, {
        method: "POST",
        body: JSON.stringify({
          tiff_file_id: selectedDemId,
          polygon_geojson: selectedPolygon.geoJSON,
          spacing_m: spacing,
          dy_freq: sampling,
          apply_smoothing: gaussian,
          gaussian_sigma: sigma,
          neighbor_eval: neighborEval,
          neighbor_range: neighborRange,
          screenshot_base64: screenshotBase64,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to start analysis");
      }

      const job = await response.json();
      setJobId(job.id);
      setResults({
        id: job.id, status: job.status, progress: job.progress,
        low_severity_ft: 0, medium_severity_ft: 0, high_severity_ft: 0,
        total_linear_ft: 0, low_count: 0, medium_count: 0, high_count: 0,
      });
      showToast("Analysis started...", "info");
    } catch (error) {
      setIsAnalyzing(false);
      showToast(error instanceof Error ? error.message : "Failed to start analysis", "error");
    }
  };

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Crown Automatic Detection
        </h2>

        {/* DEM File Selection */}
        <RowGrid label="Select DEM file" control={
          loadingFiles ? (
            <div className="flex items-center gap-1 text-[12px] text-slate-400">
              <Loader2 size={14} className="animate-spin" /><span>Loading...</span>
            </div>
          ) : demFiles.length === 0 ? (
            <span className="text-[12px] text-red-400">No DEM files found</span>
          ) : (
            <select value={selectedDemId} onChange={(e) => setSelectedDemId(e.target.value)}
              className="text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 max-w-60 text-slate-100 focus:outline-none focus:border-blue-400"
              aria-label="Select DEM file">
              {demFiles.map((file) => (
                <option key={file.id} value={file.id} className="bg-slate-800">
                  {file.folder_name ? `${file.folder_name} / ${file.filename}` : file.filename}
                </option>
              ))}
            </select>
          )
        } />

        {/* Polygon Selection */}
        <RowGrid label="Select Polygon" control={
          polygons.length === 0 ? (
            <span className="text-[12px] text-orange-400">No polygons drawn. Draw a polygon on the map first.</span>
          ) : (
            <select value={selectedPolygonId} onChange={(e) => setSelectedPolygonId(e.target.value)}
              className="text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 max-w-60 text-slate-100 focus:outline-none focus:border-blue-400"
              aria-label="Select polygon">
              <option value="" className="bg-slate-800">-- Select a polygon --</option>
              {polygons.map((polygon) => (
                <option key={polygon.id} value={polygon.id} className="bg-slate-800">
                  {polygon.name} ({new Date(polygon.createdAt).toLocaleTimeString()})
                </option>
              ))}
            </select>
          )
        } />

        {/* Parameters */}
        <div className="border-t border-slate-700 pt-2 mt-2">
          <RowGrid label="Line spacing (meters)" control={
            <input type="number" min="0.01" step="0.01" value={spacing}
              onChange={(e) => setSpacing(Number(e.target.value))} className={inputBox}
              aria-label="Line spacing in meters" />
          } />

          <RowGrid label="Sampling frequency per 100 pixels" control={
            <input type="number" min="1" step="1" value={sampling}
              onChange={(e) => setSampling(Number(e.target.value))} className={inputBox}
              aria-label="Sampling frequency" />
          } />

          <RowGrid label="Apply Gaussian smoothing" control={
            <CheckboxToggle checked={gaussian} onChange={setGaussian} label="Toggle"
              ariaLabel="Apply Gaussian smoothing" />
          } />

          {gaussian && (
            <RowGrid label="Gaussian sigma (pixels)" control={
              <input type="number" min="0.1" step="0.1" value={sigma}
                onChange={(e) => setSigma(Number(e.target.value))} className={inputBox}
                aria-label="Gaussian sigma" />
            } />
          )}

          <RowGrid label="Neighbor frequency sweep" control={
            <CheckboxToggle checked={neighborEval} onChange={setNeighborEval} label="Toggle"
              ariaLabel="Neighbor frequency sweep" />
          } />

          {neighborEval && (
            <RowGrid label="Neighbor range (±)" control={
              <input type="number" min="1" step="1" value={neighborRange}
                onChange={(e) => setNeighborRange(Number(e.target.value))} className={inputBox}
                aria-label="Neighbor range" />
            } />
          )}
        </div>

        {/* Progress */}
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

        {/* Results */}
        {!isAnalyzing && results && results.status === "completed" && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-3">
              <div className="text-[13px] font-semibold mb-2 text-green-300">Analysis Complete</div>
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                <div className="text-slate-300">Total linear feet:</div>
                <div className="font-semibold text-slate-100">{results.total_linear_ft.toFixed(1)} ft</div>

                <div className="text-green-400">Low severity:</div>
                <div className="font-semibold text-green-400">{results.low_severity_ft.toFixed(1)} ft ({results.low_count} lines)</div>

                <div className="text-orange-400">Medium severity:</div>
                <div className="font-semibold text-orange-400">{results.medium_severity_ft.toFixed(1)} ft ({results.medium_count} lines)</div>

                <div className="text-red-400">High severity:</div>
                <div className="font-semibold text-red-400">{results.high_severity_ft.toFixed(1)} ft ({results.high_count} lines)</div>
              </div>

              {results.html_report_url && (
                <div className="mt-3">
                  <a href={results.html_report_url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-[12px] font-medium hover:bg-blue-700 transition-colors shadow-lg">
                    <ExternalLink size={14} /> View Interactive Report
                  </a>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {!isAnalyzing && results && results.status === "failed" && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-[13px] font-semibold mb-2 text-red-300">
                <AlertCircle size={16} /> Analysis Failed
              </div>
              <div className="text-[12px] text-red-400">{results.error_message || "Unknown error"}</div>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-3 mt-3 border-t border-slate-700">
          <button onClick={handleRunAnalysis}
            disabled={isAnalyzing || loadingFiles || demFiles.length === 0 || polygons.length === 0 || !selectedPolygonId}
            className={`font-bold py-2.5 px-4 rounded-lg text-[13px] mx-auto block transition-all shadow-lg ${
              isAnalyzing || loadingFiles || demFiles.length === 0 || polygons.length === 0 || !selectedPolygonId
                ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                : "bg-red-700 text-white hover:bg-red-800 hover:shadow-xl"
            }`}>
            {isAnalyzing ? (
              <span className="flex items-center gap-2"><Loader2 size={16} className="animate-spin" />Analyzing...</span>
            ) : "Run Analysis"}
          </button>
        </div>
      </div>
    </>
  );
}
