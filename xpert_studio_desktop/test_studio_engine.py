"""
Unit Test Suite for Xpert Structural Design Studio (v1.5.0-structural-bim-pro)
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
    select_elements_by_box,
    align_element_face_to_reference,
    move_selected_elements_by_delta,
    measure_distance_2d,
    create_linear_dimension,
    auto_generate_exterior_dimensions,
    get_beam_span_segments,
    set_story_wall_load_policy,
    set_beam_span_wall_flag,
    convert_beam_kind_and_section,
)


class TestXpertStudioEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="xpert_studio_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_project_initialization_custom_xsd_master_and_no_duplicates(self):
        self.assertEqual(MASTER_FILE_EXT, ".xsd")
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
        self.assertTrue(master["master_file"].endswith("TestTower-00_Project_Master.xsd"))
        self.assertTrue(os.path.isfile(master["master_file"]))

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

        dxf_path = os.path.join(cad_dir, "TestTower-02_Ground_Floor.dxf")
        underlay = import_arch_dxf_underlay(dxf_path)
        self.assertTrue(underlay["visible"])
        self.assertIn("segments", underlay)

    def test_full_column_outer_face_beam_extension_and_duplicate_prevention(self):
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
        self.assertAlmostEqual(bm1["start_x"], 0.00, places=2)
        self.assertAlmostEqual(bm1["end_x"], 5.10, places=2)
        self.assertEqual(bm1["spans"], [4.9])
        self.assertEqual(bm1["cantilever_left_m"], 0.0)
        self.assertEqual(bm1["cantilever_right_m"], 0.0)

        ok_dup, bm_dup, msg_dup = validate_and_build_beam_with_cantilevers(
            "B2", (0.10, 7.80), (5.00, 7.80), "drop", 0.20, 0.50, cols, [bm1], poly
        )
        self.assertFalse(ok_dup)
        self.assertIsNone(bm_dup)
        self.assertIn("Duplicate", msg_dup)

    def test_true_physical_room_merging_no_phantom_slab_splitting(self):
        """
        Verifies Eng. Yousef's critical bug report:
        When a partial beam (e.g., stair trimmer beam B8 at Y=4.0m only inside the RIGHT bay X=[5.0, 9.0])
        is drawn, the LEFT bay X=[0.0, 5.0], Y=[0.0, 8.0] has NO horizontal beam at Y=4.0m and MUST
        remain a single unified room (NOT split into two slabs!).
        """
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [9.0, 0.0], [9.0, 8.0], [0.0, 8.0]],
            "columns": [],
            "beams": [
                # Outer perimeter beams
                {"id": "B1", "start_x": 0.0, "start_y": 8.0, "end_x": 9.0, "end_y": 8.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B2", "start_x": 0.0, "start_y": 0.0, "end_x": 9.0, "end_y": 0.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B3", "start_x": 0.0, "start_y": 0.0, "end_x": 0.0, "end_y": 8.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B4", "start_x": 9.0, "start_y": 0.0, "end_x": 9.0, "end_y": 8.0, "width_m": 0.20, "beam_kind": "drop"},
                # Central vertical dividing beam at X = 5.0m
                {"id": "B5", "start_x": 5.0, "start_y": 0.0, "end_x": 5.0, "end_y": 8.0, "width_m": 0.20, "beam_kind": "drop"},
                # Partial horizontal stair beam ONLY in the right bay X=[5.0, 9.0] at Y=4.0m
                {"id": "B8", "start_x": 5.0, "start_y": 4.0, "end_x": 9.0, "end_y": 4.0, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
        }
        bays = detect_story_grid_bays(story)
        # Must produce exactly 3 physical rooms:
        # 1 full room on the left: X=[0, 5], Y=[0, 8]
        # 2 half rooms on the right: X=[5, 9], Y=[0, 4] and X=[5, 9], Y=[4, 8]
        self.assertEqual(len(bays), 3)
        left_bays = [b for b in bays if abs(b["min_x"] - 0.0) < 0.05 and abs(b["max_x"] - 5.0) < 0.05]
        self.assertEqual(len(left_bays), 1)
        self.assertAlmostEqual(left_bays[0]["min_y"], 0.0, places=2)
        self.assertAlmostEqual(left_bays[0]["max_y"], 8.0, places=2)

    def test_cantilever_and_backspan_bidirectional_continuity(self):
        """
        Verifies that picking a cantilever slab (or picking its back-span slab after the cantilever)
        automatically aligns BOTH the cantilever slab and its adjacent back-span slab perpendicular
        to the supporting beam.
        """
        story = {
            "slab_edge_polygon": [[0.0, -1.6], [3.0, -1.6], [3.0, 5.0], [0.0, 5.0]],
            "columns": [],
            "beams": [
                {"id": "B_TOP", "start_x": 0.0, "start_y": 5.0, "end_x": 3.0, "end_y": 5.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_BOT", "start_x": 0.0, "start_y": 0.0, "end_x": 3.0, "end_y": 0.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_LEFT", "start_x": 0.0, "start_y": -1.6, "end_x": 0.0, "end_y": 5.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_RIGHT", "start_x": 3.0, "start_y": -1.6, "end_x": 3.0, "end_y": 5.0, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
        }
        # First pick main back-span room (center 1.5, 2.5): without cantilever it defaults to short span 0°
        ok1, _, s_main = pick_area_create_or_update_slab(story, 1.5, 2.5, target_mode="SLAB")
        self.assertTrue(ok1)
        self.assertEqual(s_main["rib_direction_deg"], 0)

        # Now pick bottom cantilever overhang (center 1.5, -0.8):
        # It must orient at 90° (perpendicular to B_BOT) AND automatically rotate s_main to 90°!
        ok2, _, s_cant = pick_area_create_or_update_slab(story, 1.5, -0.8, target_mode="SLAB")
        self.assertTrue(ok2)
        self.assertTrue(s_cant["is_cantilever"])
        self.assertEqual(s_cant["rib_direction_deg"], 90)
        self.assertEqual(s_main["rib_direction_deg"], 90)

    def test_crash_proof_column_rotation_with_and_without_boundary(self):
        story_no_poly = {
            "slab_edge_polygon": [],
            "columns": [
                {"id": "C1", "x": 2.0, "y": 3.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B1",
                    "start_x": 2.0,
                    "start_y": 3.0,
                    "end_x": 6.0,
                    "end_y": 3.0,
                    "width_m": 0.20,
                    "depth_m": 0.50,
                    "beam_kind": "drop",
                    "supports": [{"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20}],
                }
            ],
        }
        ok, msg = rotate_column_90_deg(story_no_poly, "C1")
        self.assertTrue(ok)
        self.assertAlmostEqual(story_no_poly["columns"][0]["b_m"], 0.40, places=2)
        self.assertAlmostEqual(story_no_poly["columns"][0]["h_m"], 0.20, places=2)
        self.assertAlmostEqual(story_no_poly["beams"][0]["supports"][0]["width_m"], 0.40, places=2)

    def test_autocad_window_vs_crossing_selection_and_align_without_padlock(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]],
            "columns": [
                {"id": "C1", "x": 1.0, "y": 1.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.0, "y": 1.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {"id": "B1", "start_x": 0.90, "start_y": 1.0, "end_x": 5.10, "end_y": 1.0, "width_m": 0.40, "beam_kind": "hidden"},
            ],
            "slabs": [],
            "openings": [],
        }
        win_sel = select_elements_by_box(story, 0.0, 0.0, 2.5, 2.5)
        self.assertEqual(win_sel, [("column", "C1")])

        cross_sel = select_elements_by_box(story, 2.5, 2.5, 0.0, 0.0)
        self.assertIn(("column", "C1"), cross_sel)
        self.assertIn(("beam", "B1"), cross_sel)

        ok_al, msg_al = align_element_face_to_reference(
            story, "column", "C1", "left", "x", 0.0, lock_constraint=False
        )
        self.assertTrue(ok_al)
        self.assertAlmostEqual(story["columns"][0]["x"], 0.10, places=2)
        self.assertNotIn("🔓", msg_al)
        self.assertNotIn("🔒", msg_al)

    def test_dimensions_and_analysis_with_slab_load_transfer(self):
        story = {
            "story_type": "ground",
            "height_m": 3.2,
            "slab_edge_polygon": [[0.0, 0.0], [6.2, 0.0], [6.2, 4.0], [0.0, 4.0]],
            "slabs": [
                {
                    "id": "S1",
                    "origin_x": 0.0,
                    "origin_y": 0.0,
                    "lx_m": 6.2,
                    "ly_m": 4.0,
                    "axis_span_m": 4.0,
                    "rib_direction_deg": 90,
                    "left_support_w_m": 0.20,
                    "right_support_w_m": 0.20,
                }
            ],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 6.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B1",
                    "beam_kind": "hidden",
                    "width_m": 0.40,
                    "depth_m": 0.30,
                    "start_x": 0.0,
                    "start_y": 0.20,
                    "end_x": 6.2,
                    "end_y": 0.20,
                    "spans": [6.0],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20},
                    ],
                    "loads": [],
                }
            ],
            "dimensions": [],
        }
        dim = create_linear_dimension(story, (0.10, 0.20), (6.10, 0.20), dim_kind="linear", offset_m=0.80)
        self.assertEqual(dim["id"], "D1")
        self.assertAlmostEqual(dim["value_m"], 6.00, places=2)

        cnt, _ = auto_generate_exterior_dimensions(story)
        self.assertGreaterEqual(cnt, 1)

        bundle = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        self.assertIn("B1", bundle["beam_results"])
        self.assertGreater(bundle["beam_results"]["B1"]["max_pos_moment"], 0.0)
        self.assertEqual(len(bundle["column_records"]), 2)

    def test_v160_dynamic_slab_rib_flip_wall_policy_and_span_counts(self):
        story = {
            "story_type": "ground",
            "height_m": 3.2,
            "adopted_slab_thickness_cm": 30.0,
            "slab_edge_polygon": [[0.0, 0.0], [10.6, 0.0], [10.6, 5.0], [0.0, 5.0]],
            "columns": [
                {"id": "C1", "x": 0.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 9.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.0, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 5.0, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [],
            "slabs": [],
            "openings": [],
        }
        # Create Beam B1 along y=0 from x=0 to x=10.6 (2 spans: 5.0m, 4.0m + 1.6m right cantilever)
        ok_b1, bm1, _ = validate_and_build_beam_with_cantilevers(
            "B1", (0.0, 0.0), (10.6, 0.0), "drop", 0.20, 0.50, story["columns"], [], story["slab_edge_polygon"]
        )
        self.assertTrue(ok_b1)
        story["beams"].append(bm1)

        # Verify span count strictly excludes cantilevers (2 spans, 1 right cantilever)
        segs = get_beam_span_segments(bm1)
        self.assertEqual(len(segs), 3)
        non_cant = [s for s in segs if not s["is_cantilever"]]
        self.assertEqual(len(non_cant), 2)

        # Add slab S1 (x=0..5, y=0..5) carrying load at 90 deg (onto horizontal beam B1)
        story["slabs"].append({
            "id": "S1",
            "x_min": 0.0, "x_max": 5.0,
            "y_min": 0.0, "y_max": 5.0,
            "lx_m": 5.0, "ly_m": 5.0,
            "axis_span_m": 5.0,
            "rib_direction_deg": 90,
            "is_cantilever": False,
        })
        bundle_90 = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        res_90 = bundle_90["beam_results"]["B1"]
        self.assertEqual(res_90["num_spans_excluding_cantilevers"], 2)
        r_sum_90 = sum(res_90["reactions_kn"])

        # Flip slab S1 rib direction from 90 deg -> 0 deg (now parallel to B1, so B1 gets 0 slab load on Span 1)
        story["slabs"][0]["rib_direction_deg"] = 0
        bundle_0 = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        res_0 = bundle_0["beam_results"]["B1"]
        r_sum_0 = sum(res_0["reactions_kn"])
        self.assertLess(r_sum_0, r_sum_90)

        # Test Story Wall Load Policy (Roof: no walls default, then enable wall load ONLY on Span 1)
        set_story_wall_load_policy(story, "no_walls", 12.0, apply_to_all_existing_spans=True)
        bundle_no_wall = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        r_no_wall = sum(bundle_no_wall["beam_results"]["B1"]["reactions_kn"])

        ok_flag, _ = set_beam_span_wall_flag(story, "B1", "span_1", True)
        self.assertTrue(ok_flag)
        bundle_span1_wall = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        r_span1_wall = sum(bundle_span1_wall["beam_results"]["B1"]["reactions_kn"])
        self.assertAlmostEqual(r_span1_wall - r_no_wall, 12.0 * 5.0, delta=1.0)

        # Test beam kind conversion
        ok_conv, _ = convert_beam_kind_and_section(story, "B1", "hidden")
        self.assertTrue(ok_conv)
        self.assertEqual(story["beams"][0]["beam_kind"], "hidden")

    def test_v170_single_xsd_master_and_legacy_cleanup(self):
        cfg = {
            "project_name": "Vilaa_test",
            "root_directory": self.tmp_dir,
            "ground_floor_height_m": 3.20,
            "include_basement": False,
            "floors_above_ground": 0,
            "include_penthouse": False,
        }
        master = initialize_studio_project(cfg)
        proj_dir = master["project_dir"]
        root_files = sorted(f for f in os.listdir(proj_dir) if os.path.isfile(os.path.join(proj_dir, f)))
        self.assertEqual(root_files, ["Vilaa_test-00_Project_Master.xsd"])

        # Simulate legacy files created by an older version and verify load_studio_project_from_master_file removes them
        legacy_xpert = os.path.join(proj_dir, "Vilaa_test-00_Project_Master.xpert")
        legacy_json = os.path.join(proj_dir, "Vilaa_test-00_Project_Master.json")
        shutil.copyfile(master["master_file"], legacy_xpert)
        shutil.copyfile(master["master_file"], legacy_json)
        loaded = load_studio_project_from_master_file(legacy_xpert)
        self.assertTrue(loaded["master_file"].endswith("Vilaa_test-00_Project_Master.xsd"))
        root_files_after = sorted(f for f in os.listdir(proj_dir) if os.path.isfile(os.path.join(proj_dir, f)))
        self.assertEqual(root_files_after, ["Vilaa_test-00_Project_Master.xsd"])

    def test_v170_crash_proof_deletion_of_carrier_beam_slab_and_dimension(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 4.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 9.90, "y": 4.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 5.00, "y": 7.80, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [],
            "slabs": [],
            "openings": [],
            "dimensions": [],
        }
        # Carrier beam B1 (horizontal at Y=4.0 from C1 to C2)
        ok1, b1, _ = validate_and_build_beam_with_cantilevers(
            "B1", (0.10, 4.0), (9.90, 4.0), "hidden", 0.40, 0.30, story["columns"], story["beams"], story["slab_edge_polygon"]
        )
        self.assertTrue(ok1)
        story["beams"].append(b1)

        # Secondary beam B2 (vertical at X=5.0 resting on B1 at Y=4.0 and C3 at Y=7.80)
        ok2, b2, _ = validate_and_build_beam_with_cantilevers(
            "B2", (5.00, 4.0), (5.00, 7.80), "drop", 0.20, 0.50, story["columns"], story["beams"], story["slab_edge_polygon"]
        )
        self.assertTrue(ok2)
        story["beams"].append(b2)

        # Create a slab and a dimension
        auto_fill_all_story_slabs(story)
        d1 = create_linear_dimension(story, (0.0, 8.0), (10.0, 8.0), offset_m=0.65, dim_kind="horizontal")
        self.assertEqual(len(story["dimensions"]), 1)

        # Delete carrier beam B1 while secondary beam B2 rests on it -> MUST NOT CRASH!
        ok_del_b1, msg_b1 = delete_selected_element_from_story(story, "beam", "B1")
        self.assertTrue(ok_del_b1)
        self.assertIn("B2", msg_b1)
        # B2 should have B1 removed from its supports without crashing
        rem_b2 = story["beams"][0]
        self.assertEqual(rem_b2["id"], "B2")
        self.assertTrue(all(s.get("target_id") != "B1" for s in rem_b2.get("supports", [])))

        # Delete dimension D1 -> MUST NOT CRASH!
        ok_del_d1, _ = delete_selected_element_from_story(story, "dimension", d1["id"])
        self.assertTrue(ok_del_d1)
        self.assertEqual(len(story["dimensions"]), 0)

        # Delete slab -> MUST NOT CRASH!
        if story["slabs"]:
            sid = story["slabs"][0]["id"]
            ok_del_s, _ = delete_selected_element_from_story(story, "slab", sid)
            self.assertTrue(ok_del_s)

    def test_v170_strict_backspan_slab_lock_and_exterior_dims_outside(self):
        """
        Verifies:
        1. Back-span slab S_back cannot have its rib direction flipped to 0° while cantilever slab S_cant has ribs at 90°
           (even after a stair trimmer beam splits the back-span bay!).
        2. Exterior auto-dimensions are strictly placed outside the building boundary (dy1 > max_y, dx1 < min_x).
        """
        story = {
            "slab_edge_polygon": [[0.0, -1.4], [4.0, -1.4], [4.0, 6.0], [0.0, 6.0]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 3.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {"id": "B_TOP", "start_x": 0.0, "start_y": 6.0, "end_x": 4.0, "end_y": 6.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_STAIR", "start_x": 0.0, "start_y": 2.4, "end_x": 4.0, "end_y": 2.4, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_CARRIER", "start_x": 0.0, "start_y": 0.0, "end_x": 4.0, "end_y": 0.0, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B_CANT_TIP", "start_x": 0.0, "start_y": -1.4, "end_x": 4.0, "end_y": -1.4, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_LEFT", "start_x": 0.0, "start_y": -1.4, "end_x": 0.0, "end_y": 6.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B_RIGHT", "start_x": 4.0, "start_y": -1.4, "end_x": 4.0, "end_y": 6.0, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
            "dimensions": [],
        }
        auto_fill_all_story_slabs(story)
        # Find cantilever slab (y in [-1.4, 0.0]) and back-span slab (y in [0.0, 2.4])
        s_cant = next(s for s in story["slabs"] if s["min_y"] < -0.5)
        s_back = next(s for s in story["slabs"] if abs(s["min_y"] - 0.0) < 0.1 and abs(s["max_y"] - 2.4) < 0.1)
        self.assertEqual(s_cant["rib_direction_deg"], 90)
        self.assertEqual(s_back["rib_direction_deg"], 90)

        # Attempt to flip s_back (at 2.0, 1.2) -> MUST BE REJECTED because s_cant extends into it!
        ok_flip_back, msg_lock, _ = toggle_slab_rib_by_label_click(story, 2.0, 1.2)
        self.assertFalse(ok_flip_back)
        self.assertIn("امتداد الكابولي", msg_lock)
        self.assertEqual(s_back["rib_direction_deg"], 90)

        # Now flip s_cant (at 2.0, -0.7) onto its two side beams B_LEFT & B_RIGHT (0°) -> ALLOWED!
        ok_flip_cant, _, _ = toggle_slab_rib_by_label_click(story, 2.0, -0.7)
        self.assertTrue(ok_flip_cant)
        self.assertEqual(s_cant["rib_direction_deg"], 0)

        # Once s_cant is at 0° (resting on side beams), s_back is now unlocked and CAN be flipped!
        ok_flip_back2, _, _ = toggle_slab_rib_by_label_click(story, 2.0, 1.2)
        self.assertTrue(ok_flip_back2)
        self.assertEqual(s_back["rib_direction_deg"], 0)

        # Verify exterior dimensions are strictly outside the building boundary
        from xpert_structural_engine import compute_dimension_geometry
        auto_generate_exterior_dimensions(story)
        for dim in story["dimensions"]:
            g = compute_dimension_geometry(dim)
            if g["kind"] == "horizontal":
                self.assertGreater(g["dy1"], 6.0)
            elif g["kind"] == "vertical":
                self.assertLess(g["dx1"], 0.0)

    def test_v170_vertical_sfd_jumps_support_kinds_and_load_formula(self):
        story = {
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 2.5, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.00, "y": 2.5, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 9.90, "y": 2.5, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [],
            "slabs": [],
        }
        ok_b1, b1, _ = validate_and_build_beam_with_cantilevers(
            "B1", (0.10, 2.5), (9.90, 2.5), "hidden", 0.40, 0.30, story["columns"], [], story["slab_edge_polygon"]
        )
        self.assertTrue(ok_b1)
        story["beams"].append(b1)
        bundle = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        res = bundle["beam_results"]["B1"]
        xs = res["x_full"]
        # Verify interior support at x = 4.90m has exact left/right discontinuity stations so SFD jump is 90° vertical
        sup2_x = res["support_critical_table"][1]["x_m"]
        near_pts = [x for x in xs if abs(x - sup2_x) < 1e-4]
        self.assertGreaterEqual(len(near_pts), 3)
        self.assertEqual(res["support_critical_table"][0]["support_kind"], "column")
        self.assertIn("formula_str", res["loads_applied"][0])

    def test_v180_carrier_beam_depth_hierarchy_and_slab_flip_and_beam_convert(self):
        """
        Verifies v1.8.0 upgrades:
        1. Carrier Beam Depth Hierarchy (`h_carrier >= max(h_supported)`): When secondary beam B7 (depth 0.55m)
           rests on carrier beam B6 (initial depth 0.40m), B6 is automatically upgraded to depth >= 0.55m
           and B7's support entry for B6 records `depth_m >= 0.55m`.
        2. Bidirectional Beam Conversion (`Hidden <-> Drop`): `convert_beam_kind_and_section` synchronizes
           both `beam["beam_kind"]` and `beam["kind"]` when toggling drop -> hidden -> drop.
        3. Small Sub-Slab Rib Flipping (`S5` vs `S3`): `flip_slab_rib_by_id` and `toggle_slab_rib_by_label_click`
           flip only the target small slab `S5` next to an interior stair opening without flipping `S3`.
        """
        from xpert_structural_engine import convert_beam_kind_and_section, flip_slab_rib_by_id

        story = {
            "adopted_slab_thickness_cm": 30.0,
            "slab_edge_polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.5], [0.0, 8.5]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.20, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 9.90, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.10, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 5.20, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C6", "x": 9.90, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C7", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C8", "x": 5.20, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C9", "x": 9.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B6", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.40,
                    "start_x": 0.10, "start_y": 4.20, "end_x": 9.90, "end_y": 4.20,
                    "spans": [5.10, 4.70],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.20, "center_coord_m": 5.20},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.20, "center_coord_m": 9.90},
                    ],
                },
                {
                    "id": "B5", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
                    "start_x": 0.10, "start_y": 0.20, "end_x": 9.90, "end_y": 0.20,
                    "spans": [5.10, 4.70],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C7", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C8", "width_m": 0.20, "center_coord_m": 5.20},
                        {"support_index": 3, "kind": "column", "target_id": "C9", "width_m": 0.20, "center_coord_m": 9.90},
                    ],
                },
                {
                    "id": "B7", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.55,
                    "start_x": 6.10, "start_y": 0.20, "end_x": 6.10, "end_y": 4.20,
                    "spans": [4.00],
                    "supports": [
                        {"support_index": 1, "kind": "beam", "target_id": "B5", "width_m": 0.20, "center_coord_m": 0.20},
                        {"support_index": 2, "kind": "beam", "target_id": "B6", "width_m": 0.20, "center_coord_m": 4.20},
                    ],
                },
            ],
            "slabs": [
                {
                    "id": "S3", "min_x": 0.10, "max_x": 5.20, "min_y": 0.20, "max_y": 4.20,
                    "clear_min_x": 0.20, "clear_max_x": 5.10, "clear_min_y": 0.30, "clear_max_y": 4.10,
                    "lx_m": 4.90, "ly_m": 3.80, "rib_angle_deg": 0, "rib_direction_deg": 0,
                },
                {
                    "id": "S5", "min_x": 5.20, "max_x": 6.10, "min_y": 0.20, "max_y": 4.20,
                    "clear_min_x": 5.30, "clear_max_x": 6.00, "clear_min_y": 0.30, "clear_max_y": 4.10,
                    "lx_m": 0.70, "ly_m": 3.80, "rib_angle_deg": 0, "rib_direction_deg": 0,
                },
            ],
            "openings": [],
        }

        # 1. Test Carrier Beam Hierarchy Rule (B6 depth must be upgraded from 0.40m to >= 0.55m to carry B7)
        bundle = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        b6_obj = next(b for b in story["beams"] if b["id"] == "B6")
        self.assertGreaterEqual(float(b6_obj["depth_m"]), 0.55)
        b7_res = bundle["beam_results"]["B7"]
        b6_sup_in_b7 = next(s for s in b7_res["support_critical_table"] if s["target_id"] == "B6")
        self.assertGreaterEqual(float(b6_sup_in_b7["depth_m"]), 0.55)

        # Verify design_beam_aci318 returns non-None required steel areas and status
        b7_des = bundle["beam_designs"]["B7"]
        self.assertIsNotNone(b7_des.get("as_pos_req_mm2"))
        self.assertIsNotNone(b7_des.get("as_neg_req_mm2"))
        self.assertIn("OK", str(b7_des.get("status", "")))

        # 2. Test Bidirectional Convert Beam (Drop -> Hidden -> Drop)
        ok_h, _ = convert_beam_kind_and_section(story, "B6", "hidden")
        self.assertTrue(ok_h)
        self.assertEqual(b6_obj["beam_kind"], "hidden")
        self.assertEqual(b6_obj["kind"], "hidden")
        ok_d, _ = convert_beam_kind_and_section(story, "B6", "drop")
        self.assertTrue(ok_d)
        self.assertEqual(b6_obj["beam_kind"], "drop")
        self.assertEqual(b6_obj["kind"], "drop")

        # 3. Test flipping S5 by ID and by click (must flip S5 and NEVER flip S3!)
        ok_f, _, flipped_s = flip_slab_rib_by_id(story, "S5")
        self.assertTrue(ok_f)
        self.assertEqual(flipped_s["id"], "S5")
        self.assertEqual(flipped_s["rib_angle_deg"], 90)
        s3_obj = next(s for s in story["slabs"] if s["id"] == "S3")
        self.assertEqual(s3_obj["rib_angle_deg"], 0)


if __name__ == "__main__":
    unittest.main()



