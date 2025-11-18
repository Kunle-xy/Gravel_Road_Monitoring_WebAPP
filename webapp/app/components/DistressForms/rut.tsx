// app/components/DistressForms/rut.tsx
"use client";
import React, { useState } from "react";
import { FolderOpen, CheckSquare, Square, AlertCircle } from "lucide-react";

function RowGrid({
  label,
  control,
}: {
  label: React.ReactNode;
  control: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-2 py-0.5">
      <label className="font-bold text-[11px] text-gray-800">{label}</label>
      <div className="flex items-center">{control}</div>
    </div>
  );
}

function CheckboxToggle({
  checked,
  onChange,
  label,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-1.5"
      aria-label={ariaLabel}
      aria-checked={checked}
      role="checkbox"
    >
      {checked ? (
        <CheckSquare size={12} className="text-blue-600" />
      ) : (
        <Square size={12} className="text-gray-400" />
      )}
      {label && <span className="text-[10px]">{label}</span>}
    </button>
  );
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
          className={`flex items-center gap-2 px-3 py-2 rounded shadow-lg text-white text-[11px] ${
            toast.type === "error"
              ? "bg-red-600"
              : toast.type === "success"
              ? "bg-green-600"
              : "bg-blue-600"
          }`}
        >
          <AlertCircle size={14} />
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}

export default function RutForm() {
  const [demFile, setDemFile] = useState<File | null>(null);
  const [orthophotoFile, setOrthophotoFile] = useState<File | null>(null);
  const [inputPolygonFile, setInputPolygonFile] = useState<File | null>(null);
  const [outputPlotPath, setOutputPlotPath] = useState("");
  const [outputDistressPath, setOutputDistressPath] = useState("");
  const [sampling, setSampling] = useState(3);
  const [ruttingWidth, setRuttingWidth] = useState(0.1);
  const [neighborRange, setNeighborRange] = useState(2);
  const [gaussian, setGaussian] = useState(false);
  const [sigma, setSigma] = useState(1);
  const [tryNeighbor, setTryNeighbor] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const inputBox =
    "w-24 border border-gray-300 rounded px-2 py-0.5 text-center text-[10px]";

  const showToast = (message: string, type: Toast["type"] = "error") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const handleFileChange = (
    event: React.ChangeEvent<HTMLInputElement>,
    type: "dem" | "ortho" | "polygon"
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (type === "polygon") {
      // Accept shapefiles and geojson for polygon features
      if (!file.name.match(/\.(shp|geojson|json)$/i)) {
        showToast("Only .shp, .geojson, or .json files are supported for polygon features");
        return;
      }
      setInputPolygonFile(file);
    } else {
      if (!file.name.match(/\.(tif|tiff)$/i)) {
        showToast("Only .tif or .tiff files are supported");
        return;
      }
      if (type === "dem") setDemFile(file);
      else setOrthophotoFile(file);
    }
  };

  const handleOutputPathChange = (type: "plot" | "distress") => {
    // In a real application, this would open a file save dialog
    // For now, we'll simulate it with a prompt
    const path = prompt(
      `Enter output path for ${type === "plot" ? "HTML plot" : "distress features"}:`,
      type === "plot" ? "output_plot.html" : "output_distress.shp"
    );
    if (path) {
      if (type === "plot") setOutputPlotPath(path);
      else setOutputDistressPath(path);
    }
  };

  const validateForm = (): boolean => {
    if (!inputPolygonFile) {
      showToast("Please select an input polygon feature file");
      return false;
    }
    if (!demFile) {
      showToast("Please select a DEM raster file");
      return false;
    }
    if (!orthophotoFile) {
      showToast("Please select an orthophoto raster file");
      return false;
    }
    if (sampling <= 0) {
      showToast("Sampling frequency must be greater than 0");
      return false;
    }
    if (ruttingWidth <= 0) {
      showToast("Rutting width must be greater than 0");
      return false;
    }
    if (tryNeighbor && neighborRange <= 0) {
      showToast("Neighbor range must be greater than 0");
      return false;
    }
    if (gaussian && sigma <= 0) {
      showToast("Gaussian sigma must be greater than 0");
      return false;
    }
    if (!outputPlotPath) {
      showToast("Please specify an output path for the HTML plot");
      return false;
    }
    if (!outputDistressPath) {
      showToast("Please specify an output path for distress features");
      return false;
    }
    return true;
  };

  const handleRunAnalysis = async () => {
    if (!validateForm()) return;

    setIsAnalyzing(true);
    try {
      // TODO: Implement actual analysis API call
      // For now, simulate processing
      showToast("Analysis started...", "info");

      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 2000));

      showToast("Analysis completed successfully!", "success");

      // Here you would typically:
      // 1. Create FormData with all files and parameters
      // 2. POST to your backend API endpoint
      // 3. Handle the response and download results

    } catch (error) {
      showToast(
        error instanceof Error ? error.message : "Analysis failed",
        "error"
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <>
      <ToastContainer toasts={toasts} />
      <div className="w-full bg-gray-50 border rounded-lg shadow p-2 text-[11px] text-gray-800 leading-tight">
        <h2 className="text-[11px] font-bold border-b pb-1 mb-1.5 text-gray-700 text-center">
          Parameters
        </h2>

        <RowGrid
          label="Input polygon feature"
          control={
            <div className="flex items-center gap-1.5">
              <input
                type="file"
                accept=".shp,.geojson,.json"
                className="hidden"
                id="polygon-file"
                onChange={(e) => handleFileChange(e, "polygon")}
                aria-label="Select polygon feature file"
              />
              <label
                htmlFor="polygon-file"
                className="flex items-center gap-1 text-blue-600 hover:text-blue-800 cursor-pointer"
              >
                <FolderOpen size={12} />
                <span className="text-[10px]">
                  {inputPolygonFile ? inputPolygonFile.name : "Browse"}
                </span>
              </label>
            </div>
          }
        />

      <RowGrid
        label="DEM raster file"
        control={
          <div className="flex items-center gap-1.5">
            <input
              type="file"
              accept=".tif,.tiff"
              className="hidden"
              id="dem-file"
              onChange={(e) => handleFileChange(e, "dem")}
              aria-label="Select DEM raster file"
            />
            <label
              htmlFor="dem-file"
              className="flex items-center gap-1 text-blue-600 hover:text-blue-800 cursor-pointer"
            >
              <FolderOpen size={12} />
              <span className="text-[10px]">
                {demFile ? demFile.name : "Browse"}
              </span>
            </label>
          </div>
        }
      />

      <RowGrid
        label="Orthophoto raster file"
        control={
          <div className="flex items-center gap-1.5">
            <input
              type="file"
              accept=".tif,.tiff"
              className="hidden"
              id="ortho-file"
              onChange={(e) => handleFileChange(e, "ortho")}
              aria-label="Select orthophoto raster file"
            />
            <label
              htmlFor="ortho-file"
              className="flex items-center gap-1 text-blue-600 hover:text-blue-800 cursor-pointer"
            >
              <FolderOpen size={12} />
              <span className="text-[10px]">
                {orthophotoFile ? orthophotoFile.name : "Browse"}
              </span>
            </label>
          </div>
        }
      />

      <RowGrid
        label="Sampling frequency per 100 pixels"
        control={
          <input
            type="number"
            min="0.1"
            step="0.1"
            value={sampling}
            onChange={(e) => setSampling(Number(e.target.value))}
            className={inputBox}
            aria-label="Sampling frequency per 100 pixels"
          />
        }
      />

      <RowGrid
        label="Rutting width, dx in meters"
        control={
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={ruttingWidth}
            onChange={(e) => setRuttingWidth(Number(e.target.value))}
            className={inputBox}
            aria-label="Rutting width in meters"
          />
        }
      />

      <RowGrid
        label="Try neighboring sampling frequencies"
        control={
          <CheckboxToggle
            checked={tryNeighbor}
            onChange={setTryNeighbor}
            label="Toggle"
            ariaLabel="Try neighboring sampling frequencies"
          />
        }
      />

      {tryNeighbor && (
        <RowGrid
          label="Neighbor range, plus or minus"
          control={
            <input
              type="number"
              min="1"
              step="1"
              value={neighborRange}
              onChange={(e) => setNeighborRange(Number(e.target.value))}
              className={inputBox}
              aria-label="Neighbor range"
            />
          }
        />
      )}

      <RowGrid
        label="Output plot, HTML"
        control={
          <button
            type="button"
            onClick={() => handleOutputPathChange("plot")}
            className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
            aria-label="Select output path for HTML plot"
          >
            <FolderOpen size={12} />
            <span className="text-[10px]">
              {outputPlotPath || "Browse"}
            </span>
          </button>
        }
      />

      <RowGrid
        label="Output distress line features"
        control={
          <button
            type="button"
            onClick={() => handleOutputPathChange("distress")}
            className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
            aria-label="Select output path for distress features"
          >
            <FolderOpen size={12} />
            <span className="text-[10px]">
              {outputDistressPath || "Browse"}
            </span>
          </button>
        }
      />

      <RowGrid
        label="Apply Gaussian smoothing to DEM before analysis"
        control={
          <CheckboxToggle
            checked={gaussian}
            onChange={setGaussian}
            label="Toggle"
            ariaLabel="Apply Gaussian smoothing to DEM"
          />
        }
      />

      {gaussian && (
        <RowGrid
          label="Gaussian sigma, pixels"
          control={
            <input
              type="number"
              min="0.1"
              step="0.1"
              value={sigma}
              onChange={(e) => setSigma(Number(e.target.value))}
              className={inputBox}
              aria-label="Gaussian sigma in pixels"
            />
          }
        />
      )}

        <div className="pt-2 mt-1 border-t">
          <button
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
            className={`font-bold py-1 px-2.5 rounded text-[11px] mx-auto block ${
              isAnalyzing
                ? "bg-gray-400 text-gray-700 cursor-not-allowed"
                : "bg-red-700 text-white hover:bg-red-800"
            }`}
          >
            {isAnalyzing ? "Analyzing..." : "Run analysis"}
          </button>
        </div>
      </div>
    </>
  );
}
