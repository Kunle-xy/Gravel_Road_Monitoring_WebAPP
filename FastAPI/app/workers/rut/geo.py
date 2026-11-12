"""
Geospatial utilities for rut analysis.

Handles GeoTIFF polygon extraction, coordinate transforms,
and Gaussian smoothing for elevation data.
"""

import os
import logging
from typing import Dict, Tuple, Any

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import Polygon, shape
from shapely.ops import transform
from scipy.ndimage import gaussian_filter
from pyproj import Transformer

from app.config import settings

logger = logging.getLogger(__name__)


def gaussian_filter_nan(arr: np.ndarray, sigma: float) -> np.ndarray:
    """
    Apply Gaussian smoothing to an array that may contain NaN.
    Normalizes by a binary mask so NaN regions remain NaN.
    """
    if sigma is None or sigma <= 0:
        return arr

    a = arr.astype(float).copy()
    nan_mask = np.isnan(a)
    a[nan_mask] = 0.0
    w = (~nan_mask).astype(float)

    a_blur = gaussian_filter(a, sigma=sigma, mode="nearest")
    w_blur = gaussian_filter(w, sigma=sigma, mode="nearest")

    with np.errstate(invalid="ignore", divide="ignore"):
        out = a_blur / w_blur
    out[w_blur == 0] = np.nan
    return out


def extract_polygon_extent(
    s3_url: str,
    polygon_geojson: Dict[str, Any],
    apply_smoothing: bool = False,
    gaussian_sigma: float = 1.0
) -> Tuple[np.ndarray, dict, Polygon]:
    """
    Extract only the polygon extent from a cloud-stored GeoTIFF.

    Returns:
        - elevation_array: 2D numpy array of elevation values
        - metadata: dict with transform, crs, bounds, resolution
        - polygon: Shapely polygon in raster CRS
    """
    # Set AWS credentials as environment variables for GDAL
    os.environ['AWS_ACCESS_KEY_ID'] = settings.AWS_ACCESS_KEY_ID
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.AWS_SECRET_ACCESS_KEY
    os.environ['AWS_REGION'] = settings.AWS_REGION

    env_options = {
        'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR',
        'CPL_VSIL_CURL_ALLOWED_EXTENSIONS': '.tif,.tiff',
        'GDAL_HTTP_TIMEOUT': '300',
        'GDAL_HTTP_MAX_RETRY': '3',
    }

    polygon_shape = shape(polygon_geojson)

    with rasterio.Env(**env_options):
        with rasterio.open(s3_url) as src:
            # Transform polygon from EPSG:4326 to DEM's CRS
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            polygon_transformed = transform(transformer.transform, polygon_shape)

            logger.info(f"Transformed polygon from EPSG:4326 to {src.crs}")
            logger.info(f"Original bounds (lat/lon): {polygon_shape.bounds}")
            logger.info(f"Transformed bounds ({src.crs}): {polygon_transformed.bounds}")

            dem_bounds = src.bounds
            poly_bounds = polygon_transformed.bounds
            poly_minx, poly_miny, poly_maxx, poly_maxy = poly_bounds

            # Validate polygon is within DEM bounds
            if (poly_maxx < dem_bounds.left or poly_minx > dem_bounds.right or
                poly_maxy < dem_bounds.bottom or poly_miny > dem_bounds.top):
                raise ValueError(
                    f"Polygon is completely outside DEM bounds. "
                    f"Polygon: ({poly_minx:.6f}, {poly_miny:.6f}, {poly_maxx:.6f}, {poly_maxy:.6f}), "
                    f"DEM: ({dem_bounds.left:.6f}, {dem_bounds.bottom:.6f}, {dem_bounds.right:.6f}, {dem_bounds.top:.6f})"
                )

            if (poly_minx < dem_bounds.left or poly_maxx > dem_bounds.right or
                poly_miny < dem_bounds.bottom or poly_maxy > dem_bounds.top):
                logger.warning(
                    f"Polygon extends beyond DEM bounds. "
                    f"Analysis will be limited to DEM coverage area."
                )

            window = from_bounds(*poly_bounds, transform=src.transform)
            band1 = src.read(1, window=window).astype(float)
            window_transform = src.window_transform(window)

            if src.nodata is not None:
                band1[band1 == float(src.nodata)] = np.nan

            if apply_smoothing:
                logger.info(f"Applying Gaussian smoothing with sigma={gaussian_sigma}")
                band1 = gaussian_filter_nan(band1, gaussian_sigma)

            metadata = {
                'transform': window_transform,
                'crs': src.crs,
                'bounds': poly_bounds,
                'resolution': src.res,
                'width': window.width,
                'height': window.height,
                'nodata': src.nodata,
                'polygon_geojson': polygon_geojson,
            }

            return band1, metadata, polygon_transformed
