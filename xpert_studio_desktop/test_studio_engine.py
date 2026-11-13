"""
Unit Test Suite for Xpert Structural Design Studio (v1.0.0)
"""

import os
import shutil
import tempfile
import unittest

from xpert_project_io import (
    initialize_studio_project,
    compute_smart_beam_tag_position,
)
from xpert_structural_engine import (
    evaluate_story_thickness_and_optimization,
    analyze_all_story_beams_and_columns,
)


class TestXpertStudioEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="xpert_studio_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_project_initialization_and_no_duplicates(self):
        cfg = {
            "project_name": "TestTower",
            "root_directory": self.tmp_dir,
            "ground_floor_height_m": 3.20,
            "include_basement": False,
            "floors_above_ground": 0,
            "include_penthouse": False,
            "foundation_depth_m": 1.50,
            "fc_mpa": 25.0,
            "fy_mpa": 420.0,
            "soil_bearing_qall_kn_m2": 200.0,
        }
        master = initialize_studio_project(cfg)
        proj_dir = master["project_dir"]
        cad_dir = os.path.join(proj_dir, "CAD_Drawings")
        cad_files = sorted(os.listdir(cad_dir))
        # Must ONLY have TestTower- prefixed files, and no duplicate Roof floor when floors_above_ground = 0
        self.assertEqual(
            cad_files,
            [
                "TestTower-00_TieBeams.dxf",
                "TestTower-02_Ground_Floor.dxf",
                "TestTower-Foundations_And_Axes.dxf",
            ],
        )

    def test_smart_drop_beam_optimization_suggestion(self):
        story = {
            "story_type": "ground",
            "slabs": [{"id": "S1", "axis_span_m": 4.0, "left_support_w_m": 0.25, "right_support_w_m": 0.25}],
            "beams": [
                {
                    "id": "B1",
                    "beam_kind": "hidden",
                    "spans": [6.2],
                    "supports": [{"width_m": 0.25}, {"width_m": 0.25}],
                }
            ],
        }
        res = evaluate_story_thickness_and_optimization(story, fy_mpa=350.0)
        self.assertTrue(res["has_data"])
        self.assertGreater(res["calculated_min_thickness_cm"], 30.0)
        self.assertIsNotNone(res["smart_optimization"])
        self.assertEqual(res["smart_optimization"]["beam_id"], "B1")

    def test_non_overlapping_beam_tag_on_2span_beam_with_middle_column(self):
        columns = [
            {"id": "C1", "x": 0.0, "y": 8.5, "b_m": 0.25, "h_m": 0.50},
            {"id": "C2", "x": 5.0, "y": 8.5, "b_m": 0.25, "h_m": 0.50},
            {"id": "C3", "x": 10.0, "y": 8.5, "b_m": 0.25, "h_m": 0.50},
        ]
        beam = {
            "id": "B1",
            "start_x": 0.0,
            "start_y": 8.5,
            "end_x": 10.0,
            "end_y": 8.5,
            "spans": [5.0, 5.0],
        }
        placed = [(5.0 + 0.245, 8.5 + 0.37)]  # C2 tag position
        tx, ty, rot = compute_smart_beam_tag_position(beam, columns, placed)
        # Distance from middle column C2 (5.0, 8.5) must be >= 1.5m (placed in first clear span)
        dist_from_c2 = ((tx - 5.0) ** 2 + (ty - 8.5) ** 2) ** 0.5
        self.assertGreater(dist_from_c2, 1.5)
        self.assertEqual(rot, 0.0)

    def test_analyze_all_beams_and_4way_column_framing(self):
        story = {
            "height_m": 3.2,
            "columns": [
                {"id": "C1", "x": 0.0, "y": 0.0, "b_m": 0.25, "h_m": 0.50, "active": True},
                {"id": "C2", "x": 5.0, "y": 0.0, "b_m": 0.25, "h_m": 0.50, "active": True},
            ],
            "beams": [
                {
                    "id": "B1",
                    "beam_kind": "drop",
                    "width_m": 0.20,
                    "depth_m": 0.50,
                    "start_x": 0.0,
                    "start_y": 0.0,
                    "end_x": 5.0,
                    "end_y": 0.0,
                    "spans": [5.0],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.25},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.25},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 5.0, "val": 24.0}],
                }
            ],
        }
        bundle = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        self.assertIn("B1", bundle["beam_results"])
        self.assertEqual(len(bundle["column_records"]), 2)
        c1_rec = bundle["column_records"][0]
        self.assertIsNotNone(c1_rec["framing_4way"]["East"])
        self.assertGreater(len(c1_rec["design"]["pm_curve_points"]), 2)


if __name__ == "__main__":
    unittest.main()
