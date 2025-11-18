// app/components/DistressForms/corrugation.tsx
"use client";
import React, { useState } from "react";
import { FolderOpen, CheckSquare, Square } from "lucide-react";

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

export default function CorrugationForm() {
  const [polygonName, setPolygonName] = useState<string>("");
  const [demFile, setDemFile] = useState<File | null>(null);
  const [sampling, setSampling] = useState<number>(10);
  const [lineInterval, setLineInterval] = useState<number>(0.1);
  const [tryNeighbor, setTryNeighbor] = useState<boolean>(false);
  const [neighborRange, setNeighborRange] = useState<number>(2);
  const [smoothSigma, setSmoothSigma] = useState<number>(2);

  const numberBox =
    "w-24 border border-gray-300 rounded px-2 py-0.5 text-center text-[10px]";
  const browseBtn =
    "flex items-center gap-1 text-blue-600 hover:text-blue-800";

  const onPickDem = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!/\.(tif|tiff)$/i.test(f.name)) {
      alert("Only tif or tiff files are supported");
      return;
    }
    setDemFile(f);
  };

  return (
    <div className="w-full bg-gray-50 border rounded-lg shadow p-2 text-[11px] text-gray-800 leading-tight">
      <h2 className="text-[11px] font-bold border-b pb-1 mb-1.5 text-gray-700 text-center">
        Parameters
      </h2>

      <RowGrid
        label="Input polygon feature"
        control={
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              placeholder="feature name"
              value={polygonName}
              onChange={(e) => setPolygonName(e.target.value)}
              className="w-36 border border-gray-300 rounded px-2 py-0.5 text-[10px]"
            />
            <button className={browseBtn} type="button">
              <FolderOpen size={12} />
              <span className="text-[10px]">Browse</span>
            </button>
          </div>
        }
      />

      <RowGrid
        label="DEM raster file"
        control={
          <div className="flex items-center gap-1.5">
            <input
              id="dem-file"
              className="hidden"
              type="file"
              accept=".tif,.tiff"
              onChange={onPickDem}
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
        label="Sampling frequency per 100 pixels"
        control={
          <input
            type="number"
            value={sampling}
            onChange={(e) => setSampling(Number(e.target.value))}
            className={numberBox}
          />
        }
      />

      <RowGrid
        label="Line interval, meters"
        control={
          <input
            type="number"
            step="0.01"
            value={lineInterval}
            onChange={(e) => setLineInterval(Number(e.target.value))}
            className={numberBox}
          />
        }
      />

      <RowGrid
        label="Try neighboring sampling frequencies"
        control={
          <button
            type="button"
            onClick={() => setTryNeighbor((v) => !v)}
            className="flex items-center gap-1.5"
          >
            {tryNeighbor ? (
              <CheckSquare size={12} className="text-blue-600" />
            ) : (
              <Square size={12} className="text-gray-400" />
            )}
            <span className="text-[10px]">Toggle</span>
          </button>
        }
      />

      {tryNeighbor && (
        <RowGrid
          label="Neighbor range, plus or minus"
          control={
            <input
              type="number"
              value={neighborRange}
              onChange={(e) => setNeighborRange(Number(e.target.value))}
              className={numberBox}
            />
          }
        />
      )}

      <RowGrid
        label="Output plot, HTML"
        control={
          <button className={browseBtn} type="button">
            <FolderOpen size={12} />
            <span className="text-[10px]">Browse</span>
          </button>
        }
      />

      <RowGrid
        label="Smooth sigma, samples"
        control={
          <input
            type="number"
            value={smoothSigma}
            onChange={(e) => setSmoothSigma(Number(e.target.value))}
            className={numberBox}
          />
        }
      />

      <div className="pt-2 mt-1 border-t">
        <button className="bg-red-700 text-white font-bold py-1 px-2.5 rounded hover:bg-red-800 text-[11px] mx-auto block">
          Run analysis
        </button>
      </div>
    </div>
  );
}
