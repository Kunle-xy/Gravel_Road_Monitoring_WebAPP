// app/components/DistressForms/pothole.tsx
"use client";
import React, { useState, useEffect } from "react";
import { AlertCircle, Loader2, ExternalLink } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS } from "@/app/lib/api";
import { usePolygons } from "@/app/contexts/PolygonContext";

interface Toast { id: number; message: string; type: "error" | "success" | "info"; }

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-white text-[13px] font-medium border ${
          t.type === "error" ? "bg-red-600 border-red-500" : t.type === "success" ? "bg-green-600 border-green-500" : "bg-blue-600 border-blue-500"
        }`}><AlertCircle size={16} /><span>{t.message}</span></div>
      ))}
    </div>
  );
}

interface DemFile { id: string; filename: string; folder_name?: string; }
interface AnalysisResult {
  id: string; status: string; progress: number; error_message?: string;
  html_report_url?: string; depth_inches: number; width_inches: number;
  width_feet: number; severity?: string;
}

export default function PotholeForm() {
  const [demFiles, setDemFiles] = useState<DemFile[]>([]);
  const [selectedDemId, setSelectedDemId] = useState("");
  const [loadingFiles, setLoadingFiles] = useState(true);
  const { polygons } = usePolygons();
  const [selectedPolygonId, setSelectedPolygonId] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResult | null>(null);

  const showToast = (msg: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((p) => [...p, { id, message: msg, type }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), 4000);
  };

  useEffect(() => {
    const fetchDems = async () => {
      try {
        const res = await fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST_WITH_FILES);
        if (res.ok) {
          const folders = await res.json();
          const dems: DemFile[] = [];
          folders.forEach((f: { name: string; files: { id: string; filename: string; file_type: string }[] }) => {
            f.files.filter((fi) => fi.file_type === "DEM").forEach((fi) => dems.push({ ...fi, folder_name: f.name }));
          });
          setDemFiles(dems);
          if (dems.length > 0) setSelectedDemId(dems[0].id);
        }
      } catch { showToast("Failed to load DEM files"); }
      finally { setLoadingFiles(false); }
    };
    fetchDems();
  }, []);

  // Poll
  useEffect(() => {
    if (!jobId || !isAnalyzing) return;
    const poll = setInterval(async () => {
      try {
        const res = await fetchWithAuth(API_ENDPOINTS.POTHOLE.STATUS(jobId));
        if (!res.ok) return;
        const data: AnalysisResult = await res.json();
        setResults(data);
        if (data.status === "completed") {
          setIsAnalyzing(false);
          showToast(`Pothole: ${data.depth_inches.toFixed(1)}in deep, ${data.severity} severity`, "success");
          clearInterval(poll);
        } else if (data.status === "failed") {
          setIsAnalyzing(false);
          showToast(data.error_message || "Analysis failed", "error");
          clearInterval(poll);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(poll);
  }, [jobId, isAnalyzing]);

  const handleRun = async () => {
    if (!selectedDemId || !selectedPolygonId) { showToast("Select a DEM file and polygon"); return; }
    const polygon = polygons.find((p) => p.id === selectedPolygonId);
    if (!polygon) { showToast("Polygon not found"); return; }

    setIsAnalyzing(true); setResults(null); setJobId(null);
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.POTHOLE.BASE, {
        method: "POST",
        body: JSON.stringify({ tiff_file_id: selectedDemId, polygon_geojson: polygon.geoJSON }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Failed"); }
      const job = await res.json();
      setJobId(job.id);
      setResults({ id: job.id, status: "queued", progress: 0, depth_inches: 0, width_inches: 0, width_feet: 0 });
      showToast("Analyzing pothole...", "info");
    } catch (e) {
      setIsAnalyzing(false);
      showToast(e instanceof Error ? e.message : "Failed", "error");
    }
  };

  const sevColor: Record<string, string> = { Low: "text-green-400", Medium: "text-orange-400", High: "text-red-400" };

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Pothole Analysis (3D Surface)
        </h2>

        {/* DEM Selection */}
        <div className="grid grid-cols-[1fr_auto] items-center gap-3 py-1">
          <label className="font-semibold text-[12px] text-slate-300">Select DEM file</label>
          {loadingFiles ? (
            <div className="flex items-center gap-1 text-[12px] text-slate-400"><Loader2 size={14} className="animate-spin" /> Loading...</div>
          ) : demFiles.length === 0 ? (
            <span className="text-[12px] text-red-400">No DEM files</span>
          ) : (
            <select value={selectedDemId} onChange={(e) => setSelectedDemId(e.target.value)}
              className="text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 max-w-60 text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400">
              {demFiles.map((f) => (
                <option key={f.id} value={f.id}>{f.folder_name ? `${f.folder_name} / ${f.filename}` : f.filename}</option>
              ))}
            </select>
          )}
        </div>

        {/* Polygon Selection */}
        <div className="grid grid-cols-[1fr_auto] items-center gap-3 py-1">
          <label className="font-semibold text-[12px] text-slate-300">Select Polygon (around pothole)</label>
          {polygons.length === 0 ? (
            <span className="text-[12px] text-orange-400">Draw a polygon around the pothole on the map.</span>
          ) : (
            <select value={selectedPolygonId} onChange={(e) => setSelectedPolygonId(e.target.value)}
              className="text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 max-w-60 text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400">
              <option value="">-- select --</option>
              {polygons.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({new Date(p.createdAt).toLocaleTimeString()})</option>
              ))}
            </select>
          )}
        </div>

        <div className="text-[11px] text-slate-400 mt-1 mb-2">
          Draw a tight polygon around the pothole. The system extracts elevation data and computes depth, width, and severity.
        </div>

        {/* Progress */}
        {isAnalyzing && results && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <Loader2 size={16} className="animate-spin text-blue-400" />
                <span className="text-[13px] font-semibold text-blue-300">Processing...</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2.5">
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
                <div className="text-slate-300">Depth:</div>
                <div className="font-semibold text-slate-100">{results.depth_inches.toFixed(2)} inches</div>
                <div className="text-slate-300">Width:</div>
                <div className="font-semibold text-slate-100">{results.width_inches.toFixed(2)} in ({results.width_feet.toFixed(2)} ft)</div>
                <div className="text-slate-300">Severity:</div>
                <div className={`font-bold ${sevColor[results.severity || ""] || "text-slate-100"}`}>{results.severity}</div>
              </div>
              {results.html_report_url && (
                <a href={results.html_report_url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center justify-center gap-1.5 mt-3 px-3 py-2 bg-blue-600 text-white rounded-lg text-[12px] font-medium hover:bg-blue-700 transition-colors shadow-lg">
                  <ExternalLink size={14} /> View 3D Plot & Report
                </a>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {!isAnalyzing && results && results.status === "failed" && (
          <div className="border-t border-slate-700 pt-2 mt-2">
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-[13px] font-semibold mb-2 text-red-300"><AlertCircle size={16} /> Analysis Failed</div>
              <div className="text-[12px] text-red-400">{results.error_message || "Unknown error"}</div>
            </div>
          </div>
        )}

        {/* Run Button */}
        <div className="pt-3 mt-3 border-t border-slate-700">
          <button onClick={handleRun}
            disabled={isAnalyzing || loadingFiles || demFiles.length === 0 || !selectedPolygonId}
            className={`font-bold py-2.5 px-4 rounded-lg text-[13px] mx-auto block transition-all shadow-lg ${
              isAnalyzing || loadingFiles || demFiles.length === 0 || !selectedPolygonId
                ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                : "bg-red-700 text-white hover:bg-red-800 hover:shadow-xl"
            }`}>
            {isAnalyzing ? <span className="flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Analyzing...</span> : "Analyze Pothole"}
          </button>
        </div>
      </div>
    </>
  );
}
