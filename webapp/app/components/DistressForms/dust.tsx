// app/components/DistressForms/dust.tsx
"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import { Upload, Play, AlertCircle, Loader2, Trash2, Video } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS } from "@/app/lib/api";

interface VideoInfo {
  id: string;
  filename: string;
  total_frames: number | null;
  fps: number | null;
  duration_seconds: number | null;
  created_at: string;
}

interface FolderInfo { id: string; name: string; }

interface Toast {
  id: number;
  message: string;
  type: "error" | "success" | "info";
}

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-white text-[13px] font-medium border ${
            toast.type === "error" ? "bg-red-600 border-red-500"
            : toast.type === "success" ? "bg-green-600 border-green-500"
            : "bg-blue-600 border-blue-500"
          }`}
        >
          <AlertCircle size={16} />
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}

export default function DustForm() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [folders, setFolders] = useState<FolderInfo[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>("");
  const [existingVideos, setExistingVideos] = useState<VideoInfo[]>([]);
  const [loadingVideos, setLoadingVideos] = useState(true);

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [videoId, setVideoId] = useState<string | null>(null);
  const [firstFrameUrl, setFirstFrameUrl] = useState<string | null>(null);
  const [polygonPoints, setPolygonPoints] = useState<number[][]>([]);
  const [isDrawing, setIsDrawing] = useState(true);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [annotatedVideoUrl, setAnnotatedVideoUrl] = useState<string | null>(null);
  const [truckFrames, setTruckFrames] = useState(0);
  const [noTruckFrames, setNoTruckFrames] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const showToast = (message: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  // --- Fetch data ---
  const fetchData = useCallback(async () => {
    try {
      const [videosRes, foldersRes] = await Promise.all([
        fetchWithAuth(API_ENDPOINTS.DUST.VIDEOS),
        fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST),
      ]);
      if (videosRes.ok) setExistingVideos(await videosRes.json());
      if (foldersRes.ok) {
        const data = await foldersRes.json();
        setFolders(data);
        if (data.length > 0 && !selectedFolderId) setSelectedFolderId(data[0].id);
      }
    } catch { /* ignore */ }
    finally { setLoadingVideos(false); }
  }, [selectedFolderId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // --- Select existing video ---
  const selectVideo = async (video: VideoInfo) => {
    setVideoId(video.id);
    setPolygonPoints([]);
    setIsDrawing(true);
    setDone(false);
    setAnnotatedVideoUrl(null);
    setFirstFrameUrl(null);
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.DUST.FIRST_FRAME(video.id));
      if (res.ok) {
        const blob = await res.blob();
        setFirstFrameUrl(URL.createObjectURL(blob));
      }
    } catch { showToast("Failed to load first frame"); }
  };

  const deleteVideo = async (id: string) => {
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_DELETE(id), { method: "DELETE" });
      if (res.ok) {
        setExistingVideos((prev) => prev.filter((v) => v.id !== id));
        if (videoId === id) { setVideoId(null); setFirstFrameUrl(null); }
        showToast("Video deleted", "success");
      }
    } catch { showToast("Failed to delete"); }
  };

  // --- Upload ---
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().match(/\.(mp4|avi|mov)$/)) {
      showToast("Only .mp4, .avi, .mov files are allowed"); return;
    }
    setVideoFile(file);
  };

  const handleUpload = async () => {
    if (!videoFile) return;
    setUploading(true); setUploadProgress(0);
    try {
      const presignRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_PRESIGN, {
        method: "POST",
        body: JSON.stringify({
          filename: videoFile.name, file_size: videoFile.size,
          folder_id: selectedFolderId || undefined,
          content_type: videoFile.type || "video/mp4",
        }),
      });
      if (!presignRes.ok) throw new Error("Failed to get presigned URL");
      const { presigned_url, video_id } = await presignRes.json();

      const xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
      });
      await new Promise<void>((resolve, reject) => {
        xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error("Upload failed")));
        xhr.onerror = () => reject(new Error("Upload failed"));
        xhr.open("PUT", presigned_url);
        xhr.setRequestHeader("Content-Type", videoFile.type || "video/mp4");
        xhr.send(videoFile);
      });

      const completeRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_COMPLETE(video_id), { method: "POST" });
      if (!completeRes.ok) throw new Error("Failed to complete upload");

      setVideoId(video_id);
      setVideoFile(null);
      setPolygonPoints([]); setIsDrawing(true); setDone(false); setAnnotatedVideoUrl(null);
      showToast("Video uploaded!", "success");

      const frameRes = await fetchWithAuth(API_ENDPOINTS.DUST.FIRST_FRAME(video_id));
      if (frameRes.ok) {
        const blob = await frameRes.blob();
        setFirstFrameUrl(URL.createObjectURL(blob));
      }
      fetchData();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Upload failed");
    } finally { setUploading(false); }
  };

  // --- Polygon Drawing ---
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imageRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);

    if (polygonPoints.length > 0) {
      ctx.strokeStyle = "#00ffff"; ctx.lineWidth = 3;
      ctx.fillStyle = "rgba(0, 255, 255, 0.15)";
      ctx.beginPath();
      ctx.moveTo(polygonPoints[0][0], polygonPoints[0][1]);
      for (let i = 1; i < polygonPoints.length; i++) ctx.lineTo(polygonPoints[i][0], polygonPoints[i][1]);
      if (polygonPoints.length === 4) { ctx.closePath(); ctx.fill(); }
      ctx.stroke();

      polygonPoints.forEach((pt, i) => {
        ctx.beginPath(); ctx.arc(pt[0], pt[1], 12, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 255, 0, 0.3)"; ctx.fill();
        ctx.beginPath(); ctx.arc(pt[0], pt[1], 8, 0, Math.PI * 2);
        ctx.fillStyle = "#00ff00"; ctx.fill();
        ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 3; ctx.stroke();
        ctx.fillStyle = "#ffffff"; ctx.font = "bold 16px sans-serif";
        ctx.strokeStyle = "#000000"; ctx.lineWidth = 3;
        ctx.strokeText(`${i + 1}`, pt[0] + 14, pt[1] - 14);
        ctx.fillText(`${i + 1}`, pt[0] + 14, pt[1] - 14);
      });
    }

    if (polygonPoints.length < 4 && isDrawing) {
      const labels = ["Click TOP-LEFT corner", "Click TOP-RIGHT corner", "Click BOTTOM-RIGHT corner", "Click BOTTOM-LEFT corner"];
      ctx.fillStyle = "rgba(0,0,0,0.8)"; ctx.fillRect(10, 10, 320, 36);
      ctx.fillStyle = "#00ffff"; ctx.font = "bold 18px sans-serif";
      ctx.fillText(labels[polygonPoints.length], 20, 35);
    }
  }, [polygonPoints, isDrawing]);

  useEffect(() => {
    if (!firstFrameUrl) return;
    const img = new Image();
    img.onload = () => { imageRef.current = img; drawCanvas(); };
    img.src = firstFrameUrl;
  }, [firstFrameUrl, drawCanvas]);

  useEffect(() => { drawCanvas(); }, [polygonPoints, drawCanvas]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || polygonPoints.length >= 4) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round((e.clientX - rect.left) * (canvas.width / rect.width));
    const y = Math.round((e.clientY - rect.top) * (canvas.height / rect.height));
    const newPoints = [...polygonPoints, [x, y]];
    setPolygonPoints(newPoints);
    if (newPoints.length === 4) setIsDrawing(false);
  };

  // --- Start Analysis + Poll ---
  const startAnalysis = async () => {
    if (!videoId || polygonPoints.length !== 4) return;
    setIsAnalyzing(true); setProgress(0); setDone(false); setAnnotatedVideoUrl(null);

    try {
      const res = await fetchWithAuth(API_ENDPOINTS.DUST.BASE, {
        method: "POST",
        body: JSON.stringify({ video_file_id: videoId, polygon_points: polygonPoints }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start");
      }
      const job = await res.json();
      showToast("Analysis started — processing video...", "info");

      // Poll for status
      const pollId = setInterval(async () => {
        try {
          const statusRes = await fetchWithAuth(API_ENDPOINTS.DUST.STATUS(job.id));
          if (!statusRes.ok) return;
          const data = await statusRes.json();
          setProgress(data.progress);
          setTruckFrames(data.truck_frames);
          setNoTruckFrames(data.no_truck_frames);

          if (data.status === "completed") {
            clearInterval(pollId);
            setIsAnalyzing(false);
            setDone(true);
            // Fetch full result to get annotated video URL
            const resultRes = await fetchWithAuth(API_ENDPOINTS.DUST.GET(job.id));
            if (resultRes.ok) {
              const result = await resultRes.json();
              if (result.results_json?.annotated_video_url) {
                setAnnotatedVideoUrl(result.results_json.annotated_video_url);
              }
            }
            showToast("Analysis complete!", "success");
          } else if (data.status === "failed") {
            clearInterval(pollId);
            setIsAnalyzing(false);
            showToast(data.error_message || "Analysis failed", "error");
          }
        } catch { /* ignore polling errors */ }
      }, 2000);
    } catch (err) {
      setIsAnalyzing(false);
      showToast(err instanceof Error ? err.message : "Failed to start", "error");
    }
  };

  const totalProcessed = truckFrames + noTruckFrames;

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-4 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[15px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Dust Detection (YOLOv8)
        </h2>

        {/* Setup: video selection + polygon */}
        {!isAnalyzing && !done && (
          <div className="space-y-3">
            {/* Existing Videos */}
            {loadingVideos ? (
              <div className="flex items-center gap-2 text-slate-400 text-[12px]">
                <Loader2 size={14} className="animate-spin" /> Loading...
              </div>
            ) : existingVideos.length > 0 && (
              <div>
                <label className="font-semibold text-[12px] text-slate-300 mb-1 block">Previous Videos</label>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {existingVideos.map((v) => (
                    <div
                      key={v.id}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded text-[12px] cursor-pointer transition-colors ${
                        videoId === v.id ? "bg-cyan-900/40 border border-cyan-700/50" : "bg-slate-700/50 hover:bg-slate-700"
                      }`}
                      onClick={() => selectVideo(v)}
                    >
                      <Video size={14} className="text-slate-400 shrink-0" />
                      <span className="flex-1 truncate">{v.filename}</span>
                      <span className="text-slate-500 text-[10px] shrink-0">
                        {v.duration_seconds ? `${v.duration_seconds.toFixed(0)}s` : ""}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteVideo(v.id); }}
                        className="text-red-400 hover:text-red-300 shrink-0"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upload New */}
            <div>
              <label className="font-semibold text-[12px] text-slate-300 mb-1 block">
                {existingVideos.length > 0 ? "Or Upload New" : "Upload Video"}
              </label>
              {folders.length > 0 && (
                <select
                  value={selectedFolderId}
                  onChange={(e) => setSelectedFolderId(e.target.value)}
                  className="w-full mb-2 text-[12px] bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-slate-100 focus:outline-none focus:border-cyan-400"
                >
                  <option value="">No project</option>
                  {folders.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              )}
              <div className="flex gap-2">
                <label className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 bg-slate-700 border border-slate-600 border-dashed rounded-lg cursor-pointer hover:bg-slate-600 transition-colors">
                  <Upload size={16} />
                  <span className="text-[12px] truncate">{videoFile ? videoFile.name : "Select .mp4 file"}</span>
                  <input type="file" accept=".mp4,.avi,.mov" onChange={handleFileSelect} className="hidden" />
                </label>
                <button
                  onClick={handleUpload}
                  disabled={!videoFile || uploading}
                  className={`px-4 py-2.5 rounded-lg text-[12px] font-medium transition-colors ${
                    !videoFile || uploading ? "bg-slate-700 text-slate-500 cursor-not-allowed" : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {uploading ? `${uploadProgress}%` : "Upload"}
                </button>
              </div>
              {uploading && (
                <div className="w-full bg-slate-700 rounded-full h-1.5 mt-1">
                  <div className="bg-blue-500 h-1.5 transition-all" style={{ width: `${uploadProgress}%` }} />
                </div>
              )}
            </div>

            {/* Polygon Drawing */}
            {firstFrameUrl && (
              <div className="space-y-2 border-t border-slate-700 pt-3">
                <div className="flex items-center justify-between">
                  <label className="font-semibold text-[12px] text-slate-300">
                    {isDrawing ? `Select road boundary (${polygonPoints.length}/4)` : "Road boundary set"}
                  </label>
                  {polygonPoints.length > 0 && (
                    <button onClick={() => { setPolygonPoints([]); setIsDrawing(true); }}
                      className="text-[11px] text-red-400 hover:text-red-300">Reset</button>
                  )}
                </div>
                <canvas
                  ref={canvasRef}
                  onClick={handleCanvasClick}
                  className={`w-full rounded border border-slate-600 ${isDrawing ? "cursor-crosshair" : "cursor-default"}`}
                  style={{ maxHeight: "380px", objectFit: "contain" }}
                />
              </div>
            )}

            {/* Start Button */}
            {videoId && polygonPoints.length === 4 && (
              <button
                onClick={startAnalysis}
                className="w-full flex items-center justify-center gap-2 px-3 py-3 bg-red-700 text-white rounded-lg text-[14px] font-bold hover:bg-red-800 transition-colors shadow-lg"
              >
                <Play size={18} /> Start Analysis
              </button>
            )}
          </div>
        )}

        {/* Processing */}
        {isAnalyzing && (
          <div className="space-y-3">
            <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Loader2 size={18} className="animate-spin text-blue-400" />
                <span className="text-[14px] font-semibold text-blue-300">Processing video...</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
                <div className="bg-blue-500 h-3 transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
              <div className="text-[12px] text-slate-400 mt-2 text-right">{progress}%</div>
              {totalProcessed > 0 && (
                <div className="grid grid-cols-2 gap-2 mt-3 text-center text-[12px]">
                  <div><span className="text-cyan-400 font-bold">{truckFrames}</span> truck frames</div>
                  <div><span className="text-slate-300 font-bold">{noTruckFrames}</span> no truck</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Results — annotated video */}
        {done && (
          <div className="space-y-3">
            {annotatedVideoUrl && (
              <div>
                <label className="font-semibold text-[12px] text-slate-300 mb-1 block">
                  Annotated Video (bounding boxes)
                </label>
                <video
                  src={annotatedVideoUrl}
                  className="w-full rounded border border-slate-600"
                  style={{ maxHeight: "400px" }}
                  controls
                  autoPlay
                  muted
                  playsInline
                />
              </div>
            )}

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[20px] font-bold text-cyan-400">{truckFrames}</div>
                <div className="text-[10px] text-slate-400">Truck Frames</div>
              </div>
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[20px] font-bold text-slate-300">{noTruckFrames}</div>
                <div className="text-[10px] text-slate-400">No Truck</div>
              </div>
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[20px] font-bold text-green-400">
                  {totalProcessed > 0 ? `${((truckFrames / totalProcessed) * 100).toFixed(1)}%` : "—"}
                </div>
                <div className="text-[10px] text-slate-400">Detection Rate</div>
              </div>
            </div>

            <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-3">
              <div className="text-[13px] font-semibold text-green-300 mb-1">Analysis Complete</div>
              <div className="text-[12px] text-slate-300">
                Processed {totalProcessed} frames. Vehicle detected in {truckFrames} ({totalProcessed > 0 ? ((truckFrames / totalProcessed) * 100).toFixed(1) : 0}%).
              </div>
              <button
                onClick={() => { setDone(false); setAnnotatedVideoUrl(null); setPolygonPoints([]); setIsDrawing(true); setFirstFrameUrl(null); setVideoId(null); }}
                className="mt-2 text-[12px] text-cyan-400 hover:text-cyan-300 underline"
              >
                Run another analysis
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
