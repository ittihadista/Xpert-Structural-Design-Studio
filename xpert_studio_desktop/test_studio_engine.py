"""
Unit Test Suite for Xpert Structural Design Studio (v1.0.0)
"""

import os
import shutil
import tempfile
import unittest

from xpert_project_io import (
    initialize_studio_project,
    load_studio_project_from_master_file,
    compute_smart_beam_tag_position,
    import_arch_dxf_underlay,
)
from xpert_structural_engine import (
    evaluate_story_thickness_and_optimization,
    analyze_all_story_beams_and_columns,
    check_duplicate_column,
    check_duplicate_beam,
    clamp_or_expand_column_boundary,
    rotate_column_90_deg,
    clamp_beam_inside_boundary,
    validate_beam_cantilevers_and_boundary,
    validate_and_build_beam_with_cantilevers,
    detect_bays_and_determine_ribs,
    detect_story_grid_bays,
    reconcile_and_split_slabs_after_beam_change,
    auto_fill_all_story_slabs,
    pick_area_slab,
    flip_rib_direction_with_equilibrium,
    toggle_bay_slab_or_opening,
    move_column_and_update_connected_beams,
    move_beam_and_update,
    delete_selected_element_from_story,
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
        # Tag is near beam midpoint (length * 0.5 = 5.0) and shifted slightly along axis to avoid C2
        dist_from_c2 = ((tx - 5.0) ** 2 + (ty - 8.5) ** 2) ** 0.5
        self.assertGreaterEqual(dist_from_c2, 0.45)
        self.assertLess(abs(tx - 5.0), 1.5)
        # Tag is placed above upper face of beam (offset = width_m/2 + 0.12)
        self.assertGreater(ty, 8.5)
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

    def test_xpert_master_file_saving_and_loading(self):
        cfg = {
            "project_name": "RoyalVilla",
            "root_directory": self.tmp_dir,
            "ground_floor_height_m": 3.20,
            "include_basement": False,
            "floors_above_ground": 2,
            "include_penthouse": False,
            "foundation_depth_m": 1.50,
            "fc_mpa": 25.0,
            "fy_mpa": 420.0,
            "soil_bearing_qall_kn_m2": 200.0,
        }
        master = initialize_studio_project(cfg)
        proj_dir = master["project_dir"]
        xpert_file = os.path.join(proj_dir, "RoyalVilla-00_Project_Master.xpert")
        json_file = os.path.join(proj_dir, "RoyalVilla-00_Project_Master.json")

        self.assertTrue(os.path.isfile(xpert_file))
        self.assertTrue(os.path.isfile(json_file))

        # Test loading from .xpert
        loaded = load_studio_project_from_master_file(xpert_file)
        self.assertEqual(loaded["project_name"], "RoyalVilla")
        self.assertEqual(len(loaded["stories"]), 3)  # 00_TieBeams, 02_Ground_Floor, 03_Typical_Floor (multiplier=2)
        self.assertEqual(loaded["stories"][2]["multiplier"], 2)
        for st in loaded["stories"]:
            self.assertTrue(os.path.isfile(st["json_file"]))
            self.assertTrue(os.path.isfile(st["dxf_file"]))

    def test_clamp_beam_inside_boundary(self):
        edge = [[0.0, 0.0], [10.0, 0.0], [10.0, 8.5], [0.0, 8.5]]
        # 1. Drop beam (w=0.20m, half_w=0.10m) drawn along top boundary line y=8.5
        top_beam = {
            "id": "B_top",
            "beam_kind": "drop",
            "width_m": 0.20,
            "depth_m": 0.50,
            "start_x": 0.0,
            "start_y": 8.5,
            "end_x": 10.0,
            "end_y": 8.5,
        }
        clamped_top, mod_top = clamp_beam_inside_boundary(top_beam, edge)
        self.assertTrue(mod_top)
        # Shifted inward by 0.10m from 8.5 -> 8.40 so top face is flush at 8.50
        self.assertEqual(clamped_top["start_y"], 8.40)
        self.assertEqual(clamped_top["end_y"], 8.40)

        # 2. Drop beam along right boundary x=10.0
        right_beam = {
            "id": "B_right",
            "beam_kind": "drop",
            "width_m": 0.20,
            "depth_m": 0.50,
            "start_x": 10.0,
            "start_y": 0.0,
            "end_x": 10.0,
            "end_y": 8.5,
        }
        clamped_right, mod_right = clamp_beam_inside_boundary(right_beam, edge)
        self.assertTrue(mod_right)
        self.assertEqual(clamped_right["start_x"], 9.90)
        self.assertEqual(clamped_right["end_x"], 9.90)

        # 3. Interior beam - not modified
        mid_beam = {
            "id": "B_mid",
            "beam_kind": "hidden",
            "width_m": 0.60,
            "depth_m": 0.30,
            "start_x": 0.0,
            "start_y": 4.25,
            "end_x": 10.0,
            "end_y": 4.25,
        }
        clamped_mid, mod_mid = clamp_beam_inside_boundary(mid_beam, edge)
        self.assertFalse(mod_mid)
        self.assertEqual(clamped_mid["start_y"], 4.25)

    def test_delete_selected_element_and_cantilever_protection(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [12.0, 0.0], [12.0, 6.0], [0.0, 6.0]],
            "columns": [
                {"id": "C1", "x": 0.0, "y": 3.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 6.0, "y": 3.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B1", "start_x": 0.0, "start_y": 3.0, "end_x": 12.0, "end_y": 3.0,
                    "spans": [6.0, 6.0],
                    "supports": [
                        {"support_index": 1, "target_id": "C1", "x": 0.0, "y": 3.0},
                        {"support_index": 2, "target_id": "C2", "x": 6.0, "y": 3.0},
                    ]
                }
            ],
            "slabs": [
                {"id": "S1_Back", "center_x": 3.0, "center_y": 3.0, "supports_cantilever_for": "S2_Cant"},
                {"id": "S2_Cant", "center_x": 9.0, "center_y": 3.0, "is_cantilever": True},
            ],
            "openings": [{"id": "OP1", "x1": 1.0, "y1": 1.0, "x2": 2.0, "y2": 2.0}],
        }

        # 1. Attempt to delete S1_Back (back-span anchor) MUST fail!
        ok, msg = delete_selected_element_from_story(story, {"type": "slab", "id": "S1_Back"})
        self.assertFalse(ok)
        self.assertIn("back-span moment anchor", msg)
        self.assertEqual(len(story["slabs"]), 2)

        # 2. Deleting cantilever slab S2_Cant succeeds
        ok2, msg2 = delete_selected_element_from_story(story, {"type": "slab", "id": "S2_Cant"})
        self.assertTrue(ok2)
        self.assertEqual(len(story["slabs"]), 1)

        # 3. Deleting column C2 updates beam B1 supports
        ok_col, msg_col = delete_selected_element_from_story(story, {"type": "column", "id": "C2"})
        self.assertTrue(ok_col)
        self.assertEqual(len(story["columns"]), 1)
        self.assertEqual(len(story["beams"][0]["supports"]), 1)

        # 4. Deleting beam B1 succeeds
        ok_bm, msg_bm = delete_selected_element_from_story(story, {"type": "beam", "id": "B1"})
        self.assertTrue(ok_bm)
        self.assertEqual(len(story["beams"]), 0)

        # 5. Deleting opening succeeds
        ok_op, msg_op = delete_selected_element_from_story(story, {"type": "opening", "id": "OP1"})
        self.assertTrue(ok_op)
        self.assertEqual(len(story["openings"]), 0)

    def test_default_column_dimensions_orientation(self):
        edge = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
        # Minimum column size: 0.20 x 0.40 (vertical) and 0.40 x 0.20 (horizontal)
        # Vertical column near right edge (10.0, 5.0)
        cx_v, cy_v, _, _ = clamp_or_expand_column_boundary(10.0, 5.0, 0.20, 0.40, edge, rule="clamp")
        self.assertEqual(cx_v, 9.90)  # 10.0 - 0.20 / 2
        self.assertEqual(cy_v, 5.0)

        # Horizontal column near right edge (10.0, 5.0)
        cx_h, cy_h, _, _ = clamp_or_expand_column_boundary(10.0, 5.0, 0.40, 0.20, edge, rule="clamp")
        self.assertEqual(cx_h, 9.80)  # 10.0 - 0.40 / 2
        self.assertEqual(cy_h, 5.0)

    def test_import_arch_dxf_underlay(self):
        import ezdxf
        test_dxf_path = os.path.join(self.tmp_dir, "Arch_Test_Plan.dxf")
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        msp.add_line((0, 0), (12.0, 0))
        msp.add_line((12.0, 0), (12.0, 8.0))
        msp.add_lwpolyline([(0, 0), (0, 8.0), (12.0, 8.0)])
        msp.add_circle((6.0, 4.0), radius=1.5)
        doc.saveas(test_dxf_path)

        res = import_arch_dxf_underlay(test_dxf_path)
        self.assertEqual(res["file_name"], "Arch_Test_Plan.dxf")
        self.assertTrue(res["visible"])
        self.assertGreater(len(res["segments"]), 0)
        self.assertEqual(len(res["circles"]), 1)
        self.assertEqual(res["circles"][0], [6.0, 4.0, 1.5])
        self.assertGreater(len(res["snap_points"]), 4)

    def test_check_duplicate_column_and_beam(self):
        cols = [
            {"id": "C1", "x": 5.0, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
        ]
        # Duplicate column at nearly identical coordinate
        ok_c, msg_c = check_duplicate_column(5.02, 4.98, 0.20, 0.40, cols)
        self.assertFalse(ok_c)
        self.assertIn("Duplicate Column Rejected", msg_c)

        # Non-duplicate column far away
        ok_c2, _ = check_duplicate_column(1.0, 1.0, 0.20, 0.40, cols)
        self.assertTrue(ok_c2)

        # Duplicate beam along same axis
        bms = [
            {"id": "B1", "start_x": 0.0, "start_y": 5.0, "end_x": 10.0, "end_y": 5.0, "width_m": 0.40}
        ]
        ok_b, msg_b = check_duplicate_beam(0.0, 5.0, 10.0, 5.0, bms)
        self.assertFalse(ok_b)
        self.assertIn("Duplicate Beam Rejected", msg_b)

        # Reverse axis duplicate
        ok_b_rev, _ = check_duplicate_beam(10.0, 5.0, 0.0, 5.0, bms)
        self.assertFalse(ok_b_rev)

        # Non-duplicate beam
        ok_b_new, _ = check_duplicate_beam(0.0, 8.0, 10.0, 8.0, bms)
        self.assertTrue(ok_b_new)

    def test_multi_span_beam_automatic_column_detection(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [12.0, 0.0], [12.0, 8.0], [0.0, 8.0]],
            "columns": [
                {"id": "C1", "x": 0.0, "y": 4.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.0, "y": 4.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 12.0, "y": 4.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [],
            "openings": [],
        }
        ok, msg, bm = validate_and_build_beam_with_cantilevers(
            (0.0, 4.0), (12.0, 4.0), "hidden", 0.40, 0.30, story
        )
        self.assertTrue(ok)
        self.assertIsNotNone(bm)
        self.assertEqual(len(bm["supports"]), 3)
        self.assertEqual(bm["supports"][1]["target_id"], "C2")
        self.assertEqual(bm["spans"], [5.0, 7.0])

    def test_zero_sliver_bays_under_85cm(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]],
            "beams": [
                {"id": "B_top", "beam_kind": "drop", "width_m": 0.20, "start_x": 0.0, "start_y": 7.85, "end_x": 10.0, "end_y": 7.85},
                {"id": "B_bot", "beam_kind": "drop", "width_m": 0.20, "start_x": 0.0, "start_y": 0.15, "end_x": 10.0, "end_y": 0.15},
                {"id": "B_mid", "beam_kind": "hidden", "width_m": 0.40, "start_x": 5.0, "start_y": 0.0, "end_x": 5.0, "end_y": 8.0},
            ],
            "slabs": [],
            "openings": [],
        }
        bays = detect_story_grid_bays(story)
        self.assertGreaterEqual(len(bays), 2)
        for b in bays:
            self.assertGreaterEqual(b["lx"], 0.85)
            self.assertGreaterEqual(b["ly"], 0.85)

    def test_reconcile_and_split_slabs_after_beam_change(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [12.0, 0.0], [12.0, 6.0], [0.0, 6.0]],
            "columns": [],
            "beams": [
                {"id": "B_left", "beam_kind": "drop", "width_m": 0.20, "start_x": 0.0, "start_y": 0.0, "end_x": 0.0, "end_y": 6.0},
                {"id": "B_right", "beam_kind": "drop", "width_m": 0.20, "start_x": 12.0, "start_y": 0.0, "end_x": 12.0, "end_y": 6.0},
            ],
            "slabs": [
                {
                    "id": "S1",
                    "polygon": [[0.0, 0.0], [12.0, 0.0], [12.0, 6.0], [0.0, 6.0]],
                    "center_x": 6.0,
                    "center_y": 3.0,
                    "axis_span_m": 6.0,
                    "rib_direction_deg": 90.0,
                }
            ],
            "openings": [],
        }
        story["beams"].append({
            "id": "B_mid",
            "beam_kind": "hidden",
            "width_m": 0.40,
            "start_x": 6.0,
            "start_y": 0.0,
            "end_x": 6.0,
            "end_y": 6.0,
        })
        split_slabs = reconcile_and_split_slabs_after_beam_change(story)
        self.assertEqual(len(split_slabs), 2)
        self.assertAlmostEqual(split_slabs[0]["lx"], 6.0, delta=0.2)
        self.assertAlmostEqual(split_slabs[1]["lx"], 6.0, delta=0.2)

    def test_rotate_column_90_deg(self):
        edge = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
        story = {
            "slab_edge_polygon": edge,
            "columns": [
                {"id": "C1", "x": 9.90, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [],
        }
        ok, msg = rotate_column_90_deg("C1", story, rule="clamp")
        self.assertTrue(ok)
        c1 = story["columns"][0]
        self.assertEqual(c1["b_m"], 0.40)
        self.assertEqual(c1["h_m"], 0.20)
        self.assertEqual(c1["x"], 9.80)
        self.assertEqual(c1["y"], 5.0)

    def test_auto_fill_all_story_slabs(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 6.0], [0.0, 6.0]],
            "beams": [
                {"id": "B1", "start_x": 0.0, "start_y": 0.0, "end_x": 10.0, "end_y": 0.0, "width_m": 0.20},
                {"id": "B2", "start_x": 0.0, "start_y": 6.0, "end_x": 10.0, "end_y": 6.0, "width_m": 0.20},
                {"id": "B3", "start_x": 0.0, "start_y": 0.0, "end_x": 0.0, "end_y": 6.0, "width_m": 0.20},
                {"id": "B4", "start_x": 10.0, "start_y": 0.0, "end_x": 10.0, "end_y": 6.0, "width_m": 0.20},
                {"id": "B_mid", "start_x": 5.0, "start_y": 0.0, "end_x": 5.0, "end_y": 6.0, "width_m": 0.40},
            ],
            "slabs": [],
            "openings": [],
        }
        count, msg = auto_fill_all_story_slabs(story)
        self.assertEqual(count, 2)
        self.assertEqual(len(story["slabs"]), 2)
        for s in story["slabs"]:
            self.assertIn(s["rib_direction_deg"], (0.0, 90.0))

    def test_demo_layout_column_full_containment(self):
        min_x, max_x = 0.0, 10.0
        min_y, max_y = 0.0, 8.5
        demo_cols = [
            {"id": "C1", "x": 0.10, "y": 8.30, "b_m": 0.20, "h_m": 0.40},
            {"id": "C2", "x": 5.00, "y": 8.30, "b_m": 0.20, "h_m": 0.40},
            {"id": "C3", "x": 9.90, "y": 8.30, "b_m": 0.20, "h_m": 0.40},
            {"id": "C4", "x": 0.10, "y": 4.25, "b_m": 0.20, "h_m": 0.40},
            {"id": "C5", "x": 5.00, "y": 4.25, "b_m": 0.20, "h_m": 0.40},
            {"id": "C6", "x": 9.90, "y": 4.25, "b_m": 0.20, "h_m": 0.40},
            {"id": "C7", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40},
            {"id": "C8", "x": 5.00, "y": 0.20, "b_m": 0.20, "h_m": 0.40},
            {"id": "C9", "x": 9.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40},
        ]
        for col in demo_cols:
            cx, cy = col["x"], col["y"]
            hb = col["b_m"] / 2.0
            hh = col["h_m"] / 2.0
            self.assertGreaterEqual(cx - hb, min_x - 1e-4, f"{col['id']} left edge out of bounds")
            self.assertLessEqual(cx + hb, max_x + 1e-4, f"{col['id']} right edge out of bounds")
            self.assertGreaterEqual(cy - hh, min_y - 1e-4, f"{col['id']} bottom edge out of bounds")
            self.assertLessEqual(cy + hh, max_y + 1e-4, f"{col['id']} top edge out of bounds")


if __name__ == "__main__":
    unittest.main()
