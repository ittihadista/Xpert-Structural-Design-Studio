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
    clamp_or_expand_column_boundary,
    validate_beam_cantilevers_and_boundary,
    detect_bays_and_determine_ribs,
    pick_area_slab,
    flip_rib_direction_with_equilibrium,
    toggle_bay_slab_or_opening,
    move_column_and_update_connected_beams,
    move_beam_and_update,
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

    def test_column_boundary_clamp_and_expand(self):
        edge = [[0.0, 0.0], [10.0, 0.0], [10.0, 8.5], [0.0, 8.5]]
        # 1. Clamp mode: column protruding outside top-right at (10.2, 8.4)
        cx, cy, poly, mod = clamp_or_expand_column_boundary(10.2, 8.4, 0.25, 0.50, edge, rule="clamp")
        self.assertTrue(mod)
        self.assertEqual(cx, 9.875)  # 10.0 - 0.25 / 2
        self.assertEqual(cy, 8.25)  # 8.5 - 0.50 / 2 = 8.25

        # 2. Expand mode: expands polygon to enclose column outer face
        cx2, cy2, exp_poly, mod2 = clamp_or_expand_column_boundary(10.2, 8.4, 0.25, 0.50, edge, rule="expand")
        self.assertTrue(mod2)
        self.assertGreaterEqual(exp_poly[1][0], 10.325)  # 10.2 + 0.25 / 2
        self.assertGreaterEqual(exp_poly[2][1], 8.65)   # 8.4 + 0.50 / 2

    def test_cantilever_beam_validation_free_end_vs_interior_rejection(self):
        edge = [[0.0, 0.0], [10.0, 0.0], [10.0, 8.5], [0.0, 8.5]]
        cols = [
            {"id": "C1", "x": 0.0, "y": 4.2, "b_m": 0.25, "h_m": 0.50, "active": True},
        ]
        # Invalid interior cantilever ending mid-slab at (4.0, 4.2) without support
        bad_beam = {"id": "B_bad", "start_x": 0.0, "start_y": 4.2, "end_x": 4.0, "end_y": 4.2}
        ok, msg = validate_beam_cantilevers_and_boundary(bad_beam, cols, [], edge)
        self.assertFalse(ok)
        self.assertIn("Invalid Interior Cantilever", msg)

        # Valid exterior cantilever extending to outer slab boundary edge at (10.0, 4.2)
        good_beam = {"id": "B_good", "start_x": 0.0, "start_y": 4.2, "end_x": 10.0, "end_y": 4.2}
        ok2, msg2 = validate_beam_cantilevers_and_boundary(good_beam, cols, [], edge)
        self.assertTrue(ok2)

    def test_pick_area_4beam_shorter_span_and_3beam_opposing_default(self):
        edge = [[0.0, 0.0], [12.0, 0.0], [12.0, 6.0], [0.0, 6.0]]
        beams = [
            {"id": "B_bot", "start_x": 0.0, "start_y": 0.0, "end_x": 12.0, "end_y": 0.0},
            {"id": "B_top", "start_x": 0.0, "start_y": 6.0, "end_x": 12.0, "end_y": 6.0},
            {"id": "B_left", "start_x": 0.0, "start_y": 0.0, "end_x": 0.0, "end_y": 6.0},
            {"id": "B_mid", "start_x": 5.0, "start_y": 0.0, "end_x": 5.0, "end_y": 6.0},
            {"id": "B_right", "start_x": 9.0, "start_y": 0.0, "end_x": 9.0, "end_y": 6.0},
        ]
        # Bay 1 (0..5, 0..6): 4 beams, Lx=5, Ly=6 -> shorter span along X (0 deg)
        ok1, msg1, slabs1, ops1 = pick_area_slab((2.5, 3.0), edge, beams, [])
        self.assertTrue(ok1)
        self.assertEqual(slabs1[0]["rib_direction_deg"], 0.0)

        # Bay 3 (9..12, 0..6): 3 beams, free edge at East -> opposing beams are North & South -> 90 deg
        ok3, msg3, slabs3, ops3 = pick_area_slab((10.5, 3.0), edge, beams, slabs1, ops1)
        self.assertTrue(ok3)
        s3 = [s for s in slabs3 if s["center_x"] > 9.0][0]
        self.assertEqual(s3["rib_direction_deg"], 90.0)

    def test_cantilever_slab_equilibrium_rule_and_back_span_collinear_forcing(self):
        edge = [[0.0, 0.0], [12.0, 0.0], [12.0, 6.0], [0.0, 6.0]]
        beams = [
            {"id": "B_bot", "start_x": 0.0, "start_y": 0.0, "end_x": 12.0, "end_y": 0.0},
            {"id": "B_top", "start_x": 0.0, "start_y": 6.0, "end_x": 12.0, "end_y": 6.0},
            {"id": "B_left", "start_x": 0.0, "start_y": 0.0, "end_x": 0.0, "end_y": 6.0},
            {"id": "B_mid", "start_x": 5.0, "start_y": 0.0, "end_x": 5.0, "end_y": 6.0},
            {"id": "B_right", "start_x": 9.0, "start_y": 0.0, "end_x": 9.0, "end_y": 6.0},
        ]
        # Initialize Bay 2 (5..9, 0..6) and Bay 3 (9..12, 0..6)
        _, _, slabs, ops = pick_area_slab((7.0, 3.0), edge, beams, [])
        _, _, slabs, ops = pick_area_slab((10.5, 3.0), edge, beams, slabs, ops)

        # Flip 3-beam bay (at 10.5, 3.0) to Cantilever Slab pointing East
        ok, msg, slabs = flip_rib_direction_with_equilibrium((10.5, 3.0), edge, beams, slabs, ops)
        self.assertTrue(ok)
        self.assertIn("Cantilever Slab", msg)

        cant = [s for s in slabs if s["center_x"] > 9.0][0]
        back = [s for s in slabs if 5.0 < s["center_x"] < 9.0][0]
        self.assertTrue(cant["is_cantilever"])
        self.assertEqual(cant["rib_direction_deg"], 0.0)
        # Back-span ribs MUST be forced to match (0 deg) for structural equilibrium
        self.assertEqual(back["rib_direction_deg"], 0.0)
        self.assertEqual(back["supports_cantilever_for"], cant["id"])

        # Attempt to convert back-span slab into an opening MUST be rejected!
        ok_op, msg_op, slabs, ops = toggle_bay_slab_or_opening((7.0, 3.0), edge, beams, slabs, ops)
        self.assertFalse(ok_op)
        self.assertIn("balancing back-span", msg_op)

    def test_move_column_and_beam_updating_connected_spans(self):
        edge = [[0.0, 0.0], [12.0, 0.0], [12.0, 10.0], [0.0, 10.0]]
        cols = [
            {"id": "C1", "x": 0.0, "y": 5.0, "b_m": 0.25, "h_m": 0.50, "active": True},
            {"id": "C2", "x": 5.0, "y": 5.0, "b_m": 0.25, "h_m": 0.50, "active": True},
            {"id": "C3", "x": 10.0, "y": 5.0, "b_m": 0.25, "h_m": 0.50, "active": True},
        ]
        beams = [
            {
                "id": "B1", "start_x": 0.0, "start_y": 5.0, "end_x": 10.0, "end_y": 5.0,
                "spans": [5.0, 5.0],
                "supports": [
                    {"support_index": 1, "target_id": "C1", "x": 0.0, "y": 5.0},
                    {"support_index": 2, "target_id": "C2", "x": 5.0, "y": 5.0},
                    {"support_index": 3, "target_id": "C3", "x": 10.0, "y": 5.0},
                ]
            }
        ]
        # Move C2 from (5.0, 5.0) to (6.0, 5.0)
        ok, msg, new_cols, new_bms, _ = move_column_and_update_connected_beams(
            "C2", 6.0, 5.0, cols, beams, edge, rule="clamp"
        )
        self.assertTrue(ok)
        self.assertEqual(new_bms[0]["spans"], [6.0, 4.0])

        # Move beam B1 by dx=0, dy=1.0 within edge
        ok_bm, msg_bm, bms2 = move_beam_and_update("B1", 0.0, 1.0, new_bms, edge)
        self.assertTrue(ok_bm)
        self.assertEqual(bms2[0]["start_y"], 6.0)


if __name__ == "__main__":
    unittest.main()
