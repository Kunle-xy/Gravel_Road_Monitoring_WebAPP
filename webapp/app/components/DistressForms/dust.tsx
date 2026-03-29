// app/components/DistressForms/dust.tsx
"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import { Upload, Play, AlertCircle, Loader2 } from "lucide-react";
import { fetchWithAuth, API_ENDPOINTS, WS_URL } from "@/app/lib/api";

interface FrameResult {
  frame: number;
  time: number;
  truck: boolean;
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
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // First frame for polygon drawing
  const [firstFrameUrl, setFirstFrameUrl] = useState<string | null>(null);
  const [polygonPoints, setPolygonPoints] = useState<number[][]>([]);
  const [isDrawing, setIsDrawing] = useState(true);

  // Video playback
  const [videoPlayUrl, setVideoPlayUrl] = useState<string | null>(null);
  const [fps, setFps] = useState(30);
  const [videoDuration, setVideoDuration] = useState(0);

  // Analysis
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [frameResults, setFrameResults] = useState<FrameResult[]>([]);
  const [totalFrames, setTotalFrames] = useState(0);
  const [done, setDone] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const chartCanvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoContainerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const animFrameRef = useRef<number>(0);

  const showToast = (message: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  // --- Upload ---
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
    setVideoPlayUrl(null);
    setPolygonPoints([]);
    setFrameResults([]);
    setDone(false);
    setIsDrawing(true);
  };

  const handleUpload = async () => {
    if (!videoFile) return;
    setUploading(true);
    setUploadProgress(0);

    try {
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

      const completeRes = await fetchWithAuth(API_ENDPOINTS.DUST.VIDEO_COMPLETE(video_id), {
        method: "POST",
      });
      if (!completeRes.ok) throw new Error("Failed to complete upload");
      const videoData = await completeRes.json();

      setVideoId(video_id);
      setTotalFrames(videoData.total_frames || 0);
      setFps(videoData.fps || 30);
      setVideoDuration(videoData.duration_seconds || 0);
      showToast("Video uploaded!", "success");

      // Create a local object URL for video playback (from the file the user already has)
      setVideoPlayUrl(URL.createObjectURL(videoFile));

      // Fetch first frame for polygon drawing
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

  // --- Polygon Drawing (cyan + visible dots) ---
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
      // Cyan polygon
      ctx.strokeStyle = "#00ffff";
      ctx.lineWidth = 3;
      ctx.fillStyle = "rgba(0, 255, 255, 0.15)";

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

      // Vertex dots — large, bright green with white outline
      polygonPoints.forEach((pt, i) => {
        // Outer glow
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 12, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 255, 0, 0.3)";
        ctx.fill();

        // Inner dot
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 8, 0, Math.PI * 2);
        ctx.fillStyle = "#00ff00";
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;
        ctx.stroke();

        // Label
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 16px sans-serif";
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = 3;
        ctx.strokeText(`${i + 1}`, pt[0] + 14, pt[1] - 14);
        ctx.fillText(`${i + 1}`, pt[0] + 14, pt[1] - 14);
      });
    }

    // Instructions
    if (polygonPoints.length < 4 && isDrawing) {
      const labels = ["Click TOP-LEFT corner", "Click TOP-RIGHT corner", "Click BOTTOM-RIGHT corner", "Click BOTTOM-LEFT corner"];
      ctx.fillStyle = "rgba(0,0,0,0.8)";
      const textWidth = ctx.measureText(labels[polygonPoints.length]).width;
      ctx.fillRect(10, 10, Math.max(textWidth + 30, 300), 36);
      ctx.fillStyle = "#00ffff";
      ctx.font = "bold 18px sans-serif";
      ctx.fillText(labels[polygonPoints.length], 20, 35);
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

  useEffect(() => { drawCanvas(); }, [polygonPoints, drawCanvas]);

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
    if (newPoints.length === 4) setIsDrawing(false);
  };

  // --- Draw polygon overlay on video ---
  const drawVideoOverlay = useCallback(() => {
    const overlay = overlayCanvasRef.current;
    const video = videoRef.current;
    const container = videoContainerRef.current;
    if (!overlay || !video || !container || polygonPoints.length !== 4) return;

    // Match overlay to video display size
    const rect = video.getBoundingClientRect();
    overlay.width = rect.width;
    overlay.height = rect.height;
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;

    const ctx = overlay.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, overlay.width, overlay.height);

    // Scale polygon points from original video resolution to display size
    const scaleX = rect.width / (video.videoWidth || 1);
    const scaleY = rect.height / (video.videoHeight || 1);

    const scaledPoints = polygonPoints.map(([x, y]) => [x * scaleX, y * scaleY]);

    // Cyan polygon
    ctx.strokeStyle = "#00ffff";
    ctx.lineWidth = 2;
    ctx.fillStyle = "rgba(0, 255, 255, 0.12)";

    ctx.beginPath();
    ctx.moveTo(scaledPoints[0][0], scaledPoints[0][1]);
    for (let i = 1; i < scaledPoints.length; i++) {
      ctx.lineTo(scaledPoints[i][0], scaledPoints[i][1]);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Vertex dots
    scaledPoints.forEach((pt) => {
      ctx.beginPath();
      ctx.arc(pt[0], pt[1], 5, 0, Math.PI * 2);
      ctx.fillStyle = "#00ff00";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  }, [polygonPoints]);

  // Redraw overlay when video resizes or loads
  useEffect(() => {
    if (!isAnalyzing && !done) return;
    const video = videoRef.current;
    if (!video) return;

    const onLoaded = () => drawVideoOverlay();
    video.addEventListener("loadeddata", onLoaded);
    video.addEventListener("resize", drawVideoOverlay);

    // Also draw after a short delay to handle layout shifts
    const timer = setTimeout(drawVideoOverlay, 200);

    return () => {
      video.removeEventListener("loadeddata", onLoaded);
      video.removeEventListener("resize", drawVideoOverlay);
      clearTimeout(timer);
    };
  }, [isAnalyzing, done, drawVideoOverlay]);

  // --- Chart with time-synced cursor ---
  const drawChart = useCallback((currentTime?: number) => {
    const canvas = chartCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    const pad = { top: 20, right: 20, bottom: 30, left: 70 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left + plotW, pad.top);
    ctx.moveTo(pad.left, pad.top + plotH);
    ctx.lineTo(pad.left + plotW, pad.top + plotH);
    // Middle dashed line
    ctx.setLineDash([4, 4]);
    ctx.moveTo(pad.left, pad.top + plotH / 2);
    ctx.lineTo(pad.left + plotW, pad.top + plotH / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Y-axis labels
    ctx.fillStyle = "#94a3b8";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("Truck", pad.left - 10, pad.top + 14);
    ctx.fillText("No Truck", pad.left - 10, pad.top + plotH + 4);

    // X-axis label
    ctx.textAlign = "center";
    ctx.fillText("Time (s)", pad.left + plotW / 2, h - 5);

    if (frameResults.length === 0) return;

    const maxTime = videoDuration > 0 ? videoDuration : (frameResults[frameResults.length - 1]?.time || 10);
    const xScale = plotW / maxTime;

    // Plot line — cyan to match polygon
    ctx.strokeStyle = "#00ffff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    frameResults.forEach((r, i) => {
      const x = pad.left + r.time * xScale;
      const y = r.truck ? pad.top + 6 : pad.top + plotH - 6;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill under truck
    ctx.fillStyle = "rgba(0, 255, 255, 0.08)";
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top + plotH);
    frameResults.forEach((r) => {
      const x = pad.left + r.time * xScale;
      const y = r.truck ? pad.top + 6 : pad.top + plotH - 6;
      ctx.lineTo(x, y);
    });
    const lastX = pad.left + frameResults[frameResults.length - 1].time * xScale;
    ctx.lineTo(lastX, pad.top + plotH);
    ctx.closePath();
    ctx.fill();

    // Cursor line synced to video playback
    if (currentTime !== undefined && currentTime >= 0) {
      const cx = pad.left + currentTime * xScale;
      if (cx >= pad.left && cx <= pad.left + plotW) {
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx, pad.top);
        ctx.lineTo(cx, pad.top + plotH);
        ctx.stroke();

        // Time label on cursor
        ctx.fillStyle = "#f97316";
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(`${currentTime.toFixed(1)}s`, cx, pad.top - 4);
      }
    }

    // Stats in bottom-left
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "left";
    ctx.font = "11px sans-serif";
    ctx.fillText(`Processed: ${frameResults.length} samples`, pad.left + 4, h - 5);
  }, [frameResults, videoDuration]);

  // Animate chart cursor with video playback + keep overlay in sync
  useEffect(() => {
    if (!isAnalyzing && !done) return;

    const animate = () => {
      const video = videoRef.current;
      drawChart(video ? video.currentTime : undefined);
      drawVideoOverlay();
      animFrameRef.current = requestAnimationFrame(animate);
    };
    animFrameRef.current = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(animFrameRef.current);
  }, [isAnalyzing, done, drawChart]);

  // --- Start Analysis + WebSocket ---
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
      showToast("Analysis started!", "info");

      // Start video playback
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
        videoRef.current.play();
      }

      // Open WebSocket
      const wsUrl = `${WS_URL}/${API_ENDPOINTS.DUST.WS(job.id)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.done) {
          setDone(true);
          setIsAnalyzing(false);
          if (videoRef.current) videoRef.current.pause();
          showToast(`Complete! ${data.total_frames} frames processed.`, "success");
          ws.close();
          return;
        }
        if (data.error) {
          setIsAnalyzing(false);
          if (videoRef.current) videoRef.current.pause();
          showToast(data.error, "error");
          ws.close();
          return;
        }

        setFrameResults((prev) => [...prev, {
          frame: data.frame,
          time: data.time || (data.frame / fps),
          truck: data.truck,
        }]);
      };

      ws.onerror = () => {
        showToast("WebSocket connection error", "error");
        setIsAnalyzing(false);
      };
      ws.onclose = () => { wsRef.current = null; };
    } catch (err) {
      setIsAnalyzing(false);
      showToast(err instanceof Error ? err.message : "Failed to start", "error");
    }
  };

  useEffect(() => { return () => { wsRef.current?.close(); }; }, []);

  const truckCount = frameResults.filter((r) => r.truck).length;
  const noTruckCount = frameResults.filter((r) => !r.truck).length;

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-4 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
        <h2 className="text-[15px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
          Dust Detection (YOLOv8)
        </h2>

        {/* Step 1: Upload */}
        {!videoId && (
          <div className="space-y-2">
            <label className="font-semibold text-[12px] text-slate-300">Upload Video</label>
            <div className="flex gap-2">
              <label className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 bg-slate-700 border border-slate-600 border-dashed rounded-lg cursor-pointer hover:bg-slate-600 transition-colors">
                <Upload size={16} />
                <span className="text-[12px] truncate">
                  {videoFile ? videoFile.name : "Select .mp4 video file"}
                </span>
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
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <div className="bg-blue-500 h-1.5 transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Draw Polygon */}
        {firstFrameUrl && !isAnalyzing && !done && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-[12px] text-slate-300">
                {isDrawing ? `Select road boundary (${polygonPoints.length}/4)` : "Road boundary set"}
              </label>
              {polygonPoints.length > 0 && (
                <button
                  onClick={() => { setPolygonPoints([]); setIsDrawing(true); }}
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
              style={{ maxHeight: "380px", objectFit: "contain" }}
            />
          </div>
        )}

        {/* Step 3: Start */}
        {videoId && polygonPoints.length === 4 && !isAnalyzing && !done && (
          <div className="pt-3">
            <button
              onClick={startAnalysis}
              className="w-full flex items-center justify-center gap-2 px-3 py-3 bg-red-700 text-white rounded-lg text-[14px] font-bold hover:bg-red-800 transition-colors shadow-lg"
            >
              <Play size={18} />
              Start Analysis
            </button>
          </div>
        )}

        {/* Video Player + Chart (shown during/after analysis) */}
        {(isAnalyzing || done) && (
          <div className="space-y-3 mt-2">
            {/* Video Player */}
            {videoPlayUrl && (
              <div ref={videoContainerRef} className="relative">
                <video
                  ref={videoRef}
                  src={videoPlayUrl}
                  className="w-full rounded border border-slate-600"
                  style={{ maxHeight: "360px" }}
                  muted
                  playsInline
                  controls
                />
                {/* Polygon overlay on top of video */}
                <canvas
                  ref={overlayCanvasRef}
                  className="absolute top-0 left-0 pointer-events-none"
                  style={{ maxHeight: "360px" }}
                />
                {isAnalyzing && (
                  <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-red-600/90 px-2 py-1 rounded text-[11px] font-bold text-white">
                    <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
                    LIVE
                  </div>
                )}
              </div>
            )}

            {/* Chart */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="font-semibold text-[12px] text-slate-300">
                  {isAnalyzing ? (
                    <span className="flex items-center gap-1">
                      <Loader2 size={12} className="animate-spin" />
                      Detecting vehicles...
                    </span>
                  ) : "Detection Results"}
                </label>
                <span className="text-[11px] text-slate-400">
                  {frameResults.length} samples
                </span>
              </div>
              <canvas
                ref={chartCanvasRef}
                width={700}
                height={180}
                className="w-full rounded border border-slate-600"
              />
            </div>

            {/* Live Stats */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[20px] font-bold text-cyan-400">{truckCount}</div>
                <div className="text-[10px] text-slate-400">Truck Detected</div>
              </div>
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[20px] font-bold text-slate-300">{noTruckCount}</div>
                <div className="text-[10px] text-slate-400">No Truck</div>
              </div>
              <div className="bg-slate-700/50 rounded p-2">
                <div className="text-[20px] font-bold text-green-400">
                  {frameResults.length > 0 ? `${((truckCount / frameResults.length) * 100).toFixed(1)}%` : "—"}
                </div>
                <div className="text-[10px] text-slate-400">Detection Rate</div>
              </div>
            </div>

            {/* Done */}
            {done && (
              <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-3">
                <div className="text-[13px] font-semibold text-green-300 mb-1">Analysis Complete</div>
                <div className="text-[12px] text-slate-300">
                  Processed {frameResults.length} samples. Vehicle detected in {truckCount} ({((truckCount / Math.max(frameResults.length, 1)) * 100).toFixed(1)}%).
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
