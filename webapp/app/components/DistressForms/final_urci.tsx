// app/components/DistressForms/final_urci.tsx
"use client";

import React, { useMemo, useState } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";

/**
 * Simple URCI (Unsurfaced Road Condition Index) calculator.
 *
 * The user enters a deduct value (DV) per distress + severity. We apply a
 * light-weight Army-Corps-style iterative CDV approximation, then report
 * URCI = 100 − CDV along with a condition band.
 *
 * Note: this is an approximation. For the exact value, use the IowaDOT
 * CDV curves with density + severity as inputs. The calculator here is
 * meant to match what most field users expect from a quick spreadsheet.
 */

const DISTRESSES = ["Rut", "Crown", "Corrugation", "Dust", "Potholes"] as const;
type Distress = (typeof DISTRESSES)[number];
const SEVERITIES = ["Low", "Medium", "High"] as const;
type Severity = (typeof SEVERITIES)[number];

type DeductTable = Record<Distress, Record<Severity, number>>;

const EMPTY_TABLE = (): DeductTable =>
  Object.fromEntries(
    DISTRESSES.map((d) => [d, { Low: 0, Medium: 0, High: 0 }])
  ) as DeductTable;

/**
 * Iterative CDV approximation.
 *   1. Collect DVs > 0, sort descending.
 *   2. In each round, compute a candidate CDV from the current list:
 *        q = count of DVs > 2
 *        cdv ≈ maxDV                        if q ≤ 1
 *        cdv ≈ maxDV + (total − maxDV) × k  otherwise, with k tapering off as q grows
 *   3. Reduce the smallest > 2 to 2 (or drop) and repeat.
 *   4. Final CDV = max candidate; URCI = max(0, 100 − CDV).
 */
function computeUrci(values: DeductTable): {
  urci: number;
  cdv: number;
  totalDV: number;
  maxDV: number;
  q: number;
  band: string;
  bandColor: string;
} {
  const flat: number[] = [];
  for (const d of DISTRESSES) {
    for (const s of SEVERITIES) {
      const v = Number(values[d][s]) || 0;
      if (v > 0) flat.push(v);
    }
  }

  if (flat.length === 0) {
    return { urci: 100, cdv: 0, totalDV: 0, maxDV: 0, q: 0, band: "Excellent", bandColor: "#16a34a" };
  }

  flat.sort((a, b) => b - a);
  const totalDV = flat.reduce((a, b) => a + b, 0);
  const maxDV = flat[0];
  const q = flat.filter((v) => v > 2).length;

  let maxCdv = 0;
  const working = [...flat];

  while (working.length > 0) {
    const wSum = working.reduce((a, b) => a + b, 0);
    const wMax = working[0];
    const wQ = working.filter((v) => v > 2).length;

    let candidate: number;
    if (wQ <= 1) {
      candidate = wMax;
    } else {
      // k starts at 0.85 for q=2 and decays with more minor distresses
      const k = Math.max(0.25, 0.85 - 0.1 * (wQ - 2));
      candidate = wMax + (wSum - wMax) * k;
    }
    if (candidate > maxCdv) maxCdv = candidate;

    // Reduce the smallest DV that is still > 2 down to 2, else drop it
    const lastIdx = working.length - 1;
    if (working[lastIdx] > 2) working[lastIdx] = 2;
    else working.pop();
  }

  const cdv = Math.min(100, maxCdv);
  const urci = Math.max(0, Math.min(100, 100 - cdv));

  const { band, bandColor } = conditionBand(urci);
  return { urci, cdv, totalDV, maxDV, q, band, bandColor };
}

function conditionBand(urci: number): { band: string; bandColor: string } {
  if (urci >= 85) return { band: "Excellent", bandColor: "#16a34a" };
  if (urci >= 70) return { band: "Good", bandColor: "#65a30d" };
  if (urci >= 55) return { band: "Fair", bandColor: "#eab308" };
  if (urci >= 40) return { band: "Poor", bandColor: "#f97316" };
  if (urci >= 25) return { band: "Very Poor", bandColor: "#dc2626" };
  return { band: "Failed", bandColor: "#7f1d1d" };
}

export default function FinalURCIForm() {
  const [values, setValues] = useState<DeductTable>(EMPTY_TABLE);
  const [computed, setComputed] = useState<ReturnType<typeof computeUrci> | null>(null);

  const hasAnyInput = useMemo(
    () =>
      DISTRESSES.some((d) =>
        SEVERITIES.some((s) => Number(values[d][s]) > 0)
      ),
    [values]
  );

  const setDv = (d: Distress, s: Severity, raw: string) => {
    const n = Math.max(0, Math.min(100, Number(raw) || 0));
    setValues((prev) => ({ ...prev, [d]: { ...prev[d], [s]: n } }));
  };

  const handleCompute = () => {
    setComputed(computeUrci(values));
  };

  const handleReset = () => {
    setValues(EMPTY_TABLE());
    setComputed(null);
  };

  const inputBox =
    "w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-right text-[12px] text-slate-100 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400";

  return (
    <div className="w-full bg-linear-to-b from-slate-800 to-slate-900 rounded-lg shadow-lg p-3 text-[13px] text-slate-100 leading-tight ring-1 ring-slate-700/50">
      <h2 className="text-[14px] font-bold border-b border-slate-700 pb-2 mb-3 text-slate-200 text-center">
        Final URCI
      </h2>

      <p className="text-[11px] text-slate-400 mb-2">
        Enter the deduct value (0–100) for each distress severity. URCI is
        estimated from the total/combined deduct.
      </p>

      <table className="w-full text-[12px] border-collapse">
        <thead>
          <tr className="text-slate-300">
            <th className="text-left font-semibold py-1 pr-2">Distress</th>
            {SEVERITIES.map((s) => (
              <th key={s} className="text-right font-semibold py-1 px-1">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DISTRESSES.map((d) => (
            <tr key={d} className="border-t border-slate-700/60">
              <td className="py-1 pr-2 font-medium text-slate-200">{d}</td>
              {SEVERITIES.map((s) => (
                <td key={s} className="py-1 px-1">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={values[d][s] || ""}
                    onChange={(e) => setDv(d, s, e.target.value)}
                    className={inputBox}
                    aria-label={`${d} ${s} deduct value`}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex gap-2 mt-3">
        <button
          onClick={handleCompute}
          disabled={!hasAnyInput}
          className="flex-1 py-2 px-3 bg-blue-600 text-white rounded-lg text-[12px] font-semibold hover:bg-blue-700 transition-colors shadow-lg disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed"
        >
          Calculate URCI
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-100 rounded-lg text-[12px] font-medium transition-colors"
          title="Clear all values"
        >
          <RotateCcw size={13} /> Reset
        </button>
      </div>

      {computed && (
        <div className="border-t border-slate-700 mt-3 pt-3">
          <div
            className="rounded-lg p-3 text-center"
            style={{
              backgroundColor: `${computed.bandColor}22`,
              border: `1px solid ${computed.bandColor}66`,
            }}
          >
            <div className="text-[11px] uppercase tracking-wide text-slate-400">
              Final URCI
            </div>
            <div
              className="text-[36px] font-extrabold leading-none mt-1"
              style={{ color: computed.bandColor }}
            >
              {computed.urci.toFixed(1)}
            </div>
            <div
              className="text-[12px] font-semibold mt-1"
              style={{ color: computed.bandColor }}
            >
              {computed.band}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mt-3 text-[11px]">
            <div className="text-slate-400">Total deduct (ΣDV):</div>
            <div className="text-right font-semibold text-slate-100">
              {computed.totalDV.toFixed(1)}
            </div>
            <div className="text-slate-400">Max single DV:</div>
            <div className="text-right font-semibold text-slate-100">
              {computed.maxDV.toFixed(1)}
            </div>
            <div className="text-slate-400">Distresses &gt; 2 (q):</div>
            <div className="text-right font-semibold text-slate-100">
              {computed.q}
            </div>
            <div className="text-slate-400">Corrected Deduct (CDV):</div>
            <div className="text-right font-semibold text-slate-100">
              {computed.cdv.toFixed(1)}
            </div>
          </div>

          <div className="flex items-start gap-2 mt-3 text-[10.5px] text-slate-400">
            <AlertCircle size={12} className="flex-shrink-0 mt-0.5" />
            <span>
              Approximation using an iterative CDV rule. For an exact URCI,
              cross-reference the IowaDOT CDV curves with density and
              severity per distress.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
