"""
Rut detection algorithms.

Contains the core rut detection logic:
- detect_ruts_along_line: Finds ruts in a single elevation profile
- analyze_ruts_in_polygon: Samples a polygon with vertical lines and aggregates rut detections
"""

import logging
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from rasterio.transform import rowcol
from shapely.geometry import Polygon, LineString

from app.workers.rut.constants import get_deduct_value

logger = logging.getLogger(__name__)


def detect_ruts_along_line(
    depths: List[float],
    dy: float,
    dx: float,
    min_depth_diff: float = 0.0127,  # 0.5 inches in meters
    min_points_between: int = 10
) -> List[Dict[str, Any]]:
    """
    Detect ruts along a single sampling line.

    Uses peak/valley detection to find rut patterns where two shoulders
    surround a depression. Classifies severity by depth:
        Low:    0.5 - 1.0 inches
        Medium: 1.0 - 3.0 inches
        High:   > 3.0 inches

    Returns list of detected ruts with depth, area, and severity.
    """
    inches_per_meter = 39.3701
    sqm_to_sqft = 10.7639

    if len(depths) < 2:
        return []

    df_input = pd.DataFrame({"section": list(range(len(depths))), "depth": depths})

    res = []
    direction_prev = None
    left_height = None
    peak_heights = [df_input["depth"].iloc[0]]
    peak_indices = [0]
    idx_h1 = 0
    h1 = df_input["depth"].iloc[0]
    low = h1
    idx_low = 0

    for idx in range(1, len(df_input)):
        current = df_input["depth"].iloc[idx]
        previous = df_input["depth"].iloc[idx - 1]
        direction = "UP" if current > previous else "DOWN"

        if direction == "UP":
            if current > peak_heights[-1]:
                peak_heights[-1] = current
                peak_indices[-1] = idx
            else:
                peak_heights.append(current)
                peak_indices.append(idx)

        # DOWN to UP transition: valley found
        if direction_prev == "DOWN" and direction == "UP":
            low = df_input["depth"].iloc[idx - 1]
            idx_low = idx - 1
            if peak_indices:
                valid_peaks = [i for i in peak_indices if i <= idx_low]
                if valid_peaks:
                    peak_heights_valid = [peak_heights[peak_indices.index(i)] for i in valid_peaks]
                    max_peak_idx = peak_heights_valid.index(max(peak_heights_valid))
                    idx_h1 = valid_peaks[max_peak_idx]
                    h1 = df_input["depth"].iloc[idx_h1]
                    left_height = h1 - low
                else:
                    left_height = None
            else:
                left_height = None

        # UP to DOWN transition: right peak found, check if rut
        elif direction_prev == "UP" and direction == "DOWN" and left_height is not None:
            if peak_indices:
                valid_peaks = [i for i in peak_indices if i > idx_low and i <= idx]
                if valid_peaks:
                    peak_heights_valid = [peak_heights[peak_indices.index(i)] for i in valid_peaks]
                    max_peak_idx = peak_heights_valid.index(max(peak_heights_valid))
                    idx_h2 = valid_peaks[max_peak_idx]
                    h2 = df_input["depth"].iloc[idx_h2]
                    right_height = h2 - low

                    avg_shoulder = 0.5 * (h1 + h2)
                    rut_depth_m = avg_shoulder - low
                    rut_depth_in = rut_depth_m * inches_per_meter

                    # Validate rut
                    if (idx_h2 > idx_low > idx_h1 and
                        (min(left_height, right_height) >= 0.1 * max(left_height, right_height)) and
                        rut_depth_m >= min_depth_diff and
                        (idx_h2 - idx_h1 - 1) > min_points_between):

                        width = (idx_h2 - idx_h1) * dy
                        rut_area = width * dx
                        rut_area_sqft = rut_area * sqm_to_sqft

                        severity = None
                        if 0.5 < rut_depth_in < 1.0:
                            severity = "Low"
                        elif 1.0 <= rut_depth_in <= 3.0:
                            severity = "Medium"
                        elif rut_depth_in > 3.0:
                            severity = "High"

                        if severity:
                            res.append({
                                'idx_h1': int(idx_h1),
                                'idx_low': int(idx_low),
                                'idx_h2': int(idx_h2),
                                'rut_depth_m': float(rut_depth_m),
                                'rut_depth_in': float(rut_depth_in),
                                'rut_area_sqft': float(rut_area_sqft),
                                'severity': severity
                            })

                        peak_heights = [h2]
                        peak_indices = [idx_h2]

        direction_prev = direction

    return res


def analyze_ruts_in_polygon(
    elevation_data: np.ndarray,
    metadata: dict,
    polygon: Polygon,
    dy_freq: int,
    dx: float,
    job_id: str,
    neighbor_eval: bool = False,
    neighbor_range: int = 2
) -> Dict[str, Any]:
    """
    Analyze ruts within polygon by sampling along vertical lines.
    Optionally test neighboring sampling frequencies.

    Returns results dictionary with detected ruts, statistics,
    density/deduct data, and cross-section samples for plotting.
    """
    polygon_area_sqm = polygon.area
    polygon_area_sqft = polygon_area_sqm * 10.7639
    logger.info(f"Job {job_id}: Polygon area = {polygon_area_sqft:.2f} sq ft")

    if neighbor_eval:
        start_freq = max(1, dy_freq - neighbor_range)
        end_freq = dy_freq + neighbor_range
        frequencies = list(range(start_freq, end_freq + 1))
        logger.info(f"Job {job_id}: Neighbor evaluation enabled, testing frequencies: {frequencies}")
    else:
        frequencies = [dy_freq]
        logger.info(f"Job {job_id}: Single frequency analysis: {dy_freq}")

    frequency_results = {}
    all_ruts_all_freq = []
    cross_sections = []

    for freq in frequencies:
        pix_m = float(np.mean(np.abs(metadata['resolution'])))
        dy = (100.0 / float(freq)) * pix_m

        logger.info(f"Job {job_id}: Processing frequency {freq}, dy={dy:.4f}m, dx={dx:.4f}m")

        min_x, min_y, max_x, max_y = polygon.bounds
        x_steps = np.arange(min_x, max_x + dx, dx)

        freq_ruts = []
        max_cross_sections = 30

        for line_idx, x in enumerate(x_steps):
            if line_idx % 100 == 0:
                logger.info(f"Job {job_id}: Freq {freq} - Processing line {line_idx}/{len(x_steps)}")

            line = LineString([(x, min_y), (x, max_y)])
            clipped_line = line.intersection(polygon)

            if clipped_line.is_empty or clipped_line.length <= 0:
                continue

            length = clipped_line.length
            distances = np.arange(0, length, dy)

            if len(distances) < 2:
                continue

            sample_points = [clipped_line.interpolate(distance) for distance in distances]

            depths = []
            for pt in sample_points:
                try:
                    row, col = rowcol(metadata['transform'], pt.x, pt.y)
                    if 0 <= row < elevation_data.shape[0] and 0 <= col < elevation_data.shape[1]:
                        depth = elevation_data[row, col]
                        if depth == -32767:
                            depth = np.nan
                    else:
                        depth = np.nan
                except IndexError:
                    depth = np.nan
                depths.append(depth)

            mask = [not np.isnan(d) for d in depths]
            if sum(mask) < 2:
                continue

            depths_filtered = [d for d, m in zip(depths, mask) if m]
            distances_filtered = [distances[i] for i, m in enumerate(mask) if m]

            if freq == dy_freq and len(cross_sections) < max_cross_sections:
                cross_sections.append({
                    'line_idx': line_idx,
                    'x': float(x),
                    'distances': [float(d) for d in distances_filtered],
                    'elevations': [float(e) for e in depths_filtered]
                })

            ruts = detect_ruts_along_line(depths_filtered, dy, dx)

            for rut in ruts:
                rut['line_x'] = float(x)
                rut['frequency'] = freq
                freq_ruts.append(rut)
                all_ruts_all_freq.append(rut)

        total_ruts = len(freq_ruts)
        low_count = sum(1 for r in freq_ruts if r['severity'] == 'Low')
        medium_count = sum(1 for r in freq_ruts if r['severity'] == 'Medium')
        high_count = sum(1 for r in freq_ruts if r['severity'] == 'High')

        low_area = sum(r['rut_area_sqft'] for r in freq_ruts if r['severity'] == 'Low')
        medium_area = sum(r['rut_area_sqft'] for r in freq_ruts if r['severity'] == 'Medium')
        high_area = sum(r['rut_area_sqft'] for r in freq_ruts if r['severity'] == 'High')
        total_area = low_area + medium_area + high_area

        frequency_results[freq] = {
            'ruts': freq_ruts,
            'total_ruts_detected': total_ruts,
            'low_severity_count': low_count,
            'medium_severity_count': medium_count,
            'high_severity_count': high_count,
            'low_area_sqft': float(low_area),
            'medium_area_sqft': float(medium_area),
            'high_area_sqft': float(high_area),
            'total_area_sqft': float(total_area),
        }

        logger.info(f"Job {job_id}: Freq {freq} - Detected {total_ruts} ruts (Low={low_count}, Medium={medium_count}, High={high_count})")

    primary_results = frequency_results[dy_freq]

    density_data = {}
    for severity in ['Low', 'Medium', 'High']:
        area_key = f'{severity.lower()}_area_sqft'
        area = primary_results[area_key]
        density_percent = (area / polygon_area_sqft * 100) if polygon_area_sqft > 0 else 0
        deduct_value = get_deduct_value(density_percent, severity)

        density_data[severity] = {
            'area_sqft': float(area),
            'density_percent': float(density_percent),
            'deduct_value': int(deduct_value)
        }

    logger.info(f"Job {job_id}: Density and deduct values calculated")
    logger.info(f"Job {job_id}: Saved {len(cross_sections)} cross-sections for plotting")

    return {
        'ruts': primary_results['ruts'],
        'total_ruts_detected': primary_results['total_ruts_detected'],
        'low_severity_count': primary_results['low_severity_count'],
        'medium_severity_count': primary_results['medium_severity_count'],
        'high_severity_count': primary_results['high_severity_count'],
        'total_area_sqft': primary_results['total_area_sqft'],
        'polygon_area_sqft': float(polygon_area_sqft),
        'density_data': density_data,
        'cross_sections': cross_sections,
        'neighbor_eval': neighbor_eval,
        'frequency_results': frequency_results if neighbor_eval else None
    }
