"""Polygon-aligned sampling without resampling or rotating the source raster.

Local X is the road direction. Local Y is across the road. A stable edge
index, captured when the map rectangle is drawn, identifies its original
horizontal axis even after rotation, resizing, or a 90-degree turn.
"""

import math

import numpy as np
from affine import Affine
from pyproj import Transformer
from shapely.affinity import affine_transform


class SamplingFrame:
    def __init__(self, polygon, metadata):
        source = metadata.get("polygon_geojson", {})
        ring = source.get("coordinates", [[]])[0]
        coords = list(polygon.exterior.coords)[:-1]
        edge = source.get("horizontal_edge_index")
        if edge is None:
            # Compatibility for clients that do not send the stable edge index.
            reference = ring[:-1] if ring else coords
            edge = max(range(len(reference)), key=lambda i: abs(
                reference[(i + 1) % len(reference)][0] - reference[i][0]
            ) / (math.dist(reference[i], reference[(i + 1) % len(reference)]) or 1))
        if not isinstance(edge, int) or not 0 <= edge < len(coords):
            raise ValueError("Invalid polygon horizontal edge index")

        start, end = coords[edge], coords[(edge + 1) % len(coords)]
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        if source.get("road_direction", "horizontal") == "vertical":
            angle += math.pi / 2
        # Preserve edge direction through right-angle turns. Reversing profiles
        # can change endpoint handling in peak/valley detection.
        self.angle_degrees = math.degrees(angle)
        origin = polygon.centroid
        self.to_world = Affine.translation(origin.x, origin.y) * Affine.rotation(self.angle_degrees)
        self.to_local = ~self.to_world
        self.polygon = self.local_geometry(polygon)
        self.metadata = {**metadata, "transform": self.to_local * metadata["transform"]}
        self._to_wgs84 = Transformer.from_crs(metadata["crs"], "EPSG:4326", always_xy=True)
        self.road_direction = source.get("road_direction", "horizontal")

    @staticmethod
    def _coefficients(matrix):
        return [matrix.a, matrix.b, matrix.d, matrix.e, matrix.c, matrix.f]

    def local_geometry(self, geometry):
        return affine_transform(geometry, self._coefficients(self.to_local))

    def world_geometry(self, geometry):
        return affine_transform(geometry, self._coefficients(self.to_world))

    def transform(self, x, y):
        """Transform local samples/overlay vertices directly to WGS84."""
        # numpy supports both scalar vertices and Shapely's coordinate arrays.
        world_x = self.to_world.a * np.asarray(x) + self.to_world.b * np.asarray(y) + self.to_world.c
        world_y = self.to_world.d * np.asarray(x) + self.to_world.e * np.asarray(y) + self.to_world.f
        return self._to_wgs84.transform(world_x, world_y)


def sample_rowcol(transform, x, y):
    """Stable pixel lookup at grid boundaries after coordinate rotation.

    Projection/affine roundoff can otherwise turn row 20 into 19.99999999,
    duplicating/skipping samples and creating artificial peak/valley widths.
    Only values within one millionth of a pixel of an integer are snapped.
    """
    col, row = ~transform * (x, y)
    if abs(col - round(col)) < 1e-6:
        col = round(col)
    if abs(row - round(row)) < 1e-6:
        row = round(row)
    return math.floor(row), math.floor(col)
