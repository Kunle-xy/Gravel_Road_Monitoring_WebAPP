"""
Crown distress detection algorithms.

Analyzes DEM elevation profiles for:
- Crown slope (left/right slope percentages)
- Rut detection within profiles (peak-valley-peak pattern)
- Crown severity classification combining slope signs and rut severity
- Optional neighbor frequency evaluation

Units:
    spacing_m — meters between vertical sampling lines
    dy — meters along a sampling line between points
    Linear feet totals use spacing_m * 3.280839895

Constraint:
    Ridge-to-ridge span along profile must be <= 3.0 feet (RUT_MAX_FEET)
"""

import math
import logging
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
from shapely.geometry import Polygon, LineString
from rasterio.transform import rowcol

logger = logging.getLogger(__name__)

FEET_PER_METER = 3.280839895
RUT_MAX_FEET = 3.0
RUT_MAX_METERS = RUT_MAX_FEET * 0.3048


def fit_line_percent_slope(y_vals: np.ndarray, step_m: float) -> Tuple[float, float, str]:
    """Fit a line to elevation values, return (slope_percent, intercept, sign)."""
    y = np.asarray(y_vals, dtype=float)
    mask = np.isfinite(y)
    if mask.sum() < 2:
        return np.nan, np.nan, "0"
    x = np.arange(mask.sum(), dtype=float) * float(step_m)
    yy = y[mask]
    m, b = np.polyfit(x, yy, 1)
    m_pct = float(m) * 100.0
    sign = "+" if m_pct > 0 else "-" if m_pct < 0 else "0"
    return m_pct, float(b), sign


def avg_slope_from_profile(depths: List[float], dy_m: float) -> Tuple[float, float, float, str, str, int]:
    """
    Compute left and right slope from an elevation profile.
    Returns (m_left_pct, m_right_pct, avg_abs_pct, sign_left, sign_right, ref_idx).
    """
    y = np.asarray(depths, dtype=float)
    y = y[np.isfinite(y)]
    if y.size < 4:
        return np.nan, np.nan, np.nan, "0", "0", 0
    mid_idx = int(y.size // 2)
    peak_idx = int(np.nanargmax(y))
    ref_idx = int((mid_idx + peak_idx) // 2)
    left = y[:ref_idx] if ref_idx > 1 else y[:1]
    right = y[ref_idx + 1:] if ref_idx + 1 < y.size else y[-1:]
    m_left, _, s_left = fit_line_percent_slope(left, dy_m)
    m_right, _, s_right = fit_line_percent_slope(right, dy_m)
    avg_abs = np.nanmean([abs(m_left), abs(m_right)])
    return m_left, m_right, avg_abs, s_left, s_right, ref_idx


def severity_from_depth_inches(depth_in: float) -> Optional[str]:
    """Classify rut severity by depth in inches."""
    if depth_in > 3.0:
        return "High"
    if 1.0 <= depth_in <= 3.0:
        return "Medium"
    if 0.5 < depth_in < 1.0:
        return "Low"
    return None


def detect_rut_severity(
    depths: List[float], dy_m: float
) -> Tuple[Optional[str], float, Optional[Tuple[int, int, int]]]:
    """
    Detect worst rut in a profile using peak-valley-peak pattern.
    Ridge-to-ridge span constrained to <= RUT_MAX_FEET.

    Returns (severity, depth_inches, (idx_h1, idx_low, idx_h2) or None).
    """
    inches_per_meter = 39.3701
    y = np.asarray(depths, dtype=float)
    mask = np.isfinite(y)
    if mask.sum() < 3:
        return None, 0.0, None

    vals = y[mask]
    res = []
    low = float(vals[0])
    idx_low = 0
    prev_dir = None
    left_height = None
    peaks_h = [float(vals[0])]
    peaks_i = [0]
    idx_h1 = 0
    h1 = low
    min_depth_diff_m = 0.0127

    max_span_samples = max(1, int(math.ceil(RUT_MAX_METERS / float(dy_m))))

    for i in range(1, vals.size):
        cur = float(vals[i])
        prev = float(vals[i - 1])
        direction = "UP" if cur > prev else "DOWN"

        if direction == "UP":
            if cur > peaks_h[-1]:
                peaks_h[-1] = cur
                peaks_i[-1] = i
            else:
                peaks_h.append(cur)
                peaks_i.append(i)

        if prev_dir == "DOWN" and direction == "UP":
            low = float(vals[i - 1])
            idx_low = i - 1
            if peaks_i:
                valids = [ii for ii in peaks_i if ii <= idx_low]
                if valids:
                    ph_valid = [peaks_h[peaks_i.index(ii)] for ii in valids]
                    best = int(np.argmax(ph_valid))
                    idx_h1 = valids[best]
                    h1 = float(vals[idx_h1])
                    left_height = h1 - low
                else:
                    left_height = None

        elif prev_dir == "UP" and direction == "DOWN" and left_height is not None:
            if peaks_i:
                valids = [ii for ii in peaks_i if ii > idx_low and ii <= i]
                if valids:
                    ph_valid = [peaks_h[peaks_i.index(ii)] for ii in valids]
                    best = int(np.argmax(ph_valid))
                    idx_h2 = valids[best]
                    h2 = float(vals[idx_h2])
                    right_height = h2 - low
                    rut_depth_m = min(h1, h2) - low
                    rut_depth_in = float(rut_depth_m) * inches_per_meter

                    if (idx_h2 > idx_low > idx_h1
                        and (idx_h2 - idx_h1) <= max_span_samples
                        and (min(left_height, right_height) >= 0.1 * max(left_height, right_height))
                        and rut_depth_m >= min_depth_diff_m):
                        res.append((rut_depth_in, idx_h1, idx_low, idx_h2))

        prev_dir = direction

    if not res:
        return None, 0.0, None

    def _sev_rank(depth_in):
        return {"Low": 1, "Medium": 2, "High": 3}.get(severity_from_depth_inches(depth_in), 0)

    best = max(res, key=lambda t: (_sev_rank(t[0]), t[0]))
    best_depth = float(best[0])
    best_sev = severity_from_depth_inches(best_depth)
    best_idxs = (int(best[1]), int(best[2]), int(best[3]))
    return best_sev, best_depth, best_idxs


def crown_severity(avg_slope_pct: float, left_sign: str, right_sign: str, rut_sev: Optional[str]) -> Optional[str]:
    """
    Determine crown severity from slope and rut analysis.
    Inverted crown (left negative, right positive) is always High.
    """
    if left_sign == "-" and right_sign == "+":
        return "High"
    x = float(avg_slope_pct)
    if x >= 4.0:
        if rut_sev == "Medium":
            return "Low"
        if rut_sev == "High":
            return "Medium"
        return None
    if 1.0 < x < 4.0:
        if rut_sev == "Low":
            return "Low"
        if rut_sev == "Medium":
            return "Medium"
        if rut_sev == "High":
            return "High"
        return None
    if 0.0 <= x <= 1.0:
        if rut_sev is None:
            return "Low"
        if rut_sev == "Low":
            return "Medium"
        if rut_sev == "Medium":
            return "High"
        if rut_sev == "High":
            return "High"
    return None


def analyze_crown_in_polygon(
    elevation_data: np.ndarray,
    metadata: dict,
    polygon: Polygon,
    spacing_m: float,
    dy_freq: int,
    job_id: str,
    neighbor_eval: bool = False,
    neighbor_range: int = 2
) -> Dict[str, Any]:
    """
    Analyze crown distress within polygon by sampling along vertical lines.

    Returns results dict with:
        - totals_ft: linear feet per severity
        - counts: line count per severity
        - profiles: top 30 profile details for plotting
        - neighbor data if neighbor_eval is True
    """
    pix_m = float(np.mean(np.abs(metadata['resolution'])))
    min_x, min_y, max_x, max_y = polygon.bounds
    dx_feet = spacing_m * FEET_PER_METER
    xs = np.arange(min_x, max_x + spacing_m, spacing_m)

    def _run_once(f_val: int):
        dy_m = (100.0 / float(f_val)) * pix_m
        totals = {"Low": 0.0, "Medium": 0.0, "High": 0.0}
        counts = {"Low": 0, "Medium": 0, "High": 0}
        profiles = []
        sev_rank = {"Low": 1, "Medium": 2, "High": 3, None: 0}

        for line_idx, x in enumerate(xs):
            if line_idx % 100 == 0:
                logger.info(f"Job {job_id}: f={f_val}, line {line_idx}/{len(xs)}")

            line = LineString([(x, min_y), (x, max_y)])
            clipped = line.intersection(polygon)
            if clipped.is_empty or clipped.length <= 0:
                continue

            length = clipped.length
            distances = np.arange(0, length, dy_m)
            if len(distances) < 4:
                continue

            sample_points = [clipped.interpolate(d) for d in distances]
            depths = []
            for pt in sample_points:
                try:
                    row, col = rowcol(metadata['transform'], pt.x, pt.y)
                    if 0 <= row < elevation_data.shape[0] and 0 <= col < elevation_data.shape[1]:
                        val = elevation_data[row, col]
                        depths.append(np.nan if val == -32767 else float(val))
                    else:
                        depths.append(np.nan)
                except (IndexError, Exception):
                    depths.append(np.nan)

            if sum(1 for d in depths if not np.isnan(d)) < 4:
                continue

            m_left, m_right, m_avg, s_left, s_right, ref_idx = avg_slope_from_profile(depths, dy_m)
            rut_sev, rut_depth_in, rut_idxs = detect_rut_severity(depths, dy_m)
            crown = crown_severity(m_avg, s_left, s_right, rut_sev)

            if crown in totals:
                totals[crown] += dx_feet
                counts[crown] += 1

            profiles.append({
                'line_idx': line_idx,
                'x': float(x),
                'depths': [float(d) if not np.isnan(d) else None for d in depths],
                'distances': [float(d) for d in distances],
                'dy_m': dy_m,
                'ref_idx': ref_idx,
                'rut_idxs': rut_idxs,
                'm_left': float(m_left) if not np.isnan(m_left) else 0.0,
                'm_right': float(m_right) if not np.isnan(m_right) else 0.0,
                'm_avg': float(m_avg) if not np.isnan(m_avg) else 0.0,
                's_left': s_left,
                's_right': s_right,
                'rut_sev': rut_sev,
                'rut_depth_in': float(rut_depth_in),
                'crown': crown,
                'rank': (sev_rank.get(crown, 0) * 1_000_000
                         + sev_rank.get(rut_sev, 0) * 10_000
                         + int(round(abs(rut_depth_in) * 100)))
            })

        return totals, counts, profiles

    if neighbor_eval:
        start_f = max(1, dy_freq - neighbor_range)
        end_f = dy_freq + neighbor_range
        freq_list = list(range(start_f, end_f + 1))
        logger.info(f"Job {job_id}: Neighbor sweep f={freq_list}")

        per_freq = []
        base_totals = base_counts = base_profiles = None
        for f_val in freq_list:
            t, c, p = _run_once(f_val)
            per_freq.append((f_val, t, c))
            if f_val == dy_freq:
                base_totals, base_counts, base_profiles = t, c, p

        # Aggregate means/stds across frequencies
        means_ft = {}
        stds_ft = {}
        for sev in ["Low", "Medium", "High"]:
            arr = np.array([t[sev] for _, t, _ in per_freq], dtype=float)
            means_ft[sev] = float(np.nanmean(arr)) if arr.size else 0.0
            stds_ft[sev] = float(np.nanstd(arr, ddof=1)) if arr.size > 1 else 0.0

        totals = base_totals or {"Low": 0.0, "Medium": 0.0, "High": 0.0}
        counts = base_counts or {"Low": 0, "Medium": 0, "High": 0}
        profiles = sorted(base_profiles or [], key=lambda d: d['rank'], reverse=True)[:30]

        return {
            'totals_ft': totals,
            'counts': counts,
            'profiles': profiles,
            'neighbor_eval': True,
            'means_ft': means_ft,
            'stds_ft': stds_ft,
            'freq_list': freq_list,
            'total_linear_ft': sum(totals.values()),
        }
    else:
        totals, counts, profiles = _run_once(dy_freq)
        profiles.sort(key=lambda d: d['rank'], reverse=True)
        profiles = profiles[:30]

        logger.info(f"Job {job_id}: Crown analysis complete. "
                    f"Low={totals['Low']:.1f}ft, Med={totals['Medium']:.1f}ft, High={totals['High']:.1f}ft")

        return {
            'totals_ft': totals,
            'counts': counts,
            'profiles': profiles,
            'neighbor_eval': False,
            'total_linear_ft': sum(totals.values()),
        }
