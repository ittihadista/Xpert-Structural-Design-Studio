"""
Xpert Structural Design Studio (v1.0.0-studio-foundation)
Main Desktop Application (PyQt6 + ezdxf + Matplotlib)
Lead Structural Engineer & Product Owner: Eng. Yousef Mohammed Keshlaf

UI Architecture:
- 100% English-Only UI (LTR), Zero Ribbon.
- Modal New Project Setup Dialog (closes on OK and opens main studio on 02_Ground_Floor).
- Classic Top Pull-Down Menu Bar + Top Standard Toolbar + Left Vertical CAD Toolbar.
- Built-in 2D Structural CAD Studio Canvas (Zoom/Pan, OSNAP, Ortho, DXF Underlay,
  Green Column Tags outside corners, Orange Beam Tags at clear-span midpoints).
- 1-Click 'Analyze All Beams (F5)' Master Summary Table + Interactive Beam Inspector.
- Column 4-Way Framing Connectivity, Cumulative Load Takedown & P-M Interaction Diagrams.
- Master Printable Calculation Report Generator.
"""

from __future__ import annotations
import json
import math
import os
import sys
from typing import Dict, Any, List, Optional, Tuple

try:
    from shapely.geometry import Point, LineString, Polygon
except ImportError:
    Point = LineString = Polygon = None

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen, QBrush, QPolygonF, QIcon
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
    QSplitter,
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
    check_duplicate_column,
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


class NewProjectSetupDialog(QDialog):
    """
    Modal Project Definition Dialog (like ETABS / SAFE / Robot).
    Closes automatically on OK after initializing Stractural-<ProjectName> on disk.
    Also provides a direct shortcut to open an existing .xpert master project.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Structural Project — Xpert Structural Design Studio")
        self.setMinimumWidth(680)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.selected_existing_master_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        # Top Bar: Open Existing Project (.xpert)
        top_open_box = QHBoxLayout()
        btn_open_exist = QPushButton("📂  Open Existing Project (.xpert / .json)...")
        btn_open_exist.setStyleSheet(
            "background-color: #0284C7; color: white; font-weight: bold; padding: 7px 16px; font-size: 13px; border-radius: 4px;"
        )
        btn_open_exist.clicked.connect(self._open_existing_project)
        top_open_box.addWidget(btn_open_exist)
        top_open_box.addStretch()
        root_layout.addLayout(top_open_box)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root_layout.addWidget(sep)

        # 1. Project Identity
        grp_id = QGroupBox("1. Project Identity && Workspace Folder")
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

        # 2. Story Hierarchy & Exact Heights
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

        # 3. Materials, Soil & Default Geometry (Explicit Ranges > 99.99)
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

        root_layout.addWidget(grp_mat)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Create Project && Open Studio")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root_layout.addWidget(btns)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Root Projects Directory")
        if folder:
            self.ed_folder.setText(folder)

    def _open_existing_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Existing Master Project",
            self.ed_folder.text().strip() or os.path.abspath("./XpertStudio_Projects"),
            "Xpert Studio Master Project (*-00_Project_Master.xpert *-00_Project_Master.json *.xpert *.json);;All Files (*.*)",
        )
        if file_path and os.path.isfile(file_path):
            self.selected_existing_master_path = file_path
            self.accept()

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


class StructuralCadCanvas2D(QGraphicsView):
    """
    Built-in 2D Interactive Structural CAD Canvas with dark CAD theme,
    wheel zoom, middle-click pan, magnetic OSNAP (F3), Ortho lock (F8),
    and color-coded non-overlapping tags:
    - Columns (C1..Cn): Bright Green (#4ADE80) outside top-right corner.
    - Beams (B1..Bm): Bright Orange (#FB923C) at clear-span midpoint.
    - Slabs (00-XD-SLAB): Dark navy fill with Gold one-way ribs and badges.
    - Openings (00-XD-OPEN): Magenta dashed outline with diagonal X.
    - Slab Boundary (00-XD-EDGE): Cyan polygon with corner vertex markers.
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self.scene_2d = QGraphicsScene(self)
        self.setScene(self.scene_2d)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0D1117")))
        self.scale_px = 45.0  # 1m = 45px
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self.active_tool = "SELECT"
        self.osnap_enabled = True
        self.ortho_enabled = False
        self.is_panning = False
        self.pan_last_pos: Optional[QPointF] = None
        self.draw_start_pt: Optional[Tuple[float, float]] = None
        self.current_snap: Optional[Dict[str, Any]] = None
        self.move_element: Optional[Dict[str, Any]] = None

        self.polyline_pts: List[Tuple[float, float]] = []
        self.selected_element: Optional[Dict[str, Any]] = None
        self.cached_bay_badges: List[Dict[str, Any]] = []

        self.snap_marker_item = None
        self.rubber_band_item = None

    def toggle_osnap(self, state: Optional[bool] = None) -> None:
        if state is None:
            self.osnap_enabled = not self.osnap_enabled
        else:
            self.osnap_enabled = state
        if not self.osnap_enabled:
            self.hide_snap_marker()
        if hasattr(self.studio, "btn_osnap"):
            self.studio.btn_osnap.setChecked(self.osnap_enabled)
            self.studio.btn_osnap.setText(f"OSNAP [F3]: {'ON' if self.osnap_enabled else 'OFF'}")

    def toggle_ortho(self, state: Optional[bool] = None) -> None:
        if state is None:
            self.ortho_enabled = not self.ortho_enabled
        else:
            self.ortho_enabled = state
        if hasattr(self.studio, "btn_ortho"):
            self.studio.btn_ortho.setChecked(self.ortho_enabled)
            self.studio.btn_ortho.setText(f"ORTHO [F8]: {'ON' if self.ortho_enabled else 'OFF'}")

    def zoom_extents(self) -> None:
        rect = self.scene_2d.itemsBoundingRect()
        if not rect.isEmpty():
            self.fitInView(rect.adjusted(-25, -25, 25, 25), Qt.AspectRatioMode.KeepAspectRatio)

    def cancel_current_operation(self) -> None:
        self.draw_start_pt = None
        self.move_element = None
        self.polyline_pts = []
        self.selected_element = None
        self.hide_rubber_band()
        self.hide_snap_marker()
        self.studio.refresh_story_ui()
        self.studio.statusBar().showMessage("Operation cancelled / Selection cleared.")

    def delete_selected(self) -> None:
        if not self.selected_element:
            self.studio.statusBar().showMessage("No element selected to delete. Click an element first or use Select tool.")
            return
        ok, msg = delete_selected_element_from_story(self.studio.current_story_data, self.selected_element)
        if ok:
            self.selected_element = None
            self.studio.save_and_sync_current_story()
            self.studio.refresh_story_ui()
            self.studio.statusBar().showMessage(msg)
        else:
            QMessageBox.warning(self.studio, "Cannot Delete Element", msg)

    def finish_polyline_boundary(self) -> None:
        if len(self.polyline_pts) < 3:
            QMessageBox.warning(self.studio, "Incomplete Boundary", "Boundary polyline requires at least 3 vertices to form a closed polygon.")
            return
        pts = list(self.polyline_pts)
        if Polygon is not None:
            poly = Polygon(pts)
            if not poly.is_valid or poly.area < 0.2:
                QMessageBox.warning(
                    self.studio,
                    "Invalid Boundary",
                    "The drawn polyline does not form a valid, non-self-intersecting closed polygon.",
                )
                return
        new_poly = [[round(p[0], 2), round(p[1], 2)] for p in pts]
        self.studio.current_story_data["slab_edge_polygon"] = new_poly
        self.polyline_pts = []
        self.draw_start_pt = None
        self.hide_rubber_band()
        self.studio.save_and_sync_current_story()
        self.studio.refresh_story_ui()
        self.studio.statusBar().showMessage(
            f"Outer Slab Polyline Boundary closed with {len(new_poly)} vertices. Ready for Step 2: Place Columns."
        )
        self.studio.activate_cad_tool("ADD_COL")

    def find_snap_candidate(self, mx: float, my: float) -> Optional[Dict[str, Any]]:
        if not self.osnap_enabled:
            return None

        tol = 14.0 / self.scale_px
        story = self.studio.current_story_data
        columns = story.get("columns", [])
        beams = story.get("beams", [])
        edge = story.get("slab_edge_polygon", [])

        # Priority 0: Architectural Underlay Snap Points (when Arch DXF layer is visible)
        if self.studio.is_layer_visible("arch"):
            arch_block = story.get("arch_underlay_block")
            if arch_block and arch_block.get("visible", True):
                for pt in arch_block.get("snap_points", []):
                    px, py = float(pt[0]), float(pt[1])
                    if ((mx - px) ** 2 + (my - py) ** 2) ** 0.5 <= tol:
                        return {"type": "Arch DXF Snap", "x": px, "y": py}

        # Priority 1: Columns (Center & Corners) - when Columns layer visible
        if self.studio.is_layer_visible("columns"):
            for col in columns:
                if not col.get("active", True):
                    continue
                cx, cy = float(col["x"]), float(col["y"])
                b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
                if ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5 <= tol:
                    return {"type": f"Column Center [{col['id']}]", "x": cx, "y": cy}
                for dx, dy in [(-b/2, -h/2), (b/2, -h/2), (b/2, h/2), (-b/2, h/2)]:
                    cor_x, cor_y = cx + dx, cy + dy
                    if ((mx - cor_x) ** 2 + (my - cor_y) ** 2) ** 0.5 <= tol:
                        return {"type": f"Column Corner [{col['id']}]", "x": cor_x, "y": cor_y}

        # Priority 2: Beams (Endpoints, Supports, Midpoints) - when Beams layer visible
        if self.studio.is_layer_visible("beams"):
            for bm in beams:
                bid = str(bm.get("id", "B"))
                sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
                if ((mx - sx) ** 2 + (my - sy) ** 2) ** 0.5 <= tol:
                    return {"type": f"Beam Endpoint [{bid}]", "x": sx, "y": sy}
                if ((mx - ex) ** 2 + (my - ey) ** 2) ** 0.5 <= tol:
                    return {"type": f"Beam Endpoint [{bid}]", "x": ex, "y": ey}
                for sup in bm.get("supports", []):
                    if "x" in sup and "y" in sup:
                        spx, spy = float(sup["x"]), float(sup["y"])
                        if ((mx - spx) ** 2 + (my - spy) ** 2) ** 0.5 <= tol:
                            return {"type": f"Beam Support [{sup.get('target_id', 'Sup')}]", "x": spx, "y": spy}
                mid_x, mid_y = (sx + ex) / 2.0, (sy + ey) / 2.0
                if ((mx - mid_x) ** 2 + (my - mid_y) ** 2) ** 0.5 <= tol:
                    return {"type": f"Beam Midpoint [{bid}]", "x": mid_x, "y": mid_y}

        # Priority 3: Slab Boundary Corners & Edges
        if edge and len(edge) >= 3:
            for idx, pt in enumerate(edge):
                px, py = float(pt[0]), float(pt[1])
                if ((mx - px) ** 2 + (my - py) ** 2) ** 0.5 <= tol:
                    return {"type": f"Slab Boundary Corner [{idx+1}]", "x": px, "y": py}
            for idx in range(len(edge)):
                p1, p2 = edge[idx], edge[(idx + 1) % len(edge)]
                x1, y1 = float(p1[0]), float(p1[1])
                x2, y2 = float(p2[0]), float(p2[1])
                dx, dy = x2 - x1, y2 - y1
                l2 = dx * dx + dy * dy
                if l2 > 1e-6:
                    t = max(0.0, min(1.0, ((mx - x1) * dx + (my - y1) * dy) / l2))
                    proj_x = x1 + t * dx
                    proj_y = y1 + t * dy
                    if ((mx - proj_x) ** 2 + (my - proj_y) ** 2) ** 0.5 <= tol:
                        return {"type": "Slab Boundary Edge", "x": round(proj_x, 2), "y": round(proj_y, 2)}

        # Priority 4: 0.10m Grid Snap
        gx = round(mx * 10.0) / 10.0
        gy = round(my * 10.0) / 10.0
        if ((mx - gx) ** 2 + (my - gy) ** 2) ** 0.5 <= tol:
            return {"type": "0.10m Grid Snap", "x": gx, "y": gy}

        return None

    def apply_ortho(self, x: float, y: float, origin: Optional[Tuple[float, float]]) -> Tuple[float, float]:
        if not self.ortho_enabled or origin is None:
            return x, y
        ox, oy = origin
        if abs(x - ox) >= abs(y - oy):
            return x, oy
        return ox, y

    def update_snap_marker(self, sx: float, sy: float) -> None:
        s = self.scale_px
        sc_x = sx * s
        sc_y = -sy * s
        if self.snap_marker_item is None:
            pen = QPen(QColor("#FACC15"), 2)
            self.snap_marker_item = self.scene_2d.addRect(QRectF(-7, -7, 14, 14), pen, QBrush(Qt.BrushStyle.NoBrush))
            self.snap_marker_item.setZValue(100)
        self.snap_marker_item.setPos(sc_x, sc_y)
        self.snap_marker_item.setVisible(True)

    def hide_snap_marker(self) -> None:
        if self.snap_marker_item:
            self.snap_marker_item.setVisible(False)

    def update_rubber_band(self, x1: float, y1: float, x2: float, y2: float) -> None:
        s = self.scale_px
        if self.rubber_band_item:
            self.scene_2d.removeItem(self.rubber_band_item)
            self.rubber_band_item = None

        if self.active_tool == "DRAW_SLAB_EDGE":
            pen = QPen(QColor("#06B6D4"), 2, Qt.PenStyle.DashLine)
            self.rubber_band_item = self.scene_2d.addLine(x1 * s, -y1 * s, x2 * s, -y2 * s, pen)
            self.rubber_band_item.setZValue(90)
        elif self.active_tool in ("ADD_HID_BEAM", "ADD_DROP_BEAM"):
            color = QColor("#EAB308") if self.active_tool == "ADD_HID_BEAM" else QColor("#10B981")
            pen = QPen(color, 3, Qt.PenStyle.DashDotLine)
            self.rubber_band_item = self.scene_2d.addLine(x1 * s, -y1 * s, x2 * s, -y2 * s, pen)
            self.rubber_band_item.setZValue(90)

    def hide_rubber_band(self) -> None:
        if self.rubber_band_item:
            self.scene_2d.removeItem(self.rubber_band_item)
            self.rubber_band_item = None

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        # Middle click Pan
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = True
            self.pan_last_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Right click to close or cancel polyline boundary
        if event.button() == Qt.MouseButton.RightButton:
            if self.active_tool == "DRAW_SLAB_EDGE":
                if len(self.polyline_pts) >= 3:
                    self.finish_polyline_boundary()
                else:
                    self.polyline_pts = []
                    self.hide_rubber_band()
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage("Polyline boundary drawing cancelled.")
                event.accept()
                return

        # Left click
        if event.button() == Qt.MouseButton.LeftButton:
            if self.active_tool == "PAN":
                self.is_panning = True
                self.pan_last_pos = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

            sp = self.mapToScene(event.pos())
            raw_x = sp.x() / self.scale_px
            raw_y = -sp.y() / self.scale_px

            # 1-Click Rib Label Toggle: STRICT ISOLATION!
            # Only allowed when active tool is SELECT or PICK_FLIP_RIB and Slabs layer is visible
            if self.active_tool in ("SELECT", "PICK_FLIP_RIB") and self.studio.is_layer_visible("slabs"):
                for badge in self.cached_bay_badges:
                    bx, by = badge["center"]
                    if ((raw_x - bx) ** 2 + (raw_y - by) ** 2) ** 0.5 <= 0.85:
                        edge = self.studio.current_story_data.get("slab_edge_polygon", [])
                        beams = self.studio.current_story_data.get("beams", [])
                        slabs = self.studio.current_story_data.get("slabs", [])
                        openings = self.studio.current_story_data.get("openings", [])
                        ok, msg, new_slabs = flip_rib_direction_with_equilibrium(
                            badge["center"], edge, beams, slabs, openings
                        )
                        if ok:
                            self.studio.current_story_data["slabs"] = new_slabs
                            self.studio.save_and_sync_current_story()
                            self.studio.refresh_story_ui()
                            self.studio.statusBar().showMessage(f"1-Click Rib Toggle: {msg}")
                        else:
                            QMessageBox.warning(self.studio, "Cantilever Equilibrium Warning", msg)
                        event.accept()
                        return

            snap = self.find_snap_candidate(raw_x, raw_y)
            cx = snap["x"] if snap else round(raw_x * 10.0) / 10.0
            cy = snap["y"] if snap else round(raw_y * 10.0) / 10.0

            # Step 1: Draw Multi-Point Polyline Boundary
            if self.active_tool == "DRAW_SLAB_EDGE":
                pt = (cx, cy)
                if self.ortho_enabled and len(self.polyline_pts) >= 1:
                    pt = self.apply_ortho(cx, cy, self.polyline_pts[-1])

                # Check if clicking near first vertex V1 to close
                if len(self.polyline_pts) >= 3:
                    v1 = self.polyline_pts[0]
                    if ((pt[0] - v1[0]) ** 2 + (pt[1] - v1[1]) ** 2) ** 0.5 <= 0.35:
                        self.finish_polyline_boundary()
                        event.accept()
                        return

                self.polyline_pts.append(pt)
                self.studio.refresh_story_ui()
                self.studio.statusBar().showMessage(
                    f"Polyline Boundary: Vertex {len(self.polyline_pts)} at ({pt[0]:.2f}, {pt[1]:.2f}). "
                    f"Click next vertex, click near V1 to close, or press Enter/C / Right-Click."
                )
                event.accept()
                return

            # Step 2: Place Column (Default 0.20 x 0.40 m with orientation toggle)
            if self.active_tool == "ADD_COL":
                rule = self.studio.get_column_boundary_rule()
                b_m, h_m = self.studio.get_column_dimensions()
                edge = self.studio.current_story_data.get("slab_edge_polygon", [])
                final_x, final_y, updated_poly, _ = clamp_or_expand_column_boundary(
                    cx, cy, b_m, h_m, edge, rule=rule
                )

                cols = self.studio.current_story_data.get("columns", [])
                dup_ok, dup_msg = check_duplicate_column(final_x, final_y, b_m, h_m, cols)
                if not dup_ok:
                    QMessageBox.warning(self.studio, "Duplicate Column Rejected", dup_msg)
                    event.accept()
                    return

                if updated_poly != edge:
                    self.studio.current_story_data["slab_edge_polygon"] = updated_poly

                col_id = f"C{len(cols) + 1}"
                cols.append({
                    "id": col_id,
                    "x": final_x,
                    "y": final_y,
                    "b_m": b_m,
                    "h_m": h_m,
                    "active": True,
                })
                self.studio.current_story_data["columns"] = cols
                self.studio.save_and_sync_current_story()
                self.studio.refresh_story_ui()
                self.studio.statusBar().showMessage(
                    f"Placed Column {col_id} ({b_m:.2f}x{h_m:.2f}m) at ({final_x:.2f}, {final_y:.2f}) m."
                )
                event.accept()
                return

            # Step 3: Draw Hidden / Drop Beam (Multi-Span Continuous Beam with Smart Reconcile)
            if self.active_tool in ("ADD_HID_BEAM", "ADD_DROP_BEAM"):
                b_kind = "hidden" if self.active_tool == "ADD_HID_BEAM" else "drop"
                if self.draw_start_pt is None:
                    self.draw_start_pt = (cx, cy)
                    self.studio.statusBar().showMessage(f"Beam Start at ({cx:.2f}, {cy:.2f}). Click beam end point.")
                else:
                    x1, y1 = self.draw_start_pt
                    x2, y2 = self.apply_ortho(cx, cy, (x1, y1))
                    if ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 < 0.20:
                        QMessageBox.warning(self.studio, "Invalid Beam", "Beam length must be at least 0.20 m.")
                        self.draw_start_pt = None
                        self.hide_rubber_band()
                        return

                    width_m = 0.40 if b_kind == "hidden" else 0.20
                    depth_m = 0.30 if b_kind == "hidden" else 0.50

                    ok, msg, new_beam = validate_and_build_beam_with_cantilevers(
                        (x1, y1), (x2, y2), b_kind, width_m, depth_m, self.studio.current_story_data
                    )
                    if not ok:
                        QMessageBox.warning(self.studio, "Cannot Add Beam", msg)
                        self.draw_start_pt = None
                        self.hide_rubber_band()
                        return

                    self.studio.current_story_data.setdefault("beams", []).append(new_beam)
                    self.draw_start_pt = None
                    self.hide_rubber_band()

                    # Smart Automatic Slab Splitting when new beam cuts through existing slabs
                    reconcile_and_split_slabs_after_beam_change(self.studio.current_story_data)

                    self.studio.save_and_sync_current_story()
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(
                        f"Added Beam {new_beam['id']} ({b_kind}) with {len(new_beam.get('spans', []))} span(s)."
                    )
                event.accept()
                return
                event.accept()
                return

            # Step 4A: Pick Area: Slab
            if self.active_tool == "PICK_SLAB":
                edge = self.studio.current_story_data.get("slab_edge_polygon", [])
                beams = self.studio.current_story_data.get("beams", [])
                slabs = self.studio.current_story_data.get("slabs", [])
                openings = self.studio.current_story_data.get("openings", [])
                ok, msg, new_slabs, new_ops = pick_area_slab((cx, cy), edge, beams, slabs, openings)
                if ok:
                    self.studio.current_story_data["slabs"] = new_slabs
                    self.studio.current_story_data["openings"] = new_ops
                    self.studio.save_and_sync_current_story()
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(msg)
                else:
                    QMessageBox.warning(self.studio, "Pick Area Failed", msg)
                event.accept()
                return

            # Step 4B: Pick: Flip Rib Direction
            if self.active_tool == "PICK_FLIP_RIB":
                edge = self.studio.current_story_data.get("slab_edge_polygon", [])
                beams = self.studio.current_story_data.get("beams", [])
                slabs = self.studio.current_story_data.get("slabs", [])
                openings = self.studio.current_story_data.get("openings", [])
                ok, msg, new_slabs = flip_rib_direction_with_equilibrium((cx, cy), edge, beams, slabs, openings)
                if ok:
                    self.studio.current_story_data["slabs"] = new_slabs
                    self.studio.save_and_sync_current_story()
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(msg)
                else:
                    QMessageBox.warning(self.studio, "Cantilever Equilibrium Warning", msg)
                event.accept()
                return

            # Step 4C: Pick: Toggle Opening
            if self.active_tool == "PICK_OPENING":
                edge = self.studio.current_story_data.get("slab_edge_polygon", [])
                beams = self.studio.current_story_data.get("beams", [])
                slabs = self.studio.current_story_data.get("slabs", [])
                openings = self.studio.current_story_data.get("openings", [])
                ok, msg, new_slabs, new_ops = toggle_bay_slab_or_opening((cx, cy), edge, beams, slabs, openings)
                if ok:
                    self.studio.current_story_data["slabs"] = new_slabs
                    self.studio.current_story_data["openings"] = new_ops
                    self.studio.save_and_sync_current_story()
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(msg)
                else:
                    QMessageBox.warning(self.studio, "Opening Protection Warning", msg)
                event.accept()
                return

            # CAD Move Tool
            if self.active_tool == "MOVE":
                if self.move_element is None:
                    cols = self.studio.current_story_data.get("columns", [])
                    beams = self.studio.current_story_data.get("beams", [])
                    hit_col = None
                    for c in cols:
                        if not c.get("active", True):
                            continue
                        if ((cx - float(c["x"]))**2 + (cy - float(c["y"]))**2)**0.5 <= 0.45:
                            hit_col = c
                            break
                    if hit_col:
                        self.move_element = {"kind": "column", "id": hit_col["id"], "start_pt": (float(hit_col["x"]), float(hit_col["y"]))}
                        self.studio.statusBar().showMessage(f"Selected Column {hit_col['id']} to move. Click target destination.")
                        event.accept()
                        return

                    hit_beam = None
                    for b in beams:
                        bl = LineString([(float(b["start_x"]), float(b["start_y"])), (float(b["end_x"]), float(b["end_y"]))])
                        if bl.distance(Point(cx, cy)) <= 0.35:
                            hit_beam = b
                            break
                    if hit_beam:
                        self.move_element = {"kind": "beam", "id": hit_beam["id"], "start_pt": (cx, cy)}
                        self.studio.statusBar().showMessage(f"Selected Beam {hit_beam['id']} to move. Click destination point.")
                        event.accept()
                        return

                    self.studio.statusBar().showMessage("Move tool: Click directly on a Column or Beam to select it first.")
                else:
                    kind = self.move_element["kind"]
                    elem_id = self.move_element["id"]
                    cols = self.studio.current_story_data.get("columns", [])
                    beams = self.studio.current_story_data.get("beams", [])
                    edge = self.studio.current_story_data.get("slab_edge_polygon", [])
                    rule = self.studio.get_column_boundary_rule()

                    if kind == "column":
                        ok, msg, new_cols, new_bms, new_poly = move_column_and_update_connected_beams(
                            elem_id, cx, cy, cols, beams, edge, rule=rule
                        )
                        if ok:
                            self.studio.current_story_data["columns"] = new_cols
                            self.studio.current_story_data["beams"] = new_bms
                            self.studio.current_story_data["slab_edge_polygon"] = new_poly
                            self.studio.save_and_sync_current_story()
                            self.studio.refresh_story_ui()
                            self.studio.statusBar().showMessage(msg)
                        else:
                            QMessageBox.warning(self.studio, "Move Failed", msg)

                    elif kind == "beam":
                        ox, oy = self.move_element["start_pt"]
                        dx = cx - ox
                        dy = cy - oy
                        ok, msg, new_bms = move_beam_and_update(elem_id, dx, dy, beams, edge)
                        if ok:
                            self.studio.current_story_data["beams"] = new_bms
                            self.studio.save_and_sync_current_story()
                            self.studio.refresh_story_ui()
                            self.studio.statusBar().showMessage(msg)
                        else:
                            QMessageBox.warning(self.studio, "Move Failed", msg)

                    self.move_element = None
                event.accept()
                return

            # SELECT Tool: Pick and Highlight Any Element (for Deletion or Inspection)
            if self.active_tool == "SELECT":
                cols = self.studio.current_story_data.get("columns", [])
                beams = self.studio.current_story_data.get("beams", [])
                slabs = self.studio.current_story_data.get("slabs", [])
                openings = self.studio.current_story_data.get("openings", [])
                edge = self.studio.current_story_data.get("slab_edge_polygon", [])

                # Check columns
                hit_col = None
                for c in cols:
                    if not c.get("active", True):
                        continue
                    cx_col, cy_col = float(c["x"]), float(c["y"])
                    bw, bh = float(c.get("b_m", 0.20)), float(c.get("h_m", 0.40))
                    if abs(raw_x - cx_col) <= bw / 2.0 + 0.15 and abs(raw_y - cy_col) <= bh / 2.0 + 0.15:
                        hit_col = c
                        break
                if hit_col:
                    self.selected_element = {"type": "column", "id": hit_col["id"], "data": hit_col}
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(
                        f"Selected Column {hit_col['id']} ({hit_col.get('b_m', 0.2):.2f}x{hit_col.get('h_m', 0.4):.2f}m). Press Del to delete."
                    )
                    event.accept()
                    return

                # Check beams
                hit_beam = None
                for b in beams:
                    bl = LineString([(float(b["start_x"]), float(b["start_y"])), (float(b["end_x"]), float(b["end_y"]))])
                    bw = float(b.get("width_m", 0.3))
                    if bl.distance(Point(raw_x, raw_y)) <= bw / 2.0 + 0.15:
                        hit_beam = b
                        break
                if hit_beam:
                    self.selected_element = {"type": "beam", "id": hit_beam["id"], "data": hit_beam}
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(
                        f"Selected Beam {hit_beam['id']} ({hit_beam.get('beam_kind', 'beam').upper()}). Press Del to delete."
                    )
                    event.accept()
                    return

                # Check openings
                hit_op = None
                for op in openings:
                    op_poly = Polygon(op.get("polygon", [])) if op.get("polygon") else None
                    if op_poly and op_poly.contains(Point(raw_x, raw_y)):
                        hit_op = op
                        break
                if hit_op:
                    self.selected_element = {"type": "opening", "id": hit_op.get("id"), "point": (raw_x, raw_y)}
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage("Selected Opening [00-XD-OPEN]. Press Del to delete.")
                    event.accept()
                    return

                # Check slabs
                hit_slab = None
                for s_entry in slabs:
                    spoly = Polygon(s_entry.get("polygon", [])) if s_entry.get("polygon") else None
                    if spoly and spoly.contains(Point(raw_x, raw_y)):
                        hit_slab = s_entry
                        break
                if hit_slab:
                    self.selected_element = {"type": "slab", "id": hit_slab.get("id"), "point": (raw_x, raw_y)}
                    self.studio.refresh_story_ui()
                    self.studio.statusBar().showMessage(f"Selected Slab {hit_slab.get('id')}. Press Del to delete.")
                    event.accept()
                    return

                # Check edge boundary
                if edge and len(edge) >= 3 and Polygon is not None:
                    epoly = Polygon(edge)
                    if epoly.exterior.distance(Point(raw_x, raw_y)) <= 0.35:
                        self.selected_element = {"type": "edge", "id": "00-XD-EDGE"}
                        self.studio.refresh_story_ui()
                        self.studio.statusBar().showMessage("Selected Outer Slab Boundary [00-XD-EDGE]. Press Del to delete.")
                        event.accept()
                        return

                self.selected_element = None
                self.studio.refresh_story_ui()
                self.studio.statusBar().showMessage("Selection cleared.")
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if getattr(self, "is_panning", False) and self.pan_last_pos is not None:
            delta = event.pos() - self.pan_last_pos
            self.pan_last_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return

        sp = self.mapToScene(event.pos())
        raw_x = sp.x() / self.scale_px
        raw_y = -sp.y() / self.scale_px

        snap = self.find_snap_candidate(raw_x, raw_y)
        snap_x = snap["x"] if snap else round(raw_x * 10.0) / 10.0
        snap_y = snap["y"] if snap else round(raw_y * 10.0) / 10.0

        if self.ortho_enabled and self.draw_start_pt is not None:
            snap_x, snap_y = self.apply_ortho(snap_x, snap_y, self.draw_start_pt)
        elif self.ortho_enabled and self.active_tool == "DRAW_SLAB_EDGE" and len(self.polyline_pts) >= 1:
            snap_x, snap_y = self.apply_ortho(snap_x, snap_y, self.polyline_pts[-1])

        # Status Bar updates
        snap_str = snap["type"] if snap else "Free Cursor"
        osnap_str = "ON" if self.osnap_enabled else "OFF"
        ortho_str = "ON" if self.ortho_enabled else "OFF"
        self.studio.statusBar().showMessage(
            f"Cursor: (X = {snap_x:.2f} m, Y = {snap_y:.2f} m) | Snap: {snap_str} | OSNAP [F3]: {osnap_str} | ORTHO [F8]: {ortho_str} | Tool: {self.active_tool}"
        )

        # Dynamic Snap Marker
        if snap and snap["type"] != "0.10m Grid Snap":
            self.update_snap_marker(snap_x, snap_y)
        else:
            self.hide_snap_marker()

        # Dynamic Rubber-band Preview
        if self.draw_start_pt is not None:
            self.update_rubber_band(self.draw_start_pt[0], self.draw_start_pt[1], snap_x, snap_y)
        elif self.active_tool == "DRAW_SLAB_EDGE" and len(self.polyline_pts) >= 1:
            self.update_rubber_band(self.polyline_pts[-1][0], self.polyline_pts[-1][1], snap_x, snap_y)
        else:
            self.hide_rubber_band()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            if getattr(self, "is_panning", False):
                self.is_panning = False
                self.pan_last_pos = None
                if self.active_tool == "PAN":
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                elif self.active_tool == "SELECT":
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                else:
                    self.setCursor(Qt.CursorShape.CrossCursor)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        if event.key() == Qt.Key.Key_R:
            self.studio.rotate_selected_column()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_C):
            if self.active_tool == "DRAW_SLAB_EDGE" and len(self.polyline_pts) >= 3:
                self.finish_polyline_boundary()
                event.accept()
                return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_current_operation()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F3:
            self.toggle_osnap()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F8:
            self.toggle_ortho()
            event.accept()
            return
        super().keyPressEvent(event)

    def render_story(self, story_data: Dict[str, Any]) -> None:
        self.scene_2d.clear()
        self.snap_marker_item = None
        self.rubber_band_item = None
        self.cached_bay_badges = []
        s = self.scale_px

        edge = story_data.get("slab_edge_polygon", [])
        columns = story_data.get("columns", [])
        beams = story_data.get("beams", [])
        slabs = story_data.get("slabs", [])
        openings = story_data.get("openings", [])

        # Determine bounds for Grid
        all_xs = [-2.0, 16.0]
        all_ys = [-2.0, 12.0]
        if edge and len(edge) >= 3:
            all_xs += [float(p[0]) for p in edge]
            all_ys += [float(p[1]) for p in edge]
        min_gx = int(math.floor(min(all_xs)) - 2)
        max_gx = int(math.ceil(max(all_xs)) + 2)
        min_gy = int(math.floor(min(all_ys)) - 2)
        max_gy = int(math.ceil(max(all_ys)) + 2)

        # Coordinate Grid (1m spacing)
        grid_pen = QPen(QColor("#161F2C"), 1, Qt.PenStyle.DotLine)
        for gx in range(min_gx, max_gx + 1):
            self.scene_2d.addLine(gx * s, -min_gy * s, gx * s, -max_gy * s, grid_pen)
        for gy in range(min_gy, max_gy + 1):
            self.scene_2d.addLine(min_gx * s, -gy * s, max_gx * s, -gy * s, grid_pen)

        # 0. Architectural DXF Reference Underlay Block (00-XD-ARCH-REF in quiet gray #64748B)
        arch_block = story_data.get("arch_underlay_block")
        if arch_block and self.studio.is_layer_visible("arch") and arch_block.get("visible", True):
            arch_pen = QPen(QColor("#64748B"), 1.2, Qt.PenStyle.SolidLine)
            for seg in arch_block.get("segments", []):
                if len(seg) >= 4:
                    self.scene_2d.addLine(
                        float(seg[0]) * s, -float(seg[1]) * s,
                        float(seg[2]) * s, -float(seg[3]) * s,
                        arch_pen,
                    )
            for circ in arch_block.get("circles", []):
                if len(circ) >= 3:
                    cx, cy, r = float(circ[0]), float(circ[1]), float(circ[2])
                    self.scene_2d.addEllipse(
                        (cx - r) * s, -(cy + r) * s,
                        2 * r * s, 2 * r * s,
                        arch_pen,
                        QBrush(Qt.BrushStyle.NoBrush),
                    )

        # 1. Slab Bays & Openings (00-XD-SLAB & 00-XD-OPEN)
        if edge and len(edge) >= 3 and self.studio.is_layer_visible("slabs"):
            detected_bays = detect_bays_and_determine_ribs(edge, beams, slabs, openings)
            for bay in detected_bays:
                poly = QPolygonF([QPointF(float(p[0]) * s, -float(p[1]) * s) for p in bay["polygon"]])
                if bay.get("is_opening", False):
                    # Void Opening
                    self.scene_2d.addPolygon(poly, QPen(QColor("#D946EF"), 2, Qt.PenStyle.DashLine), QBrush(QColor(217, 70, 239, 30)))
                    bds = bay["bounds"]
                    self.scene_2d.addLine(bds[0] * s, -bds[1] * s, bds[2] * s, -bds[3] * s, QPen(QColor("#D946EF"), 1, Qt.PenStyle.DotLine))
                    self.scene_2d.addLine(bds[0] * s, -bds[3] * s, bds[2] * s, -bds[1] * s, QPen(QColor("#D946EF"), 1, Qt.PenStyle.DotLine))
                    if self.studio.is_layer_visible("labels"):
                        txt_op = self.scene_2d.addText("OPENING\n[00-XD-OPEN]", QFont("Arial", 8, QFont.Weight.Bold))
                        txt_op.setDefaultTextColor(QColor("#D946EF"))
                        txt_op.setPos(bay["center"][0] * s - 30, -bay["center"][1] * s - 12)
                else:
                    # Solid Slab
                    self.scene_2d.addPolygon(poly, QPen(QColor("#1E293B"), 1), QBrush(QColor(15, 36, 58, 110)))
                    # Draw rib direction lines
                    rib_pen = QPen(QColor(234, 179, 8, 80), 1, Qt.PenStyle.DashLine)
                    bds = bay["bounds"]
                    rib_deg = float(bay.get("rib_direction_deg", 0.0))
                    if rib_deg == 0.0:
                        curr_y = bds[1] + 0.55
                        while curr_y < bds[3] - 0.20:
                            self.scene_2d.addLine(bds[0] * s, -curr_y * s, bds[2] * s, -curr_y * s, rib_pen)
                            curr_y += 0.55
                    else:
                        curr_x = bds[0] + 0.55
                        while curr_x < bds[2] - 0.20:
                            self.scene_2d.addLine(curr_x * s, -bds[1] * s, curr_x * s, -bds[3] * s, rib_pen)
                            curr_x += 0.55

                    # Cache badge position for 1-Click Rib Label Toggle
                    self.cached_bay_badges.append({
                        "id": bay["id"],
                        "center": bay["center"],
                        "rib_deg": rib_deg,
                    })

                    if self.studio.is_layer_visible("labels"):
                        badge = f"{bay['id']} ({bay['lx']:.1f}x{bay['ly']:.1f}m | {rib_deg:.0f}°)"
                        if bay.get("is_cantilever"):
                            badge += "\n[CANTILEVER]"
                        txt_s = self.scene_2d.addText(badge, QFont("Arial", 8, QFont.Weight.Bold))
                        txt_s.setDefaultTextColor(QColor("#FBBF24"))
                        txt_s.setPos(bay["center"][0] * s - 35, -bay["center"][1] * s - 12)

                # Selection highlight on slab
                if self.selected_element and self.selected_element.get("type") == "slab" and self.selected_element.get("id") == bay["id"]:
                    self.scene_2d.addPolygon(poly, QPen(QColor("#38BDF8"), 3, Qt.PenStyle.DashLine), QBrush(Qt.BrushStyle.NoBrush))

        # 2. Slab Boundary (00-XD-EDGE in Cyan)
        if len(edge) >= 3:
            poly = QPolygonF([QPointF(float(p[0]) * s, -float(p[1]) * s) for p in edge])
            pen_edge = QPen(QColor("#06B6D4"), 2)
            if self.selected_element and self.selected_element.get("type") in ("edge", "boundary"):
                pen_edge = QPen(QColor("#FACC15"), 3, Qt.PenStyle.DashLine)
            self.scene_2d.addPolygon(poly, pen_edge, QBrush(Qt.BrushStyle.NoBrush))
            for pt in edge:
                px, py = float(pt[0]) * s, -float(pt[1]) * s
                self.scene_2d.addRect(QRectF(px - 3, py - 3, 6, 6), QPen(QColor("#06B6D4")), QBrush(QColor("#06B6D4")))

        # In-progress polyline boundary vertices
        if self.active_tool == "DRAW_SLAB_EDGE" and len(self.polyline_pts) >= 1:
            for i in range(len(self.polyline_pts) - 1):
                p_a = self.polyline_pts[i]
                p_b = self.polyline_pts[i + 1]
                self.scene_2d.addLine(p_a[0] * s, -p_a[1] * s, p_b[0] * s, -p_b[1] * s, QPen(QColor("#06B6D4"), 2, Qt.PenStyle.SolidLine))
            for idx, p in enumerate(self.polyline_pts):
                color = QColor("#FACC15") if idx == 0 else QColor("#06B6D4")
                self.scene_2d.addRect(QRectF(p[0] * s - 4, -p[1] * s - 4, 8, 8), QPen(color, 2), QBrush(color))

        # 3. Beams: Full-Width Hatched Rectangles & Non-Overlapping Orange Beam Tags
        if self.studio.is_layer_visible("beams"):
            placed_tags = []
            for col in columns:
                if col.get("active", True):
                    placed_tags.append((float(col["x"]) + 0.25, float(col["y"]) + 0.25))

            for bm in beams:
                sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                ex, ey = float(bm.get("end_x", 5.0)), float(bm.get("end_y", 0.0))
                b_kind = bm.get("beam_kind", "hidden")
                def_w = 0.40 if b_kind == "hidden" else 0.20
                width_m = float(bm.get("width_m", def_w))
                half_w = width_m / 2.0

                dx = ex - sx
                dy = ey - sy
                length = max(0.01, (dx * dx + dy * dy) ** 0.5)
                ux = dx / length
                uy = dy / length
                nx = -uy
                ny = ux

                p1 = (sx - nx * half_w, sy - ny * half_w)
                p2 = (ex - nx * half_w, ey - ny * half_w)
                p3 = (ex + nx * half_w, ey + ny * half_w)
                p4 = (sx + nx * half_w, sy + ny * half_w)

                poly = QPolygonF([
                    QPointF(p1[0] * s, -p1[1] * s),
                    QPointF(p2[0] * s, -p2[1] * s),
                    QPointF(p3[0] * s, -p3[1] * s),
                    QPointF(p4[0] * s, -p4[1] * s),
                ])

                if b_kind == "hidden":
                    pen = QPen(QColor("#EAB308"), 2, Qt.PenStyle.DashLine)
                    brush = QBrush(QColor(234, 179, 8, 80), Qt.BrushStyle.DiagCrossPattern)
                else:
                    pen = QPen(QColor("#10B981"), 2, Qt.PenStyle.SolidLine)
                    brush = QBrush(QColor(16, 185, 129, 90), Qt.BrushStyle.BDiagPattern)

                self.scene_2d.addPolygon(poly, pen, brush)

                # Centerline subtle guide line
                self.scene_2d.addLine(sx * s, -sy * s, ex * s, -ey * s, QPen(QColor(255, 255, 255, 50), 1, Qt.PenStyle.DashDotLine))

                # Selection highlight on beam
                if self.selected_element and self.selected_element.get("type") == "beam" and self.selected_element.get("id") == bm.get("id"):
                    self.scene_2d.addPolygon(poly, QPen(QColor("#38BDF8"), 3, Qt.PenStyle.SolidLine), QBrush(Qt.BrushStyle.NoBrush))

                # Smart beam tag raised above upper face
                if self.studio.is_layer_visible("labels"):
                    tx, ty, _ = compute_smart_beam_tag_position(bm, columns, placed_tags)
                    txt = self.scene_2d.addText(f"{bm['id']}", QFont("Arial", 9, QFont.Weight.Bold))
                    txt.setDefaultTextColor(QColor("#FB923C"))  # Bright Orange
                    txt.setPos(tx * s - 10, -ty * s - 12)

        # 4. Columns & Bright Green Column Tags Outside Corner
        if self.studio.is_layer_visible("columns"):
            for col in columns:
                if not col.get("active", True):
                    continue
                cx, cy = float(col["x"]), float(col["y"])
                b = float(col.get("b_m", 0.20))
                h = float(col.get("h_m", 0.40))
                rect = QRectF((cx - b / 2.0) * s, -(cy + h / 2.0) * s, b * s, h * s)
                self.scene_2d.addRect(rect, QPen(QColor("#EF4444"), 2), QBrush(QColor(239, 68, 68, 90)))

                # Selection highlight on column
                if self.selected_element and self.selected_element.get("type") == "column" and self.selected_element.get("id") == col.get("id"):
                    self.scene_2d.addRect(rect.adjusted(-2, -2, 2, 2), QPen(QColor("#38BDF8"), 3), QBrush(Qt.BrushStyle.NoBrush))

                if self.studio.is_layer_visible("labels"):
                    tag_x = cx + b / 2.0 + 0.12
                    tag_y = cy + h / 2.0 + 0.12
                    ctxt = self.scene_2d.addText(str(col["id"]), QFont("Arial", 9, QFont.Weight.Bold))
                    ctxt.setDefaultTextColor(QColor("#4ADE80"))  # Bright Green
                    ctxt.setPos(tag_x * s, -tag_y * s - 10)


class XpertStudioMainWindow(QMainWindow):
    """
    Main Studio Workspace for Xpert Structural Design Studio (v1.0.0).
    Uses Classic Menu Bar + Classic Toolbars (Zero Ribbon).
    """

    def __init__(self, master_file_path: Optional[str] = None):
        super().__init__()
        self.setWindowTitle(f"Xpert Structural Design Studio — {STUDIO_VERSION} (ACI 318-19)")
        self.resize(1460, 900)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.master_project: Optional[Dict[str, Any]] = None
        self.current_story_index: int = 0
        self.current_story_data: Dict[str, Any] = {}
        self.last_analysis_bundle: Optional[Dict[str, Any]] = None

        self._build_classic_menu_bar()
        self._build_classic_toolbars()
        self._build_main_workspace()

        if master_file_path and os.path.isfile(master_file_path):
            self.load_master_project(master_file_path)

    def _build_classic_menu_bar(self) -> None:
        mbar = self.menuBar()

        # File Menu
        m_file = mbar.addMenu("&File")
        act_new = QAction("New Structural Project...", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.open_new_project_dialog)
        m_file.addAction(act_new)

        act_open = QAction("&Open Project (.xpert)...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.browse_and_open_project)
        m_file.addAction(act_open)

        act_save = QAction("Save Story && Sync .DXF", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_and_sync_current_story)
        m_file.addAction(act_save)

        act_import_arch = QAction("&Import Architectural Underlay (.DXF)...", self)
        act_import_arch.setStatusTip("Import architectural DXF reference underlay for the active story")
        act_import_arch.triggered.connect(self.import_arch_dxf_dialog)
        m_file.addAction(act_import_arch)

        m_file.addSeparator()
        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.setStatusTip("Close and exit Xpert Structural Design Studio")
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # Edit Menu (Object Deletion)
        m_edit = mbar.addMenu("&Edit")
        act_del = QAction("&Delete Selected Object", self)
        act_del.setShortcut("Delete")
        act_del.setStatusTip("Delete the selected CAD element (Del / Backspace)")
        act_del.triggered.connect(lambda: self.cad_canvas.delete_selected())
        m_edit.addAction(act_del)

        # View Menu
        m_view = mbar.addMenu("&View")
        act_pan = QAction("Pan (Hand)", self)
        act_pan.triggered.connect(lambda: self.activate_cad_tool("PAN"))
        m_view.addAction(act_pan)

        act_zoom_ext = QAction("Zoom Extents", self)
        act_zoom_ext.triggered.connect(lambda: self.activate_cad_tool("ZOOM_EXTENTS"))
        m_view.addAction(act_zoom_ext)

        m_view.addSeparator()
        act_osnap = QAction("Toggle OSNAP (F3)", self)
        act_osnap.setShortcut("F3")
        act_osnap.triggered.connect(lambda: self.cad_canvas.toggle_osnap())
        m_view.addAction(act_osnap)

        act_ortho = QAction("Toggle Ortho (F8)", self)
        act_ortho.setShortcut("F8")
        act_ortho.triggered.connect(lambda: self.cad_canvas.toggle_ortho())
        m_view.addAction(act_ortho)

        # Draw Menu (Strict 4-Step Sequence)
        m_draw = mbar.addMenu("&Draw && Modify")
        for label, tool_id in [
            ("1. Draw Outer Polyline Boundary [00-XD-EDGE]", "DRAW_SLAB_EDGE"),
            ("2. Place Column [00-XD-COL]", "ADD_COL"),
            ("3A. Draw Hidden Beam [00-XD-BEAM-HID]", "ADD_HID_BEAM"),
            ("3B. Draw Drop Beam [00-XD-BEAM-DROP]", "ADD_DROP_BEAM"),
            ("4A. Pick Area: Slab [00-XD-SLAB]", "PICK_SLAB"),
            ("4B. Pick: Flip Rib Direction", "PICK_FLIP_RIB"),
            ("4C. Pick: Toggle Slab <-> Opening [00-XD-OPEN]", "PICK_OPENING"),
            ("---", None),
            ("Rotate Column 90° (R)", "ROTATE_COL"),
            ("Auto-Fill All Slabs", "AUTO_FILL_SLABS"),
            ("---", None),
            ("Select / Pick Element", "SELECT"),
            ("Delete Selected Element (Del)", "DELETE_SELECTED"),
            ("Move Column / Beam", "MOVE"),
            ("Load Standard 2-Bay Structural Layout", "LOAD_TEMPLATE"),
        ]:
            if tool_id is None:
                m_draw.addSeparator()
            else:
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

        btn_open = QPushButton("Open Project...")
        btn_open.clicked.connect(self.browse_and_open_project)
        top_tb.addWidget(btn_open)

        btn_save = QPushButton("Save && Sync .DXF (Ctrl+S)")
        btn_save.clicked.connect(self.save_and_sync_current_story)
        top_tb.addWidget(btn_save)

        btn_import_arch = QPushButton("Import Arch .DXF")
        btn_import_arch.setStyleSheet("background-color: #334155; color: white; font-weight: bold;")
        btn_import_arch.setStatusTip("Import architectural DXF reference underlay for the active story")
        btn_import_arch.clicked.connect(self.import_arch_dxf_dialog)
        top_tb.addWidget(btn_import_arch)
        top_tb.addSeparator()

        top_tb.addWidget(QLabel("  Active Story: "))
        self.cb_story = QComboBox()
        self.cb_story.setMinimumWidth(240)
        self.cb_story.currentIndexChanged.connect(self._on_story_changed)
        top_tb.addWidget(self.cb_story)
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
        top_tb.addWidget(QLabel("Col Size: "))
        self.cb_col_size = QComboBox()
        self.cb_col_size.addItems([
            "Vertical (0.20 x 0.40 m)",
            "Horizontal (0.40 x 0.20 m)",
        ])
        top_tb.addWidget(self.cb_col_size)

        top_tb.addSeparator()
        top_tb.addWidget(QLabel("Col Boundary: "))
        self.cb_col_rule = QComboBox()
        self.cb_col_rule.addItems([
            "Auto-Clamp Column Flush Inside Edge",
            "Auto-Expand Slab Boundary to Fit Column",
        ])
        top_tb.addWidget(self.cb_col_rule)

        top_tb.addSeparator()
        self.btn_osnap = QPushButton("OSNAP [F3]: ON")
        self.btn_osnap.setCheckable(True)
        self.btn_osnap.setChecked(True)
        self.btn_osnap.toggled.connect(self._on_toggle_osnap)
        top_tb.addWidget(self.btn_osnap)

        self.btn_ortho = QPushButton("ORTHO [F8]: OFF")
        self.btn_ortho.setCheckable(True)
        self.btn_ortho.setChecked(False)
        self.btn_ortho.toggled.connect(self._on_toggle_ortho)
        top_tb.addWidget(self.btn_ortho)

        top_tb.addSeparator()
        btn_run_all = QPushButton("Analyze All Beams (F5)")
        btn_run_all.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px;")
        btn_run_all.clicked.connect(self.run_analyze_all_beams)
        top_tb.addWidget(btn_run_all)

        # Left Vertical CAD Toolbar (Strict 4-Step Sequence + Edit Actions)
        left_tb = QToolBar("CAD Drawing Tools", self)
        left_tb.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left_tb)

        left_tools = [
            ("1. Polyline Boundary", "DRAW_SLAB_EDGE"),
            ("2. Place Column", "ADD_COL"),
            ("3A. + Hidden Beam", "ADD_HID_BEAM"),
            ("3B. + Drop Beam", "ADD_DROP_BEAM"),
            ("4A. Pick: Slab", "PICK_SLAB"),
            ("4B. Pick: Flip Rib", "PICK_FLIP_RIB"),
            ("4C. Pick: Opening", "PICK_OPENING"),
            ("---", None),
            ("Rotate Col 90° (R)", "ROTATE_COL"),
            ("Auto-Fill All Slabs", "AUTO_FILL_SLABS"),
            ("---", None),
            ("Select", "SELECT"),
            ("Delete Selected (Del)", "DELETE_SELECTED"),
            ("Move Col / Beam", "MOVE"),
            ("Pan (Hand)", "PAN"),
            ("Zoom Extents", "ZOOM_EXTENTS"),
            ("Demo Layout", "LOAD_TEMPLATE"),
        ]

        for label, tid in left_tools:
            if tid is None:
                left_tb.addSeparator()
            else:
                btn = QPushButton(label)
                if tid == "DELETE_SELECTED":
                    btn.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold; padding: 4px;")
                btn.clicked.connect(lambda checked=False, t=tid: self.activate_cad_tool(t))
                left_tb.addWidget(btn)

    def _build_main_workspace(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)

        # Top Automatic ACI 318 Thickness & Optimization Bar
        thick_frame = QFrame()
        thick_frame.setFrameShape(QFrame.Shape.StyledPanel)
        thick_row = QHBoxLayout(thick_frame)

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

        # Layer Visibility & Freeze Control Bar
        layer_frame = QFrame()
        layer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        layer_frame.setStyleSheet("background-color: #1E293B; border-radius: 4px; padding: 2px;")
        layer_row = QHBoxLayout(layer_frame)
        layer_row.setContentsMargins(8, 2, 8, 2)

        layer_lbl = QLabel("Layer Visibility & Freeze:")
        layer_lbl.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 11px;")
        layer_row.addWidget(layer_lbl)

        self.chk_lay_arch = QCheckBox("Arch DXF Block")
        self.chk_lay_arch.setChecked(True)
        self.chk_lay_arch.toggled.connect(self._on_layer_toggled)
        layer_row.addWidget(self.chk_lay_arch)

        self.chk_lay_cols = QCheckBox("Columns")
        self.chk_lay_cols.setChecked(True)
        self.chk_lay_cols.toggled.connect(self._on_layer_toggled)
        layer_row.addWidget(self.chk_lay_cols)

        self.chk_lay_beams = QCheckBox("Beams")
        self.chk_lay_beams.setChecked(True)
        self.chk_lay_beams.toggled.connect(self._on_layer_toggled)
        layer_row.addWidget(self.chk_lay_beams)

        self.chk_lay_slabs = QCheckBox("Slabs & Ribs")
        self.chk_lay_slabs.setChecked(True)
        self.chk_lay_slabs.toggled.connect(self._on_layer_toggled)
        layer_row.addWidget(self.chk_lay_slabs)

        self.chk_lay_labels = QCheckBox("Labels")
        self.chk_lay_labels.setChecked(True)
        self.chk_lay_labels.toggled.connect(self._on_layer_toggled)
        layer_row.addWidget(self.chk_lay_labels)

        layer_row.addStretch(1)
        vbox.addWidget(layer_frame)

        # Stacked Modes
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

    def get_column_dimensions(self) -> Tuple[float, float]:
        """Returns (b_m, h_m) based on selected toolbar orientation."""
        if hasattr(self, "cb_col_size") and self.cb_col_size.currentIndex() == 1:
            return 0.40, 0.20  # Horizontal
        return 0.20, 0.40  # Vertical (Default minimum)

    def load_master_project(self, master_path: str) -> bool:
        """Loads project from .xpert or .json master file."""
        try:
            self.master_project = load_studio_project_from_master_file(master_path)
            clean_name = self.master_project.get("project_name", "Project")
            self.setWindowTitle(
                f"Xpert Structural Design Studio — {clean_name} — {STUDIO_VERSION} (ACI 318-19)"
            )
            self._populate_story_selector()
            self.switch_workspace_mode(0)
            self.statusBar().showMessage(
                f"Loaded Project: Stractural-{clean_name} from {os.path.basename(master_path)} on 02_Ground_Floor."
            )
            return True
        except Exception as e:
            QMessageBox.critical(self, "Project Load Error", f"Failed to load project from master file:\n{str(e)}")
            return False

    def browse_and_open_project(self) -> None:
        """Browse file dialog to open an existing .xpert master project."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Existing Master Project",
            os.path.abspath("./XpertStudio_Projects"),
            "Xpert Master Project (*-00_Project_Master.xpert *-00_Project_Master.json *.xpert *.json);;All Files (*.*)",
        )
        if file_path:
            self.load_master_project(file_path)

    def open_new_project_dialog(self) -> None:
        dlg = NewProjectSetupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.selected_existing_master_path:
                self.load_master_project(dlg.selected_existing_master_path)
            else:
                cfg = dlg.get_config()
                self.master_project = initialize_studio_project(cfg)
                clean_name = self.master_project.get("project_name", "Project")
                self.setWindowTitle(
                    f"Xpert Structural Design Studio — {clean_name} — {STUDIO_VERSION} (ACI 318-19)"
                )
                self._populate_story_selector()
                self.switch_workspace_mode(0)
                self.statusBar().showMessage(
                    f"Initialized Project: Stractural-{clean_name} on 02_Ground_Floor."
                )

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
            reply = QMessageBox.warning(
                self,
                "Thickness Under ACI 318 Minimum",
                f"Entered slab thickness ({entered:.1f} cm) is less than the calculated minimum "
                f"({req:.1f} cm governed by {eval_res['governing_member']}).\n\n"
                f"Proceed anyway? Long-term deflection checks will be required.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.current_story_data["adopted_slab_thickness_cm"] = entered
        self.save_and_sync_current_story()
        self.statusBar().showMessage(f"Adopted slab thickness {entered:.1f} cm saved.")

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

        if tool_id == "DELETE_SELECTED":
            self.cad_canvas.delete_selected()
            return

        if tool_id == "ROTATE_COL":
            self.rotate_selected_column()
            return

        if tool_id == "AUTO_FILL_SLABS":
            self.auto_fill_all_slabs_action()
            return

        # Strict 4-step sequence enforcement:
        if tool_id in ["ADD_COL", "ADD_HID_BEAM", "ADD_DROP_BEAM", "PICK_SLAB", "PICK_FLIP_RIB", "PICK_OPENING"]:
            edge = self.current_story_data.get("slab_edge_polygon", [])
            if not edge or len(edge) < 3:
                QMessageBox.warning(
                    self,
                    "Step 1 Required — Outer Slab Boundary",
                    "Strict Structural Workflow Requirement:\n\n"
                    "You must define the Outer Slab Boundary [00-XD-EDGE] first before "
                    "placing columns, drawing beams, or picking slabs/openings.\n\n"
                    "Active tool switched to '1. Polyline Boundary'. Click consecutive vertices to draw the perimeter.",
                )
                self.cad_canvas.active_tool = "DRAW_SLAB_EDGE"
                self.cad_canvas.polyline_pts = []
                self.cad_canvas.draw_start_pt = None
                self.statusBar().showMessage("Tool: 1. Draw Outer Polyline Boundary [00-XD-EDGE] (Click Vertex 1)")
                return

        if tool_id == "LOAD_TEMPLATE":
            self.current_story_data["slab_edge_polygon"] = [[0, 0], [10.0, 0], [10.0, 8.5], [0, 8.5]]
            # Ensure every column is 100% inside boundary: x in [0.10, 9.90], y in [0.20, 8.30]
            self.current_story_data["columns"] = [
                {"id": "C1", "x": 0.10, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C2", "x": 5.00, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C3", "x": 9.90, "y": 8.30, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C4", "x": 0.10, "y": 4.25, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C5", "x": 5.00, "y": 4.25, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C6", "x": 9.90, "y": 4.25, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C7", "x": 0.10, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C8", "x": 5.00, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
                {"id": "C9", "x": 9.90, "y": 0.20, "b_m": 0.20, "h_m": 0.40, "active": True},
            ]
            self.current_story_data["beams"] = [
                {
                    "id": "B1", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
                    "start_x": 0.10, "start_y": 8.30, "end_x": 9.90, "end_y": 8.30,
                    "spans": [4.90, 4.90],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.20, "x": 0.10, "y": 8.30},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.20, "x": 5.00, "y": 8.30},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.20, "x": 9.90, "y": 8.30},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 9.80, "val": 28.5}],
                },
                {
                    "id": "B2", "beam_kind": "hidden", "width_m": 0.40, "depth_m": 0.30,
                    "start_x": 0.10, "start_y": 4.25, "end_x": 9.90, "end_y": 4.25,
                    "spans": [4.90, 4.90],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.20, "x": 0.10, "y": 4.25},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.20, "x": 5.00, "y": 4.25},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.20, "x": 9.90, "y": 4.25},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 9.80, "val": 36.2}],
                },
            ]
            self.current_story_data["slabs"] = [
                {"id": "S1", "axis_span_m": 4.05, "left_support_w_m": 0.40, "right_support_w_m": 0.20, "rib_direction_deg": 0.0},
            ]
            self.current_story_data["openings"] = []
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.cad_canvas.zoom_extents()
            self.statusBar().showMessage("Standard 2-Bay Structural Layout loaded successfully.")
            return

        if tool_id != "DRAW_SLAB_EDGE":
            self.cad_canvas.polyline_pts = []

        self.cad_canvas.active_tool = tool_id
        self.cad_canvas.draw_start_pt = None
        self.cad_canvas.move_element = None

        if tool_id == "SELECT":
            self.cad_canvas.setCursor(Qt.CursorShape.ArrowCursor)
        elif tool_id == "PAN":
            self.cad_canvas.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.cad_canvas.setCursor(Qt.CursorShape.CrossCursor)

        self.statusBar().showMessage(f"Active Tool: {tool_id}")

    def _on_layer_toggled(self) -> None:
        self.refresh_story_ui()

    def is_layer_visible(self, name: str) -> bool:
        k = name.lower()
        if "arch" in k:
            return self.chk_lay_arch.isChecked() if hasattr(self, "chk_lay_arch") else True
        if "col" in k:
            return self.chk_lay_cols.isChecked() if hasattr(self, "chk_lay_cols") else True
        if "beam" in k:
            return self.chk_lay_beams.isChecked() if hasattr(self, "chk_lay_beams") else True
        if "slab" in k or "rib" in k:
            return self.chk_lay_slabs.isChecked() if hasattr(self, "chk_lay_slabs") else True
        if "label" in k or "tag" in k:
            return self.chk_lay_labels.isChecked() if hasattr(self, "chk_lay_labels") else True
        return True

    def import_arch_dxf_dialog(self) -> None:
        if not self.master_project or not self.current_story_data:
            QMessageBox.warning(self, "No Active Story", "Please open or create a project first before importing architectural DXF.")
            return
        dxf_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Architectural DXF for Active Story",
            "",
            "AutoCAD DXF (*.dxf);;All Files (*)",
        )
        if not dxf_path:
            return
        try:
            underlay_data = import_arch_dxf_underlay(dxf_path)
            self.current_story_data["arch_underlay_block"] = underlay_data
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.cad_canvas.zoom_extents()
            self.statusBar().showMessage(
                f"Arch DXF '{underlay_data['file_name']}' imported ({len(underlay_data['segments'])} segments, {len(underlay_data['snap_points'])} snap points)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import architectural DXF:\n{e}")

    def rotate_selected_column(self) -> None:
        sel = self.cad_canvas.selected_element
        if not sel or sel.get("type") != "column":
            self.statusBar().showMessage("Please select a column first (using Select tool) to rotate.")
            return
        col_id = sel.get("id")
        rule = self.get_column_boundary_rule()
        ok, msg = rotate_column_90_deg(col_id, self.current_story_data, rule=rule)
        if ok:
            self.save_and_sync_current_story()
            self.refresh_story_ui()
            self.statusBar().showMessage(msg)
        else:
            QMessageBox.warning(self, "Cannot Rotate Column", msg)

    def auto_fill_all_slabs_action(self) -> None:
        if not self.master_project or not self.current_story_data:
            return
        count, msg = auto_fill_all_story_slabs(self.current_story_data)
        self.save_and_sync_current_story()
        self.refresh_story_ui()
        self.statusBar().showMessage(msg)

    def get_column_boundary_rule(self) -> str:
        if hasattr(self, "cb_col_rule") and self.cb_col_rule.currentIndex() == 1:
            return "expand"
        return "clamp"

    def _on_toggle_osnap(self, checked: bool) -> None:
        self.cad_canvas.toggle_osnap(checked)

    def _on_toggle_ortho(self, checked: bool) -> None:
        self.cad_canvas.toggle_ortho(checked)

    def save_and_sync_current_story(self) -> None:
        if not self.master_project or self.current_story_index >= len(self.master_project.get("stories", [])):
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

        # Populate Beams Table
        beams = self.current_story_data.get("beams", [])
        self.tbl_beams.setRowCount(len(beams))
        for r_i, bm in enumerate(beams):
            bid = bm["id"]
            res = self.last_analysis_bundle["beam_results"].get(bid, {})
            self.tbl_beams.setItem(r_i, 0, QTableWidgetItem(bid))
            self.tbl_beams.setItem(r_i, 1, QTableWidgetItem(bm.get("beam_kind", "hidden").upper()))
            self.tbl_beams.setItem(r_i, 2, QTableWidgetItem(f"{bm.get('width_m', 0.3):.2f} x {bm.get('depth_m', 0.3):.2f}"))
            self.tbl_beams.setItem(r_i, 3, QTableWidgetItem(", ".join(str(s) for s in bm.get("spans", []))))
            self.tbl_beams.setItem(r_i, 4, QTableWidgetItem(f"{res.get('max_pos_mu_knm', 0.0):.2f}"))
            self.tbl_beams.setItem(r_i, 5, QTableWidgetItem(f"{res.get('max_neg_face_mu_knm', 0.0):.2f}"))
            self.tbl_beams.setItem(r_i, 6, QTableWidgetItem(f"{res.get('max_face_vu_kn', 0.0):.2f}"))

        # Populate Columns Table
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

        # Populate Calculation Report
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
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xpert.structural.design.studio.v1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Check command-line arguments for master file (.xpert or .json)
    master_file_arg = None
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            continue
        if arg.endswith((".xpert", ".json")) and os.path.isfile(arg):
            master_file_arg = os.path.abspath(arg)
            break

    if "--check" in sys.argv:
        win = XpertStudioMainWindow()
        cfg = {
            "project_name": "CheckProject",
            "root_directory": os.path.abspath("./test_output"),
            "ground_floor_height_m": 3.20,
            "include_basement": False,
            "floors_above_ground": 1,
            "upper_floor_height_m": 3.00,
            "upper_floors_mode": "typical",
            "include_penthouse": False,
            "foundation_depth_m": 1.50,
            "fc_mpa": 20.0,
            "fy_mpa": 350.0,
            "soil_bearing_qall_kn_m2": 150.0,
        }
        win.master_project = initialize_studio_project(cfg)
        win._populate_story_selector()
        win.activate_cad_tool("LOAD_TEMPLATE")
        win.run_analyze_all_beams()
        win.activate_cad_tool("ZOOM_EXTENTS")
        win.cad_canvas.toggle_osnap(True)
        win.cad_canvas.toggle_ortho(True)
        win.cad_canvas.render_story(win.current_story_data)
        print("HEADLESS_STUDIO_CHECK_OK")
        sys.exit(0)

    win = XpertStudioMainWindow()

    if master_file_arg:
        # Case 1: Opened directly via master project file argument (.xpert)
        ok = win.load_master_project(master_file_arg)
        if not ok:
            sys.exit(1)
        win.show()
    else:
        # Case 2: Opened directly or via shortcut -> Modal NewProjectSetupDialog opens first
        dlg = NewProjectSetupDialog(win)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.selected_existing_master_path:
                ok = win.load_master_project(dlg.selected_existing_master_path)
                if not ok:
                    sys.exit(1)
            else:
                cfg = dlg.get_config()
                win.master_project = initialize_studio_project(cfg)
                clean_name = win.master_project.get("project_name", "Project")
                win.setWindowTitle(
                    f"Xpert Structural Design Studio — {clean_name} — {STUDIO_VERSION} (ACI 318-19)"
                )
                win._populate_story_selector()
                win.switch_workspace_mode(0)
            win.show()
        else:
            sys.exit(0)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
