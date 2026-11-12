"""Run with: python -m unittest discover -s tests -v (from FastAPI)."""

import unittest
import os
from unittest.mock import patch

import numpy as np
from affine import Affine
from pyproj import Transformer
from rasterio.transform import rowcol
from shapely.affinity import affine_transform
from shapely.geometry import Polygon, LineString

from app.workers.sampling import SamplingFrame, sample_rowcol


def fixture(angle=0, direction="horizontal", square=False):
    # Preserve Leaflet's SW, NW, NE, SE corner ordering.
    width, height = (4, 4) if square else (8, 4)
    polygon = Polygon([(0, 0), (0, height), (width, height), (width, 0)])
    world = Affine.translation(500000, 4500000) * Affine.rotation(angle)
    polygon = affine_transform(polygon, SamplingFrame._coefficients(world))
    to_lonlat = Transformer.from_crs("EPSG:26915", "EPSG:4326", always_xy=True)
    ring = [list(to_lonlat.transform(x, y)) for x, y in polygon.exterior.coords]
    metadata = {
        "crs": "EPSG:26915",
        "transform": world * Affine.translation(0, height) * Affine.scale(.02, -.02),
        "resolution": (.02, .02),
        "polygon_geojson": {
            "type": "Polygon", "coordinates": [ring],
            "horizontal_edge_index": 1, "road_direction": direction,
        },
    }
    return polygon, metadata


class SamplingFrameTests(unittest.TestCase):
    def test_directions_follow_rotation_including_squares_and_right_angles(self):
        for square in (False, True):
            for angle in (0, 30, -35, 90, 135, 180):
                for direction in ("horizontal", "vertical"):
                    with self.subTest(square=square, angle=angle, direction=direction):
                        polygon, metadata = fixture(angle, direction, square)
                        frame = SamplingFrame(polygon, metadata)
                        a = frame.to_world * (0, 0)
                        b = frame.to_world * (1, 0)
                        actual = np.array(b) - a
                        target_angle = np.deg2rad(angle + (90 if direction == "vertical" else 0))
                        target = np.array([np.cos(target_angle), np.sin(target_angle)])
                        self.assertAlmostEqual(abs(np.dot(actual, target)), 1, places=7)
                        self.assertAlmostEqual(frame.polygon.area, polygon.area, places=6)

    def test_rotated_samples_read_original_raster_pixels(self):
        for angle in (0, 30, 90, -55):
            for direction in ("horizontal", "vertical"):
                polygon, metadata = fixture(angle, direction)
                frame = SamplingFrame(polygon, metadata)
                for row, col in ((10, 20), (80, 150), (150, 300)):
                    world_point = metadata["transform"] * (col + .5, row + .5)
                    local_point = frame.to_local * world_point
                    actual = rowcol(frame.metadata["transform"], *local_point)
                    self.assertEqual(actual, (row, col))

    def test_overlay_round_trip_and_clipped_line_spacing(self):
        for direction in ("horizontal", "vertical"):
            polygon, metadata = fixture(37, direction)
            frame = SamplingFrame(polygon, metadata)
            self.assertLess(frame.world_geometry(frame.polygon).hausdorff_distance(polygon), 1e-8)
            minimum_x, minimum_y, maximum_x, maximum_y = frame.polygon.bounds
            # Rut/crown transects: local Y. Corrugation transects: local X.
            cross = LineString([(0, minimum_y - 1), (0, maximum_y + 1)]).intersection(frame.polygon)
            along = LineString([(minimum_x - 1, 0), (maximum_x + 1, 0)]).intersection(frame.polygon)
            cross_world, along_world = frame.world_geometry(cross), frame.world_geometry(along)
            cross_vector = np.diff(np.array(cross_world.coords), axis=0)[0]
            along_vector = np.diff(np.array(along_world.coords), axis=0)[0]
            self.assertAlmostEqual(np.dot(cross_vector, along_vector), 0, places=6)
            self.assertLess(cross_world.difference(polygon.buffer(1e-8)).length, 1e-8)
            shifted = frame.world_geometry(LineString([(.25, minimum_y), (.25, maximum_y)]))
            self.assertAlmostEqual(cross_world.distance(shifted), .25, places=7)
            lon, lat = frame.transform(*cross.coords[0])
            expected = Transformer.from_crs(metadata["crs"], "EPSG:4326", always_xy=True).transform(*cross_world.coords[0])
            np.testing.assert_allclose([lon, lat], expected, atol=1e-10)
            # Shapely overlay reprojection also passes sequences, not just scalars.
            x, y = zip(*cross.coords)
            lon, lat = frame.transform(x, y)
            self.assertEqual(len(lon), 2)

    def test_missing_direction_defaults_to_horizontal(self):
        polygon, metadata = fixture(25)
        del metadata["polygon_geojson"]["road_direction"]
        frame = SamplingFrame(polygon, metadata)
        self.assertEqual(frame.road_direction, "horizontal")
        self.assertAlmostEqual(frame.angle_degrees, 25, places=7)

    def test_pixel_boundary_roundoff_does_not_create_false_profile_steps(self):
        self.assertEqual(sample_rowcol(Affine.identity(), 20 - 1e-9, 10 + 1e-9), (10, 20))
        self.assertEqual(sample_rowcol(Affine.identity(), 19.9, 10.2), (10, 19))


class AnalysisSamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Package initializers import Celery tasks. Keep their configuration and
        # S3 clients isolated; these tests use synthetic data and no services.
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "SECRET_KEY": "test-only",
            "S3_BUCKET_NAME": "test", "S3_BUCKET_RAW": "test",
            "AWS_CLOUDFRONT_DOMAIN": "test.invalid",
            "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
        }), patch("boto3.client"):
            from app.workers.rut.detection import analyze_ruts_in_polygon
            from app.workers.crown.detection import analyze_crown_in_polygon
            from app.workers.corrugation.detection import analyze_corrugation_in_polygon
        cls.rut = staticmethod(analyze_ruts_in_polygon)
        cls.crown = staticmethod(analyze_crown_in_polygon)
        cls.corrugation = staticmethod(analyze_corrugation_in_polygon)

    def analyze(self, kind, direction="horizontal", angle=0):
        polygon, metadata = fixture(angle, direction)
        rows, cols = np.indices((200, 400))
        # A uniform road with repeated depressions across Y, waves along X.
        coordinate = cols * .02 if kind == "corrugation" else rows * .02
        data = 100 + .03 * np.cos(2 * np.pi * coordinate / .8)
        if kind == "rut":
            return self.rut(data, metadata, polygon, 100, .25, "test")
        if kind == "crown":
            return self.crown(data, metadata, polygon, .25, 100, "test")
        return self.corrugation(data, metadata, polygon, .25, 100, "test", sigma_samples=.5)

    def test_direction_swaps_profiles_for_all_three_analyses(self):
        for kind in ("rut", "crown", "corrugation"):
            with self.subTest(kind=kind):
                horizontal = self.analyze(kind)
                vertical = self.analyze(kind, "vertical")
                if kind == "rut":
                    self.assertGreater(horizontal["total_ruts_detected"], 0)
                    self.assertEqual(vertical["total_ruts_detected"], 0)
                elif kind == "corrugation":
                    self.assertGreater(horizontal["total_area_ft2"], 0)
                    self.assertEqual(vertical["total_area_ft2"], 0)
                else:
                    self.assertGreater(horizontal["profiles"][0]["rut_depth_in"], 0)
                    self.assertEqual(vertical["profiles"][0]["rut_depth_in"], 0)

    def test_rotation_preserves_measurements_and_rotates_overlays(self):
        for kind in ("rut", "crown", "corrugation"):
            baseline = self.analyze(kind)
            key = {"rut": "total_area_sqft", "crown": "total_linear_ft", "corrugation": "total_area_ft2"}[kind]
            for angle in (30, -35, 90, 135):
                with self.subTest(kind=kind, angle=angle):
                    rotated = self.analyze(kind, angle=angle)
                    self.assertAlmostEqual(rotated[key], baseline[key], delta=baseline[key] * .01)
                    features = rotated.get("ruts", rotated.get("all_segments"))
                    self.assertTrue(features)
                    if kind == "crown":
                        ring = features[0]["geometry"]["coordinates"][0]
                    else:
                        ring = features[0]["rect_coords"]
                    self.assertTrue(all(-94 < lon < -92 and 39 < lat < 42 for lon, lat in ring))


if __name__ == "__main__":
    unittest.main()
