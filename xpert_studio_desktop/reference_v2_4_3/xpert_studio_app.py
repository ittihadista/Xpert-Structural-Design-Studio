"""
Xpert Structural Design Studio (v2.4.1-structural-bim-pro)
Main Desktop Application (PyQt6 + ezdxf)
Lead Structural Engineer & Product Owner: Eng. Yousef Mohammed Keshlaf
"""

from __future__ import annotations
import copy
import json
import math
import os
import sys
import traceback
from typing import Dict, Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen, QBrush, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from xpert_project_io import (
    STUDIO_VERSION,
    MASTER_FILE_EXT,
    DEFAULT_REBAR_DIAMETERS_TABLE,
    load_studio_global_settings,
    save_studio_global_settings,
    initialize_studio_project,
    load_studio_project_from_master_file,
    propagate_ground_columns_to_all_stories,
    sync_story_to_dxf,
    validate_project_name,
    compute_hollow_block_parameters,
    compute_smart_beam_tag_position,
    import_arch_dxf_underlay,
    set_active_project_log_dir,
    get_studio_log_file_path,
    log_studio_event,
    read_studio_log_tail,
    clear_studio_log,
)
from xpert_structural_engine import (
    STANDARD_WALL_THICKNESSES_CM,
    analyze_all_story_beams_and_columns,
    evaluate_story_thickness_and_optimization,
    get_slab_bounding_box,
    enforce_column_inside_slab_boundary,
    check_duplicate_column,
    renumber_story_columns_sequentially,
    reconcile_all_story_beams_supports_and_spans,
    validate_and_build_beam_with_cantilevers,
    detect_story_grid_bays,
    reconcile_and_split_slabs_after_beam_change,
    auto_fill_all_story_slabs,
    rotate_column_90_deg,
    pick_area_create_or_update_slab,
    toggle_slab_rib_by_label_click,
    flip_slab_rib_by_id,
    delete_selected_element_from_story,
    move_column_and_sync_connected_beams,
    move_beam_within_slab_boundary,
    select_elements_by_box,
    align_element_face_to_reference,
    move_selected_elements_by_delta,
    measure_distance_2d,
    compute_dimension_geometry,
    create_linear_dimension,
    auto_generate_exterior_dimensions,
    get_beam_span_segments,
    ensure_beam_wall_flags,
    set_story_wall_load_policy,
    set_beam_span_wall_flag,
    set_beam_span_wall_thickness,
    design_hollow_block_slab_rib,
    convert_beam_kind_and_section,
    is_point_in_opening,
    enforce_opening_adjacent_drop_beams_and_cascade,
    find_nearest_solid_edge_for_column,
    create_opening_with_priority_resolution,
)


class StartupDefaultsDialog(QDialog):
    """
    Startup Defaults Dialog:
    1. Default Projects Root Storage Folder.
    2. Reinforcing Steel Bar Diameters Table (including Φ6 Stirrups & Φ32 Main Bars).
    Accessible from both the Startup Welcome Screen (Start Menu) and the top Menu Bar.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Startup Defaults — Projects Folder & Rebar Diameters Table")
        self.setMinimumSize(700, 520)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.settings = load_studio_global_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setSpacing(12)

        grp_folder = QGroupBox("1. Default Projects Storage Folder")
        form_f = QFormLayout(grp_folder)
        row_f = QHBoxLayout()
        self.ed_root_folder = QLineEdit(str(self.settings.get("default_projects_root_folder", os.path.abspath("./XpertStudio_Projects"))))
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_folder)
        row_f.addWidget(self.ed_root_folder, 1)
        row_f.addWidget(btn_browse)
        form_f.addRow("Projects Root Directory:", row_f)
        vbox.addWidget(grp_folder)

        grp_rebar = QGroupBox("2. Reinforcing Steel Bar Diameters Table")
        v_reb = QVBoxLayout(grp_rebar)

        top_bar_row = QHBoxLayout()
        top_bar_row.addWidget(QLabel("Default Stirrup Bar:"))
        self.cb_def_stirrup = QComboBox()
        self.cb_def_stirrup.addItems(["6", "8", "10", "12"])
        self.cb_def_stirrup.setCurrentText(str(self.settings.get("default_stirrup_bar_mm", 8)))
        top_bar_row.addWidget(self.cb_def_stirrup)
        top_bar_row.addSpacing(18)

        top_bar_row.addWidget(QLabel("Default Main Longitudinal Bar:"))
        self.cb_def_main = QComboBox()
        self.cb_def_main.addItems(["12", "14", "16", "18", "20", "22", "25", "28", "32"])
        self.cb_def_main.setCurrentText(str(self.settings.get("default_main_bar_mm", 16)))
        top_bar_row.addWidget(self.cb_def_main)
        top_bar_row.addStretch(1)
        v_reb.addLayout(top_bar_row)

        rebar_rows = self.settings.get("rebar_diameters_table", DEFAULT_REBAR_DIAMETERS_TABLE)
        self.tbl_rebar = QTableWidget(len(rebar_rows), 6)
        self.tbl_rebar.setHorizontalHeaderLabels([
            "Active",
            "Designation",
            "Diameter d (mm)",
            "Area As (mm²)",
            "Unit Weight (kg/m)",
            "Usage Role",
        ])
        self.tbl_rebar.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r_idx, row in enumerate(rebar_rows):
            chk_item = QTableWidgetItem("Active")
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Checked if row.get("enabled", True) else Qt.CheckState.Unchecked)
            self.tbl_rebar.setItem(r_idx, 0, chk_item)
            self.tbl_rebar.setItem(r_idx, 1, QTableWidgetItem(str(row.get("bar_name", f"Φ{row.get('diameter_mm', 16)}"))))
            self.tbl_rebar.setItem(r_idx, 2, QTableWidgetItem(str(row.get("diameter_mm", 16))))
            self.tbl_rebar.setItem(r_idx, 3, QTableWidgetItem(f"{float(row.get('area_mm2', 201.06)):.2f}"))
            self.tbl_rebar.setItem(r_idx, 4, QTableWidgetItem(f"{float(row.get('weight_kg_m', 1.578)):.3f}"))
            self.tbl_rebar.setItem(r_idx, 5, QTableWidgetItem(str(row.get("role", "Longitudinal"))))

        v_reb.addWidget(self.tbl_rebar, 1)
        vbox.addWidget(grp_rebar, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText("Save Startup Defaults")
        btn_ok.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 6px 14px;")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Default Projects Root Folder", self.ed_root_folder.text())
        if folder:
            self.ed_root_folder.setText(folder)

    def _on_save(self) -> None:
        self.settings["default_projects_root_folder"] = self.ed_root_folder.text().strip() or os.path.abspath("./XpertStudio_Projects")
        self.settings["default_stirrup_bar_mm"] = int(self.cb_def_stirrup.currentText())
        self.settings["default_main_bar_mm"] = int(self.cb_def_main.currentText())

        updated_table: List[Dict[str, Any]] = []
        for r_idx in range(self.tbl_rebar.rowCount()):
            it_chk = self.tbl_rebar.item(r_idx, 0)
            enabled = (it_chk.checkState() == Qt.CheckState.Checked) if it_chk else True
            bname = self.tbl_rebar.item(r_idx, 1).text().strip() if self.tbl_rebar.item(r_idx, 1) else "Φ16"
            try:
                d_mm = int(float(self.tbl_rebar.item(r_idx, 2).text()))
            except Exception:
                d_mm = 16
            area_mm2 = round(math.pi * (d_mm ** 2) / 4.0, 2)
            wt_kg = round((d_mm ** 2) / 162.2, 3)
            role_txt = self.tbl_rebar.item(r_idx, 5).text().strip() if self.tbl_rebar.item(r_idx, 5) else "Longitudinal"
            updated_table.append({
                "bar_name": bname,
                "diameter_mm": d_mm,
                "area_mm2": area_mm2,
                "weight_kg_m": wt_kg,
                "role": role_txt,
                "enabled": enabled,
            })
        self.settings["rebar_diameters_table"] = updated_table
        save_studio_global_settings(self.settings)
        self.accept()


class StudioOptionsDialog(QDialog):
    """
    Options Dialog:
    1. Material Properties (f'c, Fy, Fyt, γ_c = 24 kN/m³, q_all).
    2. Hollow-Block Slab Data (Slab Thickness h = 30 cm, Topping Slab hs = 10 cm,
       Block Dimensions 40×25×20 cm, Rib Width bw = 15 cm, Finish Load = 1.5 kN/m², Live Load = 2.0 kN/m²,
       Wu(rib) = 6.44 kN/m'/rib, Wu(m×m) = 11.71 kN/m²).
    Accessible from both the Startup Welcome Screen (Start Menu) and the top Menu Bar.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        active_project: Optional[Dict[str, Any]] = None,
        active_story: Optional[Dict[str, Any]] = None,
        master_project: Optional[Dict[str, Any]] = None,
        current_story_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Options — Material Properties & Hollow-Block Slab Data (ACI 318-19)")
        self.setMinimumWidth(660)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.settings = load_studio_global_settings()
        self.active_project = active_project if active_project is not None else master_project
        self.active_story = active_story if active_story is not None else current_story_data
        self._updating_fields = False
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setSpacing(12)

        mat_cfg = dict(self.settings.get("materials_and_soil", {}))
        if self.active_project and isinstance(self.active_project.get("materials_and_soil"), dict):
            mat_cfg.update(self.active_project["materials_and_soil"])

        hb_cfg = dict(self.settings.get("hollow_block_slab_data", {}))
        if self.active_project and isinstance(self.active_project.get("hollow_block_slab_data"), dict):
            hb_cfg.update(self.active_project["hollow_block_slab_data"])
        if self.active_story and isinstance(self.active_story.get("hollow_block"), dict):
            st_hb = self.active_story["hollow_block"]
            hb_cfg["slab_thickness_cm"] = st_hb.get("total_thickness_cm", hb_cfg.get("slab_thickness_cm", 30.0))
            hb_cfg["top_compression_slab_cm"] = st_hb.get("topping_thickness_cm", hb_cfg.get("top_compression_slab_cm", 10.0))
            hb_cfg["rib_width_cm"] = st_hb.get("rib_width_cm", hb_cfg.get("rib_width_cm", 15.0))
            hb_cfg["block_width_cm"] = st_hb.get("block_width_cm", hb_cfg.get("block_width_cm", 40.0))
            hb_cfg["finish_load_kn_m2"] = st_hb.get("finishing_load_kpa", hb_cfg.get("finish_load_kn_m2", 1.5))
            hb_cfg["live_load_kn_m2"] = st_hb.get("live_load_kpa", hb_cfg.get("live_load_kn_m2", 2.0))

        grp_mat = QGroupBox("1. Material Properties & Soil Bearing")
        form_m = QFormLayout(grp_mat)

        self.sp_fc = QDoubleSpinBox()
        self.sp_fc.setRange(15.0, 100.0)
        self.sp_fc.setValue(float(mat_cfg.get("fc_mpa", 20.0)))
        self.sp_fc.setSuffix(" MPa")
        form_m.addRow("Concrete Compressive Strength f'c:", self.sp_fc)

        self.sp_fy = QDoubleSpinBox()
        self.sp_fy.setRange(200.0, 1000.0)
        self.sp_fy.setValue(float(mat_cfg.get("fy_mpa", 350.0)))
        self.sp_fy.setSuffix(" MPa")
        form_m.addRow("Main Longitudinal Steel Yield Strength Fy:", self.sp_fy)

        self.sp_fyt = QDoubleSpinBox()
        self.sp_fyt.setRange(200.0, 600.0)
        self.sp_fyt.setValue(float(mat_cfg.get("fy_stirrups_mpa", 280.0)))
        self.sp_fyt.setSuffix(" MPa")
        form_m.addRow("Transverse Stirrup Yield Strength Fyt:", self.sp_fyt)

        self.sp_gamma = QDoubleSpinBox()
        self.sp_gamma.setRange(18.0, 30.0)
        self.sp_gamma.setValue(float(mat_cfg.get("concrete_unit_weight_kn_m3", mat_cfg.get("gamma_c_kn_m3", 24.0))))
        self.sp_gamma.setSuffix(" kN/m³")
        form_m.addRow("Reinforced Concrete Unit Weight γ_c:", self.sp_gamma)

        self.sp_qall = QDoubleSpinBox()
        self.sp_qall.setRange(50.0, 2000.0)
        self.sp_qall.setValue(float(mat_cfg.get("soil_bearing_qall_kn_m2", 150.0)))
        self.sp_qall.setSuffix(" kN/m²")
        form_m.addRow("Allowable Soil Bearing Capacity q_all:", self.sp_qall)
        vbox.addWidget(grp_mat)

        grp_hb = QGroupBox("2. Hollow-Block Slab Data & Default Loads")
        form_hb = QFormLayout(grp_hb)

        self.sp_slab_t = QDoubleSpinBox()
        self.sp_slab_t.setRange(16.0, 80.0)
        cur_t = float(self.active_story.get("adopted_slab_thickness_cm", hb_cfg.get("slab_thickness_cm", 30.0))) if self.active_story else float(hb_cfg.get("slab_thickness_cm", 30.0))
        self.sp_slab_t.setValue(cur_t if cur_t >= 16.0 else 30.0)
        self.sp_slab_t.setSuffix(" cm")
        form_hb.addRow("Total Hollow-Block Slab Thickness (h):", self.sp_slab_t)

        init_h_cm = self.sp_slab_t.value()
        init_blk_h = float(hb_cfg.get("block_height_cm", 20.0 if init_h_cm >= 25.0 else 16.0))
        if abs(init_blk_h - 16.0) >= 0.5 and abs(init_blk_h - 20.0) >= 0.5:
            init_blk_h = 20.0 if init_h_cm >= 25.0 else 16.0
        init_hs_cm = max(5.0, init_h_cm - init_blk_h)

        self.sp_top_slab = QDoubleSpinBox()
        self.sp_top_slab.setRange(4.0, 20.0)
        self.sp_top_slab.setValue(init_hs_cm)
        self.sp_top_slab.setSuffix(" cm")
        form_hb.addRow("Topping Slab Thickness (hs = h - h_block):", self.sp_top_slab)

        self.sp_block_h = QDoubleSpinBox()
        self.sp_block_h.setRange(16.0, 20.0)
        self.sp_block_h.setSingleStep(4.0)
        self.sp_block_h.setValue(init_blk_h)
        self.sp_block_h.setSuffix(" cm (Standard: 20 or 16 cm)")
        form_hb.addRow("Hollow Block Height (Standard 20 or 16 cm):", self.sp_block_h)

        blk_row = QHBoxLayout()
        self.sp_block_w = QDoubleSpinBox()
        self.sp_block_w.setRange(20.0, 60.0)
        self.sp_block_w.setValue(float(hb_cfg.get("block_width_cm", 40.0)))
        self.sp_block_w.setSuffix(" cm")
        self.sp_block_l = QDoubleSpinBox()
        self.sp_block_l.setRange(15.0, 50.0)
        self.sp_block_l.setValue(float(hb_cfg.get("block_length_cm", 25.0)))
        self.sp_block_l.setSuffix(" cm")
        blk_row.addWidget(QLabel("Width (S):"))
        blk_row.addWidget(self.sp_block_w)
        blk_row.addWidget(QLabel("× Length:"))
        blk_row.addWidget(self.sp_block_l)
        form_hb.addRow("Hollow Block Plan Size (cm):", blk_row)

        self.sp_rib_w = QDoubleSpinBox()
        self.sp_rib_w.setRange(10.0, 30.0)
        self.sp_rib_w.setValue(float(hb_cfg.get("rib_width_cm", 15.0)))
        self.sp_rib_w.setSuffix(" cm")
        form_hb.addRow("Concrete Rib Width bw (cm):", self.sp_rib_w)

        ld_row = QHBoxLayout()
        self.sp_finish = QDoubleSpinBox()
        self.sp_finish.setRange(0.0, 20.0)
        self.sp_finish.setValue(float(hb_cfg.get("finish_load_kn_m2", 1.5)))
        self.sp_finish.setSuffix(" kN/m²")
        self.sp_finish_load = self.sp_finish
        self.sp_live = QDoubleSpinBox()
        self.sp_live.setRange(0.0, 50.0)
        self.sp_live.setValue(float(hb_cfg.get("live_load_kn_m2", 2.0)))
        self.sp_live.setSuffix(" kN/m²")
        ld_row.addWidget(QLabel("W_finishing:"))
        ld_row.addWidget(self.sp_finish)
        ld_row.addWidget(QLabel("Live Load (LL):"))
        ld_row.addWidget(self.sp_live)
        form_hb.addRow("Floor Finish & Live Loads:", ld_row)

        self.sp_slab_wu = QDoubleSpinBox()
        self.sp_slab_wu.setRange(2.0, 40.0)
        self.sp_slab_wu.setDecimals(2)
        cur_wu = float(self.active_story.get("slab_factored_wu_kpa", hb_cfg.get("slab_factored_wu_kpa", 11.71))) if self.active_story else float(hb_cfg.get("slab_factored_wu_kpa", 11.71))
        self.sp_slab_wu.setValue(cur_wu)
        self.sp_slab_wu.setSuffix(" kN/m²")
        form_hb.addRow("Factored Slab Load to Beams Wu(m×m):", self.sp_slab_wu)

        self.lbl_rib_wu_preview = QLabel("Wu(rib) = 6.44 kN/m'/rib  |  Wu(m×m) = 11.71 kN/m²")
        self.lbl_rib_wu_preview.setStyleSheet("color: #15803D; font-weight: bold;")
        self.lbl_computed_qu = self.lbl_rib_wu_preview
        form_hb.addRow("Calculated Rib & Area Load:", self.lbl_rib_wu_preview)

        self.sp_wall_w = QDoubleSpinBox()
        self.sp_wall_w.setRange(0.0, 60.0)
        cur_wall = float(self.active_story.get("default_wall_load_kn_m", hb_cfg.get("default_wall_load_kn_m", 10.50))) if self.active_story else float(hb_cfg.get("default_wall_load_kn_m", 10.50))
        self.sp_wall_w.setValue(cur_wall)
        self.sp_wall_w.setSuffix(" kN/m")
        form_hb.addRow("Default 20cm Masonry Wall Load (W_wall):", self.sp_wall_w)
        vbox.addWidget(grp_hb)

        for sp_w in (self.sp_slab_t, self.sp_block_h, self.sp_top_slab, self.sp_block_w, self.sp_block_l, self.sp_rib_w, self.sp_finish, self.sp_live, self.sp_gamma):
            sp_w.valueChanged.connect(self._recompute_hordi_loads_live)
        self._recompute_hordi_loads_live()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText("Save Options && Apply")
        btn_ok.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 6px 14px;")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)

    def _recompute_hordi_loads_live(self) -> None:
        if self._updating_fields:
            return
        self._updating_fields = True
        try:
            h_cm = self.sp_slab_t.value()
            sender = self.sender()
            if sender is self.sp_block_h:
                raw_blk = self.sp_block_h.value()
                std_blk_h = 20.0 if raw_blk >= 18.0 else 16.0
                if abs(raw_blk - std_blk_h) > 1e-3:
                    self.sp_block_h.setValue(std_blk_h)
            elif sender is self.sp_top_slab:
                std_blk_h = self.sp_block_h.value()
            else:
                std_blk_h = 20.0 if h_cm >= 25.0 else 16.0
                self.sp_block_h.setValue(std_blk_h)
            hs_cm = max(5.0, h_cm - std_blk_h)
            if sender is not self.sp_top_slab:
                self.sp_top_slab.setValue(hs_cm)
            else:
                hs_cm = self.sp_top_slab.value()
            res = compute_hollow_block_parameters(
                slab_thickness_cm=h_cm,
                rib_width_cm=self.sp_rib_w.value(),
                block_width_cm=self.sp_block_w.value(),
                block_length_cm=self.sp_block_l.value(),
                finish_load_kn_m2=self.sp_finish.value(),
                live_load_kn_m2=self.sp_live.value(),
                top_flange_cm=hs_cm,
                block_height_cm=std_blk_h,
                gamma_c_kn_m3=self.sp_gamma.value(),
            )
            self.sp_slab_wu.setValue(float(res["total_factored_wu_kn_m2"]))
            self.lbl_rib_wu_preview.setText(
                f"Wu(rib) = {res['wu_rib_kn_m']:.2f} kN/m'/rib  |  Wu(m×m) = {res['total_factored_wu_kn_m2']:.2f} kN/m²"
            )
        finally:
            self._updating_fields = False

    def _on_save(self) -> None:
        mat_data = {
            "fc_mpa": round(self.sp_fc.value(), 2),
            "fy_mpa": round(self.sp_fy.value(), 2),
            "fy_stirrups_mpa": round(self.sp_fyt.value(), 2),
            "concrete_unit_weight_kn_m3": round(self.sp_gamma.value(), 2),
            "gamma_c_kn_m3": round(self.sp_gamma.value(), 2),
            "soil_bearing_qall_kn_m2": round(self.sp_qall.value(), 2),
        }
        hordi_res = compute_hollow_block_parameters(
            slab_thickness_cm=self.sp_slab_t.value(),
            rib_width_cm=self.sp_rib_w.value(),
            block_width_cm=self.sp_block_w.value(),
            block_length_cm=self.sp_block_l.value(),
            finish_load_kn_m2=self.sp_finish.value(),
            live_load_kn_m2=self.sp_live.value(),
            top_flange_cm=self.sp_top_slab.value(),
            block_height_cm=self.sp_block_h.value(),
            gamma_c_kn_m3=self.sp_gamma.value(),
        )
        hb_data = {
            "slab_thickness_cm": round(self.sp_slab_t.value(), 1),
            "top_compression_slab_cm": round(self.sp_top_slab.value(), 1),
            "topping_thickness_cm": round(self.sp_top_slab.value(), 1),
            "block_height_cm": round(self.sp_block_h.value(), 1),
            "block_width_cm": round(self.sp_block_w.value(), 1),
            "block_length_cm": round(self.sp_block_l.value(), 1),
            "rib_width_cm": round(self.sp_rib_w.value(), 1),
            "slab_factored_wu_kpa": round(self.sp_slab_wu.value(), 2),
            "wu_rib_kn_m": round(hordi_res["wu_rib_kn_m"], 2),
            "finish_load_kn_m2": round(self.sp_finish.value(), 2),
            "live_load_kn_m2": round(self.sp_live.value(), 2),
            "default_wall_load_kn_m": round(self.sp_wall_w.value(), 2),
        }
        self.settings["materials_and_soil"] = mat_data
        self.settings["hollow_block_slab_data"] = hb_data
        save_studio_global_settings(self.settings)

        if self.active_project is not None:
            self.active_project.setdefault("materials_and_soil", {}).update(mat_data)
            self.active_project["hollow_block_slab_data"] = dict(hb_data)
            loads_def = self.active_project.setdefault("loads_and_defaults", {})
            loads_def["finish_load_kn_m2"] = hb_data["finish_load_kn_m2"]
            loads_def["live_load_kn_m2"] = hb_data["live_load_kn_m2"]
            loads_def["rib_width_cm"] = hb_data["rib_width_cm"]
            loads_def["hollow_block_defaults"] = dict(hordi_res)
        if self.active_story is not None:
            self.active_story["adopted_slab_thickness_cm"] = hb_data["slab_thickness_cm"]
            self.active_story["slab_factored_wu_kpa"] = hb_data["slab_factored_wu_kpa"]
            self.active_story["default_wall_load_kn_m"] = hb_data["default_wall_load_kn_m"]
            self.active_story["hollow_block_params"] = dict(hordi_res)
            self.active_story["hollow_block"] = {
                "total_thickness_cm": hb_data["slab_thickness_cm"],
                "topping_thickness_cm": hb_data["top_compression_slab_cm"],
                "block_height_cm": hb_data["block_height_cm"],
                "rib_width_cm": hb_data["rib_width_cm"],
                "rib_width_top_cm": hb_data["rib_width_cm"],
                "block_width_cm": hb_data["block_width_cm"],
                "gamma_c_kn_m3": mat_data["gamma_c_kn_m3"],
                "finishing_load_kpa": hb_data["finish_load_kn_m2"],
                "live_load_kpa": hb_data["live_load_kn_m2"],
                "wu_rib_kn_m": hb_data["wu_rib_kn_m"],
                "factored_wu_kpa": hb_data["slab_factored_wu_kpa"],
            }

        self.accept()


class StartupWelcomeDialog(QDialog):
    """
    Compact Startup Launch Window ("Start Menu") offering:
    1. Start a New Structural Project (opens NewProjectSetupDialog)
    2. Open an Existing Project (`*.xsd`) (goes directly to Ground Floor Plan)
    Plus direct buttons for:
    - Startup Defaults (Projects Folder & Rebar Table)
    - Options (Materials & Hollow-Block Data)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Welcome — Xpert Structural Design Studio ({STUDIO_VERSION})")
        self.setFixedSize(580, 370)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.choice: Optional[str] = None
        self.selected_master_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(24, 20, 24, 20)
        vbox.setSpacing(14)

        lbl_title = QLabel("Xpert Structural Design Studio")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0284C7;")
        lbl_sub = QLabel(
            "Standalone Structural BIM, Analysis & Design Suite (ACI 318-19)\n"
            "Select how you would like to begin your session:"
        )
        lbl_sub.setStyleSheet("color: #475569; font-size: 12px;")
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_sub)

        btn_new = QPushButton("1. Create New Structural Project...")
        btn_new.setMinimumHeight(54)
        btn_new.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #16A34A; color: white; border-radius: 6px; padding: 10px;"
        )
        btn_new.clicked.connect(self._on_choose_new)
        vbox.addWidget(btn_new)

        btn_open = QPushButton(f"2. Open Existing Structural Project (*{MASTER_FILE_EXT})...")
        btn_open.setMinimumHeight(54)
        btn_open.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #0284C7; color: white; border-radius: 6px; padding: 10px;"
        )
        btn_open.clicked.connect(self._on_choose_open)
        vbox.addWidget(btn_open)

        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(10)
        btn_defaults = QPushButton("Startup Defaults (Folder & Rebar Table)...")
        btn_defaults.setMinimumHeight(38)
        btn_defaults.setStyleSheet(
            "font-size: 12px; font-weight: bold; background-color: #F1F5F9; color: #0F172A; border: 1px solid #94A3B8; border-radius: 5px; padding: 6px 10px;"
        )
        btn_defaults.clicked.connect(self._on_open_startup_defaults)
        cfg_row.addWidget(btn_defaults)

        btn_options = QPushButton("Options (Materials & Hollow-Block Slab)...")
        btn_options.setMinimumHeight(38)
        btn_options.setStyleSheet(
            "font-size: 12px; font-weight: bold; background-color: #F1F5F9; color: #0F172A; border: 1px solid #94A3B8; border-radius: 5px; padding: 6px 10px;"
        )
        btn_options.clicked.connect(self._on_open_options)
        cfg_row.addWidget(btn_options)
        vbox.addLayout(cfg_row)

        vbox.addStretch(1)

    def _on_choose_new(self) -> None:
        self.choice = "NEW"
        self.accept()

    def _on_choose_open(self) -> None:
        global_cfg = load_studio_global_settings()
        start_dir = str(global_cfg.get("default_projects_root_folder", os.path.abspath("./XpertStudio_Projects")))
        if not os.path.isdir(start_dir):
            start_dir = os.path.abspath(".")
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            f"Open Xpert Structural Design Project (*{MASTER_FILE_EXT})",
            start_dir,
            f"Xpert Structural Project (*{MASTER_FILE_EXT});;Legacy Project Files (*.xpert *-00_Project_Master.json);;All Files (*)",
        )
        if fpath and os.path.isfile(fpath):
            self.selected_master_path = fpath
            self.choice = "OPEN"
            self.accept()

    def _on_open_startup_defaults(self) -> None:
        dlg = StartupDefaultsDialog(self)
        dlg.exec()

    def _on_open_options(self) -> None:
        dlg = StudioOptionsDialog(self)
        dlg.exec()


class NewProjectSetupDialog(QDialog):
    """
    Modal Project Definition Dialog (opened only when user chooses 'Create New Project').
    Pre-populated from `load_studio_global_settings()`.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Structural Project Data — Xpert Structural Design Studio")
        self.setMinimumWidth(680)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.global_settings = load_studio_global_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        mat_cfg = self.global_settings.get("materials_and_soil", {})
        hb_cfg = self.global_settings.get("hollow_block_slab_data", {})
        def_folder = str(self.global_settings.get("default_projects_root_folder", os.path.abspath("./XpertStudio_Projects")))

        grp_id = QGroupBox(f"1. New Project Identity && Workspace Folder (Master Extension: *{MASTER_FILE_EXT})")
        form_id = QFormLayout(grp_id)

        self.ed_name = QLineEdit("Villa_Al_Yasmin")
        form_id.addRow("Project Name:", self.ed_name)

        folder_row = QHBoxLayout()
        self.ed_folder = QLineEdit(def_folder)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.ed_folder)
        folder_row.addWidget(btn_browse)
        form_id.addRow("Root Projects Folder:", folder_row)
        root_layout.addWidget(grp_id)

        grp_stories = QGroupBox("2. Story Hierarchy && Exact Story Heights")
        form_stories = QFormLayout(grp_stories)

        self.sp_ground_h = QDoubleSpinBox()
        self.sp_ground_h.setRange(2.50, 12.00)
        self.sp_ground_h.setValue(3.20)
        self.sp_ground_h.setSuffix(" m")
        form_stories.addRow("Ground Floor Height (Mandatory Start):", self.sp_ground_h)

        self.chk_basement = QCheckBox("Include Basement Floor (01_Basement_Slab)")
        self.sp_basement_h = QDoubleSpinBox()
        self.sp_basement_h.setRange(2.20, 10.00)
        self.sp_basement_h.setValue(3.00)
        self.sp_basement_h.setSuffix(" m")
        self.sp_basement_h.setEnabled(False)
        self.chk_basement.toggled.connect(self.sp_basement_h.setEnabled)
        bs_row = QHBoxLayout()
        bs_row.addWidget(self.chk_basement)
        bs_row.addWidget(QLabel("Basement Height:"))
        bs_row.addWidget(self.sp_basement_h)
        form_stories.addRow("Basement Option:", bs_row)

        self.sp_upper_count = QSpinBox()
        self.sp_upper_count.setRange(0, 50)
        self.sp_upper_count.setValue(2)
        self.sp_upper_count.setSuffix(" floors")
        form_stories.addRow("Floors Above Ground (Count):", self.sp_upper_count)

        self.sp_upper_h = QDoubleSpinBox()
        self.sp_upper_h.setRange(2.50, 10.00)
        self.sp_upper_h.setValue(3.00)
        self.sp_upper_h.setSuffix(" m")
        form_stories.addRow("Upper Floor Height:", self.sp_upper_h)

        self.cb_upper_mode = QComboBox()
        self.cb_upper_mode.addItems(["Typical Repeated Floor", "Distinct Individual Floors"])
        form_stories.addRow("Upper Floors Mode:", self.cb_upper_mode)

        self.chk_penthouse = QCheckBox("Include Roof Annex / Penthouse Floor")
        self.chk_penthouse.setChecked(False)
        self.sp_penthouse_h = QDoubleSpinBox()
        self.sp_penthouse_h.setRange(2.40, 8.00)
        self.sp_penthouse_h.setValue(3.00)
        self.sp_penthouse_h.setSuffix(" m")
        self.sp_penthouse_h.setEnabled(False)
        self.chk_penthouse.toggled.connect(self.sp_penthouse_h.setEnabled)
        ph_row = QHBoxLayout()
        ph_row.addWidget(self.chk_penthouse)
        ph_row.addWidget(QLabel("Penthouse Height:"))
        ph_row.addWidget(self.sp_penthouse_h)
        form_stories.addRow("Roof Annex Option:", ph_row)

        self.sp_found_depth = QDoubleSpinBox()
        self.sp_found_depth.setRange(0.50, 25.00)
        self.sp_found_depth.setValue(1.50)
        self.sp_found_depth.setSuffix(" m")
        form_stories.addRow("Foundation / Excavation Depth:", self.sp_found_depth)
        root_layout.addWidget(grp_stories)

        grp_mat = QGroupBox("3. Materials, Soil Bearing && Default Section Dimensions (ACI 318-19)")
        form_mat = QFormLayout(grp_mat)

        self.sp_fc = QDoubleSpinBox()
        self.sp_fc.setRange(15.0, 100.0)
        self.sp_fc.setValue(float(mat_cfg.get("fc_mpa", 20.0)))
        self.sp_fc.setSuffix(" MPa")
        form_mat.addRow("Concrete f'c:", self.sp_fc)

        self.sp_fy = QDoubleSpinBox()
        self.sp_fy.setRange(200.0, 1000.0)
        self.sp_fy.setValue(float(mat_cfg.get("fy_mpa", 350.0)))
        self.sp_fy.setSuffix(" MPa")
        form_mat.addRow("Reinforcement Fy:", self.sp_fy)

        self.sp_qall = QDoubleSpinBox()
        self.sp_qall.setRange(50.0, 2000.0)
        self.sp_qall.setValue(float(mat_cfg.get("soil_bearing_qall_kn_m2", 150.0)))
        self.sp_qall.setSuffix(" kN/m²")
        form_mat.addRow("Soil Bearing Capacity (q_all):", self.sp_qall)

        self.sp_finish = QDoubleSpinBox()
        self.sp_finish.setRange(0.0, 20.0)
        self.sp_finish.setValue(float(hb_cfg.get("finish_load_kn_m2", 1.5)))
        self.sp_finish.setSuffix(" kN/m²")
        form_mat.addRow("Floor Finish Load:", self.sp_finish)

        self.sp_live = QDoubleSpinBox()
        self.sp_live.setRange(0.0, 50.0)
        self.sp_live.setValue(float(hb_cfg.get("live_load_kn_m2", 2.0)))
        self.sp_live.setSuffix(" kN/m²")
        form_mat.addRow("Live Load:", self.sp_live)

        lbl_col_note = QLabel("Initial Column Section: 0.20 × 0.40 m | Hidden Beam Width: 0.30 m | Drop Beam Width: 0.20 m")
        lbl_col_note.setStyleSheet("color: #059669; font-weight: bold;")
        form_mat.addRow("Section Defaults:", lbl_col_note)

        root_layout.addWidget(grp_mat)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText("Create Project && Open Studio")
        btn_ok.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 6px 14px;")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root_layout.addWidget(btns)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Root Projects Directory")
        if folder:
            self.ed_folder.setText(folder)

    def _on_accept(self) -> None:
        ok, _, _, err = validate_project_name(self.ed_name.text())
        if not ok:
            QMessageBox.warning(self, "Invalid Project Name", err)
            return
        self.accept()

    def get_config(self) -> Dict[str, Any]:
        return {
            "project_name": self.ed_name.text().strip(),
            "root_directory": self.ed_folder.text().strip(),
            "ground_floor_height_m": self.sp_ground_h.value(),
            "include_basement": self.chk_basement.isChecked(),
            "basement_height_m": self.sp_basement_h.value(),
            "floors_above_ground": self.sp_upper_count.value(),
            "upper_floor_height_m": self.sp_upper_h.value(),
            "upper_floors_mode": "typical" if self.cb_upper_mode.currentIndex() == 0 else "distinct",
            "include_penthouse": self.chk_penthouse.isChecked(),
            "penthouse_height_m": self.sp_penthouse_h.value(),
            "foundation_depth_m": self.sp_found_depth.value(),
            "fc_mpa": self.sp_fc.value(),
            "fy_mpa": self.sp_fy.value(),
            "soil_bearing_qall_kn_m2": self.sp_qall.value(),
            "finish_load_kn_m2": self.sp_finish.value(),
            "live_load_kn_m2": self.sp_live.value(),
        }


class MoveNumericDeltaDialog(QDialog):
    """
    Modal Dialog for entering exact ΔX (m) and ΔY (m) displacements for selected elements.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Move Selected Elements by Numeric Offset (ΔX, ΔY)")
        self.setFixedWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        form = QFormLayout()
        self.sp_dx = QDoubleSpinBox()
        self.sp_dx.setRange(-50.0, 50.0)
        self.sp_dx.setDecimals(3)
        self.sp_dx.setSingleStep(0.10)
        self.sp_dx.setSuffix(" m")
        form.addRow("Horizontal Offset ΔX (+Right / -Left):", self.sp_dx)

        self.sp_dy = QDoubleSpinBox()
        self.sp_dy.setRange(-50.0, 50.0)
        self.sp_dy.setDecimals(3)
        self.sp_dy.setSingleStep(0.10)
        self.sp_dy.setSuffix(" m")
        form.addRow("Vertical Offset ΔY (+Up / -Down):", self.sp_dy)
        vbox.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)


class DiagnosticLogDialog(QDialog):
    """
    Live Engineering & Session Diagnostic Log Viewer (`xpert_studio_session.log`):
    Allows Eng. Yousef to inspect, copy, refresh, or clear every calculation,
    conflict resolution, Hordi load, beam design iteration, and runtime event.
    """

    def __init__(self, parent: Optional[QWidget] = None, project_dir: Optional[str] = None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.setWindowTitle(f"Session & Engineering Diagnostic Log ({STUDIO_VERSION})")
        self.setMinimumSize(860, 560)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._build_ui()
        self.refresh_log()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setSpacing(8)

        log_path = get_studio_log_file_path(self.project_dir)
        lbl_path = QLabel(f"Diagnostic Log File: {log_path}")
        lbl_path.setStyleSheet("color: #0369A1; font-weight: bold;")
        vbox.addWidget(lbl_path)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "QPlainTextEdit { background: #0F172A; color: #E2E8F0; font-family: Consolas, 'Courier New', monospace; "
            "font-size: 11px; border: 1px solid #334155; border-radius: 4px; padding: 8px; }"
        )
        vbox.addWidget(self.txt_log, 1)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_log)
        btn_copy = QPushButton("Copy Full Log")
        btn_copy.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold;")
        btn_copy.clicked.connect(self._copy_log)
        btn_clear = QPushButton("Clear Log")
        btn_clear.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold;")
        btn_clear.clicked.connect(self._clear_log)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_copy)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        vbox.addLayout(btn_row)

    def refresh_log(self) -> None:
        content = read_studio_log_tail(max_lines=600, project_dir=self.project_dir)
        self.txt_log.setPlainText(content)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _copy_log(self) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(self.txt_log.toPlainText())

    def _clear_log(self) -> None:
        clear_studio_log(self.project_dir)
        log_studio_event("SESSION", "Diagnostic log cleared by user.")
        self.refresh_log()


class SlabRibDesignDialog(QDialog):
    """
    Hollow-Block (Hordi) Slab Rib Design & Cross-Section Window (v2.0.0-structural-bim-pro):
    Matches Eng. Yousef's Excel Sheet ('Design of rib slab') 100%:
    - Interactive Slab Selector (S1..Sn) and Main Bottom Bar Diameter Selector (12 mm, 14 mm, 16 mm).
    - Full Load Breakdown distinguishing:
        1. Wu_rib (kN/m'/rib) -> used for Rib Flexure & Shear Design (e.g. 6.44 kN/m'/rib for h=300mm).
        2. Wu(m×m) (kN/m²) = Wu_rib / (S + bw1) -> transferred to Supporting Beams (e.g. 11.71 kN/m² for h=300mm).
    - Simply Supported Moment Mu = Wu_rib * L² / 8 using full center-to-center span L.
    - 2D Engineered Cross-Section Drawing of One Rib + Adjacent Hollow Blocks + Open Triangular Stirrup (∅6)
      + 1 Top Fixation Bar (1∅10) + Bottom Main Bars (e.g. 2∅12).
    """

    def __init__(
        self,
        parent_studio: Optional["XpertStudioMainWindow"] = None,
        story_data: Optional[Dict[str, Any]] = None,
        initial_slab_id: Optional[str] = None,
        fc_mpa: Optional[float] = None,
        fy_mpa: Optional[float] = None,
    ):
        super().__init__(parent_studio)
        self.studio = parent_studio
        self.story_data = story_data if story_data is not None else (parent_studio.current_story_data if parent_studio else {})
        self.slabs = [s for s in self.story_data.get("slabs", []) if not s.get("is_void", False)]
        if fc_mpa is not None:
            self.fc_mpa = float(fc_mpa)
        elif self.studio and self.studio.master_project:
            self.fc_mpa = float(self.studio.master_project["materials_and_soil"]["fc_mpa"])
        else:
            self.fc_mpa = 20.0

        if fy_mpa is not None:
            self.fy_mpa = float(fy_mpa)
        elif self.studio and self.studio.master_project:
            self.fy_mpa = float(self.studio.master_project["materials_and_soil"]["fy_mpa"])
        else:
            self.fy_mpa = 350.0

        self.setWindowTitle("Design of Hollow-Block (Hordi) Rib Slab — Loads, Flexure, Shear & Cross-Section (ACI 318)")
        self.setMinimumSize(1120, 740)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._updating_controls = False
        self._build_ui(initial_slab_id)

    def _build_ui(self, initial_slab_id: Optional[str]) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(8)

        # Top Control Bar
        top_bar = QFrame()
        top_bar.setStyleSheet(
            "QFrame { background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 5px; } "
            "QLabel { color: #0F172A; font-weight: bold; border: none; } "
            "QComboBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 4px 8px; font-weight: bold; }"
        )
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(10, 6, 10, 6)
        top_lay.setSpacing(12)

        lbl_slb = QLabel("Select Slab:")
        lbl_slb.setStyleSheet("color: #0284C7; font-weight: bold;")
        top_lay.addWidget(lbl_slb)

        self.cb_slab = QComboBox()
        self.cb_slab.setMinimumWidth(260)
        target_idx = 0
        for idx, slb in enumerate(self.slabs):
            sid = str(slb.get("id", f"S{idx + 1}"))
            r_dir = int(slb.get("rib_direction_deg", slb.get("rib_angle_deg", 0)))
            des = design_hollow_block_slab_rib(slb, self.story_data, self.fc_mpa, self.fy_mpa)
            self.cb_slab.addItem(
                f"{sid} — Span L = {des['span_l_m']:.2f} m ({des['lx_m']:.2f}×{des['ly_m']:.2f}m | Ribs {r_dir}°)",
                sid,
            )
            if initial_slab_id and sid == str(initial_slab_id):
                target_idx = idx
        self.cb_slab.currentIndexChanged.connect(self._on_slab_changed)
        top_lay.addWidget(self.cb_slab)

        lbl_db = QLabel("Bottom Rebar Dia db:")
        lbl_db.setStyleSheet("color: #0D9488; font-weight: bold;")
        top_lay.addWidget(lbl_db)

        self.cb_db = QComboBox()
        for d_val in (12, 14, 16):
            self.cb_db.addItem(f"∅{d_val} mm {'(Default)' if d_val == 12 else ''}".strip(), d_val)
        self.cb_db.currentIndexChanged.connect(self._on_db_changed)
        top_lay.addWidget(self.cb_db)

        self.lbl_fixed_rebar_info = QLabel(
            "Stirrups: ∅6 mm Triangular | Top Bar: 1∅10 mm"
        )
        self.lbl_fixed_rebar_info.setStyleSheet("color: #475569; font-weight: bold;")
        top_lay.addWidget(self.lbl_fixed_rebar_info)
        top_lay.addStretch(1)
        vbox.addWidget(top_bar)

        # Main Horizontal Splitter: Left = Excel Sheet Calculation Report | Right = 2D Rib Cross-Section Drawing
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.report_view = QTextBrowser()
        self.report_view.setMinimumWidth(520)
        self.report_view.setStyleSheet(
            "QTextBrowser { background: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; padding: 8px; font-family: 'Segoe UI', Arial, sans-serif; }"
        )
        splitter.addWidget(self.report_view)

        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background: #FFFFFF; border: 1px solid #CBD5E1; }")
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(6, 6, 6, 6)
        right_lay.setSpacing(6)

        self.lbl_section_title = QLabel("2D Cross-Section of One Hordi Rib & Adjacent Hollow Blocks")
        self.lbl_section_title.setStyleSheet("color: #1E3A8A; font-weight: bold; font-size: 13px; border: none;")
        right_lay.addWidget(self.lbl_section_title)

        self.sec_scene = QGraphicsScene(self)
        self.sec_view = QGraphicsView(self.sec_scene)
        self.sec_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.sec_view.setBackgroundBrush(QBrush(QColor("#FFFFFF")))
        self.sec_view.setStyleSheet("border: 1px solid #E2E8F0; background: #FFFFFF;")
        right_lay.addWidget(self.sec_view, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        vbox.addWidget(splitter, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        vbox.addWidget(btns)

        if self.slabs:
            self.cb_slab.setCurrentIndex(target_idx)
            self._on_slab_changed(target_idx)

    def _get_current_slab_obj(self) -> Optional[Dict[str, Any]]:
        idx = self.cb_slab.currentIndex()
        if idx < 0 or idx >= len(self.slabs):
            return None
        return self.slabs[idx]

    def _on_slab_changed(self, _idx: int) -> None:
        slb = self._get_current_slab_obj()
        if slb is None:
            return
        self._updating_controls = True
        cur_db = int(slb.get("rib_bar_dia_mm", 12))
        db_idx = {12: 0, 14: 1, 16: 2}.get(cur_db, 0)
        self.cb_db.setCurrentIndex(db_idx)
        self._updating_controls = False
        self._refresh_design_and_drawing()

    def _on_db_changed(self, _idx: int) -> None:
        if self._updating_controls:
            return
        self._refresh_design_and_drawing()
        if self.studio is not None:
            self.studio.save_and_sync_current_story()

    def _refresh_design_and_drawing(self) -> None:
        slb = self._get_current_slab_obj()
        if slb is None:
            return
        db_val = int(self.cb_db.currentData() or 12)
        des = design_hollow_block_slab_rib(slb, self.story_data, self.fc_mpa, self.fy_mpa, db_mm_override=db_val)
        self._populate_excel_sheet_html(des)
        self._draw_rib_cross_section(des)

    def _populate_excel_sheet_html(self, d: Dict[str, Any]) -> None:
        shear_color = "#15803D" if d["shear_ok"] else "#DC2626"
        html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #0F172A;">
          <h3 style="margin: 0 0 8px 0; color: #1E3A8A; border-bottom: 2px solid #0284C7; padding-bottom: 4px;">
            Design of Rib Slab — {d['slab_id']} ({d['rib_direction_label']} | Center-to-Center L = {d['span_l_m']:.2f} m)
          </h3>

          <table width="100%" cellspacing="0" cellpadding="4" style="border-collapse: collapse; margin-bottom: 10px;">
            <tr style="background: #E2E8F0; font-weight: bold;">
              <td colspan="2" style="border: 1px solid #94A3B8;">1. Rib &amp; Block Geometry</td>
              <td colspan="2" style="border: 1px solid #94A3B8;">2. Material &amp; Load Constants</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Total Slab Thickness (<b>h</b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['h_mm']:.0f} mm ({d['h_mm']/10.0:.1f} cm)</td>
              <td style="border: 1px solid #CBD5E1;">Live Load (<b>LL</b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['ll_kpa']:.2f} kN/m²</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Topping Slab (<b>h<sub>s</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['hs_mm']:.0f} mm</td>
              <td style="border: 1px solid #CBD5E1;">Finishing Weight (<b>W<sub>finishing</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['w_finishing_kpa']:.2f} kN/m²</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Block Width (<b>S</b>) / Height</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['s_mm']:.0f} mm / {d['block_height_mm']:.0f} mm</td>
              <td style="border: 1px solid #CBD5E1;">Concrete <b>f'c</b> / Steel <b>Fy</b></td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['fc_mpa']:.0f} MPa / {d['fy_mpa']:.0f} MPa</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Rib Width (<b>b<sub>w1</sub> = b<sub>w2</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['bw1_mm']:.0f} mm</td>
              <td style="border: 1px solid #CBD5E1;">Concrete Unit Weight (<b>γ<sub>c</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['gamma_c_kn_m3']:.1f} kN/m³</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Effective Flange Pitch (<b>b = S + b<sub>w1</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #FEF9C3; font-weight: bold;">{d['b_mm']:.0f} mm (0.55 m)</td>
              <td style="border: 1px solid #CBD5E1;">1 Hollow Block Weight (<b>W<sub>Block</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['w_block_kn']:.2f} kN ({d['blocks_per_m']} blocks/m)</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Bar Dia (<b>d<sub>b</sub></b>) / Stirrup (<b>d<sub>s</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #DCFCE7; font-weight: bold;">{d['db_mm']} mm / {d['ds_mm']} mm</td>
              <td style="border: 1px solid #CBD5E1;">Cover (<b>d<sub>c</sub></b>) / Effective Depth (<b>d</b>)</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['dc_mm']} mm / d = {d['d_mm']:.0f} mm</td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="4" style="border-collapse: collapse; margin-bottom: 10px;">
            <tr style="background: #E2E8F0; font-weight: bold;">
              <td style="border: 1px solid #94A3B8;">3. Hollow-Block Loads Breakdown</td>
              <td style="border: 1px solid #94A3B8;">Formula</td>
              <td style="border: 1px solid #94A3B8;">Value</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Topping Slab Weight</td>
              <td style="border: 1px solid #CBD5E1;">(h<sub>s</sub> × (S + b<sub>w1</sub>)) × γ<sub>c</sub></td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['topping_wt_rib']:.3f} kN/m'/rib</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Rib Web Weight</td>
              <td style="border: 1px solid #CBD5E1;">((b<sub>w1</sub>+b<sub>w2</sub>)/2) × (h - h<sub>s</sub>) × γ<sub>c</sub></td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['rib_web_wt_rib']:.3f} kN/m'/rib</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Hollow Blocks Weight</td>
              <td style="border: 1px solid #CBD5E1;">{d['blocks_per_m']} blocks/m × {d['w_block_kn']:.2f} kN</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['block_wt_rib']:.3f} kN/m'/rib</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Finishing Weight</td>
              <td style="border: 1px solid #CBD5E1;">W<sub>finishing</sub> × (S + b<sub>w1</sub>)</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['finishing_wt_rib']:.3f} kN/m'/rib</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Total Service Dead Load / Factored DL</td>
              <td style="border: 1px solid #CBD5E1;">DL = {d['total_dl_rib']:.3f} &rarr; 1.4 × DL</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['factored_dl_rib']:.3f} kN/m'/rib</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Service Live Load / Factored LL</td>
              <td style="border: 1px solid #CBD5E1;">LL = {d['ll_rib']:.3f} &rarr; 1.7 × LL</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['factored_ll_rib']:.3f} kN/m'/rib</td>
            </tr>
            <tr style="background: #FEF3C7; font-weight: bold;">
              <td style="border: 1px solid #D97706;">Design Load per Rib (W<sub>u,rib</sub> — Used for Rib Design)</td>
              <td style="border: 1px solid #D97706;">1.4 DL + 1.7 LL</td>
              <td style="border: 1px solid #D97706; color: #B45309; font-size: 13px;">{d['wu_rib_kn_m']:.2f} kN/m'/rib</td>
            </tr>
            <tr style="background: #E0F2FE; font-weight: bold;">
              <td style="border: 1px solid #0284C7;">Slab Load per m² (W<sub>u</sub>(m×m) — Transferred to Beams)</td>
              <td style="border: 1px solid #0284C7;">W<sub>u,rib</sub> / ({d['b_mm']/1000.0:.2f} m)</td>
              <td style="border: 1px solid #0284C7; color: #0369A1; font-size: 13px;">{d['wu_m2_kpa']:.2f} kN/m²</td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="4" style="border-collapse: collapse; margin-bottom: 10px;">
            <tr style="background: #E2E8F0; font-weight: bold;">
              <td colspan="3" style="border: 1px solid #94A3B8;">4. Design of Flexure (Simply Supported Center-to-Center Span L = {d['span_l_m']:.2f} m)</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Ultimate Moment (<b>M<sub>u</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1;">W<sub>u,rib</sub> × L² / 8 = {d['wu_rib_kn_m']:.2f} × {d['span_l_m']:.2f}² / 8</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">{d['mu_knm']:.2f} kN.m / rib</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;"><b>K<sub>u</sub></b> / <b>&omega;</b> / <b>&rho;</b></td>
              <td style="border: 1px solid #CBD5E1;">M<sub>u</sub>×10<sup>6</sup> / (0.9 × b × f'c × d²)</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">K<sub>u</sub>={d['ku']:.4f} | &omega;={d['omega']:.4f} | &rho;={d['rho']:.6f}</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;"><b>A<sub>s,min</sub></b> / <b>A<sub>s,max</sub></b></td>
              <td style="border: 1px solid #CBD5E1;">(1.4/Fy)×b<sub>w</sub>×d | &rho;<sub>max</sub>={d['rho_max']:.5f}</td>
              <td style="border: 1px solid #CBD5E1;">A<sub>s,min</sub> = <b>{d['as_min_mm2']:.1f} mm²</b> | A<sub>s,max</sub> = <b>{d['as_max_mm2']:.1f} mm²</b></td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Required Steel (<b>A<sub>s</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1;">&rho; × b × d = {d['as_calc_mm2']:.2f} mm²</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">A<sub>s,req</sub> = {d['as_req_mm2']:.2f} mm²</td>
            </tr>
            <tr style="background: #DCFCE7; font-weight: bold;">
              <td style="border: 1px solid #16A34A;">Adopted Bottom Reinforcement</td>
              <td style="border: 1px solid #16A34A;">N<sub>bar</sub> = {d['as_req_mm2']:.2f} / {d['area_one_bar_mm2']:.2f} = {d['n_bar_exact']:.2f} &rArr; {d['n_bars_adopted']} bars</td>
              <td style="border: 1px solid #16A34A; color: #15803D; font-size: 13px;">{d['bottom_rebar_callout']} (A<sub>s,prov</sub> = {d['as_provided_mm2']:.1f} mm²)</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Top Fixation Bar &amp; Stirrups</td>
              <td style="border: 1px solid #CBD5E1;">Constructive Hordi Detailing</td>
              <td style="border: 1px solid #CBD5E1; font-weight: bold; color: #1E3A8A;">{d['top_rebar_callout']} + {d['stirrup_callout']}</td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="4" style="border-collapse: collapse;">
            <tr style="background: #E2E8F0; font-weight: bold;">
              <td colspan="3" style="border: 1px solid #94A3B8;">5. Design of Shear (b<sub>w</sub> = {d['bw2_mm']:.0f} mm, d = {d['d_mm']:.0f} mm)</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Concrete Shear Capacity (<b>V<sub>c</sub></b> / <b>&phi;V<sub>c</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1;">1.1 &radic;f'c × b<sub>w</sub> × d / 6</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">V<sub>c</sub> = {d['vc_kn']:.2f} kN | &phi;V<sub>c</sub> = {d['phi_vc_kn']:.2f} kN</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1;">Ultimate Shear at d (<b>V<sub>u</sub></b>)</td>
              <td style="border: 1px solid #CBD5E1;">W<sub>u,rib</sub> × (L/2 - d)</td>
              <td style="border: 1px solid #CBD5E1; background: #FEE2E2; font-weight: bold;">V<sub>u</sub> = {d['vu_kn']:.2f} kN</td>
            </tr>
            <tr>
              <td style="border: 1px solid #CBD5E1; font-weight: bold;">Shear Check Result</td>
              <td colspan="2" style="border: 1px solid #CBD5E1; font-weight: bold; color: {shear_color};">{d['shear_status_note']}</td>
            </tr>
          </table>
        </div>
        """
        self.report_view.setHtml(html)

    def _draw_rib_cross_section(self, d: Dict[str, Any]) -> None:
        """
        Draws an engineered 2D Cross-Section of One Hollow-Block (Hordi) Rib + Left & Right
        Hollow Blocks + Open Triangular Stirrup (∅6) + 1 Top Fixation Bar (1∅10) + Bottom Main Bars.
        Matches the cross-section diagram in Eng. Yousef's Excel sheet.
        """
        self.sec_scene.clear()
        self.lbl_section_title.setText(
            f"2D Rib Cross-Section — {d['slab_id']} | h={d['h_mm']:.0f}mm, hs={d['hs_mm']:.0f}mm, bw={d['bw2_mm']:.0f}mm | "
            f"{d['n_bars_adopted']}∅{d['db_mm']} Bottom + 1∅10 Top + ∅6 Triangular Stirrup"
        )

        # Scale: 1 mm = 0.42 px
        sc = 0.42
        h_mm = float(d["h_mm"])
        hs_mm = float(d["hs_mm"])
        blk_h_mm = max(50.0, h_mm - hs_mm)
        s_mm = float(d["s_mm"])
        bw1_mm = float(d["bw1_mm"])
        bw2_mm = float(d["bw2_mm"])

        total_w_mm = s_mm + bw2_mm + s_mm
        ox = 70.0
        oy = 90.0

        tot_w_px = total_w_px = total_w_mm * sc
        h_px = h_mm * sc
        hs_px = hs_mm * sc
        blk_h_px = blk_h_mm * sc
        s_px = s_mm * sc
        bw1_px = bw1_mm * sc
        bw2_px = bw2_mm * sc

        # 1. Concrete Top Compression Slab + Central Rib Polygon
        conc_pen = QPen(QColor("#334155"), 2.0)
        conc_brush = QBrush(QColor("#F1F5F9"))
        top_rect = QRectF(ox, oy, tot_w_px, hs_px)
        self.sec_scene.addRect(top_rect, conc_pen, conc_brush)

        rib_left_top = ox + s_px + (bw2_px - bw1_px) / 2.0
        rib_right_top = rib_left_top + bw1_px
        rib_left_bot = ox + s_px
        rib_right_bot = ox + s_px + bw2_px
        rib_poly = QPolygonF([
            QPointF(rib_left_top, oy + hs_px),
            QPointF(rib_right_top, oy + hs_px),
            QPointF(rib_right_bot, oy + h_px),
            QPointF(rib_left_bot, oy + h_px),
        ])
        self.sec_scene.addPolygon(rib_poly, conc_pen, conc_brush)

        # Redraw top slab continuous outline cleanly over rib joint
        self.sec_scene.addLine(ox, oy, ox + tot_w_px, oy, conc_pen)
        self.sec_scene.addLine(ox, oy, ox, oy + hs_px, conc_pen)
        self.sec_scene.addLine(ox + tot_w_px, oy, ox + tot_w_px, oy + hs_px, conc_pen)

        # Concrete stipple dots in topping slab
        dot_pen = QPen(QColor("#94A3B8"), 1.5)
        for dx_mm in range(30, int(total_w_mm) - 20, 55):
            for dy_mm in (25, 65):
                if dy_mm < hs_mm - 10:
                    self.sec_scene.addEllipse(ox + dx_mm * sc, oy + dy_mm * sc, 2, 2, dot_pen)

        # 2. Left & Right Hollow Blocks (Reddish-Brown Hollow Masonry Blocks with 2 Internal Voids)
        blk_pen = QPen(QColor("#7C2D12"), 2.0)
        blk_brush = QBrush(QColor("#9A3412"))
        void_brush = QBrush(QColor("#FFFFFF"))

        for blk_x0 in (ox, ox + s_px + bw2_px):
            outer_blk = QRectF(blk_x0, oy + hs_px, s_px, blk_h_px)
            self.sec_scene.addRect(outer_blk, blk_pen, blk_brush)
            wall_t = 12.0
            cell_w = (s_px - 3.0 * wall_t) / 2.0
            cell_h = max(16.0, blk_h_px - 2.0 * wall_t)
            c1 = QRectF(blk_x0 + wall_t, oy + hs_px + wall_t, cell_w, cell_h)
            c2 = QRectF(blk_x0 + 2.0 * wall_t + cell_w, oy + hs_px + wall_t, cell_w, cell_h)
            self.sec_scene.addRect(c1, blk_pen, void_brush)
            self.sec_scene.addRect(c2, blk_pen, void_brush)

        # 3. Open Triangular Stirrup (∅6) inside Central Rib
        cover_px = float(d["dc_mm"]) * sc
        rib_cx = ox + s_px + bw2_px / 2.0
        bot_y = oy + h_px - cover_px
        top_apex_y = oy + cover_px + 4.0
        left_bot_x = rib_left_bot + cover_px
        right_bot_x = rib_right_bot - cover_px

        stirrup_pen = QPen(QColor("#1D4ED8"), 2.4, Qt.PenStyle.SolidLine)
        # Triangular stirrup legs: bottom horizontal + left inclined leg + right inclined leg + top saddle
        tri_poly = QPolygonF([
            QPointF(left_bot_x, bot_y),
            QPointF(right_bot_x, bot_y),
            QPointF(rib_cx + 10.0, top_apex_y),
            QPointF(rib_cx - 10.0, top_apex_y),
        ])
        self.sec_scene.addPolygon(tri_poly, stirrup_pen, QBrush(Qt.BrushStyle.NoBrush))

        # 4. Top Fixation Bar (1∅10 mm)
        top_bar_r = 5.5
        self.sec_scene.addEllipse(
            rib_cx - top_bar_r,
            top_apex_y + 2.0,
            top_bar_r * 2.0,
            top_bar_r * 2.0,
            QPen(QColor("#0F172A"), 1.5),
            QBrush(QColor("#0284C7")),
        )

        # 5. Bottom Main Reinforcement Bars (n_bars_adopted ∅ db_mm)
        n_bars = int(d["n_bars_adopted"])
        bar_r = 6.5 if d["db_mm"] >= 14 else 5.8
        usable_bot_w = max(16.0, (right_bot_x - left_bot_x) - 2.0 * bar_r)
        for i in range(n_bars):
            frac = 0.5 if n_bars == 1 else (i / float(n_bars - 1))
            bx = (left_bot_x + bar_r) + frac * usable_bot_w
            by = bot_y - bar_r - 1.5
            self.sec_scene.addEllipse(
                bx - bar_r,
                by - bar_r,
                bar_r * 2.0,
                bar_r * 2.0,
                QPen(QColor("#0F172A"), 1.5),
                QBrush(QColor("#DC2626")),
            )

        # 6. Engineering Dimension Lines & Callouts (matching Excel Diagram)
        dim_pen = QPen(QColor("#0284C7"), 1.4)
        font_dim = QFont("Arial", 9, QFont.Weight.Bold)

        # Top bw1 dimension
        y_top_dim = oy - 24.0
        self.sec_scene.addLine(rib_left_top, oy - 4, rib_left_top, y_top_dim - 6, dim_pen)
        self.sec_scene.addLine(rib_right_top, oy - 4, rib_right_top, y_top_dim - 6, dim_pen)
        self.sec_scene.addLine(rib_left_top, y_top_dim, rib_right_top, y_top_dim, dim_pen)
        t_bw1 = self.sec_scene.addText(f"bw1 = {bw1_mm:.0f} mm", font_dim)
        t_bw1.setDefaultTextColor(QColor("#0369A1"))
        t_bw1.setPos(rib_cx - 42, y_top_dim - 22)

        # Bottom S and bw2 dimensions
        y_bot_dim = oy + h_px + 26.0
        for x_tick in (ox, ox + s_px, ox + s_px + bw2_px, ox + tot_w_px):
            self.sec_scene.addLine(x_tick, oy + h_px + 4, x_tick, y_bot_dim + 6, dim_pen)
        self.sec_scene.addLine(ox, y_bot_dim, ox + s_px + bw2_px, y_bot_dim, dim_pen)

        t_s = self.sec_scene.addText(f"S = {s_mm:.0f} mm", font_dim)
        t_s.setDefaultTextColor(QColor("#0369A1"))
        t_s.setPos(ox + s_px / 2.0 - 38, y_bot_dim + 4)

        t_bw2 = self.sec_scene.addText(f"bw2 = {bw2_mm:.0f} mm", font_dim)
        t_bw2.setDefaultTextColor(QColor("#0369A1"))
        t_bw2.setPos(rib_cx - 42, y_bot_dim + 4)

        # Right-side hs and h dimensions
        x_r1 = ox + tot_w_px + 24.0
        x_r2 = ox + tot_w_px + 68.0
        self.sec_scene.addLine(ox + tot_w_px + 4, oy, x_r2 + 6, oy, dim_pen)
        self.sec_scene.addLine(ox + tot_w_px + 4, oy + hs_px, x_r1 + 6, oy + hs_px, dim_pen)
        self.sec_scene.addLine(ox + tot_w_px + 4, oy + h_px, x_r2 + 6, oy + h_px, dim_pen)
        self.sec_scene.addLine(x_r1, oy, x_r1, oy + hs_px, dim_pen)
        self.sec_scene.addLine(x_r2, oy, x_r2, oy + h_px, dim_pen)

        t_hs = self.sec_scene.addText(f"hs={hs_mm:.0f}", font_dim)
        t_hs.setDefaultTextColor(QColor("#0369A1"))
        t_hs.setPos(x_r1 + 4, oy + hs_px / 2.0 - 10)

        t_h = self.sec_scene.addText(f"h={h_mm:.0f}mm", font_dim)
        t_h.setDefaultTextColor(QColor("#0F172A"))
        t_h.setPos(x_r2 + 4, oy + h_px / 2.0 - 10)

        # Reinforcement Callout Box below section
        y_box = y_bot_dim + 36.0
        callout_rect = QRectF(ox, y_box, tot_w_px, 82.0)
        self.sec_scene.addRect(callout_rect, QPen(QColor("#94A3B8"), 1.2), QBrush(QColor("#F8FAFC")))

        c_lines = [
            (f"● Bottom Main Steel: {d['n_bars_adopted']}∅{d['db_mm']} per rib (As,prov = {d['as_provided_mm2']:.1f} mm² >= As,req = {d['as_req_mm2']:.1f} mm²)", "#DC2626"),
            (f"● Top Fixation Bar: 1∅{d['top_bar_dia_mm']} mm (Erection Bar)", "#0284C7"),
            (f"● Rib Stirrups: ∅{d['ds_mm']} @ 200 mm Open Triangular Stirrups", "#1D4ED8"),
            (f"● Loads: Wu_rib = {d['wu_rib_kn_m']:.2f} kN/m'/rib  |  Wu(m×m) = {d['wu_m2_kpa']:.2f} kN/m²  |  Mu = {d['mu_knm']:.2f} kN.m", "#0F172A"),
        ]
        for idx_l, (txt_str, col_hex) in enumerate(c_lines):
            item_t = self.sec_scene.addText(txt_str, QFont("Segoe UI", 9, QFont.Weight.Bold))
            item_t.setDefaultTextColor(QColor(col_hex))
            item_t.setPos(ox + 8, y_box + 4 + idx_l * 18)

        bounds = self.sec_scene.itemsBoundingRect().adjusted(-20, -20, 25, 20)
        self.sec_scene.setSceneRect(bounds)
        self.sec_view.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)


class StructuralCadCanvas2D(QGraphicsView):
    """
    Revit + AutoCAD Hybrid 2D Structural BIM Canvas:
    - Unrestricted 20,000 x 20,000 scene rect so Pan (Hand / Middle-Mouse) and Zoom work smoothly
      across the entire drawing area without ever getting stuck on the right side.
    - Zoom Window (drag rectangle to zoom in), Zoom Extents, Zoom In/Out.
    - Window Selection (Left-to-Right solid blue box) & Crossing Selection (Right-to-Left dashed green box).
    - Direct Click + Shift/Ctrl Multi-Selection (`selected_items: List[Tuple[str, str]]`).
    - Clean 2-Click Revit Align (`AL` without padlock clutter), Move (`MV`), Rotate Column (`R`),
      Linear/Aligned Dimensions (`DLI`/`DAL`), and Measure Distance (`DI`).
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self.scene_2d = QGraphicsScene(self)
        # CRITICAL FIX: Set a massive unrestricted scene rect so QGraphicsView scrollbars
        # never clamp panning to the right half of the viewport!
        self.scene_2d.setSceneRect(-10000.0, -10000.0, 20000.0, 20000.0)
        self.setScene(self.scene_2d)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0D1117")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.scale_px = 48.0  # 1m = 48px
        self.active_tool = "SELECT"

        # Snap & Ortho settings (controlled from Bottom-Left Status Bar)
        self.osnap_enabled = True
        self.osnap_modes = {
            "ENDPOINT": True,
            "MIDPOINT": True,
            "CENTER": True,
            "INTERSECTION": True,
            "PERPENDICULAR": True,
        }
        self.ortho_enabled = True
        self.grid_snap_enabled = True

        # Layer visibility flags
        self.layer_show_arch = True
        self.layer_show_cols = True
        self.layer_show_beams = True
        self.layer_show_slabs = True
        self.layer_show_dims = True
        self.layer_show_tags = True

        # Interactive states
        self._is_panning = False
        self._pan_start_pos = QPointF()
        self._key_buffer = ""

        # Multi-selection & Window/Crossing Box state
        self.selected_items: List[Tuple[str, str]] = []
        self._is_box_selecting = False
        self._box_start_world: Optional[Tuple[float, float]] = None
        self._box_current_world: Optional[Tuple[float, float]] = None

        # Zoom Window state
        self._is_zoom_window_dragging = False
        self._zoom_win_start_world: Optional[Tuple[float, float]] = None
        self._zoom_win_current_world: Optional[Tuple[float, float]] = None

        # Drawing / Modify / Dimension tool states
        self._polyline_pts: List[Tuple[float, float]] = []
        self._opening_poly_pts: List[Tuple[float, float]] = []
        self._opening_poly_mode: bool = False  # False = Rectangle (2-click default), True = Polyline [Spacebar toggle]
        self._first_click_pt: Optional[Tuple[float, float]] = None
        self._second_click_pt: Optional[Tuple[float, float]] = None
        self._current_snap_info: Optional[Dict[str, Any]] = None

        # Revit Align (AL) state (No padlock clutter)
        self._align_ref: Optional[Dict[str, Any]] = None

        # Measure Distance (DI) & Dimension creation state
        self._measure_pts: List[Tuple[float, float]] = []
        self._last_measurement: Optional[Dict[str, Any]] = None

        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.centerOn(5.0 * self.scale_px, -4.0 * self.scale_px)

    @property
    def selected_element(self) -> Optional[Dict[str, Any]]:
        if not self.selected_items:
            return None
        kind, eid = self.selected_items[-1]
        return {"kind": kind, "id": eid}

    @selected_element.setter
    def selected_element(self, val: Optional[Dict[str, Any]]) -> None:
        if val is None:
            self.selected_items.clear()
        else:
            self.selected_items = [(str(val["kind"]), str(val["id"]))]

    def update_cursor_for_active_tool(self) -> None:
        if self._is_panning:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self.active_tool == "PAN":
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.active_tool == "SELECT":
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        elif self.active_tool in ("ALIGN_ELEMENT", "MOVE_ELEMENT", "ROTATE_COL", "FLIP_RIB", "PICK_SLAB", "PICK_VOID"):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def wheelEvent(self, event) -> None:
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        factor = 1.18 if event.angleDelta().y() > 0 else 1.0 / 1.18
        self.scale(factor, factor)
        event.accept()

    def zoom_in_step(self) -> None:
        self.scale(1.22, 1.22)

    def zoom_out_step(self) -> None:
        self.scale(1.0 / 1.22, 1.0 / 1.22)

    def zoom_extents(self) -> None:
        story = self.studio.current_story_data
        s = self.scale_px
        xs: List[float] = []
        ys: List[float] = []
        for p in story.get("slab_edge_polygon", []):
            xs.append(float(p[0]))
            ys.append(float(p[1]))
        for c in story.get("columns", []):
            if c.get("active", True):
                xs.append(float(c["x"]))
                ys.append(float(c["y"]))
        for b in story.get("beams", []):
            xs.extend([float(b.get("start_x", 0.0)), float(b.get("end_x", 0.0))])
            ys.extend([float(b.get("start_y", 0.0)), float(b.get("end_y", 0.0))])
        arch_block = story.get("arch_underlay_block")
        if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
            for seg in arch_block.get("segments", [])[:500]:
                xs.extend([float(seg[0]), float(seg[2])])
                ys.extend([float(seg[1]), float(seg[3])])

        self.resetTransform()
        if xs and ys:
            min_x, max_x = min(xs) - 1.8, max(xs) + 1.8
            min_y, max_y = min(ys) - 1.8, max(ys) + 1.8
            target_rect = QRectF(min_x * s, -max_y * s, max(4.0, max_x - min_x) * s, max(4.0, max_y - min_y) * s)
            self.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.centerOn(target_rect.center())
        else:
            default_rect = QRectF(-2.0 * s, -12.0 * s, 16.0 * s, 14.0 * s)
            self.fitInView(default_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.centerOn(default_rect.center())

    def _scene_to_world_m(self, scene_pt: QPointF) -> Tuple[float, float]:
        s = self.scale_px
        return round(scene_pt.x() / s, 3), round(-scene_pt.y() / s, 3)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        text = (event.text() or "").upper()

        if text.isalpha():
            self._key_buffer = (self._key_buffer + text)[-2:]
            if self._key_buffer == "AL":
                self._key_buffer = ""
                self.studio.activate_cad_tool("ALIGN_ELEMENT")
                event.accept()
                return
            if self._key_buffer == "MV":
                self._key_buffer = ""
                self.studio.activate_cad_tool("MOVE_ELEMENT")
                event.accept()
                return
            if self._key_buffer == "DI":
                self._key_buffer = ""
                self.studio.activate_cad_tool("MEASURE_DIST")
                event.accept()
                return

        if key == Qt.Key.Key_Space:
            if self.active_tool == "DRAW_COL":
                idx = self.studio.cb_col_orient.currentIndex()
                self.studio.cb_col_orient.setCurrentIndex(1 if idx == 0 else 0)
                self.render_story(self.studio.current_story_data)
                orient_lbl = self.studio.cb_col_orient.currentText()
                self.studio.update_contextual_prompt(
                    f"Column Placement ({orient_lbl}): Click to place column, or press [Space] to flip orientation."
                )
                event.accept()
                return
            if self.active_tool == "DRAW_OPENING":
                self._opening_poly_mode = not self._opening_poly_mode
                self._first_click_pt = None
                self._opening_poly_pts.clear()
                self.render_story(self.studio.current_story_data)
                mode_lbl = "Polyline (Multi-Point Loop)" if self._opening_poly_mode else "Rectangle (2 Opposite Corners)"
                self.studio.update_contextual_prompt(
                    f"Draw Slab Opening [{mode_lbl}]: Press [Space] to switch mode, click corners to define opening."
                )
                event.accept()
                return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.studio.delete_selected_object()
            event.accept()
            return
        if key == Qt.Key.Key_R:
            self.studio.rotate_selected_or_default_column()
            event.accept()
            return
        if key == Qt.Key.Key_F3:
            self.studio.btn_osnap_master.setChecked(not self.studio.btn_osnap_master.isChecked())
            self.studio._on_bottom_snap_settings_changed()
            event.accept()
            return
        if key == Qt.Key.Key_F8:
            self.studio.btn_ortho_bar.setChecked(not self.studio.btn_ortho_bar.isChecked())
            self.studio._on_bottom_snap_settings_changed()
            event.accept()
            return
        if key == Qt.Key.Key_F9:
            self.studio.btn_grid_snap_bar.setChecked(not self.studio.btn_grid_snap_bar.isChecked())
            self.studio._on_bottom_snap_settings_changed()
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_C):
            if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
                self._finalize_polyline_boundary()
                event.accept()
                return
            if self.active_tool == "DRAW_OPENING" and self._opening_poly_mode and len(self._opening_poly_pts) >= 3:
                self._finalize_polyline_opening()
                event.accept()
                return
            if self.active_tool in ("DIM_LINEAR", "DIM_ALIGNED") and self._first_click_pt is not None and self._second_click_pt is not None:
                p1, p2 = self._first_click_pt, self._second_click_pt
                self._first_click_pt = None
                self._second_click_pt = None
                dk = ("horizontal" if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]) else "vertical") if self.active_tool == "DIM_LINEAR" else "aligned"
                dim_obj = create_linear_dimension(self.studio.current_story_data, p1, p2, offset_m=0.65, dim_kind=dk)
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(f"Added Dimension {dim_obj['id']} = {dim_obj['text']}.")
                event.accept()
                return
        if key == Qt.Key.Key_Escape:
            self._polyline_pts.clear()
            self._opening_poly_pts.clear()
            self._first_click_pt = None
            self._second_click_pt = None
            self._align_ref = None
            self._measure_pts.clear()
            self._is_box_selecting = False
            self._is_zoom_window_dragging = False
            self.active_tool = "SELECT"
            self.update_cursor_for_active_tool()
            self.render_story(self.studio.current_story_data)
            self.studio.update_contextual_prompt("Ready (SELECT). Click element or drag Left->Right (Window) / Right->Left (Crossing).")
            event.accept()
            return
        super().keyPressEvent(event)

    def _finalize_polyline_boundary(self) -> None:
        if len(self._polyline_pts) < 3:
            QMessageBox.warning(
                self,
                "Polyline Boundary Incomplete",
                "At least 3 vertices are required to close the Building Boundary Polyline.",
            )
            return
        story = self.studio.current_story_data
        story["slab_edge_polygon"] = [[round(pt[0], 3), round(pt[1], 3)] for pt in self._polyline_pts]
        if len(story.get("beams", [])) < 3:
            story["slabs"] = []
        n_verts = len(self._polyline_pts)
        self._polyline_pts.clear()
        self.active_tool = "SELECT"
        self.update_cursor_for_active_tool()
        self.studio.save_and_sync_current_story()
        self.studio.refresh_story_ui()
        log_studio_event("BOUNDARY_DRAWN", f"Outer boundary polyline closed ({n_verts} vertices)")
        self.studio.update_contextual_prompt(
            f"Building Boundary Polyline closed ({n_verts} vertices). Now place Columns (Step 2) & Beams (Step 3)."
        )

    def _finalize_polyline_opening(self) -> None:
        if len(self._opening_poly_pts) < 3:
            QMessageBox.warning(
                self,
                "Opening Polyline Incomplete",
                "At least 3 vertices are required to close a Polygonal Slab Opening.",
            )
            return
        pts = list(self._opening_poly_pts)
        self._opening_poly_pts.clear()
        self._commit_new_opening(pts, is_polygon=True)

    def compute_osnap_point(
        self, raw_x: float, raw_y: float, story_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        candidates: List[Tuple[float, float, float, str, str]] = []
        snap_radius = 0.42

        if self.osnap_enabled:
            if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
                p0x, p0y = self._polyline_pts[0]
                d0 = math.hypot(raw_x - p0x, raw_y - p0y)
                if d0 <= snap_radius * 1.2:
                    candidates.append((d0 - 0.10, p0x, p0y, "POLY_CLOSE", f"OSNAP [End]: Close Polyline ({p0x:.2f}, {p0y:.2f})"))
            if self.active_tool == "DRAW_OPENING" and self._opening_poly_mode and len(self._opening_poly_pts) >= 3:
                p0x, p0y = self._opening_poly_pts[0]
                d0 = math.hypot(raw_x - p0x, raw_y - p0y)
                if d0 <= snap_radius * 1.2:
                    candidates.append((d0 - 0.10, p0x, p0y, "OPEN_CLOSE", f"OSNAP [End]: Close Opening Loop ({p0x:.2f}, {p0y:.2f})"))

            if self.layer_show_cols:
                for col in story_data.get("columns", []):
                    if not col.get("active", True):
                        continue
                    cx, cy = float(col["x"]), float(col["y"])
                    b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
                    cid = str(col["id"])
                    if self.osnap_modes.get("CENTER", True):
                        dist_c = math.hypot(raw_x - cx, raw_y - cy)
                        if dist_c <= snap_radius:
                            candidates.append((dist_c - 0.06, cx, cy, "COL_CENTER", f"OSNAP [Center]: {cid} ({cx:.2f}, {cy:.2f})"))
                    if self.osnap_modes.get("ENDPOINT", True):
                        for dx, dy in [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, h / 2), (-b / 2, h / 2)]:
                            kx, ky = round(cx + dx, 3), round(cy + dy, 3)
                            d_k = math.hypot(raw_x - kx, raw_y - ky)
                            if d_k <= snap_radius * 0.85:
                                candidates.append((d_k, kx, ky, "COL_CORNER", f"OSNAP [Endpoint]: {cid} Corner ({kx:.2f}, {ky:.2f})"))

            if self.layer_show_beams:
                for bm in story_data.get("beams", []):
                    bid = str(bm["id"])
                    sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                    ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
                    if self.osnap_modes.get("ENDPOINT", True):
                        for px, py, slbl in [(sx, sy, f"{bid} Start"), (ex, ey, f"{bid} End")]:
                            d_b = math.hypot(raw_x - px, raw_y - py)
                            if d_b <= snap_radius:
                                candidates.append((d_b, px, py, "BEAM_END", f"OSNAP [Endpoint]: {slbl} ({px:.2f}, {py:.2f})"))
                    if self.osnap_modes.get("MIDPOINT", True):
                        mx, my = round((sx + ex) / 2.0, 3), round((sy + ey) / 2.0, 3)
                        d_m = math.hypot(raw_x - mx, raw_y - my)
                        if d_m <= snap_radius:
                            candidates.append((d_m, mx, my, "BEAM_MID", f"OSNAP [Midpoint]: {bid} ({mx:.2f}, {my:.2f})"))
                    if self.active_tool == "DRAW_OPENING":
                        # Inner beam face snapping so opening snaps flush with beam inner edges
                        bw = float(bm.get("width_m", 0.20))
                        hw = bw / 2.0
                        if abs(ex - sx) >= abs(ey - sy):
                            # Horizontal beam: top and bottom faces
                            for fy, flbl in [(sy - hw, "Bottom Face"), (sy + hw, "Top Face")]:
                                for fx in (sx, ex, (sx + ex) / 2.0):
                                    d_f = math.hypot(raw_x - fx, raw_y - fy)
                                    if d_f <= snap_radius * 1.1:
                                        candidates.append((d_f - 0.12, fx, fy, "BEAM_FACE", f"OSNAP [Beam Face]: {bid} {flbl} ({fx:.2f}, {fy:.2f})"))
                        else:
                            # Vertical beam: left and right faces
                            for fx, flbl in [(sx - hw, "Left Face"), (sx + hw, "Right Face")]:
                                for fy in (sy, ey, (sy + ey) / 2.0):
                                    d_f = math.hypot(raw_x - fx, raw_y - fy)
                                    if d_f <= snap_radius * 1.1:
                                        candidates.append((d_f - 0.12, fx, fy, "BEAM_FACE", f"OSNAP [Beam Face]: {bid} {flbl} ({fx:.2f}, {fy:.2f})"))

            poly_pts = story_data.get("slab_edge_polygon", [])
            if len(poly_pts) >= 3:
                if self.osnap_modes.get("ENDPOINT", True):
                    for idx, pt in enumerate(poly_pts):
                        vx, vy = float(pt[0]), float(pt[1])
                        d_v = math.hypot(raw_x - vx, raw_y - vy)
                        if d_v <= snap_radius:
                            candidates.append((d_v, vx, vy, "SLAB_VERTEX", f"OSNAP [Vertex]: V{idx+1} ({vx:.2f}, {vy:.2f})"))
                for idx in range(len(poly_pts)):
                    x1, y1 = float(poly_pts[idx][0]), float(poly_pts[idx][1])
                    x2, y2 = float(poly_pts[(idx + 1) % len(poly_pts)][0]), float(poly_pts[(idx + 1) % len(poly_pts)][1])
                    if self.osnap_modes.get("MIDPOINT", True):
                        mx, my = round((x1 + x2) / 2.0, 3), round((y1 + y2) / 2.0, 3)
                        d_m = math.hypot(raw_x - mx, raw_y - my)
                        if d_m <= snap_radius:
                            candidates.append((d_m, mx, my, "EDGE_MID", f"OSNAP [Midpoint]: Boundary ({mx:.2f}, {my:.2f})"))
                    if self.osnap_modes.get("PERPENDICULAR", True):
                        dx, dy = x2 - x1, y2 - y1
                        seg_len2 = dx * dx + dy * dy
                        if seg_len2 > 1e-6:
                            t = max(0.0, min(1.0, ((raw_x - x1) * dx + (raw_y - y1) * dy) / seg_len2))
                            px, py = round(x1 + t * dx, 2), round(y1 + t * dy, 2)
                            d_seg = math.hypot(raw_x - px, raw_y - py)
                            if d_seg <= 0.28:
                                candidates.append((d_seg + 0.05, px, py, "SLAB_EDGE", f"OSNAP [Edge]: ({px:.2f}, {py:.2f})"))

            arch_block = story_data.get("arch_underlay_block")
            if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
                if self.osnap_modes.get("ENDPOINT", True):
                    for seg in arch_block.get("segments", [])[:800]:
                        for ax, ay in [(seg[0], seg[1]), (seg[2], seg[3])]:
                            d_a = math.hypot(raw_x - ax, raw_y - ay)
                            if d_a <= snap_radius * 0.75:
                                candidates.append((d_a + 0.08, ax, ay, "ARCH_END", f"OSNAP [Arch DXF]: ({ax:.2f}, {ay:.2f})"))

            if candidates:
                candidates.sort(key=lambda item: item[0])
                _, sx, sy, stype, slbl = candidates[0]
                return {"x": round(sx, 3), "y": round(sy, 3), "snap_type": stype, "label": slbl}

        if self.grid_snap_enabled:
            gx, gy = round(raw_x * 10.0) / 10.0, round(raw_y * 10.0) / 10.0
            return {"x": gx, "y": gy, "snap_type": "GRID", "label": f"Grid 0.1m ({gx:.2f}, {gy:.2f})"}

        fx, fy = round(raw_x, 3), round(raw_y, 3)
        return {"x": fx, "y": fy, "snap_type": "FREE", "label": f"Free ({fx:.2f}, {fy:.2f})"}

    def mousePressEvent(self, event) -> None:
        self.setFocus()
        # Pan via Middle Mouse button OR Left Mouse button when PAN tool is active
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self.active_tool == "PAN"
        ):
            self._is_panning = True
            self._pan_start_pos = event.position()
            self.update_cursor_for_active_tool()
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            raw_x, raw_y = self._scene_to_world_m(scene_pt)
            if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
                self._finalize_polyline_boundary()
                event.accept()
                return
            if self.active_tool == "DRAW_OPENING" and self._opening_poly_mode and len(self._opening_poly_pts) >= 3:
                self._finalize_polyline_opening()
                event.accept()
                return
            if self.active_tool != "SELECT":
                self._polyline_pts.clear()
                self._opening_poly_pts.clear()
                self._first_click_pt = None
                self._second_click_pt = None
                self._align_ref = None
                self._measure_pts.clear()
                self._is_box_selecting = False
                self._is_zoom_window_dragging = False
                self.active_tool = "SELECT"
                self.update_cursor_for_active_tool()
                self.render_story(self.studio.current_story_data)
                self.studio.update_contextual_prompt("Ready (SELECT). Right-click any Column, Beam, Slab, or Dimension for Context Actions.")
                event.accept()
                return

            found = self._find_element_near(raw_x, raw_y)
            if found is not None:
                pair = (found["kind"], found["id"])
                if pair not in self.selected_items:
                    self.selected_items = [pair]
                self.render_story(self.studio.current_story_data)
                self._show_element_context_menu(found, raw_x, raw_y, event.globalPosition().toPoint())
            else:
                self.selected_items.clear()
                self.render_story(self.studio.current_story_data)
                self.studio.update_contextual_prompt("Selection cleared. Right-click directly on a Column, Beam, or Slab for options.")
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            raw_x, raw_y = self._scene_to_world_m(scene_pt)

            # ZOOM WINDOW Tool: start dragging zoom box
            if self.active_tool == "ZOOM_WINDOW":
                self._is_zoom_window_dragging = True
                self._zoom_win_start_world = (raw_x, raw_y)
                self._zoom_win_current_world = (raw_x, raw_y)
                self.render_story(self.studio.current_story_data)
                event.accept()
                return

            snap = self.compute_osnap_point(raw_x, raw_y, self.studio.current_story_data)
            sx, sy = snap["x"], snap["y"]

            ref_pt = None
            if self.active_tool == "DRAW_SLAB_EDGE" and self._polyline_pts:
                ref_pt = self._polyline_pts[-1]
            elif self.active_tool == "DRAW_OPENING" and self._opening_poly_mode and self._opening_poly_pts:
                ref_pt = self._opening_poly_pts[-1]
            elif self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT", "DIM_LINEAR") and self._first_click_pt is not None:
                ref_pt = self._first_click_pt

            if self.ortho_enabled and ref_pt is not None and snap["snap_type"] not in ("POLY_CLOSE", "OPEN_CLOSE"):
                fx, fy = ref_pt
                if abs(sx - fx) >= abs(sy - fy):
                    sy = fy
                else:
                    sx = fx

            # In SELECT mode: click element (including Slabs!) ONLY to select it — never auto-flip slab ribs on SELECT click!
            if self.active_tool == "SELECT":
                found = self._find_element_near(raw_x, raw_y)
                mods = event.modifiers()
                is_multi_mod = bool(mods & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier))
                if found:
                    pair = (found["kind"], found["id"])
                    if is_multi_mod:
                        if pair in self.selected_items:
                            self.selected_items.remove(pair)
                        else:
                            self.selected_items.append(pair)
                    else:
                        if pair not in self.selected_items:
                            self.selected_items = [pair]
                    self.render_story(self.studio.current_story_data)
                    sel_str = ", ".join(f"{k}:{i}" for k, i in self.selected_items)
                    self.studio.update_contextual_prompt(
                        f"Selected ({len(self.selected_items)}): [{sel_str}] — Right-click for Context Menu, or press Delete (Del) / Move (MV)."
                    )
                else:
                    if not is_multi_mod:
                        self.selected_items.clear()
                    self._is_box_selecting = True
                    self._box_start_world = (raw_x, raw_y)
                    self._box_current_world = (raw_x, raw_y)
                    self.render_story(self.studio.current_story_data)
                event.accept()
                return

            self._handle_left_click_at(sx, sy, raw_x, raw_y, snap["snap_type"])
            event.accept()
            return

        super().mousePressEvent(event)

    def _show_element_context_menu(self, found: Dict[str, Any], raw_x: float, raw_y: float, global_pt) -> None:
        """
        Display / Inspection-Only Right-Click Context Menu (v1.8.0 Safety Upgrade):
        All destructive or modifying commands (Delete, Move, Align, Convert, Flip Rib) are removed
        from right-click and placed strictly in the top 'Modify' Menu & 'MODIFY' Toolbar.
        """
        kind = str(found["kind"])
        eid = str(found["id"])
        story = self.studio.current_story_data
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; padding: 6px; font-weight: bold; } "
            "QMenu::item { padding: 6px 18px; color: #0F172A; } "
            "QMenu::item:selected { background: #0284C7; color: #FFFFFF; } "
            "QMenu::item:disabled { color: #64748B; }"
        )

        if kind == "beam":
            bm_obj = next((b for b in story.get("beams", []) if str(b["id"]) == eid), None)
            b_kind_str = str((bm_obj or {}).get("beam_kind", (bm_obj or {}).get("kind", "hidden"))).upper()
            b_w = float((bm_obj or {}).get("width_m", 0.40))
            b_h = float((bm_obj or {}).get("depth_m", 0.30))
            hdr = menu.addAction(f"Beam {eid} — {b_kind_str} ({b_w:.2f} × {b_h:.2f} m)")
            hdr.setEnabled(False)
            menu.addSeparator()
            act_inspect = menu.addAction(f"Open {eid} in Beam Analysis (Loads, SFD & BMD)")
            act_rc = menu.addAction(f"Open {eid} in Beam R.C. Design & Elevation")
            act_sched = menu.addAction("Open Beams & Columns Schedules (Tab 4)")
            menu.addSeparator()
            act_zext = menu.addAction("Zoom Extents (Fit Floor Plan)")
            chosen = menu.exec(global_pt)
            if chosen == act_inspect:
                self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=eid)
            elif chosen == act_rc:
                self.studio.run_analyze_all_beams(switch_to_tab=2, select_beam_id=eid)
            elif chosen == act_sched:
                self.studio.run_analyze_all_beams(switch_to_tab=3, select_beam_id=eid)
            elif chosen == act_zext:
                self.zoom_extents()

        elif kind == "column":
            col_obj = next((c for c in story.get("columns", []) if str(c["id"]) == eid), None)
            c_b = float((col_obj or {}).get("b_m", 0.20))
            c_h = float((col_obj or {}).get("h_m", 0.40))
            hdr = menu.addAction(f"Column {eid} ({c_b:.2f} × {c_h:.2f} m)")
            hdr.setEnabled(False)
            menu.addSeparator()
            act_sched = menu.addAction(f"Inspect Column {eid} in Schedules & Report (Tab 4)")
            act_zext = menu.addAction("Zoom Extents (Fit Floor Plan)")
            chosen = menu.exec(global_pt)
            if chosen == act_sched:
                self.studio.run_analyze_all_beams(switch_to_tab=3)
            elif chosen == act_zext:
                self.zoom_extents()

        elif kind == "slab":
            slb_obj = next((s for s in story.get("slabs", []) if str(s.get("id")) == eid), None)
            ang = int(round(float((slb_obj or {}).get("rib_direction_deg", (slb_obj or {}).get("rib_angle_deg", 0)))))
            lx = float((slb_obj or {}).get("lx_m", 0.0))
            ly = float((slb_obj or {}).get("ly_m", 0.0))
            hdr = menu.addAction(f"Slab {eid} ({lx:.2f} × {ly:.2f} m | Ribs {ang}°)")
            hdr.setEnabled(False)
            menu.addSeparator()
            act_rib = menu.addAction(
                f"Inspect {eid} Rib Loads, Flexural/Shear Design & Cross-Section..."
            )
            act_sched = menu.addAction("View Story Schedules & Calculation Report (Tab 4)")
            menu.addSeparator()
            act_zext = menu.addAction("Zoom Extents (Fit Floor Plan)")
            chosen = menu.exec(global_pt)
            if chosen == act_rib:
                self.studio.open_slab_rib_design_dialog(eid)
            elif chosen == act_sched:
                self.studio.run_analyze_all_beams(switch_to_tab=3)
            elif chosen == act_zext:
                self.zoom_extents()

        else:
            hdr = menu.addAction(f"Selected {kind.upper()}: {eid}")
            hdr.setEnabled(False)
            menu.addSeparator()
            act_zext = menu.addAction("Zoom Extents (Fit Floor Plan)")
            chosen = menu.exec(global_pt)
            if chosen == act_zext:
                self.zoom_extents()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.active_tool == "SELECT":
            scene_pt = self.mapToScene(event.position().toPoint())
            raw_x, raw_y = self._scene_to_world_m(scene_pt)
            found = self._find_element_near(raw_x, raw_y)
            if found:
                if found["kind"] == "slab":
                    self.studio.open_slab_rib_design_dialog(str(found["id"]))
                    event.accept()
                    return
                if found["kind"] == "beam":
                    self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=str(found["id"]))
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._is_panning:
            delta = event.position() - self._pan_start_pos
            self._pan_start_pos = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return

        scene_pt = self.mapToScene(event.position().toPoint())
        raw_x, raw_y = self._scene_to_world_m(scene_pt)

        if self._is_zoom_window_dragging and self._zoom_win_start_world is not None:
            self._zoom_win_current_world = (raw_x, raw_y)
            self.studio.statusBar().showMessage(f"Zoom Window: Release mouse to zoom to area ({raw_x:.2f}, {raw_y:.2f})")
            self.render_story(self.studio.current_story_data)
            event.accept()
            return

        if self._is_box_selecting and self._box_start_world is not None:
            self._box_current_world = (raw_x, raw_y)
            is_cross = raw_x < self._box_start_world[0]
            mode_lbl = "CROSSING Selection (Right->Left, Green Dashed: Touching/Inside)" if is_cross else "WINDOW Selection (Left->Right, Blue Solid: 100% Inside)"
            self.studio.statusBar().showMessage(f"{mode_lbl} | Cursor: X={raw_x:.2f}m, Y={raw_y:.2f}m")
            self.render_story(self.studio.current_story_data)
            event.accept()
            return

        snap = self.compute_osnap_point(raw_x, raw_y, self.studio.current_story_data)

        ref_pt = None
        if self.active_tool == "DRAW_SLAB_EDGE" and self._polyline_pts:
            ref_pt = self._polyline_pts[-1]
        elif self.active_tool == "DRAW_OPENING" and self._opening_poly_mode and self._opening_poly_pts:
            ref_pt = self._opening_poly_pts[-1]
        elif self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT", "DIM_LINEAR") and self._first_click_pt is not None:
            ref_pt = self._first_click_pt

        if self.ortho_enabled and ref_pt is not None and snap["snap_type"] not in ("POLY_CLOSE", "OPEN_CLOSE"):
            fx, fy = ref_pt
            if abs(snap["x"] - fx) >= abs(snap["y"] - fy):
                snap["y"] = fy
            else:
                snap["x"] = fx

        self._current_snap_info = snap
        self.studio.lbl_coords_bar.setText(f"X: {snap['x']:.2f}, Y: {snap['y']:.2f} m | {snap['label']}")
        self.render_story(self.studio.current_story_data)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._is_panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._is_panning = False
            self.update_cursor_for_active_tool()
            event.accept()
            return

        if self._is_zoom_window_dragging and event.button() == Qt.MouseButton.LeftButton:
            self._is_zoom_window_dragging = False
            if self._zoom_win_start_world and self._zoom_win_current_world:
                x1, y1 = self._zoom_win_start_world
                x2, y2 = self._zoom_win_current_world
                if abs(x2 - x1) >= 0.30 and abs(y2 - y1) >= 0.30:
                    s = self.scale_px
                    bmin_x, bmax_x = min(x1, x2), max(x1, x2)
                    bmin_y, bmax_y = min(y1, y2), max(y1, y2)
                    zrect = QRectF(bmin_x * s, -bmax_y * s, (bmax_x - bmin_x) * s, (bmax_y - bmin_y) * s)
                    self.fitInView(zrect.adjusted(-15, -15, 15, 15), Qt.AspectRatioMode.KeepAspectRatio)
                    self.centerOn(zrect.center())
            self._zoom_win_start_world = None
            self._zoom_win_current_world = None
            self.active_tool = "SELECT"
            self.update_cursor_for_active_tool()
            self.render_story(self.studio.current_story_data)
            self.studio.update_contextual_prompt("Zoom Window complete. Ready (SELECT).")
            event.accept()
            return

        if self._is_box_selecting and event.button() == Qt.MouseButton.LeftButton:
            self._is_box_selecting = False
            if self._box_start_world and self._box_current_world:
                x1, y1 = self._box_start_world
                x2, y2 = self._box_current_world
                if math.hypot(x2 - x1, y2 - y1) >= 0.15:
                    newly_sel = select_elements_by_box(self.studio.current_story_data, x1, y1, x2, y2)
                    for item in newly_sel:
                        if item not in self.selected_items:
                            self.selected_items.append(item)
                    is_cross = x2 < x1
                    sel_str = ", ".join(f"{k}:{i}" for k, i in self.selected_items)
                    self.studio.update_contextual_prompt(
                        f"{'Crossing' if is_cross else 'Window'} Selected ({len(self.selected_items)}): [{sel_str or 'None'}]"
                    )
            self._box_start_world = None
            self._box_current_world = None
            self.render_story(self.studio.current_story_data)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _find_element_near(self, wx: float, wy: float) -> Optional[Dict[str, Any]]:
        story = self.studio.current_story_data
        if self.layer_show_cols:
            for col in story.get("columns", []):
                if not col.get("active", True):
                    continue
                if math.hypot(wx - float(col["x"]), wy - float(col["y"])) <= 0.38:
                    return {"kind": "column", "id": str(col["id"])}
        if self.layer_show_beams:
            for bm in story.get("beams", []):
                sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
                half_w = float(bm.get("width_m", 0.40)) / 2.0
                dx, dy = ex - sx, ey - sy
                seg_len2 = dx * dx + dy * dy
                if seg_len2 > 1e-6:
                    t = max(0.0, min(1.0, ((wx - sx) * dx + (wy - sy) * dy) / seg_len2))
                    px, py = sx + t * dx, sy + t * dy
                    if math.hypot(wx - px, wy - py) <= max(0.22, half_w + 0.04):
                        return {"kind": "beam", "id": str(bm["id"])}
        if self.layer_show_dims:
            for dim in story.get("dimensions", []):
                g = compute_dimension_geometry(dim)
                dx1, dy1, dx2, dy2 = g["dx1"], g["dy1"], g["dx2"], g["dy2"]
                ddx, ddy = dx2 - dx1, dy2 - dy1
                seg_len2 = ddx * ddx + ddy * ddy
                if seg_len2 > 1e-6:
                    t = max(0.0, min(1.0, ((wx - dx1) * ddx + (wy - dy1) * ddy) / seg_len2))
                    px, py = dx1 + t * ddx, dy1 + t * ddy
                    if math.hypot(wx - px, wy - py) <= 0.42:
                        return {"kind": "dimension", "id": str(dim["id"])}
                if math.hypot(wx - g["mx"], wy - g["my"]) <= 0.55:
                    return {"kind": "dimension", "id": str(dim["id"])}
        if self.layer_show_slabs:
            for op in story.get("openings", []):
                if is_point_in_opening(wx, wy, op, include_edge=True, tol=0.08):
                    return {"kind": "opening", "id": str(op["id"])}
            slab_hits: List[Tuple[int, float, float, str]] = []
            for slb in story.get("slabs", []):
                c_min_x = float(slb.get("clear_min_x", slb.get("min_x", 0.0)))
                c_max_x = float(slb.get("clear_max_x", slb.get("max_x", 0.0)))
                c_min_y = float(slb.get("clear_min_y", slb.get("min_y", 0.0)))
                c_max_y = float(slb.get("clear_max_y", slb.get("max_y", 0.0)))
                b_min_x = float(slb.get("min_x", c_min_x))
                b_max_x = float(slb.get("max_x", c_max_x))
                b_min_y = float(slb.get("min_y", c_min_y))
                b_max_y = float(slb.get("max_y", c_max_y))
                in_clear = (c_min_x - 0.02 <= wx <= c_max_x + 0.02) and (c_min_y - 0.02 <= wy <= c_max_y + 0.02)
                in_bay = (b_min_x - 0.02 <= wx <= b_max_x + 0.02) and (b_min_y - 0.02 <= wy <= b_max_y + 0.02)
                if in_clear or in_bay:
                    area = max(0.05, (c_max_x - c_min_x) * (c_max_y - c_min_y))
                    cx, cy = (c_min_x + c_max_x) / 2.0, (c_min_y + c_max_y) / 2.0
                    dist = math.hypot(wx - cx, wy - cy)
                    slab_hits.append((0 if in_clear else 1, area, dist, str(slb["id"])))
            if slab_hits:
                slab_hits.sort(key=lambda item: (item[0], item[1], item[2]))
                return {"kind": "slab", "id": slab_hits[0][3]}
        poly_pts = story.get("slab_edge_polygon", [])
        for idx in range(len(poly_pts)):
            x1, y1 = float(poly_pts[idx][0]), float(poly_pts[idx][1])
            x2, y2 = float(poly_pts[(idx + 1) % len(poly_pts)][0]), float(poly_pts[(idx + 1) % len(poly_pts)][1])
            dx, dy = x2 - x1, y2 - y1
            seg_len2 = dx * dx + dy * dy
            if seg_len2 > 1e-6:
                t = max(0.0, min(1.0, ((wx - x1) * dx + (wy - y1) * dy) / seg_len2))
                if math.hypot(wx - (x1 + t * dx), wy - (y1 + t * dy)) <= 0.25:
                    return {"kind": "slab_edge", "id": "00-XD-EDGE"}
        return None

    def _detect_reference_edge_at(self, wx: float, wy: float, story: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        best: Optional[Tuple[float, Dict[str, Any]]] = None

        def consider(dist: float, axis: str, coord: float, label: str) -> None:
            nonlocal best
            if dist <= 0.45 and (best is None or dist < best[0]):
                best = (dist, {"axis": axis, "coord": round(coord, 3), "label": label})

        poly = story.get("slab_edge_polygon", [])
        for idx in range(len(poly)):
            x1, y1 = float(poly[idx][0]), float(poly[idx][1])
            x2, y2 = float(poly[(idx + 1) % len(poly)][0]), float(poly[(idx + 1) % len(poly)][1])
            if abs(x2 - x1) >= abs(y2 - y1) and min(x1, x2) - 0.3 <= wx <= max(x1, x2) + 0.3:
                consider(abs(wy - y1), "y", y1, f"Boundary Horizontal Edge Y={y1:.2f}m")
            elif abs(y2 - y1) > abs(x2 - x1) and min(y1, y2) - 0.3 <= wy <= max(y1, y2) + 0.3:
                consider(abs(wx - x1), "x", x1, f"Boundary Vertical Edge X={x1:.2f}m")

        for col in story.get("columns", []):
            if not col.get("active", True):
                continue
            cx, cy = float(col["x"]), float(col["y"])
            hb, hh = float(col.get("b_m", 0.20)) / 2.0, float(col.get("h_m", 0.40)) / 2.0
            if abs(wy - cy) <= hh + 0.35:
                consider(abs(wx - (cx - hb)), "x", cx - hb, f"{col['id']} Left Face X={cx - hb:.2f}m")
                consider(abs(wx - (cx + hb)), "x", cx + hb, f"{col['id']} Right Face X={cx + hb:.2f}m")
            if abs(wx - cx) <= hb + 0.35:
                consider(abs(wy - (cy - hh)), "y", cy - hh, f"{col['id']} Bottom Face Y={cy - hh:.2f}m")
                consider(abs(wy - (cy + hh)), "y", cy + hh, f"{col['id']} Top Face Y={cy + hh:.2f}m")

        for bm in story.get("beams", []):
            sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
            hw = float(bm.get("width_m", 0.30)) / 2.0
            if abs(ex - sx) >= abs(ey - sy) and min(sx, ex) - 0.3 <= wx <= max(sx, ex) + 0.3:
                consider(abs(wy - (sy + hw)), "y", sy + hw, f"{bm['id']} Top Face Y={sy + hw:.2f}m")
                consider(abs(wy - (sy - hw)), "y", sy - hw, f"{bm['id']} Bottom Face Y={sy - hw:.2f}m")
            elif abs(ey - sy) > abs(ex - sx) and min(sy, ey) - 0.3 <= wy <= max(sy, ey) + 0.3:
                consider(abs(wx - (sx - hw)), "x", sx - hw, f"{bm['id']} Left Face X={sx - hw:.2f}m")
                consider(abs(wx - (sx + hw)), "x", sx + hw, f"{bm['id']} Right Face X={sx + hw:.2f}m")

        arch_block = story.get("arch_underlay_block")
        if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
            for seg in arch_block.get("segments", [])[:800]:
                x1, y1, x2, y2 = float(seg[0]), float(seg[1]), float(seg[2]), float(seg[3])
                if abs(x2 - x1) >= abs(y2 - y1) and min(x1, x2) - 0.2 <= wx <= max(x1, x2) + 0.2:
                    consider(abs(wy - y1), "y", y1, f"Arch DXF Horizontal Line Y={y1:.2f}m")
                elif abs(y2 - y1) > abs(x2 - x1) and min(y1, y2) - 0.2 <= wy <= max(y1, y2) + 0.2:
                    consider(abs(wx - x1), "x", x1, f"Arch DXF Vertical Line X={x1:.2f}m")

        return best[1] if best else None

    def _handle_left_click_at(self, sx: float, sy: float, raw_x: float, raw_y: float, snap_type: str) -> None:
        story = self.studio.current_story_data
        tool = self.active_tool

        # TOOL: Interactive Rotate Column 90° by direct click (`ROTATE_COL`)
        if tool == "ROTATE_COL":
            found = self._find_element_near(raw_x, raw_y)
            if not found or found["kind"] != "column":
                self.studio.update_contextual_prompt("Rotate Column 90° [R]: Click directly on any Column (C#) to rotate it 90°.")
                return
            boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            ok, msg = rotate_column_90_deg(story, found["id"], boundary_mode=boundary_mode)
            if ok:
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(msg)
            return

        # TOOL: Persistent Linear / Aligned Dimension (`DIM_LINEAR` or `DIM_ALIGNED`) — AutoCAD 3-Click Placement
        if tool in ("DIM_LINEAR", "DIM_ALIGNED"):
            if self._first_click_pt is None:
                self._first_click_pt = (sx, sy)
                self._second_click_pt = None
                self.studio.update_contextual_prompt(
                    f"Dimension ({tool}) Step 1/3: First point at ({sx:.2f}, {sy:.2f}). Click second point..."
                )
            elif self._second_click_pt is None:
                self._second_click_pt = (sx, sy)
                self.studio.update_contextual_prompt(
                    f"Dimension ({tool}) Step 2/3: Second point at ({sx:.2f}, {sy:.2f}). Move cursor & click to position dimension line (or press Enter for default offset)..."
                )
            else:
                p1 = self._first_click_pt
                p2 = self._second_click_pt
                self._first_click_pt = None
                self._second_click_pt = None
                if tool == "DIM_LINEAR":
                    dk = "horizontal" if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]) else "vertical"
                else:
                    dk = "aligned"
                dim_obj = create_linear_dimension(
                    story, p1, p2, offset_m=0.65, dim_kind=dk, offset_click_pt=(raw_x, raw_y)
                )
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(
                    f"Added Dimension {dim_obj['id']} = {dim_obj['text']} (offset={dim_obj['offset_m']:+.2f}m). Select & press Del to delete or MV to move."
                )
            self.render_story(story)
            return

        # TOOL: Interactive Measure Distance (DI)
        if tool == "MEASURE_DIST":
            self._measure_pts.append((sx, sy))
            if len(self._measure_pts) == 1:
                self.studio.update_contextual_prompt(
                    f"Measure [DI]: First point set at ({sx:.2f}, {sy:.2f}). Click second point to measure distance..."
                )
            else:
                p1, p2 = self._measure_pts[0], self._measure_pts[1]
                m_res = measure_distance_2d(p1, p2)
                self._last_measurement = {"p1": p1, "p2": p2, **m_res}
                self._measure_pts.clear()
                self.studio.update_contextual_prompt(
                    f"Measured Distance L = {m_res['distance_m']:.3f} m | ΔX = {m_res['dx_m']:+.3f} m | "
                    f"ΔY = {m_res['dy_m']:+.3f} m | Angle = {m_res['angle_deg']:.1f}°"
                )
            self.render_story(story)
            return

        # TOOL: Clean 2-Click Revit Align (AL) — No Padlock Clutter
        if tool == "ALIGN_ELEMENT":
            if self._align_ref is None:
                ref = self._detect_reference_edge_at(raw_x, raw_y, story)
                if not ref:
                    self.studio.update_contextual_prompt(
                        "Align [AL] Step 1: Click directly on a fixed Reference Edge (Boundary Edge, Column/Beam Face, or Arch Line)."
                    )
                    return
                self._align_ref = ref
                self.render_story(story)
                self.studio.update_contextual_prompt(
                    f"Align [AL] Step 2: Reference set to [{ref['label']}]. Now click the Column or Beam Face to align flush!"
                )
                return
            else:
                ref = self._align_ref
                found = self._find_element_near(raw_x, raw_y)
                if not found or found["kind"] not in ("column", "beam"):
                    self.studio.update_contextual_prompt(
                        f"Align [AL] Step 2: Click on a Column (C#) or Beam (B#) face to align with {ref['label']}."
                    )
                    return

                axis = ref["axis"]
                rc = ref["coord"]
                pref_mode = self.studio.cb_align_face_mode.currentText()

                if found["kind"] == "column":
                    col = next((c for c in story.get("columns", []) if c["id"] == found["id"]), None)
                    cx, cy = float(col["x"]), float(col["y"])
                    if "Auto" in pref_mode:
                        if axis == "x":
                            face = "left" if raw_x < cx - 0.03 else ("right" if raw_x > cx + 0.03 else ("left" if rc < cx else "right"))
                        else:
                            face = "bottom" if raw_y < cy - 0.03 else ("top" if raw_y > cy + 0.03 else ("bottom" if rc < cy else "top"))
                    elif "Center" in pref_mode:
                        face = "center"
                    else:
                        face = ("left" if rc <= cx else "right") if axis == "x" else ("bottom" if rc <= cy else "top")
                else:
                    bm = next((b for b in story.get("beams", []) if b["id"] == found["id"]), None)
                    bsx, bsy = float(bm["start_x"]), float(bm["start_y"])
                    if "Center" in pref_mode:
                        face = "center"
                    else:
                        face = ("left" if rc <= bsx else "right") if axis == "x" else ("bottom" if rc <= bsy else "top")

                boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
                ok, msg = align_element_face_to_reference(
                    story, found["kind"], found["id"], face, axis, rc, lock_constraint=False, boundary_mode=boundary_mode
                )
                self._align_ref = None
                if ok:
                    self.studio.save_and_sync_current_story()
                    self.studio.refresh_story_ui()
                    self.studio.update_contextual_prompt(msg)
                else:
                    QMessageBox.warning(self, "Align Tool Notice", msg)
                    self.render_story(story)
                return

        # STEP 1: Draw Outer Building Boundary as a Multi-Point Polyline (00-XD-EDGE)
        if tool == "DRAW_SLAB_EDGE":
            if len(self._polyline_pts) >= 3 and (
                snap_type == "POLY_CLOSE"
                or math.hypot(sx - self._polyline_pts[0][0], sy - self._polyline_pts[0][1]) <= 0.35
            ):
                self._finalize_polyline_boundary()
                return
            self._polyline_pts.append((sx, sy))
            n_pts = len(self._polyline_pts)
            self.render_story(story)
            self.studio.update_contextual_prompt(
                f"Polyline Vertex V{n_pts} at ({sx:.2f}, {sy:.2f}). "
                f"{'Click V1 or Press Enter to Close Boundary.' if n_pts >= 3 else 'Click next vertex or type X,Y in Command Bar...'}"
            )
            return

        if tool == "FLIP_RIB" and self.layer_show_slabs:
            toggled, t_msg, _ = toggle_slab_rib_by_label_click(story, raw_x, raw_y, hit_radius_m=0.65)
            if toggled:
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(f"Rib Direction Toggled: {t_msg}")
            elif t_msg:
                QMessageBox.warning(self, "Cantilever Slab Equilibrium Rule", t_msg)
            return

        is_tie_story = self.studio.is_tie_beams_story()
        has_bnd, _, _, _, _ = get_slab_bounding_box(story.get("slab_edge_polygon", []))
        if not has_bnd and not is_tie_story and tool != "SELECT":
            QMessageBox.warning(
                self,
                "Step 1 Required: Draw Building Boundary Polyline First",
                "Please draw the Outer Building Boundary Polyline (00-XD-EDGE) first before placing columns, beams, or slabs.",
            )
            return

        # STEP 2: Place Structural Column
        if tool == "DRAW_COL":
            cols = story.setdefault("columns", [])
            is_vert = self.studio.cb_col_orient.currentIndex() == 0
            b_m = 0.20 if is_vert else 0.40
            h_m = 0.40 if is_vert else 0.20
            boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            active_cols = [c for c in cols if c.get("active", True)]
            next_id = f"C{len(active_cols) + 1}"
            new_col = {
                "id": next_id,
                "x": sx,
                "y": sy,
                "b_m": b_m,
                "h_m": h_m,
                "active": True,
                "moves_with_grids": True,
                "room_bounding": True,
            }
            if has_bnd and not is_tie_story:
                updated_col, updated_poly, msg = enforce_column_inside_slab_boundary(
                    new_col, story["slab_edge_polygon"], mode=boundary_mode
                )
            else:
                updated_col, updated_poly, msg = new_col, story.get("slab_edge_polygon", []), "Placed column on Tie-Beams / open layout."

            # Check conflict with existing Slab Openings -> Alert user for Shift vs Double-Height (2H)
            if not is_tie_story:
                hit_op = next(
                    (
                        op for op in story.get("openings", [])
                        if is_point_in_opening(updated_col["x"], updated_col["y"], op, include_edge=False, tol=0.05)
                    ),
                    None,
                )
                if hit_op is not None:
                    edge_x, edge_y = find_nearest_solid_edge_for_column(story, updated_col, hit_op)
                    if "--check" not in sys.argv:
                        mb = QMessageBox(self)
                        mb.setIcon(QMessageBox.Icon.Question)
                        mb.setWindowTitle(f"Column Inside Slab Opening ({hit_op.get('id', 'OP')})")
                        mb.setText(
                            f"Warning: New Column {next_id} lies inside slab opening void ({hit_op.get('id', 'OP')})!\n\n"
                            f"Do you want to shift the column to the solid opening edge ({edge_x:.2f}, {edge_y:.2f}), or continue and designate it as a Double-Height Column (2H)?"
                        )
                        btn_shift = mb.addButton("Shift Column to Opening Edge", QMessageBox.ButtonRole.ActionRole)
                        btn_2h = mb.addButton("Continue (Double-Height Column 2H)", QMessageBox.ButtonRole.AcceptRole)
                        btn_cancel = mb.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                        mb.setDefaultButton(btn_shift)
                        mb.exec()
                        clicked = mb.clickedButton()
                        if clicked == btn_cancel:
                            self.studio.update_contextual_prompt(f"Cancelled column placement inside opening {hit_op.get('id')}.")
                            return
                        if clicked == btn_shift:
                            updated_col["x"] = edge_x
                            updated_col["y"] = edge_y
                            msg = f"Shifted Column {next_id} to solid opening edge ({edge_x:.2f}, {edge_y:.2f})."
                        else:
                            updated_col["double_height"] = True
                            updated_col["in_slab_opening"] = True
                            updated_col["opening_id"] = str(hit_op.get("id", "OP"))
                            msg = f"Placed Double-Height Column (2H) {next_id} inside opening {hit_op.get('id')}."
                    else:
                        updated_col["double_height"] = True
                        updated_col["in_slab_opening"] = True
                        updated_col["opening_id"] = str(hit_op.get("id", "OP"))

            dup_id = check_duplicate_column(updated_col["x"], updated_col["y"], b_m, h_m, cols)
            if dup_id:
                self.studio.update_contextual_prompt(
                    f"Duplicate Column Prevented: Column {dup_id} already exists at ({updated_col['x']:.2f}, {updated_col['y']:.2f})."
                )
                return
            story["slab_edge_polygon"] = updated_poly
            cols.append(updated_col)
            renumber_story_columns_sequentially(story)
            reconcile_all_story_beams_supports_and_spans(story)
            log_studio_event(
                "COLUMN_PLACED",
                f"Column {updated_col['id']} placed at ({updated_col['x']:.2f}, {updated_col['y']:.2f})",
                {"double_height": bool(updated_col.get("double_height", False))},
            )
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(f"Placed Column {updated_col['id']} ({b_m:.2f}×{h_m:.2f} m): {msg}")
            return

        # STEP 3: Draw Full-Width Hidden (0.40m) or Drop (0.20x0.40m) Beam
        if tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP"):
            if is_tie_story and tool == "DRAW_BEAM_HID":
                QMessageBox.warning(
                    self,
                    "Tie-Beams Story Rule",
                    "Hidden beams are disabled on the Tie-Beams / Grade Beams story (00_TieBeams). Please use '3B. + Drop Beam'.",
                )
                return
            if len(story.get("columns", [])) == 0:
                QMessageBox.warning(
                    self,
                    "Step 2 Required: Place Columns First",
                    "Please place or import Structural Columns (00-XD-COL) before drawing beams.",
                )
                return
            if self._first_click_pt is None:
                self._first_click_pt = (sx, sy)
                self.studio.update_contextual_prompt(
                    f"Beam Start set at ({sx:.2f}, {sy:.2f}). Click End Column Center (beam automatically extends across full column outer faces!)..."
                )
            else:
                start_pt = self._first_click_pt
                end_pt = (sx, sy)
                beams = story.setdefault("beams", [])
                next_bid = f"B{len(beams) + 1}"
                b_kind = "hidden" if (tool == "DRAW_BEAM_HID" and not is_tie_story) else "drop"
                w_m = 0.30 if b_kind == "hidden" else 0.20
                d_m = round(self.studio.sp_adopted_thick.value() / 100.0, 2) if b_kind == "hidden" else 0.40
                ok, bm_obj, msg = validate_and_build_beam_with_cantilevers(
                    next_bid,
                    start_pt,
                    end_pt,
                    b_kind,
                    w_m,
                    d_m,
                    story.get("columns", []),
                    beams,
                    story.get("slab_edge_polygon", []),
                    is_tie_beam_story=is_tie_story,
                    openings=story.get("openings", []),
                )
                self._first_click_pt = None
                if not ok or bm_obj is None:
                    QMessageBox.warning(self, "Beam Geometric / Structural Rule Violation", msg)
                    self.studio.update_contextual_prompt(f"Rejected Beam: {msg}")
                    self.render_story(story)
                    return
                beams.append(bm_obj)
                reconcile_all_story_beams_supports_and_spans(story)
                cascade_alerts: List[str] = []
                if not is_tie_story:
                    _, cascade_alerts = enforce_opening_adjacent_drop_beams_and_cascade(story)
                    _, split_msg = reconcile_and_split_slabs_after_beam_change(story)
                    if split_msg:
                        msg = f"{msg} | {split_msg}"
                if cascade_alerts and "--check" not in sys.argv:
                    QMessageBox.information(
                        self,
                        "Opening Drop Beam / Carrier Cascade Notification",
                        "\n\n".join(cascade_alerts),
                    )
                log_studio_event(
                    "BEAM_DRAWN",
                    f"Beam {bm_obj['id']} ({bm_obj['beam_kind']} {bm_obj['width_m']:.2f}x{bm_obj['depth_m']:.2f}m)",
                    {"alerts": cascade_alerts},
                )
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(msg)
            return

        # STEP 4D: Draw Slab Opening (Rectangle default / Spacebar toggles Polyline) with Opening Priority
        if tool == "DRAW_OPENING":
            if is_tie_story:
                QMessageBox.warning(
                    self,
                    "Tie-Beams Story Rule",
                    "Slab openings are disabled on the Tie-Beams story (00_TieBeams).",
                )
                return
            if self._opening_poly_mode:
                if len(self._opening_poly_pts) >= 3 and (
                    snap_type == "OPEN_CLOSE"
                    or math.hypot(sx - self._opening_poly_pts[0][0], sy - self._opening_poly_pts[0][1]) <= 0.35
                ):
                    self._finalize_polyline_opening()
                    return
                self._opening_poly_pts.append((sx, sy))
                n_pts = len(self._opening_poly_pts)
                self.render_story(story)
                self.studio.update_contextual_prompt(
                    f"Opening Vertex V{n_pts} at ({sx:.2f}, {sy:.2f}). "
                    f"{'Click V1 or Press Enter to Close Opening Loop.' if n_pts >= 3 else 'Click next corner (or press [Space] for Rectangle mode)...'}"
                )
            else:
                if self._first_click_pt is None:
                    self._first_click_pt = (sx, sy)
                    self.render_story(story)
                    self.studio.update_contextual_prompt(
                        f"Draw Opening [Rect]: First corner at ({sx:.2f}, {sy:.2f}). Click opposite corner (or press [Space] for Polyline)..."
                    )
                else:
                    p1 = self._first_click_pt
                    self._first_click_pt = None
                    self._commit_new_opening([p1, (sx, sy)], is_polygon=False)
            return

        # STEP 4: Pick Area (Slab / Opening Toggle)
        if tool in ("PICK_SLAB", "PICK_OPENING"):
            mode_str = "SLAB" if tool == "PICK_SLAB" else "TOGGLE_OPENING"
            ok, msg, _ = pick_area_create_or_update_slab(
                story, raw_x, raw_y, target_mode=mode_str
            )
            if not ok:
                QMessageBox.warning(self, "Pick Area / Cantilever Rule", msg)
            elif tool == "PICK_OPENING":
                _, c_alerts = enforce_opening_adjacent_drop_beams_and_cascade(story)
                if c_alerts and "--check" not in sys.argv:
                    QMessageBox.information(
                        self,
                        "Slab Openings and Beam Hierarchy Notification",
                        "\n\n".join(c_alerts),
                    )
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(msg)
            return

        # MOVE ELEMENT TOOL (Base-Point -> Target-Point Vector Move on Canvas)
        if tool == "MOVE_ELEMENT":
            if not self.selected_items:
                found = self._find_element_near(raw_x, raw_y)
                if not found or found["kind"] not in ("column", "beam", "dimension"):
                    self.studio.update_contextual_prompt(
                        "Move [MV]: First click on a Column, Beam, or Dimension to select it (or select multiple in SELECT mode)."
                    )
                    return
                self.selected_items = [(found["kind"], found["id"])]
                self.render_story(story)
                self.studio.update_contextual_prompt(
                    f"Move [MV]: Selected {found['kind'].upper()} {found['id']}. Now click Base Reference Point (or type ΔX,ΔY below)..."
                )
                return

            if self._first_click_pt is None:
                self._first_click_pt = (sx, sy)
                self.render_story(story)
                self.studio.update_contextual_prompt(
                    f"Move [MV]: Base Reference Point set at ({sx:.2f}, {sy:.2f}). Now click Second Destination Point (or type ΔX,ΔY in Command Bar)..."
                )
            else:
                bx, by = self._first_click_pt
                dx, dy = round(sx - bx, 3), round(sy - by, 3)
                boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
                _, msg = move_selected_elements_by_delta(story, self.selected_items, dx, dy, boundary_mode=boundary_mode)
                self._first_click_pt = None
                self.active_tool = "SELECT"
                self.update_cursor_for_active_tool()
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(msg)
            return

    def _commit_new_opening(self, pts_or_rect: Any, is_polygon: bool = False) -> None:
        story = self.studio.current_story_data
        res_op = create_opening_with_priority_resolution(story, pts_or_rect, is_polygon=is_polygon)
        if not res_op.get("ok"):
            if "--check" not in sys.argv:
                QMessageBox.warning(self, "Invalid Slab Opening", str(res_op.get("error", "Could not create opening.")))
            self.render_story(story)
            return

        alerts = list(res_op.get("alerts", []))
        conflicts = list(res_op.get("conflicting_columns", []))
        shifted_any_col = False
        for c_info in conflicts:
            cid = c_info["column_id"]
            op_id = c_info["opening_id"]
            cx, cy = c_info["current_pos"]
            ex, ey = c_info["suggested_edge"]
            col_obj = next((c for c in story.get("columns", []) if str(c.get("id")) == cid), None)
            if col_obj is None:
                continue
            choose_2h = True
            if "--check" not in sys.argv:
                mb = QMessageBox(self)
                mb.setIcon(QMessageBox.Icon.Question)
                mb.setWindowTitle(f"Column {cid} Conflict with Slab Opening ({op_id})")
                mb.setText(
                    f"Column {cid} at ({cx:.2f}, {cy:.2f}) lies inside slab opening void {op_id}!\n\n"
                    f"Choose the structural action:"
                )
                btn_shift = mb.addButton(f"Shift Column + Beams to Solid Edge ({ex:.2f}, {ey:.2f})", QMessageBox.ButtonRole.ActionRole)
                btn_2h = mb.addButton("Continue (Double-Height Column 2H)", QMessageBox.ButtonRole.AcceptRole)
                mb.setDefaultButton(btn_shift)
                mb.exec()
                choose_2h = (mb.clickedButton() != btn_shift)

            if choose_2h:
                col_obj["double_height"] = True
                col_obj["in_slab_opening"] = True
                col_obj["opening_id"] = op_id
                alerts.append(f"Column {cid} confirmed as Double-Height (2H) inside opening {op_id}.")
            else:
                move_column_and_sync_connected_beams(
                    story, cid, round(ex - cx, 3), round(ey - cy, 3), boundary_mode="clamp"
                )
                shifted_any_col = True
                alerts.append(f"Column {cid} and connected beams shifted to solid opening edge ({ex:.2f}, {ey:.2f}).")

        if shifted_any_col:
            _, extra_alerts = enforce_opening_adjacent_drop_beams_and_cascade(story)
            alerts.extend(extra_alerts)

        reconcile_and_split_slabs_after_beam_change(story)
        if alerts and "--check" not in sys.argv:
            QMessageBox.information(
                self,
                f"Slab Opening Priority Summary ({res_op['opening']['id']})",
                "\n\n".join(alerts),
            )

        self.studio.save_and_sync_current_story()
        self.studio.refresh_story_ui()
        op_id_lbl = res_op["opening"].get("id", "OP")
        self.studio.update_contextual_prompt(
            f"Opening {op_id_lbl} applied cleanly ({len(alerts)} automatic adjustment(s))."
        )

    def render_story(self, story_data: Dict[str, Any]) -> None:
        self.scene_2d.clear()
        s = self.scale_px

        # 0. Draw Wide Coordinate Grid (-30m to +50m) so user can pan anywhere freely
        grid_pen = QPen(QColor("#161F2C"), 1, Qt.PenStyle.DotLine)
        for gx in range(-30, 52):
            self.scene_2d.addLine(gx * s, -35 * s, gx * s, 30 * s, grid_pen)
        for gy in range(-30, 36):
            self.scene_2d.addLine(-30 * s, -gy * s, 52 * s, -gy * s, grid_pen)

        # 0B. Locked Per-Story Architectural .DXF Underlay Block
        arch_block = story_data.get("arch_underlay_block")
        if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
            arch_pen = QPen(QColor("#475569"), 1.1)
            for seg in arch_block.get("segments", []):
                self.scene_2d.addLine(
                    float(seg[0]) * s, -float(seg[1]) * s,
                    float(seg[2]) * s, -float(seg[3]) * s,
                    arch_pen,
                )

        # 1. Outer Building Boundary Polyline (00-XD-EDGE in Cyan — NEVER auto-draws ribs!)
        edge = story_data.get("slab_edge_polygon", [])
        if len(edge) >= 3:
            is_sel_edge = ("slab_edge", "00-XD-EDGE") in self.selected_items
            edge_pen = QPen(QColor("#F8FAFC" if is_sel_edge else "#06B6D4"), 3.0 if is_sel_edge else 2.2)
            poly = QPolygonF([QPointF(float(p[0]) * s, -float(p[1]) * s) for p in edge])
            self.scene_2d.addPolygon(poly, edge_pen, QBrush(QColor(6, 182, 212, 8)))

        # 2. Picked Slabs (00-XD-SLAB clipped to Room-Bounding Clear Inner Bounds) & Openings (00-XD-OPEN)
        # STRICTLY PRESERVING ENG. YOUSEF'S APPROVED VISUAL STYLE
        openings_list = story_data.get("openings", [])
        if self.layer_show_slabs:
            for slb in story_data.get("slabs", []):
                if "min_x" not in slb:
                    continue
                cmin_x = float(slb.get("clear_min_x", slb["min_x"]))
                cmax_x = float(slb.get("clear_max_x", slb["max_x"]))
                cmin_y = float(slb.get("clear_min_y", slb["min_y"]))
                cmax_y = float(slb.get("clear_max_y", slb["max_y"]))
                if cmax_x <= cmin_x or cmax_y <= cmin_y:
                    continue
                scx, scy = (cmin_x + cmax_x) / 2.0, (cmin_y + cmax_y) / 2.0
                if any(is_point_in_opening(scx, scy, op, include_edge=False, tol=0.05) for op in openings_list):
                    continue

                rect = QRectF(cmin_x * s, -cmax_y * s, (cmax_x - cmin_x) * s, (cmax_y - cmin_y) * s)
                is_cant = bool(slb.get("is_cantilever", False))
                is_sel_slab = ("slab", str(slb.get("id"))) in self.selected_items
                fill_col = QColor(245, 158, 11, 42) if is_cant else QColor(56, 189, 248, 22)
                border_pen = QPen(QColor("#F8FAFC" if is_sel_slab else "#38BDF8"), 2 if is_sel_slab else 1, Qt.PenStyle.DotLine)
                self.scene_2d.addRect(rect, border_pen, QBrush(fill_col))

                rib_dir = int(slb.get("rib_direction_deg", 0))
                rib_pen = QPen(QColor(234, 179, 8, 75), 1, Qt.PenStyle.DashLine)
                if rib_dir == 0:
                    y_step = cmin_y + 0.55
                    while y_step < cmax_y - 0.15:
                        self.scene_2d.addLine((cmin_x + 0.05) * s, -y_step * s, (cmax_x - 0.05) * s, -y_step * s, rib_pen)
                        y_step += 0.55
                else:
                    x_step = cmin_x + 0.55
                    while x_step < cmax_x - 0.15:
                        self.scene_2d.addLine(x_step * s, -(cmin_y + 0.05) * s, x_step * s, -(cmax_y - 0.05) * s, rib_pen)
                        x_step += 0.55

                cx = (cmin_x + cmax_x) / 2.0
                cy = (cmin_y + cmax_y) / 2.0
                arrow_pen = QPen(QColor("#FACC15"), 2.2)
                if rib_dir == 0:
                    self.scene_2d.addLine((cx - 0.65) * s, -cy * s, (cx + 0.65) * s, -cy * s, arrow_pen)
                else:
                    self.scene_2d.addLine(cx * s, -(cy - 0.65) * s, cx * s, -(cy + 0.65) * s, arrow_pen)

                if self.layer_show_tags:
                    badge_rect = QRectF(cx * s - 46, -cy * s - 12, 92, 22)
                    self.scene_2d.addRect(badge_rect, QPen(QColor("#FACC15"), 1), QBrush(QColor(15, 23, 42, 220)))
                    slb_tag = f"{slb['id']} ({slb.get('axis_span_m', 0):.1f}m | {rib_dir}°)"
                    stxt = self.scene_2d.addText(slb_tag, QFont("Arial", 8, QFont.Weight.Bold))
                    stxt.setDefaultTextColor(QColor("#FDE047"))
                    stxt.setPos(cx * s - 44, -cy * s - 12)

            for op in openings_list:
                min_x, max_x = float(op.get("min_x", 0.0)), float(op.get("max_x", 0.0))
                min_y, max_y = float(op.get("min_y", 0.0)), float(op.get("max_y", 0.0))
                poly_pts_op = op.get("polygon") or [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
                is_sel_op = ("opening", str(op.get("id"))) in self.selected_items
                open_pen = QPen(QColor("#F8FAFC" if is_sel_op else "#EC4899"), 2.6 if is_sel_op else 2.0)
                qpoly_op = QPolygonF([QPointF(float(pt[0]) * s, -float(pt[1]) * s) for pt in poly_pts_op])
                self.scene_2d.addPolygon(qpoly_op, open_pen, QBrush(QColor(236, 72, 153, 35)))
                self.scene_2d.addLine(min_x * s, -min_y * s, max_x * s, -max_y * s, QPen(QColor("#EC4899"), 1.3, Qt.PenStyle.DashLine))
                self.scene_2d.addLine(min_x * s, -max_y * s, max_x * s, -min_y * s, QPen(QColor("#EC4899"), 1.3, Qt.PenStyle.DashLine))
                if self.layer_show_tags:
                    ocx = (min_x + max_x) / 2.0
                    ocy = (min_y + max_y) / 2.0
                    otag_str = f"{op.get('id', 'OP')} (VOID)"
                    otxt = self.scene_2d.addText(otag_str, QFont("Arial", 8, QFont.Weight.Bold))
                    otxt.setDefaultTextColor(QColor("#F472B6"))
                    otxt.setPos(ocx * s - 28.0, -ocy * s - 10.0)

        # 3. Full-Width Rectangular Beams (Hidden = 0.40m DiagCross, Drop = 0.20m BDiag)
        columns = story_data.get("columns", [])
        placed_tags = []
        for col in columns:
            if col.get("active", True):
                placed_tags.append((float(col["x"]) + 0.22, float(col["y"]) + 0.25))

        if self.layer_show_beams:
            for bm in story_data.get("beams", []):
                sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                ex, ey = float(bm.get("end_x", 5.0)), float(bm.get("end_y", 0.0))
                b_kind = bm.get("beam_kind", "hidden")
                b_width = float(bm.get("width_m", 0.40 if b_kind == "hidden" else 0.20))
                half_w = b_width / 2.0

                dx, dy = ex - sx, ey - sy
                length = max(0.01, math.hypot(dx, dy))
                nx, ny = -dy / length, dx / length

                c1 = QPointF((sx + nx * half_w) * s, -(sy + ny * half_w) * s)
                c2 = QPointF((ex + nx * half_w) * s, -(ey + ny * half_w) * s)
                c3 = QPointF((ex - nx * half_w) * s, -(ey - ny * half_w) * s)
                c4 = QPointF((sx - nx * half_w) * s, -(sy - ny * half_w) * s)
                beam_poly = QPolygonF([c1, c2, c3, c4])

                is_sel_bm = ("beam", str(bm.get("id"))) in self.selected_items
                if b_kind == "hidden":
                    border_col = QColor("#38BDF8" if is_sel_bm else "#EAB308")
                    pen_style = Qt.PenStyle.DashLine
                    hatch_brush = QBrush(QColor(234, 179, 8, 130), Qt.BrushStyle.DiagCrossPattern)
                    bg_brush = QBrush(QColor(234, 179, 8, 26))
                else:
                    border_col = QColor("#38BDF8" if is_sel_bm else "#10B981")
                    pen_style = Qt.PenStyle.SolidLine
                    hatch_brush = QBrush(QColor(16, 185, 129, 145), Qt.BrushStyle.BDiagPattern)
                    bg_brush = QBrush(QColor(16, 185, 129, 30))

                self.scene_2d.addPolygon(beam_poly, QPen(Qt.PenStyle.NoPen), bg_brush)
                self.scene_2d.addPolygon(beam_poly, QPen(border_col, 2.5 if is_sel_bm else 1.5, pen_style), hatch_brush)

                if self.layer_show_tags:
                    tx, ty, _ = compute_smart_beam_tag_position(
                        bm,
                        columns,
                        placed_tags,
                        all_beams=story_data.get("beams", []),
                        slabs=story_data.get("slabs", []),
                    )
                    b_tag_str = str(bm["id"])
                    tag_w = max(24.0, len(b_tag_str) * 8.5 + 8.0)
                    tag_bg = QRectF(tx * s - tag_w / 2.0, -ty * s - 10.0, tag_w, 18.0)
                    self.scene_2d.addRect(
                        tag_bg,
                        QPen(QColor("#FB923C"), 1.0),
                        QBrush(QColor(15, 23, 42, 225)),
                    )
                    txt = self.scene_2d.addText(b_tag_str, QFont("Arial", 8, QFont.Weight.Bold))
                    txt.setDefaultTextColor(QColor("#FB923C"))
                    txt.setPos(tx * s - tag_w / 2.0 + 2.0, -ty * s - 12.0)

        # 4. Columns (0.20 x 0.40 m Strictly Inside Boundary) & Bright Green Column Tags (+ 2H Double-Height Badge)
        if self.layer_show_cols:
            for col in columns:
                if not col.get("active", True):
                    continue
                cx, cy = float(col["x"]), float(col["y"])
                b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
                is_sel_col = ("column", str(col.get("id"))) in self.selected_items
                is_2h = bool(col.get("double_height", False))
                rect = QRectF((cx - b / 2.0) * s, -(cy + h / 2.0) * s, b * s, h * s)
                col_pen = QPen(QColor("#38BDF8" if is_sel_col else ("#F59E0B" if is_2h else "#EF4444")), 2.8 if is_sel_col else 2)
                self.scene_2d.addRect(rect, col_pen, QBrush(QColor(56, 189, 248, 160) if is_sel_col else QColor(239, 68, 68, 125)))
                if is_2h:
                    self.scene_2d.addRect(rect.adjusted(-3, -3, 3, 3), QPen(QColor("#FACC15"), 1.5, Qt.PenStyle.DashLine))

                if self.layer_show_tags:
                    tag_x = cx + b / 2.0 + 0.10
                    tag_y = cy + h / 2.0 + 0.10
                    tag_label = f"{col['id']} (2H)" if is_2h else str(col["id"])
                    ctxt = self.scene_2d.addText(tag_label, QFont("Arial", 9, QFont.Weight.Bold))
                    ctxt.setDefaultTextColor(QColor("#FACC15" if is_2h else "#4ADE80"))
                    ctxt.setPos(tag_x * s, -tag_y * s - 10)

        # 5. Persistent Engineering Dimensions (`00-XD-DIM`) — Positioned Strictly Outside or at User Offset
        if self.layer_show_dims:
            ext_pen = QPen(QColor("#64748B"), 1.0, Qt.PenStyle.DotLine)
            for dim in story_data.get("dimensions", []):
                g = compute_dimension_geometry(dim)
                x1, y1, x2, y2 = g["x1"], g["y1"], g["x2"], g["y2"]
                dx1, dy1, dx2, dy2 = g["dx1"], g["dy1"], g["dx2"], g["dy2"]
                mx, my = g["mx"], g["my"]
                length = g["length"]
                is_sel_dim = ("dimension", str(dim.get("id"))) in self.selected_items
                dim_pen = QPen(QColor("#FACC15" if is_sel_dim else "#38BDF8"), 2.4 if is_sel_dim else 1.5)
                # Extension lines
                self.scene_2d.addLine(x1 * s, -y1 * s, dx1 * s, -dy1 * s, ext_pen)
                self.scene_2d.addLine(x2 * s, -y2 * s, dx2 * s, -dy2 * s, ext_pen)
                # Dimension line + architectural 45-deg ticks
                self.scene_2d.addLine(dx1 * s, -dy1 * s, dx2 * s, -dy2 * s, dim_pen)
                for tx, ty in [(dx1, dy1), (dx2, dy2)]:
                    self.scene_2d.addLine((tx - 0.10) * s, -(ty - 0.10) * s, (tx + 0.10) * s, -(ty + 0.10) * s, QPen(QColor("#FACC15"), 2.0))
                lbl = self.scene_2d.addText(str(dim.get("text", f"{length:.2f} m")), QFont("Arial", 8, QFont.Weight.Bold))
                lbl.setDefaultTextColor(QColor("#FDE047" if is_sel_dim else "#F8FAFC"))
                if g["kind"] == "vertical":
                    lbl.setPos(mx * s - 46, -my * s - 10)
                else:
                    lbl.setPos(mx * s - 22, -my * s - 18)

        # 6. Active Revit Align Reference Line (No padlock clutter)
        if self._align_ref is not None:
            ref_pen = QPen(QColor("#22D3EE"), 2.5, Qt.PenStyle.DashDotLine)
            rc = self._align_ref["coord"]
            if self._align_ref["axis"] == "x":
                self.scene_2d.addLine(rc * s, -30 * s, rc * s, 30 * s, ref_pen)
            else:
                self.scene_2d.addLine(-30 * s, -rc * s, 50 * s, -rc * s, ref_pen)

        # 7. Last Measured Distance Dimension Line (DI)
        if self._last_measurement is not None:
            p1, p2 = self._last_measurement["p1"], self._last_measurement["p2"]
            m_pen = QPen(QColor("#A855F7"), 2.2, Qt.PenStyle.DashLine)
            self.scene_2d.addLine(p1[0] * s, -p1[1] * s, p2[0] * s, -p2[1] * s, m_pen)
            mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
            d_txt = self.scene_2d.addText(
                f"L = {self._last_measurement['distance_m']:.2f} m (ΔX={self._last_measurement['dx_m']:+.2f}, ΔY={self._last_measurement['dy_m']:+.2f})",
                QFont("Arial", 9, QFont.Weight.Bold),
            )
            d_txt.setDefaultTextColor(QColor("#E9D5FF"))
            d_txt.setPos(mx * s - 45, -my * s - 22)

        # 8. Zoom Window Drag Box (Cyan Dashed)
        if self._is_zoom_window_dragging and self._zoom_win_start_world and self._zoom_win_current_world:
            x1, y1 = self._zoom_win_start_world
            x2, y2 = self._zoom_win_current_world
            bmin_x, bmax_x = min(x1, x2), max(x1, x2)
            bmin_y, bmax_y = min(y1, y2), max(y1, y2)
            zrect = QRectF(bmin_x * s, -bmax_y * s, (bmax_x - bmin_x) * s, (bmax_y - bmin_y) * s)
            self.scene_2d.addRect(zrect, QPen(QColor("#22D3EE"), 2.0, Qt.PenStyle.DashLine), QBrush(QColor(34, 211, 238, 35)))

        # 9. AutoCAD Window (Left->Right Solid Blue) vs Crossing (Right->Left Dashed Green) Selection Box
        if self._is_box_selecting and self._box_start_world and self._box_current_world:
            x1, y1 = self._box_start_world
            x2, y2 = self._box_current_world
            is_cross = x2 < x1
            bmin_x, bmax_x = min(x1, x2), max(x1, x2)
            bmin_y, bmax_y = min(y1, y2), max(y1, y2)
            srect = QRectF(bmin_x * s, -bmax_y * s, (bmax_x - bmin_x) * s, (bmax_y - bmin_y) * s)
            if is_cross:
                box_pen = QPen(QColor("#10B981"), 1.8, Qt.PenStyle.DashLine)
                box_brush = QBrush(QColor(16, 185, 129, 38))
            else:
                box_pen = QPen(QColor("#3B82F6"), 1.8, Qt.PenStyle.SolidLine)
                box_brush = QBrush(QColor(59, 130, 246, 38))
            self.scene_2d.addRect(srect, box_pen, box_brush)

        # 10. Active Polyline Boundary & Beam/Move/Dim Rubber-Band Previews
        if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 1:
            poly_pen = QPen(QColor("#06B6D4"), 2.2)
            for idx in range(len(self._polyline_pts) - 1):
                x1, y1 = self._polyline_pts[idx]
                x2, y2 = self._polyline_pts[idx + 1]
                self.scene_2d.addLine(x1 * s, -y1 * s, x2 * s, -y2 * s, poly_pen)
            for vx, vy in self._polyline_pts:
                self.scene_2d.addRect(QRectF(vx * s - 4, -vy * s - 4, 8, 8), QPen(QColor("#22D3EE"), 2))
            if self._current_snap_info is not None:
                lx, ly = self._polyline_pts[-1]
                tx, ty = self._current_snap_info["x"], self._current_snap_info["y"]
                self.scene_2d.addLine(lx * s, -ly * s, tx * s, -ty * s, QPen(QColor("#38BDF8"), 1.5, Qt.PenStyle.DashLine))
                if len(self._polyline_pts) >= 2:
                    p0x, p0y = self._polyline_pts[0]
                    self.scene_2d.addLine(tx * s, -ty * s, p0x * s, -p0y * s, QPen(QColor("#0891B2"), 1.0, Qt.PenStyle.DotLine))

        if self.active_tool == "DRAW_OPENING":
            if self._opening_poly_mode and len(self._opening_poly_pts) >= 1:
                open_pen = QPen(QColor("#EC4899"), 2.2)
                for idx in range(len(self._opening_poly_pts) - 1):
                    x1, y1 = self._opening_poly_pts[idx]
                    x2, y2 = self._opening_poly_pts[idx + 1]
                    self.scene_2d.addLine(x1 * s, -y1 * s, x2 * s, -y2 * s, open_pen)
                for vx, vy in self._opening_poly_pts:
                    self.scene_2d.addRect(QRectF(vx * s - 4, -vy * s - 4, 8, 8), QPen(QColor("#F472B6"), 2))
                if self._current_snap_info is not None:
                    lx, ly = self._opening_poly_pts[-1]
                    tx, ty = self._current_snap_info["x"], self._current_snap_info["y"]
                    self.scene_2d.addLine(lx * s, -ly * s, tx * s, -ty * s, QPen(QColor("#F472B6"), 1.6, Qt.PenStyle.DashLine))
                    if len(self._opening_poly_pts) >= 2:
                        p0x, p0y = self._opening_poly_pts[0]
                        self.scene_2d.addLine(tx * s, -ty * s, p0x * s, -p0y * s, QPen(QColor("#BE185D"), 1.0, Qt.PenStyle.DotLine))
            elif (not self._opening_poly_mode) and self._first_click_pt is not None and self._current_snap_info is not None:
                fx, fy = self._first_click_pt
                tx, ty = self._current_snap_info["x"], self._current_snap_info["y"]
                bmin_x, bmax_x = min(fx, tx), max(fx, tx)
                bmin_y, bmax_y = min(fy, ty), max(fy, ty)
                orect = QRectF(bmin_x * s, -bmax_y * s, max(0.05, bmax_x - bmin_x) * s, max(0.05, bmax_y - bmin_y) * s)
                self.scene_2d.addRect(orect, QPen(QColor("#EC4899"), 2.0, Qt.PenStyle.DashLine), QBrush(QColor(236, 72, 153, 45)))
                olbl = self.scene_2d.addText(
                    f"Opening {(bmax_x - bmin_x):.2f}×{(bmax_y - bmin_y):.2f}m [Space: Poly]",
                    QFont("Consolas", 8, QFont.Weight.Bold),
                )
                olbl.setDefaultTextColor(QColor("#F472B6"))
                olbl.setPos(bmin_x * s, -bmax_y * s - 18)

        if self._first_click_pt is not None and self._current_snap_info is not None and self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT", "DIM_LINEAR", "DIM_ALIGNED"):
            fx, fy = self._first_click_pt
            tx, ty = self._current_snap_info["x"], self._current_snap_info["y"]
            if self.active_tool in ("DIM_LINEAR", "DIM_ALIGNED") and self._second_click_pt is not None:
                p1, p2 = self._first_click_pt, self._second_click_pt
                dk = ("horizontal" if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]) else "vertical") if self.active_tool == "DIM_LINEAR" else "aligned"
                if dk == "horizontal":
                    off_preview = round(ty - (p1[1] + p2[1]) / 2.0, 2)
                elif dk == "vertical":
                    off_preview = round(tx - (p1[0] + p2[0]) / 2.0, 2)
                else:
                    off_preview = 0.65
                g_prev = compute_dimension_geometry({"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1], "offset_m": off_preview, "kind": dk})
                self.scene_2d.addLine(g_prev["dx1"] * s, -g_prev["dy1"] * s, g_prev["dx2"] * s, -g_prev["dy2"] * s, QPen(QColor("#FACC15"), 2.0, Qt.PenStyle.DashLine))
            else:
                self.scene_2d.addLine(fx * s, -fy * s, tx * s, -ty * s, QPen(QColor("#38BDF8"), 1.8, Qt.PenStyle.DashLine))

        # 10B. Live Column Ghost Preview Under Cursor (with Spacebar Orientation Toggle)
        if self.active_tool == "DRAW_COL" and self._current_snap_info is not None:
            gx, gy = self._current_snap_info["x"], self._current_snap_info["y"]
            orient_idx = self.studio.cb_col_orient.currentIndex() if hasattr(self.studio, "cb_col_orient") else 0
            gb_m = 0.20 if orient_idx == 0 else 0.40
            gh_m = 0.40 if orient_idx == 0 else 0.20
            grect = QRectF((gx - gb_m / 2.0) * s, -(gy + gh_m / 2.0) * s, gb_m * s, gh_m * s)
            self.scene_2d.addRect(
                grect,
                QPen(QColor("#38BDF8"), 2.0, Qt.PenStyle.DashLine),
                QBrush(QColor(56, 189, 248, 75)),
            )
            glbl = self.scene_2d.addText(f"{gb_m:.2f}×{gh_m:.2f}m [Space: Flip]", QFont("Consolas", 8, QFont.Weight.Bold))
            glbl.setDefaultTextColor(QColor("#38BDF8"))
            glbl.setPos((gx + gb_m / 2.0 + 0.08) * s, -(gy + gh_m / 2.0 + 0.12) * s)

        # 11. Visual Magnetic OSNAP Indicator
        if self._current_snap_info is not None and self.osnap_enabled:
            ox, oy = self._current_snap_info["x"], self._current_snap_info["y"]
            stype = self._current_snap_info["snap_type"]
            if stype not in ("GRID", "FREE"):
                marker_rect = QRectF(ox * s - 5, -oy * s - 5, 10, 10)
                self.scene_2d.addRect(marker_rect, QPen(QColor("#FACC15"), 2), QBrush(Qt.BrushStyle.NoBrush))


class XpertBeamDiagramCanvas(QGraphicsView):
    """
    Interactive white-sheet engineering canvas matching the classic 'Xpert Beam Analysis' visual style:
    - Full beam schematic with olive-green distributed loads, red point loads, blue support triangles,
      and green upward support reaction arrows (R1, R2, ...).
    - Vertical dashed reference lines from support centerlines through SFD, BMD, and bottom ruler.
    - Hatched steel-blue SFD (kN) and hatched crimson-red BMD (kN.m) with peak values and orange max-+M ticks.
    - Live mouse hover crosshair updating X (m), F (kN), and M (kN.m).
    """

    def __init__(self, parent_widget: "BeamDiagramsViewWidget"):
        super().__init__()
        self.owner = parent_widget
        self.diag_scene = QGraphicsScene(self)
        self.setScene(self.diag_scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QBrush(QColor("#FFFFFF")))
        self.setStyleSheet("border: 1px solid #CBD5E1; background: #FFFFFF;")

        self._xs: List[float] = []
        self._vs: List[float] = []
        self._ms: List[float] = []
        self._x0_px: float = 70.0
        self._w_px: float = 820.0
        self._tot_l: float = 1.0
        self._crosshair_line = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40)
        self._resize_timer.timeout.connect(self.owner._redraw_current_beam_if_ready)

    def set_curve_data(
        self, xs: List[float], vs: List[float], ms: List[float], x0_px: float, w_px: float, tot_l: float
    ) -> None:
        self._xs = xs
        self._vs = vs
        self._ms = ms
        self._x0_px = x0_px
        self._w_px = w_px
        self._tot_l = max(0.2, tot_l)
        self._crosshair_line = None

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        if not self._xs:
            return
        pt = self.mapToScene(event.position().toPoint())
        rel_px = pt.x() - self._x0_px
        if rel_px < -10 or rel_px > self._w_px + 10:
            self.owner.update_live_readout(None, None, None)
            return
        x_m = max(0.0, min(self._tot_l, (rel_px / self._w_px) * self._tot_l))
        # Find nearest sample index
        best_i = min(range(len(self._xs)), key=lambda i: abs(self._xs[i] - x_m))
        xv = self._xs[best_i]
        vv = self._vs[best_i]
        mv = self._ms[best_i]
        self.owner.update_live_readout(xv, vv, mv)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.owner._last_drawn_args is not None and not self.owner._is_drawing:
            self._resize_timer.start()


class BeamDiagramsViewWidget(QWidget):
    """
    Workspace 1: Classic 'Xpert Beam Analysis' Visual Layout (v1.8.0 Full-Viewport White Sheet):
    - Top Control Bar: Clean Light Silver-Slate theme + readable white dropdowns + Story Wall Load Policy.
    - Left Splitter Panel: Compact Project Data Table, Distributed/Point Loads Legend, Live Section Readout (X, F, M).
    - Right White Engineering Sheet: Dynamically scales across 92% of the entire viewport width and height!
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self._updating_table = False
        self._is_drawing = False
        self._span_wall_checkboxes: List[Tuple[str, QCheckBox]] = []
        self._last_drawn_args: Optional[Tuple[str, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(6)

        combo_light_qss = (
            "QComboBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 3px 8px; font-weight: bold; } "
            "QComboBox QAbstractItemView { background: #FFFFFF; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; border: 1px solid #94A3B8; }"
        )

        # Top Bar Row 1: Beam Dropdown + Story Masonry Wall Load Policy (Light Silver-Slate Theme)
        top_bar = QFrame()
        top_bar.setStyleSheet(
            "QFrame { background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 4px; }"
            "QLabel { color: #0F172A; font-weight: bold; border: none; }"
            "QDoubleSpinBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; padding: 2px 4px; font-weight: bold; }"
        )
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(8, 5, 8, 5)
        top_lay.setSpacing(8)

        lbl_sel = QLabel("Select Beam:")
        lbl_sel.setStyleSheet("color: #0284C7; font-weight: bold;")
        top_lay.addWidget(lbl_sel)

        self.cb_beam_select = QComboBox()
        self.cb_beam_select.setMinimumWidth(290)
        self.cb_beam_select.setStyleSheet(combo_light_qss)
        self.cb_beam_select.currentIndexChanged.connect(self._on_beam_selected)
        top_lay.addWidget(self.cb_beam_select)

        top_lay.addWidget(QLabel(" | Story Wall Policy:"))
        self.cb_wall_policy = QComboBox()
        self.cb_wall_policy.addItem("All Beams Carry Wall Load (Typical Story)", "all_beams")
        self.cb_wall_policy.addItem("No Walls Default (Roof / Selective Spans)", "no_walls")
        self.cb_wall_policy.setMinimumWidth(235)
        self.cb_wall_policy.setStyleSheet(combo_light_qss)
        top_lay.addWidget(self.cb_wall_policy)

        top_lay.addWidget(QLabel("Slab Wu (kN/m²):"))
        self.sp_slab_load = QDoubleSpinBox()
        self.sp_slab_load.setRange(2.0, 40.0)
        self.sp_slab_load.setValue(11.71)
        self.sp_slab_load.setSingleStep(0.5)
        self.sp_slab_load.setDecimals(2)
        self.sp_slab_load.setToolTip("Factored Hollow-Block Slab Area Load Wu(m×m) (kN/m²) transferred by one-way ribs to beams")
        top_lay.addWidget(self.sp_slab_load)

        top_lay.addWidget(QLabel("Wall w (kN/m):"))
        self.sp_wall_load = QDoubleSpinBox()
        self.sp_wall_load.setRange(0.0, 60.0)
        self.sp_wall_load.setValue(10.50)
        self.sp_wall_load.setSingleStep(0.5)
        self.sp_wall_load.setDecimals(2)
        self.sp_wall_load.setToolTip("Default Masonry Wall Load (20cm wall: Wwall = 2.5 × H × 1.4)")
        top_lay.addWidget(self.sp_wall_load)

        btn_apply_policy = QPushButton("Apply Loads && Re-Solve")
        btn_apply_policy.setStyleSheet(
            "QPushButton { background: #0284C7; color: white; font-weight: bold; padding: 4px 10px; border-radius: 3px; }"
            "QPushButton:hover { background: #0369A1; }"
        )
        btn_apply_policy.clicked.connect(self._on_apply_story_wall_policy)
        top_lay.addWidget(btn_apply_policy)

        top_lay.addStretch(1)
        vbox.addWidget(top_bar)

        # Top Bar Row 2: Per-Span Wall Load Checkboxes for Selected Beam + Quick Summary (Light Silver-Slate Theme)
        span_bar = QFrame()
        span_bar.setStyleSheet(
            "QFrame { background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; }"
            "QLabel { color: #0F172A; font-weight: bold; border: none; }"
            "QCheckBox { color: #0F172A; font-weight: bold; spacing: 5px; }"
        )
        self.span_bar_lay = QHBoxLayout(span_bar)
        self.span_bar_lay.setContentsMargins(8, 4, 8, 4)
        self.span_bar_lay.setSpacing(12)

        self.lbl_span_wall_title = QLabel("Per-Span Masonry Wall Load on Selected Beam:")
        self.lbl_span_wall_title.setStyleSheet("color: #0369A1; font-weight: bold;")
        self.span_bar_lay.addWidget(self.lbl_span_wall_title)

        self.span_chk_container = QWidget()
        self.span_chk_lay = QHBoxLayout(self.span_chk_container)
        self.span_chk_lay.setContentsMargins(0, 0, 0, 0)
        self.span_chk_lay.setSpacing(10)
        self.span_bar_lay.addWidget(self.span_chk_container)

        self.span_bar_lay.addStretch(1)
        self.lbl_beam_summary = QLabel("Select a beam to inspect loads, reactions, SFD & BMD.")
        self.lbl_beam_summary.setStyleSheet("color: #15803D; font-weight: bold;")
        self.span_bar_lay.addWidget(self.lbl_beam_summary)
        vbox.addWidget(span_bar)

        # Main Splitter: Left Data Panel (320px) + Right Classic White Diagram Sheet
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QFrame()
        left_panel.setMinimumWidth(310)
        left_panel.setMaximumWidth(390)
        left_panel.setStyleSheet(
            "QFrame { background: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; }"
            "QLabel { color: #0F172A; font-weight: bold; border: none; }"
        )
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(6, 6, 6, 6)
        left_lay.setSpacing(6)

        lbl_tbl = QLabel("Project Data Table (Double-Click Value to Edit):")
        lbl_tbl.setStyleSheet("color: #1E3A8A; font-weight: bold; font-size: 11px;")
        left_lay.addWidget(lbl_tbl)

        self.tbl_beam_data = QTableWidget(0, 3)
        self.tbl_beam_data.setHorizontalHeaderLabels(["Type", "Position / Length", "Value"])
        self.tbl_beam_data.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_beam_data.setStyleSheet(
            "QTableWidget { background: #FFFFFF; color: #0F172A; gridline-color: #CBD5E1; font-size: 11px; }"
            "QHeaderView::section { background: #F1F5F9; color: #0F172A; font-weight: bold; border: 1px solid #CBD5E1; padding: 3px; }"
        )
        self.tbl_beam_data.itemChanged.connect(self._on_table_item_edited)
        left_lay.addWidget(self.tbl_beam_data, 1)

        lbl_leg = QLabel("Distributed & Point Loads Legend:")
        lbl_leg.setStyleSheet("color: #1E3A8A; font-weight: bold; font-size: 11px;")
        left_lay.addWidget(lbl_leg)

        self.lbl_legend_box = QLabel("No loads active.")
        self.lbl_legend_box.setWordWrap(True)
        self.lbl_legend_box.setStyleSheet(
            "background: #FFFFFF; color: #1E293B; border: 1px solid #CBD5E1; padding: 6px; font-size: 11px;"
        )
        left_lay.addWidget(self.lbl_legend_box)

        btn_reset_auto = QPushButton("Reset Selected Beam to Auto Loads (Slabs + Walls)")
        btn_reset_auto.setStyleSheet(
            "QPushButton { background: #E2E8F0; color: #0F172A; font-weight: bold; padding: 5px; border: 1px solid #94A3B8; }"
            "QPushButton:hover { background: #CBD5E1; }"
        )
        btn_reset_auto.clicked.connect(self._on_reset_selected_beam_loads)
        left_lay.addWidget(btn_reset_auto)

        lbl_live = QLabel("Live Section Readout (Mouse Position):")
        lbl_live.setStyleSheet("color: #1E3A8A; font-weight: bold; font-size: 11px;")
        left_lay.addWidget(lbl_live)

        readout_row = QHBoxLayout()
        self.lbl_ro_x = QLabel("X: - m")
        self.lbl_ro_f = QLabel("F: - kN")
        self.lbl_ro_m = QLabel("M: - kNm")
        for rlbl in (self.lbl_ro_x, self.lbl_ro_f, self.lbl_ro_m):
            rlbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rlbl.setStyleSheet(
                "background: #F1F5F9; color: #0F172A; font-weight: bold; border: 1px solid #94A3B8; border-radius: 3px; padding: 5px;"
            )
            readout_row.addWidget(rlbl)
        left_lay.addLayout(readout_row)

        splitter.addWidget(left_panel)

        self.diag_view = XpertBeamDiagramCanvas(self)
        splitter.addWidget(self.diag_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        vbox.addWidget(splitter, 1)

    def update_live_readout(self, x_m: Optional[float], v_kn: Optional[float], m_knm: Optional[float]) -> None:
        if x_m is None:
            self.lbl_ro_x.setText("X: - m")
            self.lbl_ro_f.setText("F: - kN")
            self.lbl_ro_m.setText("M: - kNm")
        else:
            self.lbl_ro_x.setText(f"X: {x_m:.2f} m")
            self.lbl_ro_f.setText(f"F: {v_kn:.2f} kN")
            self.lbl_ro_m.setText(f"M: {m_knm:.2f} kNm")

    def _on_apply_story_wall_policy(self) -> None:
        story = self.studio.current_story_data
        policy = str(self.cb_wall_policy.currentData() or "all_beams")
        w_val = float(self.sp_wall_load.value())
        q_val = round(float(self.sp_slab_load.value()), 2)
        set_story_wall_load_policy(story, policy, w_val, apply_to_all_existing_spans=True, slab_load_kpa=q_val)
        current_bid = self.cb_beam_select.currentData()
        self.studio.save_and_sync_current_story()
        self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=current_bid)

    def _on_reset_selected_beam_loads(self) -> None:
        idx = self.cb_beam_select.currentIndex()
        if idx < 0:
            return
        bid = self.cb_beam_select.itemData(idx)
        story = self.studio.current_story_data
        story.pop("custom_slab_wu_override", None)
        story.pop("custom_wall_load_override", None)
        bm = next((b for b in story.get("beams", []) if str(b["id"]) == str(bid)), None)
        if bm is not None:
            bm.pop("loads", None)
            bm.pop("manual_loads_override", None)
            bm.pop("span_wall_thickness_cm", None)
            ensure_beam_wall_flags(story, bm)
            self.studio.save_and_sync_current_story()
            self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=str(bid))

    def populate_results(
        self, story_data: Dict[str, Any], bundle: Dict[str, Any], select_beam_id: Optional[str] = None
    ) -> None:
        # Sync story wall load policy controls
        policy = str(story_data.get("wall_load_policy", "all_beams"))
        p_idx = 0 if policy == "all_beams" else 1
        self.cb_wall_policy.blockSignals(True)
        self.cb_wall_policy.setCurrentIndex(p_idx)
        self.cb_wall_policy.blockSignals(False)

        self.sp_slab_load.blockSignals(True)
        self.sp_slab_load.setValue(float(story_data.get("slab_factored_wu_kpa", 11.71)))
        self.sp_slab_load.blockSignals(False)

        self.sp_wall_load.blockSignals(True)
        self.sp_wall_load.setValue(float(story_data.get("default_wall_load_kn_m", 10.50)))
        self.sp_wall_load.blockSignals(False)

        beams = story_data.get("beams", [])
        self.cb_beam_select.blockSignals(True)
        self.cb_beam_select.clear()
        target_idx = 0
        for i, bm in enumerate(beams):
            bid = str(bm["id"])
            res = bundle.get("beam_results", {}).get(bid, {})
            n_sp = int(res.get("num_spans_excluding_cantilevers", len(bm.get("spans", []))))
            kind_str = str(bm.get("beam_kind", "hidden")).upper()
            b_w = float(bm.get("width_m", 0.40))
            b_h = float(bm.get("depth_m", 0.30))
            self.cb_beam_select.addItem(
                f"{bid} — {kind_str} ({b_w:.2f}×{b_h:.2f}m | {n_sp} Span{'s' if n_sp != 1 else ''})",
                bid,
            )
            if select_beam_id is not None and bid == str(select_beam_id):
                target_idx = i
        self.cb_beam_select.blockSignals(False)

        if beams:
            self.cb_beam_select.setCurrentIndex(target_idx)
            self._on_beam_selected(target_idx)
        else:
            self.diag_view.diag_scene.clear()
            self.tbl_beam_data.setRowCount(0)

    def _rebuild_span_wall_checkboxes(self, story_data: Dict[str, Any], bm: Dict[str, Any]) -> None:
        while self.span_chk_lay.count():
            item = self.span_chk_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._span_wall_checkboxes.clear()

        segs = get_beam_span_segments(bm)
        flags = ensure_beam_wall_flags(story_data, bm)
        thick_map = bm.setdefault("span_wall_thickness_cm", {})
        default_t_cm = int(round(float(story_data.get("default_wall_thickness_cm", 20.0))))
        if default_t_cm not in STANDARD_WALL_THICKNESSES_CM:
            default_t_cm = 20
        bid = str(bm["id"])
        for seg in segs:
            skey = str(seg["key"])
            chk = QCheckBox(f"{seg['label']} ({seg['length_m']:.2f}m)")
            is_on = bool(flags.get(skey, True))
            chk.setChecked(is_on)
            chk.toggled.connect(
                lambda checked, b_id=bid, k=skey: self._on_span_wall_flag_toggled(b_id, k, checked)
            )
            self.span_chk_lay.addWidget(chk)

            cb_tw = QComboBox()
            for std_cm in STANDARD_WALL_THICKNESSES_CM:
                cb_tw.addItem(f"{std_cm} cm wall", float(std_cm))
            cur_cm = int(round(float(thick_map.get(skey, default_t_cm))))
            if cur_cm not in STANDARD_WALL_THICKNESSES_CM:
                cur_cm = min(STANDARD_WALL_THICKNESSES_CM, key=lambda v: abs(v - cur_cm))
            cb_tw.setCurrentIndex(STANDARD_WALL_THICKNESSES_CM.index(cur_cm))
            cb_tw.setEnabled(is_on)
            cb_tw.setToolTip(
                f"Standard wall thickness on {seg['label']} (10, 15, 20, 30, 40 cm): W_wall = (2.5 × H × 1.4) × (t_wall / 20)"
            )
            cb_tw.setStyleSheet(
                "QComboBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; padding: 1px 6px; font-weight: bold; } "
                "QComboBox QAbstractItemView { background: #FFFFFF; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; }"
            )
            cb_tw.currentIndexChanged.connect(
                lambda idx_cb, combo=cb_tw, b_id=bid, k=skey: self._on_span_wall_thickness_changed(
                    b_id, k, float(combo.itemData(idx_cb) or 20.0)
                )
            )
            self.span_chk_lay.addWidget(cb_tw)
            self._span_wall_checkboxes.append((skey, chk))

    def _on_span_wall_flag_toggled(self, beam_id: str, span_key: str, checked: bool) -> None:
        story = self.studio.current_story_data
        ok, msg = set_beam_span_wall_flag(story, beam_id, span_key, checked)
        if ok:
            self.studio.save_and_sync_current_story()
            self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=beam_id)
            self.studio.update_contextual_prompt(msg)

    def _on_span_wall_thickness_changed(self, beam_id: str, span_key: str, wall_t_cm: float) -> None:
        story = self.studio.current_story_data
        ok, msg = set_beam_span_wall_thickness(story, beam_id, span_key, wall_t_cm)
        if ok:
            self.studio.save_and_sync_current_story()
            self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=beam_id)
            self.studio.update_contextual_prompt(msg)

    def _on_table_item_edited(self, item: QTableWidgetItem) -> None:
        if self._updating_table or item.column() != 2:
            return
        idx = self.cb_beam_select.currentIndex()
        if idx < 0:
            return
        bid = str(self.cb_beam_select.itemData(idx))
        story = self.studio.current_story_data
        bm = next((b for b in story.get("beams", []) if str(b["id"]) == bid), None)
        if bm is None:
            return
        meta = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(meta, dict):
            return
        raw_txt = item.text().replace("kN/m", "").replace("kN", "").replace("m", "").strip()
        try:
            val = float(raw_txt)
        except ValueError:
            return
        mtype = meta.get("type")
        if mtype == "dist_load":
            ld_idx = int(meta.get("index", -1))
            loads = bm.get("loads", [])
            if 0 <= ld_idx < len(loads):
                loads[ld_idx]["mag"] = round(max(0.0, val), 2)
                self.studio.save_and_sync_current_story()
                self.studio.run_analyze_all_beams(switch_to_tab=1, select_beam_id=bid)

    def _on_beam_selected(self, idx: int) -> None:
        self.diag_view.diag_scene.clear()
        if idx < 0 or not self.studio.last_analysis_bundle:
            return
        bid = str(self.cb_beam_select.itemData(idx))
        story = self.studio.current_story_data
        bm = next((b for b in story.get("beams", []) if str(b["id"]) == bid), None)
        res = self.studio.last_analysis_bundle.get("beam_results", {}).get(bid)
        if not res or bm is None:
            return

        self._rebuild_span_wall_checkboxes(story, bm)

        reactions = res.get("reactions_kn", [])
        r_str = ", ".join(f"R{i+1}={r:.1f}kN" for i, r in enumerate(reactions))
        self.lbl_beam_summary.setText(
            f"Beam {bid}: {r_str} | Max +Mu = {res['max_pos_mu_knm']:.2f} kN.m | "
            f"Center -Mu = {res.get('max_neg_center_mu_knm', res['max_neg_face_mu_knm']):.2f} kN.m | Max Vu = {res['max_face_vu_kn']:.2f} kN"
        )

        # Populate Left Project Data Table & Legend
        self._updating_table = True
        self.tbl_beam_data.setRowCount(0)
        tot_len = float(res.get("total_len", sum(res.get("spans", [5.0]))))
        segs = get_beam_span_segments(bm)
        loads_applied = res.get("loads_applied", bm.get("loads", []))

        rows_data: List[Tuple[str, str, str, Optional[Dict[str, Any]]]] = [
            ("Total Beam Length", f"{tot_len:.2f} m", "(Cumulative Total)", None)
        ]
        for seg in segs:
            rows_data.append((seg["label"], f"{seg['length_m']:.2f} m", f"[{seg['start_m']:.2f} -> {seg['end_m']:.2f}m]", None))

        legend_lines: List[str] = [
            "<b>Load Calculation Equations (w = w_SW + w_Slab + w_Wall):</b>"
        ]
        dist_idx = 0
        pt_lines: List[str] = []
        for ld_i, ld in enumerate(loads_applied):
            ltype = str(ld.get("type", "D")).upper()
            if ltype == "D":
                dist_idx += 1
                s_m = float(ld.get("start", 0.0))
                e_m = float(ld.get("end", tot_len))
                mag = float(ld.get("mag", 0.0))
                note = str(ld.get("source_note", ""))
                formula_str = str(ld.get("formula_str", f"w = {mag:.2f} kN/m {note}"))
                rows_data.append((
                    f"Distributed Load w{dist_idx}",
                    f"From {s_m:.2f} to {e_m:.2f} m",
                    f"{mag:.2f} kN/m",
                    {"type": "dist_load", "index": ld_i},
                ))
                legend_lines.append(
                    f"<span style='color:#4D5E1E;'>&#9608;</span> <b>w{dist_idx} ({s_m:.1f}–{e_m:.1f}m):</b> {formula_str}"
                )
            elif ltype == "P":
                pos_m = float(ld.get("pos", 0.0))
                mag = float(ld.get("mag", 0.0))
                src_bm = str(ld.get("source_beam", "Sec. Beam"))
                d_sup1 = float(ld.get("dist_from_sup1_m", pos_m))
                rows_data.append((
                    f"Point Load ({src_bm})",
                    f"@ {pos_m:.2f} m (Sup1+{d_sup1:.2f}m)",
                    f"{mag:.2f} kN",
                    None,
                ))
                pt_lines.append(
                    f"<span style='color:#DC2626;'>&#9660;</span> <b>P ({src_bm}) = {mag:.2f} kN</b> @ x = {pos_m:.2f} m"
                )

        for i_r, r_val in enumerate(reactions):
            sup_info = res.get("support_critical_table", [])
            sup_lbl = sup_info[i_r]["target_id"] if i_r < len(sup_info) else f"Sup {i_r+1}"
            sup_kind = str(sup_info[i_r].get("support_kind", "column")) if i_r < len(sup_info) else "column"
            sym_lbl = "Hinge/Col" if sup_kind == "column" else "Roller/Beam"
            sup_xm = sup_info[i_r]["x_m"] if i_r < len(sup_info) else 0.0
            rows_data.append((f"R{i_r+1} [{sup_lbl} - {sym_lbl}]", f"@ {sup_xm:.2f} m", f"{r_val:.2f} kN", None))

        self.tbl_beam_data.setRowCount(len(rows_data))
        for r_i, (c0, c1, c2, meta) in enumerate(rows_data):
            it0 = QTableWidgetItem(c0)
            it0.setFlags(it0.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it1 = QTableWidgetItem(c1)
            it1.setFlags(it1.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it2 = QTableWidgetItem(c2)
            if meta is None:
                it2.setFlags(it2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                it2.setData(Qt.ItemDataRole.UserRole, meta)
            self.tbl_beam_data.setItem(r_i, 0, it0)
            self.tbl_beam_data.setItem(r_i, 1, it1)
            self.tbl_beam_data.setItem(r_i, 2, it2)
        self._updating_table = False

        if pt_lines:
            legend_lines.append("<br><b>Transferred Point Loads (Centerline):</b>")
            legend_lines.extend(pt_lines)
        self.lbl_legend_box.setText("<br>".join(legend_lines))

        # Draw Classic 'Xpert Beam Analysis' White Sheet Diagrams (Dynamically Scaled to Full Viewport)
        self._last_drawn_args = (bid, bm, res, loads_applied)
        self._draw_classic_xpert_beam_sheet(bid, bm, res, loads_applied)

    def _redraw_current_beam_if_ready(self) -> None:
        if self._is_drawing:
            return
        if self._last_drawn_args is not None:
            bid, bm, res, loads_applied = self._last_drawn_args
            self._is_drawing = True
            try:
                self._draw_classic_xpert_beam_sheet(bid, bm, res, loads_applied)
            finally:
                self._is_drawing = False

    def _draw_classic_xpert_beam_sheet(
        self, bid: str, bm: Dict[str, Any], res: Dict[str, Any], loads_applied: List[Dict[str, Any]]
    ) -> None:
        sc = self.diag_view.diag_scene
        sc.clear()
        self.diag_view.resetTransform()

        xs = res.get("x_full", [])
        vs = res.get("v_full", [])
        ms = res.get("m_full", [])
        if not xs:
            return

        # True Viewport Width Utilization (v2.4.0 Gutter Deduction & Horizontal Scrollbar Fix):
        raw_vp_w = float(self.diag_view.viewport().width())
        raw_vp_h = float(self.diag_view.viewport().height())
        vp_w = max(420.0, raw_vp_w - 28.0)
        vp_h = max(380.0, raw_vp_h - 10.0)

        tot_l = max(0.5, float(xs[-1]))
        x0 = 50.0
        right_margin_px = 75.0
        w_px = max(320.0, vp_w - x0 - right_margin_px)
        scale_x = w_px / tot_l
        max_x_allowed = x0 + w_px + right_margin_px - 8.0
        self.diag_view.set_curve_data(xs, vs, ms, x0, w_px, tot_l)

        # Proportional vertical layout across the full viewport height
        amp_px = max(54.0, vp_h * 0.095)
        y_title = 14.0
        y_beam = max(124.0, vp_h * 0.185)
        y_sfd = max(320.0, vp_h * 0.485)
        y_sfd_title = y_sfd - amp_px - 42.0
        y_bmd = max(515.0, vp_h * 0.775)
        y_bmd_title = y_bmd - amp_px - 42.0
        y_ruler = max(615.0, vp_h * 0.915)

        # Title Header: "Analysis of B1" (showing Init -> Designed when section was enlarged by design step)
        kind_lbl = str(bm.get("beam_kind", "hidden")).upper()
        w_cur = float(bm.get("width_m", 0.40))
        d_cur = float(bm.get("depth_m", 0.30))
        w_init = float(bm.get("initial_width_m", w_cur))
        d_init = float(bm.get("initial_depth_m", d_cur))
        n_sp = int(res.get("num_spans_excluding_cantilevers", len(bm.get("spans", []))))
        if abs(w_cur - w_init) > 0.005 or abs(d_cur - d_init) > 0.005:
            sec_title_str = f"{kind_lbl} Init {w_init:.2f}×{d_init:.2f}m → Designed {w_cur:.2f}×{d_cur:.2f}m"
        else:
            sec_title_str = f"{kind_lbl} {w_cur:.2f}×{d_cur:.2f}m"
        title_item = sc.addText(
            f"Analysis of {bid} ({sec_title_str} — {n_sp} Span{'s' if n_sp != 1 else ''})",
            QFont("Arial", 13, QFont.Weight.Bold),
        )
        title_item.setDefaultTextColor(QColor("#0B3C5D"))
        title_item.setPos(x0, y_title)

        # Collect key horizontal station X positions (supports + span max-moment points + beam ends)
        sup_table = res.get("support_critical_table", [])
        ref_x_stations: List[float] = [0.0, tot_l]
        for sup in sup_table:
            ref_x_stations.append(float(sup["x_m"]))
        for sp_row in res.get("span_critical_table", []):
            if float(sp_row.get("m_max_pos_knm", 0.0)) > 0.5:
                ref_x_stations.append(float(sp_row.get("x_at_m_max_m", 0.0)))

        # Draw vertical dotted projection lines across the sheet
        dash_pen = QPen(QColor("#94A3B8"), 1.0, Qt.PenStyle.DotLine)
        for rx in sorted(set(round(v, 2) for v in ref_x_stations)):
            px = x0 + rx * scale_x
            sc.addLine(px, y_beam - 62, px, y_ruler, dash_pen)

        # 1. Draw Distributed Load Blocks (Olive-Green with downward arrows)
        dist_loads = [ld for ld in loads_applied if str(ld.get("type", "D")).upper() == "D" and float(ld.get("mag", 0.0)) > 0.01]
        max_w = max([float(ld.get("mag", 1.0)) for ld in dist_loads] or [1.0])
        for ld in dist_loads:
            s_m = max(0.0, float(ld.get("start", 0.0)))
            e_m = min(tot_l, float(ld.get("end", tot_l)))
            if e_m <= s_m + 1e-3:
                continue
            mag = float(ld.get("mag", 0.0))
            h_load = 22.0 + 16.0 * (mag / max(1.0, max_w))
            lx1 = x0 + s_m * scale_x
            lx2 = x0 + e_m * scale_x
            lrect = QRectF(lx1, y_beam - h_load, lx2 - lx1, h_load - 2.0)
            sc.addRect(lrect, QPen(QColor("#5C6B28"), 1.5), QBrush(QColor(132, 150, 68, 95)))

            # Downward internal load arrows
            n_arrows = max(3, int((lx2 - lx1) / 38.0) + 1)
            arrow_pen = QPen(QColor("#4B5820"), 1.3)
            for ia in range(n_arrows):
                ax = lx1 + (lx2 - lx1) * (ia / max(1, n_arrows - 1))
                sc.addLine(ax, y_beam - h_load + 2, ax, y_beam - 4, arrow_pen)
                sc.addLine(ax - 3.5, y_beam - 10, ax, y_beam - 4, arrow_pen)
                sc.addLine(ax + 3.5, y_beam - 10, ax, y_beam - 4, arrow_pen)

            w_lbl = sc.addText(f"w = {mag:.1f} kN/m", QFont("Arial", 9, QFont.Weight.Bold))
            w_lbl.setDefaultTextColor(QColor("#5C6B28"))
            wx_pos = min(max(8.0, (lx1 + lx2) / 2.0 - 42.0), max_x_allowed - 85.0)
            w_lbl.setPos(wx_pos, y_beam - h_load - 22)

        # 2. Draw Transferred Point Loads (Red downward arrow + P value + distance from left support)
        pt_loads = [ld for ld in loads_applied if str(ld.get("type", "")).upper() == "P" and float(ld.get("mag", 0.0)) > 0.01]
        for pld in pt_loads:
            pos_m = float(pld.get("pos", 0.0))
            mag = float(pld.get("mag", 0.0))
            src_bm = str(pld.get("source_beam", ""))
            d_sup1 = float(pld.get("dist_from_sup1_m", pos_m))
            px = x0 + pos_m * scale_x
            p_pen = QPen(QColor("#DC2626"), 2.6)
            sc.addLine(px, y_beam - 64, px, y_beam - 4, p_pen)
            tri = QPolygonF([QPointF(px, y_beam - 3), QPointF(px - 6, y_beam - 15), QPointF(px + 6, y_beam - 15)])
            sc.addPolygon(tri, QPen(QColor("#DC2626"), 1.5), QBrush(QColor("#DC2626")))
            plbl = sc.addText(
                f"P({src_bm})={mag:.1f}kN\n(@ {d_sup1:.2f}m)",
                QFont("Arial", 8, QFont.Weight.Bold),
            )
            plbl.setDefaultTextColor(QColor("#B91C1C"))
            plbl.setPos(min(max(6.0, px - 38.0), max_x_allowed - 85.0), y_beam - 96)

        # 3. Draw Thick Solid Black Beam Line
        sc.addLine(x0, y_beam, x0 + w_px, y_beam, QPen(QColor("#111827"), 5.0))

        # 4. Draw Span Labels (LC, L1, L2, ..., RC) under beam
        segs = get_beam_span_segments(bm)
        for seg in segs:
            mx_px = x0 + ((seg["start_m"] + seg["end_m"]) / 2.0) * scale_x
            short_code = (
                f"LC = {seg['length_m']:.2f}m"
                if seg["is_cantilever"] and seg["key"] == "cant_left"
                else (
                    f"RC = {seg['length_m']:.2f}m"
                    if seg["is_cantilever"]
                    else f"L{seg['span_index']} = {seg['length_m']:.2f}m"
                )
            )
            slbl = sc.addText(short_code, QFont("Arial", 9, QFont.Weight.Bold))
            slbl.setDefaultTextColor(QColor("#1E293B"))
            slbl.setPos(min(max(6.0, mx_px - 32.0), max_x_allowed - 72.0), y_beam + 6)

        # 5. Draw Supports (Hinge for Column vs Roller for Beam) + Support Name (C1, B2...) + Green Reaction Arrows
        reactions = res.get("reactions_kn", [])
        for idx_s, sup in enumerate(sup_table):
            sx_px = x0 + float(sup["x_m"]) * scale_x
            sup_id = str(sup.get("target_id", f"S{idx_s+1}"))
            sup_kind = str(sup.get("support_kind", "column")).lower()

            tri = QPolygonF([
                QPointF(sx_px, y_beam + 2),
                QPointF(sx_px - 9, y_beam + 16),
                QPointF(sx_px + 9, y_beam + 16),
            ])
            if sup_kind == "beam":
                sc.addPolygon(tri, QPen(QColor("#0F172A"), 1.5), QBrush(QColor("#F59E0B")))
                sc.addEllipse(QRectF(sx_px - 7, y_beam + 16.5, 5.0, 5.0), QPen(QColor("#0F172A"), 1.3), QBrush(QColor("#FFFFFF")))
                sc.addEllipse(QRectF(sx_px + 2, y_beam + 16.5, 5.0, 5.0), QPen(QColor("#0F172A"), 1.3), QBrush(QColor("#FFFFFF")))
                sc.addLine(sx_px - 11, y_beam + 22.5, sx_px + 11, y_beam + 22.5, QPen(QColor("#0F172A"), 1.6))
                sym_tag = f"{sup_id} (Roller)"
            else:
                sc.addPolygon(tri, QPen(QColor("#0F172A"), 1.5), QBrush(QColor("#0284C7")))
                sc.addLine(sx_px - 11, y_beam + 16.5, sx_px + 11, y_beam + 16.5, QPen(QColor("#0F172A"), 1.8))
                for hx_off in range(-9, 10, 4):
                    sc.addLine(sx_px + hx_off, y_beam + 16.5, sx_px + hx_off - 3, y_beam + 21.5, QPen(QColor("#334155"), 1.1))
                sym_tag = f"{sup_id} (Hinge)"

            r_val = reactions[idx_s] if idx_s < len(reactions) else float(sup.get("reaction_kn", 0.0))
            r_pen = QPen(QColor("#15803D"), 2.6)
            sc.addLine(sx_px, y_beam + 46, sx_px, y_beam + 23, r_pen)
            r_head = QPolygonF([
                QPointF(sx_px, y_beam + 22),
                QPointF(sx_px - 5, y_beam + 30),
                QPointF(sx_px + 5, y_beam + 30),
            ])
            sc.addPolygon(r_head, QPen(QColor("#15803D"), 1.2), QBrush(QColor("#15803D")))

            rlbl = sc.addText(f"{sym_tag}\nR{idx_s+1} = {r_val:.2f} kN", QFont("Arial", 8, QFont.Weight.Bold))
            rlbl.setDefaultTextColor(QColor("#15803D"))
            rx_lbl = min(max(6.0, sx_px - 44.0), max_x_allowed - 92.0)
            rlbl.setPos(rx_lbl, y_beam + 46)

        # Helper to interpolate curve value at any x_m for crisp vertical drop lines
        def interp_curve(target_x: float, vals: List[float]) -> float:
            for k in range(len(xs) - 1):
                if xs[k] <= target_x <= xs[k + 1] and (xs[k + 1] - xs[k]) > 1e-5:
                    ratio = (target_x - xs[k]) / (xs[k + 1] - xs[k])
                    return vals[k] + ratio * (vals[k + 1] - vals[k])
            best_k = min(range(len(xs)), key=lambda i: abs(xs[i] - target_x))
            return vals[best_k]

        # ======================================================================
        # 6. Shear Force Diagram - SFD (kN)
        # ======================================================================
        sfd_hdr = sc.addText("Shear Force Diagram - SFD (kN)", QFont("Arial", 10, QFont.Weight.Bold))
        sfd_hdr.setDefaultTextColor(QColor("#0F172A"))
        sfd_hdr.setPos(x0, y_sfd_title)

        sc.addLine(x0, y_sfd, x0 + w_px, y_sfd, QPen(QColor("#0F172A"), 1.6))
        max_v = max([abs(v) for v in vs] or [1.0])
        scale_v = amp_px / max(1.0, max_v)

        v_pts = [QPointF(x0, y_sfd)] + [QPointF(x0 + xs[i] * scale_x, y_sfd - vs[i] * scale_v) for i in range(len(xs))] + [QPointF(x0 + w_px, y_sfd)]
        sc.addPolygon(QPolygonF(v_pts), QPen(QColor("#1D70B8"), 2.3), QBrush(QColor(29, 112, 184, 38)))

        hatch_v_pen = QPen(QColor(29, 112, 184, 95), 1.0)
        n_v_lines = 64
        for k_line in range(1, n_v_lines):
            xm_h = tot_l * (k_line / float(n_v_lines))
            vh = interp_curve(xm_h, vs)
            hx = x0 + xm_h * scale_x
            hy = y_sfd - vh * scale_v
            sc.addLine(hx, y_sfd, hx, hy, hatch_v_pen)

        for sup in sup_table:
            sx_px = x0 + float(sup["x_m"]) * scale_x
            vl = float(sup.get("v_left_kn", 0.0))
            vr = float(sup.get("v_right_kn", 0.0))
            sc.addLine(sx_px, y_sfd - vl * scale_v, sx_px, y_sfd - vr * scale_v, QPen(QColor("#1D70B8"), 2.4))
            if abs(vl) > 0.5:
                v_txt = sc.addText(f"{vl:.1f}", QFont("Arial", 8, QFont.Weight.Bold))
                v_txt.setDefaultTextColor(QColor("#1D70B8"))
                vy_pos = y_sfd - vl * scale_v + (-18 if vl > 0 else 2)
                v_txt.setPos(max(4.0, sx_px - 38.0), vy_pos)
            if abs(vr) > 0.5:
                v_txt2 = sc.addText(f"{vr:.1f}", QFont("Arial", 8, QFont.Weight.Bold))
                v_txt2.setDefaultTextColor(QColor("#1D70B8"))
                vy_pos2 = y_sfd - vr * scale_v + (-18 if vr > 0 else 2)
                v_txt2.setPos(min(sx_px + 4.0, max_x_allowed - 46.0), vy_pos2)

        # ======================================================================
        # 7. Bending Moment Diagram - BMD (kN.m)
        # ======================================================================
        bmd_hdr = sc.addText("Bending Moment Diagram - BMD (kN.m)", QFont("Arial", 10, QFont.Weight.Bold))
        bmd_hdr.setDefaultTextColor(QColor("#0F172A"))
        bmd_hdr.setPos(x0, y_bmd_title)

        sc.addLine(x0, y_bmd, x0 + w_px, y_bmd, QPen(QColor("#0F172A"), 1.6))
        max_m = max([abs(m) for m in ms] or [1.0])
        scale_m = amp_px / max(1.0, max_m)

        m_pts = [QPointF(x0, y_bmd)] + [QPointF(x0 + xs[i] * scale_x, y_bmd + ms[i] * scale_m) for i in range(len(xs))] + [QPointF(x0 + w_px, y_bmd)]
        sc.addPolygon(QPolygonF(m_pts), QPen(QColor("#C81E1E"), 2.3), QBrush(QColor(200, 30, 30, 36)))

        hatch_m_pen = QPen(QColor(200, 30, 30, 95), 1.0)
        for k_line in range(1, n_v_lines):
            xm_h = tot_l * (k_line / float(n_v_lines))
            mh = interp_curve(xm_h, ms)
            hx = x0 + xm_h * scale_x
            hy = y_bmd + mh * scale_m
            sc.addLine(hx, y_bmd, hx, hy, hatch_m_pen)

        for sup in sup_table:
            sx_px = x0 + float(sup["x_m"]) * scale_x
            m_cl = float(sup.get("m_center_knm", 0.0))
            if abs(m_cl) >= 0.05 or float(sup["x_m"]) == 0.0:
                mlbl = sc.addText(f"{m_cl:.2f}", QFont("Arial", 8, QFont.Weight.Bold))
                mlbl.setDefaultTextColor(QColor("#C81E1E"))
                mlbl.setPos(min(max(4.0, sx_px - 18.0), max_x_allowed - 42.0), y_bmd + m_cl * scale_m - 20)

        for sp_row in res.get("span_critical_table", []):
            m_pos = float(sp_row.get("m_max_pos_knm", 0.0))
            x_pos = float(sp_row.get("x_at_m_max_m", 0.0))
            if m_pos > 0.1:
                px = x0 + x_pos * scale_x
                plbl = sc.addText(f"{m_pos:.2f}", QFont("Arial", 8, QFont.Weight.Bold))
                plbl.setDefaultTextColor(QColor("#C81E1E"))
                plbl.setPos(min(max(4.0, px - 18.0), max_x_allowed - 42.0), y_bmd + m_pos * scale_m + 3)

                sc.addLine(px, y_ruler - 8, px, y_ruler + 4, QPen(QColor("#D97706"), 2.0))
                olbl = sc.addText(f"{x_pos:.2f}", QFont("Arial", 8, QFont.Weight.Bold))
                olbl.setDefaultTextColor(QColor("#D97706"))
                olbl.setPos(min(max(4.0, px - 15.0), max_x_allowed - 38.0), y_ruler + 2)

        # ======================================================================
        # 8. Bottom Cumulative Ruler Ticks at Supports & Ends
        # ======================================================================
        ruler_stations = sorted(set([0.0, round(tot_l, 2)] + [round(float(s["x_m"]), 2) for s in sup_table]))
        for rx in ruler_stations:
            px = x0 + rx * scale_x
            sc.addLine(px, y_ruler - 8, px, y_ruler + 5, QPen(QColor("#1E3A8A"), 2.0))
            rlbl = sc.addText(f"{rx:.2f}", QFont("Arial", 8, QFont.Weight.Bold))
            rlbl.setDefaultTextColor(QColor("#1E3A8A"))
            rlbl.setPos(min(max(4.0, px - 14.0), max_x_allowed - 38.0), y_ruler + 14)

        sc.setSceneRect(0, 0, min(vp_w, x0 + w_px + right_margin_px), y_ruler + 44)


class BeamDesignDetailWidget(QWidget):
    """
    Workspace 2: '3. Beam R.C. Design & Longitudinal Section' (ACI 318-19) — v2.2.0:
    - Left Pane: Exact Excel `Sheet4` Flexural Design Calculation Sheet (`5_e8049e44.PNG`) showing
      `h, b, d, dc, db, ds, β1, No. of bars per row, ρ_min, ρ_max, ρ_act, min bars, max bars,
      Mu,Max, Ku, ω, ρ, As, As of one bar, Nbar, As total`, and the per-station rows (`For M = ... use n Φ db`).
    - Right Pane: Crisp White Engineering Sheet (#FFFFFF) with Longitudinal Reinforcement Elevation + Section A-A,
      scaled strictly to the actual visible viewport width so the right end never clips!
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self._is_updating = False
        self._last_sheet4_html: Optional[str] = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40)
        self._resize_timer.timeout.connect(self._on_debounced_resize)
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(6)

        top_bar = QFrame()
        top_bar.setStyleSheet(
            "QFrame { background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 4px; }"
            "QLabel { color: #0F172A; font-weight: bold; border: none; }"
        )
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(8, 6, 8, 6)
        top_lay.setSpacing(10)

        lbl = QLabel("Select Beam:")
        lbl.setStyleSheet("color: #0284C7; font-weight: bold;")
        top_lay.addWidget(lbl)

        self.cb_beam_select = QComboBox()
        self.cb_beam_select.setMinimumWidth(260)
        self.cb_beam_select.setStyleSheet(
            "QComboBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 3px 8px; font-weight: bold; } "
            "QComboBox QAbstractItemView { background: #FFFFFF; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; border: 1px solid #94A3B8; }"
        )
        self.cb_beam_select.currentIndexChanged.connect(self._on_beam_selected)
        top_lay.addWidget(self.cb_beam_select)

        top_lay.addWidget(QLabel("Flexural Method:"))
        self.cb_design_mode = QComboBox()
        self.cb_design_mode.addItem("VBA Iterative Sizing (+100mm) + Double Reinf.", "double")
        self.cb_design_mode.addItem("VBA Iterative Sizing (+100mm) + Single Reinf.", "single")
        self.cb_design_mode.setStyleSheet(
            "QComboBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 3px 8px; font-weight: bold; } "
            "QComboBox QAbstractItemView { background: #FFFFFF; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; border: 1px solid #94A3B8; }"
        )
        self.cb_design_mode.currentIndexChanged.connect(self._on_design_params_changed)
        top_lay.addWidget(self.cb_design_mode)

        top_lay.addWidget(QLabel("Main Bar Φ:"))
        self.cb_bar_dia = QComboBox()
        for d_mm in [12, 14, 16, 18, 20, 22, 25, 28, 32]:
            self.cb_bar_dia.addItem(f"Φ{d_mm} mm", d_mm)
        self.cb_bar_dia.setCurrentIndex(1)  # Default Φ14/Φ16
        self.cb_bar_dia.setStyleSheet(
            "QComboBox { background: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 3px 8px; font-weight: bold; } "
            "QComboBox QAbstractItemView { background: #FFFFFF; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; border: 1px solid #94A3B8; }"
        )
        self.cb_bar_dia.currentIndexChanged.connect(self._on_design_params_changed)
        top_lay.addWidget(self.cb_bar_dia)

        self.lbl_rc_summary = QLabel("Select a beam to view its Excel Sheet4 flexural calculations & longitudinal R.C. elevation.")
        self.lbl_rc_summary.setStyleSheet("color: #15803D; font-weight: bold;")
        top_lay.addWidget(self.lbl_rc_summary, 1)
        vbox.addWidget(top_bar)

        self.rc_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Pane: Excel Sheet4 Flexural Design Sheet (matching 5_e8049e44.PNG)
        self.excel_calc_view = QTextBrowser()
        self.excel_calc_view.setMinimumWidth(360)
        self.excel_calc_view.setMaximumWidth(480)
        self.excel_calc_view.setStyleSheet(
            "QTextBrowser { background: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px; }"
        )
        self.rc_splitter.addWidget(self.excel_calc_view)

        # Right Pane: Longitudinal Reinforcement & Section A-A
        self.rc_scene = QGraphicsScene(self)
        self.rc_view = QGraphicsView(self.rc_scene)
        self.rc_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rc_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.rc_view.setBackgroundBrush(QBrush(QColor("#FFFFFF")))
        self.rc_view.setStyleSheet("border: 1px solid #CBD5E1; background: #FFFFFF;")
        self.rc_splitter.addWidget(self.rc_view)
        self.rc_splitter.setStretchFactor(0, 0)
        self.rc_splitter.setStretchFactor(1, 1)
        self.rc_splitter.setSizes([410, 920])

        vbox.addWidget(self.rc_splitter, 1)

    def _on_design_params_changed(self, _idx: int = 0) -> None:
        idx = self.cb_beam_select.currentIndex()
        if idx < 0:
            return
        bid = str(self.cb_beam_select.itemData(idx))
        story = self.studio.current_story_data
        bm = next((b for b in story.get("beams", []) if str(b["id"]) == bid), None)
        if bm is None:
            return
        mode_val = str(self.cb_design_mode.currentData() or "double")
        dia_val = int(self.cb_bar_dia.currentData() or 16)
        bm["design_mode"] = mode_val
        bm["main_bar_dia_mm"] = dia_val
        story["beam_design_mode"] = mode_val
        story["default_main_bar_dia_mm"] = dia_val
        self.studio.save_and_sync_current_story()
        self.studio._solve_story_and_refresh_views(select_beam_id=bid)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._is_updating and self.studio.last_analysis_bundle and self.cb_beam_select.currentIndex() >= 0:
            self._resize_timer.start()

    def _on_debounced_resize(self) -> None:
        if self._is_updating or not self.studio.last_analysis_bundle:
            return
        idx = self.cb_beam_select.currentIndex()
        if idx >= 0:
            self._on_beam_selected(idx)

    def populate_results(
        self, story_data: Dict[str, Any], bundle: Dict[str, Any], select_beam_id: Optional[str] = None
    ) -> None:
        beams = story_data.get("beams", [])
        self.cb_beam_select.blockSignals(True)
        self.cb_beam_select.clear()
        target_idx = 0
        for i, bm in enumerate(beams):
            bid = str(bm["id"])
            des = bundle.get("beam_designs", {}).get(bid, {})
            n_sp = int(des.get("num_spans", len(bm.get("spans", []))))
            self.cb_beam_select.addItem(
                f"{bid} ({bm.get('beam_kind', 'hidden').upper()} {bm.get('width_m', 0.4):.2f}×{bm.get('depth_m', 0.3):.2f}m — {n_sp} Spans)",
                bid,
            )
            if select_beam_id is not None and bid == str(select_beam_id):
                target_idx = i
        self.cb_beam_select.blockSignals(False)

        if beams:
            self.cb_beam_select.setCurrentIndex(target_idx)
            self._on_beam_selected(target_idx)
        else:
            self.rc_scene.clear()
            self.excel_calc_view.clear()

    def _render_excel_sheet4_html(self, bid: str, bm: Dict[str, Any], des: Dict[str, Any]) -> str:
        fc_val = float(self.studio.master_project["materials_and_soil"]["fc_mpa"]) if self.studio.master_project else 20.0
        fy_val = float(self.studio.master_project["materials_and_soil"]["fy_mpa"]) if self.studio.master_project else 350.0
        b_mm = int(des.get("b_mm", round(float(bm.get("width_m", 0.4)) * 1000)))
        h_mm = int(des.get("h_mm", round(float(bm.get("depth_m", 0.3)) * 1000)))
        init_b_mm = int(des.get("initial_b_mm", b_mm))
        init_h_mm = int(des.get("initial_h_mm", h_mm))
        d_mm = float(des.get("d_mm", h_mm - 38.0))
        dc_mm = float(des.get("dc_mm", 25.0))
        db_mm = int(des.get("main_bar_dia_mm", 14))
        ds_mm = int(des.get("stirrup_dia_mm", 6))
        beta1 = float(des.get("beta1", 0.85))
        nbs = int(des.get("n_max_per_layer", 8))
        pmin = float(des.get("rho_min", 0.004))
        pmax = float(des.get("rho_max_single", 0.01956))
        pact = float(des.get("rho_act", 0.004))
        min_bars = int(des.get("min_bars_excel", des.get("n_min_cont", 4)))
        max_bars = int(des.get("max_bars_excel", 19))
        gov_mu_signed = float(des.get("governing_mu_signed_knm", 0.0))
        gov_f = des.get("governing_flexure_details", des.get("neg_flexure_details", {}))
        ku_v = float(gov_f.get("ku", 0.0))
        w_v = float(gov_f.get("omega", 0.0))
        rho_v = float(gov_f.get("rho", 0.0))
        as_calc = float(gov_f.get("as_single_calc_mm2", gov_f.get("as_calc_mm2", 0.0)))
        as_one = float(des.get("as_one_bar_mm2", 153.86))
        n_gov = int(gov_f.get("n_total", min_bars))
        as_tot = float(gov_f.get("as_prov_mm2", n_gov * as_one))
        b_kind_lbl = "hidden beam" if str(bm.get("beam_kind", "hidden")).lower() == "hidden" else "drop beam"

        enlarged_badge = ""
        if b_mm > init_b_mm or h_mm > init_h_mm:
            enlarged_badge = (
                f"<div style='background:#FEF3C7;border:1px solid #D97706;color:#92400E;padding:4px 8px;"
                f"margin-bottom:6px;font-size:11px;font-weight:bold;border-radius:3px;'>"
                f"Section Auto-Sized (+100 mm step): {init_b_mm}×{init_h_mm} mm &rarr; <b>{b_mm}×{h_mm} mm</b>"
                f"</div>"
            )

        station_rows_html = ""
        for st in des.get("station_design_table", []):
            station_rows_html += (
                f"<tr>"
                f"<td style='padding:3px 6px;border-bottom:1px solid #E2E8F0;font-weight:bold;color:#0F172A;'>"
                f"For M = {st['mu_signed_knm']:g} ({st['station_label']}) use</td>"
                f"<td style='padding:3px 8px;border-bottom:1px solid #E2E8F0;font-weight:bold;color:#FFFFFF;"
                f"background:#2563EB;text-align:center;'>{st['bars_str']}</td>"
                f"</tr>"
            )

        return f"""
        <div style='font-family:Segoe UI,Arial,sans-serif;font-size:11.5px;color:#0F172A;'>
          <div style='background:#0F172A;color:#FFFFFF;padding:5px 8px;font-weight:bold;font-size:12px;border-radius:3px;margin-bottom:6px;'>
            Design of Flexure — {bid} ({b_kind_lbl.upper()})
          </div>
          {enlarged_badge}
          <table width='100%' cellspacing='0' cellpadding='2' style='border-collapse:collapse;border:1px solid #94A3B8;margin-bottom:8px;'>
            <tr style='background:#EFF6FF;'>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>h =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#3B82F6;color:#FFF;font-weight:bold;text-align:center;'>{h_mm} mm</td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>dc =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#4D7C0F;color:#FFF;font-weight:bold;text-align:center;'>{dc_mm:g} mm</td>
            </tr>
            <tr>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>b =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#3B82F6;color:#FFF;font-weight:bold;text-align:center;'>{b_mm} mm</td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>&beta;<sub>1</sub> =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#2563EB;color:#FFF;font-weight:bold;text-align:center;'>{beta1:.2f}</td>
            </tr>
            <tr style='background:#EFF6FF;'>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>Fy =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#4D7C0F;color:#FFF;font-weight:bold;text-align:center;'>{fy_val:g} MPa</td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>d =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#2563EB;color:#FFF;font-weight:bold;text-align:center;'>{d_mm:g} mm</td>
            </tr>
            <tr>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>Fc' =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#4D7C0F;color:#FFF;font-weight:bold;text-align:center;'>{fc_val:g} MPa</td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>No. bars/row =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#2563EB;color:#FFF;font-weight:bold;text-align:center;'>{nbs} bars</td>
            </tr>
            <tr style='background:#EFF6FF;'>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>d<sub>b</sub> =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#2563EB;color:#FFF;font-weight:bold;text-align:center;'>{db_mm} mm</td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>&rho;<sub>min</sub> / &rho;<sub>max</sub> =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;font-weight:bold;text-align:center;'>{pmin:.3f} / {pmax:.5f}</td>
            </tr>
            <tr>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>d<sub>s</sub> =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;background:#4D7C0F;color:#FFF;font-weight:bold;text-align:center;'>{ds_mm} mm</td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;'><b>min / max bars =</b></td>
              <td style='padding:3px 6px;border:1px solid #CBD5E1;font-weight:bold;text-align:center;'>{min_bars} / {max_bars}</td>
            </tr>
          </table>

          <table width='100%' cellspacing='0' cellpadding='3' style='border-collapse:collapse;border:1px solid #94A3B8;margin-bottom:8px;'>
            <tr style='background:#F0FDF4;'>
              <td style='border:1px solid #CBD5E1;'><b>M<sub>u,Max</sub> =</b></td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;color:#15803D;'>{gov_mu_signed:g} kN.m</td>
              <td style='border:1px solid #CBD5E1;'><b>&rho;<sub>act</sub> =</b></td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;'>{pact:.5f}</td>
            </tr>
            <tr>
              <td colspan='3' style='border:1px solid #CBD5E1;'><b>K<sub>u</sub></b> = (M<sub>u</sub>&times;10<sup>6</sup>)/(0.9&times;b&times;F<sub>c</sub>'&times;d<sup>2</sup>) =</td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;'>{ku_v:.5f}</td>
            </tr>
            <tr style='background:#F8FAFC;'>
              <td colspan='3' style='border:1px solid #CBD5E1;'><b>&omega;</b> = (1 &minus; &radic;(1 &minus; 2.36&times;K<sub>u</sub>)) / 1.18 =</td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;'>{w_v:.5f}</td>
            </tr>
            <tr>
              <td colspan='3' style='border:1px solid #CBD5E1;'><b>&rho;</b> = &omega; &times; (F<sub>c</sub>' / F<sub>y</sub>) =</td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;'>{rho_v:.4f}</td>
            </tr>
            <tr style='background:#F8FAFC;'>
              <td style='border:1px solid #CBD5E1;'><b>A<sub>s</sub> = &rho;(b&times;d)</b></td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;'>{as_calc:.2f} mm&sup2;</td>
              <td style='border:1px solid #CBD5E1;'><b>A<sub>s,1bar</sub> =</b></td>
              <td style='border:1px solid #CBD5E1;font-weight:bold;'>{as_one:.2f} mm&sup2;</td>
            </tr>
            <tr style='background:#EFF6FF;'>
              <td style='border:1px solid #CBD5E1;'><b>N<sub>bar</sub> =</b></td>
              <td style='border:1px solid #CBD5E1;background:#2563EB;color:#FFF;font-weight:bold;text-align:center;'>{n_gov} &Phi; {db_mm}</td>
              <td style='border:1px solid #CBD5E1;'><b>A<sub>s,total</sub> =</b></td>
              <td style='border:1px solid #CBD5E1;background:#2563EB;color:#FFF;font-weight:bold;text-align:center;'>{as_tot:.1f} mm&sup2;</td>
            </tr>
          </table>

          <div style='background:#F1F5F9;padding:4px 6px;font-weight:bold;border:1px solid #CBD5E1;margin-bottom:2px;'>
            Station-by-Station Reinforcement Schedule:
          </div>
          <table width='100%' cellspacing='0' cellpadding='2' style='border-collapse:collapse;border:1px solid #CBD5E1;'>
            {station_rows_html}
          </table>
        </div>
        """

    def _on_beam_selected(self, idx: int) -> None:
        if self._is_updating:
            return
        self._is_updating = True
        try:
            self.rc_scene.clear()
            self.rc_view.resetTransform()
            if idx < 0 or not self.studio.last_analysis_bundle:
                return
            bid = str(self.cb_beam_select.itemData(idx))
            story = self.studio.current_story_data
            bm = next((b for b in story.get("beams", []) if str(b["id"]) == bid), None)
            res = self.studio.last_analysis_bundle.get("beam_results", {}).get(bid)
            des = self.studio.last_analysis_bundle.get("beam_designs", {}).get(bid)
            if not res or not des or bm is None:
                return

            # Sync design mode & main bar Φ selectors without firing signals
            cur_mode = str(bm.get("design_mode", des.get("design_mode", story.get("beam_design_mode", "double")))).lower()
            cur_dia = int(bm.get("main_bar_dia_mm", des.get("main_bar_dia_mm", story.get("default_main_bar_dia_mm", 16))))
            self.cb_design_mode.blockSignals(True)
            self.cb_design_mode.setCurrentIndex(1 if cur_mode == "single" else 0)
            self.cb_design_mode.blockSignals(False)
            self.cb_bar_dia.blockSignals(True)
            dia_idx = self.cb_bar_dia.findData(cur_dia)
            if dia_idx >= 0:
                self.cb_bar_dia.setCurrentIndex(dia_idx)
            self.cb_bar_dia.blockSignals(False)

            # Render Excel Sheet4 Calculation Panel on the left (skip redundant HTML relayout on resize)
            sheet4_html = self._render_excel_sheet4_html(bid, bm, des)
            if sheet4_html != self._last_sheet4_html:
                self._last_sheet4_html = sheet4_html
                self.excel_calc_view.setHtml(sheet4_html)

            as_pos = des.get("as_pos_req_mm2", des.get("as_pos_req", 0.0))
            as_neg = des.get("as_neg_req_mm2", des.get("as_neg_req", 0.0))
            cont_bars = des.get("continuous_min_bars", "4 Φ 14")
            self.lbl_rc_summary.setText(
                f"Beam {bid} ({des.get('b_mm', 400)}×{des.get('h_mm', 300)} mm, d={des.get('d_mm', 252):g} mm, n_max/row={des.get('n_max_per_layer', 8)}): "
                f"Min Bars = {cont_bars} | Bot = {des.get('bottom_bars')} ({as_pos:.1f} mm²) | "
                f"Top = {des.get('top_bars')} ({as_neg:.1f} mm²) | Stirrups = {des.get('stirrups')}"
            )
            self._draw_beam_rc_canvas(bid, bm, res, des)
        finally:
            self._is_updating = False

    def _draw_beam_rc_canvas(
        self, bid: str, bm: Dict[str, Any], res: Dict[str, Any], des: Dict[str, Any]
    ) -> None:
        cont_bars = des.get("continuous_min_bars", "4 Φ 14")

        sc = self.rc_scene
        tot_l = max(0.5, float(res.get("total_len", 5.0)))

        # True Right-Pane Viewport Width Utilization (v2.4.0 Gutter Deduction & Section A-A Fit):
        raw_vp_w = float(self.rc_view.viewport().width())
        raw_vp_h = float(self.rc_view.viewport().height())
        vp_w = max(420.0, raw_vp_w - 28.0)
        vp_h = max(380.0, raw_vp_h - 10.0)

        b_m = float(bm.get("width_m", 0.40))
        h_m = float(bm.get("depth_m", 0.30))
        sec_w = max(110.0, min(170.0, b_m * 220.0))
        sec_h = max(110.0, min(190.0, h_m * 220.0))

        sup_table = res.get("support_critical_table", [])
        c_left = float(bm.get("cantilever_left_m", 0.0))
        c_right = float(bm.get("cantilever_right_m", 0.0))

        ext_left_m = (float(sup_table[0].get("width_m", 0.20)) / 2.0) if (sup_table and c_left <= 1e-3) else 0.0
        ext_right_m = (float(sup_table[-1].get("width_m", 0.20)) / 2.0) if (sup_table and c_right <= 1e-3) else 0.0

        # Solve horizontal scale across FULL physical width (ext_left + tot_l + ext_right) so Section A-A NEVER clips!
        left_margin_px = 50.0
        gap_to_sec_px = 36.0
        right_sec_pad_px = 24.0
        avail_phys_px = max(280.0, vp_w - left_margin_px - gap_to_sec_px - sec_w - right_sec_pad_px)
        tot_phys_m = max(0.5, ext_left_m + tot_l + ext_right_m)
        scale_x = avail_phys_px / tot_phys_m
        x_beam_left = left_margin_px
        x0 = x_beam_left + ext_left_m * scale_x
        x_beam_right = x0 + (tot_l + ext_right_m) * scale_x
        w_beam_phys_px = x_beam_right - x_beam_left

        y_top = max(145.0, vp_h * 0.26)
        h_px = max(115.0, min(195.0, vp_h * 0.24))
        y_bot = y_top + h_px

        hdr = sc.addText(
            f"Longitudinal Reinforcement & Stirrup Elevation — Beam {bid} ({bm.get('beam_kind', 'hidden').upper()} {b_m:.2f}×{h_m:.2f}m | Cont. As,min = {cont_bars} Top & Bot)",
            QFont("Arial", 11, QFont.Weight.Bold),
        )
        hdr.setDefaultTextColor(QColor("#0B3C5D"))
        hdr.setPos(max(16.0, x_beam_left - 12.0), 18)

        beam_rect = QRectF(x_beam_left, y_top, w_beam_phys_px, h_px)
        sc.addRect(beam_rect, QPen(QColor("#1E293B"), 2.4), QBrush(QColor(241, 245, 249, 235)))

        for sup in sup_table:
            sx_px = x0 + float(sup["x_m"]) * scale_x
            sup_w_m = float(sup.get("width_m", 0.30))
            sup_d_m = float(sup.get("depth_m", 0.30))
            sup_kind = str(sup.get("support_kind", "column")).lower()
            sup_id = str(sup.get("target_id", "Sup"))
            col_w_px = max(20.0, sup_w_m * scale_x)
            if sup_kind == "beam":
                bm_h_px = max(h_px, (sup_d_m / max(0.20, h_m)) * h_px)
                crect_bm = QRectF(sx_px - col_w_px / 2.0, y_top, col_w_px, bm_h_px)
                sc.addRect(crect_bm, QPen(QColor("#D97706"), 2.2, Qt.PenStyle.DashLine), QBrush(QColor(245, 158, 11, 55)))
                sc.addLine(sx_px - col_w_px / 2.0, y_top, sx_px + col_w_px / 2.0, y_top + bm_h_px, QPen(QColor("#D97706"), 1.4))
                sc.addLine(sx_px - col_w_px / 2.0, y_top + bm_h_px, sx_px + col_w_px / 2.0, y_top, QPen(QColor("#D97706"), 1.4))
                clbl = sc.addText(
                    f"Carrier Beam {sup_id} [Roller]\n({sup_w_m:.2f}×{sup_d_m:.2f}m @ {sup['x_m']:.2f}m)",
                    QFont("Arial", 8, QFont.Weight.Bold),
                )
                clbl.setDefaultTextColor(QColor("#B45309"))
                clbl.setPos(sx_px - 48, y_top + bm_h_px + 48)
            else:
                crect_bot = QRectF(sx_px - col_w_px / 2.0, y_bot, col_w_px, 80.0)
                sc.addRect(crect_bot, QPen(QColor("#DC2626"), 2.0), QBrush(QColor(239, 68, 68, 40)))
                clbl = sc.addText(
                    f"Col {sup_id} [Hinge]\n(w={sup_w_m:.2f}m @ {sup['x_m']:.2f}m)",
                    QFont("Arial", 8, QFont.Weight.Bold),
                )
                clbl.setDefaultTextColor(QColor("#991B1B"))
                clbl.setPos(sx_px - 42, y_bot + 84)
            sc.addLine(sx_px, y_top - 44, sx_px, y_bot + 90, QPen(QColor("#94A3B8"), 1.1, Qt.PenStyle.DashDotLine))

        stir_pen = QPen(QColor("#059669"), 1.2)
        n_stirs = 48
        for i_s in range(1, n_stirs):
            sx = x_beam_left + (w_beam_phys_px * i_s / n_stirs)
            sc.addLine(sx, y_top + 12, sx, y_bot - 12, stir_pen)

        cover_px = 10.0
        bar_x1 = x_beam_left + cover_px
        bar_x2 = x_beam_right - cover_px
        bot_bar_y = y_bot - 14.0
        top_bar_y = y_top + 14.0

        bot_pen = QPen(QColor("#0284C7"), 3.4)
        sc.addLine(bar_x1, bot_bar_y, bar_x2, bot_bar_y, bot_pen)
        sc.addLine(bar_x1, bot_bar_y, bar_x1, bot_bar_y - h_px * 0.48, bot_pen)
        sc.addLine(bar_x2, bot_bar_y, bar_x2, bot_bar_y - h_px * 0.48, bot_pen)

        top_pen = QPen(QColor("#D97706"), 2.8, Qt.PenStyle.DashLine)
        sc.addLine(bar_x1, top_bar_y, bar_x2, top_bar_y, top_pen)
        sc.addLine(bar_x1, top_bar_y, bar_x1, top_bar_y + h_px * 0.48, QPen(QColor("#EA580C"), 3.0))
        sc.addLine(bar_x2, top_bar_y, bar_x2, top_bar_y + h_px * 0.48, QPen(QColor("#EA580C"), 3.0))

        span_designs = des.get("span_designs", [])
        segs = get_beam_span_segments(bm)
        for i_sp, seg in enumerate(segs):
            mx_px = x0 + ((seg["start_m"] + seg["end_m"]) / 2.0) * scale_x
            sp_des = span_designs[min(i_sp, len(span_designs) - 1)] if span_designs else {}
            bot_txt = sp_des.get("bottom_bars", des.get("bottom_bars", "4 Φ 14"))
            bot_add = sp_des.get("bottom_additional_bars", "None")
            stir_txt = sp_des.get("stirrups", des.get("stirrups", "Φ8 @ 150 mm"))
            add_line = f" (Cont. {cont_bars} + Add. {bot_add})" if bot_add != "None" else f" (Cont. {cont_bars})"

            blbl = sc.addText(
                f"{seg['label']} ({seg['length_m']:.2f}m)\nBot: {bot_txt}{add_line}\nStirrups: {stir_txt}",
                QFont("Arial", 8, QFont.Weight.Bold),
            )
            blbl.setDefaultTextColor(QColor("#0369A1"))
            blbl.setPos(mx_px - 68, y_bot + 6)

        sup_designs = des.get("support_designs", [])
        for i_s, sup in enumerate(sup_table):
            sx_px = x0 + float(sup["x_m"]) * scale_x
            s_des = sup_designs[i_s] if i_s < len(sup_designs) else {}
            top_txt = s_des.get("top_bars", des.get("top_bars", "4 Φ 14"))
            top_add = s_des.get("top_additional_bars", "None")
            top_add_str = f" [+{top_add} Add.]" if top_add != "None" else ""
            sc.addLine(
                max(bar_x1, sx_px - 55),
                top_bar_y + 4,
                min(bar_x2, sx_px + 55),
                top_bar_y + 4,
                QPen(QColor("#DC2626"), 3.8),
            )
            tlbl = sc.addText(
                f"{sup['target_id']} Top: {top_txt}{top_add_str}\n(-Mu={s_des.get('mu_neg_center_knm', s_des.get('mu_neg_face_knm', 0.0)):.1f}kNm)",
                QFont("Arial", 8, QFont.Weight.Bold),
            )
            tlbl.setDefaultTextColor(QColor("#B91C1C"))
            tlbl.setPos(sx_px - 50, y_top - 64)

        # Draw Cross-Section A-A on the Right Side
        sec_x = x_beam_right + 38.0
        sec_y = y_top

        sec_hdr = sc.addText(f"Section A-A ({b_m:.2f} × {h_m:.2f} m)", QFont("Arial", 10, QFont.Weight.Bold))
        sec_hdr.setDefaultTextColor(QColor("#0F172A"))
        sec_hdr.setPos(sec_x, sec_y - 30)

        sc.addRect(QRectF(sec_x, sec_y, sec_w, sec_h), QPen(QColor("#0F172A"), 2.4), QBrush(QColor("#F1F5F9")))
        sc.addRect(
            QRectF(sec_x + 12, sec_y + 12, sec_w - 24, sec_h - 24),
            QPen(QColor("#059669"), 2.0),
            QBrush(Qt.BrushStyle.NoBrush),
        )
        # Draw top and bottom rebar circles inside Section A-A (supporting multi-layer rows for Drop Beams)
        nbs_max = max(2, int(des.get("n_max_per_layer", 6)))
        n_top_tot = max(2, int(des.get("n_bars_neg_total", 4)))
        n_bot_tot = max(2, int(des.get("n_bars_pos_total", 4)))

        def draw_rebar_rows(n_tot: int, is_top: bool) -> None:
            rem = n_tot
            r_idx = 0
            while rem > 0 and r_idx < 3:
                n_row = min(rem, nbs_max)
                ry = (sec_y + 16 + r_idx * 14) if is_top else (sec_y + sec_h - 24 - r_idx * 14)
                for i_b in range(n_row):
                    bx = sec_x + 18 + (sec_w - 36) * (i_b / max(1.0, float(n_row - 1))) if n_row > 1 else (sec_x + sec_w / 2.0)
                    pen_c = QColor("#991B1B") if is_top else QColor("#0369A1")
                    br_c = QColor("#DC2626") if is_top else QColor("#0284C7")
                    sc.addEllipse(QRectF(bx - 4.5, ry, 9.0, 9.0), QPen(pen_c, 1.1), QBrush(br_c))
                rem -= n_row
                r_idx += 1

        draw_rebar_rows(n_top_tot, is_top=True)
        draw_rebar_rows(n_bot_tot, is_top=False)

        sec_info = sc.addText(
            f"b = {des.get('b_mm', 400)} mm | h = {des.get('h_mm', 300)} mm\n"
            f"d = {des.get('d_mm', 252):g} mm | dc = {des.get('dc_mm', 25):g} mm\n"
            f"Top: {des.get('top_bars')} (Max {nbs_max}/row)\n"
            f"Bot: {des.get('bottom_bars')} (Min {cont_bars})\n"
            f"Stir: {des.get('stirrups')}",
            QFont("Arial", 8, QFont.Weight.Bold),
        )
        sec_info.setDefaultTextColor(QColor("#0F172A"))
        sec_info.setPos(sec_x, sec_y + sec_h + 8)

        sc.setSceneRect(0, 0, min(vp_w, sec_x + sec_w + 16.0), max(vp_h - 16.0, y_bot + 145.0))


class SchedulesAndReportsWidget(QWidget):
    """
    Workspace 3: '4. Schedules & Engineering Report' (v1.8.0 Clean Light Theme)
    Dedicated schedules & reporting workspace with 3 sub-tabs:
      1. Beams Reinforcement Schedule (ACI 318-19) — with 'No. of Spans' strictly between 'Beam ID' and 'Section (b × h)',
         excluding cantilevers from the span count, and one row per span/cantilever zone for multi-span clarity.
      2. Columns & 4-Way Framing Schedule.
      3. Printable Engineering Calculation Report.
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #CBD5E1; background: #FFFFFF; }"
            "QTabBar::tab { background: #E2E8F0; color: #0F172A; font-weight: bold; padding: 8px 18px; border: 1px solid #CBD5E1; }"
            "QTabBar::tab:selected { background: #0284C7; color: #FFFFFF; border-bottom: 2px solid #0369A1; }"
        )

        # Sub-Tab 1: Beams Reinforcement Schedule
        self.tbl_beam_schedule = QTableWidget(0, 12)
        self.tbl_beam_schedule.setHorizontalHeaderLabels([
            "Beam ID",
            "No. of Spans\n(Excl. Cantilevers)",
            "Section (b × h)",
            "Beam Type",
            "Span / Zone",
            "Length (m)",
            "Wall Load",
            "Max +Mu (kN.m)",
            "Bottom Steel (ACI 318)",
            "Support Center -Mu (kN.m)",
            "Top Steel (ACI 318)",
            "Critical Vu (kN) & Stirrups",
        ])
        self.tbl_beam_schedule.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_beam_schedule.setStyleSheet(
            "QTableWidget { background: #FFFFFF; color: #0F172A; gridline-color: #CBD5E1; font-size: 11px; }"
            "QHeaderView::section { background: #F1F5F9; color: #0F172A; font-weight: bold; padding: 5px; border: 1px solid #CBD5E1; }"
        )
        self.tabs.addTab(self.tbl_beam_schedule, "1. Beams Reinforcement Schedule (ACI 318-19)")

        # Sub-Tab 2: Columns & 4-Way Framing Schedule
        self.tbl_columns = QTableWidget(0, 7)
        self.tbl_columns.setHorizontalHeaderLabels([
            "Column ID",
            "Section (mm)",
            "Story Pu (kN)",
            "End Moments (Mux, Muy)",
            "4-Way Framing (N/S/E/W)",
            "Reinforcement (ACI 318)",
            "Capacity φPn,max (kN)",
        ])
        self.tbl_columns.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_columns.setStyleSheet(
            "QTableWidget { background: #FFFFFF; color: #0F172A; gridline-color: #CBD5E1; font-size: 11px; }"
            "QHeaderView::section { background: #F1F5F9; color: #15803D; font-weight: bold; padding: 5px; border: 1px solid #CBD5E1; }"
        )
        self.tabs.addTab(self.tbl_columns, "2. Columns & 4-Way Framing Schedule")

        # Sub-Tab 3: Printable Engineering Calculation Report
        self.report_browser = QTextBrowser()
        self.report_browser.setStyleSheet("background: #FFFFFF; color: #0F172A; padding: 10px;")
        self.tabs.addTab(self.report_browser, "3. Printable Calculation Report")

        vbox.addWidget(self.tabs, 1)

    def populate_results(self, master_project: Dict[str, Any], story_data: Dict[str, Any], bundle: Dict[str, Any]) -> None:
        beams = story_data.get("beams", [])
        schedule_rows: List[Tuple[str, ...]] = []
        beam_report_rows_html = ""

        for bm in beams:
            bid = str(bm["id"])
            res = bundle.get("beam_results", {}).get(bid, {})
            des = bundle.get("beam_designs", {}).get(bid, {})
            n_spans_excl = int(res.get("num_spans_excluding_cantilevers", des.get("num_spans", len(bm.get("spans", [])))))
            sec_str = f"{bm.get('width_m', 0.40):.2f} × {bm.get('depth_m', 0.30):.2f} m"
            btype_str = str(bm.get("beam_kind", "hidden")).upper()
            segs = get_beam_span_segments(bm)
            flags = ensure_beam_wall_flags(story_data, bm)
            span_designs = des.get("span_designs", [])

            for idx_seg, seg in enumerate(segs):
                skey = str(seg["key"])
                sp_des = span_designs[min(idx_seg, len(span_designs) - 1)] if span_designs else {}
                wall_on = "YES" if flags.get(skey, True) else "NO"
                mu_pos = float(sp_des.get("mu_pos_knm", res.get("max_pos_mu_knm", 0.0)))
                bot_bars = str(sp_des.get("bottom_bars", des.get("bottom_bars", "-")))
                mu_neg = float(res.get("max_neg_center_mu_knm", res.get("max_neg_face_mu_knm", 0.0)))
                top_bars = str(des.get("top_bars", "-"))
                vu_val = float(sp_des.get("vu_kn", res.get("max_face_vu_kn", 0.0)))
                stir_str = f"{vu_val:.1f} kN — {sp_des.get('stirrups', des.get('stirrups', '-'))}"

                schedule_rows.append((
                    bid if idx_seg == 0 else f"  ↳ {bid}",
                    str(n_spans_excl) if idx_seg == 0 else "",
                    sec_str if idx_seg == 0 else "",
                    btype_str if idx_seg == 0 else "",
                    str(seg["label"]),
                    f"{float(seg['length_m']):.2f} m",
                    wall_on,
                    f"{mu_pos:.2f}",
                    bot_bars,
                    f"{mu_neg:.2f}" if idx_seg == 0 else "-",
                    top_bars if idx_seg == 0 else "-",
                    stir_str,
                ))

            beam_report_rows_html += (
                f"<tr>"
                f"<td><b>{bid}</b></td>"
                f"<td align='center'><b>{n_spans_excl}</b></td>"
                f"<td>{sec_str}</td>"
                f"<td>{btype_str}</td>"
                f"<td>{', '.join(f'{float(s):.2f}m' for s in res.get('spans', []))}</td>"
                f"<td>{res.get('max_pos_mu_knm', 0.0):.2f}</td>"
                f"<td>{res.get('max_neg_center_mu_knm', res.get('max_neg_face_mu_knm', 0.0)):.2f}</td>"
                f"<td>{res.get('max_face_vu_kn', 0.0):.2f}</td>"
                f"<td>Bot: {des.get('bottom_bars', '-')} | Top: {des.get('top_bars', '-')} | {des.get('stirrups', '-')}</td>"
                f"</tr>"
            )

        self.tbl_beam_schedule.setRowCount(len(schedule_rows))
        for r_i, row_tuple in enumerate(schedule_rows):
            for c_i, val_str in enumerate(row_tuple):
                it = QTableWidgetItem(val_str)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c_i in (0, 1):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_beam_schedule.setItem(r_i, c_i, it)

        # Populate Columns Table
        col_recs = bundle.get("column_records", [])
        self.tbl_columns.setRowCount(len(col_recs))
        col_rows_html = ""
        for c_i, crec in enumerate(col_recs):
            des = crec["design"]
            f4 = crec["framing_4way"]
            f4_str = " | ".join(f"{k[0]}:{v['beam_id']}" for k, v in f4.items() if v) or "Corner/Edge"
            is_2h = bool(crec.get("double_height", False) or des.get("double_height", False))
            eff_h_m = float(crec.get("eff_h_m", des.get("lu_m", 3.0)))
            cid_lbl = f"{crec['column_id']} (2H={eff_h_m:.1f}m)" if is_2h else str(crec["column_id"])
            self.tbl_columns.setItem(c_i, 0, QTableWidgetItem(cid_lbl))
            self.tbl_columns.setItem(c_i, 1, QTableWidgetItem(des["section_mm"]))
            self.tbl_columns.setItem(c_i, 2, QTableWidgetItem(f"{crec['story_pu_kn']:.1f}"))
            self.tbl_columns.setItem(c_i, 3, QTableWidgetItem(f"({crec['mux_knm']:.1f}, {crec['muy_knm']:.1f})"))
            self.tbl_columns.setItem(c_i, 4, QTableWidgetItem(f4_str))
            self.tbl_columns.setItem(c_i, 5, QTableWidgetItem(des["chosen_bars"]))
            self.tbl_columns.setItem(c_i, 6, QTableWidgetItem(f"{des['phi_pn_max_kn']:.1f} ({des['status']})"))

            col_rows_html += (
                f"<tr><td><b>{cid_lbl}</b></td><td>{des['section_mm']}</td>"
                f"<td>{crec['story_pu_kn']:.1f} kN</td><td>({crec['mux_knm']:.1f}, {crec['muy_knm']:.1f}) kN.m</td>"
                f"<td>{des['chosen_bars']} ({des['rho_pct']}%)</td>"
                f"<td>{des['phi_pn_max_kn']:.1f} kN — <b>{des['status']}</b></td></tr>"
            )

        fc = float(master_project["materials_and_soil"]["fc_mpa"]) if master_project else 25.0
        fy = float(master_project["materials_and_soil"]["fy_mpa"]) if master_project else 420.0
        proj_name = master_project.get("project_name", "Project") if master_project else "Project"
        self.report_browser.setHtml(
            f"<div style='font-family: Arial, sans-serif; padding: 12px; color: #0F172A;'>"
            f"<h2>Xpert Structural Design Studio — ACI 318-19 Calculation Report ({STUDIO_VERSION})</h2>"
            f"<p><b>Project:</b> {proj_name} | "
            f"<b>Story:</b> {story_data.get('story_label', '02_Ground_Floor')} | "
            f"<b>f'c:</b> {fc} MPa | <b>Fy:</b> {fy} MPa</p>"
            f"<h3>1. Continuous Beams Analytical Slope-Deflection & ACI 318 Reinforcement Schedule</h3>"
            f"<table border='1' cellspacing='0' cellpadding='6' width='100%'>"
            f"<tr style='background:#1E293B; color:white;'>"
            f"<th>Beam ID</th><th>No. of Spans (Excl. Cantilevers)</th><th>Section (b × h)</th><th>Type</th><th>Spans (m)</th>"
            f"<th>Max +Mu (kN.m)</th><th>Center -Mu (kN.m)</th><th>Face Vu (kN)</th><th>ACI 318 Reinforcement</th></tr>"
            f"{beam_report_rows_html}</table>"
            f"<h3>2. Columns Load Takedown, Moments & ACI 318 Interaction Design</h3>"
            f"<table border='1' cellspacing='0' cellpadding='6' width='100%'>"
            f"<tr style='background:#1E293B; color:white;'><th>Column</th><th>Section</th><th>Story Pu</th>"
            f"<th>Moments (Mux, Muy)</th><th>Main Bars</th><th>Capacity φPn,max</th></tr>"
            f"{col_rows_html}</table></div>"
        )


class ProjectDataDialog(QDialog):
    """v2.4.1: Edit story count / heights / foundation depth / materials after project creation."""
    def __init__(self, parent_studio, master_project):
        super().__init__(parent_studio)
        self.studio = parent_studio; self.master = master_project
        self.setWindowTitle("Project Data — Stories, Heights & Materials")
        self.setMinimumWidth(560); self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        sh = master_project.get("story_heights", {})
        vb = QVBoxLayout(self); form = QFormLayout()
        self.sp_floors = QSpinBox(); self.sp_floors.setRange(0, 50)
        self.sp_floors.setValue(sum(1 for s in master_project.get("stories", []) if s.get("story_type") in ("typical", "standard")))
        form.addRow("Floors Above Ground:", self.sp_floors)
        self.sp_ground = QDoubleSpinBox(); self.sp_ground.setRange(2.5, 12.0); self.sp_ground.setValue(float(sh.get("ground_floor_height_m", 3.2))); self.sp_ground.setSuffix(" m"); form.addRow("Ground Floor Height:", self.sp_ground)
        self.sp_upper = QDoubleSpinBox(); self.sp_upper.setRange(2.5, 10.0); self.sp_upper.setValue(float(sh.get("upper_floor_height_m", 3.0))); self.sp_upper.setSuffix(" m"); form.addRow("Upper Floor Height:", self.sp_upper)
        self.sp_found = QDoubleSpinBox(); self.sp_found.setRange(0.5, 25.0); self.sp_found.setValue(float(sh.get("foundation_depth_m", 1.5))); self.sp_found.setSuffix(" m"); form.addRow("Foundation Depth:", self.sp_found)
        self.chk_pent = QCheckBox("Include Roof Annex / Penthouse"); self.chk_pent.setChecked(any(s.get("story_type") == "penthouse" for s in master_project.get("stories", []))); form.addRow(self.chk_pent)
        mats = master_project.get("materials_and_soil", {})
        self.sp_fc = QDoubleSpinBox(); self.sp_fc.setRange(15, 100); self.sp_fc.setValue(float(mats.get("fc_mpa", 20))); self.sp_fc.setSuffix(" MPa"); form.addRow("f'c:", self.sp_fc)
        self.sp_fy = QDoubleSpinBox(); self.sp_fy.setRange(200, 1000); self.sp_fy.setValue(float(mats.get("fy_mpa", 350))); self.sp_fy.setSuffix(" MPa"); form.addRow("Fy:", self.sp_fy)
        self.sp_qall = QDoubleSpinBox(); self.sp_qall.setRange(50, 2000); self.sp_qall.setValue(float(mats.get("soil_bearing_qall_kn_m2", 150))); self.sp_qall.setSuffix(" kN/m²"); form.addRow("q_all:", self.sp_qall)
        vb.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save); bb.rejected.connect(self.reject); vb.addWidget(bb)
    def _save(self):
        import xpert_project_io as _pio
        cfg = {"floors_above_ground": self.sp_floors.value(), "ground_floor_height_m": self.sp_ground.value(),
               "upper_floor_height_m": self.sp_upper.value(), "foundation_depth_m": self.sp_found.value(),
               "include_penthouse": self.chk_pent.isChecked(), "fc_mpa": self.sp_fc.value(), "fy_mpa": self.sp_fy.value(),
               "soil_bearing_qall_kn_m2": self.sp_qall.value()}
        _pio.update_project_story_configuration(self.master, cfg)
        self.studio._populate_story_selector(); self.studio.refresh_story_ui()
        self.studio.update_contextual_prompt("Project Data updated (stories, heights & materials).")
        self.accept()


class XpertStudioMainWindow(QMainWindow):
    """
    Main Studio Workspace for Xpert Structural Design Studio (v1.8.0-structural-bim-pro).
    - Clean Silver-Slate & White Engineering UI Theme (no black chrome or black-on-black dropdowns).
    - Workflow-Ordered Top Menu Bar: File > View > Draw > Modify > Dimensions > Analysis & Design.
    - Multi-Step Undo (Ctrl+Z) & Redo (Ctrl+Y) across all drawing and modification operations.
    - Right-Click Context Menu strictly for Display/Inspection; all modifications live in Modify Menu & Toolbar.
    """

    def __init__(self, initial_master_project: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.setWindowTitle(f"Xpert Structural Design Studio — {STUDIO_VERSION} (ACI 318-19)")
        self.resize(1580, 950)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        # Global Light Silver-Slate Engineering Chrome + Crisp White Dropdown Menus (Upgrades #1 & #2)
        self.setStyleSheet(
            "QMainWindow, QWidget { background-color: #F8FAFC; color: #0F172A; } "
            "QMenuBar { background-color: #F1F5F9; color: #0F172A; font-weight: bold; border-bottom: 1px solid #CBD5E1; } "
            "QMenuBar::item { background: transparent; color: #0F172A; padding: 5px 12px; } "
            "QMenuBar::item:selected { background: #0284C7; color: #FFFFFF; border-radius: 3px; } "
            "QMenu { background-color: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; padding: 4px; font-weight: bold; } "
            "QMenu::item { padding: 6px 20px; color: #0F172A; } "
            "QMenu::item:selected { background-color: #0284C7; color: #FFFFFF; } "
            "QToolBar { background-color: #F1F5F9; border: 1px solid #CBD5E1; spacing: 4px; padding: 3px; } "
            "QPushButton { background-color: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 4px 8px; font-weight: bold; } "
            "QPushButton:hover { background-color: #E2E8F0; } "
            "QComboBox { background-color: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 3px 8px; font-weight: bold; } "
            "QComboBox:hover { border-color: #0284C7; } "
            "QComboBox QAbstractItemView { background-color: #FFFFFF; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; border: 1px solid #94A3B8; outline: 0px; } "
            "QDoubleSpinBox, QSpinBox, QLineEdit { background-color: #FFFFFF; color: #0F172A; border: 1px solid #94A3B8; border-radius: 3px; padding: 2px 6px; font-weight: bold; } "
            "QStatusBar { background-color: #F1F5F9; color: #0F172A; font-weight: bold; border-top: 1px solid #CBD5E1; }"
        )

        self.master_project: Optional[Dict[str, Any]] = initial_master_project
        self.current_story_index: int = 0
        self.current_story_data: Dict[str, Any] = {}
        self.last_analysis_bundle: Optional[Dict[str, Any]] = None

        # Multi-step Undo / Redo stacks (Upgrade #10)
        self._undo_stack: List[str] = []
        self._redo_stack: List[str] = []
        self._last_saved_snapshot: Optional[str] = None

        self._slab_only_widgets: List[Any] = []

        self._build_classic_menu_bar()
        self._build_separated_toolbars()
        self._build_main_workspace()

        if self.master_project is not None:
            set_active_project_log_dir(self.master_project.get("project_folder"))
            log_studio_event("PROJECT_READY", f"Studio opened project '{self.master_project.get('project_name')}'")
            self._populate_story_selector()
            self.update_contextual_prompt(
                f"Loaded Project: {self.master_project.get('project_name')} — Active Story: 02_Ground_Floor."
            )

    def open_project_data_dialog(self) -> None:
        if not self.master_project:
            QMessageBox.information(self, "Project Data", "Open or create a project first.")
            return
        ProjectDataDialog(self, self.master_project).exec()

    def is_tie_beams_story(self) -> bool:
        return str(self.current_story_data.get("story_id", "")) == "00_TieBeams"

    def open_diagnostic_log_dialog(self) -> None:
        proj_dir = self.master_project.get("project_folder") if self.master_project else None
        dlg = DiagnosticLogDialog(self, project_dir=proj_dir)
        dlg.exec()

    def open_startup_defaults_dialog(self) -> None:
        dlg = StartupDefaultsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if self.master_project is not None:
                settings = load_studio_global_settings()
                self.master_project["rebar_diameters_table"] = settings.get("rebar_diameters_table", [])
            self.update_contextual_prompt("Saved Startup Defaults (Default Projects Directory & Steel Bar Diameters Table).")

    def open_studio_options_dialog(self) -> None:
        dlg = StudioOptionsDialog(self, master_project=self.master_project, current_story_data=self.current_story_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if "adopted_slab_thickness_cm" in self.current_story_data:
                self.sp_adopted_thick.setValue(float(self.current_story_data["adopted_slab_thickness_cm"]))
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            if self.current_story_data.get("beams"):
                self._solve_story_and_refresh_views()
            self.update_contextual_prompt("Applied Options (Materials, Concrete/Steel Strength & Hollow-Block Slab Parameters).")

    def _build_classic_menu_bar(self) -> None:
        """
        Top Menu Bar strictly ordered by structural workflow stages:
        File > View > Draw > Modify > Dimensions > Analysis & Design > Options
        """
        mbar = self.menuBar()

        # 1. FILE MENU
        m_file = mbar.addMenu("&File")
        act_new = QAction("New Structural Project...", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.open_new_project_dialog)
        m_file.addAction(act_new)

        act_open = QAction(f"Open Master Project (*{MASTER_FILE_EXT})...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.open_existing_project_file_dialog)
        m_file.addAction(act_open)

        act_imp_dxf = QAction("Import Architectural .DXF Underlay for Active Story...", self)
        act_imp_dxf.setShortcut("Ctrl+I")
        act_imp_dxf.triggered.connect(self.import_arch_dxf_for_current_story)
        m_file.addAction(act_imp_dxf)

        act_save = QAction("Save Story && Sync .DXF", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_and_sync_current_story)
        m_file.addAction(act_save)

        m_file.addSeparator()
        act_start_def = QAction("Startup Defaults (Projects Folder & Rebar Table)...", self)
        act_start_def.triggered.connect(self.open_startup_defaults_dialog)
        m_file.addAction(act_start_def)

        act_opts = QAction("Options (Materials & Hollow-Block Data)...", self)
        act_opts.triggered.connect(self.open_studio_options_dialog)
        m_file.addAction(act_opts)

        # 2. VIEW MENU
        m_view = mbar.addMenu("&View")
        for lbl, tid in [
            ("Zoom Window (Drag Box)", "ZOOM_WINDOW"),
            ("Zoom Extents (Fit All)", "ZOOM_EXTENTS"),
            ("Pan View (Hand)", "PAN"),
            ("Zoom In (+)", "ZOOM_IN"),
            ("Zoom Out (-)", "ZOOM_OUT"),
        ]:
            act = QAction(lbl, self)
            act.triggered.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            m_view.addAction(act)
        m_view.addSeparator()
        act_diag_log = QAction("Open Session Diagnostic Log...", self)
        act_diag_log.triggered.connect(self.open_diagnostic_log_dialog)
        m_view.addAction(act_diag_log)

        # 3. DRAW MENU
        m_draw = mbar.addMenu("&Draw")
        slab_only_tids = {"DRAW_SLAB_EDGE", "DRAW_BEAM_HID", "PICK_SLAB", "FLIP_RIB", "PICK_OPENING", "DRAW_OPENING", "AUTO_FILL_SLABS"}
        for label, tool_id in [
            ("Select / Box-Select Elements", "SELECT"),
            ("Step 1: Draw Building Boundary Polyline (00-XD-EDGE)", "DRAW_SLAB_EDGE"),
            ("Step 2: Place Structural Column 0.20×0.40m (00-XD-COL)", "DRAW_COL"),
            ("Step 3A: Draw Hidden Beam 0.30m Width", "DRAW_BEAM_HID"),
            ("Step 3B: Draw Drop Beam 0.20×0.40m Width", "DRAW_BEAM_DROP"),
            ("Step 4A: Pick Area -> Create Slab", "PICK_SLAB"),
            ("Step 4B: Flip Selected or Picked Slab Rib (0° ↔ 90°)", "FLIP_RIB"),
            ("Step 4C: Pick Area -> Toggle Void Opening", "PICK_OPENING"),
            ("Step 4D: Draw Slab Opening [Rect / Space=Poly] (00-XD-OPEN)", "DRAW_OPENING"),
            ("Auto-Fill All Story Slabs (1-Click)", "AUTO_FILL_SLABS"),
            ("Convert Columns from Imported Arch .DXF", "CONVERT_ARCH_COLS"),
            ("Load Standard 2-Bay Structural Layout", "LOAD_TEMPLATE"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, tid=tool_id: self.activate_cad_tool(tid))
            m_draw.addAction(act)
            if tool_id in slab_only_tids:
                self._slab_only_widgets.append(act)

        # 4. MODIFY MENU (Includes Undo/Redo, Convert Beam Hidden <-> Drop, Flip Slab Rib, Wall Load, Move, Align, Delete)
        m_modify = mbar.addMenu("&Modify")
        act_undo = QAction("Undo Last Action (Ctrl+Z)", self)
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        act_undo.triggered.connect(self.undo_action)
        m_modify.addAction(act_undo)

        act_redo = QAction("Redo Action (Ctrl+Y)", self)
        act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        act_redo.triggered.connect(self.redo_action)
        m_modify.addAction(act_redo)
        m_modify.addSeparator()

        for lbl, cb, is_slab_only in [
            ("Convert Selected Beam: Hidden ↔ Drop", self.convert_selected_beam_kind, True),
            ("Flip Selected Slab Rib Direction (0° ↔ 90°)", self.flip_selected_or_pick_slab_rib, True),
            ("Toggle Masonry Wall Load on Selected Beam", self.toggle_selected_beam_wall_load, False),
            ("Align Element Face to Edge (AL)", lambda: self.activate_cad_tool("ALIGN_ELEMENT"), False),
            ("Move Selected by Base-Point -> Second-Point (MV)", lambda: self.activate_cad_tool("MOVE_ELEMENT"), False),
            ("Move Selected by Numeric ΔX, ΔY Dialog...", self.open_numeric_move_dialog, False),
            ("Rotate Selected or Clicked Column 90° (R)", self.rotate_selected_or_default_column, False),
            ("Delete Selected Elements (Del)", self.delete_selected_object, False),
        ]:
            act = QAction(lbl, self)
            act.triggered.connect(cb)
            m_modify.addAction(act)
            if is_slab_only:
                self._slab_only_widgets.append(act)

        # 5. DIMENSIONS MENU
        m_dims = mbar.addMenu("Di&mensions")
        for lbl, tid in [
            ("Linear Dimension Horizontal/Vertical (DLI)", "DIM_LINEAR"),
            ("Aligned Dimension (DAL)", "DIM_ALIGNED"),
            ("Auto-Generate Exterior && Grid Dimensions (1-Click)", "DIM_AUTO_EXTERIOR"),
            ("Measure Distance && Angle (DI)", "MEASURE_DIST"),
            ("Clear All Story Dimensions", "DIM_CLEAR_ALL"),
        ]:
            act = QAction(lbl, self)
            act.triggered.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            m_dims.addAction(act)

        # 6. ANALYSIS & DESIGN MENU
        m_analyze = mbar.addMenu("&Analysis && Design")
        act_all = QAction("Run Full Story Analysis && ACI 318 Design (F5)", self)
        act_all.setShortcut("F5")
        act_all.triggered.connect(lambda: self.run_analyze_all_beams(switch_to_tab=1))
        m_analyze.addAction(act_all)

        act_rc_tab = QAction("Open Beam R.C. Design & Longitudinal Section (Tab 3)", self)
        act_rc_tab.triggered.connect(lambda: self.run_analyze_all_beams(switch_to_tab=2))
        m_analyze.addAction(act_rc_tab)

        act_sched_tab = QAction("Open Schedules & Calculation Report (Tab 4)", self)
        act_sched_tab.triggered.connect(lambda: self.run_analyze_all_beams(switch_to_tab=3))
        m_analyze.addAction(act_sched_tab)

        m_analyze.addSeparator()
        act_slab_rib = QAction("Open Hollow-Block Slab Rib Design && Cross-Section...", self)
        act_slab_rib.triggered.connect(lambda: self.open_slab_rib_design_dialog())
        m_analyze.addAction(act_slab_rib)

        # 7. OPTIONS MENU (Startup Defaults & Materials/Hollow-Block Slab Options)
        m_options = mbar.addMenu("&Options")
        act_opt_start = QAction("Startup Defaults (Projects Folder & Rebar Table)...", self)
        act_opt_start.triggered.connect(self.open_startup_defaults_dialog)
        m_options.addAction(act_opt_start)

        act_opt_mat = QAction("Materials && Hollow-Block Slab Options...", self)
        act_opt_mat.triggered.connect(self.open_studio_options_dialog)
        m_options.addAction(act_opt_mat)
        act_proj_data = QAction("Project Data (Stories, Heights & Materials)...", self)
        act_proj_data.triggered.connect(self.open_project_data_dialog)
        m_options.addAction(act_proj_data)

    def _build_separated_toolbars(self) -> None:
        # ======================================================================
        # TOP ROW 1: Project File Actions + Undo/Redo + Story Selector + 4 Workspaces + Run Analysis
        # ======================================================================
        self.top_tb = QToolBar("Project & Workspace Toolbar", self)
        self.top_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.top_tb)

        for lbl, slot in [
            ("New Project", self.open_new_project_dialog),
            (f"Open (*{MASTER_FILE_EXT})", self.open_existing_project_file_dialog),
            ("Import Arch .DXF", self.import_arch_dxf_for_current_story),
            ("Save && Sync (Ctrl+S)", self.save_and_sync_current_story),
            ("Options", self.open_studio_options_dialog),
            ("↶ Undo", self.undo_action),
            ("↷ Redo", self.redo_action),
        ]:
            b = QPushButton(lbl)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(slot)
            self.top_tb.addWidget(b)
        self.top_tb.addSeparator()

        self.top_tb.addWidget(QLabel(" Story: "))
        self.cb_story = QComboBox()
        self.cb_story.setMinimumWidth(190)
        self.cb_story.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_story.currentIndexChanged.connect(self._on_story_changed)
        self.top_tb.addWidget(self.cb_story)
        self.top_tb.addSeparator()

        self.view_btn_group = QButtonGroup(self)
        self.view_btn_group.setExclusive(True)
        for idx, m_label in enumerate([
            "1. 2D Structural Drawing",
            "2. Beam Analysis (Loads, SFD & BMD)",
            "3. Beam R.C. Design & Elevation",
            "4. Schedules & Report",
        ]):
            b = QPushButton(m_label)
            b.setCheckable(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if idx == 0:
                b.setChecked(True)
            b.setStyleSheet(
                "QPushButton { padding: 4px 10px; font-weight: bold; border: 1px solid #94A3B8; background: #E2E8F0; color: #0F172A; border-radius: 3px; } "
                "QPushButton:checked { background: #0284C7; color: #FFFFFF; border-color: #0369A1; }"
            )
            b.clicked.connect(lambda checked=False, i=idx: self.switch_workspace_mode(i))
            self.view_btn_group.addButton(b, idx)
            self.top_tb.addWidget(b)

        self.top_tb.addSeparator()
        btn_run_all = QPushButton("Run Analysis && Design (F5)")
        btn_run_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_run_all.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px;")
        btn_run_all.clicked.connect(lambda: self.run_analyze_all_beams(switch_to_tab=1))
        self.top_tb.addWidget(btn_run_all)

        # ======================================================================
        # TOP ROW 2 (Context-Specific for 2D Drawing Mode ONLY):
        #   - Dedicated ZOOM Toolbar
        #   - Dedicated MODIFY Toolbar
        #   - Dedicated DIMENSIONS Toolbar
        # ======================================================================
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        # 1. Dedicated ZOOM Toolbar
        self.zoom_tb = QToolBar("Zoom & Navigation Toolbar", self)
        self.zoom_tb.setStyleSheet("QToolBar { spacing: 4px; padding: 2px 6px; background: #F1F5F9; }")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.zoom_tb)
        lbl_z = QLabel(" VIEW / ZOOM: ")
        lbl_z.setStyleSheet("font-weight: bold; color: #0284C7;")
        self.zoom_tb.addWidget(lbl_z)
        for lbl, tid in [
            ("Zoom Window", "ZOOM_WINDOW"),
            ("Zoom Extents", "ZOOM_EXTENTS"),
            ("Pan (Hand)", "PAN"),
            ("Zoom In (+)", "ZOOM_IN"),
            ("Zoom Out (-)", "ZOOM_OUT"),
        ]:
            btn = QPushButton(lbl)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet("padding: 3px 8px; font-weight: bold;")
            btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            self.zoom_tb.addWidget(btn)

        # 2. Dedicated MODIFY Toolbar (Includes Convert Beam Hidden<->Drop, Flip Slab Rib & Slab Rib Design)
        self.modify_tb = QToolBar("Modify Toolbar", self)
        self.modify_tb.setStyleSheet("QToolBar { spacing: 4px; padding: 2px 6px; background: #F1F5F9; }")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.modify_tb)
        lbl_m = QLabel(" MODIFY: ")
        lbl_m.setStyleSheet("font-weight: bold; color: #0D9488;")
        self.modify_tb.addWidget(lbl_m)
        for lbl, tid in [
            ("Select / Box", "SELECT"),
            ("Convert Beam (Hid↔Drop)", "CONVERT_BEAM_KIND"),
            ("Flip Slab Rib (0°↔90°)", "FLIP_SLAB_RIB_NOW"),
            ("Slab Rib Design", "SLAB_RIB_DESIGN_DLG"),
            ("Align Face (AL)", "ALIGN_ELEMENT"),
            ("Move: Pt->Pt (MV)", "MOVE_ELEMENT"),
            ("Move: ΔX, ΔY", "MOVE_NUMERIC_DLG"),
            ("Rotate Col 90° (R)", "ROTATE_COL"),
            ("Delete (Del)", "DELETE_SELECTED"),
        ]:
            btn = QPushButton(lbl)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if tid == "DELETE_SELECTED":
                btn.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold; padding: 3px 8px;")
                btn.clicked.connect(self.delete_selected_object)
            elif tid == "ALIGN_ELEMENT":
                btn.setStyleSheet("background-color: #0D9488; color: white; font-weight: bold; padding: 3px 8px;")
                btn.clicked.connect(lambda: self.activate_cad_tool("ALIGN_ELEMENT"))
            elif tid == "CONVERT_BEAM_KIND":
                btn.setStyleSheet("background-color: #E0F2FE; color: #0369A1; border: 1px solid #0284C7; font-weight: bold; padding: 3px 8px;")
                btn.clicked.connect(self.convert_selected_beam_kind)
                self._slab_only_widgets.append(btn)
            elif tid == "FLIP_SLAB_RIB_NOW":
                btn.setStyleSheet("background-color: #FEF3C7; color: #92400E; border: 1px solid #D97706; font-weight: bold; padding: 3px 8px;")
                btn.clicked.connect(self.flip_selected_or_pick_slab_rib)
                self._slab_only_widgets.append(btn)
            elif tid == "SLAB_RIB_DESIGN_DLG":
                btn.setStyleSheet("background-color: #DCFCE7; color: #166534; border: 1px solid #16A34A; font-weight: bold; padding: 3px 8px;")
                btn.clicked.connect(lambda: self.open_slab_rib_design_dialog())
                self._slab_only_widgets.append(btn)
            elif tid == "MOVE_NUMERIC_DLG":
                btn.setStyleSheet("padding: 3px 8px; font-weight: bold;")
                btn.clicked.connect(self.open_numeric_move_dialog)
            elif tid == "ROTATE_COL":
                btn.setStyleSheet("padding: 3px 8px; font-weight: bold;")
                btn.clicked.connect(self.rotate_selected_or_default_column)
            else:
                btn.setStyleSheet("padding: 3px 8px; font-weight: bold;")
                btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            self.modify_tb.addWidget(btn)

        # 3. Dedicated DIMENSIONS Toolbar
        self.dim_tb = QToolBar("Dimensions Toolbar", self)
        self.dim_tb.setStyleSheet("QToolBar { spacing: 4px; padding: 2px 6px; background: #F1F5F9; }")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.dim_tb)
        lbl_d = QLabel(" DIMENSIONS: ")
        lbl_d.setStyleSheet("font-weight: bold; color: #7C3AED;")
        self.dim_tb.addWidget(lbl_d)
        for lbl, tid in [
            ("Linear Dim", "DIM_LINEAR"),
            ("Aligned Dim", "DIM_ALIGNED"),
            ("Auto Exterior Dims", "DIM_AUTO_EXTERIOR"),
            ("Measure (DI)", "MEASURE_DIST"),
            ("Clear Dims", "DIM_CLEAR_ALL"),
        ]:
            btn = QPushButton(lbl)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet("padding: 3px 8px; font-weight: bold;")
            btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            self.dim_tb.addWidget(btn)

        # ======================================================================
        # 4. Dedicated DRAW Toolbar (Left Vertical Dock — Shown ONLY in 2D Drawing Mode!)
        # ======================================================================
        self.draw_tb = QToolBar("Draw Structural Elements Toolbar", self)
        self.draw_tb.setOrientation(Qt.Orientation.Vertical)
        self.draw_tb.setStyleSheet("QToolBar { spacing: 5px; padding: 6px 4px; background: #F1F5F9; }")
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.draw_tb)

        lbl_draw_hdr = QLabel(" DRAW TOOLS")
        lbl_draw_hdr.setStyleSheet("font-weight: bold; color: #0284C7; padding: 4px 2px;")
        self.draw_tb.addWidget(lbl_draw_hdr)

        slab_only_draw_tids = {"DRAW_SLAB_EDGE", "DRAW_BEAM_HID", "PICK_SLAB", "FLIP_RIB", "PICK_OPENING", "DRAW_OPENING", "AUTO_FILL_SLABS"}
        for label, tid in [
            ("1. Boundary Polyline", "DRAW_SLAB_EDGE"),
            ("2. Place Column", "DRAW_COL"),
            ("3A. + Hidden Beam", "DRAW_BEAM_HID"),
            ("3B. + Drop Beam", "DRAW_BEAM_DROP"),
            ("4A. Pick: Slab", "PICK_SLAB"),
            ("4B. Pick: Flip Rib", "FLIP_RIB"),
            ("4C. Pick: Opening", "PICK_OPENING"),
            ("4D. Draw Opening [Rect/Poly]", "DRAW_OPENING"),
            ("Auto-Fill All Slabs", "AUTO_FILL_SLABS"),
            ("Convert Arch Cols", "CONVERT_ARCH_COLS"),
            ("Demo Layout", "LOAD_TEMPLATE"),
        ]:
            btn = QPushButton(label)
            btn.setMinimumHeight(30)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if tid == "AUTO_FILL_SLABS":
                btn.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold;")
            elif tid == "DRAW_OPENING":
                btn.setStyleSheet("background-color: #FDF2F8; color: #BE185D; border: 1px solid #F472B6; font-weight: bold;")
            self.draw_tb.addWidget(btn)
            btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            if tid in slab_only_draw_tids:
                self._slab_only_widgets.append(btn)

    def _build_main_workspace(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setSpacing(3)
        vbox.setContentsMargins(4, 4, 4, 4)

        # Bar 1: Clipping-Free Contextual Prompt & Column/Alignment Options Bar (Light Silver-Slate Theme)
        self.ctx_frame = QFrame()
        self.ctx_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.ctx_frame.setStyleSheet("background-color: #F1F5F9; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 3px;")
        ctx_row = QHBoxLayout(self.ctx_frame)
        ctx_row.setContentsMargins(8, 3, 8, 3)
        ctx_row.setSpacing(8)

        self.lbl_ctx_prompt = QLabel(
            "Ready (SELECT): Click element to select, Right-click to inspect, or use Modify toolbar."
        )
        self.lbl_ctx_prompt.setStyleSheet("color: #0369A1; font-weight: bold; border: none;")
        self.lbl_ctx_prompt.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_ctx_prompt.setMinimumWidth(240)
        ctx_row.addWidget(self.lbl_ctx_prompt, 1)

        ctx_row.addWidget(QLabel("Col Section [Space]:"))
        self.cb_col_orient = QComboBox()
        self.cb_col_orient.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_col_orient.addItems(["Vertical (0.20×0.40m)", "Horizontal (0.40×0.20m)"])
        self.cb_col_orient.currentIndexChanged.connect(lambda _: self.cad_canvas.render_story(self.current_story_data) if hasattr(self, "cad_canvas") else None)
        ctx_row.addWidget(self.cb_col_orient)

        ctx_row.addWidget(QLabel("Edge Rule:"))
        self.cb_col_boundary_rule = QComboBox()
        self.cb_col_boundary_rule.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_col_boundary_rule.addItems(["Clamp Inside Edge", "Expand Boundary"])
        ctx_row.addWidget(self.cb_col_boundary_rule)

        ctx_row.addWidget(QLabel("Align Pref:"))
        self.cb_align_face_mode = QComboBox()
        self.cb_align_face_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_align_face_mode.addItems(["Auto (Clicked Face)", "Outer/Inner Face", "Centerline"])
        ctx_row.addWidget(self.cb_align_face_mode)
        vbox.addWidget(self.ctx_frame)

        # Bar 2: ACI 318 Thickness & Layer Visibility Bar (Light Silver-Slate Theme)
        self.thick_frame = QFrame()
        self.thick_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.thick_frame.setStyleSheet("background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 3px;")
        thick_row = QHBoxLayout(self.thick_frame)
        thick_row.setContentsMargins(8, 2, 8, 2)
        thick_row.setSpacing(6)

        self.lbl_calc_thick = QLabel("Calculated Min. Thickness: --")
        self.lbl_calc_thick.setStyleSheet("font-weight: bold; color: #0284C7; border: none;")
        self.lbl_gov_member = QLabel("Governing Member: None")
        self.lbl_gov_member.setStyleSheet("color: #334155; font-weight: bold; border: none;")
        self.lbl_gov_member.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_gov_member.setMinimumWidth(180)

        self.sp_adopted_thick = QDoubleSpinBox()
        self.sp_adopted_thick.setRange(14.0, 100.0)
        self.sp_adopted_thick.setValue(30.0)
        self.sp_adopted_thick.setSuffix(" cm")

        self.btn_apply_thick = QPushButton("Apply Thickness")
        self.btn_apply_thick.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_apply_thick.clicked.connect(self.apply_story_thickness)
        self._slab_only_widgets.extend([self.sp_adopted_thick, self.btn_apply_thick])

        self.btn_smart_opt = QPushButton("Convert Critical Hidden Beam to Drop Beam")
        self.btn_smart_opt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_smart_opt.setStyleSheet("background-color: #F59E0B; color: black; font-weight: bold;")
        self.btn_smart_opt.setVisible(False)
        self.btn_smart_opt.clicked.connect(self.convert_critical_beam_to_drop)

        thick_row.addWidget(self.lbl_calc_thick)
        thick_row.addWidget(self.lbl_gov_member, 1)
        thick_row.addWidget(self.btn_smart_opt)
        thick_row.addWidget(QLabel("Slab Thickness:"))
        thick_row.addWidget(self.sp_adopted_thick)
        thick_row.addWidget(self.btn_apply_thick)
        thick_row.addSpacing(8)

        thick_row.addWidget(QLabel("Layers:"))
        self.chk_layer_arch = QCheckBox("Arch DXF")
        self.chk_layer_arch.setChecked(True)
        self.chk_layer_arch.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_arch)

        self.chk_layer_cols = QCheckBox("Cols")
        self.chk_layer_cols.setChecked(True)
        self.chk_layer_cols.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_cols)

        self.chk_layer_beams = QCheckBox("Beams")
        self.chk_layer_beams.setChecked(True)
        self.chk_layer_beams.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_beams)

        self.chk_layer_slabs = QCheckBox("Slabs")
        self.chk_layer_slabs.setChecked(True)
        self.chk_layer_slabs.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_slabs)
        self._slab_only_widgets.append(self.chk_layer_slabs)

        self.chk_layer_dims = QCheckBox("Dims")
        self.chk_layer_dims.setChecked(True)
        self.chk_layer_dims.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_dims)

        self.chk_layer_tags = QCheckBox("Tags")
        self.chk_layer_tags.setChecked(True)
        self.chk_layer_tags.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_tags)
        vbox.addWidget(self.thick_frame)

        # Central 4-Workspace Stack
        self.stack = QStackedWidget()
        vbox.addWidget(self.stack, 1)

        # Workspace 0: 2D Structural Drawing
        self.cad_canvas = StructuralCadCanvas2D(self)
        self.stack.addWidget(self.cad_canvas)

        # Workspace 1: Classic Xpert Beam Analysis (Loads, Reactions, SFD & BMD)
        self.beam_diagrams_view = BeamDiagramsViewWidget(self)
        self.stack.addWidget(self.beam_diagrams_view)

        # Workspace 2: Beam R.C. Design & Longitudinal Section Elevation
        self.beam_design_view = BeamDesignDetailWidget(self)
        self.stack.addWidget(self.beam_design_view)

        # Workspace 3: Schedules (Beams Schedule, Columns Schedule) & Printable Report
        self.schedules_view = SchedulesAndReportsWidget(self)
        self.tbl_columns = self.schedules_view.tbl_columns
        self.report_browser = self.schedules_view.report_browser
        self.stack.addWidget(self.schedules_view)

        # Bar 3: Upgraded AutoCAD/Revit Bottom Status Bar (Light Silver-Slate Theme)
        self.bot_frame = QFrame()
        self.bot_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.bot_frame.setStyleSheet("background-color: #F1F5F9; color: #0F172A; border-top: 1px solid #CBD5E1;")
        bot_row = QHBoxLayout(self.bot_frame)
        bot_row.setContentsMargins(8, 3, 8, 3)
        bot_row.setSpacing(5)

        def make_status_pill(text: str, active_bg: str, active_fg: str = "#FFFFFF") -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: #E2E8F0; color: #475569; border: 1px solid #94A3B8; "
                f"border-radius: 4px; padding: 3px 8px; font-weight: bold; font-size: 11px; }} "
                f"QPushButton:checked {{ background-color: {active_bg}; color: {active_fg}; border-color: #0F172A; }}"
            )
            btn.toggled.connect(self._on_bottom_snap_settings_changed)
            return btn

        self.btn_osnap_master = make_status_pill("OSNAP [F3]", "#D97706")
        bot_row.addWidget(self.btn_osnap_master)

        self.btn_osnap_end = make_status_pill("End", "#0284C7")
        bot_row.addWidget(self.btn_osnap_end)

        self.btn_osnap_mid = make_status_pill("Mid", "#0284C7")
        bot_row.addWidget(self.btn_osnap_mid)

        self.btn_osnap_cen = make_status_pill("Cen", "#0284C7")
        bot_row.addWidget(self.btn_osnap_cen)

        self.btn_osnap_perp = make_status_pill("Perp", "#0284C7")
        bot_row.addWidget(self.btn_osnap_perp)

        self.btn_ortho_bar = make_status_pill("ORTHO [F8]", "#0891B2")
        bot_row.addWidget(self.btn_ortho_bar)

        self.btn_grid_snap_bar = make_status_pill("GRID 0.1m [F9]", "#16A34A")
        bot_row.addWidget(self.btn_grid_snap_bar)

        self.lbl_coords_bar = QLabel("X: 0.00, Y: 0.00 m")
        self.lbl_coords_bar.setStyleSheet("color: #0F172A; font-family: Consolas, monospace; font-size: 11px; font-weight: bold; padding-left: 6px; border: none;")
        self.lbl_coords_bar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_coords_bar.setMinimumWidth(170)
        bot_row.addWidget(self.lbl_coords_bar, 1)

        lbl_cmd = QLabel("Cmd / ΔX,ΔY:")
        lbl_cmd.setStyleSheet("color: #0369A1; font-weight: bold; border: none;")
        bot_row.addWidget(lbl_cmd)

        self.ed_command_input = QLineEdit()
        self.ed_command_input.setPlaceholderText("e.g. 0.50, 0.00 or AL / MV / DI")
        self.ed_command_input.setFixedWidth(185)
        self.ed_command_input.setStyleSheet("background-color: #FFFFFF; color: #0F172A; padding: 3px 6px; border: 1px solid #94A3B8;")
        self.ed_command_input.returnPressed.connect(self.execute_bottom_command_or_numeric_input)
        bot_row.addWidget(self.ed_command_input)

        btn_exec_cmd = QPushButton("Apply")
        btn_exec_cmd.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_exec_cmd.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 3px 10px;")
        btn_exec_cmd.clicked.connect(self.execute_bottom_command_or_numeric_input)
        bot_row.addWidget(btn_exec_cmd)

        vbox.addWidget(self.bot_frame)
        self.setStatusBar(QStatusBar())

    def update_contextual_prompt(self, message: str) -> None:
        self.lbl_ctx_prompt.setText(message)
        self.statusBar().showMessage(message)

    def _on_bottom_snap_settings_changed(self) -> None:
        self.cad_canvas.osnap_enabled = self.btn_osnap_master.isChecked()
        self.cad_canvas.osnap_modes["ENDPOINT"] = self.btn_osnap_end.isChecked()
        self.cad_canvas.osnap_modes["MIDPOINT"] = self.btn_osnap_mid.isChecked()
        self.cad_canvas.osnap_modes["CENTER"] = self.btn_osnap_cen.isChecked()
        self.cad_canvas.osnap_modes["PERPENDICULAR"] = self.btn_osnap_perp.isChecked()
        self.cad_canvas.ortho_enabled = self.btn_ortho_bar.isChecked()
        self.cad_canvas.grid_snap_enabled = self.btn_grid_snap_bar.isChecked()

    def undo_action(self) -> None:
        if not self._undo_stack:
            self.update_contextual_prompt("Undo (Ctrl+Z): Nothing to undo on active story.")
            return
        cur_snap = json.dumps(self.current_story_data, sort_keys=True)
        self._redo_stack.append(cur_snap)
        prev_snap = self._undo_stack.pop()
        self.current_story_data = json.loads(prev_snap)
        self._last_saved_snapshot = prev_snap
        self.save_and_sync_current_story(record_undo=False)
        self.refresh_story_ui()
        self.update_contextual_prompt(f"Undo complete ({len(self._undo_stack)} undo steps remaining).")

    def redo_action(self) -> None:
        if not self._redo_stack:
            self.update_contextual_prompt("Redo (Ctrl+Y): Nothing to redo on active story.")
            return
        cur_snap = json.dumps(self.current_story_data, sort_keys=True)
        self._undo_stack.append(cur_snap)
        next_snap = self._redo_stack.pop()
        self.current_story_data = json.loads(next_snap)
        self._last_saved_snapshot = next_snap
        self.save_and_sync_current_story(record_undo=False)
        self.refresh_story_ui()
        self.update_contextual_prompt(f"Redo complete ({len(self._redo_stack)} redo steps remaining).")

    def convert_selected_beam_kind(self) -> None:
        """
        Bidirectionally converts selected beam(s) between Hidden Beam and Drop Beam.
        Enforces v1.9.0 structural hierarchy rule: prevents Drop Beam resting on Hidden Beam!
        """
        if self.is_tie_beams_story():
            QMessageBox.warning(
                self,
                "Tie-Beams Story Rule",
                "All Tie-Beams / Grade Beams must remain Drop / Rectangular Beams (0.20×0.50m). Hidden beams are disabled on this story.",
            )
            return
        beam_ids = [eid for kind, eid in self.cad_canvas.selected_items if kind == "beam"]
        if not beam_ids:
            self.update_contextual_prompt(
                "Convert Beam (Hidden ↔ Drop): Select one or more Beams (B#) on the canvas first, then click Convert Beam."
            )
            return
        last_msg = ""
        converted = 0
        for bid in beam_ids:
            bm_obj = next((b for b in self.current_story_data.get("beams", []) if str(b.get("id")) == str(bid)), None)
            if bm_obj is None:
                continue
            cur_kind = str(bm_obj.get("beam_kind", bm_obj.get("kind", "hidden"))).lower()
            target_kind = "hidden" if "drop" in cur_kind else "drop"
            ok, msg = convert_beam_kind_and_section(self.current_story_data, str(bid), target_kind)
            if ok:
                converted += 1
                last_msg = msg
            else:
                QMessageBox.warning(self, "Structural Hierarchy Rule", msg)
                self.update_contextual_prompt(msg)
        if converted > 0:
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt(last_msg)

    def flip_selected_or_pick_slab_rib(self) -> None:
        """
        Flips the exact selected slab(s) by ID if any slab is selected (Upgrade #7);
        otherwise activates the interactive `FLIP_RIB` pick tool.
        """
        slab_ids = [eid for kind, eid in self.cad_canvas.selected_items if kind == "slab"]
        if slab_ids:
            last_msg = ""
            flipped_any = False
            for sid in slab_ids:
                ok, msg, _ = flip_slab_rib_by_id(self.current_story_data, str(sid))
                if ok:
                    flipped_any = True
                    last_msg = msg
                elif msg:
                    QMessageBox.warning(self, "Cantilever & Back-Span Slab Equilibrium Rule", msg)
            if flipped_any:
                self.save_and_sync_current_story()
                self.refresh_story_ui()
                self.update_contextual_prompt(last_msg)
            return
        self.activate_cad_tool("FLIP_RIB")

    def toggle_selected_beam_wall_load(self) -> None:
        beam_ids = [eid for kind, eid in self.cad_canvas.selected_items if kind == "beam"]
        if not beam_ids:
            self.update_contextual_prompt("Select a Beam (B#) on the canvas first to toggle its Masonry Wall Load.")
            return
        for bid in beam_ids:
            bm_obj = next((b for b in self.current_story_data.get("beams", []) if str(b.get("id")) == str(bid)), None)
            if bm_obj is not None:
                flags = ensure_beam_wall_flags(self.current_story_data, bm_obj)
                new_state = not bool(bm_obj.get("has_wall_load", True))
                for k in list(flags.keys()):
                    flags[k] = new_state
                bm_obj["has_wall_load"] = new_state
        self.save_and_sync_current_story()
        self.refresh_story_ui()
        self.update_contextual_prompt(f"Toggled Masonry Wall Load on {', '.join(beam_ids)}.")

    def execute_bottom_command_or_numeric_input(self) -> None:
        raw = self.ed_command_input.text().strip()
        if not raw:
            return
        self.ed_command_input.clear()
        upper = raw.upper()

        if upper in ("U", "UNDO"):
            self.undo_action()
            return
        if upper in ("REDO",):
            self.redo_action()
            return
        if upper in ("AL", "ALIGN"):
            self.activate_cad_tool("ALIGN_ELEMENT")
            return
        if upper in ("MV", "MOVE"):
            self.activate_cad_tool("MOVE_ELEMENT")
            return
        if upper in ("DI", "DIST", "MEASURE"):
            self.activate_cad_tool("MEASURE_DIST")
            return
        if upper in ("DLI", "DIM"):
            self.activate_cad_tool("DIM_LINEAR")
            return
        if upper in ("DAL",):
            self.activate_cad_tool("DIM_ALIGNED")
            return
        if upper in ("DEL", "DELETE", "E", "ERASE"):
            self.delete_selected_object()
            return
        if upper in ("R", "ROT", "ROTATE"):
            self.rotate_selected_or_default_column()
            return

        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        if len(parts) == 2:
            try:
                v1, v2 = float(parts[0]), float(parts[1])
            except ValueError:
                self.update_contextual_prompt(f"Invalid numeric input: '{raw}'. Enter ΔX, ΔY (e.g. 0.40, 0.00).")
                return

            if self.cad_canvas.active_tool == "MOVE_ELEMENT" or self.cad_canvas.selected_items:
                boundary_mode = "clamp" if self.cb_col_boundary_rule.currentIndex() == 0 else "expand"
                _, msg = move_selected_elements_by_delta(
                    self.current_story_data, self.cad_canvas.selected_items, v1, v2, boundary_mode=boundary_mode
                )
                self.cad_canvas._first_click_pt = None
                self.save_and_sync_current_story()
                self.refresh_story_ui()
                self.update_contextual_prompt(msg)
                return

            self.cad_canvas._handle_left_click_at(v1, v2, v1, v2, "NUMERIC")
            return

        if len(parts) == 1:
            try:
                length_val = float(parts[0])
            except ValueError:
                self.update_contextual_prompt(f"Unrecognized command or number: '{raw}'.")
                return
            ref_pt = None
            if self.cad_canvas.active_tool == "DRAW_SLAB_EDGE" and self.cad_canvas._polyline_pts:
                ref_pt = self.cad_canvas._polyline_pts[-1]
            elif self.cad_canvas._first_click_pt is not None:
                ref_pt = self.cad_canvas._first_click_pt
            if ref_pt and self.cad_canvas._current_snap_info:
                tx, ty = self.cad_canvas._current_snap_info["x"], self.cad_canvas._current_snap_info["y"]
                dx, dy = tx - ref_pt[0], ty - ref_pt[1]
                cur_len = math.hypot(dx, dy)
                if cur_len > 1e-6:
                    nx, ny = round(ref_pt[0] + (dx / cur_len) * length_val, 3), round(ref_pt[1] + (dy / cur_len) * length_val, 3)
                else:
                    nx, ny = round(ref_pt[0] + length_val, 3), ref_pt[1]
                self.cad_canvas._handle_left_click_at(nx, ny, nx, ny, "NUMERIC_LEN")

    def open_numeric_move_dialog(self) -> None:
        if not self.cad_canvas.selected_items:
            QMessageBox.information(
                self,
                "Move by Numeric Offset (ΔX, ΔY)",
                "Please select one or more Columns or Beams first (by clicking or dragging a selection window), then invoke Move.",
            )
            return
        dlg = MoveNumericDeltaDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dx, dy = dlg.sp_dx.value(), dlg.sp_dy.value()
            boundary_mode = "clamp" if self.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            _, msg = move_selected_elements_by_delta(
                self.current_story_data, self.cad_canvas.selected_items, dx, dy, boundary_mode=boundary_mode
            )
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt(msg)

    open_move_selected_dialog = open_numeric_move_dialog

    def _on_layer_visibility_changed(self) -> None:
        self.cad_canvas.layer_show_arch = self.chk_layer_arch.isChecked()
        self.cad_canvas.layer_show_cols = self.chk_layer_cols.isChecked()
        self.cad_canvas.layer_show_beams = self.chk_layer_beams.isChecked()
        self.cad_canvas.layer_show_slabs = self.chk_layer_slabs.isChecked()
        self.cad_canvas.layer_show_dims = self.chk_layer_dims.isChecked()
        self.cad_canvas.layer_show_tags = self.chk_layer_tags.isChecked()
        self.cad_canvas.render_story(self.current_story_data)

    def import_arch_dxf_for_current_story(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Architectural .DXF Plan as Locked Block for Current Story",
            os.path.abspath("."),
            "AutoCAD DXF Files (*.dxf);;All Files (*)",
        )
        if not fpath or not os.path.isfile(fpath):
            return
        try:
            arch_block = import_arch_dxf_underlay(fpath)
            self.current_story_data["arch_underlay_block"] = arch_block
            self.chk_layer_arch.setChecked(True)
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.cad_canvas.zoom_extents()
            self.update_contextual_prompt(
                f"Imported Architectural DXF '{arch_block['source_file']}' ({len(arch_block['segments'])} segments) as Locked Block."
            )
        except Exception as exc:
            QMessageBox.critical(self, "DXF Import Error", str(exc))

    def rotate_selected_or_default_column(self) -> None:
        col_ids = [eid for kind, eid in self.cad_canvas.selected_items if kind == "column"]
        if col_ids:
            boundary_mode = "clamp" if self.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            last_msg = ""
            for cid in col_ids:
                ok, msg = rotate_column_90_deg(self.current_story_data, cid, boundary_mode=boundary_mode)
                if ok:
                    last_msg = msg
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt(last_msg or f"Rotated {len(col_ids)} column(s) by 90°.")
            return

        new_idx = 1 if self.cb_col_orient.currentIndex() == 0 else 0
        self.cb_col_orient.setCurrentIndex(new_idx)
        self.activate_cad_tool("ROTATE_COL")

    def open_new_project_dialog(self) -> bool:
        dlg = NewProjectSetupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.get_config()
            self.master_project = initialize_studio_project(cfg)
            self._populate_story_selector()
            self.switch_workspace_mode(0)
            self.update_contextual_prompt(
                f"Created Project: {self.master_project['master_file']} — Opened on 02_Ground_Floor."
            )
            return True
        return False

    def open_existing_project_file_dialog(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            f"Open Xpert Structural Master Project File (*{MASTER_FILE_EXT})",
            os.path.abspath("./XpertStudio_Projects"),
            f"Xpert Structural Project (*{MASTER_FILE_EXT});;Legacy Project Files (*.xpert *-00_Project_Master.json);;All Files (*)",
        )
        if fpath and os.path.isfile(fpath):
            self.load_project_from_file(fpath)

    def load_project_from_file(self, master_file_path: str) -> None:
        try:
            self.master_project = load_studio_project_from_master_file(master_file_path)
            self._populate_story_selector()
            self.switch_workspace_mode(0)
            self.update_contextual_prompt(
                f"Opened Existing Project: {self.master_project.get('project_name')} — Active Story: 02_Ground_Floor."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Project", str(exc))

    def delete_selected_object(self) -> None:
        if not self.cad_canvas.selected_items:
            self.update_contextual_prompt("No elements selected. Click any Column, Beam, Slab, Opening, or Dimension (or drag Window/Crossing box) then press Del.")
            return
        deleted_count = 0
        deleted_kinds = set()
        last_msg = ""
        last_err = ""
        for kind, eid in list(self.cad_canvas.selected_items):
            ok, msg = delete_selected_element_from_story(self.current_story_data, kind, eid)
            if ok:
                deleted_count += 1
                deleted_kinds.add(str(kind).lower())
                last_msg = msg
            else:
                last_err = msg
        if deleted_count == 0 and last_err:
            QMessageBox.warning(self, "Cannot Delete Element", last_err)
            return
        if "beam" in deleted_kinds:
            reconcile_and_split_slabs_after_beam_change(self.current_story_data)
        self.cad_canvas.selected_items.clear()
        self.save_and_sync_current_story()
        self.refresh_story_ui()
        self.update_contextual_prompt(last_msg if deleted_count == 1 else f"Deleted {deleted_count} selected element(s).")

    def _populate_story_selector(self) -> None:
        self.cb_story.blockSignals(True)
        self.cb_story.clear()
        start_idx = 0
        if self.master_project:
            for idx, st in enumerate(self.master_project.get("stories", [])):
                self.cb_story.addItem(st["story_label"], idx)
                if st["story_id"] == "02_Ground_Floor":
                    start_idx = idx
        self.cb_story.setCurrentIndex(start_idx)
        self.cb_story.blockSignals(False)
        self._on_story_changed(start_idx)

    def _on_story_changed(self, idx: int) -> None:
        if not self.master_project or idx < 0:
            return
        stories = self.master_project.get("stories", [])
        if idx >= len(stories):
            return
        self.current_story_index = idx
        jpath = stories[idx]["json_file"]
        if os.path.isfile(jpath):
            with open(jpath, "r", encoding="utf-8") as f:
                self.current_story_data = json.load(f)
        renumber_story_columns_sequentially(self.current_story_data)
        reconcile_all_story_beams_supports_and_spans(self.current_story_data)

        is_tie = self.is_tie_beams_story()
        if is_tie:
            # Ensure no slabs/openings or hidden beams exist on Tie-Beams story (00_TieBeams)
            self.current_story_data["slabs"] = []
            self.current_story_data["openings"] = []
            for bm in self.current_story_data.get("beams", []):
                bm["beam_kind"] = "drop"
                bm["kind"] = "drop"
                bm["width_m"] = float(bm.get("width_m", 0.20)) if float(bm.get("width_m", 0.20)) <= 0.30 else 0.20
                bm["depth_m"] = 0.40
                bm["initial_depth_m"] = 0.40
            if self.cad_canvas.active_tool in ("DRAW_SLAB_EDGE", "DRAW_BEAM_HID", "PICK_SLAB", "FLIP_RIB", "PICK_OPENING", "DRAW_OPENING"):
                self.cad_canvas.active_tool = "SELECT"
                self.cad_canvas.update_cursor_for_active_tool()

        for w in self._slab_only_widgets:
            w.setEnabled(not is_tie)

        adopted_cm = float(self.current_story_data.get("adopted_slab_thickness_cm", 30.0))
        self.sp_adopted_thick.blockSignals(True)
        self.sp_adopted_thick.setValue(adopted_cm)
        self.sp_adopted_thick.blockSignals(False)

        self._undo_stack.clear()
        self._redo_stack.clear()
        self._last_saved_snapshot = json.dumps(self.current_story_data, sort_keys=True)
        self.refresh_story_ui()
        self.cad_canvas.zoom_extents()

    def refresh_story_ui(self) -> None:
        reconcile_all_story_beams_supports_and_spans(self.current_story_data)
        self.cad_canvas.render_story(self.current_story_data)
        if self.is_tie_beams_story():
            self.lbl_calc_thick.setText("Tie-Beams Story: No Slabs / Hidden Beams")
            self.lbl_gov_member.setText("Draw Drop Tie-Beams (3B) directly between Columns without Boundary")
            self.btn_smart_opt.setVisible(False)
            return
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"]) if self.master_project else 350.0
        eval_res = evaluate_story_thickness_and_optimization(self.current_story_data, fy)
        self.lbl_calc_thick.setText(f"Calculated Min. Thickness: {eval_res['badge_text']}")
        self.lbl_gov_member.setText(f"Governing Member: {eval_res['governing_member']}")

        smart_opt = eval_res.get("smart_optimization")
        if smart_opt:
            self.btn_smart_opt.setText(f"Convert {smart_opt['beam_id']} to Drop Beam (Keep 30 cm Slab)")
            self.btn_smart_opt.setToolTip(smart_opt["message"])
            self.btn_smart_opt.setVisible(True)
        else:
            self.btn_smart_opt.setVisible(False)

    def _check_and_apply_slab_thickness(self, interactive: bool = True) -> float:
        """
        v2.0.0: Evaluates the entered slab thickness in `sp_adopted_thick` (default 30.0 cm)
        against the calculated minimum thickness from the floor plan (`calculated_min_thickness_cm`,
        always rounded UP to the nearest integer centimeter via math.ceil).
        If entered < calculated_min_thickness_cm and `interactive=True`, shows a ONE-TIME warning dialog
        giving the user two explicit choices:
          1. Continue with entered thickness -> keep entered value and record
             `thickness_warning_acknowledged_cm = entered` so the warning does NOT pop up repeatedly.
          2. Modify thickness to calculated minimum -> update spinbox & story thickness.
        Then updates `adopted_slab_thickness_cm`, hidden beam depths, and Hordi area load `Wu (m×m)`.
        """
        if self.is_tie_beams_story():
            return 30.0
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"]) if self.master_project else 350.0
        eval_res = evaluate_story_thickness_and_optimization(self.current_story_data, fy)
        entered = float(self.sp_adopted_thick.value())
        req = float(eval_res.get("calculated_min_thickness_cm", 0.0))
        ack_cm = self.current_story_data.get("thickness_warning_acknowledged_cm")
        already_acknowledged = (ack_cm is not None) and (abs(float(ack_cm) - entered) <= 1e-3)

        if (
            interactive
            and "--check" not in sys.argv
            and eval_res.get("has_data")
            and entered < req - 1e-4
            and not already_acknowledged
        ):
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Minimum Hollow-Block Slab Thickness Warning")
            msg_box.setText(
                f"Entered slab thickness ({entered:.0f} cm) is less than the calculated minimum thickness ({req:.0f} cm) "
                f"governed by member: {eval_res.get('governing_member', '')}.\n\n"
                f"Choose calculation action:"
            )
            btn_continue = msg_box.addButton(
                f"Continue with entered thickness ({entered:.0f} cm)", QMessageBox.ButtonRole.AcceptRole
            )
            btn_modify = msg_box.addButton(
                f"Adjust thickness to ({req:.0f} cm) and calculate", QMessageBox.ButtonRole.ActionRole
            )
            msg_box.setDefaultButton(btn_modify)
            msg_box.exec()
            if msg_box.clickedButton() == btn_modify:
                entered = float(math.ceil(req - 1e-6))
                self.sp_adopted_thick.blockSignals(True)
                self.sp_adopted_thick.setValue(entered)
                self.sp_adopted_thick.blockSignals(False)
                self.current_story_data["thickness_warning_acknowledged_cm"] = None
            elif msg_box.clickedButton() == btn_continue:
                # User explicitly chose to continue with this thickness — do NOT warn again for this thickness!
                self.current_story_data["thickness_warning_acknowledged_cm"] = entered

        self.current_story_data["adopted_slab_thickness_cm"] = entered
        h_m = round(entered / 100.0, 3)
        for bm in self.current_story_data.get("beams", []):
            kind_str = str(bm.get("beam_kind", bm.get("kind", "hidden"))).lower()
            if "drop" not in kind_str:
                bm["depth_m"] = h_m
        hb_src: Dict[str, Any] = {}
        if self.master_project:
            if isinstance(self.master_project.get("hollow_block_slab_options"), dict):
                hb_src.update(self.master_project["hollow_block_slab_options"])
            elif isinstance(self.master_project.get("loads_and_defaults"), dict):
                hb_src.update(self.master_project["loads_and_defaults"])
        if isinstance(self.current_story_data.get("hollow_block"), dict):
            hb_src.update(self.current_story_data["hollow_block"])
        if isinstance(self.current_story_data.get("hollow_block_slab_options"), dict):
            hb_src.update(self.current_story_data["hollow_block_slab_options"])
        std_blk_h = 20.0 if entered >= 25.0 else 16.0
        std_hs_cm = max(5.0, entered - std_blk_h)
        hb_src["total_slab_thickness_cm"] = entered
        hb_src["slab_thickness_cm"] = entered
        hb_src["h_mm"] = entered * 10.0
        hb_src["block_height_cm"] = std_blk_h
        hb_src["top_compression_slab_cm"] = std_hs_cm
        hb_src["topping_thickness_cm"] = std_hs_cm
        hb_src["top_flange_cm"] = std_hs_cm
        hb_src["hs_mm"] = std_hs_cm * 10.0
        hb_res = compute_hollow_block_parameters(hb_src)
        hb_src.update(hb_res)
        self.current_story_data["hollow_block_slab_options"] = dict(hb_src)
        self.current_story_data["hollow_block_params"] = dict(hb_res)
        self.current_story_data["hollow_block"] = dict(hb_res)
        if self.master_project is not None:
            self.master_project["hollow_block_slab_options"] = dict(hb_src)
            ld_def = self.master_project.setdefault("loads_and_defaults", {})
            ld_def["slab_factored_wu_kpa"] = float(hb_res["area_factored_qu_kn_m2"])
            ld_def["wu_rib_kn_m"] = float(hb_res["rib_factored_wu_kn_m"])
            ld_def["block_height_cm"] = std_blk_h
            ld_def["top_compression_slab_cm"] = std_hs_cm
        assump = self.current_story_data.setdefault("beam_load_assumptions", {})
        assump["slab_qu_kn_m2"] = float(hb_res["area_factored_qu_kn_m2"])
        self.current_story_data["slab_factored_wu_kpa"] = float(hb_res["area_factored_qu_kn_m2"])
        if hasattr(self, "sp_slab_qu"):
            self.sp_slab_qu.blockSignals(True)
            self.sp_slab_qu.setValue(float(hb_res["area_factored_qu_kn_m2"]))
            self.sp_slab_qu.blockSignals(False)
        return entered

    def apply_story_thickness(self) -> None:
        try:
            final_cm = self._check_and_apply_slab_thickness(interactive=True)
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            if self.current_story_data.get("beams"):
                self._solve_story_and_refresh_views()
            hb_opts = self.current_story_data.get("hollow_block_slab_options", {})
            wu_m2 = float(hb_opts.get("area_factored_qu_kn_m2", 11.71))
            wu_rib = float(hb_opts.get("rib_factored_wu_kn_m", 6.44))
            self.update_contextual_prompt(
                f"Applied Slab Thickness h = {final_cm:.1f} cm ({final_cm*10:.0f} mm) -> "
                f"Wu(rib) = {wu_rib:.2f} kN/m'/rib | Area Load Wu(m×m) = {wu_m2:.2f} kN/m²."
            )
        except Exception as exc:
            _report_studio_exception(self, "Apply Slab Thickness Error", exc)

    def open_slab_rib_design_dialog(self, initial_slab_id: Optional[str] = None) -> None:
        try:
            if self.is_tie_beams_story():
                QMessageBox.information(
                    self,
                    "Tie-Beams Story",
                    "Tie-Beams story (00_TieBeams) does not contain hollow-block slabs.",
                )
                return
            slabs = self.current_story_data.get("slabs", [])
            if not slabs:
                QMessageBox.information(
                    self,
                    "Hollow-Block Slab Rib Design",
                    "No slabs found on the active story. Click 'Auto-Fill All Slabs' or '4A. Pick: Slab' first.",
                )
                return
            if not initial_slab_id:
                sel_slabs = [eid for kind, eid in self.cad_canvas.selected_items if kind == "slab"]
                if sel_slabs:
                    initial_slab_id = str(sel_slabs[0])
            self._check_and_apply_slab_thickness(interactive=False)
            fc = float(self.master_project["materials_and_soil"]["fc_mpa"]) if self.master_project else 20.0
            fy = float(self.master_project["materials_and_soil"]["fy_mpa"]) if self.master_project else 350.0
            dlg = SlabRibDesignDialog(
                self,
                story_data=self.current_story_data,
                fc_mpa=fc,
                fy_mpa=fy,
                initial_slab_id=initial_slab_id,
            )
            dlg.exec()
            self.save_and_sync_current_story()
            self.refresh_story_ui()
        except Exception as exc:
            _report_studio_exception(self, "Hollow-Block Slab Rib Design Error", exc)

    def convert_critical_beam_to_drop(self) -> None:
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"]) if self.master_project else 350.0
        eval_res = evaluate_story_thickness_and_optimization(self.current_story_data, fy)
        smart_opt = eval_res.get("smart_optimization")
        if not smart_opt:
            return
        target_id = smart_opt["beam_id"]
        convert_beam_kind_and_section(self.current_story_data, target_id, "drop")
        self.save_and_sync_current_story()
        self.refresh_story_ui()

    def activate_cad_tool(self, tool_id: str) -> None:
        self.switch_workspace_mode(0)

        if tool_id == "FLIP_RIB":
            # Upgrade #7: If a slab is ALREADY selected, immediately flip that exact slab by ID!
            slab_ids = [eid for kind, eid in self.cad_canvas.selected_items if kind == "slab"]
            if slab_ids:
                self.flip_selected_or_pick_slab_rib()
                return

        if tool_id == "ZOOM_EXTENTS":
            self.cad_canvas.zoom_extents()
            self.update_contextual_prompt("Zoom Extents: Fitted entire structural floor plan in view.")
            return

        if tool_id == "ZOOM_IN":
            self.cad_canvas.zoom_in_step()
            return

        if tool_id == "ZOOM_OUT":
            self.cad_canvas.zoom_out_step()
            return

        if tool_id == "DIM_AUTO_EXTERIOR":
            count, msg = auto_generate_exterior_dimensions(self.current_story_data)
            self.chk_layer_dims.setChecked(True)
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt(msg)
            return

        if tool_id == "DIM_CLEAR_ALL":
            self.current_story_data["dimensions"] = []
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt("Cleared all dimension annotations on active story.")
            return

        if tool_id == "AUTO_FILL_SLABS":
            count, msg = auto_fill_all_story_slabs(self.current_story_data)
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt(msg)
            return

        if tool_id == "CONVERT_ARCH_COLS":
            arch_block = self.current_story_data.get("arch_underlay_block")
            if not isinstance(arch_block, dict) or not arch_block.get("candidate_columns"):
                QMessageBox.information(
                    self,
                    "Convert Architectural Columns",
                    "No closed column rectangles found in the active story's imported Architectural .DXF block.",
                )
                return
            cols = self.current_story_data.setdefault("columns", [])
            poly = self.current_story_data.get("slab_edge_polygon", [])
            added = 0
            for rc in arch_block["candidate_columns"]:
                if check_duplicate_column(rc["x"], rc["y"], 0.20, 0.40, cols) is None:
                    cid = f"C{len(cols) + 1}"
                    c_obj = {
                        "id": cid, "x": rc["x"], "y": rc["y"], "b_m": 0.20, "h_m": 0.40,
                        "active": True, "moves_with_grids": True, "room_bounding": True,
                    }
                    if len(poly) >= 3:
                        c_obj, poly, _ = enforce_column_inside_slab_boundary(c_obj, poly, mode="clamp")
                    cols.append(c_obj)
                    added += 1
            self.current_story_data["slab_edge_polygon"] = poly
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.update_contextual_prompt(f"Converted {added} Architectural Columns to 0.20×0.40m Structural Columns.")
            return

        if tool_id == "LOAD_TEMPLATE":
            self.current_story_data["slab_edge_polygon"] = [[0, 0], [10.0, 0], [10.0, 8.5], [0, 8.5]]
            self.current_story_data["columns"] = [
                {"id": "C1", "x": 0.10, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C2", "x": 5.20, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C3", "x": 9.90, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C4", "x": 0.10, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C5", "x": 5.20, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C6", "x": 9.90, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C7", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C8", "x": 5.20, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
                {"id": "C9", "x": 9.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True, "moves_with_grids": True, "room_bounding": True},
            ]
            self.current_story_data["beams"] = [
                {
                    "id": "B1", "beam_kind": "drop", "kind": "drop", "width_m": 0.20, "depth_m": 0.40,
                    "initial_width_m": 0.20, "initial_depth_m": 0.40, "room_bounding": True,
                    "start_x": 0.0, "start_y": 8.40, "end_x": 10.0, "end_y": 8.40,
                    "spans": [5.1, 4.7],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20, "center_coord_m": 5.20},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.20, "center_coord_m": 9.90},
                    ],
                },
                {
                    "id": "B2", "beam_kind": "hidden", "kind": "hidden", "width_m": 0.30, "depth_m": 0.30,
                    "initial_width_m": 0.30, "initial_depth_m": 0.30, "room_bounding": True,
                    "start_x": 0.0, "start_y": 4.20, "end_x": 10.0, "end_y": 4.20,
                    "spans": [5.1, 4.7],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.20, "center_coord_m": 5.20},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.20, "center_coord_m": 9.90},
                    ],
                },
                {
                    "id": "B3", "beam_kind": "drop", "kind": "drop", "width_m": 0.20, "depth_m": 0.40,
                    "initial_width_m": 0.20, "initial_depth_m": 0.40, "room_bounding": True,
                    "start_x": 0.0, "start_y": 0.10, "end_x": 10.0, "end_y": 0.10,
                    "spans": [5.1, 4.7],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C7", "width_m": 0.20, "center_coord_m": 0.10},
                        {"support_index": 2, "kind": "column", "target_id": "C8", "width_m": 0.20, "center_coord_m": 5.20},
                        {"support_index": 3, "kind": "column", "target_id": "C9", "width_m": 0.20, "center_coord_m": 9.90},
                    ],
                },
                {
                    "id": "B4", "beam_kind": "drop", "kind": "drop", "width_m": 0.20, "depth_m": 0.40,
                    "initial_width_m": 0.20, "initial_depth_m": 0.40, "room_bounding": True,
                    "start_x": 0.10, "start_y": 0.0, "end_x": 0.10, "end_y": 8.5,
                    "spans": [4.0, 4.1],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C7", "width_m": 0.40, "center_coord_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C4", "width_m": 0.40, "center_coord_m": 4.20},
                        {"support_index": 3, "kind": "column", "target_id": "C1", "width_m": 0.40, "center_coord_m": 8.30},
                    ],
                },
                {
                    "id": "B5", "beam_kind": "hidden", "kind": "hidden", "width_m": 0.30, "depth_m": 0.30,
                    "initial_width_m": 0.30, "initial_depth_m": 0.30, "room_bounding": True,
                    "start_x": 5.20, "start_y": 0.0, "end_x": 5.20, "end_y": 8.5,
                    "spans": [4.0, 4.1],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C8", "width_m": 0.40, "center_coord_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.40, "center_coord_m": 4.20},
                        {"support_index": 3, "kind": "column", "target_id": "C2", "width_m": 0.40, "center_coord_m": 8.30},
                    ],
                },
                {
                    "id": "B6", "beam_kind": "drop", "kind": "drop", "width_m": 0.20, "depth_m": 0.40,
                    "initial_width_m": 0.20, "initial_depth_m": 0.40, "room_bounding": True,
                    "start_x": 9.90, "start_y": 0.0, "end_x": 9.90, "end_y": 8.5,
                    "spans": [4.0, 4.1],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C9", "width_m": 0.40, "center_coord_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C6", "width_m": 0.40, "center_coord_m": 4.20},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.40, "center_coord_m": 8.30},
                    ],
                },
            ]
            self.current_story_data["slabs"] = []
            self.current_story_data["openings"] = []
            auto_fill_all_story_slabs(self.current_story_data)
            auto_generate_exterior_dimensions(self.current_story_data)
            self.cad_canvas.active_tool = "SELECT"
            self.cad_canvas.update_cursor_for_active_tool()
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.cad_canvas.zoom_extents()
            return

        self.cad_canvas.active_tool = tool_id
        self.cad_canvas._polyline_pts.clear()
        self.cad_canvas._opening_poly_pts.clear()
        self.cad_canvas._first_click_pt = None
        self.cad_canvas._align_ref = None
        self.cad_canvas._measure_pts.clear()
        self.cad_canvas._is_zoom_window_dragging = False
        self.cad_canvas.update_cursor_for_active_tool()
        self.cad_canvas.render_story(self.current_story_data)

        prompts = {
            "SELECT": "SELECT Mode: Click any element (Right-Click to Inspect in Analysis/Design), or drag Window (Blue) / Crossing (Green).",
            "ZOOM_WINDOW": "Zoom Window: Click and drag a rectangle over the area you want to zoom into.",
            "PAN": "Pan Mode (Hand): Click and drag anywhere on the canvas to pan smoothly in any direction.",
            "ROTATE_COL": "Rotate Column 90° [R]: Click directly on any Column (C#) on the canvas to rotate it 90°.",
            "ALIGN_ELEMENT": "Align [AL] — Step 1: Click the fixed Reference Edge (Boundary, Column/Beam Face, or Arch Line).",
            "MOVE_ELEMENT": "Move [MV]: Click Base Reference Point -> Click Second Target Point (or type ΔX, ΔY below).",
            "DIM_LINEAR": "Linear Dimension [DLI]: Click First Point -> Click Second Point to place horizontal/vertical dimension.",
            "DIM_ALIGNED": "Aligned Dimension [DAL]: Click First Point -> Click Second Point to place aligned dimension.",
            "MEASURE_DIST": "Measure [DI]: Click First Point -> Click Second Point to measure L, ΔX, ΔY, and Angle.",
            "DRAW_SLAB_EDGE": "Step 1 (Boundary Polyline): Click vertices around the building perimeter.",
            "DRAW_COL": "Step 2 (Place Column): Move cursor to preview column, press [Space] to flip orientation, click to place.",
            "DRAW_BEAM_HID": "Step 3A (Hidden Beam 0.30m): Click Start Column Center -> Click End Column Center.",
            "DRAW_BEAM_DROP": "Step 3B (Drop Beam 0.20×0.40m): Click Start Column Center -> Click End Column Center.",
            "PICK_SLAB": "Step 4A (Pick Slab): Click inside any beam-bounded bay to create/update its Hollow-Block Slab.",
            "FLIP_RIB": "Step 4B (Flip Rib): Click inside any Slab or on its yellow tag to flip its rib orientation (0° <-> 90°).",
            "PICK_OPENING": "Step 4C (Pick Opening): Click inside any bay to toggle a Void Opening (X).",
            "DRAW_OPENING": "Step 4D (Draw Slab Opening): Click 2 opposite corners (Rectangle) or press [Space] for Polyline Loop (auto-merges adjacent openings).",
        }
        self.update_contextual_prompt(prompts.get(tool_id, f"Activated Tool: {tool_id}"))

    def save_and_sync_current_story(self, record_undo: bool = True) -> None:
        if not self.master_project:
            return
        new_snap = json.dumps(self.current_story_data, sort_keys=True)
        if record_undo and self._last_saved_snapshot is not None and new_snap != self._last_saved_snapshot:
            self._undo_stack.append(self._last_saved_snapshot)
            if len(self._undo_stack) > 40:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
        self._last_saved_snapshot = new_snap

        st_meta = self.master_project["stories"][self.current_story_index]
        jpath = st_meta["json_file"]
        dpath = st_meta["dxf_file"]
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(self.current_story_data, f, indent=2)
        sync_story_to_dxf(self.current_story_data, dpath)
        if st_meta["story_id"] == "02_Ground_Floor":
            propagate_ground_columns_to_all_stories(
                self.master_project, self.current_story_data.get("columns", [])
            )

    def _solve_story_and_refresh_views(self, select_beam_id: Optional[str] = None) -> bool:
        if not self.master_project:
            return False
        beams = self.current_story_data.get("beams", [])
        if not beams:
            return False
        fc = float(self.master_project["materials_and_soil"]["fc_mpa"])
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"])
        self.last_analysis_bundle = analyze_all_story_beams_and_columns(self.current_story_data, fc, fy)

        self.beam_diagrams_view.populate_results(self.current_story_data, self.last_analysis_bundle, select_beam_id=select_beam_id)
        self.beam_design_view.populate_results(self.current_story_data, self.last_analysis_bundle, select_beam_id=select_beam_id)
        self.schedules_view.populate_results(self.master_project, self.current_story_data, self.last_analysis_bundle)
        return True

    def run_analyze_all_beams(self, switch_to_tab: int = 1, select_beam_id: Optional[str] = None) -> None:
        if not self.master_project:
            return
        beams = self.current_story_data.get("beams", [])
        if not beams:
            QMessageBox.information(
                self,
                "Run Analysis & Design (F5)",
                "No beams found on the active story. Please draw beams (or click 'Demo Layout') before running structural analysis.",
            )
            return

        try:
            self._check_and_apply_slab_thickness(interactive=True)
            # Enforce opening-adjacent Drop Beams & recursive carrier cascade before analysis
            _, pre_alerts = enforce_opening_adjacent_drop_beams_and_cascade(self.current_story_data)
            if pre_alerts and "--check" not in sys.argv:
                QMessageBox.information(
                    self,
                    "Structural Hierarchy Notification",
                    "\n\n".join(pre_alerts),
                )
            self.save_and_sync_current_story()
            self._solve_story_and_refresh_views(select_beam_id=select_beam_id)
            col_recs = self.last_analysis_bundle.get("column_records", []) if self.last_analysis_bundle else []
            slab_recs = self.last_analysis_bundle.get("slab_designs", {}) if self.last_analysis_bundle else {}
            log_studio_event(
                "RUN_ANALYSIS",
                f"Solved {len(slab_recs)} slab(s), {len(beams)} beam(s), {len(col_recs)} column(s) on {self.current_story_data.get('story_id')}",
            )
            self.switch_workspace_mode(switch_to_tab, auto_solve=False)
            self.update_contextual_prompt(
                f"Analysis & Design Complete (ACI 318-19): Solved {len(slab_recs)} slab(s), {len(beams)} beam(s), and {len(col_recs)} column(s)."
            )
        except Exception as exc:
            _report_studio_exception(self, "Structural Analysis & Design Error", exc)

    def switch_workspace_mode(self, mode_idx: int, auto_solve: bool = True) -> None:
        try:
            if auto_solve and mode_idx in (1, 2, 3) and self.current_story_data.get("beams"):
                cur_bid = self.beam_diagrams_view.cb_beam_select.currentData()
                self._solve_story_and_refresh_views(select_beam_id=str(cur_bid) if cur_bid else None)

            self.stack.setCurrentIndex(mode_idx)
            btn = self.view_btn_group.button(mode_idx)
            if btn:
                btn.setChecked(True)

            # Context-Specific Toolbars: Show 2D CAD toolbars ONLY in Workspace 0 (2D Structural Drawing)!
            is_cad = mode_idx == 0
            for w in (self.zoom_tb, self.modify_tb, self.dim_tb, self.draw_tb, self.ctx_frame, self.thick_frame, self.bot_frame):
                w.setVisible(is_cad)

            # Redraw active diagram after stack switch & toolbar visibility change settles so viewport width is 100% accurate
            if mode_idx == 1 and self.last_analysis_bundle:
                idx_b = self.beam_diagrams_view.cb_beam_select.currentIndex()
                if idx_b >= 0:
                    QTimer.singleShot(0, lambda idx=idx_b: self.beam_diagrams_view._on_beam_selected(idx))
            elif mode_idx == 2 and self.last_analysis_bundle:
                idx_rc = self.beam_design_view.cb_beam_select.currentIndex()
                if idx_rc >= 0:
                    QTimer.singleShot(0, lambda idx=idx_rc: self.beam_design_view._on_beam_selected(idx))
        except Exception as exc:
            _report_studio_exception(self, "Workspace Switch Error", exc)


def _report_studio_exception(parent: Optional[QWidget], title: str, exc: BaseException) -> None:
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_studio_event("ERROR", f"{title}: {type(exc).__name__}: {exc}", tb_str, level="ERROR")
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xpert_studio_crash.log")
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- [{STUDIO_VERSION}] {title} ---\n{tb_str}\n")
    except Exception:
        pass
    print(tb_str, file=sys.stderr)
    if "--check" in sys.argv:
        raise exc
    if QApplication.instance() is not None:
        QMessageBox.critical(
            parent,
            title,
            f"An unexpected error was intercepted safely without closing the studio:\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            f"Details logged to xpert_studio_session.log & xpert_studio_crash.log.",
        )


def _install_global_excepthook() -> None:
    def _hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log_studio_event("UNHANDLED_QT_EXCEPTION", f"{exc_type.__name__}: {exc_value}", tb_str, level="CRITICAL")
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xpert_studio_crash.log")
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- [{STUDIO_VERSION}] Unhandled Qt Exception ---\n{tb_str}\n")
        except Exception:
            pass
        print(tb_str, file=sys.stderr)
        if QApplication.instance() is not None and "--check" not in sys.argv:
            QMessageBox.critical(
                None,
                f"Xpert Studio Exception Handler ({STUDIO_VERSION})",
                f"An unexpected error occurred and was safely caught:\n\n"
                f"{exc_type.__name__}: {exc_value}",
            )

    sys.excepthook = _hook


def main() -> None:
    if "--check" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)
    _install_global_excepthook()

    if "--check" in sys.argv:
        cfg = {
            "project_name": "Villa_Yasmin",
            "root_directory": os.path.abspath("./XpertStudio_Projects"),
            "ground_floor_height_m": 3.20,
            "include_basement": False,
            "floors_above_ground": 2,
            "upper_floor_height_m": 3.00,
            "upper_floors_mode": "typical",
            "include_penthouse": False,
            "foundation_depth_m": 1.50,
            "fc_mpa": 20.0,
            "fy_mpa": 350.0,
            "soil_bearing_qall_kn_m2": 150.0,
        }
        master = initialize_studio_project(cfg)
        win = XpertStudioMainWindow(initial_master_project=master)
        win.activate_cad_tool("LOAD_TEMPLATE")
        win.run_analyze_all_beams()
        print("HEADLESS_STUDIO_CHECK_OK")
        sys.exit(0)

    cli_project_path = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and arg.lower().endswith((MASTER_FILE_EXT, ".xpert", ".json")) and os.path.isfile(arg):
            cli_project_path = arg
            break

    if cli_project_path:
        master_data = load_studio_project_from_master_file(cli_project_path)
        win = XpertStudioMainWindow(initial_master_project=master_data)
        win.showMaximized()
        sys.exit(app.exec())

    welcome_dlg = StartupWelcomeDialog()
    if welcome_dlg.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    if welcome_dlg.choice == "OPEN" and welcome_dlg.selected_master_path:
        master_data = load_studio_project_from_master_file(welcome_dlg.selected_master_path)
    else:
        setup_dlg = NewProjectSetupDialog()
        if setup_dlg.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        master_data = initialize_studio_project(setup_dlg.get_config())

    win = XpertStudioMainWindow(initial_master_project=master_data)
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# ===== v2.4.2-structural-bim-pro additive upgrades =====
class MinSectionsDialog(QDialog):
    def __init__(self, parent_studio, master):
        super().__init__(parent_studio)
        self.studio = parent_studio; self.master = master
        self.setWindowTitle("Minimum Beam Sections (persistent project-wide)")
        self.setMinimumWidth(420); self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ld = master.get("loads_and_defaults", {})
        vb = QVBoxLayout(self); form = QFormLayout()
        self.sp_hw = QDoubleSpinBox(); self.sp_hw.setRange(20.0, 60.0); self.sp_hw.setSingleStep(5.0)
        self.sp_hw.setValue(float(ld.get("hidden_beam_min_width_cm", 30.0))); self.sp_hw.setSuffix(" cm")
        form.addRow("Hidden Beam MIN width:", self.sp_hw)
        self.sp_dd = QDoubleSpinBox(); self.sp_dd.setRange(30.0, 80.0); self.sp_dd.setSingleStep(5.0)
        self.sp_dd.setValue(float(ld.get("drop_beam_min_depth_cm", 40.0))); self.sp_dd.setSuffix(" cm")
        form.addRow("Drop Beam MIN depth:", self.sp_dd)
        vb.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save); bb.rejected.connect(self.reject); vb.addWidget(bb)
    def _save(self):
        import xpert_project_io as _pio
        _pio.update_min_sections(self.master, self.sp_hw.value(), self.sp_dd.value())
        self.studio._populate_story_selector(); self.studio.refresh_story_ui()
        self.accept()

def _open_min_sections(self):
    if not self.master_project:
        QMessageBox.information(self, "Minimum Sections", "Open a project first."); return
    MinSectionsDialog(self, self.master_project).exec()
XpertStudioMainWindow.open_min_sections_dialog = _open_min_sections

_orig_menu = XpertStudioMainWindow._build_classic_menu_bar
def _menu2(self):
    _orig_menu(self)
    m = self.menuBar().addMenu("&Sections")
    a = QAction("Minimum Beam Sections (Hidden Width / Drop Depth)...", self)
    a.triggered.connect(self.open_min_sections_dialog); m.addAction(a)
XpertStudioMainWindow._build_classic_menu_bar = _menu2

_orig_load = XpertStudioMainWindow.load_project_from_file
def _load2(self, path):
    _orig_load(self, path)
    if self.master_project:
        import xpert_project_io as _pio
        _pio.migrate_master_to_v242(self.master_project)
        self._populate_story_selector()
XpertStudioMainWindow.load_project_from_file = _load2

_orig_story = XpertStudioMainWindow._on_story_changed
def _story2(self, idx):
    _orig_story(self, idx)
    if self.master_project and self.current_story_data:
        import xpert_project_io as _pio
        _pio.migrate_story_to_v242(self.current_story_data, self.master_project)
        self.refresh_story_ui(); self.cad_canvas.zoom_extents()
XpertStudioMainWindow._on_story_changed = _story2

_orig_render = StructuralCadCanvas2D.render_story
def _render2(self, story_data):
    import xpert_project_io as _pio
    _pio.migrate_story_to_v242(story_data, getattr(self.studio, "master_project", None))
    _orig_render(self, story_data)
StructuralCadCanvas2D.render_story = _render2

_orig_zoom = StructuralCadCanvas2D.zoom_extents
def _zoom2(self):
    _orig_zoom(self)
    rect = self.scene_2d.itemsBoundingRect()
    if not rect.isNull():
        self.scene_2d.setSceneRect(rect.adjusted(-40, -40, 40, 40))
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
StructuralCadCanvas2D.zoom_extents = _zoom2


# ===== v2.4.3-structural-bim-pro additive upgrades (no visual/style changes to approved elements) =====
class MinimumDimensionsDialog(QDialog):
    def __init__(self, parent_studio, master):
        super().__init__(parent_studio)
        self.studio = parent_studio; self.master = master
        self.setWindowTitle("Minimum Dimensions (project-wide defaults, per-element overridable)")
        self.setMinimumWidth(460); self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ld = master.get("loads_and_defaults", {})
        vb = QVBoxLayout(self); form = QFormLayout()
        def sp(val, lo, hi, step, suf):
            s = QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(step); s.setValue(float(val)); s.setSuffix(suf); return s
        self.sp_hw = sp(ld.get("hidden_beam_min_width_cm", 30.0), 20, 80, 5, " cm")
        self.sp_dd = sp(ld.get("drop_beam_min_depth_cm", 40.0), 30, 100, 5, " cm")
        self.sp_cb = sp(ld.get("column_min_b_m", 0.20), 0.15, 1.0, 0.05, " m")
        self.sp_ch = sp(ld.get("column_min_h_m", 0.40), 0.20, 1.5, 0.05, " m")
        self.sp_fb = sp(ld.get("footing_min_b_m", 0.80), 0.5, 4.0, 0.1, " m")
        self.sp_fh = sp(ld.get("footing_min_h_m", 0.80), 0.5, 4.0, 0.1, " m")
        self.sp_ft = sp(ld.get("footing_min_t_m", 0.30), 0.2, 1.5, 0.05, " m")
        form.addRow("Hidden Beam MIN width:", self.sp_hw)
        form.addRow("Drop Beam MIN depth:", self.sp_dd)
        form.addRow("Column MIN b:", self.sp_cb)
        form.addRow("Column MIN h:", self.sp_ch)
        form.addRow("Footing MIN B:", self.sp_fb)
        form.addRow("Footing MIN H:", self.sp_fh)
        form.addRow("Footing MIN thickness:", self.sp_ft)
        vb.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save); bb.rejected.connect(self.reject); vb.addWidget(bb)
    def _save(self):
        import xpert_project_io as _pio
        _pio.update_minimum_dimensions(self.master, self.sp_hw.value(), self.sp_dd.value(),
                                       self.sp_cb.value(), self.sp_ch.value(),
                                       self.sp_fb.value(), self.sp_fh.value(), self.sp_ft.value())
        self.studio._populate_story_selector(); self.studio.refresh_story_ui()
        self.accept()

def _open_min_dims(self):
    if not self.master_project:
        QMessageBox.information(self, "Minimum Dimensions", "Open a project first."); return
    MinimumDimensionsDialog(self, self.master_project).exec()
XpertStudioMainWindow.open_minimum_dimensions_dialog = _open_min_dims

def _discontinue_col_upper(self):
    import xpert_project_io as _pio
    ids = [i for k, i in self.cad_canvas.selected_items if k == "column"]
    if not ids:
        QMessageBox.information(self, "Discontinue Column", "Select a ground-floor column first."); return
    for cid in ids:
        for s in self.master_project.get("stories", []):
            sid = s.get("story_id", "")
            if not sid.startswith("02_") and not sid.startswith("00_"):
                _pio.set_column_story_override(self.master_project, cid, sid, active=False)
    _pio.propagate_ground_columns_to_all_stories(self.master_project, self.current_story_data.get("columns", []))
    self.refresh_story_ui(); self.update_contextual_prompt(f"Discontinued {', '.join(ids)} in upper stories (Undo restores).")
XpertStudioMainWindow.discontinue_selected_column_upper = _discontinue_col_upper

def _restore_col_upper(self):
    import xpert_project_io as _pio
    ids = [i for k, i in self.cad_canvas.selected_items if k == "column"]
    if not ids:
        QMessageBox.information(self, "Restore Column", "Select a ground-floor column first."); return
    for cid in ids:
        _pio.restore_column_in_upper_stories(self.master_project, cid)
    _pio.propagate_ground_columns_to_all_stories(self.master_project, self.current_story_data.get("columns", []))
    self.refresh_story_ui(); self.update_contextual_prompt(f"Restored {', '.join(ids)} in upper stories.")
XpertStudioMainWindow.restore_selected_column_upper = _restore_col_upper

_orig_menu_v243 = XpertStudioMainWindow._build_classic_menu_bar
def _menu_v243(self):
    _orig_menu_v243(self)
    for a in self.menuBar().actions():
        t = a.text().replace("&", "").lower()
        if t == "options":
            m = a.menu()
            if m is not None:
                m.addSeparator()
                act = QAction("Minimum Dimensions...", self)
                act.triggered.connect(self.open_minimum_dimensions_dialog); m.addAction(act)
        elif t == "modify":
            m = a.menu()
            if m is not None:
                m.addSeparator()
                a1 = QAction("Discontinue Selected Column in Upper Stories", self)
                a1.triggered.connect(self.discontinue_selected_column_upper); m.addAction(a1)
                a2 = QAction("Restore Selected Column in Upper Stories", self)
                a2.triggered.connect(self.restore_selected_column_upper); m.addAction(a2)
XpertStudioMainWindow._build_classic_menu_bar = _menu_v243

_orig_tb_v243 = XpertStudioMainWindow._build_separated_toolbars
def _tb_v243(self):
    _orig_tb_v243(self)
    btns = self.draw_tb.findChildren(QPushButton)
    self._btn_place_col = next((b for b in btns if b.text().strip().startswith("2.")), None)
    self._btn_neck_col = QPushButton("2. Neck Column (Ties)")
    self._btn_neck_col.setMinimumHeight(30); self._btn_neck_col.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self._btn_neck_col.setStyleSheet("background-color:#0D9488;color:white;font-weight:bold;")
    self._btn_neck_col.clicked.connect(lambda: self.activate_cad_tool("DRAW_NECK_COL"))
    target = None
    for a in self.draw_tb.actions():
        w = a.defaultWidget() if hasattr(a, "defaultWidget") else None
        if w is self._btn_place_col: target = a; break
    if target is not None: self.draw_tb.insertWidget(target, self._btn_neck_col)
    else: self.draw_tb.addWidget(self._btn_neck_col)
    self._btn_neck_col.setVisible(False)
XpertStudioMainWindow._build_separated_toolbars = _tb_v243

_orig_story_v243 = XpertStudioMainWindow._on_story_changed
def _story_v243(self, idx):
    _orig_story_v243(self, idx)
    import xpert_project_io as _pio
    if self.master_project and self.current_story_data:
        _pio.migrate_story_to_v243(self.current_story_data, self.master_project)
    tie = self.is_tie_beams_story()
    if getattr(self, "_btn_place_col", None) is not None: self._btn_place_col.setVisible(not tie)
    if getattr(self, "_btn_neck_col", None) is not None: self._btn_neck_col.setVisible(tie)
    for w in self._slab_only_widgets:
        if hasattr(w, "styleSheet"):
            if not hasattr(w, "_orig_ss_v243"): w._orig_ss_v243 = w.styleSheet()
            w.setStyleSheet("background-color:#E2E8F0;color:#94A3B8;border:1px solid #CBD5E1;" if tie else w._orig_ss_v243)
        w.setEnabled(not tie)
    self.cad_canvas.zoom_extents()
XpertStudioMainWindow._on_story_changed = _story_v243

_orig_load_v243 = XpertStudioMainWindow.load_project_from_file
def _load_v243(self, path):
    _orig_load_v243(self, path)
    if self.master_project:
        import xpert_project_io as _pio
        _pio.migrate_master_to_v243(self.master_project)
        self._populate_story_selector()
XpertStudioMainWindow.load_project_from_file = _load_v243

_orig_undo_v243 = XpertStudioMainWindow.undo_action
def _undo_v243(self):
    _orig_undo_v243(self)
    if self.master_project and str(self.current_story_data.get("story_id", "")) == "02_Ground_Floor":
        import xpert_project_io as _pio
        _pio.propagate_ground_columns_to_all_stories(self.master_project, self.current_story_data.get("columns", []))
XpertStudioMainWindow.undo_action = _undo_v243
_orig_redo_v243 = XpertStudioMainWindow.redo_action
def _redo_v243(self):
    _orig_redo_v243(self)
    if self.master_project and str(self.current_story_data.get("story_id", "")) == "02_Ground_Floor":
        import xpert_project_io as _pio
        _pio.propagate_ground_columns_to_all_stories(self.master_project, self.current_story_data.get("columns", []))
XpertStudioMainWindow.redo_action = _redo_v243

_orig_click_v243 = StructuralCadCanvas2D._handle_left_click_at
def _click_v243(self, sx, sy, raw_x, raw_y, snap_type):
    if self.active_tool == "DRAW_NECK_COL":
        if not self.studio.is_tie_beams_story():
            self.studio.update_contextual_prompt("Neck Columns are allowed ONLY on the Tie-Beams story."); return
        story = self.studio.current_story_data
        cols = story.setdefault("columns", [])
        nid = f"NC{sum(1 for c in cols if str(c.get('id','')).startswith('NC')) + 1}"
        ld = (self.studio.master_project or {}).get("loads_and_defaults", {})
        b = float(ld.get("column_min_b_m", 0.20)); h = float(ld.get("column_min_h_m", 0.40))
        cols.append({"id": nid, "x": sx, "y": sy, "b_m": b, "h_m": h, "active": True, "neck": True, "room_bounding": True})
        self.studio.save_and_sync_current_story(); self.studio.refresh_story_ui()
        self.studio.update_contextual_prompt(f"Placed Neck Column {nid} (carries tie beams only, stops here, own footing).")
        return
    _orig_click_v243(self, sx, sy, raw_x, raw_y, snap_type)
StructuralCadCanvas2D._handle_left_click_at = _click_v243

def _zoom_v243(self):
    story = self.studio.current_story_data
    s = self.scale_px
    xs, ys = [], []
    for p in story.get("slab_edge_polygon", []): xs.append(float(p[0])); ys.append(float(p[1]))
    for c in story.get("columns", []):
        if c.get("active", True):
            xs += [float(c["x"]) - float(c.get("b_m", 0.2)) / 2, float(c["x"]) + float(c.get("b_m", 0.2)) / 2]
            ys += [float(c["y"]) - float(c.get("h_m", 0.4)) / 2, float(c["y"]) + float(c.get("h_m", 0.4)) / 2]
    for b in story.get("beams", []):
        xs += [float(b.get("start_x", 0)), float(b.get("end_x", 0))]; ys += [float(b.get("start_y", 0)), float(b.get("end_y", 0))]
    for sl in story.get("slabs", []):
        if "min_x" in sl: xs += [float(sl["min_x"]), float(sl["max_x"])]; ys += [float(sl["min_y"]), float(sl["max_y"])]
    for d in story.get("dimensions", []):
        xs += [float(d.get("dx1", d.get("x1", 0))), float(d.get("dx2", d.get("x2", 0)))]
        ys += [float(d.get("dy1", d.get("y1", 0))), float(d.get("dy2", d.get("y2", 0)))]
    self.resetTransform()
    if xs and ys:
        m = 1.5
        r = QRectF((min(xs) - m) * s, -(max(ys) + m) * s, (max(xs) - min(xs) + 2 * m) * s, (max(ys) - min(ys) + 2 * m) * s)
    else:
        r = QRectF(-2 * s, -12 * s, 16 * s, 14 * s)
    self.scene_2d.setSceneRect(r.adjusted(-2 * s, -2 * s, 2 * s, 2 * s))
    self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
    self.centerOn(r.center())
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
StructuralCadCanvas2D.zoom_extents = _zoom_v243

_orig_resize_v243 = StructuralCadCanvas2D.resizeEvent
def _resize_v243(self, e):
    _orig_resize_v243(self, e)
    self.zoom_extents()
StructuralCadCanvas2D.resizeEvent = _resize_v243

_orig_rc_v243 = BeamDesignDetailWidget._draw_beam_rc_canvas
def _rc_v243(self, bid, bm, res, des):
    _orig_rc_v243(self, bid, bm, res, des)
    sc = self.rc_scene
    base = sc.sceneRect().bottom() + 40
    sup = des.get("support_designs", []); spans = des.get("span_designs", [])
    b_mm = float(des.get("b_mm", 400)); h_mm = float(des.get("h_mm", 300))
    sc_w = max(90.0, min(150.0, b_mm * 0.22)); sc_h = max(90.0, min(150.0, h_mm * 0.22))
    nbs = max(2, int(des.get("n_max_per_layer", 6)))
    nbot_cont = int(des.get("n_bars_min_cont", des.get("bottom_n_bars", 2)))
    ntop_cont = int(des.get("n_min_cont", des.get("top_n_bars", 2)))
    x = 40.0
    seq = []
    for i in range(max(len(sup), len(spans))):
        if i < len(sup): seq.append(("sup", i))
        if i < len(spans): seq.append(("span", i))
    for kind, i in seq:
        if kind == "sup":
            s = sup[i]; label = f"Sec @ {s.get('target_id', 'C')}"; nt = int(s.get("top_n_bars", ntop_cont)); nb = nbot_cont
            stir = s.get("stirrups_end", des.get("stirrups", ""))
        else:
            s = spans[i]; label = f"Sec Mid-Span {s.get('span_index', i + 1)}"; nt = ntop_cont; nb = int(s.get("bottom_n_bars", nbot_cont))
            stir = s.get("stirrups", des.get("stirrups", ""))
        sc.addRect(QRectF(x, base, sc_w, sc_h), QPen(QColor("#0F172A"), 2), QBrush(QColor("#F1F5F9")))
        sc.addRect(QRectF(x + 8, base + 8, sc_w - 16, sc_h - 16), QPen(QColor("#059669"), 1.6), QBrush(Qt.BrushStyle.NoBrush))
        def row(n, top):
            rem = n; r = 0
            while rem > 0 and r < 3:
                nr = min(rem, nbs); ry = base + 12 + r * 12 if top else base + sc_h - 18 - r * 12
                for k in range(nr):
                    bx = x + 12 + (sc_w - 24) * (k / max(1, nr - 1)) if nr > 1 else x + sc_w / 2
                    sc.addEllipse(QRectF(bx - 3.5, ry, 7, 7), QPen(QColor("#991B1B" if top else "#0369A1"), 1), QBrush(QColor("#DC2626" if top else "#0284C7")))
                rem -= nr; r += 1
        row(nt, True); row(nb, False)
        t = sc.addText(label, QFont("Arial", 8, QFont.Weight.Bold)); t.setDefaultTextColor(QColor("#0B3C5D")); t.setPos(x, base - 18)
        t2 = sc.addText(f"Top {nt} / Bot {nb}\n{stir}", QFont("Arial", 7)); t2.setPos(x, base + sc_h + 4)
        x += sc_w + 40
    sc.setSceneRect(sc.itemsBoundingRect().adjusted(-20, -20, 20, 60))
BeamDesignDetailWidget._draw_beam_rc_canvas = _rc_v243
