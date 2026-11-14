"""
Xpert Structural Design Studio (v1.6.0-structural-bim-pro)
Main Desktop Application (PyQt6 + ezdxf + Matplotlib)
Lead Structural Engineer & Product Owner: Eng. Yousef Mohammed Keshlaf
"""

from __future__ import annotations
import json
import math
import os
import sys
from typing import Dict, Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF
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
    QPushButton,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from xpert_project_io import (
    STUDIO_VERSION,
    MASTER_FILE_EXT,
    initialize_studio_project,
    load_studio_project_from_master_file,
    propagate_ground_columns_to_all_stories,
    sync_story_to_dxf,
    validate_project_name,
    compute_smart_beam_tag_position,
    import_arch_dxf_underlay,
)
from xpert_structural_engine import (
    analyze_all_story_beams_and_columns,
    evaluate_story_thickness_and_optimization,
    get_slab_bounding_box,
    enforce_column_inside_slab_boundary,
    check_duplicate_column,
    validate_and_build_beam_with_cantilevers,
    detect_story_grid_bays,
    reconcile_and_split_slabs_after_beam_change,
    auto_fill_all_story_slabs,
    rotate_column_90_deg,
    pick_area_create_or_update_slab,
    toggle_slab_rib_by_label_click,
    delete_selected_element_from_story,
    move_column_and_sync_connected_beams,
    move_beam_within_slab_boundary,
    select_elements_by_box,
    align_element_face_to_reference,
    move_selected_elements_by_delta,
    measure_distance_2d,
    create_linear_dimension,
    auto_generate_exterior_dimensions,
    get_beam_span_segments,
    ensure_beam_wall_flags,
    set_story_wall_load_policy,
    set_beam_span_wall_flag,
    convert_beam_kind_and_section,
)


class StartupWelcomeDialog(QDialog):
    """
    Compact Startup Launch Window offering ONLY two mutually exclusive choices:
    1. Start a New Structural Project (opens NewProjectSetupDialog)
    2. Open an Existing Project (`*.xsd`) (goes directly to Ground Floor Plan)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Welcome — Xpert Structural Design Studio ({STUDIO_VERSION})")
        self.setFixedSize(540, 310)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.choice: Optional[str] = None  # "NEW" or "OPEN"
        self.selected_master_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(24, 22, 24, 22)
        vbox.setSpacing(16)

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
        btn_new.setMinimumHeight(58)
        btn_new.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #16A34A; color: white; border-radius: 6px; padding: 10px;"
        )
        btn_new.clicked.connect(self._on_choose_new)
        vbox.addWidget(btn_new)

        btn_open = QPushButton(f"2. Open Existing Structural Project (*{MASTER_FILE_EXT})...")
        btn_open.setMinimumHeight(58)
        btn_open.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #0284C7; color: white; border-radius: 6px; padding: 10px;"
        )
        btn_open.clicked.connect(self._on_choose_open)
        vbox.addWidget(btn_open)

        vbox.addStretch(1)

    def _on_choose_new(self) -> None:
        self.choice = "NEW"
        self.accept()

    def _on_choose_open(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Xpert Structural Design Project (*.xsd)",
            os.path.abspath("./XpertStudio_Projects"),
            f"Xpert Structural Project (*{MASTER_FILE_EXT} *.xpert *-00_Project_Master.json);;All Files (*)",
        )
        if fpath and os.path.isfile(fpath):
            self.selected_master_path = fpath
            self.choice = "OPEN"
            self.accept()


class NewProjectSetupDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Structural Project Data — Xpert Structural Design Studio")
        self.setMinimumWidth(680)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        grp_id = QGroupBox(f"1. New Project Identity && Workspace Folder (Master Extension: *{MASTER_FILE_EXT})")
        form_id = QFormLayout(grp_id)

        self.ed_name = QLineEdit("Villa_Al_Yasmin")
        form_id.addRow("Project Name:", self.ed_name)

        folder_row = QHBoxLayout()
        self.ed_folder = QLineEdit(os.path.abspath("./XpertStudio_Projects"))
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
        self.sp_fc.setValue(20.0)
        self.sp_fc.setSuffix(" MPa")
        form_mat.addRow("Concrete f'c:", self.sp_fc)

        self.sp_fy = QDoubleSpinBox()
        self.sp_fy.setRange(200.0, 1000.0)
        self.sp_fy.setValue(350.0)
        self.sp_fy.setSuffix(" MPa")
        form_mat.addRow("Reinforcement Fy:", self.sp_fy)

        self.sp_qall = QDoubleSpinBox()
        self.sp_qall.setRange(50.0, 2000.0)
        self.sp_qall.setValue(150.0)
        self.sp_qall.setSuffix(" kN/m²")
        form_mat.addRow("Soil Bearing Capacity (q_all):", self.sp_qall)

        self.sp_finish = QDoubleSpinBox()
        self.sp_finish.setRange(0.0, 20.0)
        self.sp_finish.setValue(2.0)
        self.sp_finish.setSuffix(" kN/m²")
        form_mat.addRow("Floor Finish Load:", self.sp_finish)

        self.sp_live = QDoubleSpinBox()
        self.sp_live.setRange(0.0, 50.0)
        self.sp_live.setValue(2.0)
        self.sp_live.setSuffix(" kN/m²")
        form_mat.addRow("Live Load:", self.sp_live)

        lbl_col_note = QLabel("Initial Column Section: 0.20 × 0.40 m | Hidden Beam Width: 0.40 m | Drop Beam Width: 0.20 m")
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




class XpertBeamAnalysisDiagramWidget(QWidget):
    """
    Classic Xpert Beam Analysis interactive canvas:
    - Pure white engineering background.
    - Full continuous beam line with support centerlines & dimensions.
    - Distributed loads (olive green with downward arrows & load breakdown).
    - Concentrated loads (red downward arrows with distance from Support 1).
    - Green support reactions (R1, R2, ...).
    - Blue hatched Shear Force Diagram (#1D70B8).
    - Red hatched Bending Moment Diagram (#C81E1E, positive downward).
    - Dynamic real-time cursor tracker showing (X, V, M) on mouse hover.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.beam: Optional[Dict[str, Any]] = None
        self.res: Optional[Dict[str, Any]] = None
        self.hover_x_m: Optional[float] = None
        self.setMouseTracking(True)
        self.setMinimumHeight(520)
        self.setStyleSheet("background-color: #FFFFFF;")

    def set_beam_data(self, beam: Optional[Dict[str, Any]], res: Optional[Dict[str, Any]]) -> None:
        self.beam = beam
        self.res = res
        self.hover_x_m = None
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self.res or "x_full" not in self.res or not self.res["x_full"]:
            super().mouseMoveEvent(event)
            return

        x_pts = self.res["x_full"]
        x_min, x_max = min(x_pts), max(x_pts)
        tot_l = max(1e-3, x_max - x_min)

        pad_left = 75.0
        pad_right = 45.0
        plot_w = max(10.0, float(self.width()) - pad_left - pad_right)

        px = float(event.position().x())
        if pad_left <= px <= pad_left + plot_w:
            frac = (px - pad_left) / plot_w
            self.hover_x_m = round(x_min + frac * tot_l, 2)
        else:
            self.hover_x_m = None
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_x_m = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        painter.fillRect(0, 0, int(w), int(h), QColor("#FFFFFF"))

        if not self.beam or not self.res or "x_full" not in self.res or len(self.res["x_full"]) < 2:
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No beam analysis data available.\nSelect a beam and click 'Run Analysis & Design (F5)'.")
            return

        x_pts = self.res["x_full"]
        v_pts = self.res["v_full"]
        m_pts = self.res["m_full"]
        spans = self.res.get("spans", [])
        reactions = self.res.get("reactions_kn", [])
        c_left = float(self.beam.get("cantilever_left_m", 0.0))
        c_right = float(self.beam.get("cantilever_right_m", 0.0))
        loads = self.beam.get("loads", [])
        b_id = str(self.beam.get("id", "Beam"))

        x_min = min(x_pts)
        x_max = max(x_pts)
        L_total = max(1e-3, x_max - x_min)

        pad_left = 75.0
        pad_right = 45.0
        plot_w = max(10.0, w - pad_left - pad_right)

        def to_sx(x_val: float) -> float:
            return pad_left + ((x_val - x_min) / L_total) * plot_w

        h_unit = (h - 60.0) / 3.0
        sec1_mid = 30.0 + h_unit * 0.55
        sec2_mid = 30.0 + h_unit * 1.55
        sec3_mid = 30.0 + h_unit * 2.55

        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        b_kind_str = self.beam.get("beam_kind", "hidden").upper()
        sec_str = f"{float(self.beam.get('width_m', 0.4)):.2f}×{float(self.beam.get('depth_m', 0.3)):.2f}m"
        n_spans_txt = f"{len(spans)} Spans" + (f" + Cantilevers ({c_left:.2f}m / {c_right:.2f}m)" if (c_left > 0 or c_right > 0) else "")
        painter.drawText(int(pad_left), 22, f"Xpert Beam Analysis — {b_id} [{b_kind_str} Beam {sec_str}] | {n_spans_txt}")

        supp_xs = [c_left]
        for s in spans:
            supp_xs.append(round(supp_xs[-1] + s, 3))

        # --- Draw Beam Axis in Section 1 ---
        painter.setPen(QPen(QColor("#1E293B"), 4.0))
        painter.drawLine(int(to_sx(0.0)), int(sec1_mid), int(to_sx(L_total)), int(sec1_mid))

        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        for idx, sx in enumerate(supp_xs):
            px = to_sx(sx)
            tri = QPolygonF([QPointF(px, sec1_mid), QPointF(px - 7, sec1_mid + 14), QPointF(px + 7, sec1_mid + 14)])
            painter.setPen(QPen(QColor("#0F172A"), 1.5))
            painter.setBrush(QBrush(QColor("#E2E8F0")))
            painter.drawPolygon(tri)

            painter.drawLine(int(px - 10), int(sec1_mid + 14), int(px + 10), int(sec1_mid + 14))
            for hx in range(-8, 9, 4):
                painter.drawLine(int(px + hx), int(sec1_mid + 14), int(px + hx - 3), int(sec1_mid + 18))

            r_val = reactions[idx] if idx < len(reactions) else 0.0
            r_str = f"R{idx+1}={r_val:.1f} kN"
            painter.setPen(QColor("#16A34A"))
            painter.drawText(int(px - 25), int(sec1_mid + 28), r_str)

        dim_pen = QPen(QColor("#64748B"), 1.0)
        painter.setPen(dim_pen)
        dim_y = sec1_mid + 42.0
        for s_idx, s_len in enumerate(spans):
            x1 = to_sx(supp_xs[s_idx])
            x2 = to_sx(supp_xs[s_idx + 1])
            painter.drawLine(int(x1), int(dim_y), int(x2), int(dim_y))
            painter.drawLine(int(x1), int(dim_y - 4), int(x1), int(dim_y + 4))
            painter.drawLine(int(x2), int(dim_y - 4), int(x2), int(dim_y + 4))
            mid_x = (x1 + x2) / 2.0
            painter.setPen(QColor("#334155"))
            painter.drawText(int(mid_x - 22), int(dim_y + 12), f"L{s_idx+1}={s_len:.2f}m")
            painter.setPen(dim_pen)

        # Draw Loads in Section 1
        for ld in loads:
            if ld.get("type") == "dist":
                lx1 = float(ld.get("x1", 0.0))
                lx2 = float(ld.get("x2", L_total))
                w_val = float(ld.get("val", 0.0))
                px1 = to_sx(lx1)
                px2 = to_sx(lx2)
                ld_h = 24.0
                ld_rect = QRectF(px1, sec1_mid - ld_h, px2 - px1, ld_h)
                painter.setPen(QPen(QColor("#556B2F"), 1.2))
                painter.setBrush(QBrush(QColor(85, 107, 47, 40)))
                painter.drawRect(ld_rect)
                arrow_step = max(20.0, (px2 - px1) / 6.0)
                curr_px = px1 + 10.0
                while curr_px < px2:
                    painter.drawLine(int(curr_px), int(sec1_mid - ld_h), int(curr_px), int(sec1_mid))
                    painter.drawLine(int(curr_px), int(sec1_mid), int(curr_px - 3), int(sec1_mid - 4))
                    painter.drawLine(int(curr_px), int(sec1_mid), int(curr_px + 3), int(sec1_mid - 4))
                    curr_px += arrow_step
                w_lbl = f"w = {w_val:.1f} kN/m"
                painter.setPen(QColor("#3B5323"))
                painter.drawText(int((px1 + px2) / 2.0 - 25), int(sec1_mid - ld_h - 4), w_lbl)

            elif ld.get("type") in ("point", "P"):
                lx = float(ld.get("x", 0.0))
                pval = float(ld.get("val", 0.0))
                px = to_sx(lx)
                p_len = 36.0
                painter.setPen(QPen(QColor("#DC2626"), 2.2))
                painter.drawLine(int(px), int(sec1_mid - p_len), int(px), int(sec1_mid))
                painter.drawLine(int(px), int(sec1_mid), int(px - 4), int(sec1_mid - 7))
                painter.drawLine(int(px), int(sec1_mid), int(px + 4), int(sec1_mid - 7))
                dist_txt = f"d1={ld.get('dist_from_sup1_m', lx):.2f}m" if 'dist_from_sup1_m' in ld else ""
                p_lbl = f"P={pval:.1f}kN" + (f" ({dist_txt})" if dist_txt else "")
                painter.drawText(int(px - 20), int(sec1_mid - p_len - 4), p_lbl)

        # --- Section 2: SFD (#1D70B8) ---
        max_abs_v = max(abs(v) for v in v_pts) if v_pts else 1.0
        if max_abs_v < 1e-3:
            max_abs_v = 1.0
        v_scale = (h_unit * 0.38) / max_abs_v

        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#1D70B8"))
        painter.drawText(int(pad_left), int(sec2_mid - h_unit * 0.42), "Shear Force Diagram — Vu (kN)")

        painter.setPen(QPen(QColor("#94A3B8"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(int(pad_left), int(sec2_mid), int(pad_left + plot_w), int(sec2_mid))
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor("#64748B"))
        painter.drawText(int(pad_left - 30), int(sec2_mid + 4), "0.0")

        sfd_poly = [QPointF(to_sx(x_pts[0]), sec2_mid)]
        for x, v in zip(x_pts, v_pts):
            sfd_poly.append(QPointF(to_sx(x), sec2_mid - v * v_scale))
        sfd_poly.append(QPointF(to_sx(x_pts[-1]), sec2_mid))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1D70B8"), Qt.BrushStyle.BDiagPattern))
        painter.drawPolygon(QPolygonF(sfd_poly))

        painter.setPen(QPen(QColor("#1D70B8"), 2.0))
        for i in range(len(x_pts) - 1):
            p1 = QPointF(to_sx(x_pts[i]), sec2_mid - v_pts[i] * v_scale)
            p2 = QPointF(to_sx(x_pts[i + 1]), sec2_mid - v_pts[i + 1] * v_scale)
            painter.drawLine(p1, p2)

        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#1D70B8"))
        for s_entry in self.res.get("support_critical_table", []):
            sx = s_entry.get("x_m", 0.0)
            px = to_sx(sx)
            v_l = s_entry.get("v_left_kn", 0.0)
            v_r = s_entry.get("v_right_kn", 0.0)
            if abs(v_l) > 0.1:
                painter.drawText(int(px - 35), int(sec2_mid - v_l * v_scale - 4), f"{v_l:.1f}")
            if abs(v_r) > 0.1:
                painter.drawText(int(px + 4), int(sec2_mid - v_r * v_scale + 12), f"{v_r:.1f}")

        # --- Section 3: BMD (#C81E1E) ---
        max_abs_m = max(abs(m) for m in m_pts) if m_pts else 1.0
        if max_abs_m < 1e-3:
            max_abs_m = 1.0
        m_scale = (h_unit * 0.38) / max_abs_m

        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#C81E1E"))
        painter.drawText(int(pad_left), int(sec3_mid - h_unit * 0.42), "Bending Moment Diagram — Mu (kN.m) [Positive Downward (+M ↓)]")

        painter.setPen(QPen(QColor("#94A3B8"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(int(pad_left), int(sec3_mid), int(pad_left + plot_w), int(sec3_mid))
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor("#64748B"))
        painter.drawText(int(pad_left - 30), int(sec3_mid + 4), "0.0")

        bmd_poly = [QPointF(to_sx(x_pts[0]), sec3_mid)]
        for x, m in zip(x_pts, m_pts):
            bmd_poly.append(QPointF(to_sx(x), sec3_mid + m * m_scale))
        bmd_poly.append(QPointF(to_sx(x_pts[-1]), sec3_mid))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#C81E1E"), Qt.BrushStyle.DiagCrossPattern))
        painter.drawPolygon(QPolygonF(bmd_poly))

        painter.setPen(QPen(QColor("#C81E1E"), 2.0))
        for i in range(len(x_pts) - 1):
            p1 = QPointF(to_sx(x_pts[i]), sec3_mid + m_pts[i] * m_scale)
            p2 = QPointF(to_sx(x_pts[i + 1]), sec3_mid + m_pts[i + 1] * m_scale)
            painter.drawLine(p1, p2)

        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#C81E1E"))
        for sp in self.res.get("span_critical_table", []):
            mx_pos = sp.get("m_max_pos_knm", 0.0)
            x_pos = sp.get("x_at_m_max_m", 0.0)
            if mx_pos > 0.1:
                px = to_sx(x_pos)
                py = sec3_mid + mx_pos * m_scale
                painter.drawText(int(px - 20), int(py + 14), f"+{mx_pos:.1f}")

        for sup in self.res.get("support_critical_table", []):
            m_c = sup.get("m_center_knm", 0.0)
            sx = sup.get("x_m", 0.0)
            if m_c < -0.1:
                px = to_sx(sx)
                py = sec3_mid + m_c * m_scale
                painter.drawText(int(px - 20), int(py - 6), f"{m_c:.1f}")

        # --- Real-Time Mouse Tracker ---
        if self.hover_x_m is not None:
            hx = self.hover_x_m
            hpx = to_sx(hx)
            hv_val = 0.0
            hm_val = 0.0
            for k in range(len(x_pts) - 1):
                if x_pts[k] <= hx <= x_pts[k + 1]:
                    dt = max(1e-6, x_pts[k + 1] - x_pts[k])
                    frac = (hx - x_pts[k]) / dt
                    hv_val = v_pts[k] + frac * (v_pts[k + 1] - v_pts[k])
                    hm_val = m_pts[k] + frac * (m_pts[k + 1] - m_pts[k])
                    break

            painter.setPen(QPen(QColor("#E11D48"), 1.5, Qt.PenStyle.DashDotLine))
            painter.drawLine(int(hpx), int(sec1_mid - 35), int(hpx), int(sec3_mid + h_unit * 0.45))

            badge_txt = f"X = {hx:.2f} m | Vu = {hv_val:+.2f} kN | Mu = {hm_val:+.2f} kN.m"
            badge_w = 260
            badge_h = 24
            badge_x = min(int(w - badge_w - 20), max(20, int(hpx - badge_w / 2.0)))
            badge_y = int(sec1_mid - 55)

            painter.setPen(QPen(QColor("#0F172A"), 1.2))
            painter.setBrush(QBrush(QColor(15, 23, 42, 235)))
            painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 4, 4)

            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#F8FAFC"))
            painter.drawText(QRectF(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, badge_txt)


class XpertBeamRcDesignWidget(QWidget):
    """
    Beam R.C. Design Elevation & Cross-Section Interactive Display (Mode 2):
    - Concrete continuous beam elevation with spans, supports, and cantilevers.
    - Bottom longitudinal rebar with hooks.
    - Top support negative rebar over columns extending into adjacent spans.
    - Stirrups distribution zones (support dense zone and mid-span zone).
    - Detailed Cross-Section (Section A-A) showing ties, bars, width b, depth h, cover.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.beam: Optional[Dict[str, Any]] = None
        self.res: Optional[Dict[str, Any]] = None
        self.des: Optional[Dict[str, Any]] = None
        self.setMinimumHeight(480)
        self.setStyleSheet("background-color: #0F172A;")

    def set_data(self, beam: Optional[Dict[str, Any]], res: Optional[Dict[str, Any]], des: Optional[Dict[str, Any]]) -> None:
        self.beam = beam
        self.res = res
        self.des = des
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        painter.fillRect(0, 0, int(w), int(h), QColor("#0B0F19"))

        if not self.beam or not self.des or not self.res:
            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No beam design available.\nClick 'Run Analysis & Design (F5)' to design reinforced concrete.")
            return

        b_id = str(self.beam.get("id", "Beam"))
        spans = self.res.get("spans", [])
        c_left = float(self.beam.get("cantilever_left_m", 0.0))
        c_right = float(self.beam.get("cantilever_right_m", 0.0))
        tot_l = c_left + sum(spans) + c_right

        b_mm = float(self.des.get("b_mm", 300))
        h_mm = float(self.des.get("h_mm", 300))
        bot_bars = self.des.get("bottom_bars", "3 Phi 16 mm")
        top_bars = self.des.get("top_bars", "4 Phi 16 mm")
        stirrups = self.des.get("stirrups", "Phi 8 @ 150 mm")

        # Partition: Left 72% Elevation, Right 28% Section A-A
        elev_w = max(100.0, w * 0.70)
        sec_w = w - elev_w

        # --- 1. ELEVATION VIEW ---
        pad_l = 50.0
        pad_r = 30.0
        plot_elev_w = elev_w - pad_l - pad_r

        def to_ex(x_m: float) -> float:
            return pad_l + (x_m / tot_l) * plot_elev_w

        elev_mid_y = h * 0.45
        beam_draw_h = 42.0

        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#38BDF8"))
        painter.drawText(int(pad_l), 28, f"Beam R.C. Elevation — {b_id} [{self.beam.get('beam_kind','').upper()} {b_mm:.0f}×{h_mm:.0f}mm]")

        # Concrete outline
        b_rect = QRectF(to_ex(0.0), elev_mid_y - beam_draw_h / 2.0, plot_elev_w, beam_draw_h)
        painter.setPen(QPen(QColor("#94A3B8"), 2.0))
        painter.setBrush(QBrush(QColor(30, 41, 59, 220)))
        painter.drawRect(b_rect)

        # Support Columns underneath
        supp_xs = [c_left]
        for s in spans:
            supp_xs.append(round(supp_xs[-1] + s, 3))

        for idx, sx in enumerate(supp_xs):
            px = to_ex(sx)
            col_rect = QRectF(px - 14, elev_mid_y + beam_draw_h / 2.0, 28, 45)
            painter.setPen(QPen(QColor("#64748B"), 1.5))
            painter.setBrush(QBrush(QColor(15, 23, 42, 240)))
            painter.drawRect(col_rect)
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(int(px - 10), int(elev_mid_y + beam_draw_h / 2.0 + 26), f"C{idx+1}")

        # Longitudinal Bottom Rebar (Green #22C55E)
        bar_pen_bot = QPen(QColor("#22C55E"), 3.0)
        painter.setPen(bar_pen_bot)
        bot_y = elev_mid_y + beam_draw_h / 2.0 - 7.0
        # Main line
        painter.drawLine(int(to_ex(0.0) + 8), int(bot_y), int(to_ex(tot_l) - 8), int(bot_y))
        # End 90 deg hooks
        painter.drawLine(int(to_ex(0.0) + 8), int(bot_y), int(to_ex(0.0) + 8), int(bot_y - 14))
        painter.drawLine(int(to_ex(tot_l) - 8), int(bot_y), int(to_ex(tot_l) - 8), int(bot_y - 14))

        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#4ADE80"))
        painter.drawText(int(to_ex(tot_l / 2.0) - 40), int(bot_y + 16), f"Bottom: {bot_bars}")

        # Longitudinal Top Rebar Over Supports (Cyan #38BDF8)
        bar_pen_top = QPen(QColor("#38BDF8"), 3.0)
        painter.setPen(bar_pen_top)
        top_y = elev_mid_y - beam_draw_h / 2.0 + 7.0

        for idx, sx in enumerate(supp_xs):
            px = to_ex(sx)
            # Extension L/3 on each side
            ext_l = (spans[idx - 1] / 3.0) if idx > 0 else 0.8
            ext_r = (spans[idx] / 3.0) if idx < len(spans) else 0.8
            x_l = max(to_ex(0.0) + 8, to_ex(sx - ext_l))
            x_r = min(to_ex(tot_l) - 8, to_ex(sx + ext_r))
            painter.drawLine(int(x_l), int(top_y), int(x_r), int(top_y))
            painter.drawText(int(px - 20), int(top_y - 8), f"Top: {top_bars}")

        # Stirrups distribution indication
        stirr_pen = QPen(QColor("#F59E0B"), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(stirr_pen)
        stirr_y1 = elev_mid_y - beam_draw_h / 2.0 + 4
        stirr_y2 = elev_mid_y + beam_draw_h / 2.0 - 4
        for s_idx, s_len in enumerate(spans):
            x1 = to_ex(supp_xs[s_idx])
            x2 = to_ex(supp_xs[s_idx + 1])
            step = max(14.0, (x2 - x1) / 12.0)
            curr = x1 + 10.0
            while curr < x2 - 8.0:
                painter.drawLine(int(curr), int(stirr_y1), int(curr), int(stirr_y2))
                curr += step

        # Span dimension lines
        dim_y = elev_mid_y + beam_draw_h / 2.0 + 55
        painter.setPen(QPen(QColor("#64748B"), 1.0))
        for s_idx, s_len in enumerate(spans):
            x1 = to_ex(supp_xs[s_idx])
            x2 = to_ex(supp_xs[s_idx + 1])
            painter.drawLine(int(x1), int(dim_y), int(x2), int(dim_y))
            painter.drawLine(int(x1), int(dim_y - 4), int(x1), int(dim_y + 4))
            painter.drawLine(int(x2), int(dim_y - 4), int(x2), int(dim_y + 4))
            painter.drawText(int((x1 + x2) / 2.0 - 20), int(dim_y + 14), f"L = {s_len:.2f} m")

        # --- 2. CROSS SECTION (SECTION A-A) ---
        sec_cx = elev_w + sec_w / 2.0
        sec_cy = h * 0.45
        scale_sec = min(sec_w * 0.70 / max(1.0, b_mm), (h * 0.55) / max(1.0, h_mm))
        draw_b = max(60.0, b_mm * scale_sec)
        draw_h = max(70.0, h_mm * scale_sec)

        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#F8FAFC"))
        painter.drawText(int(sec_cx - 45), 28, "Section A-A")

        # Concrete section
        c_sec_rect = QRectF(sec_cx - draw_b / 2.0, sec_cy - draw_h / 2.0, draw_b, draw_h)
        painter.setPen(QPen(QColor("#94A3B8"), 2.0))
        painter.setBrush(QBrush(QColor(30, 41, 59, 230)))
        painter.drawRect(c_sec_rect)

        # Stirrup tie
        cov = 8.0
        tie_rect = c_sec_rect.adjusted(cov, cov, -cov, -cov)
        painter.setPen(QPen(QColor("#F59E0B"), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(tie_rect)

        # Top bars (dots)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#38BDF8")))
        bar_r = 5.0
        top_y_dot = tie_rect.top() + 6.0
        bot_y_dot = tie_rect.bottom() - 6.0

        n_top = 4 if b_mm >= 350 else 3
        for k in range(n_top):
            bx = tie_rect.left() + 6.0 + k * ((tie_rect.width() - 12.0) / max(1, n_top - 1))
            painter.drawEllipse(QPointF(bx, top_y_dot), bar_r, bar_r)

        # Bottom bars (dots)
        painter.setBrush(QBrush(QColor("#22C55E")))
        n_bot = 3 if b_mm >= 300 else 2
        for k in range(n_bot):
            bx = tie_rect.left() + 6.0 + k * ((tie_rect.width() - 12.0) / max(1, n_bot - 1))
            painter.drawEllipse(QPointF(bx, bot_y_dot), bar_r, bar_r)

        # Dimensions & callouts
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#E2E8F0"))
        painter.drawText(int(sec_cx - 30), int(sec_cy + draw_h / 2.0 + 18), f"b = {b_mm:.0f} mm")
        painter.drawText(int(sec_cx + draw_b / 2.0 + 8), int(sec_cy + 4), f"h = {h_mm:.0f} mm")
        painter.drawText(int(sec_cx - draw_b / 2.0), int(sec_cy + draw_h / 2.0 + 34), f"Stirrups: {stirrups}")

class BeamDiagramsViewWidget(QWidget):
    """
    Renders analytical Shear Force Diagram (SFD - Vu in kN) and
    Bending Moment Diagram (BMD - Mu in kN.m) with zero baselines,
    positive moment downward (tension face down), support markers,
    and critical peak annotations.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.beam_data: Optional[Dict[str, Any]] = None
        self.setMinimumHeight(340)
        self.setStyleSheet("background-color: #0B0F19;")

    def set_beam_analysis_data(self, beam_data: Optional[Dict[str, Any]]) -> None:
        self.beam_data = beam_data
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#0B0F19"))

        if not self.beam_data or "x_full" not in self.beam_data or len(self.beam_data["x_full"]) < 2:
            painter.setPen(QPen(QColor("#94A3B8"), 1))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            msg = "Select a beam and click 'Run Analysis & Design (F5)' to display SFD (Vu) & BMD (Mu) diagrams."
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
            return

        x_pts = self.beam_data["x_full"]
        v_pts = self.beam_data["v_full"]
        m_pts = self.beam_data["m_full"]
        beam_id = str(self.beam_data.get("beam_id", "Beam"))
        spans = self.beam_data.get("spans", [])

        x_min = min(x_pts)
        x_max = max(x_pts)
        L_total = max(1e-3, x_max - x_min)

        pad_left = 65
        pad_right = 35
        pad_top = 35
        pad_bottom = 25
        plot_w = max(10, w - pad_left - pad_right)

        half_h = (h - pad_top - pad_bottom - 20) / 2.0
        sfd_top = pad_top
        sfd_bot = sfd_top + half_h
        sfd_mid = (sfd_top + sfd_bot) / 2.0

        bmd_top = sfd_bot + 20
        bmd_bot = bmd_top + half_h
        bmd_mid = (bmd_top + bmd_bot) / 2.0

        def to_sx(x_val: float) -> float:
            return pad_left + ((x_val - x_min) / L_total) * plot_w

        # --- SFD (Vu) ---
        max_abs_v = max(abs(v) for v in v_pts) if v_pts else 1.0
        if max_abs_v < 1e-3:
            max_abs_v = 1.0
        v_scale = (half_h * 0.42) / max_abs_v

        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#38BDF8"))
        max_v = max(v_pts) if v_pts else 0.0
        min_v = min(v_pts) if v_pts else 0.0
        painter.drawText(
            pad_left, int(sfd_top - 12),
            f"Shear Force Diagram — {beam_id} [Vu, kN]  (Max +Vu = {max_v:.2f} kN, Max -Vu = {min_v:.2f} kN)"
        )

        painter.setPen(QPen(QColor("#475569"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(int(pad_left), int(sfd_mid), int(pad_left + plot_w), int(sfd_mid))
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor("#64748B"))
        painter.drawText(int(pad_left - 35), int(sfd_mid + 4), "0.0")

        sfd_poly = [QPointF(to_sx(x_pts[0]), sfd_mid)]
        for x, v in zip(x_pts, v_pts):
            sfd_poly.append(QPointF(to_sx(x), sfd_mid - v * v_scale))
        sfd_poly.append(QPointF(to_sx(x_pts[-1]), sfd_mid))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(6, 182, 212, 45)))
        painter.drawPolygon(QPolygonF(sfd_poly))

        painter.setPen(QPen(QColor("#06B6D4"), 2.0))
        for i in range(len(x_pts) - 1):
            p1 = QPointF(to_sx(x_pts[i]), sfd_mid - v_pts[i] * v_scale)
            p2 = QPointF(to_sx(x_pts[i + 1]), sfd_mid - v_pts[i + 1] * v_scale)
            painter.drawLine(p1, p2)

        # --- BMD (Mu) ---
        max_abs_m = max(abs(m) for m in m_pts) if m_pts else 1.0
        if max_abs_m < 1e-3:
            max_abs_m = 1.0
        m_scale = (half_h * 0.42) / max_abs_m

        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#F59E0B"))
        max_m = max(m_pts) if m_pts else 0.0
        min_m = min(m_pts) if m_pts else 0.0
        painter.drawText(
            pad_left, int(bmd_top - 12),
            f"Bending Moment Diagram — {beam_id} [Mu, kN.m]  (Max +Mu = {max_m:.2f} kN.m, Max -Mu = {min_m:.2f} kN.m [Tension Face Down])"
        )

        painter.setPen(QPen(QColor("#475569"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(int(pad_left), int(bmd_mid), int(pad_left + plot_w), int(bmd_mid))
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor("#64748B"))
        painter.drawText(int(pad_left - 35), int(bmd_mid + 4), "0.0")

        bmd_poly = [QPointF(to_sx(x_pts[0]), bmd_mid)]
        for x, m in zip(x_pts, m_pts):
            bmd_poly.append(QPointF(to_sx(x), bmd_mid + m * m_scale))
        bmd_poly.append(QPointF(to_sx(x_pts[-1]), bmd_mid))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(245, 158, 11, 45)))
        painter.drawPolygon(QPolygonF(bmd_poly))

        painter.setPen(QPen(QColor("#F59E0B"), 2.0))
        for i in range(len(x_pts) - 1):
            p1 = QPointF(to_sx(x_pts[i]), bmd_mid + m_pts[i] * m_scale)
            p2 = QPointF(to_sx(x_pts[i + 1]), bmd_mid + m_pts[i + 1] * m_scale)
            painter.drawLine(p1, p2)

        # Supports & ticks
        supp_xs = [0.0]
        cur_x = 0.0
        for s in spans:
            cur_x += float(s)
            supp_xs.append(cur_x)

        supp_pen = QPen(QColor("#EF4444"), 1.5)
        for sx_val in supp_xs:
            if sx_val <= x_max + 1e-4:
                px = to_sx(sx_val)
                painter.setPen(supp_pen)
                painter.setBrush(QBrush(QColor("#EF4444")))
                tri_s = QPolygonF([QPointF(px, sfd_mid), QPointF(px - 5, sfd_mid + 10), QPointF(px + 5, sfd_mid + 10)])
                painter.drawPolygon(tri_s)
                tri_m = QPolygonF([QPointF(px, bmd_mid), QPointF(px - 5, bmd_mid - 10), QPointF(px + 5, bmd_mid - 10)])
                painter.drawPolygon(tri_m)

        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        if max_m > 0.01:
            max_idx = m_pts.index(max(m_pts))
            peak_x = to_sx(x_pts[max_idx])
            peak_y = bmd_mid + max_m * m_scale
            painter.setPen(QColor("#FDE047"))
            painter.drawText(int(peak_x - 30), int(peak_y + 16), f"+{max_m:.2f}")

        if min_m < -0.01:
            min_idx = m_pts.index(min(m_pts))
            peak_x = to_sx(x_pts[min_idx])
            peak_y = bmd_mid + min_m * m_scale
            painter.setPen(QColor("#FDE047"))
            painter.drawText(int(peak_x - 30), int(peak_y - 8), f"{min_m:.2f}")


class StructuralCadCanvas2D(QGraphicsView):
    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self.scene_2d = QGraphicsScene(self)
        self.scene_2d.setSceneRect(-10000.0, -10000.0, 20000.0, 20000.0)
        self.setScene(self.scene_2d)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0D1117")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.scale_px = 48.0  # 1m = 48px
        self.active_tool = "SELECT"

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

        self.layer_show_arch = True
        self.layer_show_cols = True
        self.layer_show_beams = True
        self.layer_show_slabs = True
        self.layer_show_tags = True

        self._is_panning = False
        self._pan_start_pos = QPointF()
        self._key_buffer = ""

        self.selected_items: List[Tuple[str, str]] = []
        self._is_box_selecting = False
        self._box_start_world: Optional[Tuple[float, float]] = None
        self._box_current_world: Optional[Tuple[float, float]] = None

        self._polyline_pts: List[Tuple[float, float]] = []
        self._first_click_pt: Optional[Tuple[float, float]] = None
        self._current_snap_info: Optional[Dict[str, Any]] = None

        self._align_ref: Optional[Dict[str, Any]] = None

        self._measure_pts: List[Tuple[float, float]] = []
        self._last_measurement: Optional[Dict[str, Any]] = None

        self._zoom_win_start: Optional[Tuple[float, float]] = None
        self._zoom_win_curr: Optional[Tuple[float, float]] = None
        self._dim_first_pt: Optional[Tuple[float, float]] = None

        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

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
        elif self.active_tool in ("ROTATE_COL", "ALIGN_ELEMENT", "MOVE_ELEMENT", "FLIP_RIB", "PICK_SLAB", "PICK_OPENING"):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        elif self.active_tool in (
            "DRAW_COL", "DRAW_BEAM_HID", "DRAW_BEAM_DROP", "DRAW_SLAB_EDGE",
            "DIM_LINEAR", "DIM_ALIGNED", "MEASURE_DIST", "ZOOM_WINDOW",
        ):
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def zoom_extents(self) -> None:
        self.resetTransform()
        rect = self.scene_2d.itemsBoundingRect()
        if not rect.isNull() and rect.width() > 10 and rect.height() > 10:
            self.fitInView(rect.adjusted(-60, -60, 60, 60), Qt.AspectRatioMode.KeepAspectRatio)

    def _scene_to_world_m(self, scene_pt: QPointF) -> Tuple[float, float]:
        s = self.scale_px
        return round(scene_pt.x() / s, 3), round(-scene_pt.y() / s, 3)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        text = (event.text() or "").upper()

        if key == Qt.Key.Key_Space:
            if self.active_tool == "DRAW_COL":
                cur_idx = self.studio.cb_col_orient.currentIndex()
                new_idx = 1 if cur_idx == 0 else 0
                self.studio.cb_col_orient.setCurrentIndex(new_idx)
                self.render_story(self.studio.current_story_data)
                orient_txt = "Vertical (0.20x0.40m)" if new_idx == 0 else "Horizontal (0.40x0.20m)"
                self.studio.update_contextual_prompt(f"Column Orientation Flipped [Spacebar]: {orient_txt}")
                event.accept()
                return

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

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.studio.delete_selected_object()
            event.accept()
            return
        if key == Qt.Key.Key_R:
            self.studio.rotate_selected_or_default_column()
            event.accept()
            return
        if key == Qt.Key.Key_F3:
            self.studio.chk_osnap_master.setChecked(not self.studio.chk_osnap_master.isChecked())
            event.accept()
            return
        if key == Qt.Key.Key_F8:
            self.studio.chk_ortho_bar.setChecked(not self.studio.chk_ortho_bar.isChecked())
            event.accept()
            return
        if key == Qt.Key.Key_F9:
            self.studio.chk_grid_snap_bar.setChecked(not self.studio.chk_grid_snap_bar.isChecked())
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_C):
            if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
                self._finalize_polyline_boundary()
                event.accept()
                return
        if key == Qt.Key.Key_Escape:
            self._polyline_pts.clear()
            self._first_click_pt = None
            self._align_ref = None
            self._measure_pts.clear()
            self._dim_first_pt = None
            self._zoom_win_start = None
            self._zoom_win_curr = None
            self._is_box_selecting = False
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
        self.studio.update_contextual_prompt(
            f"Building Boundary Polyline closed ({n_verts} vertices, Zero auto-ribs). Now place Columns (Step 2) & Beams (Step 3)."
        )

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
            found = self._find_element_near(raw_x, raw_y)
            if found and self.active_tool == "SELECT":
                self._show_element_context_menu(found, event.globalPosition().toPoint())
                event.accept()
                return

            if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
                self._finalize_polyline_boundary()
            else:
                self._polyline_pts.clear()
                self._first_click_pt = None
                self._align_ref = None
                self._measure_pts.clear()
                self._dim_first_pt = None
                self._zoom_win_start = None
                self._zoom_win_curr = None
                self._is_box_selecting = False
                self.active_tool = "SELECT"
                self.update_cursor_for_active_tool()
                self.render_story(self.studio.current_story_data)
                self.studio.update_contextual_prompt("Ready (SELECT). Click element or drag Left->Right (Window) / Right->Left (Crossing).")
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            raw_x, raw_y = self._scene_to_world_m(scene_pt)

            if self.active_tool == "ZOOM_WINDOW":
                self._zoom_win_start = (raw_x, raw_y)
                self._zoom_win_curr = (raw_x, raw_y)
                self.render_story(self.studio.current_story_data)
                event.accept()
                return

            if self.active_tool == "ROTATE_COL":
                found = self._find_element_near(raw_x, raw_y)
                if found and found["kind"] == "column":
                    cid = str(found["id"])
                    ok, msg = rotate_column_90_deg(self.studio.current_story_data, cid)
                    if ok:
                        self.studio.save_and_sync_current_story()
                        self.studio.refresh_story_ui()
                        self.studio.update_contextual_prompt(f"Column {cid} rotated: {msg}")
                    else:
                        QMessageBox.warning(self, "Rotate Column Notice", msg)
                        self.studio.update_contextual_prompt(msg)
                else:
                    self.studio.update_contextual_prompt("Rotate Col [R]: Click directly on a Column (C#) to rotate it 90°.")
                event.accept()
                return

            snap = self.compute_osnap_point(raw_x, raw_y, self.studio.current_story_data)
            sx, sy = snap["x"], snap["y"]

            ref_pt = None
            if self.active_tool == "DRAW_SLAB_EDGE" and self._polyline_pts:
                ref_pt = self._polyline_pts[-1]
            elif self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT") and self._first_click_pt is not None:
                ref_pt = self._first_click_pt

            if self.ortho_enabled and ref_pt is not None and snap["snap_type"] != "POLY_CLOSE":
                fx, fy = ref_pt
                if abs(sx - fx) >= abs(sy - fy):
                    sy = fy
                else:
                    sx = fx

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
                        f"Selected ({len(self.selected_items)}): [{sel_str}] — Use Delete (Del), Move (MV), Align (AL), or Rotate (R)."
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

        if self.active_tool == "ZOOM_WINDOW" and self._zoom_win_start is not None:
            self._zoom_win_curr = (raw_x, raw_y)
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
        elif self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT") and self._first_click_pt is not None:
            ref_pt = self._first_click_pt
        elif self.active_tool in ("DIM_LINEAR", "DIM_ALIGNED") and self._dim_first_pt is not None:
            ref_pt = self._dim_first_pt

        if self.ortho_enabled and ref_pt is not None and snap["snap_type"] != "POLY_CLOSE":
            fx, fy = ref_pt
            if abs(snap["x"] - fx) >= abs(snap["y"] - fy):
                snap["y"] = fy
            else:
                snap["x"] = fx

        self._current_snap_info = snap
        self.studio.lbl_coords_bar.setText(f"X: {snap['x']:.2f} m, Y: {snap['y']:.2f} m | {snap['label']}")
        self.render_story(self.studio.current_story_data)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._is_panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._is_panning = False
            self.update_cursor_for_active_tool()
            event.accept()
            return

        if self.active_tool == "ZOOM_WINDOW" and self._zoom_win_start is not None and event.button() == Qt.MouseButton.LeftButton:
            x1, y1 = self._zoom_win_start
            scene_pt = self.mapToScene(event.position().toPoint())
            x2, y2 = self._scene_to_world_m(scene_pt)
            s = self.scale_px
            min_x, max_x = min(x1, x2), max(x1, x2)
            min_y, max_y = min(y1, y2), max(y1, y2)
            if (max_x - min_x) > 0.05 and (max_y - min_y) > 0.05:
                rect = QRectF(min_x * s, -max_y * s, (max_x - min_x) * s, (max_y - min_y) * s)
                self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_win_start = None
            self._zoom_win_curr = None
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

    def _show_element_context_menu(self, element: Dict[str, Any], global_pos) -> None:
        menu = QMenu(self)
        kind = element["kind"]
        eid = str(element["id"])

        if kind == "column":
            menu.addAction(f"Column: {eid}").setEnabled(False)
            menu.addSeparator()
            act_rot = menu.addAction("Rotate 90° (R)")
            act_rot.triggered.connect(lambda: self._context_rotate_col(eid))
            act_mv = menu.addAction("Move (MV)")
            act_mv.triggered.connect(lambda: self._context_start_move("column", eid))
            act_al = menu.addAction("Align Face (AL)")
            act_al.triggered.connect(lambda: self._context_start_align("column", eid))
            menu.addSeparator()
            act_del = menu.addAction("Delete Column (Del)")
            act_del.triggered.connect(lambda: self._context_delete("column", eid))

        elif kind == "beam":
            bm = next((b for b in self.studio.current_story_data.get("beams", []) if b["id"] == eid), None)
            b_kind = bm.get("beam_kind", "hidden") if bm else "hidden"
            menu.addAction(f"Beam: {eid} ({b_kind.upper()})").setEnabled(False)
            menu.addSeparator()
            if b_kind == "hidden":
                act_conv = menu.addAction("Convert to Drop Beam (0.20×0.50m)")
                act_conv.triggered.connect(lambda: self._context_convert_beam(eid, "drop", 0.20, 0.50))
            else:
                act_conv = menu.addAction("Convert to Hidden Beam (0.40×0.30m)")
                act_conv.triggered.connect(lambda: self._context_convert_beam(eid, "hidden", 0.40, 0.30))
            act_wall = menu.addAction("Toggle Wall Load for Beam")
            act_wall.triggered.connect(lambda: self._context_toggle_beam_wall(eid))
            menu.addSeparator()
            act_open_an = menu.addAction("Open in Beam Analysis (SFD & BMD)")
            act_open_an.triggered.connect(lambda: self._context_open_analysis(eid))
            act_open_des = menu.addAction("Open in Beam R.C. Design")
            act_open_des.triggered.connect(lambda: self._context_open_design(eid))
            menu.addSeparator()
            act_mv = menu.addAction("Move (MV)")
            act_mv.triggered.connect(lambda: self._context_start_move("beam", eid))
            act_al = menu.addAction("Align Face (AL)")
            act_al.triggered.connect(lambda: self._context_start_align("beam", eid))
            act_del = menu.addAction("Delete Beam (Del)")
            act_del.triggered.connect(lambda: self._context_delete("beam", eid))

        elif kind == "slab":
            menu.addAction(f"Slab: {eid}").setEnabled(False)
            menu.addSeparator()
            act_flip = menu.addAction("Flip Rib Direction (0° ↔ 90°)")
            act_flip.triggered.connect(lambda: self._context_flip_rib(eid))
            act_op = menu.addAction("Convert to Opening")
            act_op.triggered.connect(lambda: self._context_convert_slab_to_opening(eid))
            menu.addSeparator()
            act_del = menu.addAction("Delete Slab (Del)")
            act_del.triggered.connect(lambda: self._context_delete("slab", eid))

        menu.exec(global_pos)

    def _context_rotate_col(self, col_id: str) -> None:
        ok, msg = rotate_column_90_deg(self.studio.current_story_data, col_id)
        if ok:
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(msg)

    def _context_convert_beam(self, beam_id: str, new_kind: str, new_w: float, new_d: float) -> None:
        ok, msg = convert_beam_kind_and_section(self.studio.current_story_data, beam_id, new_kind, new_w, new_d)
        if ok:
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(msg)

    def _context_toggle_beam_wall(self, beam_id: str) -> None:
        bm = next((b for b in self.studio.current_story_data.get("beams", []) if b["id"] == beam_id), None)
        if not bm:
            return
        flags = ensure_beam_wall_flags(self.studio.current_story_data, bm)
        cur_any = any(flags.values())
        new_val = not cur_any
        for k in flags:
            flags[k] = new_val
        self.studio.save_and_sync_current_story()
        self.studio.refresh_story_ui()
        self.studio.update_contextual_prompt(f"Wall load for beam {beam_id} set to {'ENABLED (12 kN/m)' if new_val else 'DISABLED (0 kN/m)'}.")

    def _context_open_analysis(self, beam_id: str) -> None:
        self.studio.switch_workspace_mode(1)
        idx = self.studio.cb_analysis_beam.findText(beam_id)
        if idx >= 0:
            self.studio.cb_analysis_beam.setCurrentIndex(idx)

    def _context_open_design(self, beam_id: str) -> None:
        self.studio.switch_workspace_mode(2)
        idx = self.studio.cb_design_beam.findText(beam_id)
        if idx >= 0:
            self.studio.cb_design_beam.setCurrentIndex(idx)

    def _context_flip_rib(self, slab_id: str) -> None:
        for slb in self.studio.current_story_data.get("slabs", []):
            if str(slb.get("id")) == str(slab_id):
                cur_deg = int(slb.get("rib_direction_deg", 0))
                slb["rib_direction_deg"] = 90 if cur_deg == 0 else 0
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(f"Slab {slab_id} rib direction flipped to {slb['rib_direction_deg']}°.")
                break

    def _context_convert_slab_to_opening(self, slab_id: str) -> None:
        slabs = self.studio.current_story_data.get("slabs", [])
        slb = next((s for s in slabs if str(s.get("id")) == str(slab_id)), None)
        if slb:
            slabs.remove(slb)
            openings = self.studio.current_story_data.setdefault("openings", [])
            openings.append({
                "id": f"OP{len(openings)+1}",
                "min_x": slb["min_x"], "max_x": slb["max_x"],
                "min_y": slb["min_y"], "max_y": slb["max_y"],
            })
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(f"Slab {slab_id} converted to Opening OP{len(openings)}.")

    def _context_start_move(self, kind: str, eid: str) -> None:
        self.selected_items = [(kind, eid)]
        self.studio.activate_cad_tool("MOVE_ELEMENT")

    def _context_start_align(self, kind: str, eid: str) -> None:
        self.selected_items = [(kind, eid)]
        self.studio.activate_cad_tool("ALIGN_ELEMENT")

    def _context_delete(self, kind: str, eid: str) -> None:
        self.selected_items = [(kind, eid)]
        self.studio.delete_selected_object()

    def _find_element_near(self, wx: float, wy: float) -> Optional[Dict[str, Any]]:
        story = self.studio.current_story_data
        if self.layer_show_cols:
            for col in story.get("columns", []):
                if not col.get("active", True):
                    continue
                if math.hypot(wx - float(col["x"]), wy - float(col["y"])) <= 0.38:
                    return {"kind": "column", "id": col["id"]}
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
                        return {"kind": "beam", "id": bm["id"]}
        if self.layer_show_slabs:
            for op in story.get("openings", []):
                if float(op["min_x"]) <= wx <= float(op["max_x"]) and float(op["min_y"]) <= wy <= float(op["max_y"]):
                    return {"kind": "opening", "id": op["id"]}
            for slb in story.get("slabs", []):
                if "min_x" in slb and float(slb["min_x"]) <= wx <= float(slb["max_x"]) and float(slb["min_y"]) <= wy <= float(slb["max_y"]):
                    return {"kind": "slab", "id": slb["id"]}
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
                    f"Align [AL] Step 2: Reference locked to [{ref['label']}]. Now click the Column or Beam Face you want to align to it!"
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

        if tool in ("DIM_LINEAR", "DIM_ALIGNED"):
            if self._dim_first_pt is None:
                self._dim_first_pt = (sx, sy)
                self.render_story(story)
                self.studio.update_contextual_prompt(f"{tool}: Point 1 set at ({sx:.2f}, {sy:.2f}). Click second point to place dimension...")
            else:
                p1 = self._dim_first_pt
                p2 = (sx, sy)
                dim_type = "linear" if tool == "DIM_LINEAR" else "aligned"
                dim_obj = create_linear_dimension(story, p1, p2, offset_m=0.65, dim_kind=dim_type)
                self._dim_first_pt = None
                self.studio.save_and_sync_current_story()
                self.render_story(story)
                self.studio.update_contextual_prompt(f"Created Dimension {dim_obj['id']} ({dim_obj['text']}). Click next point or right-click to finish.")
            return

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
                f"{'Click V1 or Press Enter to Close Boundary (Zero auto-ribs).' if n_pts >= 3 else 'Click next vertex or type X,Y in Command Bar...'}"
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

        has_bnd, _, _, _, _ = get_slab_bounding_box(story.get("slab_edge_polygon", []))
        if not has_bnd and tool != "SELECT":
            QMessageBox.warning(
                self,
                "Step 1 Required: Draw Building Boundary Polyline First",
                "Please draw the Outer Building Boundary Polyline (00-XD-EDGE) first before placing columns, beams, or slabs.",
            )
            return

        if tool == "DRAW_COL":
            cols = story.setdefault("columns", [])
            is_vert = self.studio.cb_col_orient.currentIndex() == 0
            b_m = 0.20 if is_vert else 0.40
            h_m = 0.40 if is_vert else 0.20
            boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            next_id = f"C{len(cols) + 1}"
            new_col = {
                "id": next_id,
                "x": sx,
                "y": sy,
                "b_m": b_m,
                "h_m": h_m,
                "active": True,
                "moves_with_grids": self.studio.chk_col_moves_grids.isChecked(),
                "room_bounding": self.studio.chk_col_room_bounding.isChecked(),
            }
            updated_col, updated_poly, msg = enforce_column_inside_slab_boundary(
                new_col, story["slab_edge_polygon"], mode=boundary_mode
            )
            dup_id = check_duplicate_column(updated_col["x"], updated_col["y"], b_m, h_m, cols)
            if dup_id:
                self.studio.update_contextual_prompt(
                    f"Duplicate Column Prevented: Column {dup_id} already exists at ({updated_col['x']:.2f}, {updated_col['y']:.2f})."
                )
                return
            story["slab_edge_polygon"] = updated_poly
            cols.append(updated_col)
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(f"Placed Column {next_id} ({b_m:.2f}x{h_m:.2f} m): {msg}")
            return

        if tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP"):
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
                b_kind = "hidden" if tool == "DRAW_BEAM_HID" else "drop"
                w_m = 0.40 if b_kind == "hidden" else 0.20
                d_m = round(self.studio.sp_adopted_thick.value() / 100.0, 2) if b_kind == "hidden" else 0.50
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
                )
                self._first_click_pt = None
                if not ok or bm_obj is None:
                    QMessageBox.warning(self, "Beam Geometric Rule Violation", msg)
                    self.studio.update_contextual_prompt(f"Rejected Beam: {msg}")
                    self.render_story(story)
                    return
                beams.append(bm_obj)
                split_n, split_msg = reconcile_and_split_slabs_after_beam_change(story)
                if split_msg:
                    msg = f"{msg} | {split_msg}"
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.update_contextual_prompt(msg)
            return

        if tool in ("PICK_SLAB", "PICK_OPENING"):
            mode_str = "SLAB" if tool == "PICK_SLAB" else "TOGGLE_OPENING"
            ok, msg, _ = pick_area_create_or_update_slab(
                story, raw_x, raw_y, target_mode=mode_str
            )
            if not ok:
                QMessageBox.warning(self, "Pick Area / Cantilever Rule", msg)
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.update_contextual_prompt(msg)
            return

        if tool == "MOVE_ELEMENT":
            if not self.selected_items:
                found = self._find_element_near(raw_x, raw_y)
                if not found or found["kind"] not in ("column", "beam"):
                    self.studio.update_contextual_prompt(
                        "Move [MV]: First click on a Column or Beam to select it (or select multiple in SELECT mode)."
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

    def render_story(self, story_data: Dict[str, Any]) -> None:
        self.scene_2d.clear()
        s = self.scale_px

        grid_pen = QPen(QColor("#161F2C"), 1, Qt.PenStyle.DotLine)
        for gx in range(-30, 53):
            self.scene_2d.addLine(gx * s, -52 * s, gx * s, 30 * s, grid_pen)
        for gy in range(-30, 53):
            self.scene_2d.addLine(-30 * s, -gy * s, 52 * s, -gy * s, grid_pen)

        arch_block = story_data.get("arch_underlay_block")
        if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
            arch_pen = QPen(QColor("#475569"), 1.1)
            for seg in arch_block.get("segments", []):
                self.scene_2d.addLine(
                    float(seg[0]) * s, -float(seg[1]) * s,
                    float(seg[2]) * s, -float(seg[3]) * s,
                    arch_pen,
                )

        edge = story_data.get("slab_edge_polygon", [])
        if len(edge) >= 3:
            is_sel_edge = ("slab_edge", "00-XD-EDGE") in self.selected_items
            edge_pen = QPen(QColor("#F8FAFC" if is_sel_edge else "#06B6D4"), 3.0 if is_sel_edge else 2.2)
            poly = QPolygonF([QPointF(float(p[0]) * s, -float(p[1]) * s) for p in edge])
            self.scene_2d.addPolygon(poly, edge_pen, QBrush(QColor(6, 182, 212, 8)))

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

            for op in story_data.get("openings", []):
                min_x, max_x = float(op["min_x"]), float(op["max_x"])
                min_y, max_y = float(op["min_y"]), float(op["max_y"])
                rect = QRectF(min_x * s, -max_y * s, (max_x - min_x) * s, (max_y - min_y) * s)
                is_sel_op = ("opening", str(op.get("id"))) in self.selected_items
                open_pen = QPen(QColor("#F8FAFC" if is_sel_op else "#EC4899"), 2.5 if is_sel_op else 2)
                self.scene_2d.addRect(rect, open_pen, QBrush(QColor(236, 72, 153, 35)))
                self.scene_2d.addLine(min_x * s, -min_y * s, max_x * s, -max_y * s, open_pen)
                self.scene_2d.addLine(min_x * s, -max_y * s, max_x * s, -min_y * s, open_pen)

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
                    tx, ty, _ = compute_smart_beam_tag_position(bm, columns, placed_tags)
                    txt = self.scene_2d.addText(f"{bm['id']}", QFont("Arial", 9, QFont.Weight.Bold))
                    txt.setDefaultTextColor(QColor("#FB923C"))
                    txt.setPos(tx * s - 10, -ty * s - 12)

        # Live Column Preview in DRAW_COL mode
        if self.active_tool == "DRAW_COL" and self._current_snap_info is not None:
            cx = float(self._current_snap_info["x"])
            cy = float(self._current_snap_info["y"])
            is_vert = self.studio.cb_col_orient.currentIndex() == 0
            b_m = 0.20 if is_vert else 0.40
            h_m = 0.40 if is_vert else 0.20
            prev_rect = QRectF((cx - b_m / 2.0) * s, -(cy + h_m / 2.0) * s, b_m * s, h_m * s)
            self.scene_2d.addRect(
                prev_rect,
                QPen(QColor("#38BDF8"), 1.8, Qt.PenStyle.DashLine),
                QBrush(QColor(56, 189, 248, 70)),
            )

        if self.layer_show_cols:
            for col in columns:
                if not col.get("active", True):
                    continue
                cx, cy = float(col["x"]), float(col["y"])
                b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
                is_sel_col = ("column", str(col.get("id"))) in self.selected_items
                rect = QRectF((cx - b / 2.0) * s, -(cy + h / 2.0) * s, b * s, h * s)
                col_pen = QPen(QColor("#38BDF8" if is_sel_col else "#EF4444"), 2.8 if is_sel_col else 2)
                self.scene_2d.addRect(rect, col_pen, QBrush(QColor(56, 189, 248, 160) if is_sel_col else QColor(239, 68, 68, 125)))

                if self.layer_show_tags:
                    tag_x = cx + b / 2.0 + 0.10
                    tag_y = cy + h / 2.0 + 0.10
                    ctxt = self.scene_2d.addText(str(col["id"]), QFont("Arial", 9, QFont.Weight.Bold))
                    ctxt.setDefaultTextColor(QColor("#4ADE80"))
                    ctxt.setPos(tag_x * s, -tag_y * s - 10)

        if self._align_ref is not None:
            ref_pen = QPen(QColor("#22D3EE"), 2.5, Qt.PenStyle.DashDotLine)
            rc = self._align_ref["coord"]
            if self._align_ref["axis"] == "x":
                self.scene_2d.addLine(rc * s, -14 * s, rc * s, 2 * s, ref_pen)
            else:
                self.scene_2d.addLine(-2 * s, -rc * s, 18 * s, -rc * s, ref_pen)



                # Persistent CAD Dimensions (00-XD-DIM)
        for dim in story_data.get("dimensions", []):
            x1, y1 = float(dim.get("x1", 0.0)), float(dim.get("y1", 0.0))
            x2, y2 = float(dim.get("x2", 0.0)), float(dim.get("y2", 0.0))
            off = float(dim.get("offset_m", 0.65))
            dx, dy = x2 - x1, y2 - y1
            L = max(1e-6, math.hypot(dx, dy))
            nx, ny = -dy / L, dx / L
            ox1, oy1 = x1 + nx * off, y1 + ny * off
            ox2, oy2 = x2 + nx * off, y2 + ny * off

            dim_pen = QPen(QColor("#38BDF8"), 1.2)
            ext_pen = QPen(QColor("#64748B"), 1.0, Qt.PenStyle.DashLine)

            self.scene_2d.addLine(x1 * s, -y1 * s, (ox1 + nx * 0.15) * s, -(oy1 + ny * 0.15) * s, ext_pen)
            self.scene_2d.addLine(x2 * s, -y2 * s, (ox2 + nx * 0.15) * s, -(oy2 + ny * 0.15) * s, ext_pen)
            self.scene_2d.addLine(ox1 * s, -oy1 * s, ox2 * s, -oy2 * s, dim_pen)

            tick_len = 0.12
            tx, ty = (dx / L) * tick_len, (dy / L) * tick_len
            tnx, tny = nx * tick_len, ny * tick_len
            self.scene_2d.addLine((ox1 - tx - tnx) * s, -(oy1 - ty - tny) * s, (ox1 + tx + tnx) * s, -(oy1 + ty + tny) * s, dim_pen)
            self.scene_2d.addLine((ox2 - tx - tnx) * s, -(oy2 - ty - tny) * s, (ox2 + tx + tnx) * s, -(oy2 + ty + tny) * s, dim_pen)

            mx, my = (ox1 + ox2) / 2.0 + nx * 0.15, (oy1 + oy2) / 2.0 + ny * 0.15
            txt_str = dim.get("text", f"{L:.2f} m")
            d_txt = self.scene_2d.addText(txt_str, QFont("Arial", 8, QFont.Weight.Bold))
            d_txt.setDefaultTextColor(QColor("#E0F2FE"))
            d_txt.setPos(mx * s - 20, -my * s - 10)

        if self.active_tool in ("DIM_LINEAR", "DIM_ALIGNED") and self._dim_first_pt is not None and self._current_snap_info is not None:
            p1x, p1y = self._dim_first_pt
            p2x, p2y = self._current_snap_info["x"], self._current_snap_info["y"]
            self.scene_2d.addLine(p1x * s, -p1y * s, p2x * s, -p2y * s, QPen(QColor("#38BDF8"), 1.5, Qt.PenStyle.DashLine))

        if self.active_tool == "ZOOM_WINDOW" and self._zoom_win_start and self._zoom_win_curr:
            zx1, zy1 = self._zoom_win_start
            zx2, zy2 = self._zoom_win_curr
            zmin_x, zmax_x = min(zx1, zx2), max(zx1, zx2)
            zmin_y, zmax_y = min(zy1, zy2), max(zy1, zy2)
            zrect = QRectF(zmin_x * s, -zmax_y * s, (zmax_x - zmin_x) * s, (zmax_y - zmin_y) * s)
            self.scene_2d.addRect(zrect, QPen(QColor("#818CF8"), 1.8, Qt.PenStyle.DashLine), QBrush(QColor(99, 102, 241, 30)))

        if self._last_measurement is not None:
            p1, p2 = self._last_measurement["p1"], self._last_measurement["p2"]
            dim_pen = QPen(QColor("#A855F7"), 2.2, Qt.PenStyle.DashLine)
            self.scene_2d.addLine(p1[0] * s, -p1[1] * s, p2[0] * s, -p2[1] * s, dim_pen)
            mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
            d_txt = self.scene_2d.addText(
                f"L = {self._last_measurement['distance_m']:.2f} m (ΔX={self._last_measurement['dx_m']:+.2f}, ΔY={self._last_measurement['dy_m']:+.2f})",
                QFont("Arial", 9, QFont.Weight.Bold),
            )
            d_txt.setDefaultTextColor(QColor("#E9D5FF"))
            d_txt.setPos(mx * s - 45, -my * s - 22)

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

        if self._first_click_pt is not None and self._current_snap_info is not None and self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT"):
            fx, fy = self._first_click_pt
            tx, ty = self._current_snap_info["x"], self._current_snap_info["y"]
            self.scene_2d.addLine(fx * s, -fy * s, tx * s, -ty * s, QPen(QColor("#38BDF8"), 1.8, Qt.PenStyle.DashLine))

        if self._current_snap_info is not None and self.osnap_enabled:
            ox, oy = self._current_snap_info["x"], self._current_snap_info["y"]
            stype = self._current_snap_info["snap_type"]
            if stype not in ("GRID", "FREE"):
                marker_rect = QRectF(ox * s - 5, -oy * s - 5, 10, 10)
                self.scene_2d.addRect(marker_rect, QPen(QColor("#FACC15"), 2), QBrush(Qt.BrushStyle.NoBrush))



StructuralCanvas2DView = StructuralCadCanvas2D

class XpertStudioMainWindow(QMainWindow):
    def __init__(self, initial_master_project: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.setWindowTitle(f"Xpert Structural Design Studio — {STUDIO_VERSION} (ACI 318-19)")
        self.resize(1580, 950)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.master_project: Optional[Dict[str, Any]] = initial_master_project
        self.current_story_index: int = 0
        self.current_story_data: Dict[str, Any] = {}
        self.last_analysis_bundle: Optional[Dict[str, Any]] = None

        self._build_classic_menu_bar()
        self._build_classic_toolbars()
        self._build_main_workspace()

        if self.master_project is not None:
            self._populate_story_selector()
            self.update_contextual_prompt(
                f"Loaded Project: {self.master_project.get('project_name')} ({self.master_project.get('master_file', '')}) — Opened on Ground Floor."
            )

    def _build_classic_menu_bar(self) -> None:
        mbar = self.menuBar()

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

        m_modify = mbar.addMenu("&Modify")
        act_align = QAction("Align Element Face to Edge (AL)", self)
        act_align.triggered.connect(lambda: self.activate_cad_tool("ALIGN_ELEMENT"))
        m_modify.addAction(act_align)

        act_move_pt = QAction("Move Selected by Base-Point -> Second-Point (MV)", self)
        act_move_pt.triggered.connect(lambda: self.activate_cad_tool("MOVE_ELEMENT"))
        m_modify.addAction(act_move_pt)

        act_move_num = QAction("Move Selected by Numeric ΔX, ΔY Dialog...", self)
        act_move_num.triggered.connect(self.open_numeric_move_dialog)
        m_modify.addAction(act_move_num)

        act_meas = QAction("Measure Distance && Angle (DI)", self)
        act_meas.triggered.connect(lambda: self.activate_cad_tool("MEASURE_DIST"))
        m_modify.addAction(act_meas)

        act_rot_col = QAction("Rotate Selected Column 90° (R)", self)
        act_rot_col.setShortcut("R")
        act_rot_col.triggered.connect(self.rotate_selected_or_default_column)
        m_modify.addAction(act_rot_col)

        act_del = QAction("Delete Selected Elements (Del)", self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(self.delete_selected_object)
        m_modify.addAction(act_del)

        m_view = mbar.addMenu("&View")
        act_zext = QAction("Zoom Extents", self)
        act_zext.triggered.connect(lambda: self.cad_canvas.zoom_extents())
        m_view.addAction(act_zext)

        m_draw = mbar.addMenu("&Draw")
        for label, tool_id in [
            ("Select / Box-Select Elements (Arrow)", "SELECT"),
            ("Pan View (Hand Cursor)", "PAN"),
            ("Step 1: Draw Building Boundary Polyline (00-XD-EDGE)", "DRAW_SLAB_EDGE"),
            ("Step 2: Place Structural Column 0.20x0.40m (00-XD-COL)", "DRAW_COL"),
            ("Step 3A: Draw Hidden Beam 0.40m Width (Full Column Bearing)", "DRAW_BEAM_HID"),
            ("Step 3B: Draw Drop Beam 0.20m Width (Full Column Bearing)", "DRAW_BEAM_DROP"),
            ("Step 4A: Pick Area -> Create Slab", "PICK_SLAB"),
            ("Step 4B: Pick Area -> Toggle Void Opening", "PICK_OPENING"),
            ("Productivity: Auto-Fill All Story Slabs (1-Click)", "AUTO_FILL_SLABS"),
            ("Productivity: Convert Columns from Imported Arch .DXF", "CONVERT_ARCH_COLS"),
            ("Load Standard 2-Bay Structural Layout", "LOAD_TEMPLATE"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, tid=tool_id: self.activate_cad_tool(tid))
            m_draw.addAction(act)

        m_analyze = mbar.addMenu("&Analyze && Design")
        act_all = QAction("Analyze All Beams && Columns (F5)", self)
        act_all.setShortcut("F5")
        act_all.triggered.connect(self.run_analyze_all_beams)
        m_analyze.addAction(act_all)

    def _build_classic_toolbars(self) -> None:
        # Row 1: Project & Workspace Toolbar
        row1_tb = QToolBar("Project & Workspace Bar", self)
        row1_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, row1_tb)

        btn_new = QPushButton("New Project")
        btn_new.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_new.clicked.connect(self.open_new_project_dialog)
        row1_tb.addWidget(btn_new)

        btn_open = QPushButton(f"Open (*{MASTER_FILE_EXT})")
        btn_open.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_open.clicked.connect(self.open_existing_project_file_dialog)
        row1_tb.addWidget(btn_open)

        btn_imp_dxf = QPushButton("Import Arch .DXF")
        btn_imp_dxf.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_imp_dxf.clicked.connect(self.import_arch_dxf_for_current_story)
        row1_tb.addWidget(btn_imp_dxf)

        btn_save = QPushButton("Save && Sync (Ctrl+S)")
        btn_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_save.clicked.connect(self.save_and_sync_current_story)
        row1_tb.addWidget(btn_save)
        row1_tb.addSeparator()

        row1_tb.addWidget(QLabel(" Story: "))
        self.cb_story = QComboBox()
        self.cb_story.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_story.setMinimumWidth(210)
        self.cb_story.currentIndexChanged.connect(self._on_story_changed)
        row1_tb.addWidget(self.cb_story)
        row1_tb.addSeparator()

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
                "QPushButton { padding: 5px 12px; font-weight: bold; border: 1px solid #334155; background: #1E293B; color: #E2E8F0; } "
                "QPushButton:checked { background: #0284C7; color: white; border-color: #38BDF8; }"
            )
            b.clicked.connect(lambda checked=False, i=idx: self.switch_workspace_mode(i))
            self.view_btn_group.addButton(b, idx)
            row1_tb.addWidget(b)

        row1_tb.addSeparator()
        btn_run_all = QPushButton("Run Analysis && Design (F5)")
        btn_run_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_run_all.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px;")
        btn_run_all.clicked.connect(self.run_analyze_all_beams)
        row1_tb.addWidget(btn_run_all)

        # Break to Row 2
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        # Row 2 Toolbar A: Modify Toolbar
        self.mod_tb = QToolBar("Modify Tools", self)
        self.mod_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.mod_tb)

        btn_sel = QPushButton("Select")
        btn_sel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_sel.clicked.connect(lambda: self.activate_cad_tool("SELECT"))
        self.mod_tb.addWidget(btn_sel)

        btn_al = QPushButton("Align (AL)")
        btn_al.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_al.setStyleSheet("background-color: #0D9488; color: white; font-weight: bold;")
        btn_al.clicked.connect(lambda: self.activate_cad_tool("ALIGN_ELEMENT"))
        self.mod_tb.addWidget(btn_al)

        btn_mv = QPushButton("Move (MV)")
        btn_mv.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_mv.clicked.connect(lambda: self.activate_cad_tool("MOVE_ELEMENT"))
        self.mod_tb.addWidget(btn_mv)

        btn_mvd = QPushButton("Move ΔX,ΔY")
        btn_mvd.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_mvd.clicked.connect(self.open_numeric_move_dialog)
        self.mod_tb.addWidget(btn_mvd)

        btn_rot = QPushButton("Rotate Col 90° (R)")
        btn_rot.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_rot.clicked.connect(lambda: self.activate_cad_tool("ROTATE_COL"))
        self.mod_tb.addWidget(btn_rot)

        btn_del = QPushButton("Delete (Del)")
        btn_del.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_del.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold;")
        btn_del.clicked.connect(self.delete_selected_object)
        self.mod_tb.addWidget(btn_del)

        # Row 2 Toolbar B: Dimensions Toolbar
        self.dim_tb = QToolBar("Dimensions Tools", self)
        self.dim_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.dim_tb)

        btn_dim_lin = QPushButton("Linear Dim")
        btn_dim_lin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_dim_lin.setStyleSheet("background-color: #1E293B; color: #38BDF8; font-weight: bold; border: 1px solid #0284C7;")
        btn_dim_lin.clicked.connect(lambda: self.activate_cad_tool("DIM_LINEAR"))
        self.dim_tb.addWidget(btn_dim_lin)

        btn_dim_aln = QPushButton("Aligned Dim")
        btn_dim_aln.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_dim_aln.setStyleSheet("background-color: #1E293B; color: #38BDF8; font-weight: bold; border: 1px solid #0284C7;")
        btn_dim_aln.clicked.connect(lambda: self.activate_cad_tool("DIM_ALIGNED"))
        self.dim_tb.addWidget(btn_dim_aln)

        btn_auto_dims = QPushButton("Auto Exterior Dims")
        btn_auto_dims.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_auto_dims.setStyleSheet("background-color: #0369A1; color: white; font-weight: bold;")
        btn_auto_dims.clicked.connect(self.generate_exterior_dimensions)
        self.dim_tb.addWidget(btn_auto_dims)

        btn_meas = QPushButton("Measure (DI)")
        btn_meas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_meas.clicked.connect(lambda: self.activate_cad_tool("MEASURE_DIST"))
        self.dim_tb.addWidget(btn_meas)

        btn_clr_dims = QPushButton("Clear Dims")
        btn_clr_dims.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_clr_dims.clicked.connect(self.clear_all_dimensions)
        self.dim_tb.addWidget(btn_clr_dims)

        # Row 2 Toolbar C: Zoom & View Toolbar
        self.zoom_tb = QToolBar("Zoom & View Tools", self)
        self.zoom_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.zoom_tb)

        btn_zwin = QPushButton("Zoom Win")
        btn_zwin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_zwin.setStyleSheet("background-color: #4338CA; color: white; font-weight: bold;")
        btn_zwin.clicked.connect(lambda: self.activate_cad_tool("ZOOM_WINDOW"))
        self.zoom_tb.addWidget(btn_zwin)

        btn_zext = QPushButton("Zoom Extents")
        btn_zext.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_zext.clicked.connect(lambda: self.activate_cad_tool("ZOOM_EXTENTS"))
        self.zoom_tb.addWidget(btn_zext)

        btn_pan = QPushButton("Pan")
        btn_pan.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_pan.clicked.connect(lambda: self.activate_cad_tool("PAN"))
        self.zoom_tb.addWidget(btn_pan)

        btn_zin = QPushButton("Zoom +")
        btn_zin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_zin.clicked.connect(lambda: self.activate_cad_tool("ZOOM_IN"))
        self.zoom_tb.addWidget(btn_zin)

        btn_zout = QPushButton("Zoom -")
        btn_zout.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_zout.clicked.connect(lambda: self.activate_cad_tool("ZOOM_OUT"))
        self.zoom_tb.addWidget(btn_zout)

        # Left Toolbar: Structural BIM Modeling Tools
        self.left_tb = QToolBar("BIM Modeling Tools", self)
        self.left_tb.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.left_tb)

        for label, tid in [
            ("1. Polyline Boundary", "DRAW_SLAB_EDGE"),
            ("2. Place Column", "DRAW_COL"),
            ("3A. + Hidden Beam", "DRAW_BEAM_HID"),
            ("3B. + Drop Beam", "DRAW_BEAM_DROP"),
            ("4A. Pick: Slab", "PICK_SLAB"),
            ("4B. Pick: Flip Rib", "FLIP_RIB"),
            ("4C. Pick: Opening", "PICK_OPENING"),
            ("Auto-Fill All Slabs", "AUTO_FILL_SLABS"),
            ("Demo Layout", "LOAD_TEMPLATE"),
        ]:
            btn = QPushButton(label)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if tid == "AUTO_FILL_SLABS":
                btn.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold;")
                btn.clicked.connect(lambda: self.activate_cad_tool("AUTO_FILL_SLABS"))
            else:
                btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            self.left_tb.addWidget(btn)

    def _build_main_workspace(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setSpacing(3)
        vbox.setContentsMargins(4, 4, 4, 4)

        self.ctx_frame = QFrame()
        self.ctx_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.ctx_frame.setStyleSheet("background-color: #0F172A; color: #F8FAFC; border: 1px solid #334155;")
        ctx_row = QHBoxLayout(self.ctx_frame)
        ctx_row.setContentsMargins(8, 4, 8, 4)

        self.lbl_ctx_prompt = QLabel(
            "Ready (SELECT): Click any element, or drag Left->Right (Window) / Right->Left (Crossing). Press Spacebar in Place Column."
        )
        self.lbl_ctx_prompt.setStyleSheet("color: #38BDF8; font-weight: bold;")
        ctx_row.addWidget(self.lbl_ctx_prompt, 1)

        ctx_row.addWidget(QLabel("Col Section:"))
        self.cb_col_orient = QComboBox()
        self.cb_col_orient.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_col_orient.addItems(["Vertical (0.20×0.40m)", "Horizontal (0.40×0.20m)"])
        ctx_row.addWidget(self.cb_col_orient)

        self.chk_col_moves_grids = QCheckBox("Moves with Grids")
        self.chk_col_moves_grids.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_col_moves_grids.setChecked(True)
        ctx_row.addWidget(self.chk_col_moves_grids)

        self.chk_col_room_bounding = QCheckBox("Room Bounding")
        self.chk_col_room_bounding.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_col_room_bounding.setChecked(True)
        ctx_row.addWidget(self.chk_col_room_bounding)

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

        self.thick_frame = QFrame()
        self.thick_frame.setFrameShape(QFrame.Shape.StyledPanel)
        thick_row = QHBoxLayout(self.thick_frame)
        thick_row.setContentsMargins(8, 2, 8, 2)

        self.lbl_calc_thick = QLabel("Calculated Min. Thickness: --")
        self.lbl_calc_thick.setStyleSheet("font-weight: bold; color: #0284C7;")
        self.lbl_gov_member = QLabel("Governing Member: None")
        self.lbl_gov_member.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.sp_adopted_thick = QDoubleSpinBox()
        self.sp_adopted_thick.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sp_adopted_thick.setRange(14.0, 100.0)
        self.sp_adopted_thick.setValue(30.0)
        self.sp_adopted_thick.setSuffix(" cm")

        btn_apply_thick = QPushButton("Apply Thickness")
        btn_apply_thick.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_apply_thick.clicked.connect(self.apply_story_thickness)

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
        thick_row.addWidget(btn_apply_thick)
        thick_row.addSpacing(12)

        thick_row.addWidget(QLabel("Layers:"))
        self.chk_layer_arch = QCheckBox("Arch DXF")
        self.chk_layer_arch.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_layer_arch.setChecked(True)
        self.chk_layer_arch.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_arch)

        self.chk_layer_cols = QCheckBox("Columns")
        self.chk_layer_cols.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_layer_cols.setChecked(True)
        self.chk_layer_cols.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_cols)

        self.chk_layer_beams = QCheckBox("Beams")
        self.chk_layer_beams.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_layer_beams.setChecked(True)
        self.chk_layer_beams.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_beams)

        self.chk_layer_slabs = QCheckBox("Slabs && Ribs")
        self.chk_layer_slabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_layer_slabs.setChecked(True)
        self.chk_layer_slabs.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_slabs)

        self.chk_layer_tags = QCheckBox("Tags")
        self.chk_layer_tags.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_layer_tags.setChecked(True)
        self.chk_layer_tags.toggled.connect(self._on_layer_visibility_changed)
        thick_row.addWidget(self.chk_layer_tags)
        vbox.addWidget(self.thick_frame)

        self.stack = QStackedWidget()
        vbox.addWidget(self.stack, 1)

        # MODE 0: 2D Structural Drawing Canvas
        self.cad_canvas = StructuralCadCanvas2D(self)
        self.stack.addWidget(self.cad_canvas)

        # MODE 1: Beam Analysis (Loads, SFD & BMD)
        self.analysis_tab_widget = QWidget()
        an_layout = QVBoxLayout(self.analysis_tab_widget)
        an_layout.setContentsMargins(4, 4, 4, 4)
        an_layout.setSpacing(4)

        an_bar = QHBoxLayout()
        an_bar.addWidget(QLabel("Select Beam: "))
        self.cb_analysis_beam = QComboBox()
        self.cb_analysis_beam.setMinimumWidth(180)
        self.cb_analysis_beam.currentIndexChanged.connect(self._on_analysis_beam_changed)
        an_bar.addWidget(self.cb_analysis_beam)

        btn_wall_all = QPushButton("All Beams Carry Walls (12 kN/m)")
        btn_wall_all.setStyleSheet("background: #0284C7; color: white; font-weight: bold; padding: 4px 8px;")
        btn_wall_all.clicked.connect(lambda: self._set_all_walls_policy("all_beams"))
        an_bar.addWidget(btn_wall_all)

        btn_wall_none = QPushButton("No Wall Loads (0 kN/m)")
        btn_wall_none.setStyleSheet("background: #475569; color: white; font-weight: bold; padding: 4px 8px;")
        btn_wall_none.clicked.connect(lambda: self._set_all_walls_policy("no_walls"))
        an_bar.addWidget(btn_wall_none)

        an_bar.addSpacing(10)
        an_bar.addWidget(QLabel("Span Wall Toggles:"))
        self.span_wall_toggles_widget = QWidget()
        self.span_wall_toggles_layout = QHBoxLayout(self.span_wall_toggles_widget)
        self.span_wall_toggles_layout.setContentsMargins(0, 0, 0, 0)
        self.span_wall_toggles_layout.setSpacing(6)
        an_bar.addWidget(self.span_wall_toggles_widget)

        an_bar.addStretch(1)
        btn_an_sync = QPushButton("Re-Calculate && Sync (F5)")
        btn_an_sync.setStyleSheet("background: #16A34A; color: white; font-weight: bold; padding: 4px 12px;")
        btn_an_sync.clicked.connect(self.run_analyze_all_beams)
        an_bar.addWidget(btn_an_sync)

        an_layout.addLayout(an_bar)

        self.beam_analysis_diagram_widget = XpertBeamAnalysisDiagramWidget(self)
        an_layout.addWidget(self.beam_analysis_diagram_widget, 1)
        self.stack.addWidget(self.analysis_tab_widget)

        # MODE 2: Beam R.C. Design & Elevation
        self.design_tab_widget = QWidget()
        des_layout = QVBoxLayout(self.design_tab_widget)
        des_layout.setContentsMargins(4, 4, 4, 4)
        des_layout.setSpacing(4)

        des_bar = QHBoxLayout()
        des_bar.addWidget(QLabel("Select Beam: "))
        self.cb_design_beam = QComboBox()
        self.cb_design_beam.setMinimumWidth(180)
        self.cb_design_beam.currentIndexChanged.connect(self._on_design_beam_changed)
        des_bar.addWidget(self.cb_design_beam)

        self.lbl_design_sec_info = QLabel("Section: -- | Spans: --")
        self.lbl_design_sec_info.setStyleSheet("color: #38BDF8; font-weight: bold; margin-left: 12px;")
        des_bar.addWidget(self.lbl_design_sec_info, 1)

        btn_des_sync = QPushButton("Run Analysis && Re-Design (F5)")
        btn_des_sync.setStyleSheet("background: #16A34A; color: white; font-weight: bold; padding: 4px 12px;")
        btn_des_sync.clicked.connect(self.run_analyze_all_beams)
        des_bar.addWidget(btn_des_sync)
        des_layout.addLayout(des_bar)

        self.beam_rc_design_widget = XpertBeamRcDesignWidget(self)
        des_layout.addWidget(self.beam_rc_design_widget, 1)
        self.stack.addWidget(self.design_tab_widget)

        # MODE 3: Schedules & Report
        self.schedules_tab_widget = QWidget()
        sch_layout = QVBoxLayout(self.schedules_tab_widget)
        sch_layout.setContentsMargins(4, 4, 4, 4)
        sch_layout.setSpacing(6)

        sch_splitter = QSplitter(Qt.Orientation.Vertical)

        # Beam schedule table
        b_box = QGroupBox("Beam Reinforcement Schedule (ACI 318 - Each Span on Separate Row)")
        b_box_layout = QVBoxLayout(b_box)
        self.tbl_beam_schedule = QTableWidget(0, 9)
        self.tbl_beam_schedule.cellClicked.connect(self._on_beam_table_row_selected)
        self.tbl_beam_schedule.setHorizontalHeaderLabels([
            "Beam ID", "No. of Spans (Excl. Cantilevers)", "Section (b × h)",
            "Span / Cantilever", "Length (m)", "Bottom Rebar",
            "Top Rebar (Left)", "Top Rebar (Right)", "Stirrups (ACI 318)",
        ])
        self.tbl_beam_schedule.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        b_box_layout.addWidget(self.tbl_beam_schedule)
        sch_splitter.addWidget(b_box)

        # Column schedule table & Report in horizontal splitter
        c_r_splitter = QSplitter(Qt.Orientation.Horizontal)

        c_box = QGroupBox("Column Schedule & P-M Design (ACI 318)")
        c_box_layout = QVBoxLayout(c_box)
        self.tbl_columns = QTableWidget(0, 7)
        self.tbl_columns.setHorizontalHeaderLabels([
            "Column ID", "Section", "Story Pu (kN)", "End Moments (Mux, Muy)",
            "4-Way Framing (N/S/E/W)", "Reinforcement (ACI 318)", "Capacity phi*Pn (kN)",
        ])
        self.tbl_columns.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        c_box_layout.addWidget(self.tbl_columns)
        c_r_splitter.addWidget(c_box)

        r_box = QGroupBox("Engineering Master Calculation Report")
        r_box_layout = QVBoxLayout(r_box)
        self.report_browser = QTextBrowser()
        r_box_layout.addWidget(self.report_browser)
        c_r_splitter.addWidget(r_box)

        c_r_splitter.setStretchFactor(0, 1)
        c_r_splitter.setStretchFactor(1, 1)
        sch_splitter.addWidget(c_r_splitter)

        sch_splitter.setStretchFactor(0, 1)
        sch_splitter.setStretchFactor(1, 1)
        sch_layout.addWidget(sch_splitter, 1)

        self.stack.addWidget(self.schedules_tab_widget)

        # Bottom Frame
        bot_frame = QFrame()
        bot_frame.setFrameShape(QFrame.Shape.StyledPanel)
        bot_frame.setStyleSheet("background-color: #0F172A; color: #E2E8F0; border-top: 1px solid #334155;")
        bot_row = QHBoxLayout(bot_frame)
        bot_row.setContentsMargins(8, 3, 8, 3)
        bot_row.setSpacing(8)

        self.chk_osnap_master = QPushButton("OSNAP [F3]")
        self.chk_osnap_master.setCheckable(True)
        self.chk_osnap_master.setChecked(True)
        self.chk_osnap_master.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_osnap_master.setStyleSheet(
            "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #475569; padding: 3px 8px; font-weight: bold; border-radius: 3px; } "
            "QPushButton:checked { background: #FACC15; color: #000000; border-color: #EAB308; }"
        )
        self.chk_osnap_master.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_osnap_master)

        self.chk_osnap_end = QCheckBox("End")
        self.chk_osnap_end.setChecked(True)
        self.chk_osnap_end.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_osnap_end.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_osnap_end)

        self.chk_osnap_mid = QCheckBox("Mid")
        self.chk_osnap_mid.setChecked(True)
        self.chk_osnap_mid.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_osnap_mid.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_osnap_mid)

        self.chk_osnap_cen = QCheckBox("Cen")
        self.chk_osnap_cen.setChecked(True)
        self.chk_osnap_cen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_osnap_cen.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_osnap_cen)

        self.chk_osnap_perp = QCheckBox("Edge/Perp")
        self.chk_osnap_perp.setChecked(True)
        self.chk_osnap_perp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_osnap_perp.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_osnap_perp)

        self.chk_ortho_bar = QPushButton("ORTHO [F8]")
        self.chk_ortho_bar.setCheckable(True)
        self.chk_ortho_bar.setChecked(True)
        self.chk_ortho_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_ortho_bar.setStyleSheet(
            "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #475569; padding: 3px 8px; font-weight: bold; border-radius: 3px; } "
            "QPushButton:checked { background: #38BDF8; color: #000000; border-color: #0284C7; }"
        )
        self.chk_ortho_bar.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_ortho_bar)

        self.chk_grid_snap_bar = QPushButton("GRID 0.1m [F9]")
        self.chk_grid_snap_bar.setCheckable(True)
        self.chk_grid_snap_bar.setChecked(True)
        self.chk_grid_snap_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_grid_snap_bar.setStyleSheet(
            "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #475569; padding: 3px 8px; font-weight: bold; border-radius: 3px; } "
            "QPushButton:checked { background: #4ADE80; color: #000000; border-color: #16A34A; }"
        )
        self.chk_grid_snap_bar.toggled.connect(self._on_bottom_snap_settings_changed)
        bot_row.addWidget(self.chk_grid_snap_bar)

        self.lbl_coords_bar = QLabel("X: 0.00 m, Y: 0.00 m")
        self.lbl_coords_bar.setMinimumWidth(220)
        bot_row.addWidget(self.lbl_coords_bar)

        bot_row.addStretch(1)
        bot_row.addWidget(QLabel("Command / Numeric Input (ΔX,ΔY or X,Y or AL/MV/DI):"))
        self.ed_command_input = QLineEdit()
        self.ed_command_input.setPlaceholderText("e.g. 0.50, 0.00  or  AL  or  MV  or  DI")
        self.ed_command_input.setFixedWidth(230)
        self.ed_command_input.setStyleSheet("background-color: #1E293B; color: #F8FAFC; padding: 3px 6px; border: 1px solid #475569;")
        self.ed_command_input.returnPressed.connect(self.execute_bottom_command_or_numeric_input)
        bot_row.addWidget(self.ed_command_input)

        btn_exec_cmd = QPushButton("Apply [Enter]")
        btn_exec_cmd.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_exec_cmd.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 3px 10px;")
        btn_exec_cmd.clicked.connect(self.execute_bottom_command_or_numeric_input)
        bot_row.addWidget(btn_exec_cmd)

        vbox.addWidget(bot_frame)
        self.setStatusBar(QStatusBar())

    def update_contextual_prompt(self, message: str) -> None:
        self.lbl_ctx_prompt.setText(message)
        self.statusBar().showMessage(message)

    def _on_bottom_snap_settings_changed(self) -> None:
        self.cad_canvas.osnap_enabled = self.chk_osnap_master.isChecked()
        self.cad_canvas.osnap_modes["ENDPOINT"] = self.chk_osnap_end.isChecked()
        self.cad_canvas.osnap_modes["MIDPOINT"] = self.chk_osnap_mid.isChecked()
        self.cad_canvas.osnap_modes["CENTER"] = self.chk_osnap_cen.isChecked()
        self.cad_canvas.osnap_modes["PERPENDICULAR"] = self.chk_osnap_perp.isChecked()
        self.cad_canvas.ortho_enabled = self.chk_ortho_bar.isChecked()
        self.cad_canvas.grid_snap_enabled = self.chk_grid_snap_bar.isChecked()

    def execute_bottom_command_or_numeric_input(self) -> None:
        raw = self.ed_command_input.text().strip()
        if not raw:
            return
        self.ed_command_input.clear()
        upper = raw.upper()

        if upper in ("AL", "ALIGN"):
            self.activate_cad_tool("ALIGN_ELEMENT")
            return
        if upper in ("MV", "MOVE"):
            self.activate_cad_tool("MOVE_ELEMENT")
            return
        if upper in ("DI", "DIST", "MEASURE"):
            self.activate_cad_tool("MEASURE_DIST")
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

    def _on_beam_table_row_selected(self, row: int, col: int) -> None:
        item = self.tbl_beam_schedule.item(row, 0)
        if item:
            bid = item.text()
            idx = self.cb_analysis_beam.findText(bid)
            if idx >= 0:
                self.cb_analysis_beam.setCurrentIndex(idx)
            idx_des = self.cb_design_beam.findText(bid)
            if idx_des >= 0:
                self.cb_design_beam.setCurrentIndex(idx_des)

    def generate_exterior_dimensions(self) -> None:
        if not self.master_project:
            return
        count, msg = auto_generate_exterior_dimensions(self.current_story_data)
        self.save_and_sync_current_story()
        self.cad_canvas.render_story(self.current_story_data)
        self.update_contextual_prompt(msg)

    def clear_all_dimensions(self) -> None:
        if not self.master_project:
            return
        dims = self.current_story_data.get("dimensions", [])
        n = len(dims)
        self.current_story_data["dimensions"] = []
        self.save_and_sync_current_story()
        self.cad_canvas.render_story(self.current_story_data)
        self.update_contextual_prompt(f"Cleared {n} persistent dimensions.")

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

    def _on_layer_visibility_changed(self) -> None:
        self.cad_canvas.layer_show_arch = self.chk_layer_arch.isChecked()
        self.cad_canvas.layer_show_cols = self.chk_layer_cols.isChecked()
        self.cad_canvas.layer_show_beams = self.chk_layer_beams.isChecked()
        self.cad_canvas.layer_show_slabs = self.chk_layer_slabs.isChecked()
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
        self.update_contextual_prompt(f"Switched new column orientation to: {self.cb_col_orient.currentText()}")

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
            f"Xpert Structural Project (*{MASTER_FILE_EXT} *.xpert *-00_Project_Master.json);;All Files (*)",
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
            self.update_contextual_prompt("No elements selected. Click or drag a Window/Crossing box to select elements first.")
            return
        deleted_count = 0
        last_err = ""
        for kind, eid in list(self.cad_canvas.selected_items):
            ok, msg = delete_selected_element_from_story(self.current_story_data, kind, eid)
            if ok:
                deleted_count += 1
            else:
                last_err = msg
        if deleted_count == 0 and last_err:
            QMessageBox.warning(self, "Cannot Delete Element", last_err)
            return
        reconcile_and_split_slabs_after_beam_change(self.current_story_data)
        self.cad_canvas.selected_items.clear()
        self.save_and_sync_current_story()
        self.refresh_story_ui()
        self.update_contextual_prompt(f"Deleted {deleted_count} selected element(s).")

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
        self.refresh_story_ui()

    def refresh_story_ui(self) -> None:
        self.cad_canvas.render_story(self.current_story_data)
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

    def apply_story_thickness(self) -> None:
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"]) if self.master_project else 350.0
        eval_res = evaluate_story_thickness_and_optimization(self.current_story_data, fy)
        entered = self.sp_adopted_thick.value()
        req = float(eval_res.get("calculated_min_thickness_cm", 0.0))

        if eval_res.get("has_data") and entered < req:
            ans = QMessageBox.warning(
                self,
                "ACI 318 Minimum Thickness Warning",
                f"Entered slab thickness ({entered:.1f} cm) is less than the ACI 318 calculated minimum "
                f"thickness ({req:.1f} cm) governed by {eval_res['governing_member']}.\n\n"
                f"Do you want to continue with your entered value ({entered:.1f} cm) or modify it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.No:
                self.sp_adopted_thick.setFocus()
                return

        self.current_story_data["adopted_slab_thickness_cm"] = entered
        self.save_and_sync_current_story()

    def convert_critical_beam_to_drop(self) -> None:
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"]) if self.master_project else 350.0
        eval_res = evaluate_story_thickness_and_optimization(self.current_story_data, fy)
        smart_opt = eval_res.get("smart_optimization")
        if not smart_opt:
            return
        target_id = smart_opt["beam_id"]
        for bm in self.current_story_data.get("beams", []):
            if bm["id"] == target_id:
                bm["beam_kind"] = "drop"
                bm["width_m"] = 0.20
                bm["depth_m"] = 0.50
        self.save_and_sync_current_story()
        self.refresh_story_ui()

    def activate_cad_tool(self, tool_id: str) -> None:
        if tool_id == "ZOOM_EXTENTS":
            self.cad_canvas.zoom_extents()
            return

        if tool_id == "ZOOM_IN":
            self.cad_canvas.scale(1.2, 1.2)
            return

        if tool_id == "ZOOM_OUT":
            self.cad_canvas.scale(1.0 / 1.2, 1.0 / 1.2)
            return

        if tool_id == "AUTO_DIMS":
            self.generate_exterior_dimensions()
            return

        if tool_id == "CLEAR_DIMS":
            self.clear_all_dimensions()
            return

        if tool_id == "ROTATE_COL":
            self.cad_canvas.active_tool = "ROTATE_COL"
            self.cad_canvas.update_cursor_for_active_tool()
            self.update_contextual_prompt("Rotate Column [R]: Click directly on any Column (C#) to rotate it 90°.")
            return

        if tool_id == "ZOOM_WINDOW":
            self.cad_canvas.active_tool = "ZOOM_WINDOW"
            self.cad_canvas._zoom_win_start = None
            self.cad_canvas._zoom_win_curr = None
            self.cad_canvas.update_cursor_for_active_tool()
            self.update_contextual_prompt("Zoom Window: Drag a rectangle over the area you want to zoom in on.")
            return

        if tool_id in ("DIM_LINEAR", "DIM_ALIGNED"):
            self.cad_canvas.active_tool = tool_id
            self.cad_canvas._dim_first_pt = None
            self.cad_canvas.update_cursor_for_active_tool()
            self.update_contextual_prompt(f"{tool_id}: Click first point on canvas (endpoint/midpoint snap enabled)...")
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
            self.update_contextual_prompt(f"Converted {added} Architectural Columns to 0.20x0.40m Structural Columns.")
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
                    "id": "B1", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50, "room_bounding": True,
                    "start_x": 0.0, "start_y": 8.40, "end_x": 10.0, "end_y": 8.40,
                    "spans": [5.1, 4.7],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.20},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 10.0, "val": 28.5}],
                },
                {
                    "id": "B2", "beam_kind": "hidden", "width_m": 0.40, "depth_m": 0.30, "room_bounding": True,
                    "start_x": 0.0, "start_y": 4.20, "end_x": 10.0, "end_y": 4.20,
                    "spans": [5.1, 4.7],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.20},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.20},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 10.0, "val": 36.2}],
                },
                {
                    "id": "B3", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50, "room_bounding": True,
                    "start_x": 0.0, "start_y": 0.10, "end_x": 10.0, "end_y": 0.10,
                    "spans": [5.1, 4.7],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C7", "width_m": 0.20},
                        {"support_index": 2, "kind": "column", "target_id": "C8", "width_m": 0.20},
                        {"support_index": 3, "kind": "column", "target_id": "C9", "width_m": 0.20},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 10.0, "val": 28.5}],
                },
                {
                    "id": "B4", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50, "room_bounding": True,
                    "start_x": 0.10, "start_y": 0.0, "end_x": 0.10, "end_y": 8.5,
                    "spans": [4.0, 4.1],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C7", "width_m": 0.40},
                        {"support_index": 2, "kind": "column", "target_id": "C4", "width_m": 0.40},
                        {"support_index": 3, "kind": "column", "target_id": "C1", "width_m": 0.40},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 8.5, "val": 25.0}],
                },
                {
                    "id": "B5", "beam_kind": "hidden", "width_m": 0.40, "depth_m": 0.30, "room_bounding": True,
                    "start_x": 5.20, "start_y": 0.0, "end_x": 5.20, "end_y": 8.5,
                    "spans": [4.0, 4.1],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C8", "width_m": 0.40},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.40},
                        {"support_index": 3, "kind": "column", "target_id": "C2", "width_m": 0.40},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 8.5, "val": 32.0}],
                },
                {
                    "id": "B6", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50, "room_bounding": True,
                    "start_x": 9.90, "start_y": 0.0, "end_x": 9.90, "end_y": 8.5,
                    "spans": [4.0, 4.1],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C9", "width_m": 0.40},
                        {"support_index": 2, "kind": "column", "target_id": "C6", "width_m": 0.40},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.40},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 8.5, "val": 25.0}],
                },
            ]
            self.current_story_data["slabs"] = []
            self.current_story_data["openings"] = []
            auto_fill_all_story_slabs(self.current_story_data)
            self.cad_canvas.active_tool = "SELECT"
            self.cad_canvas.update_cursor_for_active_tool()
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            return

        self.cad_canvas.active_tool = tool_id
        self.cad_canvas._polyline_pts.clear()
        self.cad_canvas._first_click_pt = None
        self.cad_canvas._align_ref = None
        self.cad_canvas._measure_pts.clear()
        self.cad_canvas.update_cursor_for_active_tool()

        prompts = {
            "SELECT": "SELECT Mode: Click any element, or drag Left->Right (Window Blue) / Right->Left (Crossing Green).",
            "ALIGN_ELEMENT": "Revit Align [AL] — Step 1: Click the fixed Reference Edge (Boundary, Grid, Arch Line, or Column/Beam Face).",
            "MOVE_ELEMENT": "Move [MV]: Click Base Reference Point -> Click Second Target Point (or type ΔX, ΔY in the Command Bar below).",
            "MEASURE_DIST": "Measure [DI]: Click First Point on canvas -> Click Second Point to measure L, ΔX, ΔY, and Angle.",
            "DRAW_SLAB_EDGE": "Step 1 (Polyline Boundary): Click vertices around the building perimeter (NEVER auto-fills ribs!).",
            "DRAW_COL": "Step 2 (Place Column): Click to place 0.20x0.40m column (or use AL to align its faces flush with edges).",
            "DRAW_BEAM_HID": "Step 3A (Hidden Beam 0.40m): Click Start Column Center -> Click End Column Center (auto-extends to outer faces!).",
            "DRAW_BEAM_DROP": "Step 3B (Drop Beam 0.20m): Click Start Column Center -> Click End Column Center (auto-extends to outer faces!).",
        }
        self.update_contextual_prompt(prompts.get(tool_id, f"Activated Tool: {tool_id}"))

    def save_and_sync_current_story(self) -> None:
        if not self.master_project:
            return
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

    def run_analyze_all_beams(self) -> None:
        if not self.master_project:
            return
        fc = float(self.master_project["materials_and_soil"]["fc_mpa"])
        fy = float(self.master_project["materials_and_soil"]["fy_mpa"])
        self.last_analysis_bundle = analyze_all_story_beams_and_columns(self.current_story_data, fc, fy)

        beams = self.current_story_data.get("beams", [])
        col_recs = self.last_analysis_bundle.get("column_records", [])
        self.tbl_columns.setRowCount(len(col_recs))
        for c_i, crec in enumerate(col_recs):
            des = crec["design"]
            f4 = crec["framing_4way"]
            f4_str = " | ".join(f"{k[0]}:{v['beam_id']}" for k, v in f4.items() if v) or "Corner/Edge"
            self.tbl_columns.setItem(c_i, 0, QTableWidgetItem(crec["column_id"]))
            self.tbl_columns.setItem(c_i, 1, QTableWidgetItem(des["section_mm"]))
            self.tbl_columns.setItem(c_i, 2, QTableWidgetItem(f"{crec['story_pu_kn']:.1f}"))
            self.tbl_columns.setItem(c_i, 3, QTableWidgetItem(f"({crec['mux_knm']:.1f}, {crec['muy_knm']:.1f})"))
            self.tbl_columns.setItem(c_i, 4, QTableWidgetItem(f4_str))
            self.tbl_columns.setItem(c_i, 5, QTableWidgetItem(des["chosen_bars"]))
            self.tbl_columns.setItem(c_i, 6, QTableWidgetItem(f"{des['phi_pn_max_kn']:.1f} ({des['status']})"))

        self.report_browser.setHtml(
            f"<h2>Xpert Structural Design Studio — Master Calculation Report ({STUDIO_VERSION})</h2>"
            f"<p><b>Project:</b> {self.master_project['project_name']} | "
            f"<b>Master File:</b> {self.master_project.get('master_file')} | "
            f"<b>Beams Analyzed:</b> {len(beams)} | <b>Columns Designed:</b> {len(col_recs)}</p>"
        )
        self._sync_analysis_tab_ui()
        self._sync_design_tab_ui()
        self._sync_schedules_tab_ui()
        self.switch_workspace_mode(1)

    def switch_workspace_mode(self, mode_idx: int) -> None:
        self.stack.setCurrentIndex(mode_idx)
        btn = self.view_btn_group.button(mode_idx)
        if btn:
            btn.setChecked(True)

        is_drawing_mode = (mode_idx == 0)
        self.left_tb.setVisible(is_drawing_mode)
        self.mod_tb.setVisible(is_drawing_mode)
        self.dim_tb.setVisible(is_drawing_mode)
        self.ctx_frame.setVisible(is_drawing_mode)
        self.thick_frame.setVisible(is_drawing_mode)

        if mode_idx == 1:
            self._sync_analysis_tab_ui()
        elif mode_idx == 2:
            self._sync_design_tab_ui()
        elif mode_idx == 3:
            self._sync_schedules_tab_ui()

    def _sync_analysis_tab_ui(self) -> None:
        beams = self.current_story_data.get("beams", [])
        self.cb_analysis_beam.blockSignals(True)
        cur_id = self.cb_analysis_beam.currentText()
        self.cb_analysis_beam.clear()
        for bm in beams:
            self.cb_analysis_beam.addItem(bm["id"])
        if cur_id and self.cb_analysis_beam.findText(cur_id) >= 0:
            self.cb_analysis_beam.setCurrentText(cur_id)
        elif beams:
            self.cb_analysis_beam.setCurrentIndex(0)
        self.cb_analysis_beam.blockSignals(False)

        selected_id = self.cb_analysis_beam.currentText()
        self._update_analysis_diagram_for_beam(selected_id)

    def _on_analysis_beam_changed(self, idx: int) -> None:
        b_id = self.cb_analysis_beam.currentText()
        if b_id:
            self._update_analysis_diagram_for_beam(b_id)

    def _update_analysis_diagram_for_beam(self, beam_id: str) -> None:
        bm = next((b for b in self.current_story_data.get("beams", []) if b["id"] == beam_id), None)
        if not bm:
            return

        # Build per-span wall toggle checkboxes
        while self.span_wall_toggles_layout.count():
            item = self.span_wall_toggles_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        flags = ensure_beam_wall_flags(self.current_story_data, bm)
        segs = get_beam_span_segments(bm)
        for seg in segs:
            s_key = seg["key"]
            chk = QCheckBox(seg["label"])
            chk.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            chk.setChecked(flags.get(s_key, True))
            chk.toggled.connect(lambda st, sk=s_key, bid=beam_id: self._toggle_current_beam_span_wall(bid, sk, st))
            self.span_wall_toggles_layout.addWidget(chk)

        if hasattr(self, "last_analysis_bundle") and self.last_analysis_bundle:
            b_res = self.last_analysis_bundle.get("beam_results", {}).get(beam_id)
            self.beam_analysis_diagram_widget.set_beam_data(bm, b_res)
        else:
            self.beam_analysis_diagram_widget.set_beam_data(bm, None)

    def _set_all_walls_policy(self, policy: str) -> None:
        set_story_wall_load_policy(self.current_story_data, policy)
        self.save_and_sync_current_story()
        self.run_analyze_all_beams()
        self.update_contextual_prompt(f"Wall loads policy set to: {'ALL BEAMS (12 kN/m)' if policy == 'all_beams' else 'NO WALL LOADS'}.")

    def _toggle_current_beam_span_wall(self, beam_id: str, span_key: str, state: bool) -> None:
        set_beam_span_wall_flag(self.current_story_data, beam_id, span_key, state)
        self.save_and_sync_current_story()
        self.run_analyze_all_beams()

    def _sync_design_tab_ui(self) -> None:
        beams = self.current_story_data.get("beams", [])
        self.cb_design_beam.blockSignals(True)
        cur_id = self.cb_design_beam.currentText()
        self.cb_design_beam.clear()
        for bm in beams:
            self.cb_design_beam.addItem(bm["id"])
        if cur_id and self.cb_design_beam.findText(cur_id) >= 0:
            self.cb_design_beam.setCurrentText(cur_id)
        elif beams:
            self.cb_design_beam.setCurrentIndex(0)
        self.cb_design_beam.blockSignals(False)

        selected_id = self.cb_design_beam.currentText()
        self._update_design_elevation_for_beam(selected_id)

    def _on_design_beam_changed(self, idx: int) -> None:
        b_id = self.cb_design_beam.currentText()
        if b_id:
            self._update_design_elevation_for_beam(b_id)

    def _update_design_elevation_for_beam(self, beam_id: str) -> None:
        bm = next((b for b in self.current_story_data.get("beams", []) if b["id"] == beam_id), None)
        if not bm:
            return

        b_kind_str = bm.get("beam_kind", "hidden").upper()
        w_m = float(bm.get("width_m", 0.40))
        d_m = float(bm.get("depth_m", 0.30))
        self.lbl_design_sec_info.setText(f"Beam {beam_id}: {b_kind_str} ({w_m:.2f}×{d_m:.2f}m) | Spans: {', '.join(str(s) for s in bm.get('spans', []))} m")

        if hasattr(self, "last_analysis_bundle") and self.last_analysis_bundle:
            b_res = self.last_analysis_bundle.get("beam_results", {}).get(beam_id)
            b_des = self.last_analysis_bundle.get("beam_designs", {}).get(beam_id)
            self.beam_rc_design_widget.set_data(bm, b_res, b_des)
        else:
            self.beam_rc_design_widget.set_data(bm, None, None)

    def _sync_schedules_tab_ui(self) -> None:
        if not hasattr(self, "last_analysis_bundle") or not self.last_analysis_bundle:
            return

        beams = self.current_story_data.get("beams", [])
        beam_results = self.last_analysis_bundle.get("beam_results", {})
        beam_designs = self.last_analysis_bundle.get("beam_designs", {})

        # Populate tbl_beam_schedule: Each span on a separate row!
        row_count = 0
        for bm in beams:
            segs = get_beam_span_segments(bm)
            row_count += len(segs)

        self.tbl_beam_schedule.setRowCount(row_count)
        cur_row = 0

        for bm in beams:
            bid = bm["id"]
            res = beam_results.get(bid, {})
            des = beam_designs.get(bid, {})
            b_kind = bm.get("beam_kind", "hidden").upper()
            sec_txt = f"{float(bm.get('width_m', 0.4)):.2f} × {float(bm.get('depth_m', 0.3)):.2f}"
            n_spans_excl = str(des.get("num_spans_excluding_cantilevers", len(bm.get("spans", []))))

            segs = get_beam_span_segments(bm)
            span_des_list = des.get("span_designs", [])
            supp_des_list = des.get("support_designs", [])

            for s_idx, seg in enumerate(segs):
                self.tbl_beam_schedule.setItem(cur_row, 0, QTableWidgetItem(bid))
                self.tbl_beam_schedule.setItem(cur_row, 1, QTableWidgetItem(n_spans_excl))
                self.tbl_beam_schedule.setItem(cur_row, 2, QTableWidgetItem(f"{sec_txt} ({b_kind})"))
                self.tbl_beam_schedule.setItem(cur_row, 3, QTableWidgetItem(seg["label"]))
                self.tbl_beam_schedule.setItem(cur_row, 4, QTableWidgetItem(f"{seg['length_m']:.2f}"))

                # Rebar details for this span
                if seg["type"] == "span":
                    sp_i = seg.get("span_index", 1) - 1
                    sp_d = span_des_list[sp_i] if sp_i < len(span_des_list) else {}
                    bot_str = sp_d.get("bottom_bars", des.get("bottom_bars", "3 Phi 16 mm"))
                    sup_l = supp_des_list[sp_i].get("top_bars", des.get("top_bars", "4 Phi 16 mm")) if sp_i < len(supp_des_list) else "-"
                    sup_r = supp_des_list[sp_i + 1].get("top_bars", des.get("top_bars", "4 Phi 16 mm")) if (sp_i + 1) < len(supp_des_list) else "-"
                    stirr_str = sp_d.get("stirrups", des.get("stirrups", "Phi 8 @ 150 mm"))
                else:
                    bot_str = "2 Phi 16 mm (Tie-backs)"
                    sup_l = des.get("top_bars", "4 Phi 16 mm")
                    sup_r = "-"
                    stirr_str = "Phi 8 @ 100 mm"

                self.tbl_beam_schedule.setItem(cur_row, 5, QTableWidgetItem(bot_str))
                self.tbl_beam_schedule.setItem(cur_row, 6, QTableWidgetItem(sup_l))
                self.tbl_beam_schedule.setItem(cur_row, 7, QTableWidgetItem(sup_r))
                self.tbl_beam_schedule.setItem(cur_row, 8, QTableWidgetItem(stirr_str))
                cur_row += 1


def main() -> None:
    if "--check" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)

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
        win.show()
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
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
