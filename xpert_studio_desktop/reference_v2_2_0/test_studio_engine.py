"""
Unit Test Suite for Xpert Structural Design Studio (v1.5.0-structural-bim-pro)
"""

import os
import shutil
import tempfile
import unittest

from xpert_project_io import (
    MASTER_FILE_EXT,
    compute_hollow_block_parameters,
    initialize_studio_project,
    load_studio_project_from_master_file,
    compute_smart_beam_tag_position,
    import_arch_dxf_underlay,
)
from xpert_structural_engine import (
    evaluate_story_thickness_and_optimization,
    analyze_all_story_beams_and_columns,
    design_hollow_block_slab_rib,
    design_beam_aci318,
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
        # Carrier beam B1 (horizontal at Y=4.0 from C1 to C2 — Drop beam carrying Drop beam B2)
        ok1, b1, _ = validate_and_build_beam_with_cantilevers(
            "B1", (0.10, 4.0), (9.90, 4.0), "drop", 0.20, 0.50, story["columns"], story["beams"], story["slab_edge_polygon"]
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

        # 2. Test Bidirectional Convert Beam (Drop -> Hidden -> Drop) and Drop-on-Hidden rejection
        # Since B7 is currently a Drop beam resting on B6, converting B6 to Hidden MUST be rejected!
        ok_h_blocked, msg_blocked = convert_beam_kind_and_section(story, "B6", "hidden")
        self.assertFalse(ok_h_blocked)
        self.assertIn("B7", msg_blocked)

        # Once B7 is converted to Hidden, B6 CAN be converted to Hidden and back to Drop!
        ok_b7_hid, _ = convert_beam_kind_and_section(story, "B7", "hidden")
        self.assertTrue(ok_b7_hid)
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

    def test_v190_column_delete_reconcile_drop_on_hidden_piecewise_loads_and_tie_beams(self):
        """
        Verifies all v1.9.0 structural engineering upgrades requested by Eng. Yousef:
        1. Deleting an intermediate column (e.g. C5 in the middle of B6 and at the bottom of B5):
           - Renumbers active columns sequentially C1..C8 with zero gaps.
           - Reconciles B6 from 2 spans (4.5m + 4.8m) to 1 span (9.30m) supported only at its left & right end columns.
           - Reconciles B5 so its bottom end now rests on Carrier Beam B6 (Roller) instead of the deleted column!
           - Re-evaluates story minimum slab thickness so Hidden Beam B6 (9.30m single span, Ln=9.10m, L/16) governs (~56.9 cm).
        2. Piecewise Slab & Void-Opening Load Distribution along Beam Spans:
           - Where an opening (OP1) or parallel-rib slab (S2 at 0°) borders B6, w_Slab = 0.0 kN/m (only w_SW + w_Wall).
           - Where perpendicular-rib slab S5 (90°) borders B6 over [7.30m, 9.30m], S5's full tributary load acts strictly on [7.30m, 9.30m].
        3. Tie-Beams Story (00_TieBeams) allows drawing Drop Tie-Beams directly between columns with NO outer boundary polyline.
        """
        from xpert_structural_engine import (
            convert_beam_kind_and_section,
            delete_selected_element_from_story,
            evaluate_story_thickness_and_optimization,
        )

        story = {
            "story_id": "02_Ground_Floor",
            "adopted_slab_thickness_cm": 30.0,
            "slab_factored_wu_kpa": 10.0,
            "default_wall_load_kn_m": 10.0,
            "wall_load_policy": "all_beams",
            "slab_edge_polygon": [[0.0, 0.0], [9.50, 0.0], [9.50, 8.50], [0.0, 8.50]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 4.60, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 9.40, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.10, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 4.60, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C6", "x": 9.40, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B6", "beam_kind": "hidden", "kind": "hidden", "width_m": 0.40, "depth_m": 0.30,
                    "start_x": 0.10, "start_y": 4.20, "end_x": 9.40, "end_y": 4.20,
                    "spans": [4.50, 4.80],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.20, "center_coord_m": 4.60},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.20, "center_coord_m": 9.40},
                    ],
                },
                {
                    "id": "B5", "beam_kind": "hidden", "kind": "hidden", "width_m": 0.40, "depth_m": 0.30,
                    "start_x": 4.60, "start_y": 4.20, "end_x": 4.60, "end_y": 8.30,
                    "spans": [4.10],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C5", "width_m": 0.40, "center_coord_m": 4.20},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.40, "center_coord_m": 8.30},
                    ],
                },
            ],
            "slabs": [
                {
                    "id": "S1", "min_x": 0.10, "max_x": 4.60, "min_y": 4.20, "max_y": 8.30,
                    "lx_m": 4.50, "ly_m": 4.10, "rib_angle_deg": 90, "rib_direction_deg": 90,
                },
                {
                    "id": "S2", "min_x": 4.60, "max_x": 9.40, "min_y": 4.20, "max_y": 8.30,
                    "lx_m": 4.80, "ly_m": 4.10, "rib_angle_deg": 0, "rib_direction_deg": 0,
                },
                {
                    "id": "S6", "min_x": 0.10, "max_x": 5.40, "min_y": 0.0, "max_y": 4.20,
                    "lx_m": 5.30, "ly_m": 4.20, "rib_angle_deg": 90, "rib_direction_deg": 90,
                },
                {
                    "id": "S5", "min_x": 7.40, "max_x": 9.40, "min_y": 2.20, "max_y": 4.20,
                    "lx_m": 2.00, "ly_m": 2.00, "rib_angle_deg": 90, "rib_direction_deg": 90,
                },
            ],
            "openings": [
                {"id": "OP1", "min_x": 5.40, "max_x": 7.40, "min_y": 2.20, "max_y": 4.20},
            ],
        }

        # Delete central column C5 (at 4.60, 4.20)
        ok_del, _ = delete_selected_element_from_story(story, "column", "C5")
        self.assertTrue(ok_del)

        # 1A. Verify active columns are sequentially numbered C1..C5 with zero gaps
        col_ids = [c["id"] for c in story["columns"]]
        self.assertEqual(col_ids, ["C1", "C2", "C3", "C4", "C5"])

        # 1B. Verify B6 is now a 1-span beam (9.30m) supported on C4 (left) and C5 (right, formerly C6)
        b6 = next(b for b in story["beams"] if b["id"] == "B6")
        self.assertEqual(len(b6["spans"]), 1)
        self.assertAlmostEqual(b6["spans"][0], 9.30, places=2)
        self.assertEqual([s["target_id"] for s in b6["supports"]], ["C4", "C5"])

        # 1C. Verify B5 now rests on Carrier Beam B6 (kind='beam') at its bottom support and C2 at its top support!
        b5 = next(b for b in story["beams"] if b["id"] == "B5")
        self.assertEqual(b5["supports"][0]["kind"], "beam")
        self.assertEqual(b5["supports"][0]["target_id"], "B6")
        self.assertEqual(b5["supports"][1]["kind"], "column")
        self.assertEqual(b5["supports"][1]["target_id"], "C2")

        # 1D. Verify Hidden Beam B6 (single 9.30m span) now governs minimum slab thickness (> 50 cm)
        eval_thick = evaluate_story_thickness_and_optimization(story, 420.0)
        self.assertIn("B6", eval_thick["governing_member"])
        self.assertGreater(eval_thick["calculated_min_thickness_cm"], 50.0)

        # 2. Verify Piecewise Distributed Loads on B6:
        #    - [0.00, 4.50]: S1 (90°) + S6 (90°)
        #    - [4.50, 5.30]: S6 (90°) only (S2 is 0° parallel)
        #    - [5.30, 7.30]: Opening OP1 below & S2 (0°) above -> w_Slab = 0.0 kN/m!
        #    - [7.30, 9.30]: S5 (90°, Ly=2.0m -> w_Slab = 10.0*(2.0/2) = 10.0 kN/m, NOT diluted!)
        bundle = analyze_all_story_beams_and_columns(story, 25.0, 420.0)
        b6_loads = [ld for ld in bundle["beam_results"]["B6"]["loads_applied"] if ld["type"] == "D"]
        self.assertEqual(len(b6_loads), 4)
        # Over opening [5.30, 7.30], w_Slab == 0, so mag == w_SW + w_Wall (no slab term in formula_str)
        op_seg = next(ld for ld in b6_loads if abs(ld["start"] - 5.30) < 0.1)
        self.assertIn("w_Slab (0.00)", op_seg["formula_str"])
        # Over S5 [7.30, 9.30], S5 contributes full tributary load (reduced by ΔB/2 = 0.70m after B6 widens from 0.40m to 1.80m)
        s5_seg = next(ld for ld in b6_loads if abs(ld["start"] - 7.30) < 0.1)
        self.assertIn("S5: 11.71×", s5_seg["formula_str"])

        # 3. Verify Tie-Beams story allows drawing a Drop Beam with empty slab_edge_polygon
        tie_cols = [
            {"id": "C1", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            {"id": "C2", "x": 5.00, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
        ]
        ok_tie, tie_bm, _ = validate_and_build_beam_with_cantilevers(
            "B1", (0.10, 0.20), (5.00, 0.20), "drop", 0.20, 0.50, tie_cols, [], [], is_tie_beam_story=True
        )
        self.assertTrue(ok_tie)
        self.assertEqual(tie_bm["beam_kind"], "drop")

    def test_v200_excel_hordi_slab_rib_design_beam_ow_wall_and_wu_transfer(self):
        """
        Verifies all v2.0.0 upgrades requested by Eng. Yousef matching his Excel sheet (`Design of rib slab`):
        1. Hollow-Block (Hordi) Slab Load Calculation & Rib Design (`design_hollow_block_slab_rib`):
           - For h = 300 mm (30 cm), hs = 100 mm, S = 400 mm, bw1 = bw2 = 150 mm, b = 550 mm,
             γc = 24 kN/m³, W_finishing = 1.5 kN/m², LL = 2.0 kN/m², W_block = 0.10 kN,
             fy = 350 MPa, fc' = 20 MPa, db = 12 mm, ds = 6 mm, dc = 20 mm, Center-to-Center Span L = 4.55 m:
           - Topping = 1.320, Rib = 0.720, Blocks = 0.400, Finishing = 0.825 -> DL = 3.265 kN/m'/rib -> 1.4*DL = 4.571
           - LL = 1.100 kN/m'/rib -> 1.7*LL = 1.870
           - Design Load per Rib: Wu(rib) = 6.441 kN/m'/rib (6.44 kN/m'/rib)
           - Area Load per Square Meter (transferred to Beams): Wu(m×m) = 6.441 / 0.55 = 11.71 kN/m²
           - Flexure: Mu = Wu(rib) * L² / 8 = 6.441 * 4.55² / 8 = 16.67 kN.m, d = 268 mm,
             Ku = 0.0234, ω = 0.0237, ρ = 0.001354, As = 199.58 mm², Nbar = 1.76 -> 2∅12 Bottom,
             1∅10 Top fixation bar, ∅6 @ 200 mm open triangular stirrup.
           - Shear: Vc = 32.96 kN, φVc = 28.02 kN, Vu = 12.93 kN <= φVc (OK).
        2. Exact Beam Self-Weight (`O.W = b * h * 24 * 1.4`) and Masonry Wall Load (`W_wall = 2.5 * (t_wall/20) * H * 1.4`):
           - Hidden beam 0.40×0.30m -> O.W = 0.40 * 0.30 * 24 * 1.4 = 4.032 kN/m (4.03 kN/m).
           - Drop beam 0.20×0.50m -> O.W = 0.20 * 0.50 * 24 * 1.4 = 3.360 kN/m (3.36 kN/m).
           - Wall height H = 3.0m, t_wall = 20 cm -> W_wall = 2.5 * 1.0 * 3.0 * 1.4 = 10.50 kN/m.
           - Per-span wall thickness override (`set_beam_span_wall_thickness`): t_wall = 15 cm -> W_wall = 7.88 kN/m.
        """
        from xpert_structural_engine import (
            design_hollow_block_slab_rib,
            set_beam_span_wall_thickness,
        )

        # 1. Exact Excel verification for L = 4.55 m (Center-to-Center Span) and h = 30.0 cm (300 mm)
        slab_excel = {
            "id": "S1",
            "min_x": 0.0,
            "max_x": 4.55,
            "min_y": 0.0,
            "max_y": 4.00,
            "lx_m": 4.55,
            "ly_m": 4.00,
            "rib_angle_deg": 0,
            "rib_direction_deg": 0,
            "rib_bar_dia_mm": 12,
        }
        story_excel = {
            "story_id": "02_Ground_Floor",
            "height_m": 3.00,
            "adopted_slab_thickness_cm": 30.0,
        }
        res_rib = design_hollow_block_slab_rib(slab_excel, story_excel, fc_mpa=20.0, fy_mpa=350.0)

        self.assertAlmostEqual(res_rib["topping_wt_rib"], 1.32, places=2)
        self.assertAlmostEqual(res_rib["rib_web_wt_rib"], 0.72, places=2)
        self.assertAlmostEqual(res_rib["block_wt_rib"], 0.40, places=2)
        self.assertAlmostEqual(res_rib["finishing_wt_rib"], 0.825, places=3)
        self.assertAlmostEqual(res_rib["total_dl_rib"], 3.265, places=3)
        self.assertAlmostEqual(res_rib["factored_dl_rib"], 4.571, places=3)
        self.assertAlmostEqual(res_rib["ll_rib"], 1.10, places=2)
        self.assertAlmostEqual(res_rib["factored_ll_rib"], 1.87, places=2)
        self.assertAlmostEqual(res_rib["wu_rib_kn_m"], 6.44, places=2)
        self.assertAlmostEqual(res_rib["wu_m2_kpa"], 11.71, places=2)
        self.assertAlmostEqual(res_rib["d_mm"], 268.0, places=1)
        self.assertAlmostEqual(res_rib["mu_knm"], 16.67, places=2)
        self.assertAlmostEqual(res_rib["ku"], 0.0234, places=4)
        self.assertAlmostEqual(res_rib["omega"], 0.0237, places=4)
        self.assertAlmostEqual(res_rib["rho"], 0.001354, places=5)
        self.assertAlmostEqual(res_rib["as_calc_mm2"], 199.58, places=1)
        self.assertAlmostEqual(res_rib["n_bar_exact"], 1.76, places=2)
        self.assertEqual(res_rib["n_bars_adopted"], 2)
        self.assertIn("2∅12", res_rib["bottom_rebar_callout"])
        self.assertIn("1∅10", res_rib["top_rebar_callout"])
        self.assertAlmostEqual(res_rib["vc_kn"], 32.96, places=1)
        self.assertAlmostEqual(res_rib["phi_vc_kn"], 28.02, places=1)
        self.assertAlmostEqual(res_rib["vu_kn"], 12.93, places=1)
        self.assertTrue(res_rib["shear_ok"])

        # 2. Verify changing slab thickness h from 30.0 cm to 25.0 cm dynamically updates Wu(rib) and Wu(m×m)
        story_excel["adopted_slab_thickness_cm"] = 25.0
        res_rib_25 = design_hollow_block_slab_rib(slab_excel, story_excel, fc_mpa=20.0, fy_mpa=350.0)
        self.assertLess(res_rib_25["wu_rib_kn_m"], res_rib["wu_rib_kn_m"])
        self.assertLess(res_rib_25["wu_m2_kpa"], res_rib["wu_m2_kpa"])

        # 3. Verify Beam O.W = b*h*24*1.4, W_wall = 2.5*(t_wall/20)*H*1.4, and Area Load Wu(m×m) = 11.71 kN/m² transfer
        story_beams = {
            "story_id": "02_Ground_Floor",
            "height_m": 3.00,
            "adopted_slab_thickness_cm": 30.0,
            "wall_load_policy": "all_beams",
            "slab_edge_polygon": [[0.0, 0.0], [5.0, 0.0], [5.0, 4.0], [0.0, 4.0]],
            "columns": [
                {"id": "C1", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 4.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 0.10, "y": 3.80, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 4.90, "y": 3.80, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B1", "beam_kind": "hidden", "kind": "hidden", "width_m": 0.40, "depth_m": 0.30,
                    "lock_section_dimensions": True,
                    "start_x": 0.10, "start_y": 0.20, "end_x": 4.90, "end_y": 0.20,
                    "spans": [4.80],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20, "center_coord_m": 4.90},
                    ],
                },
                {
                    "id": "B2", "beam_kind": "drop", "kind": "drop", "width_m": 0.20, "depth_m": 0.50,
                    "lock_section_dimensions": True,
                    "start_x": 0.10, "start_y": 3.80, "end_x": 4.90, "end_y": 3.80,
                    "spans": [4.80],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C3", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C4", "width_m": 0.20, "center_coord_m": 4.90},
                    ],
                },
            ],
            "slabs": [
                {
                    "id": "S1", "min_x": 0.10, "max_x": 4.90, "min_y": 0.20, "max_y": 3.80,
                    "lx_m": 4.80, "ly_m": 3.60, "rib_angle_deg": 90, "rib_direction_deg": 90,
                },
            ],
            "openings": [],
        }
        bundle = analyze_all_story_beams_and_columns(story_beams, 20.0, 350.0)
        b1_ld = bundle["beam_results"]["B1"]["loads_applied"][0]
        b2_ld = bundle["beam_results"]["B2"]["loads_applied"][0]

        # B1 (Hidden 0.40×0.30m): O.W = 4.03 kN/m, w_Slab = 11.71*(3.60/2) = 21.08 kN/m, W_wall(20cm, H=3.0m) = 10.50 kN/m -> Total = 35.61 kN/m
        self.assertIn("O.W (4.03", b1_ld["formula_str"])
        self.assertIn("W_wall (10.50", b1_ld["formula_str"])
        self.assertAlmostEqual(b1_ld["mag"], 4.032 + 11.71 * 1.80 + 10.50, places=1)

        # B2 (Drop 0.20×0.50m): O.W = 3.36 kN/m
        self.assertIn("O.W (3.36", b2_ld["formula_str"])

        # Change B2 Span 1 wall thickness to 15 cm -> W_wall = 2.5*(15/20)*3.0*1.4 = 7.875 kN/m
        ok_wt, _ = set_beam_span_wall_thickness(story_beams, "B2", 1, 15.0)
        self.assertTrue(ok_wt)
        bundle2 = analyze_all_story_beams_and_columns(story_beams, 20.0, 350.0)
        b2_ld2 = bundle2["beam_results"]["B2"]["loads_applied"][0]
        self.assertIn("2.5×(15/20)×3.0×1.4", b2_ld2["formula_str"])

    def test_v200_pdf_code_beam_design_ceiling_thickness_and_dialogs(self):
        """
        Verifies the 9 engineering & UI fixes requested by Eng. Yousef:
        1. Calculated minimum slab thickness is rounded UP to the next whole centimeter (math.ceil):
           e.g. Ln = 4.50 m, L/16 = 28.125 cm -> 29 cm (290 mm).
        2. DEFAULT_REBAR_DIAMETERS_TABLE includes Φ6 (for stirrups) and Φ32 (for main bars).
        3. Standard wall thicknesses [10, 15, 20, 30, 40] cm snap and scale W_wall = (2.5*H*1.4)*(t_wall/20).
        4. Beam flexural & shear design per attached Code PDFs (Pages 1-2, 8, 11, 13):
           - Continuous As,min (n_min Φ db) top and bottom from start to end of beam.
           - Double Reinforcement with Continuous As,min (quadratic x1, x2, C, fs' = 600*(C-d')/C, As1, additional bars).
           - Single Reinforcement mode toggle.
        5. Headless verification of StartupDefaultsDialog, StudioOptionsDialog, and SlabRibDesignDialog (zero crashes).
        """
        from xpert_project_io import DEFAULT_REBAR_DIAMETERS_TABLE
        from xpert_structural_engine import (
            STANDARD_WALL_THICKNESSES_CM,
            design_beam_aci318,
            evaluate_story_thickness_and_optimization,
            snap_standard_wall_thickness_cm,
        )

        # 1. Verify Φ6 and Φ32 exist in DEFAULT_REBAR_DIAMETERS_TABLE
        dias = [int(r["dia_mm"]) for r in DEFAULT_REBAR_DIAMETERS_TABLE]
        self.assertIn(6, dias)
        self.assertIn(32, dias)

        # 2. Verify ceiling integer rounding of calculated minimum slab thickness (28.125 cm -> 29 cm)
        story_ceil = {
            "story_id": "02_Ground_Floor",
            "beams": [
                {
                    "id": "B1",
                    "beam_kind": "hidden",
                    "width_m": 0.40,
                    "depth_m": 0.30,
                    "spans": [4.70],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20},
                    ],
                }
            ],
            "slabs": [],
        }
        # Clear span Ln = 4.70 - 0.10 - 0.10 = 4.50 m; for fy=420 MPa, coeff=16 -> 450/16 = 28.125 cm -> ceil = 29 cm!
        eval_c = evaluate_story_thickness_and_optimization(story_ceil, 420.0)
        self.assertEqual(eval_c["calculated_min_thickness_cm"], 29.0)
        self.assertEqual(eval_c["badge_text"], "29 cm")

        # 3. Verify standard wall thicknesses [10, 15, 20, 30, 40] cm
        self.assertEqual(STANDARD_WALL_THICKNESSES_CM, [10, 15, 20, 30, 40])
        self.assertEqual(snap_standard_wall_thickness_cm(14.0), 15.0)
        self.assertEqual(snap_standard_wall_thickness_cm(32.0), 30.0)

        # 4. Verify PDF Code Equations for Beam Flexure (Double vs Single with Continuous As,min)
        bm_sample = {
            "id": "B_TEST",
            "beam_kind": "drop",
            "width_m": 0.25,
            "depth_m": 0.50,
            "spans": [5.0],
        }
        res_sample = {
            "num_spans_excluding_cantilevers": 1,
            "max_pos_mu_knm": 135.0,
            "max_neg_face_mu_knm": 90.0,
            "max_face_vu_kn": 110.0,
            "span_critical_table": [
                {"span_index": 1, "length_m": 5.0, "max_pos_mu_knm": 135.0, "max_face_vu_kn": 110.0}
            ],
            "support_critical_table": [
                {"support_index": 1, "target_id": "C1", "support_kind": "column", "x_m": 0.0, "width_m": 0.20, "mu_face_neg_knm": 90.0, "vu_face_max_kn": 110.0},
                {"support_index": 2, "target_id": "C2", "support_kind": "column", "x_m": 5.0, "width_m": 0.20, "mu_face_neg_knm": 90.0, "vu_face_max_kn": 110.0},
            ],
        }
        des_double = design_beam_aci318(bm_sample, res_sample, fc_mpa=25.0, fy_mpa=420.0, design_mode="double", main_bar_dia_mm=16)
        des_single = design_beam_aci318(bm_sample, res_sample, fc_mpa=25.0, fy_mpa=420.0, design_mode="single", main_bar_dia_mm=16)

        self.assertEqual(des_double["design_mode"], "double")
        self.assertEqual(des_single["design_mode"], "single")
        self.assertGreaterEqual(des_double["n_bars_min_cont"], 2)
        self.assertIn("pos_flexure_details", des_double)
        self.assertGreater(des_double["pos_flexure_details"]["C_mm"], 0.0)
        # Double reinforcement utilizes compression steel As2 = As,min, so total tension As required is slightly lower than or equal to single reinforcement
        self.assertLessEqual(des_double["as_pos_req_mm2"], des_single["as_pos_req_mm2"] + 5.0)
        self.assertGreaterEqual(des_double["n_max_per_layer"], 2)

        # 5. Verify xpert_studio_app.py Dialog Signatures, Imports, and Fullscreen Launch (via AST + PyQt6 if available)
        import ast
        app_path = os.path.join(os.path.dirname(__file__), "xpert_studio_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            app_src = f.read()
        tree = ast.parse(app_src, filename="xpert_studio_app.py")
        self.assertIsNotNone(tree)
        self.assertIn("win.showMaximized()", app_src)
        self.assertNotIn("compute_hollow_block_slab_loads(", app_src)
        self.assertIn("compute_hollow_block_parameters(", app_src)
        self.assertIn("STANDARD_WALL_THICKNESSES_CM", app_src)
        self.assertIn("thickness_warning_acknowledged_cm", app_src)

        try:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PyQt6.QtWidgets import QApplication
            from xpert_studio_app import (
                SlabRibDesignDialog,
                StartupDefaultsDialog,
                StudioOptionsDialog,
                XpertStudioMainWindow,
            )

            _app = QApplication.instance() or QApplication([])
            cfg = {
                "project_name": "TestDialogs",
                "root_directory": self.tmp_dir,
                "ground_floor_height_m": 3.00,
                "include_basement": False,
                "floors_above_ground": 1,
                "include_penthouse": False,
                "fc_mpa": 20.0,
                "fy_mpa": 350.0,
            }
            master = initialize_studio_project(cfg)
            win = XpertStudioMainWindow(initial_master_project=master)
            win.activate_cad_tool("LOAD_TEMPLATE")

            dlg_def = StartupDefaultsDialog(win)
            stir_items = [dlg_def.cb_def_stirrup.itemText(i) for i in range(dlg_def.cb_def_stirrup.count())]
            main_items = [dlg_def.cb_def_main.itemText(i) for i in range(dlg_def.cb_def_main.count())]
            self.assertIn("6", stir_items)
            self.assertIn("32", main_items)

            dlg_opt = StudioOptionsDialog(win, master_project=win.master_project, current_story_data=win.current_story_data)
            self.assertAlmostEqual(dlg_opt.sp_finish_load.value(), 1.50, places=2)
            self.assertIn("11.71", dlg_opt.lbl_computed_qu.text())

            dlg_rib = SlabRibDesignDialog(win, story_data=win.current_story_data, fc_mpa=20.0, fy_mpa=350.0)
            self.assertGreater(dlg_rib.cb_slab.count(), 0)
        except ModuleNotFoundError:
            pass

    def test_v220_hordi_fixed_block_height_vba_beam_sizing_and_rib_reduction(self) -> None:
        """
        Verifies v2.2.0 upgrades:
        1. Fixed commercial Hordi block height (200 mm for h >= 250 mm, 160 mm for h < 250 mm) and variable topping hs = h - h_block:
           - At h = 28 cm (280 mm): h_block = 200 mm, hs = 80 mm -> Wu(rib) = 6.07 kN/m'/rib, Wu(m×m) = 11.04 kN/m² (matching 4_17463a4e.PNG 100%).
           - At h = 29 cm (290 mm): h_block = 200 mm, hs = 90 mm -> Wu(rib) = 6.26 kN/m'/rib, Wu(m×m) = 11.38 kN/m².
           - At h = 30 cm (300 mm): h_block = 200 mm, hs = 100 mm -> Wu(rib) = 6.44 kN/m'/rib, Wu(m×m) = 11.71 kN/m².
        2. Exact Excel Sheet4 (5_e8049e44.PNG) & VBA Sub ReDesign_Sec() match for Hidden Beam #7 (600×290 mm, db=14, ds=6, dc=25, M=-97):
           - d = 252 mm, Ku = 0.14143, ω = 0.15574, ρ = 0.0089, As = 1345.68 mm², As_1bar = 153.86 mm², Nbar = 9 Φ 14, As_total = 1384.7 mm²,
             nbs = 13, min_bars = 4, max_bars = 19, and station bars [4, 6, 9, 5, 4] Φ 14.
        3. Automatic +100 mm iterative section sizing for Hidden Beam width B and Drop Beam depth h,
           coupled with O.W increase and Slab Rib Length (L_rib) reduction (ΔL_rib = sum(ΔB/2)) in analyze_all_story_beams_and_columns.
        """
        # 1. Verify h = 280 mm (28 cm) matches Excel 4_17463a4e.PNG 100%
        hb_28 = compute_hollow_block_parameters(slab_thickness_cm=28.0)
        self.assertAlmostEqual(hb_28["block_height_cm"], 20.0, places=2)
        self.assertAlmostEqual(hb_28["top_compression_slab_cm"], 8.0, places=2)
        self.assertAlmostEqual(hb_28["topping_wt_rib_kn_m"], 1.056, places=3)
        self.assertAlmostEqual(hb_28["rib_web_wt_rib_kn_m"], 0.720, places=3)
        self.assertAlmostEqual(hb_28["block_wt_rib_kn_m"], 0.400, places=3)
        self.assertAlmostEqual(hb_28["finishing_wt_rib_kn_m"], 0.825, places=3)
        self.assertAlmostEqual(hb_28["total_dl_rib_kn_m"], 3.001, places=3)
        self.assertAlmostEqual(hb_28["factored_dl_rib_kn_m"], 4.2014, places=4)
        self.assertAlmostEqual(hb_28["wu_rib_kn_m"], 6.07, places=2)
        self.assertAlmostEqual(hb_28["total_factored_wu_kn_m2"], 11.04, places=2)

        # Verify design_hollow_block_slab_rib at h = 28 cm also uses hs = 80 mm and block = 200 mm
        story_28 = {"adopted_slab_thickness_cm": 28.0, "hollow_block": {}}
        rib_28 = design_hollow_block_slab_rib({"id": "S1", "lx_m": 4.55, "ly_m": 4.55, "rib_direction_deg": 0}, story_28)
        self.assertAlmostEqual(rib_28["h_mm"], 280.0, places=1)
        self.assertAlmostEqual(rib_28["hs_mm"], 80.0, places=1)
        self.assertAlmostEqual(rib_28["block_height_mm"], 200.0, places=1)
        self.assertAlmostEqual(rib_28["wu_rib_kn_m"], 6.07, places=2)
        self.assertAlmostEqual(rib_28["wu_m2_kpa"], 11.04, places=2)

        # 2. Verify Excel Sheet4 (5_e8049e44.PNG) exact match for Beam #7 (600×290 mm, db=14, ds=6, M=[-0, +59, -97, +50, -0])
        bm_excel7 = {
            "id": "B7",
            "beam_kind": "hidden",
            "width_m": 0.60,
            "depth_m": 0.29,
            "lock_section_dimensions": True,
            "spans": [5.0, 5.0],
            "main_bar_dia_mm": 14,
            "stirrup_dia_mm": 6,
        }
        res_excel7 = {
            "spans": [5.0, 5.0],
            "max_pos_mu_knm": 59.0,
            "max_neg_face_mu_knm": 97.0,
            "max_face_vu_kn": 120.0,
            "support_critical_table": [
                {"support_index": 1, "target_id": "C8", "x_m": 0.0, "face_neg_mu_knm": 0.0, "face_vu_kn": 100.0},
                {"support_index": 2, "target_id": "B2", "x_m": 5.0, "face_neg_mu_knm": 97.0, "face_vu_kn": 120.0},
                {"support_index": 3, "target_id": "C9", "x_m": 10.0, "face_neg_mu_knm": 0.0, "face_vu_kn": 95.0},
            ],
            "span_critical_table": [
                {"span_index": 1, "length_m": 5.0, "max_pos_mu_knm": 59.0, "max_face_vu_kn": 120.0},
                {"span_index": 2, "length_m": 5.0, "max_pos_mu_knm": 50.0, "max_face_vu_kn": 110.0},
            ],
        }
        des_b7 = design_beam_aci318(bm_excel7, res_excel7, fc_mpa=20.0, fy_mpa=350.0, bar_dia_mm=14, stirrup_dia_mm=6, auto_size_section=False)
        self.assertEqual(des_b7["b_mm"], 600)
        self.assertEqual(des_b7["h_mm"], 290)
        self.assertAlmostEqual(des_b7["d_mm"], 252.0, places=1)
        self.assertEqual(des_b7["n_max_per_layer"], 13)
        self.assertEqual(des_b7["min_bars_excel"], 4)
        self.assertEqual(des_b7["max_bars_excel"], 19)
        self.assertAlmostEqual(des_b7["rho_min"], 0.004, places=4)
        self.assertAlmostEqual(des_b7["rho_max_single"], 0.01956, places=5)
        self.assertAlmostEqual(des_b7["as_one_bar_mm2"], 153.86, places=2)

        gov7 = des_b7["governing_flexure_details"]
        self.assertAlmostEqual(gov7["ku"], 0.14143, places=5)
        self.assertAlmostEqual(gov7["omega"], 0.15574, places=5)
        self.assertAlmostEqual(gov7["rho"], 0.0089, places=4)
        self.assertAlmostEqual(gov7["as_single_calc_mm2"], 1345.68, places=2)
        self.assertEqual(gov7["n_total"], 9)
        self.assertAlmostEqual(gov7["as_prov_mm2"], 1384.7, places=1)
        self.assertAlmostEqual(des_b7["rho_act"], 0.00916, places=4)

        station_bars = [st["n_bars"] for st in des_b7["station_design_table"]]
        self.assertEqual(station_bars, [4, 6, 9, 5, 4])

        # 3. Verify +100 mm step iterative section sizing when Hidden Beam starts at B_min = 400 mm
        bm_auto_hid = {
            "id": "B_AUTO",
            "beam_kind": "hidden",
            "initial_width_m": 0.40,
            "initial_depth_m": 0.29,
            "width_m": 0.40,
            "depth_m": 0.29,
            "spans": [5.0, 5.0],
            "main_bar_dia_mm": 14,
            "stirrup_dia_mm": 6,
        }
        # With Mu = -97 kN.m on 400x290 mm (d=252, nbs=8):
        # At B=400: Ku = 97e6 / (0.9 * 400 * 20 * 252^2) = 0.21215 -> w = 0.2484 -> p = 0.01419 -> As = 1430.8 -> nbr = 10 > nbs(8) -> B + 100 = 500 mm!
        # At B=500: nbs = 11, Ku = 0.16972 -> w = 0.19127 -> p = 0.01093 -> As = 1377.1 -> nbr = 9 <= nbs(11) -> stops at B = 500 mm!
        des_auto_500 = design_beam_aci318(bm_auto_hid, res_excel7, fc_mpa=20.0, fy_mpa=350.0, bar_dia_mm=14, stirrup_dia_mm=6, auto_size_section=True)
        self.assertEqual(des_auto_500["b_mm"], 500)
        self.assertTrue(des_auto_500["section_enlarged"])

        # And if we switch bar diameter from Φ14 to Φ12 on the same beam, nbr increases to 13 > nbs(500)=12 -> B widens by another +100 mm to 600 mm!
        des_auto_600 = design_beam_aci318(bm_auto_hid, res_excel7, fc_mpa=20.0, fy_mpa=350.0, bar_dia_mm=12, stirrup_dia_mm=6, auto_size_section=True)
        self.assertEqual(des_auto_600["b_mm"], 600)

        # 4. Verify coupled 2-pass O.W increase + Slab Rib Length L_rib reduction in analyze_all_story_beams_and_columns
        story_coupled = {
            "story_id": "02_Ground_Floor",
            "height_m": 3.0,
            "adopted_slab_thickness_cm": 29.0,
            "slab_factored_wu_kpa": 11.38,
            "default_main_bar_dia_mm": 12,
            "default_stirrup_dia_mm": 6,
            "columns": [
                {"id": "C1", "x": 0.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.5, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 11.0, "y": 0.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.0, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 5.5, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C6", "x": 11.0, "y": 5.0, "b_m": 0.20, "h_m": 0.40, "active": True},
            ],
            "beams": [
                {
                    "id": "B1",
                    "beam_kind": "hidden",
                    "width_m": 0.40,
                    "depth_m": 0.29,
                    "start_x": 0.0,
                    "start_y": 0.0,
                    "end_x": 11.0,
                    "end_y": 0.0,
                    "spans": [5.5, 5.5],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20, "center_coord_m": 0.0},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20, "center_coord_m": 5.5},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.20, "center_coord_m": 11.0},
                    ],
                },
                {
                    "id": "B2",
                    "beam_kind": "hidden",
                    "width_m": 0.40,
                    "depth_m": 0.29,
                    "start_x": 0.0,
                    "start_y": 5.0,
                    "end_x": 11.0,
                    "end_y": 5.0,
                    "spans": [5.5, 5.5],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.20, "center_coord_m": 0.0},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.20, "center_coord_m": 5.5},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.20, "center_coord_m": 11.0},
                    ],
                },
            ],
            "slabs": [
                {"id": "S1", "min_x": 0.0, "max_x": 11.0, "min_y": 0.0, "max_y": 5.0, "rib_direction_deg": 90}
            ],
            "openings": [],
        }
        bundle = analyze_all_story_beams_and_columns(story_coupled, fc_mpa=20.0, fy_mpa=350.0)
        b1_des = bundle["beam_designs"]["B1"]
        self.assertGreater(b1_des["b_mm"], 400)  # B1 widened from 400 mm in +100 mm steps!
        b1_loads = bundle["beam_results"]["B1"]["loads_applied"]
        # Verify O.W uses the new widened B1 width and w_Slab is reduced because L_rib decreased by ΔB!
        new_bw = b1_des["b_mm"] / 1000.0
        expected_ow = round(new_bw * 0.29 * 24.0 * 1.4, 2)
        self.assertAlmostEqual(b1_loads[0]["w_sw"], expected_ow, places=2)
        unreduced_w_slab = round(11.38 * (5.0 / 2.0), 2)
        self.assertLess(b1_loads[0]["w_slab"], unreduced_w_slab)


if __name__ == "__main__":
    unittest.main()






