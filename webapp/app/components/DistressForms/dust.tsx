// app/components/DistressForms/dust.tsx
"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import { Upload, Play, AlertCircle, Loader2, Trash2, Video, StopCircle } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS, API_URL } from "@/app/lib/api";

interface VideoInfo { id: string; filename: string; duration_seconds: number | null; }
interface FolderInfo { id: string; name: string; }
interface Toast { id: number; message: string; type: "error" | "success" | "info"; }

const MODELS = [
  { id: "yolo26", label: "YOLO26" },
];

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-white text-[13px] font-medium border ${
          t.type === "error" ? "bg-red-600 border-red-500" : t.type === "success" ? "bg-green-600 border-green-500" : "bg-blue-600 border-blue-500"
        }`}><AlertCircle size={12} /><span>{t.message}</span></div>
      ))}
    </div>
  );
}

export default function DustForm() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [folders, setFolders] = useState<FolderInfo[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState("");
  const [existingVideos, setExistingVideos] = useState<VideoInfo[]>([]);
  const [loadingVideos, setLoadingVideos] = useState(true);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [firstFrameUrl, setFirstFrameUrl] = useState<string | null>(null);
  const [polygonPoints, setPolygonPoints] = useState<number[][]>([]);
  const [isDrawing, setIsDrawing] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("yolo26");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const sel = "text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400";

  const showToast = (msg: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((p) => [...p, { id, message: msg, type }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), 4000);
  };

  const fetchData = useCallback(async () => {
    try {
      const [vRes, fRes] = await Promise.all([fetchWithAuth(API_ENDPOINTS.DUST.VIDEOS), fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST)]);
      if (vRes.ok) setExistingVideos(await vRes.json());
      if (fRes.ok) { const d = await fRes.json(); setFolders(d); if (d.length > 0 && !selectedFolderId) setSelectedFolderId(d[0].id); }
    } catch {} finally { setLoadingVideos(false); }
  }, [selectedFolderId]);
  useEffect(() => { fetchData(); }, [fetchData]);

  const [loadingFrame, setLoadingFrame] = useState(false);

  const selectVideo = async (v: VideoInfo) => {
    setVideoId(v.id); setPolygonPoints([]); setIsDrawing(true); setIsStreaming(false); setStreamUrl(null); setFirstFrameUrl(null); setLoadingFrame(true);
    try { const r = await fetchWithAuth(API_ENDPOINTS.DUST.FIRST_FRAME(v.id)); if (r.ok) setFirstFrameUrl(URL.createObjectURL(await r.blob())); }
    catch { showToast("Failed to load frame"); }
    finally { setLoadingFrame(false); }
  };

  const deleteVideo = async (id: string) => {
    try { const r = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_DELETE(id), { method: "DELETE" }); if (r.ok) { setExistingVideos((p) => p.filter((v) => v.id !== id)); if (videoId === id) { setVideoId(null); setFirstFrameUrl(null); } showToast("Deleted", "success"); } }
    catch { showToast("Failed to delete"); }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return;
    if (!f.name.toLowerCase().match(/\.(mp4|avi|mov)$/)) { showToast("Only .mp4, .avi, .mov"); return; }
    setVideoFile(f);
  };

  const handleUpload = async () => {
    if (!videoFile) return; setUploading(true); setUploadProgress(0);
    try {
      const pRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_PRESIGN, { method: "POST", body: JSON.stringify({ filename: videoFile.name, file_size: videoFile.size, folder_id: selectedFolderId || undefined, content_type: videoFile.type || "video/mp4" }) });
      if (!pRes.ok) throw new Error("Presign failed");
      const { presigned_url, video_id } = await pRes.json();
      const xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", (e) => { if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100)); });
      await new Promise<void>((res, rej) => { xhr.onload = () => xhr.status < 300 ? res() : rej(); xhr.onerror = () => rej(); xhr.open("PUT", presigned_url); xhr.setRequestHeader("Content-Type", videoFile.type || "video/mp4"); xhr.send(videoFile); });
      const cRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_COMPLETE(video_id), { method: "POST" });
      if (!cRes.ok) throw new Error("Complete failed");
      setVideoId(video_id); setVideoFile(null); setPolygonPoints([]); setIsDrawing(true); setIsStreaming(false); setStreamUrl(null);
      showToast("Uploaded!", "success");
      const fRes = await fetchWithAuth(API_ENDPOINTS.DUST.FIRST_FRAME(video_id));
      if (fRes.ok) setFirstFrameUrl(URL.createObjectURL(await fRes.blob()));
      fetchData();
    } catch (e) { showToast(e instanceof Error ? e.message : "Upload failed"); }
    finally { setUploading(false); }
  };

  // Polygon
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current; const img = imageRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);
    if (polygonPoints.length > 0) {
      ctx.strokeStyle = "#00ffff"; ctx.lineWidth = 3; ctx.fillStyle = "rgba(0,255,255,0.15)";
      ctx.beginPath(); ctx.moveTo(polygonPoints[0][0], polygonPoints[0][1]);
      for (let i = 1; i < polygonPoints.length; i++) ctx.lineTo(polygonPoints[i][0], polygonPoints[i][1]);
      if (polygonPoints.length === 4) { ctx.closePath(); ctx.fill(); }
      ctx.stroke();
      polygonPoints.forEach((pt, i) => {
        ctx.beginPath(); ctx.arc(pt[0], pt[1], 10, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,255,0,0.3)"; ctx.fill();
        ctx.beginPath(); ctx.arc(pt[0], pt[1], 6, 0, Math.PI * 2); ctx.fillStyle = "#00ff00"; ctx.fill();
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = "#fff"; ctx.font = "bold 14px sans-serif"; ctx.strokeStyle = "#000"; ctx.lineWidth = 2;
        ctx.strokeText(`${i + 1}`, pt[0] + 10, pt[1] - 10); ctx.fillText(`${i + 1}`, pt[0] + 10, pt[1] - 10);
      });
    }
    if (polygonPoints.length < 4 && isDrawing) {
      const labels = [
        "Click TOP-LEFT corner of road",
        "Click TOP-RIGHT corner of road",
        "Click BOTTOM-RIGHT corner of road",
        "Click BOTTOM-LEFT corner of road",
      ];
      const step = `Step ${polygonPoints.length + 1}/4`;
      const fontSize = Math.max(16, Math.round(canvas.width / 40));
      ctx.font = `bold ${fontSize}px sans-serif`;
      const text = labels[polygonPoints.length];
      const tw = ctx.measureText(text).width;
      const padding = 12;
      const boxH = fontSize + padding * 2;
      // Background
      ctx.fillStyle = "rgba(0,0,0,0.8)";
      ctx.fillRect(0, 0, tw + padding * 3 + ctx.measureText(step).width + 20, boxH);
      // Step badge
      ctx.fillStyle = "#f97316";
      ctx.fillText(step, padding, fontSize + padding - 2);
      // Instruction text
      ctx.fillStyle = "#00ffff";
      ctx.fillText(text, padding + ctx.measureText(step).width + 12, fontSize + padding - 2);
    }
  }, [polygonPoints, isDrawing]);
  useEffect(() => { if (!firstFrameUrl) return; const img = new Image(); img.onload = () => { imageRef.current = img; drawCanvas(); }; img.src = firstFrameUrl; }, [firstFrameUrl, drawCanvas]);
  useEffect(() => { drawCanvas(); }, [polygonPoints, drawCanvas]);
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || polygonPoints.length >= 4) return;
    const c = canvasRef.current; if (!c) return; const r = c.getBoundingClientRect();
    const pts = [...polygonPoints, [Math.round((e.clientX - r.left) * (c.width / r.width)), Math.round((e.clientY - r.top) * (c.height / r.height))]];
    setPolygonPoints(pts); if (pts.length === 4) setIsDrawing(false);
  };

  // Stream
  const [streamLoading, setStreamLoading] = useState(false);
  const startStream = (m?: string) => {
    if (!videoId || polygonPoints.length !== 4) return;
    setStreamLoading(true);
    setStreamUrl(`${API_URL}${API_ENDPOINTS.DUST.STREAM(videoId, polygonPoints, 1.0, m ?? selectedModel)}`);
    setIsStreaming(true);
  };
  const changeModel = (m: string) => { setSelectedModel(m); if (isStreaming) { setStreamUrl(null); setTimeout(() => startStream(m), 50); } };
  const stopStream = () => { setStreamUrl(null); setIsStreaming(false); setStreamLoading(false); };

  // Analysis job
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisResults, setAnalysisResults] = useState<{ counts: Record<string, number>; percentages: Record<string, number>; total_classified: number } | null>(null);
  const [showResults, setShowResults] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startAnalysis = async () => {
    if (!videoId || polygonPoints.length !== 4) return;
    setIsAnalyzing(true); setAnalysisProgress(0); setAnalysisResults(null); setAnalysisError(null);
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.DUST.BASE, {
        method: "POST",
        body: JSON.stringify({ video_file_id: videoId, polygon_points: polygonPoints }),
      });
      if (!res.ok) throw new Error("Failed to start analysis");
      const job = await res.json();
      const jobId = job.id;

      pollingRef.current = setInterval(async () => {
        try {
          const s = await fetchWithAuth(API_ENDPOINTS.DUST.STATUS(jobId));
          if (!s.ok) return;
          const data = await s.json();
          setAnalysisProgress(data.progress);

          if (data.status === "completed") {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setAnalysisResults(data.results_json);
            setIsAnalyzing(false);
            showToast("Analysis complete!", "success");
          } else if (data.status === "failed") {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setAnalysisError(data.error_message || "Analysis failed");
            setIsAnalyzing(false);
          }
        } catch {}
      }, 2000);
    } catch (e) {
      setIsAnalyzing(false);
      showToast(e instanceof Error ? e.message : "Failed to start analysis");
    }
  };

  useEffect(() => { return () => { if (pollingRef.current) clearInterval(pollingRef.current); }; }, []);

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Object Detection (YOLO)
        </h2>

        {/* === SETUP === */}
        {!isStreaming && !showResults && (
          <div className="space-y-2">
            {/* Row 1: Video select + Model + Project */}
            <div className="flex gap-1.5 items-end">
              {/* Video dropdown */}
              <div className="flex-1">
                <label className="font-semibold text-[12px] text-slate-300 block mb-1">Video</label>
                {loadingVideos ? <span className="text-slate-500">Loading...</span> : (
                  <select
                    value={videoId || ""}
                    onChange={(e) => { const v = existingVideos.find(v => v.id === e.target.value); if (v) selectVideo(v); }}
                    className={sel + " w-full"}
                  >
                    <option value="">-- select --</option>
                    {existingVideos.map((v) => (
                      <option key={v.id} value={v.id}>{v.filename}{v.duration_seconds ? ` (${v.duration_seconds.toFixed(0)}s)` : ""}</option>
                    ))}
                  </select>
                )}
              </div>
              {/* Model dropdown */}
              <div>
                <label className="font-semibold text-[12px] text-slate-300 block mb-1">Model</label>
                <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} className={sel}>
                  {MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </div>
            </div>

            {/* Row 2: Upload new */}
            <div className="flex gap-1.5 items-end">
              {folders.length > 0 && (
                <div>
                  <label className="font-semibold text-[12px] text-slate-300 block mb-1">Project</label>
                  <select value={selectedFolderId} onChange={(e) => setSelectedFolderId(e.target.value)} className={sel}>
                    <option value="">None</option>
                    {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </div>
              )}
              <div className="flex-1">
                <label className="font-semibold text-[12px] text-slate-300 block mb-1">Upload new</label>
                <div className="flex gap-1">
                  <label className="flex-1 flex items-center gap-1 px-2 py-1 bg-slate-700 border border-slate-600 border-dashed rounded cursor-pointer hover:bg-slate-600">
                    <Upload size={10} /><span className="truncate">{videoFile ? videoFile.name : ".mp4"}</span>
                    <input type="file" accept=".mp4,.avi,.mov" onChange={handleFileSelect} className="hidden" />
                  </label>
                  <button onClick={handleUpload} disabled={!videoFile || uploading} className={`px-2 py-1 rounded font-medium ${!videoFile || uploading ? "bg-slate-700 text-slate-500" : "bg-blue-600 text-white hover:bg-blue-700"}`}>
                    {uploading ? `${uploadProgress}%` : "Go"}
                  </button>
                </div>
              </div>
            </div>
            {uploading && <div className="w-full bg-slate-700 rounded-full h-1"><div className="bg-blue-500 h-1 transition-all" style={{ width: `${uploadProgress}%` }} /></div>}

            {/* Loading first frame */}
            {loadingFrame && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
                <span className="ml-2 text-slate-400 text-[12px]">Loading video frame...</span>
              </div>
            )}

            {/* Polygon drawing */}
            {firstFrameUrl && !loadingFrame && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-[12px] text-slate-300">{isDrawing ? `Select detection region (${polygonPoints.length}/4)` : "Detection region set"}</span>
                  {polygonPoints.length > 0 && <button onClick={() => { setPolygonPoints([]); setIsDrawing(true); }} className="text-red-400 hover:text-red-300">Reset</button>}
                </div>
                <canvas ref={canvasRef} onClick={handleCanvasClick} className={`w-full rounded border border-slate-600 ${isDrawing ? "cursor-crosshair" : ""}`} style={{ maxHeight: "280px" }} />
              </div>
            )}

            {/* Start buttons */}
            {videoId && polygonPoints.length === 4 && !isAnalyzing && (
              <div className="flex gap-2">
                <button onClick={() => startStream()} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-700 text-white rounded-lg text-[13px] font-bold hover:bg-red-800 shadow-lg">
                  <Play size={16} /> Live Preview
                </button>
                <button onClick={startAnalysis} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-700 text-white rounded-lg text-[13px] font-bold hover:bg-blue-800 shadow-lg">
                  <Play size={16} /> Run Analysis
                </button>
              </div>
            )}

            {/* Analysis progress */}
            {isAnalyzing && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                  <span className="text-[12px] text-slate-300">Analyzing video... {analysisProgress}%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2">
                  <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${analysisProgress}%` }} />
                </div>
              </div>
            )}

            {/* Analysis error */}
            {analysisError && (
              <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-2 text-[12px] text-red-300">
                {analysisError}
              </div>
            )}

            {/* Results ready — show button */}
            {analysisResults && !showResults && (
              <button onClick={() => setShowResults(true)} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-700 text-white rounded-lg text-[13px] font-bold hover:bg-green-800 shadow-lg">
                View Results
              </button>
            )}
          </div>
        )}

        {/* === LIVE STREAM === */}
        {isStreaming && (
          <div className="space-y-2">
            <div className="relative">
              {streamLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60 rounded z-10">
                  <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
                  <span className="ml-2 text-white text-[13px] font-medium">Loading detection stream...</span>
                </div>
              )}
              {streamUrl && (
                <img src={streamUrl} alt="Detection" onLoad={() => setStreamLoading(false)} className="w-full rounded border border-slate-600" style={{ maxHeight: "55vh", objectFit: "contain", backgroundColor: "#000" }} />
              )}
              <div className="absolute top-1.5 left-1.5 flex items-center gap-1 bg-red-600/90 px-1.5 py-0.5 rounded text-[9px] font-bold text-white">
                <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" /> LIVE
              </div>
            </div>

            {/* Controls row */}
            <div className="flex items-center gap-2">
              <select value={selectedModel} onChange={(e) => changeModel(e.target.value)} className={sel}>
                {MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
              <button onClick={stopStream} className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 text-white rounded-lg text-[12px] hover:bg-slate-600">
                <StopCircle size={14} /> Stop
              </button>
            </div>
          </div>
        )}
        {/* === RESULTS VIEW === */}
        {showResults && analysisResults && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[14px] font-bold text-slate-200">Dust Analysis Results</h3>
              <button onClick={() => setShowResults(false)} className="text-[11px] text-blue-400 hover:text-blue-300">Back to setup</button>
            </div>

            {/* Pie chart */}
            <div className="flex justify-center">
              <PieChart data={analysisResults.percentages} counts={analysisResults.counts} total={analysisResults.total_classified} />
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-2">
                <div className="text-[18px] font-bold text-red-400">{analysisResults.percentages["High Dust"]}%</div>
                <div className="text-[10px] text-slate-400">High Dust</div>
                <div className="text-[10px] text-slate-500">{analysisResults.counts["High Dust"]} frames</div>
              </div>
              <div className="bg-yellow-900/30 border border-yellow-700/50 rounded-lg p-2">
                <div className="text-[18px] font-bold text-yellow-400">{analysisResults.percentages["Low Dust"]}%</div>
                <div className="text-[10px] text-slate-400">Low Dust</div>
                <div className="text-[10px] text-slate-500">{analysisResults.counts["Low Dust"]} frames</div>
              </div>
              <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-2">
                <div className="text-[18px] font-bold text-green-400">{analysisResults.percentages["Non Dust"]}%</div>
                <div className="text-[10px] text-slate-400">Non Dust</div>
                <div className="text-[10px] text-slate-500">{analysisResults.counts["Non Dust"]} frames</div>
              </div>
            </div>

            <div className="text-[10px] text-slate-500 text-center">
              Total classified frames: {analysisResults.total_classified}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/* Simple SVG pie chart — no external dependencies */
function PieChart({ data, counts, total }: { data: Record<string, number>; counts: Record<string, number>; total: number }) {
  const colors: Record<string, string> = { "High Dust": "#ef4444", "Low Dust": "#eab308", "Non Dust": "#22c55e" };
  const entries = Object.entries(data).filter(([, v]) => v > 0);

  if (entries.length === 0) {
    return <div className="text-slate-500 text-[12px] py-4">No classified frames</div>;
  }

  const size = 200;
  const cx = size / 2, cy = size / 2, r = 80;
  let cumAngle = -Math.PI / 2;

  const slices = entries.map(([label, pct]) => {
    const angle = (pct / 100) * 2 * Math.PI;
    const startX = cx + r * Math.cos(cumAngle);
    const startY = cy + r * Math.sin(cumAngle);
    cumAngle += angle;
    const endX = cx + r * Math.cos(cumAngle);
    const endY = cy + r * Math.sin(cumAngle);
    const large = angle > Math.PI ? 1 : 0;
    const d = `M ${cx} ${cy} L ${startX} ${startY} A ${r} ${r} 0 ${large} 1 ${endX} ${endY} Z`;

    // Label position
    const midAngle = cumAngle - angle / 2;
    const labelR = r * 0.6;
    const lx = cx + labelR * Math.cos(midAngle);
    const ly = cy + labelR * Math.sin(midAngle);

    return { label, pct, d, color: colors[label] || "#888", lx, ly };
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {slices.map((s) => (
        <g key={s.label}>
          <path d={s.d} fill={s.color} stroke="#1e293b" strokeWidth="2" />
          {s.pct > 8 && (
            <text x={s.lx} y={s.ly} textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="12" fontWeight="bold">
              {s.pct}%
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
