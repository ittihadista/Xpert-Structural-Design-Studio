"""
Xpert Structural Design Studio (v1.3.0-smart-cad-intelligence)
Main Desktop Application (PyQt6 + ezdxf + Matplotlib)
Lead Structural Engineer & Product Owner: Eng. Yousef Mohammed Keshlaf

Key Upgrades in v1.3.0:
1. Per-Story Architectural .DXF Import as a Unified Locked Block (`arch_underlay_block`)
   with 1-Click Show/Hide toggle and OSNAP support without mixing with structural layers.
2. Layer Visibility & Freeze Checkboxes (`Arch DXF`, `Columns`, `Beams`, `Slabs & Ribs`, `Tags`)
   to easily hide/freeze Slabs when drawing Beams in tight spaces or vice-versa.
3. Realistic Hidden Beam Width (`0.40 m` default instead of `0.60 m`) + Distinct Hatching.
4. Strict Tool Isolation: Drawing a Beam or clicking a Column NEVER accidentally creates a slab
   or flips rib directions. Rib flipping by clicking the label (`S# [0°]`) works strictly in
   `SELECT` (or `FLIP_RIB`) mode when clicking the center label badge.
5. Zero Duplicate Overlapping Elements (no Column-on-Column, no Beam-on-Beam, no Slab-on-Slab,
   and zero perimeter sliver bays).
6. Dynamic Automatic Slab Splitting: Drawing a new beam that divides an existing 9.0m slab in
   half automatically splits it into two independent 4.5m slabs supported by that beam!
7. Full Column Cross-Section Strictly Inside Slab Boundary (including in Demo Layout).
8. Standard Arrow Cursor (`ArrowCursor`) by default, Hand Cursor (`OpenHandCursor` / `ClosedHandCursor`)
   in `PAN` mode, and Crosshair (`CrossCursor`) only when an active drawing tool is selected.
9. 2-Click Continuous Multi-Span Beam Drawing with Live Intermediate Support Highlighting,
   plus Productivity Tools: `Auto-Fill All Slabs`, `Rotate Col 90° (R)`, and `Convert Arch Columns`.
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
    QMessageBox,
    QPushButton,
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
)


class NewProjectSetupDialog(QDialog):
    """
    Modal Startup & Project Definition Dialog.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Structural Project — Xpert Structural Design Studio")
        self.setMinimumWidth(700)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.opened_existing_master_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        open_bar = QFrame()
        open_bar.setFrameShape(QFrame.Shape.StyledPanel)
        open_row = QHBoxLayout(open_bar)
        lbl_open = QLabel("Have an existing project? Open its Master File (*-00_Project_Master.xpert):")
        lbl_open.setStyleSheet("font-weight: bold; color: #0284C7;")
        btn_open_existing = QPushButton("Open Existing Project (.xpert)...")
        btn_open_existing.setStyleSheet("padding: 5px 12px; font-weight: bold;")
        btn_open_existing.clicked.connect(self._browse_existing_xpert)
        open_row.addWidget(lbl_open, 1)
        open_row.addWidget(btn_open_existing)
        root_layout.addWidget(open_bar)

        grp_id = QGroupBox("1. New Project Identity && Workspace Folder")
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

    def _browse_existing_xpert(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Xpert Structural Master Project File",
            os.path.abspath("./XpertStudio_Projects"),
            f"Xpert Project Master (*{MASTER_FILE_EXT} *-00_Project_Master.json);;All Files (*)",
        )
        if fpath and os.path.isfile(fpath):
            self.opened_existing_master_path = fpath
            self.accept()

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Root Projects Directory")
        if folder:
            self.ed_folder.setText(folder)

    def _on_accept(self) -> None:
        ok, _, _, err = validate_project_name(self.ed_name.text())
        if not ok:
            QMessageBox.warning(self, "Invalid Project Name", err)
            return
        self.opened_existing_master_path = None
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


class StructuralCadCanvas2D(QGraphicsView):
    """
    Built-in 2D Interactive Structural CAD Canvas with:
    - Locked Per-Story Architectural .DXF Underlay Block (Show/Hide).
    - Layer Visibility & Freeze Controls (Arch DXF, Columns, Beams, Slabs/Ribs, Tags).
    - Standard ArrowCursor in SELECT mode, OpenHand/ClosedHand in PAN mode, CrossCursor in Draw modes.
    - Strict Tool Isolation & Automatic Dynamic Slab Splitting when divided by a new beam.
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self.scene_2d = QGraphicsScene(self)
        self.setScene(self.scene_2d)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0D1117")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.scale_px = 48.0  # 1m = 48px
        self.active_tool = "SELECT"
        self.osnap_enabled = True
        self.ortho_enabled = True

        # Layer visibility & freeze flags
        self.layer_show_arch = True
        self.layer_show_cols = True
        self.layer_show_beams = True
        self.layer_show_slabs = True
        self.layer_show_tags = True

        # Interactive states
        self._is_panning = False
        self._pan_start_pos = QPointF()
        self._polyline_pts: List[Tuple[float, float]] = []
        self._first_click_pt: Optional[Tuple[float, float]] = None
        self._current_snap_info: Optional[Dict[str, Any]] = None
        self.selected_element: Optional[Dict[str, Any]] = None

        # Ensure standard Arrow Cursor at startup
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def update_cursor_for_active_tool(self) -> None:
        if self._is_panning:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self.active_tool == "PAN":
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.active_tool == "SELECT":
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)

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
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.studio.delete_selected_object()
            event.accept()
            return
        if key == Qt.Key.Key_R:
            self.studio.rotate_selected_or_default_column()
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
            self.selected_element = None
            self.active_tool = "SELECT"
            self.update_cursor_for_active_tool()
            self.render_story(self.studio.current_story_data)
            self.studio.statusBar().showMessage("Returned to SELECT tool (Arrow Cursor).")
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
        n_verts = len(self._polyline_pts)
        self._polyline_pts.clear()
        self.active_tool = "SELECT"
        self.update_cursor_for_active_tool()
        self.studio.save_and_sync_current_story()
        self.studio.refresh_story_ui()
        self.studio.statusBar().showMessage(
            f"Step 1 Complete: Closed Building Boundary Polyline with {n_verts} vertices. Proceed to Step 2 (+ Column 0.20x0.40m)."
        )

    def compute_osnap_point(
        self, raw_x: float, raw_y: float, story_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Finds the closest magnetic OSNAP target within 0.42 m radius:
        Priority: Active Polyline Start -> Column Center/Corner -> Beam End/Mid ->
                  Slab Polyline Vertex/Edge -> Architectural DXF Block Endpoints -> 0.1m Grid.
        """
        if not self.osnap_enabled:
            gx, gy = round(raw_x, 2), round(raw_y, 2)
            return {"x": gx, "y": gy, "snap_type": "FREE", "label": f"({gx:.2f}, {gy:.2f})"}

        candidates: List[Tuple[float, float, float, str, str]] = []
        snap_radius = 0.42

        if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
            p0x, p0y = self._polyline_pts[0]
            d0 = math.hypot(raw_x - p0x, raw_y - p0y)
            if d0 <= snap_radius * 1.2:
                candidates.append((d0 - 0.10, p0x, p0y, "POLY_CLOSE", f"OSNAP: Close Polyline at Start ({p0x:.2f}, {p0y:.2f})"))

        # 1. Columns (Center & 4 Corners)
        if self.layer_show_cols:
            for col in story_data.get("columns", []):
                if not col.get("active", True):
                    continue
                cx, cy = float(col["x"]), float(col["y"])
                b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
                cid = str(col["id"])
                dist_c = math.hypot(raw_x - cx, raw_y - cy)
                if dist_c <= snap_radius:
                    candidates.append((dist_c - 0.06, cx, cy, "COL_CENTER", f"OSNAP: {cid} Center ({cx:.2f}, {cy:.2f})"))
                for dx, dy in [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, h / 2), (-b / 2, h / 2)]:
                    kx, ky = round(cx + dx, 3), round(cy + dy, 3)
                    d_k = math.hypot(raw_x - kx, raw_y - ky)
                    if d_k <= snap_radius * 0.85:
                        candidates.append((d_k, kx, ky, "COL_CORNER", f"OSNAP: {cid} Corner ({kx:.2f}, {ky:.2f})"))

        # 2. Beams (Endpoints & Midpoints)
        if self.layer_show_beams:
            for bm in story_data.get("beams", []):
                bid = str(bm["id"])
                sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
                mx, my = round((sx + ex) / 2.0, 3), round((sy + ey) / 2.0, 3)
                for px, py, stype, slbl in [
                    (sx, sy, "BEAM_END", f"OSNAP: {bid} Start"),
                    (ex, ey, "BEAM_END", f"OSNAP: {bid} End"),
                    (mx, my, "BEAM_MID", f"OSNAP: {bid} Midpoint"),
                ]:
                    d_b = math.hypot(raw_x - px, raw_y - py)
                    if d_b <= snap_radius:
                        candidates.append((d_b, px, py, stype, f"{slbl} ({px:.2f}, {py:.2f})"))

        # 3. Polyline Slab Boundary Vertices & Segment Projections
        poly_pts = story_data.get("slab_edge_polygon", [])
        if len(poly_pts) >= 3:
            for idx, pt in enumerate(poly_pts):
                vx, vy = float(pt[0]), float(pt[1])
                d_v = math.hypot(raw_x - vx, raw_y - vy)
                if d_v <= snap_radius:
                    candidates.append((d_v, vx, vy, "SLAB_VERTEX", f"OSNAP: Boundary Vertex V{idx+1} ({vx:.2f}, {vy:.2f})"))
            for idx in range(len(poly_pts)):
                x1, y1 = float(poly_pts[idx][0]), float(poly_pts[idx][1])
                x2, y2 = float(poly_pts[(idx + 1) % len(poly_pts)][0]), float(poly_pts[(idx + 1) % len(poly_pts)][1])
                dx, dy = x2 - x1, y2 - y1
                seg_len2 = dx * dx + dy * dy
                if seg_len2 > 1e-6:
                    t = max(0.0, min(1.0, ((raw_x - x1) * dx + (raw_y - y1) * dy) / seg_len2))
                    px, py = round(x1 + t * dx, 2), round(y1 + t * dy, 2)
                    d_seg = math.hypot(raw_x - px, raw_y - py)
                    if d_seg <= 0.28:
                        candidates.append((d_seg + 0.05, px, py, "SLAB_EDGE", f"OSNAP: Boundary Edge ({px:.2f}, {py:.2f})"))

        # 4. Architectural DXF Underlay Block Endpoints (if visible)
        arch_block = story_data.get("arch_underlay_block")
        if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
            for seg in arch_block.get("segments", [])[:800]:
                for ax, ay in [(seg[0], seg[1]), (seg[2], seg[3])]:
                    d_a = math.hypot(raw_x - ax, raw_y - ay)
                    if d_a <= snap_radius * 0.75:
                        candidates.append((d_a + 0.08, ax, ay, "ARCH_END", f"OSNAP: Arch DXF Pt ({ax:.2f}, {ay:.2f})"))

        if candidates:
            candidates.sort(key=lambda item: item[0])
            _, sx, sy, stype, slbl = candidates[0]
            return {"x": round(sx, 3), "y": round(sy, 3), "snap_type": stype, "label": slbl}

        gx, gy = round(raw_x * 10.0) / 10.0, round(raw_y * 10.0) / 10.0
        return {"x": gx, "y": gy, "snap_type": "GRID", "label": f"Grid ({gx:.2f}, {gy:.2f})"}

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
            if self.active_tool == "DRAW_SLAB_EDGE" and len(self._polyline_pts) >= 3:
                self._finalize_polyline_boundary()
            else:
                self._polyline_pts.clear()
                self._first_click_pt = None
                self.active_tool = "SELECT"
                self.update_cursor_for_active_tool()
                self.render_story(self.studio.current_story_data)
                self.studio.statusBar().showMessage("Returned to SELECT mode (Arrow Cursor).")
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            raw_x, raw_y = self._scene_to_world_m(scene_pt)
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
        snap = self.compute_osnap_point(raw_x, raw_y, self.studio.current_story_data)

        ref_pt = None
        if self.active_tool == "DRAW_SLAB_EDGE" and self._polyline_pts:
            ref_pt = self._polyline_pts[-1]
        elif self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT") and self._first_click_pt is not None:
            ref_pt = self._first_click_pt

        if self.ortho_enabled and ref_pt is not None and snap["snap_type"] != "POLY_CLOSE":
            fx, fy = ref_pt
            if abs(snap["x"] - fx) >= abs(snap["y"] - fy):
                snap["y"] = fy
            else:
                snap["x"] = fx

        self._current_snap_info = snap
        self.studio.statusBar().showMessage(
            f"Tool: {self.active_tool} | Cursor: X={raw_x:.2f}m, Y={raw_y:.2f}m | {snap['label']} | "
            f"OSNAP (F3): {'ON' if self.osnap_enabled else 'OFF'} | ORTHO (F8): {'ON' if self.ortho_enabled else 'OFF'}"
        )
        self.render_story(self.studio.current_story_data)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._is_panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._is_panning = False
            self.update_cursor_for_active_tool()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _find_element_near(self, wx: float, wy: float) -> Optional[Dict[str, Any]]:
        story = self.studio.current_story_data
        # 1. Columns (highest selection priority)
        if self.layer_show_cols:
            for col in story.get("columns", []):
                if not col.get("active", True):
                    continue
                if math.hypot(wx - float(col["x"]), wy - float(col["y"])) <= 0.38:
                    return {"kind": "column", "id": col["id"]}
        # 2. Beams
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
        # 3. Openings & Slabs
        if self.layer_show_slabs:
            for op in story.get("openings", []):
                if float(op["min_x"]) <= wx <= float(op["max_x"]) and float(op["min_y"]) <= wy <= float(op["max_y"]):
                    return {"kind": "opening", "id": op["id"]}
            for slb in story.get("slabs", []):
                if "min_x" in slb and float(slb["min_x"]) <= wx <= float(slb["max_x"]) and float(slb["min_y"]) <= wy <= float(slb["max_y"]):
                    return {"kind": "slab", "id": slb["id"]}
        # 4. Building Boundary Polyline Edge
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

    def _handle_left_click_at(self, sx: float, sy: float, raw_x: float, raw_y: float, snap_type: str) -> None:
        story = self.studio.current_story_data
        tool = self.active_tool

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
            self.studio.statusBar().showMessage(
                f"Polyline Vertex V{n_pts} added at ({sx:.2f}, {sy:.2f}). "
                f"{'Click near V1 or Right-Click / Press Enter to Close Polyline.' if n_pts >= 3 else 'Click next vertex...'}"
            )
            return

        # STRICT TOOL ISOLATION:
        # Clicking the Slab Rib Label (`S1 [0°]`) to flip rib direction ONLY happens in `SELECT` or `FLIP_RIB` mode
        # (NEVER when drawing columns or beams!)
        if tool in ("SELECT", "FLIP_RIB") and self.layer_show_slabs:
            toggled, t_msg, _ = toggle_slab_rib_by_label_click(story, raw_x, raw_y, hit_radius_m=0.45)
            if toggled:
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.statusBar().showMessage(f"Rib Direction Toggled: {t_msg}")
                return
            elif t_msg:
                QMessageBox.warning(self, "Cantilever Slab Equilibrium Rule", t_msg)
                self.studio.statusBar().showMessage(t_msg)
                return

        # Enforce Step 1 before any drawing tool
        has_bnd, _, _, _, _ = get_slab_bounding_box(story.get("slab_edge_polygon", []))
        if not has_bnd and tool != "SELECT":
            QMessageBox.warning(
                self,
                "Step 1 Required: Draw Building Boundary Polyline First",
                "Please draw the Outer Building Boundary Polyline (00-XD-EDGE) first before placing columns, beams, or slabs.",
            )
            return

        # STEP 2: Place Column (Fixed Initial Minimum Size 0.20 x 0.40 m, Full Section Inside Boundary, No Duplicates)
        if tool == "DRAW_COL":
            cols = story.setdefault("columns", [])
            is_vert = self.studio.cb_col_orient.currentIndex() == 0
            b_m = 0.20 if is_vert else 0.40
            h_m = 0.40 if is_vert else 0.20
            boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            next_id = f"C{len(cols) + 1}"
            new_col = {"id": next_id, "x": sx, "y": sy, "b_m": b_m, "h_m": h_m, "active": True}
            updated_col, updated_poly, msg = enforce_column_inside_slab_boundary(
                new_col, story["slab_edge_polygon"], mode=boundary_mode
            )
            dup_id = check_duplicate_column(updated_col["x"], updated_col["y"], b_m, h_m, cols)
            if dup_id:
                self.studio.statusBar().showMessage(
                    f"Duplicate Column Prevented: Column {dup_id} already exists at ({updated_col['x']:.2f}, {updated_col['y']:.2f})."
                )
                return
            story["slab_edge_polygon"] = updated_poly
            cols.append(updated_col)
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.statusBar().showMessage(f"Placed Column {next_id} ({b_m:.2f}x{h_m:.2f} m): {msg}")
            return

        # STEP 3: Draw Full-Width Hidden (0.40m) or Drop (0.20m) Beam (2-Click Continuous Multi-Span + Auto Split Slabs)
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
                self.studio.statusBar().showMessage(
                    f"Beam Start set at ({sx:.2f}, {sy:.2f}). Click End Support (single line automatically detects all intermediate columns!)..."
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
                    self.studio.statusBar().showMessage(f"Rejected Beam: {msg}")
                    self.render_story(story)
                    return
                beams.append(bm_obj)
                # SMART DYNAMIC SLAB SPLITTING: If this new beam divides an existing slab (e.g. 9m -> 4.5m + 4.5m), split it automatically!
                split_n, split_msg = reconcile_and_split_slabs_after_beam_change(story)
                if split_msg:
                    msg = f"{msg} | {split_msg}"
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.statusBar().showMessage(msg)
            return

        # STEP 4: Pick Area (Slab / Opening Toggle)
        if tool in ("PICK_SLAB", "PICK_OPENING"):
            mode_str = "SLAB" if tool == "PICK_SLAB" else "TOGGLE_OPENING"
            ok, msg, _ = pick_area_create_or_update_slab(
                story, raw_x, raw_y, target_mode=mode_str
            )
            if not ok:
                QMessageBox.warning(self, "Pick Area / Cantilever Rule", msg)
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.statusBar().showMessage(msg)
            return

        # MOVE ELEMENT TOOL (Move Column or Move Beam)
        if tool == "MOVE_ELEMENT":
            if self.selected_element is None or self.selected_element["kind"] not in ("column", "beam"):
                found = self._find_element_near(raw_x, raw_y)
                if not found or found["kind"] not in ("column", "beam"):
                    self.studio.statusBar().showMessage("Move Tool: Click on a Column (C#) or Beam (B#) to select it for moving.")
                    return
                self.selected_element = found
                self._first_click_pt = (sx, sy)
                self.render_story(story)
                self.studio.statusBar().showMessage(
                    f"Selected {found['kind'].upper()} {found['id']}. Click new target position to move it..."
                )
            else:
                el = self.selected_element
                start_pt = self._first_click_pt or (sx, sy)
                if el["kind"] == "column":
                    boundary_mode = "clamp" if self.studio.cb_col_boundary_rule.currentIndex() == 0 else "expand"
                    ok, msg = move_column_and_sync_connected_beams(
                        story, el["id"], sx, sy, boundary_mode=boundary_mode
                    )
                else:
                    dx = round(sx - start_pt[0], 3)
                    dy = round(sy - start_pt[1], 3)
                    ok, msg = move_beam_within_slab_boundary(story, el["id"], dx, dy)
                reconcile_and_split_slabs_after_beam_change(story)
                self.selected_element = None
                self._first_click_pt = None
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.statusBar().showMessage(msg)
            return

        # Default SELECT tool
        found = self._find_element_near(raw_x, raw_y)
        self.selected_element = found
        if found:
            self.studio.statusBar().showMessage(
                f"Selected {found['kind'].upper()}: {found['id']} (Press 'Delete' to remove, or 'R' to rotate Column 90°)"
            )
        else:
            self.studio.statusBar().showMessage("Ready (SELECT). Click any element to select, or click Slab Label (S#) to flip rib direction.")
        self.render_story(story)

    def render_story(self, story_data: Dict[str, Any]) -> None:
        self.scene_2d.clear()
        s = self.scale_px

        # 0. Draw Coordinate Grid (1m spacing)
        grid_pen = QPen(QColor("#161F2C"), 1, Qt.PenStyle.DotLine)
        for gx in range(-2, 18):
            self.scene_2d.addLine(gx * s, -14 * s, gx * s, 2 * s, grid_pen)
        for gy in range(-2, 14):
            self.scene_2d.addLine(-2 * s, -gy * s, 18 * s, -gy * s, grid_pen)

        # 0B. Locked Per-Story Architectural .DXF Underlay Block (drawn behind all structural layers)
        arch_block = story_data.get("arch_underlay_block")
        if self.layer_show_arch and isinstance(arch_block, dict) and arch_block.get("visible", True):
            arch_pen = QPen(QColor("#475569"), 1.1)
            for seg in arch_block.get("segments", []):
                self.scene_2d.addLine(
                    float(seg[0]) * s, -float(seg[1]) * s,
                    float(seg[2]) * s, -float(seg[3]) * s,
                    arch_pen,
                )

        # 1. Outer Building Boundary Polyline (00-XD-EDGE in Cyan)
        edge = story_data.get("slab_edge_polygon", [])
        if len(edge) >= 3:
            is_sel_edge = self.selected_element and self.selected_element.get("kind") == "slab_edge"
            edge_pen = QPen(QColor("#F8FAFC" if is_sel_edge else "#06B6D4"), 3.0 if is_sel_edge else 2.2)
            poly = QPolygonF([QPointF(float(p[0]) * s, -float(p[1]) * s) for p in edge])
            self.scene_2d.addPolygon(poly, edge_pen, QBrush(QColor(6, 182, 212, 10)))

        # 2. Picked Slabs (00-XD-SLAB) & Openings (00-XD-OPEN)
        if self.layer_show_slabs:
            for slb in story_data.get("slabs", []):
                if "min_x" not in slb:
                    continue
                min_x, max_x = float(slb["min_x"]), float(slb["max_x"])
                min_y, max_y = float(slb["min_y"]), float(slb["max_y"])
                rect = QRectF(min_x * s, -max_y * s, (max_x - min_x) * s, (max_y - min_y) * s)
                is_cant = bool(slb.get("is_cantilever", False))
                is_sel_slab = self.selected_element and self.selected_element.get("kind") == "slab" and self.selected_element.get("id") == slb.get("id")
                fill_col = QColor(245, 158, 11, 42) if is_cant else QColor(56, 189, 248, 22)
                border_pen = QPen(QColor("#F8FAFC" if is_sel_slab else "#38BDF8"), 2 if is_sel_slab else 1, Qt.PenStyle.DotLine)
                self.scene_2d.addRect(rect, border_pen, QBrush(fill_col))

                # Subtle rib lines inside bay
                rib_dir = int(slb.get("rib_direction_deg", 0))
                rib_pen = QPen(QColor(234, 179, 8, 70), 1, Qt.PenStyle.DashLine)
                if rib_dir == 0:
                    y_step = min_y + 0.55
                    while y_step < max_y - 0.25:
                        self.scene_2d.addLine((min_x + 0.2) * s, -y_step * s, (max_x - 0.2) * s, -y_step * s, rib_pen)
                        y_step += 0.55
                else:
                    x_step = min_x + 0.55
                    while x_step < max_x - 0.25:
                        self.scene_2d.addLine(x_step * s, -(min_y + 0.2) * s, x_step * s, -(max_y - 0.2) * s, rib_pen)
                        x_step += 0.55

                cx = (min_x + max_x) / 2.0
                cy = (min_y + max_y) / 2.0
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
                is_sel_op = self.selected_element and self.selected_element.get("kind") == "opening" and self.selected_element.get("id") == op.get("id")
                open_pen = QPen(QColor("#F8FAFC" if is_sel_op else "#EC4899"), 2.5 if is_sel_op else 2)
                self.scene_2d.addRect(rect, open_pen, QBrush(QColor(236, 72, 153, 35)))
                self.scene_2d.addLine(min_x * s, -min_y * s, max_x * s, -max_y * s, open_pen)
                self.scene_2d.addLine(min_x * s, -max_y * s, max_x * s, -min_y * s, open_pen)

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

                is_sel_bm = self.selected_element and self.selected_element.get("kind") == "beam" and self.selected_element.get("id") == bm.get("id")
                if b_kind == "hidden":
                    border_col = QColor("#F8FAFC" if is_sel_bm else "#EAB308")
                    pen_style = Qt.PenStyle.DashLine
                    hatch_brush = QBrush(QColor(234, 179, 8, 130), Qt.BrushStyle.DiagCrossPattern)
                    bg_brush = QBrush(QColor(234, 179, 8, 26))
                else:
                    border_col = QColor("#F8FAFC" if is_sel_bm else "#10B981")
                    pen_style = Qt.PenStyle.SolidLine
                    hatch_brush = QBrush(QColor(16, 185, 129, 145), Qt.BrushStyle.BDiagPattern)
                    bg_brush = QBrush(QColor(16, 185, 129, 30))

                self.scene_2d.addPolygon(beam_poly, QPen(Qt.PenStyle.NoPen), bg_brush)
                self.scene_2d.addPolygon(beam_poly, QPen(border_col, 2.2 if is_sel_bm else 1.5, pen_style), hatch_brush)

                if self.layer_show_tags:
                    tx, ty, _ = compute_smart_beam_tag_position(bm, columns, placed_tags)
                    txt = self.scene_2d.addText(f"{bm['id']}", QFont("Arial", 9, QFont.Weight.Bold))
                    txt.setDefaultTextColor(QColor("#FB923C"))
                    txt.setPos(tx * s - 10, -ty * s - 12)

        # 4. Columns (0.20 x 0.40 m Strictly Inside Boundary) & Bright Green Column Tags
        if self.layer_show_cols:
            for col in columns:
                if not col.get("active", True):
                    continue
                cx, cy = float(col["x"]), float(col["y"])
                b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
                is_sel_col = self.selected_element and self.selected_element.get("kind") == "column" and self.selected_element.get("id") == col.get("id")
                rect = QRectF((cx - b / 2.0) * s, -(cy + h / 2.0) * s, b * s, h * s)
                col_pen = QPen(QColor("#F8FAFC" if is_sel_col else "#EF4444"), 2.6 if is_sel_col else 2)
                self.scene_2d.addRect(rect, col_pen, QBrush(QColor(239, 68, 68, 125)))

                if self.layer_show_tags:
                    tag_x = cx + b / 2.0 + 0.10
                    tag_y = cy + h / 2.0 + 0.10
                    ctxt = self.scene_2d.addText(str(col["id"]), QFont("Arial", 9, QFont.Weight.Bold))
                    ctxt.setDefaultTextColor(QColor("#4ADE80"))
                    ctxt.setPos(tag_x * s, -tag_y * s - 10)

        # 5. Active Polyline Boundary Rubber-Band Preview
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

        # 6. Active Beam Rubber-Band Preview
        if self._first_click_pt is not None and self._current_snap_info is not None and self.active_tool in ("DRAW_BEAM_HID", "DRAW_BEAM_DROP", "MOVE_ELEMENT"):
            fx, fy = self._first_click_pt
            tx, ty = self._current_snap_info["x"], self._current_snap_info["y"]
            self.scene_2d.addLine(fx * s, -fy * s, tx * s, -ty * s, QPen(QColor("#38BDF8"), 1.8, Qt.PenStyle.DashLine))

        # 7. Visual Magnetic OSNAP Indicator
        if self._current_snap_info is not None and self.osnap_enabled:
            ox, oy = self._current_snap_info["x"], self._current_snap_info["y"]
            stype = self._current_snap_info["snap_type"]
            if stype != "GRID":
                marker_rect = QRectF(ox * s - 5, -oy * s - 5, 10, 10)
                self.scene_2d.addRect(marker_rect, QPen(QColor("#FACC15"), 2), QBrush(Qt.BrushStyle.NoBrush))


class XpertStudioMainWindow(QMainWindow):
    """
    Main Studio Workspace for Xpert Structural Design Studio.
    Uses Classic Menu Bar + Classic Toolbars (Zero Ribbon).
    """

    def __init__(self, initial_master_project: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.setWindowTitle(f"Xpert Structural Design Studio — {STUDIO_VERSION} (ACI 318-19)")
        self.resize(1540, 930)
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
            self.statusBar().showMessage(
                f"Loaded Project: {self.master_project.get('project_name')} ({self.master_project.get('master_file', '')})"
            )

    def _build_classic_menu_bar(self) -> None:
        mbar = self.menuBar()

        # File Menu
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

        # Edit Menu
        m_edit = mbar.addMenu("&Edit")
        act_rot_col = QAction("Rotate Selected Column 90° (R)", self)
        act_rot_col.setShortcut("R")
        act_rot_col.triggered.connect(self.rotate_selected_or_default_column)
        m_edit.addAction(act_rot_col)

        act_del = QAction("Delete Selected Object", self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(self.delete_selected_object)
        m_edit.addAction(act_del)

        # View Menu
        m_view = mbar.addMenu("&View")
        act_zext = QAction("Zoom Extents", self)
        act_zext.triggered.connect(lambda: self.cad_canvas.zoom_extents())
        m_view.addAction(act_zext)

        self.act_osnap = QAction("Toggle Object Snap (OSNAP)", self, checkable=True, checked=True)
        self.act_osnap.setShortcut("F3")
        self.act_osnap.toggled.connect(self._toggle_osnap)
        m_view.addAction(self.act_osnap)

        self.act_ortho = QAction("Toggle Orthogonal Lock (ORTHO)", self, checkable=True, checked=True)
        self.act_ortho.setShortcut("F8")
        self.act_ortho.toggled.connect(self._toggle_ortho)
        m_view.addAction(self.act_ortho)

        # Draw & Modify Menu
        m_draw = mbar.addMenu("&Draw && Modify")
        for label, tool_id in [
            ("Select Element (Arrow Cursor / Click Rib Label to Flip)", "SELECT"),
            ("Pan View (Hand Cursor)", "PAN"),
            ("Step 1: Draw Building Boundary Polyline (00-XD-EDGE)", "DRAW_SLAB_EDGE"),
            ("Step 2: Place Structural Column 0.20x0.40m (00-XD-COL)", "DRAW_COL"),
            ("Step 3A: Draw Hidden Beam 0.40m Width (00-XD-BEAM-HID)", "DRAW_BEAM_HID"),
            ("Step 3B: Draw Drop Beam 0.20m Width (00-XD-BEAM-DROP)", "DRAW_BEAM_DROP"),
            ("Step 4A: Pick Area -> Create Slab (Auto Shortest / 3-Beam Rule)", "PICK_SLAB"),
            ("Step 4B: Pick Area -> Toggle Void Opening (Slab <-> Opening)", "PICK_OPENING"),
            ("Productivity: Auto-Fill All Story Slabs (1-Click)", "AUTO_FILL_SLABS"),
            ("Productivity: Convert Columns from Imported Arch .DXF", "CONVERT_ARCH_COLS"),
            ("Modify: Move Column or Beam", "MOVE_ELEMENT"),
            ("Load Standard 2-Bay Structural Layout", "LOAD_TEMPLATE"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, tid=tool_id: self.activate_cad_tool(tid))
            m_draw.addAction(act)

        # Analyze Menu
        m_analyze = mbar.addMenu("&Analyze")
        act_all = QAction("Analyze All Beams (F5)", self)
        act_all.setShortcut("F5")
        act_all.triggered.connect(self.run_analyze_all_beams)
        m_analyze.addAction(act_all)

        # Design Menu
        m_design = mbar.addMenu("De&sign")
        act_des = QAction("Design All Beams, Columns && Foundations (ACI 318)", self)
        act_des.triggered.connect(lambda: self.switch_workspace_mode(2))
        m_design.addAction(act_des)

        # Reports Menu
        m_rep = mbar.addMenu("&Reports")
        act_rep = QAction("Generate Master Calculation Report", self)
        act_rep.triggered.connect(lambda: self.switch_workspace_mode(3))
        m_rep.addAction(act_rep)

    def _build_classic_toolbars(self) -> None:
        # Top Classic Toolbar
        top_tb = QToolBar("Standard Studio Toolbar", self)
        top_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, top_tb)

        btn_new = QPushButton("New Project...")
        btn_new.clicked.connect(self.open_new_project_dialog)
        top_tb.addWidget(btn_new)

        btn_open = QPushButton("Open (.xpert)...")
        btn_open.clicked.connect(self.open_existing_project_file_dialog)
        top_tb.addWidget(btn_open)

        btn_imp_dxf = QPushButton("Import Arch .DXF")
        btn_imp_dxf.setToolTip("Import Architectural .DXF file as a locked background block for the active story")
        btn_imp_dxf.clicked.connect(self.import_arch_dxf_for_current_story)
        top_tb.addWidget(btn_imp_dxf)

        btn_save = QPushButton("Save && Sync .DXF (Ctrl+S)")
        btn_save.clicked.connect(self.save_and_sync_current_story)
        top_tb.addWidget(btn_save)
        top_tb.addSeparator()

        top_tb.addWidget(QLabel(" Active Story: "))
        self.cb_story = QComboBox()
        self.cb_story.setMinimumWidth(210)
        self.cb_story.currentIndexChanged.connect(self._on_story_changed)
        top_tb.addWidget(self.cb_story)
        top_tb.addSeparator()

        top_tb.addWidget(QLabel(" Col Size: "))
        self.cb_col_orient = QComboBox()
        self.cb_col_orient.addItems(["Vertical (0.20 × 0.40 m)", "Horizontal (0.40 × 0.20 m)"])
        top_tb.addWidget(self.cb_col_orient)

        top_tb.addWidget(QLabel(" Col Boundary: "))
        self.cb_col_boundary_rule = QComboBox()
        self.cb_col_boundary_rule.addItems([
            "Auto-Shift Inside Edge",
            "Auto-Expand Boundary",
        ])
        top_tb.addWidget(self.cb_col_boundary_rule)
        top_tb.addSeparator()

        for idx, m_label in enumerate([
            "1. 2D CAD Modeler",
            "2. Beam Analysis",
            "3. R.C. Design && Columns P-M",
            "4. Calculation Report",
        ]):
            b = QPushButton(m_label)
            b.clicked.connect(lambda checked=False, i=idx: self.switch_workspace_mode(i))
            top_tb.addWidget(b)

        top_tb.addSeparator()
        btn_run_all = QPushButton("Analyze All Beams (F5)")
        btn_run_all.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px;")
        btn_run_all.clicked.connect(self.run_analyze_all_beams)
        top_tb.addWidget(btn_run_all)

        # Left Vertical CAD Toolbar
        left_tb = QToolBar("CAD Drawing Tools", self)
        left_tb.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left_tb)

        for label, tid in [
            ("1. Polyline Boundary", "DRAW_SLAB_EDGE"),
            ("2. Place Column", "DRAW_COL"),
            ("Rotate Col 90° (R)", "ROTATE_COL"),
            ("3A. + Hidden Beam", "DRAW_BEAM_HID"),
            ("3B. + Drop Beam", "DRAW_BEAM_DROP"),
            ("4A. Pick: Slab", "PICK_SLAB"),
            ("4B. Pick: Flip Rib", "FLIP_RIB"),
            ("4C. Pick: Opening", "PICK_OPENING"),
            ("Auto-Fill All Slabs", "AUTO_FILL_SLABS"),
            ("Select (Arrow)", "SELECT"),
            ("Delete Selected (Del)", "DELETE_SELECTED"),
            ("Move Col / Beam", "MOVE_ELEMENT"),
            ("Pan (Hand)", "PAN"),
            ("Zoom Extents", "ZOOM_EXTENTS"),
            ("Demo Layout", "LOAD_TEMPLATE"),
        ]:
            btn = QPushButton(label)
            if tid == "DELETE_SELECTED":
                btn.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold;")
                btn.clicked.connect(self.delete_selected_object)
            elif tid == "ROTATE_COL":
                btn.clicked.connect(self.rotate_selected_or_default_column)
            elif tid == "AUTO_FILL_SLABS":
                btn.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold;")
                btn.clicked.connect(lambda: self.activate_cad_tool("AUTO_FILL_SLABS"))
            else:
                btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
            left_tb.addWidget(btn)

    def _build_main_workspace(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setSpacing(4)

        # Bar 1: Top Automatic ACI 318 Thickness & Optimization Bar
        thick_frame = QFrame()
        thick_frame.setFrameShape(QFrame.Shape.StyledPanel)
        thick_row = QHBoxLayout(thick_frame)
        thick_row.setContentsMargins(8, 4, 8, 4)

        self.lbl_calc_thick = QLabel("Calculated Min. Thickness: -- (Awaiting CAD Data)")
        self.lbl_calc_thick.setStyleSheet("font-weight: bold; color: #0284C7;")
        self.lbl_gov_member = QLabel("Governing Critical Member: None")

        self.sp_adopted_thick = QDoubleSpinBox()
        self.sp_adopted_thick.setRange(14.0, 100.0)
        self.sp_adopted_thick.setValue(30.0)
        self.sp_adopted_thick.setSuffix(" cm")

        btn_apply_thick = QPushButton("Apply Story Thickness")
        btn_apply_thick.clicked.connect(self.apply_story_thickness)

        self.btn_smart_opt = QPushButton("Convert Critical Hidden Beam to Drop Beam")
        self.btn_smart_opt.setStyleSheet("background-color: #F59E0B; color: black; font-weight: bold;")
        self.btn_smart_opt.setVisible(False)
        self.btn_smart_opt.clicked.connect(self.convert_critical_beam_to_drop)

        thick_row.addWidget(self.lbl_calc_thick)
        thick_row.addWidget(self.lbl_gov_member, 1)
        thick_row.addWidget(self.btn_smart_opt)
        thick_row.addWidget(QLabel("Adopted Story Slab Thickness:"))
        thick_row.addWidget(self.sp_adopted_thick)
        thick_row.addWidget(btn_apply_thick)
        vbox.addWidget(thick_frame)

        # Bar 2: Layer Visibility & Freeze Controls (Show/Hide Arch DXF, Columns, Beams, Slabs & Ribs, Tags)
        layer_frame = QFrame()
        layer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        layer_row = QHBoxLayout(layer_frame)
        layer_row.setContentsMargins(8, 2, 8, 2)
        layer_row.addWidget(QLabel("Layer Visibility && Freeze:"))

        self.chk_layer_arch = QCheckBox("Arch DXF Block")
        self.chk_layer_arch.setChecked(True)
        self.chk_layer_arch.toggled.connect(self._on_layer_visibility_changed)
        layer_row.addWidget(self.chk_layer_arch)

        self.chk_layer_cols = QCheckBox("Columns (00-XD-COL)")
        self.chk_layer_cols.setChecked(True)
        self.chk_layer_cols.toggled.connect(self._on_layer_visibility_changed)
        layer_row.addWidget(self.chk_layer_cols)

        self.chk_layer_beams = QCheckBox("Beams (00-XD-BEAM)")
        self.chk_layer_beams.setChecked(True)
        self.chk_layer_beams.toggled.connect(self._on_layer_visibility_changed)
        layer_row.addWidget(self.chk_layer_beams)

        self.chk_layer_slabs = QCheckBox("Slabs && Ribs (Uncheck to Freeze Slabs while Drawing Beams)")
        self.chk_layer_slabs.setChecked(True)
        self.chk_layer_slabs.toggled.connect(self._on_layer_visibility_changed)
        layer_row.addWidget(self.chk_layer_slabs)

        self.chk_layer_tags = QCheckBox("Labels (C# / B# / S#)")
        self.chk_layer_tags.setChecked(True)
        self.chk_layer_tags.toggled.connect(self._on_layer_visibility_changed)
        layer_row.addWidget(self.chk_layer_tags)
        layer_row.addStretch(1)
        vbox.addWidget(layer_frame)

        self.stack = QStackedWidget()
        vbox.addWidget(self.stack, 1)

        # Mode 0: 2D CAD Modeler
        self.cad_canvas = StructuralCadCanvas2D(self)
        self.stack.addWidget(self.cad_canvas)

        # Mode 1: All Beams Analysis Table
        self.tbl_beams = QTableWidget(0, 7)
        self.tbl_beams.setHorizontalHeaderLabels([
            "Beam ID", "Type", "Section (m)", "Spans (m)", "Max +Mu (kN.m)", "Face -Mu (kN.m)", "Face Vu (kN)"
        ])
        self.tbl_beams.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stack.addWidget(self.tbl_beams)

        # Mode 2: R.C. Design & Columns 4-Way Framing
        self.tbl_columns = QTableWidget(0, 7)
        self.tbl_columns.setHorizontalHeaderLabels([
            "Column ID", "Section", "Story Pu (kN)", "End Moments (Mux, Muy)",
            "4-Way Framing (N/S/E/W)", "Reinforcement (ACI 318)", "Capacity phi*Pn (kN)"
        ])
        self.tbl_columns.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stack.addWidget(self.tbl_columns)

        # Mode 3: Master Calculation Report
        self.report_browser = QTextBrowser()
        self.stack.addWidget(self.report_browser)

        self.setStatusBar(QStatusBar())

    def _on_layer_visibility_changed(self) -> None:
        self.cad_canvas.layer_show_arch = self.chk_layer_arch.isChecked()
        self.cad_canvas.layer_show_cols = self.chk_layer_cols.isChecked()
        self.cad_canvas.layer_show_beams = self.chk_layer_beams.isChecked()
        self.cad_canvas.layer_show_slabs = self.chk_layer_slabs.isChecked()
        self.cad_canvas.layer_show_tags = self.chk_layer_tags.isChecked()
        self.cad_canvas.render_story(self.current_story_data)

    def _toggle_osnap(self, checked: bool) -> None:
        self.cad_canvas.osnap_enabled = checked
        self.statusBar().showMessage(f"Object Snap (OSNAP): {'ON' if checked else 'OFF'}")

    def _toggle_ortho(self, checked: bool) -> None:
        self.cad_canvas.ortho_enabled = checked
        self.statusBar().showMessage(f"Orthogonal Lock (ORTHO): {'ON' if checked else 'OFF'}")

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
            self.statusBar().showMessage(
                f"Imported Architectural DXF '{arch_block['source_file']}' ({len(arch_block['segments'])} segments) as Locked Block for this story."
            )
        except Exception as exc:
            QMessageBox.critical(self, "DXF Import Error", str(exc))

    def rotate_selected_or_default_column(self) -> None:
        sel = self.cad_canvas.selected_element
        if sel and sel.get("kind") == "column":
            boundary_mode = "clamp" if self.cb_col_boundary_rule.currentIndex() == 0 else "expand"
            ok, msg = rotate_column_90_deg(self.current_story_data, sel["id"], boundary_mode=boundary_mode)
            if ok:
                self.save_and_sync_current_story()
                self.refresh_story_ui()
                self.statusBar().showMessage(msg)
            return
        # Otherwise toggle the default column orientation selector in the toolbar
        new_idx = 1 if self.cb_col_orient.currentIndex() == 0 else 0
        self.cb_col_orient.setCurrentIndex(new_idx)
        self.statusBar().showMessage(f"Switched new column orientation to: {self.cb_col_orient.currentText()}")

    def open_new_project_dialog(self) -> bool:
        dlg = NewProjectSetupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.opened_existing_master_path:
                self.load_project_from_file(dlg.opened_existing_master_path)
            else:
                cfg = dlg.get_config()
                self.master_project = initialize_studio_project(cfg)
                self._populate_story_selector()
                self.switch_workspace_mode(0)
                self.statusBar().showMessage(
                    f"Created Project: {self.master_project['master_file']} — Opened on 02_Ground_Floor."
                )
            return True
        return False

    def open_existing_project_file_dialog(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Xpert Structural Master Project File",
            os.path.abspath("./XpertStudio_Projects"),
            f"Xpert Project Master (*{MASTER_FILE_EXT} *-00_Project_Master.json);;All Files (*)",
        )
        if fpath and os.path.isfile(fpath):
            self.load_project_from_file(fpath)

    def load_project_from_file(self, master_file_path: str) -> None:
        try:
            self.master_project = load_studio_project_from_master_file(master_file_path)
            self._populate_story_selector()
            self.switch_workspace_mode(0)
            self.statusBar().showMessage(
                f"Opened Existing Project: {self.master_project.get('project_name')} from {master_file_path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Project", str(exc))

    def delete_selected_object(self) -> None:
        sel = self.cad_canvas.selected_element
        if not sel:
            self.statusBar().showMessage("No object selected. Click on a Column, Beam, Slab, Opening, or Boundary first.")
            return
        ok, msg = delete_selected_element_from_story(
            self.current_story_data, sel["kind"], sel["id"]
        )
        if not ok:
            QMessageBox.warning(self, "Cannot Delete Object", msg)
            return
        self.cad_canvas.selected_element = None
        self.save_and_sync_current_story()
        self.refresh_story_ui()
        self.statusBar().showMessage(msg)

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

        if tool_id == "AUTO_FILL_SLABS":
            count, msg = auto_fill_all_story_slabs(self.current_story_data)
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.statusBar().showMessage(msg)
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
                    c_obj = {"id": cid, "x": rc["x"], "y": rc["y"], "b_m": 0.20, "h_m": 0.40, "active": True}
                    if len(poly) >= 3:
                        c_obj, poly, _ = enforce_column_inside_slab_boundary(c_obj, poly, mode="clamp")
                    cols.append(c_obj)
                    added += 1
            self.current_story_data["slab_edge_polygon"] = poly
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.statusBar().showMessage(f"Converted {added} Architectural Columns to 0.20x0.40m Structural Columns.")
            return

        if tool_id == "LOAD_TEMPLATE":
            # Clean 2x2 Bay Layout: All columns 0.20x0.40m strictly inside [0, 0] - [10.0, 8.5],
            # Hidden Beams 0.40m width, Drop Beams 0.20m width, and 4 clean Slabs (S1..S4) with ZERO sliver strips!
            self.current_story_data["slab_edge_polygon"] = [[0, 0], [10.0, 0], [10.0, 8.5], [0, 8.5]]
            self.current_story_data["columns"] = [
                {"id": "C1", "x": 0.10, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.20, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 9.90, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.10, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 5.20, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C6", "x": 9.90, "y": 4.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C7", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C8", "x": 5.20, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C9", "x": 9.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ]
            self.current_story_data["beams"] = [
                {
                    "id": "B1", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
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
                    "id": "B2", "beam_kind": "hidden", "width_m": 0.40, "depth_m": 0.30,
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
                    "id": "B3", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
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
                    "id": "B4", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
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
                    "id": "B5", "beam_kind": "hidden", "width_m": 0.40, "depth_m": 0.30,
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
                    "id": "B6", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
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
        self.cad_canvas.update_cursor_for_active_tool()
        self.statusBar().showMessage(f"Activated CAD Tool: {tool_id}")

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
        self.tbl_beams.setRowCount(len(beams))
        for r_i, bm in enumerate(beams):
            bid = bm["id"]
            res = self.last_analysis_bundle["beam_results"].get(bid, {})
            self.tbl_beams.setItem(r_i, 0, QTableWidgetItem(bid))
            self.tbl_beams.setItem(r_i, 1, QTableWidgetItem(bm.get("beam_kind", "hidden").upper()))
            self.tbl_beams.setItem(r_i, 2, QTableWidgetItem(f"{bm.get('width_m', 0.4):.2f} x {bm.get('depth_m', 0.3):.2f}"))
            self.tbl_beams.setItem(r_i, 3, QTableWidgetItem(", ".join(str(s) for s in bm.get("spans", []))))
            self.tbl_beams.setItem(r_i, 4, QTableWidgetItem(f"{res.get('max_pos_mu_knm', 0.0):.2f}"))
            self.tbl_beams.setItem(r_i, 5, QTableWidgetItem(f"{res.get('max_neg_face_mu_knm', 0.0):.2f}"))
            self.tbl_beams.setItem(r_i, 6, QTableWidgetItem(f"{res.get('max_face_vu_kn', 0.0):.2f}"))

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
            f"<b>Beams Analyzed:</b> {len(beams)} | <b>Columns Designed:</b> {len(col_recs)}</p>"
        )
        self.switch_workspace_mode(1)

    def switch_workspace_mode(self, mode_idx: int) -> None:
        self.stack.setCurrentIndex(mode_idx)


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
        if not arg.startswith("-") and arg.lower().endswith((MASTER_FILE_EXT, ".json")) and os.path.isfile(arg):
            cli_project_path = arg
            break

    if cli_project_path:
        master_data = load_studio_project_from_master_file(cli_project_path)
        win = XpertStudioMainWindow(initial_master_project=master_data)
        win.show()
        sys.exit(app.exec())

    startup_dlg = NewProjectSetupDialog()
    if startup_dlg.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    if startup_dlg.opened_existing_master_path:
        master_data = load_studio_project_from_master_file(startup_dlg.opened_existing_master_path)
    else:
        master_data = initialize_studio_project(startup_dlg.get_config())

    win = XpertStudioMainWindow(initial_master_project=master_data)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
