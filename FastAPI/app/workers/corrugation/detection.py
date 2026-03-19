"""
Corrugation detection algorithms.

Detects corrugation (wave-like surface distortion) in elevation profiles by:
1. Gaussian smoothing the elevation signal
2. Tracking UP/DOWN trend transitions to find peaks and valleys
3. Computing drop depth (interpolated crest to valley) in inches
4. Classifying severity: Low (<1"), Medium (1-3"), High (>3")

Also handles polygon-wide analysis with horizontal transect sampling.
"""

import logging
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
from shapely.geometry import Polygon, LineString
from rasterio.transform import rowcol

logger = logging.getLogger(__name__)

M_TO_IN = 39.3701
M2_TO_FT2 = 10.7639


def smooth_gaussian(x: np.ndarray, sigma_samples: float) -> np.ndarray:
    """
    Gaussian smooth an array preserving length.
    Uses scipy if available, otherwise a mirror-padded convolution fallback.
    """
    x = np.asarray(x, dtype=float)
    if sigma_samples is None or sigma_samples <= 0 or x.size == 0:
        return x.copy()
    try:
        from scipy.ndimage import gaussian_filter1d
        return gaussian_filter1d(x, sigma=float(sigma_samples), mode="nearest", truncate=3.0)
    except Exception:
        win = int(max(3, round(6.0 * float(sigma_samples))))
        if win % 2 == 0:
            win += 1
        half = win // 2
        if half > 0 and x.size > 1:
            left = x[1:half + 1][::-1]
            right = x[-half - 1:-1][::-1]
        else:
            left = right = x[:0]
        ypad = np.concatenate([left, x, right])
        t = np.arange(-half, half + 1, dtype=float)
        k = np.exp(-(t ** 2) / (2.0 * sigma_samples ** 2))
        k /= k.sum()
        y = np.convolve(ypad, k, mode="valid")
        return y[:x.shape[0]]


def detect_corrugations_trend(
    section: np.ndarray,
    depth_m: np.ndarray,
    dx_m: float,
    sigma_samples: float = 2.0
) -> Tuple[pd.DataFrame, np.ndarray, List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Detect corrugations in an elevation profile using trend analysis.

    Returns:
        df: DataFrame with section, depth_m, drop_in, severity
        y_smooth: smoothed elevation array
        peaks: list of (index, value) tuples
        valleys: list of (index, value) tuples
    """
    y = smooth_gaussian(depth_m.astype(float), sigma_samples=sigma_samples)
    n = len(y)

    trend = ['UP' if y[i] > y[i - 1] else 'DOWN' for i in range(1, n)]

    sev_str = ["NO CORRUGATION"] * n
    amp_in = np.zeros(n, dtype=float)
    peaks = []
    valleys = []

    index = 0
    while index < len(trend) - 1:
        if trend[index] == 'UP' and trend[index + 1] == 'DOWN':
            left_peak_idx = index + 1
            peaks.append((left_peak_idx, float(y[left_peak_idx])))

            j = index + 1
            while j < len(trend) and trend[j] == 'DOWN':
                j += 1
            if j >= len(trend) or trend[j] != 'UP':
                index += 1
                continue

            k = j
            while k < len(trend) - 1 and trend[k] == 'UP':
                k += 1
            if k >= len(trend) or trend[k] != 'DOWN':
                index += 1
                continue

            right_peak_idx = k
            peaks.append((right_peak_idx, float(y[right_peak_idx])))

            if right_peak_idx - left_peak_idx > 1:
                valley_region = y[left_peak_idx + 1:right_peak_idx]
                if valley_region.size > 0:
                    valley_rel = int(np.argmin(valley_region))
                    valley_idx = left_peak_idx + 1 + valley_rel
                    valleys.append((valley_idx, float(y[valley_idx])))

                    left_peak = y[left_peak_idx]
                    right_peak = y[right_peak_idx]
                    valley = y[valley_idx]

                    if not (np.isnan(left_peak) or np.isnan(right_peak) or np.isnan(valley)):
                        dx_total = right_peak_idx - left_peak_idx
                        if dx_total > 0:
                            t = (valley_idx - left_peak_idx) / dx_total
                            crest_at_valley = left_peak + t * (right_peak - left_peak)
                            depth_diff_m = max(0.0, crest_at_valley - valley)
                            drop_inches = depth_diff_m * M_TO_IN
                        else:
                            drop_inches = 0.0

                        max_p = max(left_peak, right_peak)
                        min_p = min(left_peak, right_peak)
                        symmetry_ok = (min_p / max_p) >= 0.10 if max_p != 0 else False

                        if not symmetry_ok or drop_inches <= 0.0:
                            severity = "NO CORRUGATION"
                        elif drop_inches < 1.0:
                            severity = "LOW"
                        elif drop_inches < 3.0:
                            severity = "MEDIUM"
                        else:
                            severity = "HIGH"

                        for ii in range(left_peak_idx, right_peak_idx + 1):
                            if severity != "NO CORRUGATION":
                                sev_str[ii] = severity
                                amp_in[ii] = max(amp_in[ii], drop_inches)

            index = max(right_peak_idx - 1, 0)
        else:
            index += 1

    # Post-pass: promote subtle lows
    sev_arr = np.array(sev_str, dtype=object)
    low_cands = amp_in[(amp_in > 0) & (sev_arr == "NO CORRUGATION")]
    if low_cands.size > 0:
        mu = float(np.mean(low_cands))
        sd = float(np.std(low_cands))
        thr = max(0.0, mu - 0.5 * sd) if (np.isfinite(sd) and sd > 1e-6) else max(0.0, 0.5 * mu)
        for i in range(n):
            if sev_str[i] == "NO CORRUGATION" and amp_in[i] > 0:
                if amp_in[i] <= thr:
                    amp_in[i] = 0.0
                else:
                    sev_str[i] = "LOW"

    df = pd.DataFrame({
        "section": section.astype(int),
        "depth_m": depth_m.astype(float),
        "drop_in": amp_in,
        "severity": sev_str
    })
    return df, y, peaks, valleys


def analyze_corrugation_in_polygon(
    elevation_data: np.ndarray,
    metadata: dict,
    polygon: Polygon,
    line_interval: float,
    dy_freq: int,
    job_id: str,
    sigma_samples: float = 2.0,
    neighbor_eval: bool = False,
    neighbor_range: int = 2
) -> Dict[str, Any]:
    """
    Analyze corrugation within polygon using horizontal transect lines.

    Returns dict with totals, profiles, and optional neighbor summary.
    """
    pix_m = float(np.mean(np.abs(metadata['resolution'])))
    min_x, min_y, max_x, max_y = polygon.bounds
    transect_ys = np.arange(min_y, max_y + line_interval, line_interval)

    if neighbor_eval:
        start_f = max(1, dy_freq - neighbor_range)
        end_f = dy_freq + neighbor_range
        frequencies = list(range(start_f, end_f + 1))
    else:
        frequencies = [dy_freq]

    all_ruts = []
    neighbor_summary = []
    profiles = []
    severity_levels = ["LOW", "MEDIUM", "HIGH"]

    for f in frequencies:
        dx = (100.0 * pix_m) / float(f)
        freq_ruts = []

        for t_idx, transect_y in enumerate(transect_ys):
            if t_idx % 50 == 0:
                logger.info(f"Job {job_id}: f={f}, transect {t_idx}/{len(transect_ys)}")

            h_line = LineString([(min_x - 10, transect_y), (max_x + 10, transect_y)])
            inter = polygon.intersection(h_line)
            if inter.is_empty:
                continue

            if inter.geom_type == 'MultiLineString':
                line = max(inter.geoms, key=lambda g: g.length)
            else:
                line = inter

            if line.length < dx:
                continue

            length = line.length
            dists = np.arange(0.0, length + dx, dx)
            pts = [line.interpolate(d) for d in dists]

            depths = []
            valid_dists = []
            for i, pt in enumerate(pts):
                try:
                    row, col = rowcol(metadata['transform'], pt.x, pt.y)
                    if 0 <= row < elevation_data.shape[0] and 0 <= col < elevation_data.shape[1]:
                        val = elevation_data[row, col]
                        if val == -32767 or (metadata.get('nodata') is not None and val == metadata['nodata']):
                            depths.append(np.nan)
                        else:
                            depths.append(float(val))
                    else:
                        depths.append(np.nan)
                except (IndexError, Exception):
                    depths.append(np.nan)
                valid_dists.append(float(dists[i]) if i < len(dists) else float(i * dx))

            depths_arr = np.array(depths, dtype=float)
            # Interpolate NaN gaps
            mask_valid = np.isfinite(depths_arr)
            if mask_valid.sum() < 5:
                continue

            depths_series = pd.Series(depths_arr).interpolate("linear").bfill().ffill()
            depths_clean = depths_series.to_numpy()

            sections = np.arange(len(depths_clean))
            df_result, y_smooth, peaks, valleys = detect_corrugations_trend(
                sections, depths_clean, dx, sigma_samples
            )

            # Extract corrugation segments
            df_line = df_result.copy()
            df_nonzero = df_line[(df_line["drop_in"] > 0) | (df_line["severity"].isin(["MEDIUM", "HIGH"]))]

            if not df_nonzero.empty:
                seg_break = (df_nonzero["severity"].shift() != df_nonzero["severity"]).cumsum()
                for _, group in df_nonzero.groupby(seg_break):
                    depth_in = float(group["drop_in"].max())
                    severity = str(group["severity"].iloc[0])
                    if severity == "NO CORRUGATION":
                        continue
                    num_sections = int(len(group))
                    length_m = num_sections * dx
                    area_ft2 = float(length_m * line_interval * M2_TO_FT2)
                    freq_ruts.append({
                        "transect_y": float(transect_y),
                        "depth_in": depth_in,
                        "area_ft2": area_ft2,
                        "severity": severity,
                        "frequency": int(f)
                    })

            # Save profile for plotting (only for primary frequency, max 30)
            if f == dy_freq and len(profiles) < 30:
                profiles.append({
                    "transect_y": float(transect_y),
                    "sections": sections.tolist(),
                    "depths": depths_clean.tolist(),
                    "smoothed": y_smooth.tolist(),
                    "severity_labels": df_result["severity"].tolist(),
                    "peaks": [(int(p[0]), float(p[1])) for p in peaks],
                    "valleys": [(int(v[0]), float(v[1])) for v in valleys],
                })

        # Aggregate per frequency
        for sev in severity_levels:
            items = [r for r in freq_ruts if r["severity"] == sev]
            areas = np.array([r["area_ft2"] for r in items], dtype=float) if items else np.array([])
            depths_a = np.array([r["depth_in"] for r in items], dtype=float) if items else np.array([])
            neighbor_summary.append({
                "frequency": int(f),
                "severity": sev,
                "count": len(items),
                "mean_depth_in": float(np.nanmean(depths_a)) if depths_a.size else 0.0,
                "std_depth_in": float(np.nanstd(depths_a)) if depths_a.size else 0.0,
                "total_area_ft2": float(np.nansum(areas)) if areas.size else 0.0,
            })

        all_ruts.extend(freq_ruts)

    # Summary for primary frequency
    primary_ruts = [r for r in all_ruts if r["frequency"] == dy_freq]
    totals = {s: 0.0 for s in severity_levels}
    counts = {s: 0 for s in severity_levels}
    for r in primary_ruts:
        if r["severity"] in totals:
            totals[r["severity"]] += r["area_ft2"]
            counts[r["severity"]] += 1

    total_area = sum(totals.values())
    logger.info(f"Job {job_id}: Corrugation complete. Low={totals['LOW']:.1f}ft2, "
                f"Med={totals['MEDIUM']:.1f}ft2, High={totals['HIGH']:.1f}ft2")

    return {
        "totals_ft2": totals,
        "counts": counts,
        "total_area_ft2": total_area,
        "profiles": profiles,
        "neighbor_eval": neighbor_eval,
        "neighbor_summary": neighbor_summary if neighbor_eval else None,
        "all_segments": primary_ruts,
    }
