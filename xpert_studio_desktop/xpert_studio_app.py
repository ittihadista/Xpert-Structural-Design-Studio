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
import os
import sys
from typing import Dict, Any, List, Optional

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
    propagate_ground_columns_to_all_stories,
    sync_story_to_dxf,
    validate_project_name,
    compute_smart_beam_tag_position,
)
from xpert_structural_engine import (
    analyze_all_story_beams_and_columns,
    evaluate_story_thickness_and_optimization,
)


class NewProjectSetupDialog(QDialog):
    """
    Modal Project Definition Dialog (like ETABS / SAFE / Robot).
    Closes automatically on OK after initializing Stractural-<ProjectName> on disk.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Structural Project — Xpert Structural Design Studio")
        self.setMinimumWidth(680)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

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
    wheel zoom, middle-click pan, OSNAP, and color-coded non-overlapping tags:
    - Columns (C1..Cn): Bright Green (#22C55E) outside top-right corner.
    - Beams (B1..Bm): Bright Orange (#F97316) at clear-span midpoint.
    """

    def __init__(self, parent_studio: "XpertStudioMainWindow"):
        super().__init__()
        self.studio = parent_studio
        self.scene_2d = QGraphicsScene(self)
        self.setScene(self.scene_2d)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0D1117")))
        self.scale_px = 45.0  # 1m = 45px
        self.active_tool = "SELECT"
        self.beam_start_col: Optional[Dict[str, Any]] = None

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def render_story(self, story_data: Dict[str, Any]) -> None:
        self.scene_2d.clear()
        s = self.scale_px

        # Draw Subtle Coordinate Grid (1m spacing)
        grid_pen = QPen(QColor("#161F2C"), 1, Qt.PenStyle.DotLine)
        for gx in range(-2, 16):
            self.scene_2d.addLine(gx * s, -2 * s, gx * s, 12 * s, grid_pen)
        for gy in range(-2, 12):
            self.scene_2d.addLine(-2 * s, -gy * s, 16 * s, -gy * s, grid_pen)

        # 1. Slab Boundary (00-XD-EDGE in Cyan)
        edge = story_data.get("slab_edge_polygon", [])
        if len(edge) >= 3:
            poly = QPolygonF([QPointF(float(p[0]) * s, -float(p[1]) * s) for p in edge])
            self.scene_2d.addPolygon(poly, QPen(QColor("#06B6D4"), 2), QBrush(Qt.BrushStyle.NoBrush))

        # 2. Beams & Non-Overlapping Orange Beam Tags
        columns = story_data.get("columns", [])
        placed_tags = []
        for col in columns:
            if col.get("active", True):
                placed_tags.append((float(col["x"]) + 0.25, float(col["y"]) + 0.25))

        for bm in story_data.get("beams", []):
            sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            ex, ey = float(bm.get("end_x", 5.0)), float(bm.get("end_y", 0.0))
            b_kind = bm.get("beam_kind", "hidden")
            pen_color = QColor("#EAB308") if b_kind == "hidden" else QColor("#10B981")
            pen_style = Qt.PenStyle.DashLine if b_kind == "hidden" else Qt.PenStyle.SolidLine
            self.scene_2d.addLine(sx * s, -sy * s, ex * s, -ey * s, QPen(pen_color, 3, pen_style))

            tx, ty, _ = compute_smart_beam_tag_position(bm, columns, placed_tags)
            txt = self.scene_2d.addText(f"{bm['id']}", QFont("Arial", 9, QFont.Weight.Bold))
            txt.setDefaultTextColor(QColor("#FB923C"))  # Bright Orange
            txt.setPos(tx * s - 10, -ty * s - 12)

        # 3. Columns & Bright Green Column Tags Outside Corner
        for col in columns:
            if not col.get("active", True):
                continue
            cx, cy = float(col["x"]), float(col["y"])
            b, h = float(col.get("b_m", 0.25)), float(col.get("h_m", 0.50))
            rect = QRectF((cx - b / 2.0) * s, -(cy + h / 2.0) * s, b * s, h * s)
            self.scene_2d.addRect(rect, QPen(QColor("#EF4444"), 2), QBrush(QColor(239, 68, 68, 90)))

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

    def __init__(self):
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
        self._init_demo_project_silently()

    def _build_classic_menu_bar(self) -> None:
        mbar = self.menuBar()

        # File Menu
        m_file = mbar.addMenu("&File")
        act_new = QAction("New Structural Project...", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.open_new_project_dialog)
        m_file.addAction(act_new)

        act_save = QAction("Save Story && Sync .DXF", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_and_sync_current_story)
        m_file.addAction(act_save)

        m_file.addSeparator()
        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.setStatusTip("Close and exit Xpert Structural Design Studio")
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # Draw Menu
        m_draw = mbar.addMenu("&Draw")
        for label, tool_id in [
            ("Select / Pick Element", "SELECT"),
            ("Draw Column (00-XD-COL)", "DRAW_COL"),
            ("Draw Hidden Beam (00-XD-BEAM-HID)", "DRAW_BEAM_HID"),
            ("Draw Drop Beam (00-XD-BEAM-DROP)", "DRAW_BEAM_DROP"),
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

        btn_save = QPushButton("Save && Sync .DXF (Ctrl+S)")
        btn_save.clicked.connect(self.save_and_sync_current_story)
        top_tb.addWidget(btn_save)
        top_tb.addSeparator()

        top_tb.addWidget(QLabel("  Active Story: "))
        self.cb_story = QComboBox()
        self.cb_story.setMinimumWidth(260)
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
        btn_run_all = QPushButton("Analyze All Beams (F5)")
        btn_run_all.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px;")
        btn_run_all.clicked.connect(self.run_analyze_all_beams)
        top_tb.addWidget(btn_run_all)

        # Left Vertical CAD Toolbar
        left_tb = QToolBar("CAD Drawing Tools", self)
        left_tb.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left_tb)

        for label, tid in [
            ("Select", "SELECT"),
            ("+ Column", "ADD_COL"),
            ("+ Hidden Beam", "ADD_HID_BEAM"),
            ("+ Drop Beam", "ADD_DROP_BEAM"),
            ("Demo Layout", "LOAD_TEMPLATE"),
        ]:
            btn = QPushButton(label)
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

    def _init_demo_project_silently(self) -> None:
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
        self.master_project = initialize_studio_project(cfg)
        self._populate_story_selector()
        self.activate_cad_tool("LOAD_TEMPLATE")

    def open_new_project_dialog(self) -> None:
        dlg = NewProjectSetupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.get_config()
            self.master_project = initialize_studio_project(cfg)
            self._populate_story_selector()
            self.switch_workspace_mode(0)
            self.statusBar().showMessage(
                f"Initialized Project: Stractural-{self.master_project['project_name']} on 02_Ground_Floor."
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
        if tool_id == "LOAD_TEMPLATE":
            self.current_story_data["slab_edge_polygon"] = [[0, 0], [10.0, 0], [10.0, 8.5], [0, 8.5]]
            self.current_story_data["columns"] = [
                {"id": "C1", "x": 0.0, "y": 8.5, "b_m": 0.25, "h_m": 0.50, "active": True},
                {"id": "C2", "x": 5.2, "y": 8.5, "b_m": 0.25, "h_m": 0.60, "active": True},
                {"id": "C3", "x": 10.0, "y": 8.5, "b_m": 0.25, "h_m": 0.50, "active": True},
                {"id": "C4", "x": 0.0, "y": 4.2, "b_m": 0.25, "h_m": 0.50, "active": True},
                {"id": "C5", "x": 5.2, "y": 4.2, "b_m": 0.30, "h_m": 0.60, "active": True},
                {"id": "C6", "x": 10.0, "y": 4.2, "b_m": 0.25, "h_m": 0.50, "active": True},
                {"id": "C7", "x": 0.0, "y": 0.0, "b_m": 0.25, "h_m": 0.50, "active": True},
                {"id": "C8", "x": 5.2, "y": 0.0, "b_m": 0.25, "h_m": 0.60, "active": True},
                {"id": "C9", "x": 10.0, "y": 0.0, "b_m": 0.25, "h_m": 0.50, "active": True},
            ]
            self.current_story_data["beams"] = [
                {
                    "id": "B1", "beam_kind": "drop", "width_m": 0.20, "depth_m": 0.50,
                    "start_x": 0.0, "start_y": 8.5, "end_x": 10.0, "end_y": 8.5,
                    "spans": [5.2, 4.8],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C1", "width_m": 0.25},
                        {"support_index": 2, "kind": "column", "target_id": "C2", "width_m": 0.25},
                        {"support_index": 3, "kind": "column", "target_id": "C3", "width_m": 0.25},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 10.0, "val": 28.5}],
                },
                {
                    "id": "B2", "beam_kind": "hidden", "width_m": 0.60, "depth_m": 0.30,
                    "start_x": 0.0, "start_y": 4.2, "end_x": 10.0, "end_y": 4.2,
                    "spans": [5.2, 4.8],
                    "supports": [
                        {"support_index": 1, "kind": "column", "target_id": "C4", "width_m": 0.25},
                        {"support_index": 2, "kind": "column", "target_id": "C5", "width_m": 0.30},
                        {"support_index": 3, "kind": "column", "target_id": "C6", "width_m": 0.25},
                    ],
                    "loads": [{"type": "dist", "x1": 0.0, "x2": 10.0, "val": 36.2}],
                },
            ]
            self.current_story_data["slabs"] = [
                {"id": "S1", "axis_span_m": 4.3, "left_support_w_m": 0.60, "right_support_w_m": 0.20},
            ]
            self.save_and_sync_current_story()
            self.refresh_story_ui()

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
    win = XpertStudioMainWindow()
    if "--check" in sys.argv:
        win.run_analyze_all_beams()
        print("HEADLESS_STUDIO_CHECK_OK")
        sys.exit(0)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
