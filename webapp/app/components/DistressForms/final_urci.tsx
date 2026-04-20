// app/components/DistressForms/final_urci.tsx
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, RotateCcw, Save, Trash2 } from "lucide-react";
import { API_ENDPOINTS, fetchWithAuth } from "@/app/lib/api";

/**
 * Final URCI — manual calculator + saved history.
 *
 * Flow:
 *   1. User names the sample unit.
 *   2. User enters one deduct value per distress (read off the IowaDOT
 *      charts for the severity they observed).
 *   3. Total deduct (ΣDV) and q (count of DVs > 2) auto-compute.
 *   4. Reference CDV chart shows below; the user traces ΣDV × q to get CDV.
 *   5. User enters final URCI (100 − CDV) they read off the chart.
 *   6. Save persists sample_unit + DVs + q + total_dv + final_urci.
 */

// IowaDOT's seven gravel-road distresses.
const DISTRESSES = [
  "Improper Cross Section",
  "Inadequate Roadside Drainage",
  "Potholes",
  "Ruts",
  "Loose Aggregate",
  "Corrugations",
  "Dust",
] as const;
type Distress = (typeof DISTRESSES)[number];

type DeductMap = Record<Distress, number>;

const EMPTY_DV = (): DeductMap =>
  Object.fromEntries(DISTRESSES.map((d) => [d, 0])) as DeductMap;

interface URCIRecord {
  id: string;
  sample_unit: string;
  deduct_values: Record<string, number>;
  total_dv: number;
  q_value: number;
  final_urci: number;
  created_at: string;
}

// Reference images under webapp/public/urci/. Missing files are hidden.
const IMAGES: { file: string; caption: string }[] = [
  { file: "/urci/cdv_curve.png",          caption: "Corrected deduct value (CDV) chart" },
  { file: "/urci/deduct_rut.png",         caption: "Rut — deduct chart" },
  { file: "/urci/deduct_crown.png",       caption: "Improper cross section — deduct chart" },
  { file: "/urci/deduct_corrugation.png", caption: "Corrugations — deduct chart" },
  { file: "/urci/deduct_dust.png",        caption: "Dust — deduct chart" },
  { file: "/urci/deduct_pothole.png",     caption: "Potholes — deduct chart" },
  { file: "/urci/severity_classes.png",   caption: "Severity classification key" },
];

function conditionBand(urci: number): { band: string; color: string } {
  if (urci >= 85) return { band: "Excellent", color: "#16a34a" };
  if (urci >= 70) return { band: "Good", color: "#65a30d" };
  if (urci >= 55) return { band: "Fair", color: "#eab308" };
  if (urci >= 40) return { band: "Poor", color: "#f97316" };
  if (urci >= 25) return { band: "Very Poor", color: "#dc2626" };
  return { band: "Failed", color: "#7f1d1d" };
}

export default function FinalURCIForm() {
  const [sampleUnit, setSampleUnit] = useState("");
  const [dvs, setDvs] = useState<DeductMap>(EMPTY_DV);
  const [finalUrciInput, setFinalUrciInput] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [records, setRecords] = useState<URCIRecord[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [missing, setMissing] = useState<Set<string>>(new Set());

  // Derived: total deduct (ΣDV) and q (count of DVs > 2).
  const { totalDV, qValue } = useMemo(() => {
    let total = 0;
    let q = 0;
    for (const d of DISTRESSES) {
      const v = Number(dvs[d]) || 0;
      if (v > 0) total += v;
      if (v > 2) q += 1;
    }
    return { totalDV: total, qValue: q };
  }, [dvs]);

  const finalUrciNum = useMemo(() => {
    const n = parseFloat(finalUrciInput);
    if (!Number.isFinite(n)) return null;
    return Math.max(0, Math.min(100, n));
  }, [finalUrciInput]);

  const loadRecords = useCallback(async () => {
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.URCI.LIST);
      if (res.ok) setRecords(await res.json());
    } catch (e) {
      console.error("Failed to list URCI records:", e);
    } finally {
      setLoadingRecords(false);
    }
  }, []);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const handleSetDv = (d: Distress, raw: string) => {
    const n = Math.max(0, Math.min(100, Number(raw) || 0));
    setDvs((prev) => ({ ...prev, [d]: n }));
  };

  const handleReset = () => {
    setSampleUnit("");
    setDvs(EMPTY_DV());
    setFinalUrciInput("");
    setNotes("");
    setFlash(null);
  };

  const handleSave = async () => {
    if (!sampleUnit.trim()) {
      setFlash({ kind: "err", text: "Sample unit name is required." });
      return;
    }
    if (finalUrciNum === null) {
      setFlash({ kind: "err", text: "Enter the final URCI value from the chart." });
      return;
    }
    setSaving(true);
    setFlash(null);
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.URCI.CREATE, {
        method: "POST",
        body: JSON.stringify({
          sample_unit: sampleUnit.trim(),
          deduct_values: dvs,
          total_dv: totalDV,
          q_value: qValue,
          final_urci: finalUrciNum,
          notes: notes.trim() || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Save failed (${res.status})`);
      }
      const saved: URCIRecord = await res.json();
      setRecords((prev) => [saved, ...prev]);
      setFlash({ kind: "ok", text: `Saved "${saved.sample_unit}" — URCI ${saved.final_urci.toFixed(1)}` });
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRecord = async (id: string, name: string) => {
    if (!confirm(`Delete URCI record "${name}"?`)) return;
    try {
      const res = await fetchWithAuth(API_ENDPOINTS.URCI.DELETE(id), { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        throw new Error(`Delete failed (${res.status})`);
      }
      setRecords((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Delete failed" });
    }
  };

  const band = finalUrciNum !== null ? conditionBand(finalUrciNum) : null;

  const inputBox =
    "w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-[12px] text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400";
  const numBox = `${inputBox} text-right`;

  return (
    <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
      <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
        Final URCI
      </h2>

      {/* Sample unit + deduct inputs */}
      <label className="block text-[11px] font-semibold text-slate-300 mb-1">
        Sample unit name
      </label>
      <input
        type="text"
        value={sampleUnit}
        onChange={(e) => setSampleUnit(e.target.value)}
        placeholder="e.g. 150th St — Section A"
        className={inputBox}
      />

      <div className="mt-3">
        <div className="text-[11px] font-semibold text-slate-300 mb-1">
          Deduct values (from manual)
        </div>
        <table className="w-full text-[12px] border-collapse">
          <tbody>
            {DISTRESSES.map((d) => (
              <tr key={d} className="border-t border-slate-700/60">
                <td className="py-1 pr-2 text-slate-200">{d}</td>
                <td className="py-1 pl-1" style={{ width: "5.5rem" }}>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={dvs[d] || ""}
                    onChange={(e) => handleSetDv(d, e.target.value)}
                    className={numBox}
                    aria-label={`${d} deduct value`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Auto ΣDV + q */}
      <div className="grid grid-cols-2 gap-2 mt-3 text-[12px]">
        <div className="bg-slate-800 border border-slate-700 rounded p-2">
          <div className="text-[10px] uppercase tracking-wide text-slate-400">Total deduct (ΣDV)</div>
          <div className="text-[18px] font-bold text-slate-100 mt-0.5">{totalDV.toFixed(1)}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded p-2">
          <div className="text-[10px] uppercase tracking-wide text-slate-400">q (DVs &gt; 2)</div>
          <div className="text-[18px] font-bold text-slate-100 mt-0.5">{qValue}</div>
        </div>
      </div>

      {/* Reference charts */}
      {IMAGES.some((img) => !missing.has(img.file)) && (
        <div className="border-t border-slate-700 mt-3 pt-3">
          <div className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">
            Reference charts — trace ΣDV × q → CDV
          </div>
          <div className="grid grid-cols-2 gap-2">
            {IMAGES.map(({ file, caption }) =>
              missing.has(file) ? null : (
                <figure key={file} className="m-0 min-w-0">
                  <img
                    src={file}
                    alt={caption}
                    className="w-full h-auto max-h-40 object-contain rounded border border-slate-700 bg-slate-900"
                    onError={() =>
                      setMissing((prev) => {
                        if (prev.has(file)) return prev;
                        const next = new Set(prev);
                        next.add(file);
                        return next;
                      })
                    }
                  />
                  <figcaption className="text-[10px] text-slate-400 text-center mt-1">
                    {caption}
                  </figcaption>
                </figure>
              )
            )}
          </div>
        </div>
      )}

      {/* Final URCI input + save */}
      <div className="border-t border-slate-700 mt-3 pt-3">
        <label className="block text-[11px] font-semibold text-slate-300 mb-1">
          Final URCI value (read from chart)
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            max={100}
            step={0.1}
            value={finalUrciInput}
            onChange={(e) => setFinalUrciInput(e.target.value)}
            placeholder="0 – 100"
            className={`${numBox} flex-1`}
          />
          {band && (
            <div
              className="px-2 py-1 rounded text-[12px] font-bold"
              style={{ backgroundColor: `${band.color}22`, color: band.color, border: `1px solid ${band.color}66` }}
            >
              {band.band}
            </div>
          )}
        </div>

        <label className="block text-[11px] font-semibold text-slate-300 mt-3 mb-1">
          Notes (optional)
        </label>
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="weather, surveyor, etc."
          className={inputBox}
        />

        <div className="flex gap-2 mt-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[12px] font-semibold transition-colors shadow-lg disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed"
          >
            <Save size={13} /> {saving ? "Saving..." : "Save URCI"}
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-100 rounded-lg text-[12px] font-medium transition-colors"
            title="Clear all fields"
          >
            <RotateCcw size={13} /> Reset
          </button>
        </div>

        {flash && (
          <div
            className={`flex items-start gap-2 mt-2 p-2 rounded-lg text-[11px] ${
              flash.kind === "ok"
                ? "bg-emerald-900/30 border border-emerald-700/60 text-emerald-200"
                : "bg-red-900/30 border border-red-700/60 text-red-200"
            }`}
          >
            <AlertCircle size={12} className="flex-shrink-0 mt-0.5" />
            <span>{flash.text}</span>
          </div>
        )}
      </div>

      {/* Saved history */}
      <div className="border-t border-slate-700 mt-3 pt-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400">
            Saved URCI records
          </div>
          <div className="text-[10px] text-slate-500">{records.length}</div>
        </div>
        {loadingRecords ? (
          <div className="text-[11px] text-slate-400">Loading…</div>
        ) : records.length === 0 ? (
          <div className="text-[11px] text-slate-500 italic">No records yet.</div>
        ) : (
          <ul className="space-y-1 max-h-40 overflow-y-auto pr-1">
            {records.map((r) => {
              const rBand = conditionBand(r.final_urci);
              return (
                <li
                  key={r.id}
                  className="flex items-center gap-2 bg-slate-800/60 border border-slate-700 rounded px-2 py-1.5"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-semibold text-slate-100 truncate">
                      {r.sample_unit}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      ΣDV {r.total_dv.toFixed(1)} · q {r.q_value} ·{" "}
                      {new Date(r.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div
                    className="px-2 py-0.5 rounded text-[11px] font-bold"
                    style={{
                      backgroundColor: `${rBand.color}22`,
                      color: rBand.color,
                      border: `1px solid ${rBand.color}66`,
                    }}
                  >
                    {r.final_urci.toFixed(1)}
                  </div>
                  <button
                    onClick={() => handleDeleteRecord(r.id, r.sample_unit)}
                    className="p-1 text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded"
                    title="Delete record"
                    aria-label={`Delete ${r.sample_unit}`}
                  >
                    <Trash2 size={12} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
