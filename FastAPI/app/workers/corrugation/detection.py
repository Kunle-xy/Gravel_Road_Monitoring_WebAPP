"""
Corrugation detection algorithms.

Detects corrugation (wave-like surface distortion) in elevation profiles by:
1. Linear-detrending the elevation signal so road grade doesn't mask peaks.
2. Gaussian smoothing (sigma auto-clamped against min_wavelength_m so it can
   never wash out the target wave band).
3. Locating peaks and valleys with scipy.signal.find_peaks, guarded by
   `distance` (≥ min_wavelength_m / dx) and `prominence` (~30 % of the
   classification floor) — prominence replaces the old symmetry check and
   is inherently slope-insensitive.
4. Computing drop depth (interpolated crest to valley, in inches).
5. Classifying severity: Low (<1"), Medium (1–3"), High (>3").

Also handles polygon-wide analysis with horizontal transect sampling.
"""

import logging
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.signal import find_peaks
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
    sigma_samples: float = 3.0,
    min_drop_in: float = 0.25,
    min_wavelength_m: float = 0.2,
    max_wavelength_m: float = 2.0,
) -> Tuple[pd.DataFrame, np.ndarray, List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Detect corrugations in an elevation profile.

    Pipeline:
      1. Linear-detrend the profile so road grade doesn't hide local peaks.
      2. Smooth (sigma auto-clamped to ≤25 % of samples-per-min-wavelength).
      3. Run scipy.signal.find_peaks with `distance` and `prominence` guards.
      4. Pair adjacent peaks, take the lowest valley between, compute drop
         as the linearly-interpolated crest minus the valley (baseline-free).
      5. Classify: drop ≥ min_drop_in → LOW (<1"), MEDIUM (1–3"), HIGH (>3").

    Prominence replaces the old min/max-peak symmetry check and is
    inherently slope-insensitive, so the detrend + prominence combo
    handles rising grades cleanly.

    Returns:
        df: DataFrame with section, depth_m, drop_in, severity
        y_smooth: smoothed (non-detrended) elevation for display
        peaks: list of (index, value) tuples (values taken from y_smooth)
        valleys: list of (index, value) tuples (values taken from y_smooth)
    """
    depth_arr = np.asarray(depth_m, dtype=float)
    section_arr = np.asarray(section, dtype=int)
    n = len(depth_arr)

    def _empty_result() -> Tuple[pd.DataFrame, np.ndarray, List[Tuple[int, float]], List[Tuple[int, float]]]:
        return (
            pd.DataFrame({
                "section": section_arr,
                "depth_m": depth_arr,
                "drop_in": np.zeros(n, dtype=float),
                "severity": ["NO CORRUGATION"] * n,
            }),
            depth_arr.copy(),
            [],
            [],
        )

    if n < 5:
        return _empty_result()

    # Clamp sigma so the smoothing kernel cannot wash out the target band.
    samples_per_min_wave = max(1.0, float(min_wavelength_m) / float(dx_m))
    max_sigma = max(0.5, 0.25 * samples_per_min_wave)
    effective_sigma = min(float(sigma_samples), max_sigma)
    if effective_sigma < float(sigma_samples):
        logger.debug(
            f"corrugation: sigma clamped {sigma_samples} → {effective_sigma:.2f} "
            f"(samples/min_wave={samples_per_min_wave:.1f}, dx={dx_m:.4f} m)"
        )

    # Smoothed absolute signal — used for drop math (baseline cancels in
    # the crest-at-valley interpolation) and returned for plotting.
    y_smooth = smooth_gaussian(depth_arr, sigma_samples=effective_sigma)

    # Linear-detrended + smoothed signal — used only for peak detection so
    # a rising grade can't mask local maxima / minima.
    valid = np.isfinite(depth_arr)
    if valid.sum() < 3:
        return _empty_result()
    x_idx = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x_idx[valid], depth_arr[valid], 1)
    baseline = slope * x_idx + intercept
    y_det = smooth_gaussian(depth_arr - baseline, sigma_samples=effective_sigma)

    min_dist_samples = max(2, int(round(float(min_wavelength_m) / float(dx_m))))
    # ~30 % of the classification floor, in metres. Prominence is slope-
    # insensitive, which is why we can drop the old symmetry ratio check.
    min_prominence_m = max(1e-6, (float(min_drop_in) / M_TO_IN) * 0.3)
    peaks_idx_arr, _ = find_peaks(y_det, distance=min_dist_samples, prominence=min_prominence_m)
    valleys_idx_arr, _ = find_peaks(-y_det, distance=min_dist_samples, prominence=min_prominence_m)

    peaks: List[Tuple[int, float]] = [(int(p), float(y_smooth[p])) for p in peaks_idx_arr]
    valleys: List[Tuple[int, float]] = [(int(v), float(y_smooth[v])) for v in valleys_idx_arr]

    sev_str = ["NO CORRUGATION"] * n
    amp_in = np.zeros(n, dtype=float)

    peaks_idx = [int(p) for p in peaks_idx_arr]
    valleys_idx = [int(v) for v in valleys_idx_arr]

    for left_idx, right_idx in zip(peaks_idx[:-1], peaks_idx[1:]):
        dx_total = right_idx - left_idx
        if dx_total <= 0:
            continue
        wavelength_m = dx_total * dx_m
        if not (min_wavelength_m <= wavelength_m <= max_wavelength_m):
            continue

        interior = [v for v in valleys_idx if left_idx < v < right_idx]
        if not interior:
            continue
        valley_idx = min(interior, key=lambda v: y_smooth[v])

        left_peak = float(y_smooth[left_idx])
        right_peak = float(y_smooth[right_idx])
        valley = float(y_smooth[valley_idx])
        if not np.isfinite(left_peak + right_peak + valley):
            continue

        t = (valley_idx - left_idx) / dx_total
        crest_at_valley = left_peak + t * (right_peak - left_peak)
        drop_inches = max(0.0, crest_at_valley - valley) * M_TO_IN
        if drop_inches < min_drop_in:
            continue

        if drop_inches < 1.0:
            severity = "LOW"
        elif drop_inches < 3.0:
            severity = "MEDIUM"
        else:
            severity = "HIGH"

        for ii in range(left_idx, right_idx + 1):
            if drop_inches > amp_in[ii]:
                amp_in[ii] = drop_inches
                sev_str[ii] = severity

    df = pd.DataFrame({
        "section": section_arr,
        "depth_m": depth_arr,
        "drop_in": amp_in,
        "severity": sev_str,
    })
    return df, y_smooth, peaks, valleys


def analyze_corrugation_in_polygon(
    elevation_data: np.ndarray,
    metadata: dict,
    polygon: Polygon,
    line_interval: float,
    dy_freq: int,
    job_id: str,
    sigma_samples: float = 3.0,
    min_drop_in: float = 0.25,
    min_wavelength_m: float = 0.2,
    max_wavelength_m: float = 2.0,
) -> Dict[str, Any]:
    """
    Analyze corrugation within polygon using horizontal transect lines at a
    single sampling frequency (dy_freq).

    Returns dict with totals, per-severity counts, and profile data for plots.
    """
    pix_m = float(np.mean(np.abs(metadata['resolution'])))
    min_x, min_y, max_x, max_y = polygon.bounds
    transect_ys = np.arange(min_y, max_y + line_interval, line_interval)

    to_wgs84 = Transformer.from_crs(metadata['crs'], "EPSG:4326", always_xy=True)
    half_width = line_interval / 2.0
    dx = (100.0 * pix_m) / float(dy_freq)

    segments: List[Dict[str, Any]] = []
    profiles: List[Dict[str, Any]] = []
    severity_levels = ["LOW", "MEDIUM", "HIGH"]

    for t_idx, transect_y in enumerate(transect_ys):
        if t_idx % 50 == 0:
            logger.info(f"Job {job_id}: transect {t_idx}/{len(transect_ys)}")

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
        for pt in pts:
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

        depths_arr = np.array(depths, dtype=float)
        mask_valid = np.isfinite(depths_arr)
        if mask_valid.sum() < 5:
            continue

        depths_clean = pd.Series(depths_arr).interpolate("linear").bfill().ffill().to_numpy()

        sections = np.arange(len(depths_clean))
        df_result, y_smooth, peaks, valleys = detect_corrugations_trend(
            sections, depths_clean, dx, sigma_samples,
            min_drop_in=min_drop_in,
            min_wavelength_m=min_wavelength_m,
            max_wavelength_m=max_wavelength_m,
        )

        df_nonzero = df_result[(df_result["drop_in"] > 0) | (df_result["severity"].isin(["MEDIUM", "HIGH"]))]

        if not df_nonzero.empty:
            seg_break = (df_nonzero["severity"].shift() != df_nonzero["severity"]).cumsum()
            for _, group in df_nonzero.groupby(seg_break):
                severity = str(group["severity"].iloc[0])
                if severity == "NO CORRUGATION":
                    continue
                depth_in = float(group["drop_in"].max())
                num_sections = int(len(group))
                length_m = num_sections * dx
                area_ft2 = float(length_m * line_interval * M2_TO_FT2)

                seg = {
                    "transect_y": float(transect_y),
                    "depth_in": depth_in,
                    "area_ft2": area_ft2,
                    "severity": severity,
                    "frequency": int(dy_freq),
                }
                try:
                    s_min = max(0, min(int(group["section"].min()), len(pts) - 1))
                    s_max = max(0, min(int(group["section"].max()), len(pts) - 1))
                    x_a = pts[s_min].x
                    x_b = pts[s_max].x
                    if x_a > x_b:
                        x_a, x_b = x_b, x_a
                    corners_proj = [
                        (x_a, transect_y - half_width),
                        (x_b, transect_y - half_width),
                        (x_b, transect_y + half_width),
                        (x_a, transect_y + half_width),
                        (x_a, transect_y - half_width),
                    ]
                    seg["rect_coords"] = [
                        [float(lon), float(lat)]
                        for lon, lat in (to_wgs84.transform(cx, cy) for cx, cy in corners_proj)
                    ]
                except Exception as e:
                    logger.warning(f"Job {job_id}: failed to build corrugation rectangle: {e}")

                segments.append(seg)

        if len(profiles) < 30:
            profiles.append({
                "transect_y": float(transect_y),
                "sections": sections.tolist(),
                "depths": depths_clean.tolist(),
                "smoothed": y_smooth.tolist(),
                "severity_labels": df_result["severity"].tolist(),
                "peaks": [(int(p[0]), float(p[1])) for p in peaks],
                "valleys": [(int(v[0]), float(v[1])) for v in valleys],
            })

    totals = {s: 0.0 for s in severity_levels}
    counts = {s: 0 for s in severity_levels}
    for r in segments:
        if r["severity"] in totals:
            totals[r["severity"]] += r["area_ft2"]
            counts[r["severity"]] += 1

    total_area = sum(totals.values())
    polygon_area_sqft = float(polygon.area * 10.7639)
    logger.info(f"Job {job_id}: Corrugation complete. Low={totals['LOW']:.1f}ft2, "
                f"Med={totals['MEDIUM']:.1f}ft2, High={totals['HIGH']:.1f}ft2, "
                f"polygon={polygon_area_sqft:.1f}ft2")

    return {
        "totals_ft2": totals,
        "counts": counts,
        "total_area_ft2": total_area,
        "polygon_area_sqft": polygon_area_sqft,
        "profiles": profiles,
        "all_segments": segments,
    }
