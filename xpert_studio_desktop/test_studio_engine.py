"""
Unit Test Suite for Xpert Structural Design Studio (v1.3.0-smart-cad-intelligence)
"""

import os
import shutil
import tempfile
import unittest

from xpert_project_io import (
    MASTER_FILE_EXT,
    initialize_studio_project,
    load_studio_project_from_master_file,
    compute_smart_beam_tag_position,
    import_arch_dxf_underlay,
)
from xpert_structural_engine import (
    evaluate_story_thickness_and_optimization,
    analyze_all_story_beams_and_columns,
    enforce_column_inside_slab_boundary,
    check_duplicate_column,
    validate_and_build_beam_with_cantilevers,
    detect_story_grid_bays,
    pick_area_create_or_update_slab,
    reconcile_and_split_slabs_after_beam_change,
    auto_fill_all_story_slabs,
    rotate_column_90_deg,
    toggle_slab_rib_by_label_click,
    delete_selected_element_from_story,
)


class TestXpertStudioEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="xpert_studio_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_project_initialization_custom_xpert_master_and_no_duplicates(self):
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
        self.assertTrue(master["master_file"].endswith(f"TestTower-00_Project_Master{MASTER_FILE_EXT}"))
        self.assertTrue(os.path.isfile(master["master_file"]))

        # Verify loading existing project via .xpert master file
        loaded = load_studio_project_from_master_file(master["master_file"])
        self.assertEqual(loaded["project_name"], "TestTower")
        self.assertEqual(loaded["loads_and_defaults"]["default_column_b_m"], 0.20)
        self.assertEqual(loaded["loads_and_defaults"]["default_column_h_m"], 0.40)

        cad_dir = os.path.join(proj_dir, "CAD_Drawings")
        cad_files = sorted(os.listdir(cad_dir))
        self.assertEqual(
            cad_files,
            [
                "TestTower-00_TieBeams.dxf",
                "TestTower-02_Ground_Floor.dxf",
                "TestTower-Foundations_And_Axes.dxf",
            ],
        )

        # Verify Architectural DXF Block Underlay Import
        dxf_path = os.path.join(cad_dir, "TestTower-02_Ground_Floor.dxf")
        underlay = import_arch_dxf_underlay(dxf_path)
        self.assertTrue(underlay["visible"])
        self.assertIn("segments", underlay)

    def test_smart_drop_beam_optimization_suggestion(self):
        story = {
            "story_type": "ground",
            "slabs": [{"id": "S1", "axis_span_m": 4.0, "left_support_w_m": 0.20, "right_support_w_m": 0.20}],
            "beams": [
                {
                    "id": "B1",
                    "beam_kind": "hidden",
                    "spans": [6.2],
                    "supports": [{"width_m": 0.20}, {"width_m": 0.20}],
                }
            ],
        }
        res = evaluate_story_thickness_and_optimization(story, fy_mpa=350.0)
        self.assertTrue(res["has_data"])
        self.assertGreater(res["calculated_min_thickness_cm"], 30.0)
        self.assertIsNotNone(res["smart_optimization"])
        self.assertEqual(res["smart_optimization"]["beam_id"], "B1")

    def test_beam_tag_near_midpoint_and_slightly_above_beam_width(self):
        columns = [
            {"id": "C1", "x": 0.0, "y": 8.0, "b_m": 0.20, "h_m": 0.40},
            {"id": "C2", "x": 6.0, "y": 8.0, "b_m": 0.20, "h_m": 0.40},
        ]
        beam = {
            "id": "B1",
            "width_m": 0.40,
            "start_x": 0.0,
            "start_y": 8.0,
            "end_x": 6.0,
            "end_y": 8.0,
            "spans": [6.0],
        }
        placed = []
        tx, ty, rot = compute_smart_beam_tag_position(beam, columns, placed)
        self.assertAlmostEqual(tx, 3.0, places=2)
        self.assertAlmostEqual(ty, 8.0 + 0.20 + 0.12, places=2)
        self.assertEqual(rot, 0.0)

    def test_analyze_all_beams_and_4way_column_framing(self):
        story = {
            "height_m": 3.2,
            "columns": [
                {"id": "C1", "x": 0.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
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
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20},
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

    def test_column_boundary_clamp_and_expand_modes(self):
        poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]]
        col_outside = {"id": "C1", "x": 10.5, "y": 8.2, "b_m": 0.20, "h_m": 0.40, "active": True}

        # Mode A: Clamp flush inside boundary (max_x - 0.10 = 9.90, max_y - 0.20 = 7.80)
        clamped_col, same_poly, _ = enforce_column_inside_slab_boundary(col_outside, poly, mode="clamp")
        self.assertAlmostEqual(clamped_col["x"], 9.90, places=2)
        self.assertAlmostEqual(clamped_col["y"], 7.80, places=2)
        self.assertEqual(same_poly, poly)

        # Mode B: Expand slab boundary to contain column outer faces (10.5 + 0.10 = 10.60, 8.2 + 0.20 = 8.40)
        kept_col, exp_poly, _ = enforce_column_inside_slab_boundary(col_outside, poly, mode="expand")
        self.assertAlmostEqual(kept_col["x"], 10.5, places=2)
        self.assertAlmostEqual(max(p[0] for p in exp_poly), 10.60, places=2)
        self.assertAlmostEqual(max(p[1] for p in exp_poly), 8.40, places=2)

    def test_duplicate_column_and_beam_prevention(self):
        poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]]
        cols = [
            {"id": "C1", "x": 0.10, "y": 7.80, "b_m": 0.20, "h_m": 0.40, "active": True},
            {"id": "C2", "x": 5.00, "y": 7.80, "b_m": 0.20, "h_m": 0.40, "active": True},
        ]
        dup_col_id = check_duplicate_column(0.12, 7.78, 0.20, 0.40, cols)
        self.assertEqual(dup_col_id, "C1")

        ok1, bm1, _ = validate_and_build_beam_with_cantilevers(
            "B1", (0.10, 7.80), (5.00, 7.80), "hidden", 0.40, 0.30, cols, [], poly
        )
        self.assertTrue(ok1)

        # Attempt to draw another beam right over B1 -> Must be blocked!
        ok_dup, bm_dup, msg_dup = validate_and_build_beam_with_cantilevers(
            "B2", (0.10, 7.80), (5.00, 7.80), "drop", 0.20, 0.50, cols, [bm1], poly
        )
        self.assertFalse(ok_dup)
        self.assertIsNone(bm_dup)
        self.assertIn("Duplicate", msg_dup)

    def test_zero_sliver_bays_and_dynamic_9m_to_4_5m_slab_splitting(self):
        # 1. Start with a single 9.0m x 5.0m bay with perimeter beams shifted inward by half-width
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [9.0, 0.0], [9.0, 5.0], [0.0, 5.0]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 4.80, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 4.50, "y": 4.80, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 8.90, "y": 4.80, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 4.50, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C6", "x": 8.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {"id": "B1", "start_x": 0.10, "start_y": 4.80, "end_x": 8.90, "end_y": 4.80, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B2", "start_x": 0.10, "start_y": 0.20, "end_x": 8.90, "end_y": 0.20, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B3", "start_x": 0.10, "start_y": 0.20, "end_x": 0.10, "end_y": 4.80, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B4", "start_x": 8.90, "start_y": 0.20, "end_x": 8.90, "end_y": 4.80, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
        }

        # Verify zero sliver bays: only 1 structural bay (9.0m x 5.0m) exists!
        bays_before = detect_story_grid_bays(story)
        self.assertEqual(len(bays_before), 1)
        self.assertAlmostEqual(bays_before[0]["lx_m"], 9.0, places=2)
        self.assertAlmostEqual(bays_before[0]["ly_m"], 5.0, places=2)

        # Create 9.0m horizontal rib slab (0 deg)
        ok_s1, _, s1 = pick_area_create_or_update_slab(story, 4.5, 2.5, target_mode="SLAB")
        self.assertTrue(ok_s1)
        s1["rib_direction_deg"] = 0
        s1["axis_span_m"] = 9.0
        self.assertEqual(len(story["slabs"]), 1)

        # 2. Now draw a new intermediate vertical beam at x = 4.50m dividing the 9.0m slab in half!
        story["beams"].append(
            {"id": "B5", "start_x": 4.50, "start_y": 0.20, "end_x": 4.50, "end_y": 4.80, "width_m": 0.40, "beam_kind": "hidden"}
        )
        split_count, split_msg = reconcile_and_split_slabs_after_beam_change(story)
        self.assertEqual(split_count, 2)
        self.assertIn("Automatically split", split_msg)
        self.assertEqual(len(story["slabs"]), 2)
        self.assertAlmostEqual(story["slabs"][0]["lx_m"], 4.5, places=2)
        self.assertAlmostEqual(story["slabs"][1]["lx_m"], 4.5, places=2)
        self.assertAlmostEqual(story["slabs"][0]["axis_span_m"], 4.5, places=2)
        self.assertAlmostEqual(story["slabs"][1]["axis_span_m"], 4.5, places=2)

    def test_rotate_column_and_auto_fill_slabs(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 7.80, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {"id": "B1", "start_x": 0.10, "start_y": 7.80, "end_x": 9.90, "end_y": 7.80, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B2", "start_x": 0.10, "start_y": 4.00, "end_x": 9.90, "end_y": 4.00, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B3", "start_x": 0.10, "start_y": 0.20, "end_x": 9.90, "end_y": 0.20, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B4", "start_x": 0.10, "start_y": 0.20, "end_x": 0.10, "end_y": 7.80, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B5", "start_x": 5.00, "start_y": 0.20, "end_x": 5.00, "end_y": 7.80, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B6", "start_x": 9.90, "start_y": 0.20, "end_x": 9.90, "end_y": 7.80, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
        }

        ok_rot, _ = rotate_column_90_deg(story, "C1")
        self.assertTrue(ok_rot)
        self.assertAlmostEqual(story["columns"][0]["b_m"], 0.40, places=2)
        self.assertAlmostEqual(story["columns"][0]["h_m"], 0.20, places=2)

        added, _ = auto_fill_all_story_slabs(story)
        self.assertEqual(added, 4)
        self.assertEqual(len(story["slabs"]), 4)

    def test_pick_area_and_direct_click_on_rib_label_and_delete_selected(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [6.0, 0.0], [6.0, 6.5], [0.0, 6.5]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {"id": "B1", "start_x": 0.0, "start_y": 0.10, "end_x": 6.0, "end_y": 0.10, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B2", "start_x": 0.0, "start_y": 4.50, "end_x": 6.0, "end_y": 4.50, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B3", "start_x": 0.10, "start_y": 0.0, "end_x": 0.10, "end_y": 6.50, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B4", "start_x": 5.90, "start_y": 0.0, "end_x": 5.90, "end_y": 6.50, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
        }

        # 1. Pick lower 4-beam bay (Lx=6.0m, Ly=4.5m) -> default rib direction = 90 deg (shorter span)
        ok1, _, slb1 = pick_area_create_or_update_slab(story, 3.0, 2.0, target_mode="SLAB")
        self.assertTrue(ok1)
        self.assertEqual(slb1["rib_direction_deg"], 90)

        # 2. Click directly on/near the Slab Rib Label at center (3.0, 2.25) -> flips to 0 deg!
        ok_lbl, _, slb_flipped = toggle_slab_rib_by_label_click(story, 3.0, 2.25)
        self.assertTrue(ok_lbl)
        self.assertEqual(slb_flipped["rib_direction_deg"], 0)

        # 3. Pick upper 3-beam bay -> default 0 deg; then click its label at (3.0, 5.5) -> flips to 90 deg Cantilever
        # and automatically aligns lower back-span slab back to 90 deg!
        pick_area_create_or_update_slab(story, 3.0, 5.5, target_mode="SLAB")
        ok_cant, _, slb2_cant = toggle_slab_rib_by_label_click(story, 3.0, 5.5)
        self.assertTrue(ok_cant)
        self.assertEqual(slb2_cant["rib_direction_deg"], 90)
        self.assertTrue(slb2_cant["is_cantilever"])
        self.assertEqual(story["slabs"][0]["rib_direction_deg"], 90)

        # 4. Delete Selected Column C1
        ok_del, _ = delete_selected_element_from_story(story, "column", "C1")
        self.assertTrue(ok_del)
        self.assertEqual(len(story["columns"]), 0)


if __name__ == "__main__":
    unittest.main()
