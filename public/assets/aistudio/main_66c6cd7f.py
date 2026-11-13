import sys
import json
import os
import copy
import re
import traceback
import io
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QToolBar, QSplitter, QTableWidget, 
                             QTableWidgetItem, QLabel, QInputDialog, QMessageBox,
                             QDialog, QTextEdit, QFileDialog, QPushButton, QSizePolicy, 
                             QHeaderView, QGroupBox, QLineEdit, QFormLayout, QComboBox, QColorDialog, QCheckBox, QScrollArea)
from PyQt6.QtGui import QAction, QKeySequence, QPainter, QGuiApplication, QColor, QFont, QIcon, QPixmap, QPen, QPolygon, QPageSize, QPageLayout
from PyQt6.QtCore import Qt, QStandardPaths, QPoint, QByteArray, QSize, QSettings
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.lines as mlines
from matplotlib.transforms import blended_transform_factory

APP_NAME = "Xpert Beam Analysis"
APP_VERSION = "1.0.0-beta"
APP_TAG = "Beta"

# ==============================================================================
# 1. PROFESSIONAL SVG ICON GENERATOR
# ==============================================================================
def get_professional_icon(icon_type, color="#003366"):
    svgs = {
        "new": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
        "open": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
        "save": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',
        "save_as": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/><path d="M15.5 16.5l3-3 2 2-3 3h-2z"/></svg>',
        "span": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="10" x2="21" y2="10" stroke-width="2.5"/><polygon points="5,10 8,10 6.5,14" fill="{color}" opacity="0.4"/><polygon points="16,10 19,10 17.5,14" fill="{color}" opacity="0.4"/><line x1="5" y1="14" x2="8" y2="14"/><line x1="16" y1="14" x2="19" y2="14"/></svg>',
        "cantilever": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="12" x2="20" y2="12"/><rect x="2" y="8" width="3" height="8" fill="{color}" opacity="0.3"/><line x1="2" y1="8" x2="2" y2="16"/><line x1="5" y1="8" x2="5" y2="16"/><line x1="2" y1="10" x2="5" y2="10"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="2" y1="14" x2="5" y2="14"/></svg>',
        "point_load": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v14"/><path d="M8 14l4 6 4-6"/></svg>',
        "dist_load": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="5" y1="6" x2="5" y2="14"/><path d="M3 14l2-2 2 2"/><line x1="9" y1="6" x2="9" y2="14"/><path d="M7 14l2-2 2 2"/><line x1="13" y1="6" x2="13" y2="14"/><path d="M11 14l2-2 2 2"/><line x1="17" y1="6" x2="17" y2="14"/><path d="M15 14l2-2 2 2"/></svg>',
        "properties": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="12" height="16" fill="{color}" opacity="0.2"/><rect x="6" y="4" width="12" height="16"/><line x1="3" y1="4" x2="3" y2="20"/><line x1="21" y1="4" x2="21" y2="20"/><line x1="3" y1="4" x2="6" y2="4"/><line x1="3" y1="20" x2="6" y2="20"/><line x1="18" y1="4" x2="21" y2="4"/><line x1="18" y1="20" x2="21" y2="20"/></svg>',
        "clear": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#d9534f" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>',
        "report": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        "print": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>',
        "undo": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#555555" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>'
    }
    svg_str = svgs.get(icon_type, svgs["span"])
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(svg_str.encode('utf-8')), "SVG")
    if pixmap.isNull():
        return QIcon()
    return QIcon(pixmap.scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

def create_structural_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(0, 51, 102))
    painter.setPen(QPen(QColor(255, 255, 255), 2))
    painter.drawRoundedRect(4, 4, 56, 56, 10, 10)
    painter.setPen(QPen(QColor(255, 255, 255), 4))
    painter.drawLine(10, 32, 54, 32)
    painter.setBrush(QColor(255, 165, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(QPolygon([QPoint(18, 44), QPoint(26, 32), QPoint(10, 32)]))
    painter.drawPolygon(QPolygon([QPoint(46, 44), QPoint(54, 32), QPoint(38, 32)]))
    painter.end()
    return QIcon(pixmap)

# ------------------------------------------------------------------------------
# Distributed-load color palette: MUTED EARTH TONES (olive / brown / slate /
# taupe / forest).  Deliberately avoids the SFD blue (#1f77b4), the BMD red
# (#d62728), the uplift orange (#f39c12) and the legacy dark-green (#1b5e20),
# and the 8 shades are distinct enough to remain separable in B&W printing.
LOAD_PALETTE = [
    "#556b2f",  # 1 dark olive green
    "#795548",  # 2 earthy brown (taupe)
    "#5f6a72",  # 3 slate / lead grey
    "#8b5e34",  # 4 sienna / trap brown
    "#3b5323",  # 5 dark forest green
    "#6e6e6e",  # 6 medium charcoal grey
    "#a0785a",  # 7 light tan / sand
    "#4f5b4a",  # 8 grey-green
]

def compute_net_load_profile(loads, total_length):
    """Sweep-line: split the beam at every distributed-load breakpoint and, for
    each contiguous interval, return the algebraic NET intensity plus the ordered
    list of contributing (w, color) segments (signed).  Net column height == the
    exact value the analysis engine integrates, so drawing matches computation."""
    dist = [l for l in loads if l['type'] == 'dist']
    if not dist or total_length <= 0:
        return []
    pts = {0.0, float(total_length)}
    for l in dist:
        x1 = max(0.0, min(float(l['x1']), total_length))
        x2 = max(0.0, min(float(l['x2']), total_length))
        if x2 > x1:
            pts.add(x1); pts.add(x2)
    pts = sorted(pts)
    intervals = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if b - a < 1e-9:
            continue
        mid = 0.5 * (a + b)
        contribs, net = [], 0.0
        for k, l in enumerate(dist):
            x1 = max(0.0, min(float(l['x1']), total_length))
            x2 = max(0.0, min(float(l['x2']), total_length))
            if x1 - 1e-9 <= mid <= x2 + 1e-9:
                w = float(l['val'])
                contribs.append((w, LOAD_PALETTE[k % len(LOAD_PALETTE)]))
                net += w
        intervals.append({'x0': a, 'x1': b, 'net': net, 'contribs': contribs})
    return intervals

def center_on_primary_screen(widget):
    """Move any QDialog to the geometric center of the primary screen.
    Called at the end of each dialog __init__ (after setGeometry, so width()/
    height() are already the final sizes)."""
    try:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        w, h = int(widget.width()), int(widget.height())
        if w <= 0 or h <= 0:
            hint = widget.sizeHint()
            w, h = max(1, int(hint.width())), max(1, int(hint.height()))
        x = geo.x() + (geo.width() - w) // 2
        y = geo.y() + (geo.height() - h) // 2
        widget.move(max(geo.x(), x), max(geo.y(), y))
    except Exception:
        pass

# ==============================================================================
# 2. DIALOGS
# ==============================================================================
class DisplaySettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - Display & Graphics Preferences")
        self.setGeometry(200, 200, 620, 460)
        self.settings = copy.deepcopy(current_settings)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        def create_style_row(target):
            h_layout = QHBoxLayout()
            btn = QPushButton("Choose Color...")
            color = QColor(self.settings.get(f'{target}_color', "#1f77b4"))
            setattr(self, f'{target}_color_btn', btn)
            setattr(self, f'{target}_color', color)
            self.update_btn_color(btn, color)
            btn.clicked.connect(lambda: self.pick_color(target))
            hatch_cb = QCheckBox("Enable Hatch")
            hatch_cb.setChecked(self.settings.get(f'{target}_hatch_enabled', True))
            setattr(self, f'{target}_hatch_cb', hatch_cb)
            hatch_combo = QComboBox()
            hatch_combo.addItems([
                "Coarse (0.30 m)",
                "Medium (0.15 m)",
                "Fine (0.075 m)",
                "Extra Fine (0.04 m)"
            ])
            hatch_combo.setCurrentText(self.settings.get(f'{target}_hatch_style', "Medium (0.15 m)"))
            setattr(self, f'{target}_hatch_combo', hatch_combo)
            h_layout.addWidget(btn); h_layout.addWidget(hatch_cb); h_layout.addWidget(hatch_combo)
            return h_layout

        form_layout.addRow(QLabel("Shear Force Diagram (SFD):"), create_style_row('sfd'))
        form_layout.addRow(QLabel("Bending Moment Diagram (BMD):"), create_style_row('bmd'))
        load_layout = QHBoxLayout()
        self.load_color_btn = QPushButton("Choose Color...")
        self.load_color = QColor(self.settings.get('pos_load_color', "#1b5e20"))
        self.update_btn_color(self.load_color_btn, self.load_color)
        self.load_color_btn.clicked.connect(lambda: self.pick_color('load'))
        self.load_hatch_cb = QCheckBox("Enable Fill/Hatch")
        self.load_hatch_cb.setChecked(self.settings.get('pos_load_hatch_enabled', True))
        self.load_hatch_combo = QComboBox()
        self.load_hatch_combo.addItems([
            "None (solid fill)",
            "Vertical ( | )",
            "Horizontal ( - )",
            "Plus ( + )",
            "Cross ( x )",
            "Dots ( . )",
            "Circles ( o )"
        ])
        _pat_to_text = {None: "None (solid fill)", '|': "Vertical ( | )", '-': "Horizontal ( - )",
                        '+': "Plus ( + )", 'x': "Cross ( x )", '.': "Dots ( . )", 'o': "Circles ( o )"}
        self.load_hatch_combo.setCurrentText(_pat_to_text.get(self.settings.get('load_hatch_pattern', '|'), "Vertical ( | )"))
        load_layout.addWidget(self.load_color_btn); load_layout.addWidget(self.load_hatch_cb); load_layout.addWidget(self.load_hatch_combo)
        form_layout.addRow(QLabel("Loads Style / Hatch:"), load_layout)
        layout.addLayout(form_layout); layout.addSpacing(15)
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("↺ Reset to Defaults")
        btn_reset.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; padding: 6px;")
        btn_reset.clicked.connect(self.reset_to_defaults)
        btn_save = QPushButton("Apply & Save")
        btn_save.setStyleSheet("background-color: #003366; color: white; font-weight: bold; padding: 6px;")
        btn_save.clicked.connect(self.accept_settings)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_reset); btn_layout.addStretch(); btn_layout.addWidget(btn_save); btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        center_on_primary_screen(self)

    def reset_to_defaults(self):
        self.sfd_color = QColor("#1f77b4"); self.update_btn_color(self.sfd_color_btn, self.sfd_color)
        self.sfd_hatch_cb.setChecked(True); self.sfd_hatch_combo.setCurrentText("Medium (0.15 m)")
        self.bmd_color = QColor("#d62728"); self.update_btn_color(self.bmd_color_btn, self.bmd_color)
        self.bmd_hatch_cb.setChecked(True); self.bmd_hatch_combo.setCurrentText("Medium (0.15 m)")
        self.load_color = QColor("#1b5e20"); self.update_btn_color(self.load_color_btn, self.load_color)
        self.load_hatch_cb.setChecked(True); self.load_hatch_combo.setCurrentText("Vertical ( | )")

    def pick_color(self, target):
        color = QColorDialog.getColor(getattr(self, f'{target}_color'), self, "Select Color")
        if color.isValid():
            setattr(self, f'{target}_color', color)
            self.update_btn_color(getattr(self, f'{target}_color_btn'), color)

    def update_btn_color(self, btn, color):
        hex_c = color.name()
        text_c = "#ffffff" if color.lightness() < 130 else "#000000"
        btn.setStyleSheet(f"background-color: {hex_c}; color: {text_c}; font-weight: bold; padding: 5px;")

    def accept_settings(self):
        hatch_map = {
            "Coarse (0.30 m)": 0.30,
            "Medium (0.15 m)": 0.15,
            "Fine (0.075 m)": 0.075,
            "Extra Fine (0.04 m)": 0.04
        }
        pat_map = {
            "None (solid fill)": None,
            "Vertical ( | )": '|',
            "Horizontal ( - )": '-',
            "Plus ( + )": '+',
            "Cross ( x )": 'x',
            "Dots ( . )": '.',
            "Circles ( o )": 'o'
        }
        self.settings['sfd_color'] = self.sfd_color.name()
        self.settings['sfd_hatch_enabled'] = self.sfd_hatch_cb.isChecked()
        self.settings['sfd_hatch_spacing'] = hatch_map.get(self.sfd_hatch_combo.currentText(), 0.15)
        self.settings['sfd_hatch_style'] = self.sfd_hatch_combo.currentText()
        self.settings['bmd_color'] = self.bmd_color.name()
        self.settings['bmd_hatch_enabled'] = self.bmd_hatch_cb.isChecked()
        self.settings['bmd_hatch_spacing'] = hatch_map.get(self.bmd_hatch_combo.currentText(), 0.15)
        self.settings['bmd_hatch_style'] = self.bmd_hatch_combo.currentText()
        self.settings['pos_load_color'] = self.load_color.name()
        self.settings['pos_load_hatch_enabled'] = self.load_hatch_cb.isChecked()
        self.settings['load_hatch_pattern'] = pat_map.get(self.load_hatch_combo.currentText(), '|')
        self.accept()

    def get_settings(self): return self.settings


class PropertiesDialog(QDialog):
    def __init__(self, current_properties, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - Section Properties")
        self.setGeometry(200, 200, 450, 400)
        self.properties = copy.deepcopy(current_properties)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.b_input = QLineEdit(str(self.properties.get('B', 0.2)))
        self.b_input.setPlaceholderText("Width (m)")
        self.b_input.textChanged.connect(self.update_calculated)
        form_layout.addRow(QLabel("B (Width, m):"), self.b_input)
        
        self.h_input = QLineEdit(str(self.properties.get('H', 0.4)))
        self.h_input.setPlaceholderText("Height (m)")
        self.b_input.textChanged.connect(self.update_calculated)
        form_layout.addRow(QLabel("H (Height, m):"), self.h_input)
        
        self.fc_input = QLineEdit(str(self.properties.get('fc', 20)))
        self.fc_input.setPlaceholderText("MPa")
        self.fc_input.textChanged.connect(self.update_calculated)
        form_layout.addRow(QLabel("fc' (Concrete Strength, MPa):"), self.fc_input)
        
        self.fy_input = QLineEdit(str(self.properties.get('fy', 350)))
        self.fy_input.setPlaceholderText("MPa")
        form_layout.addRow(QLabel("Fy (Yield Strength, MPa):"), self.fy_input)
        
        layout.addLayout(form_layout)
        layout.addSpacing(10)
        
        calc_group = QGroupBox("Calculated Properties:")
        calc_group.setStyleSheet("QGroupBox { font-weight: bold; color: #003366; }")
        calc_layout = QFormLayout(calc_group)
        
        self.e_input = QLineEdit()
        self.e_input.setReadOnly(True)
        self.e_input.setStyleSheet("background-color: #eef6ff; font-weight: bold;")
        calc_layout.addRow(QLabel("E (Modulus, MPa):"), self.e_input)
        
        self.i_input = QLineEdit()
        self.i_input.setReadOnly(True)
        self.i_input.setStyleSheet("background-color: #eef6ff; font-weight: bold;")
        calc_layout.addRow(QLabel("I (Moment of Inertia, m⁴):"), self.i_input)
        
        self.a_input = QLineEdit()
        self.a_input.setReadOnly(True)
        self.a_input.setStyleSheet("background-color: #eef6ff; font-weight: bold;")
        calc_layout.addRow(QLabel("A (Area, m²):"), self.a_input)
        
        layout.addWidget(calc_group)
        
        note_label = QLabel("Note: E is calculated using ACI formula: E = 4700 × √(fc')")
        note_label.setStyleSheet("font-size: 10px; color: #555555; font-style: italic;")
        layout.addWidget(note_label)
        
        layout.addSpacing(10)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save Properties")
        btn_save.setStyleSheet("background-color: #003366; color: white; font-weight: bold; padding: 6px;")
        btn_save.clicked.connect(self.accept_properties)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.update_calculated()
        center_on_primary_screen(self)
    
    def update_calculated(self):
        try:
            B = abs(float(self.b_input.text())) if self.b_input.text() else 0.2
            H = abs(float(self.h_input.text())) if self.h_input.text() else 0.4
            fc = abs(float(self.fc_input.text())) if self.fc_input.text() else 20
            if B <= 0 or H <= 0 or fc <= 0:
                return
            E = 4700 * np.sqrt(fc)
            I = B * (H ** 3) / 12.0
            A = B * H
            
            self.e_input.setText(f"{E:.2f}")
            self.i_input.setText(f"{I:.6f}")
            self.a_input.setText(f"{A:.4f}")
        except ValueError:
            pass
    
    def accept_properties(self):
        try:
            B = abs(float(self.b_input.text()))
            H = abs(float(self.h_input.text()))
            fc = abs(float(self.fc_input.text()))
            fy = abs(float(self.fy_input.text()))
            if B <= 0 or H <= 0 or fc <= 0 or fy <= 0:
                raise ValueError
            self.properties['B'] = B
            self.properties['H'] = H
            self.properties['fc'] = fc
            self.properties['fy'] = fy
            self.properties['E'] = 4700 * np.sqrt(fc)
            self.properties['I'] = B * (H ** 3) / 12.0
            self.properties['A'] = B * H
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid positive numeric values.")
    
    def get_properties(self):
        return self.properties


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME} ({APP_TAG})")
        self.setGeometry(200, 200, 560, 520)
        layout = QVBoxLayout(self)
        title_lbl = QLabel(f"{APP_NAME} ({APP_TAG})")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #003366;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        subtitle_lbl = QLabel("Continuous Beam Structural Analysis Engine")
        subtitle_lbl.setStyleSheet("font-size: 12px; color: #555555; font-style: italic;")
        subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_lbl)
        layout.addSpacing(10)
        # NOTE: all Arabic sentences below are preserved EXACTLY as authored.
        # Only independent English identity lines were added (Full/Short/Developer).
        desc_text = (
                    "<b>عن التطبيق (About):</b><br>"
                    "تطبيق هندسي متكامل ومخصص لتحليل الكمرات المستمرة (Continuous Beams) باستخدام طريقة Slope Deflection.<br>"
                    "يهدف التطبيق إلى تقديم تجربة تعليمية وهندسية تفاعلية تتيح للمهندس والطالب استعراض خطوات الحل اليدوي وقيم القص والعزوم.<br><br>"
                    "<b>Full Name:</b> Xpert Beam Analysis<br>"
                    "<b>Short Name:</b> XB Analysis<br><br>"
                    "<b>Version:</b> 1.0.0-beta (Pre-release)<br><br>"
                    "<b>الترخيص (License):</b><br>"
                    "<span style='color: green; font-weight: bold;'>التطبيق مجاني بالكامل 100% للاستخدام الهندسي والتعليمي.</span><br><br>"
                    "<b>إعداد:</b> المهندس يوسف محمد كشلاف<br>"
                    "<b>Developed by:</b> YOUSEF MOHAMMED KESHLAF<br><br>"
                    "<b>بيانات التواصل (Contact Info):</b><br>"
                    "للتواصل معنا لإبداء الملاحظات والمقترحات لتطوير التطبيق:<br>"
                    "📍 <b>Adress:</b> Tripoli - Libya<br>"
                    "✉️ <b>E-Mail:</b> Alittihad_EC@outlook.com<br>"
                    "📞 <b>Tel:</b> 00218920959914<br>"
                    "💬 <b>What's App:</b> 00218920959914<br>"
                    "🌐 <b>Facebook:</b> -"
                )
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setHtml(desc_text)
        text_widget.setStyleSheet("background-color: #fcfcfc; border: 1px solid #dddddd; padding: 8px; font-size: 12px;")
        layout.addWidget(text_widget)
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: #003366; color: white; font-weight: bold; padding: 6px; width: 100px;")
        btn_close.clicked.connect(self.accept)
        btn_layout = QHBoxLayout(); btn_layout.addStretch(); btn_layout.addWidget(btn_close); btn_layout.addStretch()
        layout.addLayout(btn_layout)
        center_on_primary_screen(self)


class DetailedCalculationReportDialog(QDialog):
    def __init__(self, report_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - Academic Slope-Deflection Calculation Report")
        self.setGeometry(100, 80, 850, 750)
        layout = QVBoxLayout(self)
        title_label = QLabel("📘 Step-by-Step Structural Analysis & Slope-Deflection Method Solution Report:")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #003366;")
        layout.addWidget(title_label)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(report_text)
        self.text_edit.setStyleSheet("font-family: 'Consolas', 'Courier New', Monospace; font-size: 12px; background-color: #fdfdfd; line-height: 1.5;")
        layout.addWidget(self.text_edit)
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy Report"); btn_copy.clicked.connect(lambda: self.copy_save('copy'))
        btn_save = QPushButton("💾 Save as Text File..."); btn_save.clicked.connect(lambda: self.copy_save('save'))
        btn_close = QPushButton("Close"); btn_close.setStyleSheet("background-color: #003366; color: white; font-weight: bold; padding: 6px;"); btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_copy); btn_layout.addWidget(btn_save); btn_layout.addStretch(); btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        center_on_primary_screen(self)

    def copy_save(self, action):
        if action == 'copy':
            QApplication.clipboard().setText(self.text_edit.toPlainText())
            QMessageBox.information(self, "Copied", "Calculation report copied to clipboard successfully.")
        else:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save Calculation Report", "Calculation_Report.txt", "Text Files (*.txt)")
            if file_name:
                try:
                    with open(file_name, 'w', encoding='utf-8') as f: f.write(self.text_edit.toPlainText())
                    QMessageBox.information(self, "Saved", f"Report saved successfully to:\n{file_name}")
                except Exception as e: QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")


class SettingsDialog(QDialog):
    def __init__(self, current_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - Settings & Preferences")
        self.setGeometry(200, 200, 500, 180)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.dir_input = QLineEdit(current_dir); self.dir_input.setReadOnly(True)
        btn_browse = QPushButton("Browse..."); btn_browse.clicked.connect(self.browse_directory)
        dir_layout = QHBoxLayout(); dir_layout.addWidget(self.dir_input); dir_layout.addWidget(btn_browse)
        form_layout.addRow(QLabel("Default Save Directory:"), dir_layout)
        layout.addLayout(form_layout)
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save Settings"); btn_save.setStyleSheet("background-color: #003366; color: white; font-weight: bold; padding: 6px;"); btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(); btn_layout.addWidget(btn_save); btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        center_on_primary_screen(self)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Default Save Directory", self.dir_input.text())
        if dir_path: self.dir_input.setText(dir_path)
    def get_selected_directory(self): return self.dir_input.text()


class PrintOptionsDialog(QDialog):
    """Pre-print options dialog: Black & White toggle + page orientation.
    The B&W choice is applied at render time (grayscale conversion of the
    exported image) WITHOUT touching the on-screen colored drawing."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - Print Options")
        self.setGeometry(200, 200, 460, 250)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.chk_bw = QCheckBox("Print in Black & White (no color ink)")
        self.chk_bw.setChecked(bool(getattr(parent, '_bw_print', False)))
        form.addRow(self.chk_bw)
        self.cmb_orient = QComboBox()
        self.cmb_orient.addItems([
            "Landscape (wide - recommended for beam plots)",
            "Portrait"
        ])
        if getattr(parent, '_print_orientation', 'landscape') == 'portrait':
            self.cmb_orient.setCurrentIndex(1)
        form.addRow(QLabel("Page orientation:"), self.cmb_orient)
        layout.addLayout(form)
        layout.addSpacing(8)
        note = QLabel("Tip: Landscape fits the full beam + SFD + BMD width on a single page.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 10px; color: #555555; font-style: italic;")
        layout.addWidget(note)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Open Print Preview / Print")
        btn_ok.setStyleSheet("background-color: #003366; color: white; font-weight: bold; padding: 6px;")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(); btn_layout.addWidget(btn_ok); btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        center_on_primary_screen(self)

    def is_black_white(self):
        return self.chk_bw.isChecked()

    def orientation(self):
        return 'portrait' if self.cmb_orient.currentIndex() == 1 else 'landscape'

# ==============================================================================
# 3. MATPLOTLIB CANVAS
# ==============================================================================
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=10, height=8, dpi=120):
        fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#ffffff')
        self.axes_beam = fig.add_subplot(311)
        self.axes_shear = fig.add_subplot(312, sharex=self.axes_beam)
        self.axes_moment = fig.add_subplot(313, sharex=self.axes_beam)
        super().__init__(fig)
        self.analysis_results = {'solved': False}
        self.spans, self.loads = [], []
        self.cantilevers = {'left': 0.0, 'right': 0.0}
        self.parent_window = parent
        self.display_settings = {
            'sfd_color': "#1f77b4", 'sfd_hatch_enabled': True, 'sfd_hatch_spacing': 0.15, 'sfd_hatch_style': "Medium (0.15 m)",
            'bmd_color': "#d62728", 'bmd_hatch_enabled': True, 'bmd_hatch_spacing': 0.15, 'bmd_hatch_style': "Medium (0.15 m)",
            'pos_load_color': "#1b5e20", 'pos_load_hatch_enabled': True, 'load_hatch_pattern': '|'
        }
        self.hover_callback = None
        self.mpl_connect('motion_notify_event', self.on_mouse_move)

    def draw_custom_hatch(self, ax, x_data, y_data, color, spacing):
        if len(x_data) < 2 or spacing <= 0:
            return
        x_min, x_max = min(x_data), max(x_data)
        n_lines = int((x_max - x_min) / spacing) if spacing > 0 else 0
        if n_lines > 500:
            spacing = (x_max - x_min) / 500
        current_x = x_min
        while current_x <= x_max:
            y_val = np.interp(current_x, x_data, y_data)
            if abs(y_val) < 1e-6:   # skip near-zero samples (unloaded members)
                current_x += spacing
                continue
            y_start, y_end = 0.0, y_val
            ax.vlines(current_x, min(y_start, y_end), max(y_start, y_end), 
                      color=color, linewidth=0.8, alpha=0.5)
            current_x += spacing

    def draw_results(self, spans, loads, cantilevers, analysis_results):
        self.spans, self.loads, self.cantilevers, self.analysis_results = spans, loads, cantilevers, analysis_results
        fig = self.figure; fig.clf()
        self.axes_beam = fig.add_subplot(311)
        self.axes_shear = fig.add_subplot(312, sharex=self.axes_beam)
        self.axes_moment = fig.add_subplot(313, sharex=self.axes_beam)
        fig.tight_layout(pad=4.2)
        for ax in [self.axes_beam, self.axes_shear, self.axes_moment]: ax.grid(False)

        if not spans and not cantilevers['left'] and not cantilevers['right']:
            self.axes_beam.set_title("Add spans and loads to start live analysis", fontsize=11, color='gray')
            for ax in [self.axes_beam, self.axes_shear, self.axes_moment]: ax.axis('off')
            self.draw(); return

        c_left, c_right = float(cantilevers['left']), float(cantilevers['right'])
        total_length = c_left + sum(spans) + c_right
        support_x = [c_left]
        for L in spans: support_x.append(support_x[-1] + float(L))

        self.axes_beam.plot([0, total_length], [0, 0], color='black', lw=4)
        if spans:
            self.axes_beam.plot(support_x, np.zeros_like(support_x), '^', color='#003366', ms=12)

        if c_left > 0:
            self.axes_beam.text(c_left / 2.0, -0.38, f'LC = {c_left}m', ha='center', va='center', fontsize=10, fontweight='bold', color='#333333', bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.85))
        curr_pos = c_left
        for i in range(len(spans)):
            self.axes_beam.text(curr_pos + spans[i] / 2.0, -0.38, f'L{i+1} = {spans[i]}m', ha='center', va='center', fontsize=10, fontweight='bold', color='#333333', bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.85))
            curr_pos += spans[i]
        if c_right > 0:
            self.axes_beam.text(support_x[-1] + c_right / 2.0, -0.38, f'RC = {c_right}m', ha='center', va='center', fontsize=10, fontweight='bold', color='#333333', bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.85))

        pos_load_hex = self.display_settings.get('pos_load_color', "#1b5e20")
        pos_load_hatch = self.display_settings.get('pos_load_hatch_enabled', True)
        _load_hatch_pat = self.display_settings.get('load_hatch_pattern', '|')

        # ---- merged net distributed-load profile (signed, value-scaled) ----
        profile = compute_net_load_profile(loads, total_length)
        _net_max_pos = 0.0; _net_max_neg = 0.0
        for iv in profile:
            if iv['net'] > _net_max_pos: _net_max_pos = iv['net']
            if iv['net'] < _net_max_neg: _net_max_neg = iv['net']
        _max_abs = max(_net_max_pos, -_net_max_neg, 1e-9)
        _h_per_unit = (0.60 / _max_abs) if profile else 1.0   # slimmer net bars ~0.60

        # ---- point loads: tag + VALUE on the beam, with edge-aware alignment ----
        # The arrow stays vertical (text x == load x); only horizontal anchor
        # flips near the ends so the full "Pn = v kN" string never gets clipped.
        _pt_n = 0
        _edge_margin = max(0.12 * total_length, 0.4)
        for load in loads:
            if load['type'] == 'point':
                _pt_n += 1
                x, val = float(load['x']), float(load['val'])
                over_dist = any(float(d['x1']) - 1e-9 <= x <= float(d['x2']) + 1e-9
                                for d in loads if d['type'] == 'dist')
                text_y_offset = 1.05 if over_dist else 0.75
                color = pos_load_hex if val >= 0 else '#f39c12'
                edge = '#0d3b13' if val >= 0 else '#d35400'
                if x <= _edge_margin:
                    ha_pt = 'left'
                elif x >= total_length - _edge_margin:
                    ha_pt = 'right'
                else:
                    ha_pt = 'center'
                self.axes_beam.annotate(f'P{_pt_n} = {val} kN', xy=(x, 0.05),
                                        xytext=(x, text_y_offset if val >= 0 else -1.15),
                                        arrowprops=dict(facecolor=color, edgecolor=edge,
                                                        shrink=0.03, width=2.2, headwidth=8),
                                        ha=ha_pt, fontsize=10, color=color, fontweight='bold')

        # ---- distributed loads: cumulative SIGNED stacked segments ----
        # Segment height proportional to its value; total column = algebraic NET.
        for iv in profile:
            a, b, net, contribs = iv['x0'], iv['x1'], iv['net'], iv['contribs']
            if not contribs:
                continue
            span = b - a
            xs_arr = [(a + b) / 2.0] if span < 0.12 else \
                     np.linspace(a + 0.05, b - 0.05, max(3, int(span * 2)))
            acc = 0.0
            for (w, col) in contribs:
                lo = acc; acc += w; hi = acc
                y_lo = lo * _h_per_unit; y_hi = hi * _h_per_unit
                if pos_load_hatch and _load_hatch_pat:
                    self.axes_beam.fill_between([a, b], y_lo, y_hi, color=col, alpha=0.30,
                                                hatch=_load_hatch_pat, edgecolor=col, linewidth=0)
                else:
                    self.axes_beam.fill_between([a, b], y_lo, y_hi, color=col, alpha=0.30)
                self.axes_beam.plot([a, b], [y_hi, y_hi], color=col, lw=1.6)
                self.axes_beam.plot([a, b], [y_lo, y_lo], color=col, lw=0.8, alpha=0.5)
                seg_col = col if w >= 0 else '#f39c12'
                if w >= 0:   # downward arrows: head at lower edge (toward beam)
                    for x_a in xs_arr:
                        self.axes_beam.annotate('', xy=(x_a, y_lo + 0.02), xytext=(x_a, y_hi),
                                                arrowprops=dict(arrowstyle="->", color=seg_col, lw=1.2))
                else:        # upward arrows: head at upper edge
                    for x_a in xs_arr:
                        self.axes_beam.annotate('', xy=(x_a, y_hi - 0.02), xytext=(x_a, y_lo),
                                                arrowprops=dict(arrowstyle="->", color=seg_col, lw=1.2))
            net_y = net * _h_per_unit
            # single contributor -> label takes that segment's own color (no clash);
            # superposition -> gold, so overlapping zones are instantly obvious.
            lab_col = contribs[0][1] if len(contribs) == 1 else "#b8860b"
            self.axes_beam.text((a + b) / 2.0, net_y + (0.10 if net >= 0 else -0.10),
                                f'w = {net:.1f} kN/m', ha='center',
                                va='bottom' if net >= 0 else 'top', fontsize=9.5,
                                color=lab_col, fontweight='bold',
                                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.9))

        reactions = analysis_results.get('reactions', {})
        if spans and analysis_results.get('solved', False):
            for i, x in enumerate(support_x):
                r_val = float(reactions.get(i+1, 0.0))
                color = 'darkgreen' if r_val >= 0 else 'darkred'
                self.axes_beam.text(x, -0.85, f'R{i+1} = {r_val:.2f} kN', ha='center', va='center', color=color, fontsize=10, fontweight='bold', bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.9))
                if r_val >= 0:
                    self.axes_beam.annotate('', xy=(x, -0.22), xytext=(x, -0.70), arrowprops=dict(facecolor=color, edgecolor=color, shrink=0.0, width=2.2, headwidth=7.5))
                else:
                    self.axes_beam.annotate('', xy=(x, -0.70), xytext=(x, -0.22), arrowprops=dict(facecolor=color, edgecolor=color, shrink=0.0, width=2.2, headwidth=7.5))

        beam_name = os.path.splitext(os.path.basename(self.parent_window.current_file_path))[0] if self.parent_window and getattr(self.parent_window, 'current_file_path', None) else "B1"
        self.axes_beam.text(0.0, 1.08, f"Analysis of {beam_name}", transform=self.axes_beam.transAxes, ha='left', va='bottom', fontsize=14, fontweight='bold', color='#003366')
        _top = max(1.45, _net_max_pos * _h_per_unit + 0.55)
        _bot = min(-1.35, _net_max_neg * _h_per_unit - 0.45)
        self.axes_beam.set_xlim(0, total_length); self.axes_beam.set_ylim(_bot, _top); self.axes_beam.axis('off')

        if not analysis_results.get('solved', False):
            self.axes_shear.text(0.0, 1.12, 'Shear Force Diagram - SFD (kN)', transform=self.axes_shear.transAxes, fontsize=9.0, fontweight='bold')
            self.axes_moment.text(0.0, 1.15, 'Bending Moment Diagram - BMD (kN.m)', transform=self.axes_moment.transAxes, fontsize=9.0, fontweight='bold')
            self.axes_shear.axis('off'); self.axes_moment.axis('off')
            self.draw(); return

        for ax in [self.axes_shear, self.axes_moment]:
            for spine in ax.spines.values(): spine.set_visible(False)
            ax.set_xlim(0, total_length)

        drop_x_coords = set(support_x)
        for load in loads:
            if load['type'] == 'point': drop_x_coords.add(float(load['x']))
            elif load['type'] == 'dist': drop_x_coords.add(float(load['x1'])); drop_x_coords.add(float(load['x2']))
            
        x_shear_full = np.array(analysis_results.get('x_shear_full', []))
        v_shear_full = np.array(analysis_results.get('v_shear_full', []))
        x_moment_full = np.array(analysis_results.get('x_moment_full', []))
        m_moment_full = np.array(analysis_results.get('m_moment_full', []))

        # zero-shear = location of MAX POSITIVE moment in each span (dM/dx = V).
        zero_shear_x_list = []
        if len(x_moment_full) > 1 and len(spans) > 0:
            for s_i in range(len(spans)):
                s_st, s_en = support_x[s_i], support_x[s_i + 1]
                mask = (x_moment_full >= s_st - 1e-9) & (x_moment_full <= s_en + 1e-9)
                if np.any(mask):
                    x_span = x_moment_full[mask]
                    m_span = m_moment_full[mask]
                    max_idx = int(np.argmax(m_span))
                    if m_span[max_idx] > 1e-2:
                        zc = float(x_span[max_idx])
                        if not any(abs(zc - sx) < 0.05 for sx in support_x):
                            zero_shear_x_list.append(zc)
            uniq = []
            for z in sorted(zero_shear_x_list):
                if not uniq or abs(z - uniq[-1]) > 0.02:
                    uniq.append(z)
            zero_shear_x_list = uniq
            for z in zero_shear_x_list:
                drop_x_coords.add(z)

        sorted_drop_x = sorted(list(drop_x_coords))

        def _cat(xv):
            if any(abs(xv - sx) < 1e-4 for sx in support_x): return 'support'
            if any(abs(xv - zz) < 1e-4 for zz in zero_shear_x_list): return 'zero'
            return 'other'
        cat_map = {round(xv, 6): _cat(xv) for xv in sorted_drop_x}

        fig.canvas.draw()
        box_beam = self.axes_beam.get_position()
        box_moment = self.axes_moment.get_position()
        y_top_fig = box_beam.y1
        y_axis_bottom_fig = box_moment.y0
        mh = box_moment.height
        Y_TEXT_HIGH = -0.08
        Y_TEXT_LOW  = -0.20
        CONNECT_END = -0.03

        for xv in sorted_drop_x:
            pt_fig = self.axes_beam.transData.transform((xv, 0))
            x_fig = fig.transFigure.inverted().transform(pt_fig)[0]
            y_end_fig = y_axis_bottom_fig + CONNECT_END * mh
            line = mlines.Line2D([x_fig, x_fig], [y_end_fig, y_top_fig],
                                 transform=fig.transFigure, color='#9a9a9a',
                                 linestyle=':', alpha=0.75, lw=1.0)
            fig.add_artist(line)

        sfd_hex = self.display_settings.get('sfd_color', "#1f77b4")
        bmd_hex = self.display_settings.get('bmd_color', "#d62728")
        sfd_hatch_enabled = self.display_settings.get('sfd_hatch_enabled', True)
        bmd_hatch_enabled = self.display_settings.get('bmd_hatch_enabled', True)
        sfd_hatch_spacing = self.display_settings.get('sfd_hatch_spacing', 0.15)
        bmd_hatch_spacing = self.display_settings.get('bmd_hatch_spacing', 0.15)

        if len(x_shear_full) > 0:
            self.axes_shear.plot(x_shear_full, v_shear_full, color=sfd_hex, lw=2.0)
            self.axes_shear.fill_between(x_shear_full, 0, v_shear_full, color=sfd_hex, alpha=0.2)
            if sfd_hatch_enabled:
                self.draw_custom_hatch(self.axes_shear, x_shear_full, v_shear_full, sfd_hex, sfd_hatch_spacing)
            self.axes_shear.vlines([x_shear_full[0], x_shear_full[-1]], 0, [v_shear_full[0], v_shear_full[-1]], color=sfd_hex, lw=2.0)
            for x_p in sorted_drop_x:
                if cat_map[round(x_p, 6)] == 'zero': continue
                idx_left = int(np.argmin(np.abs(x_shear_full - (x_p - 1e-3))))
                idx_right = int(np.argmin(np.abs(x_shear_full - (x_p + 1e-3))))
                v_left, v_right = v_shear_full[idx_left], v_shear_full[idx_right]
                if abs(v_left) > 0.1:
                    self.axes_shear.annotate(f'{v_left:.1f}', (x_p, v_left), textcoords="offset points", xytext=(-4, 4 if v_left>=0 else -11),
                                             ha='right', fontsize=9.0, fontweight='bold', color=sfd_hex, bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.85))
                if abs(v_right) > 0.1 and abs(v_right - v_left) > 0.5:
                    self.axes_shear.annotate(f'{v_right:.1f}', (x_p, v_right), textcoords="offset points", xytext=(4, 4 if v_right>=0 else -11),
                                             ha='left', fontsize=9.0, fontweight='bold', color=sfd_hex, bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.85))

        self.axes_shear.axhline(0, color='black', lw=1.2)
        self.axes_shear.text(0.0, 1.12, 'Shear Force Diagram - SFD (kN)', transform=self.axes_shear.transAxes, fontsize=9.0, fontweight='bold')
        self.axes_shear.yaxis.set_visible(False); self.axes_shear.tick_params(labelbottom=False, bottom=False)

        if len(x_moment_full) > 0:
            plot_m = [-m for m in m_moment_full]
            self.axes_moment.plot(x_moment_full, plot_m, color=bmd_hex, lw=2.0)
            self.axes_moment.fill_between(x_moment_full, 0, plot_m, color=bmd_hex, alpha=0.2)
            if bmd_hatch_enabled:
                self.draw_custom_hatch(self.axes_moment, x_moment_full, plot_m, bmd_hex, bmd_hatch_spacing)
            self.axes_moment.vlines([x_moment_full[0], x_moment_full[-1]], 0, [plot_m[0], plot_m[-1]], color=bmd_hex, lw=2.0)
            
            for i, x_supp in enumerate(support_x):
                idx = int(np.argmin(np.abs(x_moment_full - x_supp)))
                m_val = m_moment_full[idx]
                plot_y = plot_m[idx]
                offset_y = 5 if plot_y >= 0 else -12
                self.axes_moment.annotate(f'{m_val:.2f}', (x_supp, plot_y), textcoords="offset points", xytext=(0, offset_y),
                                          ha='center', fontsize=9.0, fontweight='bold', color=bmd_hex, bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.9))

            for s_i in range(len(spans)):
                s_st, s_en = support_x[s_i], support_x[s_i + 1]
                mask = (x_moment_full >= s_st) & (x_moment_full <= s_en)
                if np.any(mask):
                    x_span, m_span = x_moment_full[mask], m_moment_full[mask]
                    max_idx = np.argmax(m_span)
                    max_m, peak_x = m_span[max_idx], x_span[max_idx]
                    if max_m > 1e-2:
                        plot_y_peak = -max_m
                        self.axes_moment.annotate(f'{max_m:.2f}', (peak_x, plot_y_peak), textcoords="offset points", xytext=(0, -12),
                                                  ha='center', fontsize=9.0, fontweight='bold', color=bmd_hex,
                                                  bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.9))

            y_min_cur, y_max_cur = self.axes_moment.get_ylim()
            span_y = max(abs(y_max_cur - y_min_cur), 1.0)
            self.axes_moment.set_ylim(min(y_min_cur, 0.0) - 0.22 * span_y, max(y_max_cur, 0.0) + 0.18 * span_y)

        self.axes_moment.axhline(0, color='black', lw=1.2)
        self.axes_moment.text(0.0, 1.15, 'Bending Moment Diagram - BMD (kN.m)', transform=self.axes_moment.transAxes, fontsize=9.0, fontweight='bold')
        self.axes_moment.yaxis.set_visible(False)

        self.axes_moment.tick_params(labelbottom=False, bottom=False)
        trans_blend = blended_transform_factory(self.axes_moment.transData, self.axes_moment.transAxes)
        COL_SUP, COL_ZS, COL_OTH = "#003366", "#e67e22", "#666666"

        for xv in sorted_drop_x:
            cat = cat_map[round(xv, 6)]
            if cat == 'support':
                col, ytxt = COL_SUP, Y_TEXT_LOW
                tick_top, tick_bot = Y_TEXT_HIGH - 0.02, Y_TEXT_LOW + 0.02
            elif cat == 'zero':
                col, ytxt = COL_ZS, Y_TEXT_HIGH
                tick_top, tick_bot = 0.0, Y_TEXT_HIGH + 0.02
            else:
                col, ytxt = COL_OTH, Y_TEXT_HIGH
                tick_top, tick_bot = 0.0, Y_TEXT_HIGH + 0.02
            self.axes_moment.plot([xv, xv], [tick_top, tick_bot], transform=trans_blend,
                                  color=col, lw=1.1, clip_on=False)
            self.axes_moment.text(xv, ytxt, f'{xv:.2f}', transform=trans_blend,
                                  ha='center', va='top', fontsize=8.2, fontweight='bold',
                                  color=col, clip_on=False)

        self.draw()

    def on_mouse_move(self, event):
        if not self.analysis_results.get('solved', False) or self.hover_callback is None or event.inaxes not in [self.axes_beam, self.axes_shear, self.axes_moment]:
            if self.hover_callback: self.hover_callback(None, None, None)
            return
        x_pos = event.xdata
        if x_pos is None: 
            if self.hover_callback: self.hover_callback(None, None, None)
            return
        x_shear_full = np.array(self.analysis_results.get('x_shear_full', []))
        if len(x_shear_full) == 0: 
            if self.hover_callback: self.hover_callback(None, None, None)
            return
        total_length = self.cantilevers['left'] + sum(self.spans) + self.cantilevers['right']
        if x_pos < 0 or x_pos > total_length: 
            if self.hover_callback: self.hover_callback(None, None, None)
            return
        idx = int(np.argmin(np.abs(x_shear_full - x_pos)))
        self.hover_callback(x_shear_full[idx], self.analysis_results.get('v_shear_full', [])[idx], self.analysis_results.get('m_moment_full', [])[idx])

# ==============================================================================
# 4. MAIN APPLICATION UI
# ==============================================================================
class StructuralAppUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} ({APP_TAG})")
        self._app_icon = create_structural_icon()
        self.setWindowIcon(self._app_icon)
        QApplication.setWindowIcon(self._app_icon)
        
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry() if QGuiApplication.primaryScreen() else None
        if screen_geometry: self.setGeometry(screen_geometry)
        else: self.setGeometry(50, 50, 1250, 800)

        self.spans, self.loads = [], []
        self.cantilevers = {'left': 0.0, 'right': 0.0}
        self.analysis_results = {
            'solved': False, 'reactions': {},
            'x_shear_full': [], 'v_shear_full': [],
            'x_moment_full': [], 'm_moment_full': [], 'Mus': []
        }
        self.current_file_path = None
        # ---- persistent settings (survive app close AND PC reboot) ----
        self._qsettings = QSettings("KeshlafSoft", "XBAnalysis")
        _saved_dir = self._qsettings.value("default_save_dir", "", type=str)
        if _saved_dir and os.path.isdir(_saved_dir):
            self.default_save_dir = _saved_dir
        else:
            self.default_save_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self._bw_print = self._qsettings.value("print_bw", False, type=bool)
        self._print_orientation = self._qsettings.value("print_orient", "landscape", type=str)
        self.row_mapping, self.history = [], []
        
        self.section_properties = {
            'B': 0.2, 'H': 0.4, 'fc': 20, 'fy': 350,
            'E': 4700 * np.sqrt(20), 'I': 0.2 * (0.4 ** 3) / 12.0, 'A': 0.2 * 0.4
        }
        
        self.create_menus_and_toolbar()

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)
        left_widget = QWidget(); left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Project Data Table (Editable):"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Type", "Position / Length", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 120); self.table.setColumnWidth(1, 130)
        self.table.itemChanged.connect(self.on_table_item_changed)

        btn_delete = QPushButton("🗑️ Delete Selected Item")
        btn_delete.setStyleSheet("background-color: #f8f9fa; border: 1px solid #cccccc; border-radius: 4px; padding: 6px; font-weight: bold; color: #333333; font-size: 11px;")
        btn_delete.clicked.connect(self.delete_selected_item)

        # ---- Distributed-loads legend panel (colored key only; point loads live in the table) ----
        self.loads_group = QGroupBox("Distributed Loads Legend:")
        self.loads_group.setStyleSheet("QGroupBox { font-weight: bold; color: #003366; }")
        _lg_outer = QVBoxLayout(self.loads_group)
        _lg_outer.setContentsMargins(6, 6, 6, 6)
        self.lbl_loads_summary = QLabel("—")
        self.lbl_loads_summary.setWordWrap(True)
        self.lbl_loads_summary.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.lbl_loads_summary.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_loads_summary.setStyleSheet(
            "background-color: #f8f9fa; border: 1px solid #cccccc; border-radius: 4px;"
            "padding: 6px; font-size: 10pt; color: #002244;")
        _lg_scroll = QScrollArea()
        _lg_scroll.setWidgetResizable(True)
        _lg_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        _lg_scroll.setWidget(self.lbl_loads_summary)
        _lg_outer.addWidget(_lg_scroll)

        # ---- vertical splitter: table (big) + legend (small), both scrollable & resizable ----
        table_splitter = QSplitter(Qt.Orientation.Vertical)
        table_splitter.addWidget(self.table)
        table_splitter.addWidget(self.loads_group)
        table_splitter.setStretchFactor(0, 3)
        table_splitter.setStretchFactor(1, 1)
        table_splitter.setSizes([430, 130])
        table_splitter.setCollapsible(0, False)
        table_splitter.setCollapsible(1, True)

        left_layout.addWidget(table_splitter, 1)
        left_layout.addWidget(btn_delete)

        group_box = QGroupBox("Live Section Readout (Mouse Position):")
        group_box.setStyleSheet("QGroupBox { font-weight: bold; color: #003366; }")
        box_layout = QHBoxLayout(group_box)
        self.lbl_val_x = QLabel("X: - m"); self.lbl_val_f = QLabel("F: - kN"); self.lbl_val_m = QLabel("M: - kNm")
        for lbl in [self.lbl_val_x, self.lbl_val_f, self.lbl_val_m]:
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background-color: #f8f9fa; border: 1px solid #cccccc; border-radius: 4px; padding: 7px; font-weight: bold; font-size: 11pt; color: #002244;")
            box_layout.addWidget(lbl)
        left_layout.addWidget(group_box)
        left_layout.addWidget(QLabel("Tip: Drag the divider between table & legend to resize; double-click cells to edit."))

        main_splitter.addWidget(left_widget)
        self.canvas = MplCanvas(self, width=9, height=7, dpi=120)
        self.canvas.hover_callback = self.update_live_readout
        main_splitter.addWidget(self.canvas)
        main_splitter.setStretchFactor(0, 0); main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([370, 930])
        
        self.update_cantilever_button_state()
        self.update_ui()
        self.showMaximized()

    def persist_save_dir(self):
        """Write the current default save directory to permanent storage so it
        survives application close AND computer reboot."""
        try:
            self._qsettings.setValue("default_save_dir", self.default_save_dir)
            self._qsettings.sync()
        except Exception:
            pass

    def persist_print_prefs(self):
        try:
            self._qsettings.setValue("print_bw", bool(self._bw_print))
            self._qsettings.setValue("print_orient", self._print_orientation)
            self._qsettings.sync()
        except Exception:
            pass

    def update_title(self):
        if self.current_file_path:
            name = os.path.basename(self.current_file_path)
            self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - {name}")
        else:
            self.setWindowTitle(f"{APP_NAME} ({APP_TAG}) - New Project")
    def update_live_readout(self, x, f, m):
        if x is None:
            self.lbl_val_x.setText("X: - m"); self.lbl_val_f.setText("F: - kN"); self.lbl_val_m.setText("M: - kNm")
        else:
            self.lbl_val_x.setText(f"X: {x:.2f} m"); self.lbl_val_f.setText(f"F: {f:.2f} kN"); self.lbl_val_m.setText(f"M: {m:.2f} kNm")

    def save_history(self):
        self.history.append({'spans': copy.deepcopy(self.spans), 'cantilevers': copy.deepcopy(self.cantilevers), 'loads': copy.deepcopy(self.loads)})
        if len(self.history) > 30: self.history.pop(0)

    def undo_action(self):
        if not self.history:
            QMessageBox.information(self, "Undo", "No previous actions to undo."); return
        last_state = self.history.pop()
        self.spans, self.cantilevers, self.loads = last_state['spans'], last_state['cantilevers'], last_state['loads']
        self.run_vba_analysis_engine(); self.update_cantilever_button_state(); self.update_ui()

    def create_menus_and_toolbar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        for text, shortcut, func in [("New", "Ctrl+N", self.file_new), ("Open...", "Ctrl+O", self.file_open), ("Save", "Ctrl+S", self.file_save), ("Save As...", "", self.file_save_as), ("Print / Export PDF...", "Ctrl+P", self.file_print), ("Exit", "", self.close)]:
            action = QAction(text, self)
            if shortcut: action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(func)
            file_menu.addAction(action)
        
        edit_menu = menubar.addMenu("&Edit")
        undo_action = QAction("Undo", self); undo_action.setShortcut(QKeySequence("Ctrl+Z")); undo_action.triggered.connect(self.undo_action)
        edit_menu.addAction(undo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Add Span", self, triggered=self.add_span_dialog))
        edit_menu.addAction(QAction("Add Cantilever", self, triggered=self.add_cantilever_dialog))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Section Properties...", self, triggered=self.open_properties_dialog))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Add Point Load", self, triggered=self.add_point_load_dialog))
        edit_menu.addAction(QAction("Add Distributed Load", self, triggered=self.add_dist_load_dialog))
        
        options_menu = menubar.addMenu("&Options")
        options_menu.addAction(QAction("Display & Graphics Settings...", self, triggered=self.open_display_settings_dialog))
        options_menu.addSeparator()
        options_menu.addAction(QAction("Preferences...", self, triggered=self.open_settings_dialog))
        menubar.addMenu("&About").addAction(QAction(f"About {APP_NAME} ({APP_TAG})...", self, triggered=self.open_about_dialog))

        toolbar = QToolBar("Main Toolbar"); self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(24, 24))
        font = QFont("Segoe UI", 10, QFont.Weight.Normal)
        
        def add_tool_action(icon_name, text, color, func):
            action = QAction(get_professional_icon(icon_name, color), f" {text}", self)
            action.setFont(font)
            action.setToolTip(text)
            action.setStatusTip(text)
            action.triggered.connect(func)
            toolbar.addAction(action)
            return action

        add_tool_action("new", "New", "#003366", self.file_new)
        add_tool_action("open", "Open", "#003366", self.file_open)
        add_tool_action("save", "Save", "#003366", self.file_save)
        add_tool_action("save_as", "Save As", "#003366", self.file_save_as)
        toolbar.addSeparator()
        self.btn_add_span = add_tool_action("span", "Add Span", "#003366", self.add_span_dialog)
        self.btn_add_cantilever = add_tool_action("cantilever", "Add Cantilever", "#003366", self.add_cantilever_dialog)
        toolbar.addSeparator()
        add_tool_action("properties", "Properties", "#003366", self.open_properties_dialog)
        toolbar.addSeparator()
        add_tool_action("point_load", "Point Load", "#d62728", self.add_point_load_dialog)
        add_tool_action("dist_load", "Distributed Load", "#1f77b4", self.add_dist_load_dialog)
        toolbar.addSeparator()
        add_tool_action("undo", "Undo", "#555555", self.undo_action)
        add_tool_action("clear", "Clear All", "#d9534f", self.clear_all)
        toolbar.addSeparator()
        add_tool_action("report", "Calculation Report", "#003366", self.show_detailed_calculation_report)
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        add_tool_action("print", "Print / PDF", "#003366", self.file_print)

    def open_properties_dialog(self):
        dialog = PropertiesDialog(self.section_properties, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.section_properties = dialog.get_properties()
            QMessageBox.information(self, "Properties Saved", 
                f"Section properties updated:\n"
                f"B = {self.section_properties['B']:.3f} m\n"
                f"H = {self.section_properties['H']:.3f} m\n"
                f"fc' = {self.section_properties['fc']:.1f} MPa\n"
                f"Fy = {self.section_properties['fy']:.0f} MPa\n"
                f"E = {self.section_properties['E']:.0f} MPa\n"
                f"I = {self.section_properties['I']:.6f} m⁴\n"
                f"A = {self.section_properties['A']:.4f} m²")

    def open_display_settings_dialog(self):
        dialog = DisplaySettingsDialog(self.canvas.display_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.canvas.display_settings = dialog.get_settings()
            self.canvas.draw_results(self.spans, self.loads, self.cantilevers, self.analysis_results)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.default_save_dir, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.default_save_dir = dialog.get_selected_directory()
            self.persist_save_dir()
            QMessageBox.information(self, "Settings Saved", f"Default save directory updated and saved permanently to:\n{self.default_save_dir}")

    def open_about_dialog(self): AboutDialog(self).exec()

    def file_new(self):
        if QMessageBox.question(self, "New Project", "Create a new project? Unsaved changes will be cleared.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.save_history(); self.clear_all(); self.current_file_path = None
            self.update_title()

    def update_cantilever_button_state(self):
        if not hasattr(self, 'btn_add_cantilever') or self.btn_add_cantilever is None:
            return
        is_full = self.cantilevers['left'] > 0 and self.cantilevers['right'] > 0
        self.btn_add_cantilever.setEnabled(not is_full)
        self.btn_add_cantilever.setToolTip("Both left and right cantilevers are already added." if is_full else "Add Cantilever")

    def add_cantilever_dialog(self):
        if not self.spans:
            QMessageBox.warning(self, "Warning", "Please add at least one main span before adding cantilevers."); return
        sides = []
        if self.cantilevers['left'] == 0: sides.append("Left")
        if self.cantilevers['right'] == 0: sides.append("Right")
        if not sides:
            QMessageBox.warning(self, "Warning", "Both cantilevers are already defined."); return
        side, ok1 = QInputDialog.getItem(self, "Add Cantilever", "Select side:", sides, 0, False)
        if ok1 and side:
            length, ok2 = QInputDialog.getDouble(self, "Add Cantilever", f"Enter {side} cantilever length (m): [Must be > 0]", 2.0, 0.01, 20.0, 2)
            if ok2 and length > 0:
                self.save_history()
                self.cantilevers['left' if side == "Left" else 'right'] = abs(length)
                self.update_cantilever_button_state(); self.update_ui(); self.run_vba_analysis_engine()
            elif ok2:
                QMessageBox.warning(self, "Invalid Length", "Cantilever length must be greater than zero.")

    def delete_selected_item(self):
        curr_row = self.table.currentRow()
        if curr_row < 0 or curr_row >= len(self.row_mapping):
            QMessageBox.warning(self, "Warning", "Please select an item row from the table to delete."); return
        item_info = self.row_mapping[curr_row]
        if item_info['type'] == 'read_only_total':
            QMessageBox.information(self, "Info", "Total Beam Length row is calculated automatically and cannot be deleted."); return
        self.save_history()
        if item_info['type'] == 'left_cantilever': self.cantilevers['left'] = 0.0
        elif item_info['type'] == 'right_cantilever': self.cantilevers['right'] = 0.0
        elif item_info['type'] == 'span' and len(self.spans) > item_info['index']: self.spans.pop(item_info['index'])
        elif item_info['type'] == 'load' and len(self.loads) > item_info['index']: self.loads.pop(item_info['index'])
        self.validate_loads_bounds(); self.update_cantilever_button_state(); self.run_vba_analysis_engine(); self.update_ui()

    def validate_loads_bounds(self):
        total_len = float(self.cantilevers['left']) + sum(self.spans) + float(self.cantilevers['right'])
        if total_len <= 0:
            self.loads.clear()
            return
        valid_loads = []
        for load in self.loads:
            if load['type'] == 'point':
                load['x'] = abs(float(load['x']))
                if load['x'] > total_len: load['x'] = total_len
                valid_loads.append(load)
            elif load['type'] == 'dist':
                load['x1'] = abs(float(load['x1']))
                load['x2'] = abs(float(load['x2']))
                if load['x1'] > total_len: load['x1'] = total_len
                if load['x2'] > total_len: load['x2'] = total_len
                if load['x2'] < load['x1']:
                    load['x1'], load['x2'] = load['x2'], load['x1']
                if load['x2'] > load['x1']:
                    valid_loads.append(load)
        self.loads = valid_loads

    def on_table_item_changed(self, item):
        row, col = item.row(), item.column()
        if row < 0 or row >= len(self.row_mapping) or self.row_mapping[row]['type'] == 'read_only_total': return
        text_val = item.text().strip()
        try:
            info = self.row_mapping[row]
            match = re.search(r'[-+]?\d*\.?\d+', text_val)
            if not match: raise ValueError("No numeric value found")
            raw = float(match.group())
            mag = abs(raw)
            if info['type'] in ['left_cantilever', 'right_cantilever', 'span'] and mag <= 0:
                raise ValueError("Length must be positive")
            if info['type'] == 'left_cantilever' and col == 1: self.cantilevers['left'] = mag
            elif info['type'] == 'right_cantilever' and col == 1: self.cantilevers['right'] = mag
            elif info['type'] == 'span' and col == 1: self.spans[info['index']] = mag
            elif info['type'] == 'load':
                load_ref = self.loads[info['index']]
                if load_ref['type'] == 'point':
                    if col == 1: load_ref['x'] = mag
                    elif col == 2: load_ref['val'] = raw
                elif load_ref['type'] == 'dist':
                    if col == 1:
                        parts = re.findall(r'[-+]?\d*\.?\d+', text_val)
                        if len(parts) >= 2:
                            new_x1, new_x2 = abs(float(parts[0])), abs(float(parts[1]))
                            if new_x2 < new_x1: new_x1, new_x2 = new_x2, new_x1
                            if new_x2 <= new_x1: raise ValueError("End must be greater than start")
                            load_ref['x1'], load_ref['x2'] = new_x1, new_x2
                        else:
                            raise ValueError("Need two numbers: start, end")
                    elif col == 2: load_ref['val'] = raw
            self.validate_loads_bounds(); self.run_vba_analysis_engine(); self.update_ui()
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", f"Could not parse '{text_val}':\n{str(e)}\n\nPlease enter a valid number.")
            self.update_ui()

    def file_open(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Project", self.default_save_dir, "Xpert Files (*.xpt);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.save_history()
                    self.spans = data.get('spans', [])
                    self.cantilevers = data.get('cantilevers', {'left': 0.0, 'right': 0.0})
                    self.loads = data.get('loads', [])
                    if 'section_properties' in data:
                        sp = data['section_properties']
                        sp.setdefault('E', 4700 * np.sqrt(sp.get('fc', 20)))
                        sp.setdefault('I', sp.get('B', 0.2) * (sp.get('H', 0.4) ** 3) / 12.0)
                        sp.setdefault('A', sp.get('B', 0.2) * sp.get('H', 0.4))
                        self.section_properties = sp
                    self.current_file_path = file_name
                    self.default_save_dir = os.path.dirname(file_name)
                    self.persist_save_dir()
                    self.update_cantilever_button_state(); self.run_vba_analysis_engine(); self.update_ui()
                    self.update_title()
                    QMessageBox.information(self, "Success", f"Project loaded successfully from {file_name}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")

    def file_save(self):
        if not self.current_file_path: self.file_save_as()
        else: self.save_to_file(self.current_file_path)

    def file_save_as(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Project As", os.path.join(self.default_save_dir, "project.xpt"), "Xpert Files (*.xpt);;All Files (*)")
        if file_name:
            if not file_name.endswith('.xpt'): file_name += '.xpt'
            self.current_file_path = file_name; self.default_save_dir = os.path.dirname(file_name)
            self.persist_save_dir()
            self.save_to_file(file_name)

    def save_to_file(self, file_name):
        try:
            data = {
                'spans': self.spans, 
                'cantilevers': self.cantilevers, 
                'loads': self.loads,
                'section_properties': self.section_properties
            }
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.update_title()
            QMessageBox.information(self, "Success", f"Project saved successfully to:\n{file_name}")
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")

    # ======================================================================
    # PRINT / EXPORT PDF  (CRASH-FREE, with optional Black & White)
    # ======================================================================
    def file_print(self):
        # 1) Ask print preferences first (B&W + orientation) -> persisted.
        opts = PrintOptionsDialog(self)
        if opts.exec() != QDialog.DialogCode.Accepted:
            return
        self._bw_print = opts.is_black_white()
        self._print_orientation = opts.orientation()
        self.persist_print_prefs()

        # 2) Build a fresh, self-contained printer.
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        except Exception:
            printer = QPrinter()
        try:
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        except Exception:
            pass
        try:
            printer.setPageOrientation(
                QPageLayout.Orientation.Landscape if self._print_orientation == 'landscape'
                else QPageLayout.Orientation.Portrait)
        except Exception:
            pass
        try:
            printer.setColorMode(QPrinter.ColorMode.GrayScale if self._bw_print else QPrinter.ColorMode.Color)
        except Exception:
            pass

        preview_dialog = QPrintPreviewDialog(printer, self)
        preview_dialog.setWindowTitle("Xpert Beam Analysis - Print Preview & Options")
        preview_dialog.resize(1100, 780)
        preview_dialog.paintRequested.connect(self.render_print_page)
        preview_dialog.exec()

    def render_print_page(self, printer):
        try:
            fig = self.canvas.figure
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight',
                        facecolor='white', edgecolor='none')
            buf.seek(0)
            img_bytes = buf.read()
            if not img_bytes:
                return
            # Optional Black & White: grayscale-convert the EXPORTED image only,
            # so the on-screen colored drawing is never modified.
            if getattr(self, '_bw_print', False):
                try:
                    from PIL import Image, ImageOps
                    _tmp = io.BytesIO(img_bytes)
                    _im = Image.open(_tmp).convert('L')          # grayscale
                    _im = ImageOps.autocontrast(_im, cutoff=2)   # boost separation
                    _out = io.BytesIO()
                    _im.save(_out, format='PNG')
                    img_bytes = _out.getvalue()
                except Exception:
                    pass  # graceful fallback to the color image if PIL fails
            pixmap = QPixmap()
            if not pixmap.loadFromData(img_bytes):
                return
            if pixmap.isNull() or pixmap.width() <= 0 or pixmap.height() <= 0:
                return
            painter = QPainter(printer)
            if not painter.isActive():
                return
            page_rect = painter.viewport()
            px, py = int(page_rect.x()), int(page_rect.y())
            pw, ph = int(page_rect.width()), int(page_rect.height())
            if pw <= 0 or ph <= 0:
                painter.end()
                return
            header_height = max(1, int(ph * 0.06))
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            painter.setPen(QColor("#003366"))
            painter.drawText(px, py, pw, header_height,
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                             f"{APP_NAME} ({APP_TAG}) - Structural Analysis Report")
            img_x, img_y = px, py + header_height
            img_w, img_h = pw, ph - header_height
            if img_w <= 0 or img_h <= 0:
                painter.end()
                return
            target = QSize(img_w, img_h)
            size = pixmap.size()
            size.scale(target, Qt.AspectRatioMode.KeepAspectRatio)
            sw = max(1, int(size.width()))
            sh = max(1, int(size.height()))
            off_x = img_x + (img_w - sw) // 2
            painter.setViewport(int(off_x), int(img_y), sw, sh)
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
        except Exception as e:
            try:
                QMessageBox.critical(self, "Print Error",
                                     f"Printing could not be completed:\n{str(e)}")
            except Exception:
                pass

    def extract_span_data(self):
        NS = len(self.spans)
        if NS < 1: return 0, [], np.zeros((1, 1, 1)), np.zeros((1, 1, 1)), 0.0, 0.0, 0.0, 0.0
        c_left, c_right = float(self.cantilevers['left']), float(self.cantilevers['right'])
        L = [0.0] + [float(x) for x in self.spans]
        W1, P1 = np.zeros((NS + 5, 55, 5)), np.zeros((NS + 5, 55, 4))
        span_starts = [c_left]
        for l_val in self.spans: span_starts.append(span_starts[-1] + float(l_val))
        CL_moment = CL_force = CR_moment = CR_force = 0.0

        for load in self.loads:
            if load['type'] == 'dist':
                w_val, d_st, d_en = float(load['val']), float(load['x1']), float(load['x2'])
                if c_left > 0 and d_st < c_left:
                    overlap_st, overlap_en = d_st, min(d_en, c_left)
                    len_c = overlap_en - overlap_st
                    if len_c > 0:
                        f_c = w_val * len_c; arm_c = c_left - (overlap_st + len_c / 2.0)
                        CL_force += f_c; CL_moment += f_c * arm_c
                right_start_x = span_starts[-1]
                if c_right > 0 and d_en > right_start_x:
                    overlap_st, overlap_en = max(d_st, right_start_x), d_en
                    len_c = overlap_en - overlap_st
                    if len_c > 0:
                        f_c = w_val * len_c; arm_c = (overlap_st + len_c / 2.0) - right_start_x
                        CR_force += f_c; CR_moment += f_c * arm_c
                for i in range(1, NS + 1):
                    s_st, s_en = span_starts[i - 1], span_starts[i]
                    overlap_st, overlap_en = max(d_st, s_st), min(d_en, s_en)
                    if overlap_st < overlap_en:
                        for j in range(1, 50):
                            if W1[i, j, 1] == 0:
                                W1[i, j, 1], W1[i, j, 2], W1[i, j, 3] = w_val, overlap_st - s_st, overlap_en - overlap_st
                                break
            elif load['type'] == 'point':
                p_val, p_x = float(load['val']), float(load['x'])
                if c_left > 0 and p_x < c_left: CL_force += p_val; CL_moment += p_val * (c_left - p_x)
                right_start_x = span_starts[-1]
                if c_right > 0 and p_x > right_start_x: CR_force += p_val; CR_moment += p_val * (p_x - right_start_x)
                for i in range(1, NS + 1):
                    s_st, s_en = span_starts[i - 1], span_starts[i]
                    if i == NS:
                        is_inside = (s_st <= p_x <= s_en)
                    else:
                        is_inside = (s_st <= p_x < s_en - 1e-9) or np.isclose(p_x, s_st, atol=1e-6)
                    if is_inside:
                        for j in range(1, 50):
                            if P1[i, j, 1] == 0:
                                P1[i, j, 1], P1[i, j, 2] = p_val, p_x - s_st
                                break
                        break
        return NS, L, W1, P1, CL_moment, CL_force, CR_moment, CR_force

    def show_detailed_calculation_report(self):
        if not self.analysis_results.get('solved', False):
            QMessageBox.warning(self, "Analysis Required", "Please add spans and loads first to solve the beam."); return
        NS, L, W1, P1, CL_m, CL_f, CR_m, CR_f = self.extract_span_data()
        c_left, c_right = float(self.cantilevers['left']), float(self.cantilevers['right'])
        sp = self.section_properties
        lines = [
            "==========================================================================",
            f"          {APP_NAME.upper()} ({APP_TAG.upper()}) - STEP-BY-STEP ACADEMIC REPORT      ",
            "                  CONTINUOUS BEAM ANALYSIS (SLOPE-DEFLECTION METHOD)      ",
            "==========================================================================\n",
            "SECTION 1: THEORETICAL FRAMEWORK",
            "--------------------------------------------------------------------------",
            "1.1 Fundamental Slope-Deflection Equations:",
            "    For any span (ij) with length L, flexural rigidity EI, subject to end",
            "    rotations (theta_i, theta_j) and chord rotation (psi = delta / L):",
            "",
            "    M_ij = FEM_ij + (2 * E * I / L) * [ 2 * theta_i + theta_j - 3 * psi ]",
            "    M_ji = FEM_ji + (2 * E * I / L) * [ 2 * theta_j + theta_i - 3 * psi ]",
            "",
            "    Variable Definitions:",
            "    -------------------",
            "    M_ij   : Internal bending moment at end i of span ij (kN.m)",
            "    M_ji   : Internal bending moment at end j of span ij (kN.m)",
            "    FEM_ij : Fixed-End Moment at end i due to external loads on span (kN.m)",
            "    FEM_ji : Fixed-End Moment at end j due to external loads on span (kN.m)",
            "    E      : Modulus of Elasticity of the beam material (MPa)",
            "    I      : Moment of Inertia of the beam cross-section (m⁴)",
            "    L      : Length of the span between supports i and j (m)",
            "    theta_i: Rotation (slope) at joint i (radians)",
            "    theta_j: Rotation (slope) at joint j (radians)",
            "    psi    : Chord rotation due to support settlement (psi = 0 for unyielding supports)",
            "    K_ij   : Relative flexural stiffness of span ij (K_ij = I / L)",
            "",
            "1.2 Joint Equilibrium Condition:",
            "    At any continuous joint 'j', the algebraic sum of all internal end",
            "    moments meeting at that joint must equal zero: sum(M_j) = M_ji + M_jk = 0\n",
            "1.3 Support Reactions Calculation:",
            "    After determining final end moments, support reactions are calculated",
            "    using static equilibrium equations: R = R_simple + (M_left + M_right) / L\n",
            "==========================================================================",
            "SECTION 2: NUMERICAL COMPUTATIONS",
            "==========================================================================",
            f"2.0 Section & Material Properties:",
            f"    - Width (B) = {sp['B']:.3f} m  |  Height (H) = {sp['H']:.3f} m  |  Area (A) = {sp['A']:.4f} m²",
            f"    - Concrete fc' = {sp['fc']:.1f} MPa  |  Steel Fy = {sp['fy']:.0f} MPa",
            f"    - Elastic Modulus (E) = {sp['E']:.2f} MPa  |  Moment of Inertia (I) = {sp['I']:.6f} m⁴\n",
            f"2.1 Beam Geometry: NS = {NS} | Left Cantilever = {c_left:.2f} m | Right Cantilever = {c_right:.2f} m"
        ]
        for i in range(1, NS + 1):
            lines.append(f"    - Span #{i} Length (L{i}) = {L[i]:.2f} m  |  Relative Stiffness K{i} = {1.0/L[i]:.4f} * EI")
        lines.append(f"\n2.2 Cantilever End Moments: M_LC = {CL_m:.2f} kN.m  |  M_RC = {CR_m:.2f} kN.m")
        lines.append("\n2.3 Fixed-End Moments (FEMs) Calculations:")
        FL, FR = [0.0] * (NS + 2), [0.0] * (NS + 2)
        for i in range(1, NS + 1):
            lines.append(f"    [Span #{i} (L{i} = {L[i]:.2f}m)]:")
            for j in range(1, 50):
                if W1[i, j, 1] != 0:
                    ww = W1[i, j, 1] * W1[i, j, 3]
                    Aa = W1[i, j, 2]
                    Ll = L[i]
                    Cc = W1[i, j, 3]
                    Ss_val = Aa + Cc / 2.0
                    Tt = Ll - Ss_val
                    fl_add = ww * ((Ss_val * (Tt * Tt)) + (Ss_val - 2.0 * Tt) * (Cc * Cc) / 12.0) / (Ll * Ll)
                    fr_add = ww * ((Tt * (Ss_val * Ss_val)) + (Tt - 2.0 * Ss_val) * (Cc * Cc) / 12.0) / (Ll * Ll)
                    FL[i] += fl_add; FR[i] += fr_add
                    lines.append(f"      • Dist Load w={W1[i,j,1]} kN/m -> FEM_Left = {fl_add:.2f} kNm, FEM_Right = {fr_add:.2f} kNm")
            for j in range(1, 50):
                if P1[i, j, 1] != 0:
                    ww = P1[i, j, 1]
                    Aa = P1[i, j, 2]
                    Ll = L[i]
                    Ss_val = Aa
                    Tt = Ll - Ss_val
                    fl_add = ww * (Ss_val * (Tt * Tt)) / (Ll * Ll)
                    fr_add = ww * (Tt * (Ss_val * Ss_val)) / (Ll * Ll)
                    FL[i] += fl_add; FR[i] += fr_add
                    lines.append(f"      • Point Load P={P1[i,j,1]} kN  -> FEM_Left = {fl_add:.2f} kNm, FEM_Right = {fr_add:.2f} kNm")
            lines.append(f"      => Total FEM_L{i} = {FL[i]:.2f} kN.m | Total FEM_R{i} = {FR[i]:.2f} kN.m\n")

        lines.append("2.4 Final Support Bending Moments (After solving equilibrium equations):")
        Mus = self.analysis_results.get('Mus', [])
        for i in range(1, NS + 2):
            lines.append(f"    - Support #{i} Final Moment (M{i}) = {Mus[i]:.2f} kN.m")

        lines.append("\n2.5 Support Vertical Reactions (R):")
        reactions = self.analysis_results.get('reactions', {})
        for i in range(1, NS + 2):
            lines.append(f"    - Support #{i} Total Vertical Reaction (R{i}) = {float(reactions.get(i, 0.0)):.2f} kN")

        lines.append("\n2.6 Maximum Positive Span Moments:")
        x_moment_full = np.array(self.analysis_results.get('x_moment_full', []))
        m_moment_full = np.array(self.analysis_results.get('m_moment_full', []))
        support_x = [c_left]
        for l_val in self.spans: support_x.append(support_x[-1] + float(l_val))
        for s_i in range(NS):
            s_st, s_en = support_x[s_i], support_x[s_i + 1]
            mask = (x_moment_full >= s_st) & (x_moment_full <= s_en)
            if np.any(mask):
                x_span, m_span = x_moment_full[mask], m_moment_full[mask]
                max_idx = np.argmax(m_span)
                lines.append(f"    - Span #{s_i+1} Max Positive Moment = {m_span[max_idx]:.2f} kN.m (at x = {x_span[max_idx] - s_st:.2f} m from support #{s_i+1})")

        lines.append("\n==========================================================================")
        lines.append("                       END OF CALCULATION REPORT                          ")
        lines.append("==========================================================================")
        DetailedCalculationReportDialog("\n".join(lines), self).exec()

    def add_span_dialog(self):
        length, ok = QInputDialog.getDouble(self, "Add Span", "Enter span length (m): [Must be > 0]", 5.0, 0.1, 50.0, 2)
        if ok and length > 0:
            self.save_history(); self.spans.append(abs(length)); self.run_vba_analysis_engine(); self.update_ui()
        elif ok: QMessageBox.warning(self, "Invalid Length", "Span length must be greater than zero.")

    def add_point_load_dialog(self):
        if not self.spans:
            QMessageBox.warning(self, "Warning", "Please add at least one span before adding loads."); return
        total_len = self.cantilevers['left'] + sum(self.spans) + self.cantilevers['right']
        x, ok1 = QInputDialog.getDouble(self, "Point Load", f"Load position from start (0 to {total_len:.2f} m):", total_len/2, 0, total_len, 2)
        if ok1:
            val, ok2 = QInputDialog.getDouble(self, "Point Load", "Load magnitude (kN) [Use negative for upward]:", 50.0, -10000.0, 10000.0, 2)
            if ok2:
                self.save_history(); self.loads.append({'type': 'point', 'x': abs(x), 'val': val}); self.run_vba_analysis_engine(); self.update_ui()

    def add_dist_load_dialog(self):
        if not self.spans:
            QMessageBox.warning(self, "Warning", "Please add at least one span before adding loads."); return
        total_len = self.cantilevers['left'] + sum(self.spans) + self.cantilevers['right']
        x1, ok1 = QInputDialog.getDouble(self, "Distributed Load", "Start position (m):", 0, 0, total_len, 2)
        if ok1:
            x2, ok2 = QInputDialog.getDouble(self, "Distributed Load", "End position (m):", total_len, x1, total_len, 2)
            if ok2:
                if x2 <= x1:
                    QMessageBox.warning(self, "Invalid Range", "End position must be greater than start position."); return
                val, ok3 = QInputDialog.getDouble(self, "Distributed Load", "Load intensity (kN/m) [Use negative for upward]:", 20.0, -5000.0, 5000.0, 2)
                if ok3:
                    self.save_history(); self.loads.append({'type': 'dist', 'x1': abs(x1), 'x2': abs(x2), 'val': val}); self.run_vba_analysis_engine(); self.update_ui()

    def clear_all(self):
        self.save_history()
        self.spans.clear()
        self.cantilevers = {'left': 0.0, 'right': 0.0}
        self.loads.clear()
        self.analysis_results = {
            'solved': False, 'reactions': {},
            'x_shear_full': [], 'v_shear_full': [],
            'x_moment_full': [], 'm_moment_full': [], 'Mus': []
        }
        self.update_cantilever_button_state(); self.update_ui()

    def run_vba_analysis_engine(self):
        NS, L, W1, P1, CL_m, CL_f, CR_m, CR_f = self.extract_span_data()
        if NS < 1:
            self.analysis_results = {
                'solved': False, 'reactions': {},
                'x_shear_full': [], 'v_shear_full': [],
                'x_moment_full': [], 'm_moment_full': [], 'Mus': []
            }
            return
        try:
            II2 = [1.0] * (NS + 10)
            K2 = [0.0] * (NS + 2)
            for i in range(1, NS + 1): K2[i] = II2[i] / L[i]
            D, E = [0.0] * (NS + 3), [0.0] * (NS + 3)
            D[1], E[1] = 4.0 * K2[1], 2.0 * K2[1]
            for i in range(2, NS + 1): D[i], E[i] = 4.0 * (K2[i - 1] + K2[i]), 2.0 * K2[i]
            D[NS + 1], E[NS + 1] = 4.0 * K2[NS], 0.0
            FL, FR = [0.0] * (NS + 2), [0.0] * (NS + 2)
            for i in range(1, NS + 1):
                for j in range(1, 50):
                    if W1[i, j, 1] != 0:
                        ww = W1[i, j, 1] * W1[i, j, 3]
                        Aa = W1[i, j, 2]
                        Ll = L[i]
                        Cc = W1[i, j, 3]
                        Ss_val = Aa + Cc / 2.0
                        Tt = Ll - Ss_val
                        FL[i] += ww * ((Ss_val * (Tt * Tt)) + (Ss_val - 2.0 * Tt) * (Cc * Cc) / 12.0) / (Ll * Ll)
                        FR[i] += ww * ((Tt * (Ss_val * Ss_val)) + (Tt - 2.0 * Ss_val) * (Cc * Cc) / 12.0) / (Ll * Ll)
                for j in range(1, 50):
                    if P1[i, j, 1] != 0:
                        ww = P1[i, j, 1]
                        Aa = P1[i, j, 2]
                        Ll = L[i]
                        Ss_val = Aa
                        Tt = Ll - Ss_val
                        FL[i] += ww * (Ss_val * (Tt * Tt)) / (Ll * Ll)
                        FR[i] += ww * (Tt * (Ss_val * Ss_val)) / (Ll * Ll)
            F = [0.0] * (NS + 3)
            F[1] = CL_m - FL[1]
            for i in range(2, NS + 1): F[i] = FR[i - 1] - FL[i]
            F[NS + 1] = FR[NS] - CR_m
            R_rot, d_temp, f_temp = [0.0] * (NS + 3), [0.0] * (NS + 3), [0.0] * (NS + 3)
            d_temp[1], f_temp[1] = D[1], F[1]
            for i in range(2, NS + 2):
                if abs(d_temp[i - 1]) < 1e-12:
                    raise ValueError("Singular stiffness matrix - check beam geometry.")
                m = E[i - 1] / d_temp[i - 1]
                d_temp[i] = D[i] - m * E[i - 1]
                f_temp[i] = F[i] - m * f_temp[i - 1]
            R_rot[NS + 1] = f_temp[NS + 1] / d_temp[NS + 1]
            for i in range(NS, 0, -1): R_rot[i] = (f_temp[i] - E[i] * R_rot[i + 1]) / d_temp[i]
            ML, MR, Mus = [0.0] * (NS + 2), [0.0] * (NS + 2), [0.0] * (NS + 3)
            for i in range(1, NS + 1):
                ML[i] = (4.0 * R_rot[i] + 2.0 * R_rot[i + 1]) * K2[i] + FL[i]
                MR[i] = (2.0 * R_rot[i] + 4.0 * R_rot[i + 1]) * K2[i] - FR[i]
            Mus[1] = -CL_m
            for i in range(1, NS): Mus[i + 1] = MR[i]
            Mus[NS + 1] = -CR_m
            RRR, RRL, RA = [0.0] * (NS + 2), [0.0] * (NS + 2), [0.0] * (NS + 3)
            for i in range(1, NS + 1):
                RRR1, RRL1 = -(ML[i] + MR[i]) / L[i], (ML[i] + MR[i]) / L[i]
                RRL2 = RRR2 = RRR3 = RRL3 = 0.0
                for j in range(1, 50):
                    if W1[i, j, 1] != 0:
                        q_w, Dd_w = W1[i, j, 1], W1[i, j, 3]
                        Aa_w, Bb_w = W1[i, j, 2] + Dd_w / 2.0, L[i] - (W1[i, j, 2] + Dd_w / 2.0)
                        RRL2 += (q_w * Dd_w * Bb_w / L[i]); RRR2 += (q_w * Dd_w * Aa_w / L[i])
                for j in range(1, 50):
                    if P1[i, j, 1] != 0:
                        q_p, Aa_p = P1[i, j, 1], P1[i, j, 2]
                        Bb_p = L[i] - Aa_p
                        RRR3 += (q_p * Aa_p / L[i]); RRL3 += (q_p * Bb_p / L[i])
                RRR[i], RRL[i] = -(RRR1 + RRR2 + RRR3), RRL1 + RRL2 + RRL3
            RA[1] = RRL[1] + CL_f
            for i in range(1, NS): RA[i + 1] = RRL[i + 1] - RRR[i]
            RA[NS + 1] = -RRR[NS] + CR_f
            reactions_dict = {i: float(RA[i]) for i in range(1, NS + 2)}
            c_left, c_right = float(self.cantilevers['left']), float(self.cantilevers['right'])
            total_len = c_left + sum(self.spans) + c_right
            num_pts = min(max(int(1000 * total_len) + 1, 500), 25000)
            x_full = np.linspace(0, total_len, num_pts)
            v_full, m_full = np.zeros_like(x_full), np.zeros_like(x_full)
            support_x = [c_left]
            for l_val in self.spans: support_x.append(support_x[-1] + float(l_val))
            for idx, x_pos in enumerate(x_full):
                v_val, m_val = 0.0, 0.0
                for s_i, s_x in enumerate(support_x):
                    if x_pos >= s_x:
                        v_val += float(RA[s_i + 1]); m_val += float(RA[s_i + 1]) * (x_pos - s_x)
                for load in self.loads:
                    if load['type'] == 'point' and x_pos >= float(load['x']):
                        v_val -= float(load['val']); m_val -= float(load['val']) * (x_pos - float(load['x']))
                    elif load['type'] == 'dist' and x_pos > float(load['x1']):
                        eff_len = min(x_pos, float(load['x2'])) - float(load['x1'])
                        if eff_len > 0:
                            f_w = float(load['val']) * eff_len
                            v_val -= f_w; m_val -= f_w * ((x_pos - float(load['x1'])) - eff_len / 2.0)
                v_full[idx], m_full[idx] = v_val, m_val
            self.analysis_results = {
                'solved': True, 'reactions': reactions_dict,
                'x_shear_full': list(x_full), 'v_shear_full': list(v_full),
                'x_moment_full': list(x_full), 'm_moment_full': list(m_full), 'Mus': Mus
            }
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Analysis Engine Error:\n{error_details}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze the beam structure.\n\nError Details:\n{str(e)}\n\nPlease check your input values.")
            self.analysis_results = {
                'solved': False, 'reactions': {},
                'x_shear_full': [], 'v_shear_full': [],
                'x_moment_full': [], 'm_moment_full': [], 'Mus': []
            }

    def update_ui(self):
        if self.table.state() == QTableWidget.State.EditingState: self.table.clearFocus()
        current_row = self.table.currentRow()
        self.table.blockSignals(True); self.table.setRowCount(0); self.row_mapping.clear()
        total_beam_length = float(self.cantilevers['left']) + sum(self.spans) + float(self.cantilevers['right'])
        soft_light_blue = QColor("#eef6ff")
        
        def add_row(type_str, col0, col1, col2, index=None, editable_cols=()):
            row = self.table.rowCount(); self.table.insertRow(row)
            items = [QTableWidgetItem(col0), QTableWidgetItem(col1), QTableWidgetItem(col2)]
            for c_idx, itm in enumerate(items):
                if c_idx not in editable_cols:
                    itm.setFlags(itm.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, c_idx, itm)
            mapping = {'type': type_str}
            if index is not None: mapping['index'] = index
            self.row_mapping.append(mapping)
            return row

        add_row('read_only_total', "Total Beam Length", f"{total_beam_length:.2f} m", "(Cumulative Total)", editable_cols=())
        for col in range(3):
            self.table.item(self.table.rowCount()-1, col).setBackground(soft_light_blue)
            
        if self.cantilevers['left'] > 0: add_row('left_cantilever', "Left Cantilever", f"{self.cantilevers['left']} m", "-", editable_cols=(1,))
        for i, L_val in enumerate(self.spans): add_row('span', f"Span {i+1}", f"{L_val} m", "-", i, editable_cols=(1,))
        if self.cantilevers['right'] > 0: add_row('right_cantilever', "Right Cantilever", f"{self.cantilevers['right']} m", "-", editable_cols=(1,))
        _pt_counter = 0
        for i, load in enumerate(self.loads):
            if load['type'] == 'point':
                _pt_counter += 1
                r = add_row('load', f"P{_pt_counter}", f"X = {load['x']} m", f"{load['val']} kN", i, editable_cols=(1, 2))
                self.table.item(r, 1).setToolTip("Edit position (m)")
            elif load['type'] == 'dist':
                r = add_row('load', "Distributed Load", f"From {load['x1']} to {load['x2']} m", f"{load['val']} kN/m", i, editable_cols=(1, 2))
                self.table.item(r, 1).setToolTip("Edit as: start, end  (e.g., 2.5, 7.0)")
            
        self.table.blockSignals(False)
        if 0 <= current_row < self.table.rowCount(): self.table.selectRow(current_row)

        # refresh left-side legend: colored distributed loads ONLY (point loads live in the table)
        _dists = [l for l in self.loads if l['type'] == 'dist']
        _parts = ["<b>Distributed Loads:</b>"]
        if _dists:
            for k, l in enumerate(_dists):
                _col = LOAD_PALETTE[k % len(LOAD_PALETTE)]
                _wv = float(l['val'])
                _parts.append(f'&nbsp;&nbsp;<span style="background-color:{_col};">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>&nbsp; w{k+1} = {_wv:.2f} kN/m')
        else:
            _parts.append("&nbsp;&nbsp;—   (no distributed loads)")
        self.lbl_loads_summary.setText("<br>".join(_parts))

        self.canvas.draw_results(self.spans, self.loads, self.cantilevers, self.analysis_results)

if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = StructuralAppUI()
    window.show()
    sys.exit(app.exec())