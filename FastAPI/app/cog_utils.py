"""
Utility functions for Cloud Optimized GeoTIFF (COG) conversion
"""
import os
import tempfile
from typing import Tuple, Optional
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
import rasterio
from rasterio.io import MemoryFile


def is_cog(file_path: str) -> bool:
    """
    Check if a TIFF file is already a Cloud Optimized GeoTIFF
    """
    try:
        with rasterio.open(file_path) as src:
            # COG requirements:
            # 1. Tiled
            # 2. Has overviews
            # 3. Has internal masks (if needed)
            is_tiled = src.profile.get('tiled', False)
            has_overviews = len(src.overviews(1)) > 0 if src.count > 0 else False

            return is_tiled and has_overviews
    except Exception as e:
        print(f"Error checking if file is COG: {e}")
        return False


def convert_to_cog(
    input_data: bytes,
    output_path: Optional[str] = None,
    compression: str = "deflate",
    blocksize: int = 512
) -> Tuple[bytes, int]:
    """
    Convert a TIFF file to Cloud Optimized GeoTIFF (COG)

    Args:
        input_data: Raw bytes of the input TIFF file
        output_path: Optional path to save the COG file
        compression: Compression method (deflate, lzw, jpeg, etc.)
        blocksize: Tile size (256 or 512 recommended)

    Returns:
        Tuple of (cog_bytes, cog_size)
    """
    # Create temporary file for input
    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp_input:
        tmp_input.write(input_data)
        tmp_input_path = tmp_input.name

    try:
        # Create output file path
        if output_path is None:
            tmp_output = tempfile.NamedTemporaryFile(suffix='_cog.tif', delete=False)
            output_path = tmp_output.name
            tmp_output.close()

        # Configure COG profile
        profile = cog_profiles.get(compression)
        if profile is None:
            profile = cog_profiles.get("deflate")

        profile.update({
            "blockxsize": blocksize,
            "blockysize": blocksize,
        })

        # Perform COG conversion
        cog_translate(
            tmp_input_path,
            output_path,
            profile,
            config={"GDAL_NUM_THREADS": "ALL_CPUS"},
            in_memory=False,
            quiet=True
        )

        # Read the converted COG
        with open(output_path, 'rb') as f:
            cog_data = f.read()
            cog_size = len(cog_data)

        return cog_data, cog_size

    finally:
        # Clean up temporary files
        if os.path.exists(tmp_input_path):
            os.unlink(tmp_input_path)
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)


def get_raster_metadata(file_data: bytes) -> dict:
    """
    Extract metadata from a raster file

    Args:
        file_data: Raw bytes of the raster file

    Returns:
        Dictionary with raster metadata
    """
    try:
        with MemoryFile(file_data) as memfile:
            with memfile.open() as src:
                bounds = src.bounds
                return {
                    "width": src.width,
                    "height": src.height,
                    "count": src.count,
                    "dtype": str(src.dtypes[0]) if src.count > 0 else None,
                    "crs": str(src.crs) if src.crs else None,
                    "bounds": {
                        "left": bounds.left,
                        "bottom": bounds.bottom,
                        "right": bounds.right,
                        "top": bounds.top
                    },
                    "transform": list(src.transform),
                    "nodata": src.nodata,
                }
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return {}
