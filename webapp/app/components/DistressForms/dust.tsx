// app/components/DistressForms/dust.tsx
"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import { Upload, Play, AlertCircle, Loader2, X } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS, WS_URL } from "@/app/lib/api";

interface FrameResult {
  frame: number;
  truck: boolean;
  vehicle_count?: number;
}

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
            toast.type === "error"
              ? "bg-red-600 border-red-500"
              : toast.type === "success"
              ? "bg-green-600 border-green-500"
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
  // State
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [firstFrameUrl, setFirstFrameUrl] = useState<string | null>(null);
  const [polygonPoints, setPolygonPoints] = useState<number[][]>([]);
  const [isDrawing, setIsDrawing] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [frameResults, setFrameResults] = useState<FrameResult[]>([]);
  const [totalFrames, setTotalFrames] = useState(0);
  const [done, setDone] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartCanvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const showToast = (message: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  // --- Video Upload ---
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().match(/\.(mp4|avi|mov)$/)) {
      showToast("Only .mp4, .avi, .mov files are allowed");
      return;
    }
    setVideoFile(file);
    setVideoId(null);
    setFirstFrameUrl(null);
    setPolygonPoints([]);
    setFrameResults([]);
    setDone(false);
  };

  const handleUpload = async () => {
    if (!videoFile) return;
    setUploading(true);
    setUploadProgress(0);

    try {
      // Get presigned URL
      const presignRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_PRESIGN, {
        method: "POST",
        body: JSON.stringify({
          filename: videoFile.name,
          file_size: videoFile.size,
          content_type: videoFile.type || "video/mp4",
        }),
      });
      if (!presignRes.ok) throw new Error("Failed to get presigned URL");
      const { presigned_url, video_id } = await presignRes.json();

      // Upload to S3
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

      // Complete upload
      const completeRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_COMPLETE(video_id), {
        method: "POST",
      });
      if (!completeRes.ok) throw new Error("Failed to complete upload");
      const videoData = await completeRes.json();

      setVideoId(video_id);
      setTotalFrames(videoData.total_frames || 0);
      showToast("Video uploaded successfully!", "success");

      // Fetch first frame
      const frameRes = await fetchWithAuth(API_ENDPOINTS.DUST.FIRST_FRAME(video_id));
      if (frameRes.ok) {
        const blob = await frameRes.blob();
        setFirstFrameUrl(URL.createObjectURL(blob));
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  // --- Draw first frame + polygon on canvas ---
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imageRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);

    // Draw polygon points
    if (polygonPoints.length > 0) {
      ctx.strokeStyle = "#ff0000";
      ctx.lineWidth = 3;
      ctx.fillStyle = "rgba(255, 0, 0, 0.15)";

      ctx.beginPath();
      ctx.moveTo(polygonPoints[0][0], polygonPoints[0][1]);
      for (let i = 1; i < polygonPoints.length; i++) {
        ctx.lineTo(polygonPoints[i][0], polygonPoints[i][1]);
      }
      if (polygonPoints.length === 4) {
        ctx.closePath();
        ctx.fill();
      }
      ctx.stroke();

      // Draw vertex circles
      polygonPoints.forEach((pt, i) => {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 6, 0, Math.PI * 2);
        ctx.fillStyle = "#00ff00";
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();

        // Label
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 14px sans-serif";
        ctx.fillText(`${i + 1}`, pt[0] + 10, pt[1] - 10);
      });
    }

    // Instructions
    if (polygonPoints.length < 4 && isDrawing) {
      const labels = ["Click TOP-LEFT", "Click TOP-RIGHT", "Click BOTTOM-RIGHT", "Click BOTTOM-LEFT"];
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      ctx.fillRect(10, 10, 280, 32);
      ctx.fillStyle = "#ff4444";
      ctx.font = "bold 16px sans-serif";
      ctx.fillText(labels[polygonPoints.length], 20, 32);
    }
  }, [polygonPoints, isDrawing]);

  useEffect(() => {
    if (!firstFrameUrl) return;
    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      drawCanvas();
    };
    img.src = firstFrameUrl;
  }, [firstFrameUrl, drawCanvas]);

  useEffect(() => {
    drawCanvas();
  }, [polygonPoints, drawCanvas]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || polygonPoints.length >= 4) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    const newPoints = [...polygonPoints, [x, y]];
    setPolygonPoints(newPoints);

    if (newPoints.length === 4) {
      setIsDrawing(false);
    }
  };

  // --- Real-time chart ---
  const drawChart = useCallback(() => {
    const canvas = chartCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    const padding = { top: 20, right: 20, bottom: 30, left: 60 };
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1;

    // Y-axis labels
    ctx.fillStyle = "#94a3b8";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("Truck", padding.left - 8, padding.top + 8);
    ctx.fillText("No Truck", padding.left - 8, padding.top + plotH + 4);

    // Horizontal grid lines
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left + plotW, padding.top);
    ctx.moveTo(padding.left, padding.top + plotH);
    ctx.lineTo(padding.left + plotW, padding.top + plotH);
    ctx.stroke();

    // X-axis label
    ctx.textAlign = "center";
    ctx.fillText("Frame", padding.left + plotW / 2, h - 5);

    if (frameResults.length === 0) return;

    // Plot line
    const maxFrame = Math.max(frameResults.length, 100);
    const xScale = plotW / maxFrame;

    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    frameResults.forEach((r, i) => {
      const x = padding.left + i * xScale;
      const y = r.truck ? padding.top + 4 : padding.top + plotH - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill under truck detections
    ctx.fillStyle = "rgba(59, 130, 246, 0.1)";
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + plotH);
    frameResults.forEach((r, i) => {
      const x = padding.left + i * xScale;
      const y = r.truck ? padding.top + 4 : padding.top + plotH - 4;
      ctx.lineTo(x, y);
    });
    ctx.lineTo(padding.left + (frameResults.length - 1) * xScale, padding.top + plotH);
    ctx.closePath();
    ctx.fill();

    // Frame count
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "left";
    ctx.fillText(`Frame ${frameResults.length}${totalFrames ? ` / ${totalFrames}` : ""}`, padding.left + 4, h - 5);
  }, [frameResults, totalFrames]);

  useEffect(() => {
    drawChart();
  }, [frameResults, drawChart]);

  // --- WebSocket ---
  const startAnalysis = async () => {
    if (!videoId || polygonPoints.length !== 4) return;

    setIsAnalyzing(true);
    setFrameResults([]);
    setDone(false);

    try {
      const res = await fetchWithAuth(API_ENDPOINTS.DUST.BASE, {
        method: "POST",
        body: JSON.stringify({
          video_file_id: videoId,
          polygon_points: polygonPoints,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start analysis");
      }

      const job = await res.json();
      setJobId(job.id);
      showToast("Analysis started!", "info");

      // Open WebSocket directly to backend (bypasses Next.js rewrite)
      const wsUrl = `${WS_URL}/${API_ENDPOINTS.DUST.WS(job.id)}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.done) {
          setDone(true);
          setIsAnalyzing(false);
          showToast(`Analysis complete! ${data.total_frames} frames processed.`, "success");
          ws.close();
          return;
        }

        if (data.error) {
          setIsAnalyzing(false);
          showToast(data.error, "error");
          ws.close();
          return;
        }

        // Per-frame result
        setFrameResults((prev) => [...prev, { frame: data.frame, truck: data.truck, vehicle_count: data.vehicle_count }]);
      };

      ws.onerror = () => {
        showToast("WebSocket connection error", "error");
        setIsAnalyzing(false);
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    } catch (err) {
      setIsAnalyzing(false);
      showToast(err instanceof Error ? err.message : "Failed to start", "error");
    }
  };

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  // Stats
  const truckCount = frameResults.filter((r) => r.truck).length;
  const noTruckCount = frameResults.filter((r) => !r.truck).length;

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Dust Detection (YOLOv8)
        </h2>

        {/* Step 1: Upload Video */}
        {!videoId && (
          <div className="space-y-2">
            <label className="font-semibold text-[12px] text-slate-300">Upload Video</label>
            <div className="flex gap-2">
              <label className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg cursor-pointer hover:bg-slate-600 transition-colors">
                <Upload size={14} />
                <span className="text-[12px] truncate">
                  {videoFile ? videoFile.name : "Select .mp4 file"}
                </span>
                <input
                  type="file"
                  accept=".mp4,.avi,.mov"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
              <button
                onClick={handleUpload}
                disabled={!videoFile || uploading}
                className={`px-3 py-2 rounded-lg text-[12px] font-medium transition-colors ${
                  !videoFile || uploading
                    ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {uploading ? `${uploadProgress}%` : "Upload"}
              </button>
            </div>
            {uploading && (
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <div className="bg-blue-500 h-1.5 transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Draw Polygon on First Frame */}
        {firstFrameUrl && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-[12px] text-slate-300">
                {isDrawing ? `Draw road polygon (${polygonPoints.length}/4 points)` : "Road polygon set"}
              </label>
              {polygonPoints.length > 0 && (
                <button
                  onClick={() => {
                    setPolygonPoints([]);
                    setIsDrawing(true);
                  }}
                  className="text-[11px] text-red-400 hover:text-red-300"
                >
                  Reset
                </button>
              )}
            </div>
            <canvas
              ref={canvasRef}
              onClick={handleCanvasClick}
              className={`w-full rounded border border-slate-600 ${isDrawing ? "cursor-crosshair" : "cursor-default"}`}
              style={{ maxHeight: "360px", objectFit: "contain" }}
            />
          </div>
        )}

        {/* Step 3: Start Analysis */}
        {videoId && polygonPoints.length === 4 && !isAnalyzing && !done && (
          <div className="pt-2">
            <button
              onClick={startAnalysis}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-red-700 text-white rounded-lg text-[13px] font-bold hover:bg-red-800 transition-colors shadow-lg"
            >
              <Play size={16} />
              Start Analysis
            </button>
          </div>
        )}

        {/* Real-time Chart */}
        {(isAnalyzing || done) && (
          <div className="space-y-2 mt-2">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-[12px] text-slate-300">
                {isAnalyzing ? (
                  <span className="flex items-center gap-1">
                    <Loader2 size={12} className="animate-spin" />
                    Processing...
                  </span>
                ) : (
                  "Detection Complete"
                )}
              </label>
              <span className="text-[11px] text-slate-400">
                {frameResults.length} frames
              </span>
            </div>

            {/* Chart */}
            <canvas
              ref={chartCanvasRef}
              width={700}
              height={180}
              className="w-full rounded border border-slate-600"
            />

            {/* Live Stats */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[18px] font-bold text-blue-400">{truckCount}</div>
                <div className="text-[10px] text-slate-400">Truck Frames</div>
              </div>
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[18px] font-bold text-slate-300">{noTruckCount}</div>
                <div className="text-[10px] text-slate-400">No Truck</div>
              </div>
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[18px] font-bold text-green-400">
                  {frameResults.length > 0 ? `${((truckCount / frameResults.length) * 100).toFixed(1)}%` : "—"}
                </div>
                <div className="text-[10px] text-slate-400">Truck %</div>
              </div>
            </div>
          </div>
        )}

        {/* Done Summary */}
        {done && (
          <div className="mt-2 bg-green-900/30 border border-green-700/50 rounded-lg p-3">
            <div className="text-[13px] font-semibold text-green-300 mb-1">Analysis Complete</div>
            <div className="text-[12px] text-slate-300">
              Processed {frameResults.length} frames. Truck detected in {truckCount} frames ({((truckCount / Math.max(frameResults.length, 1)) * 100).toFixed(1)}%).
            </div>
          </div>
        )}
      </div>
    </>
  );
}
