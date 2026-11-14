"""
Unit Test Suite for Xpert Structural Design Studio (v1.4.0-revit-bim-ux)
"""

import os
import shutil
import tempfile
import unittest

from xpert_project_io import (
    MASTER_FILE_EXT,
    initialize_studio_project,
    load_studio_project_from_master_file,
    import_arch_dxf_underlay,
)
from xpert_structural_engine import (
    evaluate_story_thickness_and_optimization,
    analyze_all_story_beams_and_columns,
    check_duplicate_column,
    validate_and_build_beam_with_cantilevers,
    detect_story_grid_bays,
    pick_area_create_or_update_slab,
    reconcile_and_split_slabs_after_beam_change,
    select_elements_by_box,
    align_element_face_to_reference,
    move_selected_elements_by_delta,
    measure_distance_2d,
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
        self.assertTrue(master["master_file"].endswith("TestTower-00_Project_Master.xsd"))
        self.assertTrue(os.path.isfile(master["master_file"]))

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

    def test_boundary_only_never_creates_slabs_and_room_bounding_clear_bays(self):
        story_only_edge = {
            "slab_edge_polygon": [[0.0, 0.0], [9.0, 0.0], [9.0, 5.0], [0.0, 5.0]],
            "columns": [],
            "beams": [],
            "slabs": [],
        }
        self.assertEqual(detect_story_grid_bays(story_only_edge), [])

        story = {
            "slab_edge_polygon": [[0.0, 0.0], [9.0, 0.0], [9.0, 5.0], [0.0, 5.0]],
            "columns": [],
            "beams": [
                {"id": "B1", "start_x": 0.0, "start_y": 4.80, "end_x": 9.0, "end_y": 4.80, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B2", "start_x": 0.0, "start_y": 0.20, "end_x": 9.0, "end_y": 0.20, "width_m": 0.40, "beam_kind": "hidden"},
                {"id": "B3", "start_x": 0.10, "start_y": 0.0, "end_x": 0.10, "end_y": 5.0, "width_m": 0.20, "beam_kind": "drop"},
                {"id": "B4", "start_x": 8.90, "start_y": 0.0, "end_x": 8.90, "end_y": 5.0, "width_m": 0.20, "beam_kind": "drop"},
            ],
            "slabs": [],
            "openings": [],
        }
        bays = detect_story_grid_bays(story)
        self.assertEqual(len(bays), 1)
        self.assertAlmostEqual(bays[0]["clear_min_x"], 0.20, places=2)
        self.assertAlmostEqual(bays[0]["clear_max_x"], 8.80, places=2)

    def test_autocad_window_vs_crossing_selection_and_revit_align(self):
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

        ok_al, _ = align_element_face_to_reference(story, "column", "C1", "left", "x", 0.0, lock_constraint=True)
        self.assertTrue(ok_al)
        self.assertAlmostEqual(story["columns"][0]["x"], 0.10, places=2)

        m_res = measure_distance_2d((0.0, 0.0), (3.0, 4.0))
        self.assertAlmostEqual(m_res["distance_m"], 5.0, places=3)


if __name__ == "__main__":
    unittest.main()
