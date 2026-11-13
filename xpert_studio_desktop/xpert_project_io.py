"""
Xpert Structural Design Studio (v1.0.0)
Module: xpert_project_io.py
Lead Engineer: Eng. Yousef Mohammed Keshlaf

Handles:
1. Project Name Validation & Stractural-<ProjectName> Workspace Initialization.
2. Strict <ProjectName>- File Prefixing with Zero Unprefixed Duplicates.
3. Two-Way Live Synchronization between In-Memory Story Models, JSON Databases,
   and Standard AutoCAD .DXF Drawings ($INSUNITS = 6 Meters, Z = 0).
4. Color-Coded Non-Overlapping CAD Tags:
   - Columns (00-XD-TAG-COL): Bright Green (ACI Color 3), outside top-right corner.
   - Beams (00-XD-TAG-BEAM): Bright Orange (ACI Color 30), parallel to beam at
     the midpoint of the first clear span (strictly between columns).
"""

from __future__ import annotations
import json
import os
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple

try:
    import ezdxf
except ImportError:
    ezdxf = None


STUDIO_VERSION = "v1.0.0-studio-foundation"

STANDARD_LAYERS = [
    ("00-XD-EDGE", 4, "Continuous"),       # Cyan: Outer Slab Boundary
    ("00-XD-OPEN", 6, "Continuous"),       # Magenta: Slab Openings
    ("00-XD-COL", 1, "Continuous"),        # Red: Structural Columns
    ("00-XD-BEAM-HID", 2, "DASHED"),       # Yellow: Hidden Beams
    ("00-XD-BEAM-DROP", 3, "Continuous"),  # Green: Drop Beams
    ("00-XD-SLAB", 40, "Continuous"),      # Gold: One-Way Hollow-Block Ribs
    ("00-XD-TAG-COL", 3, "Continuous"),    # Bright Green: Column Tags (C1..Cn)
    ("00-XD-TAG-BEAM", 30, "Continuous"),  # Bright Orange: Beam Tags (B1..Bm)
    ("00-XD-ARCH-REF", 8, "Continuous"),   # Gray: Imported Architectural Underlay
]


def validate_project_name(name: str) -> Tuple[bool, str, str, str]:
    """
    Validates project identifier (alphanumeric and spaces/underscores only).
    Returns: (is_valid, clean_name, folder_name, error_message_en)
    """
    trimmed = (name or "").strip()
    if not trimmed:
        return False, "", "", "Project Name cannot be empty."
    if not re.match(r"^[A-Za-z0-9_\s\-]+$", trimmed):
        return (
            False,
            "",
            "",
            "Project Name must contain English letters, digits, spaces, or hyphens only (no special symbols).",
        )
    clean_name = re.sub(r"\s+", "_", trimmed)
    folder_name = f"Stractural-{clean_name}"
    return True, clean_name, folder_name, ""


def compute_hollow_block_parameters(
    slab_thickness_cm: float = 30.0,
    rib_width_cm: float = 15.0,
    block_width_cm: float = 40.0,
    block_length_cm: float = 25.0,
    block_weight_kn: float = 0.10,
    finish_load_kn_m2: float = 2.0,
    live_load_kn_m2: float = 2.0,
) -> Dict[str, float]:
    """
    Computes hollow-block (Hordi) parameters per Eng. Yousef's standard rules:
    - t_s <= 24 cm -> h_block = 16 cm
    - t_s >= 25 cm -> h_block = 20 cm
    """
    block_height_cm = 20.0 if slab_thickness_cm >= 25.0 else 16.0
    top_flange_cm = max(5.0, slab_thickness_cm - block_height_cm)
    rib_spacing_cm = block_width_cm + rib_width_cm  # Default 55 cm
    gamma_rc = 25.0  # kN/m3

    top_slab_wt = (top_flange_cm / 100.0) * gamma_rc
    rib_vol_per_m = (rib_width_cm / 100.0) * (block_height_cm / 100.0)
    ribs_per_m = 100.0 / rib_spacing_cm
    ribs_wt = rib_vol_per_m * ribs_per_m * gamma_rc

    blocks_per_m2 = (100.0 / rib_spacing_cm) * (100.0 / block_length_cm)
    blocks_wt = blocks_per_m2 * block_weight_kn

    self_weight_kn_m2 = round(top_slab_wt + ribs_wt + blocks_wt, 2)
    total_dead_kn_m2 = round(self_weight_kn_m2 + finish_load_kn_m2, 2)
    total_service_kn_m2 = round(total_dead_kn_m2 + live_load_kn_m2, 2)
    total_factored_wu_kn_m2 = round(1.2 * total_dead_kn_m2 + 1.6 * live_load_kn_m2, 2)

    return {
        "block_height_cm": block_height_cm,
        "top_flange_cm": top_flange_cm,
        "rib_spacing_cm": rib_spacing_cm,
        "blocks_per_m2": round(blocks_per_m2, 2),
        "self_weight_kn_m2": self_weight_kn_m2,
        "total_dead_kn_m2": total_dead_kn_m2,
        "total_service_kn_m2": total_service_kn_m2,
        "total_factored_wu_kn_m2": total_factored_wu_kn_m2,
    }


def cleanup_unprefixed_duplicates(project_dir: str, clean_project_name: str) -> None:
    """
    Ensures zero legacy unprefixed files remain inside Stractural-<ProjectName>.
    """
    prefix = f"{clean_project_name}-"
    for sub in ["", "CAD_Drawings", "Stories_Data"]:
        target_dir = os.path.join(project_dir, sub) if sub else project_dir
        if not os.path.isdir(target_dir):
            continue
        for fname in os.listdir(target_dir):
            if fname.endswith((".dxf", ".json", ".xpert")) and not fname.startswith(prefix):
                full_p = os.path.join(target_dir, fname)
                try:
                    os.remove(full_p)
                except OSError:
                    pass


MASTER_FILE_EXT = ".xpert"


def load_studio_project_from_master_file(master_path: str) -> Dict[str, Any]:
    """
    Loads an existing project from its custom `<ProjectName>-00_Project_Master.xpert`
    (or `.json`) file and resolves relative story paths if the project folder was moved.
    """
    abs_path = os.path.abspath(master_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Master project file not found: {abs_path}")

    with open(abs_path, "r", encoding="utf-8") as f:
        master_payload = json.load(f)

    project_dir = os.path.dirname(abs_path)
    master_payload["project_dir"] = project_dir
    master_payload["master_file"] = abs_path

    clean_name = master_payload.get("project_name", "Project")
    stories_dir = os.path.join(project_dir, "Stories_Data")
    cad_dir = os.path.join(project_dir, "CAD_Drawings")

    for sm in master_payload.get("stories", []):
        sid = sm["story_id"]
        sm["json_file"] = os.path.join(stories_dir, f"{clean_name}-{sid}.json")
        sm["dxf_file"] = os.path.join(cad_dir, f"{clean_name}-{sid}.dxf")

    return master_payload


def initialize_studio_project(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates Stractural-<ProjectName> and generates the custom `<ProjectName>-00_Project_Master.xpert`
    master file along with all `<ProjectName>-` prefixed JSON and DXF files.
    """
    raw_name = config.get("project_name", "NewProject")
    ok, clean_name, folder_name, err = validate_project_name(raw_name)
    if not ok:
        raise ValueError(err)

    root_dir = config.get("root_directory") or os.path.abspath("./XpertStudio_Projects")
    project_dir = os.path.join(root_dir, folder_name)
    cad_dir = os.path.join(project_dir, "CAD_Drawings")
    stories_dir = os.path.join(project_dir, "Stories_Data")

    os.makedirs(cad_dir, exist_ok=True)
    os.makedirs(stories_dir, exist_ok=True)

    cleanup_unprefixed_duplicates(project_dir, clean_name)

    ground_h = float(config.get("ground_floor_height_m", 3.20))
    basement_h = float(config.get("basement_height_m", 3.00))
    upper_h = float(config.get("upper_floor_height_m", 3.00))
    penthouse_h = float(config.get("penthouse_height_m", 3.00))
    foundation_depth = float(config.get("foundation_depth_m", 1.50))

    include_basement = bool(config.get("include_basement", False))
    floors_above_ground = max(0, int(config.get("floors_above_ground", 0)))
    upper_mode = config.get("upper_floors_mode", "typical")  # 'typical' or 'distinct'
    include_penthouse = bool(config.get("include_penthouse", False))

    stories_meta: List[Dict[str, Any]] = []

    # 00 - Tie Beams
    stories_meta.append({
        "story_id": "00_TieBeams",
        "story_label": "00 - Tie Beams & Grade Beams",
        "story_type": "tie_beams",
        "multiplier": 1,
        "height_m": foundation_depth,
        "adopted_slab_thickness_cm": 0.0,
        "allow_hidden_beams": False,
        "allow_slabs": False,
        "status": "PENDING_GROUND_COLUMNS",
    })

    # 01 - Optional Basement
    if include_basement:
        stories_meta.append({
            "story_id": "01_Basement_Slab",
            "story_label": "01 - Basement Floor Slab",
            "story_type": "basement",
            "multiplier": 1,
            "height_m": basement_h,
            "adopted_slab_thickness_cm": 30.0,
            "allow_hidden_beams": True,
            "allow_slabs": True,
            "status": "PENDING_GROUND_COLUMNS",
        })

    # 02 - Mandatory Ground Floor
    stories_meta.append({
        "story_id": "02_Ground_Floor",
        "story_label": "02 - Ground Floor Slab (Mandatory Start)",
        "story_type": "ground",
        "multiplier": 1,
        "height_m": ground_h,
        "adopted_slab_thickness_cm": 30.0,
        "allow_hidden_beams": True,
        "allow_slabs": True,
        "status": "ACTIVE_START",
    })

    # Upper Floors (03+)
    next_code = 3
    if floors_above_ground > 0:
        if upper_mode == "typical" and floors_above_ground >= 1:
            stories_meta.append({
                "story_id": f"{next_code:02d}_Typical_Floor",
                "story_label": f"{next_code:02d} - Typical Upper Floor (x{floors_above_ground})",
                "story_type": "typical",
                "multiplier": floors_above_ground,
                "height_m": upper_h,
                "adopted_slab_thickness_cm": 30.0,
                "allow_hidden_beams": True,
                "allow_slabs": True,
                "status": "PENDING_GROUND_COLUMNS",
            })
            next_code += 1
        else:
            for idx in range(floors_above_ground):
                stories_meta.append({
                    "story_id": f"{next_code:02d}_Upper_Floor_{idx + 1}",
                    "story_label": f"{next_code:02d} - Upper Floor #{idx + 1}",
                    "story_type": "standard",
                    "multiplier": 1,
                    "height_m": upper_h,
                    "adopted_slab_thickness_cm": 30.0,
                    "allow_hidden_beams": True,
                    "allow_slabs": True,
                    "status": "PENDING_GROUND_COLUMNS",
                })
                next_code += 1

    # Optional Roof Annex / Penthouse (Unchecked by default)
    if include_penthouse:
        stories_meta.append({
            "story_id": f"{next_code:02d}_Penthouse_Floor",
            "story_label": f"{next_code:02d} - Roof Annex / Penthouse Slab",
            "story_type": "penthouse",
            "multiplier": 1,
            "height_m": penthouse_h,
            "adopted_slab_thickness_cm": 30.0,
            "allow_hidden_beams": True,
            "allow_slabs": True,
            "status": "PENDING_GROUND_COLUMNS",
        })

    hordi_defaults = compute_hollow_block_parameters(
        slab_thickness_cm=30.0,
        rib_width_cm=float(config.get("rib_width_cm", 15.0)),
        finish_load_kn_m2=float(config.get("finish_load_kn_m2", 2.0)),
        live_load_kn_m2=float(config.get("live_load_kn_m2", 2.0)),
    )

    master_xpert_file = os.path.join(project_dir, f"{clean_name}-00_Project_Master{MASTER_FILE_EXT}")
    master_json_file = os.path.join(project_dir, f"{clean_name}-00_Project_Master.json")

    master_payload = {
        "studio_version": STUDIO_VERSION,
        "file_format": "XPERT_STRUCTURAL_PROJECT_MASTER",
        "project_uuid": f"XPERT-{uuid.uuid4().hex[:8].upper()}",
        "project_name": clean_name,
        "folder_name": folder_name,
        "project_dir": project_dir,
        "master_file": master_xpert_file,
        "mandatory_start_story_id": "02_Ground_Floor",
        "materials_and_soil": {
            "fc_mpa": float(config.get("fc_mpa", 20.0)),
            "fy_mpa": float(config.get("fy_mpa", 350.0)),
            "soil_bearing_qall_kn_m2": float(config.get("soil_bearing_qall_kn_m2", 150.0)),
            "foundation_depth_m": foundation_depth,
        },
        "story_heights": {
            "ground_floor_height_m": ground_h,
            "basement_height_m": basement_h,
            "upper_floor_height_m": upper_h,
            "penthouse_height_m": penthouse_h,
            "foundation_depth_m": foundation_depth,
        },
        "loads_and_defaults": {
            "default_slab_thickness_cm": 30.0,
            "default_column_b_m": 0.20,
            "default_column_h_m": 0.40,
            "finish_load_kn_m2": float(config.get("finish_load_kn_m2", 2.0)),
            "live_load_kn_m2": float(config.get("live_load_kn_m2", 2.0)),
            "rib_width_cm": float(config.get("rib_width_cm", 15.0)),
            "hidden_beam_min_width_cm": float(config.get("hidden_beam_min_width_cm", 30.0)),
            "drop_beam_width_cm": float(config.get("drop_beam_width_cm", 20.0)),
            "drop_beam_min_depth_cm": float(config.get("drop_beam_min_depth_cm", 40.0)),
            "wall_width_cm": float(config.get("wall_width_cm", 20.0)),
            "hollow_block_defaults": hordi_defaults,
        },
        "stories": [],
    }

    for sm in stories_meta:
        sid = sm["story_id"]
        json_fname = f"{clean_name}-{sid}.json"
        dxf_fname = f"{clean_name}-{sid}.dxf"
        json_path = os.path.join(stories_dir, json_fname)
        dxf_path = os.path.join(cad_dir, dxf_fname)

        sm_entry = dict(sm)
        sm_entry["json_file"] = json_path
        sm_entry["dxf_file"] = dxf_path
        master_payload["stories"].append(sm_entry)

        story_data = {
            "project_name": clean_name,
            "story_id": sid,
            "story_label": sm["story_label"],
            "story_type": sm["story_type"],
            "multiplier": sm["multiplier"],
            "height_m": sm["height_m"],
            "adopted_slab_thickness_cm": sm["adopted_slab_thickness_cm"],
            "slab_edge_polygon": [],
            "openings": [],
            "columns": [],
            "beams": [],
            "slabs": [],
            "arch_underlay_lines": [],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(story_data, f, indent=2)

        sync_story_to_dxf(story_data, dxf_path, role="STORY_EXTRACTION")

    # Root Master (.xpert and .json) & Output JSON files
    takedown_file = os.path.join(project_dir, f"{clean_name}-Columns_Load_Takedown.json")
    foundations_file = os.path.join(project_dir, f"{clean_name}-Foundations_Design.json")
    boq_file = os.path.join(project_dir, f"{clean_name}-BOQ_Quantities.json")
    foundations_dxf = os.path.join(cad_dir, f"{clean_name}-Foundations_And_Axes.dxf")

    with open(master_xpert_file, "w", encoding="utf-8") as f:
        json.dump(master_payload, f, indent=2)

    with open(master_json_file, "w", encoding="utf-8") as f:
        json.dump(master_payload, f, indent=2)

    with open(takedown_file, "w", encoding="utf-8") as f:
        json.dump({"project_name": clean_name, "columns_takedown": {}}, f, indent=2)

    with open(foundations_file, "w", encoding="utf-8") as f:
        json.dump({"project_name": clean_name, "footings": []}, f, indent=2)

    with open(boq_file, "w", encoding="utf-8") as f:
        json.dump({"project_name": clean_name, "stories_boq": {}, "total_concrete_m3": 0.0, "total_steel_kg": 0.0}, f, indent=2)

    sync_story_to_dxf(
        {"project_name": clean_name, "story_id": "Foundations_And_Axes", "columns": [], "beams": [], "slabs": []},
        foundations_dxf,
        role="FOUNDATION_PLOT_ONLY",
    )

    cleanup_unprefixed_duplicates(project_dir, clean_name)
    return master_payload


def compute_smart_beam_tag_position(
    beam: Dict[str, Any],
    columns: List[Dict[str, Any]],
    placed_positions: List[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """
    Computes a non-overlapping label position (x, y, rotation_deg) for a beam B#:
    - Places the label near the midpoint of the beam (or midpoint of its first clear span
      if a column sits directly at the overall midpoint), and slightly ABOVE the top face
      of the full-width beam rectangle (offset = width_m / 2.0 + 0.12 m).
    """
    sx = float(beam.get("start_x", 0.0))
    sy = float(beam.get("start_y", 0.0))
    ex = float(beam.get("end_x", 5.0))
    ey = float(beam.get("end_y", 0.0))
    b_width = float(beam.get("width_m", 0.30))

    dx = ex - sx
    dy = ey - sy
    length = max(0.01, (dx * dx + dy * dy) ** 0.5)
    ux = dx / length
    uy = dy / length
    # Perpendicular unit vector (above horizontal beam, left of vertical beam)
    nx = -uy
    ny = ux

    is_vertical = abs(dy) > abs(dx)
    rot_deg = 90.0 if is_vertical else 0.0

    # Offset slightly above the outer face of the full-width beam rectangle
    perp_offset = (b_width / 2.0) + 0.12

    # Prefer near the beam midpoint; if an intermediate column is at the exact midpoint,
    # shift slightly toward the first clear span midpoint so it never sits on a column
    mid_dist = length * 0.50
    spans = beam.get("spans", [])
    first_span_mid = float(spans[0]) * 0.50 if spans else length * 0.45

    cand_x = sx + ux * mid_dist + nx * perp_offset
    cand_y = sy + uy * mid_dist + ny * perp_offset

    for shift_try in [0.0, first_span_mid - mid_dist, 0.50, -0.50, 0.95, -0.95]:
        tx = sx + ux * (mid_dist + shift_try) + nx * perp_offset
        ty = sy + uy * (mid_dist + shift_try) + ny * perp_offset
        collision = False
        for col in columns:
            cx, cy = float(col.get("x", 0.0)), float(col.get("y", 0.0))
            if ((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5 < 0.42:
                collision = True
                break
        if not collision:
            for px, py in placed_positions:
                if ((tx - px) ** 2 + (ty - py) ** 2) ** 0.5 < 0.40:
                    collision = True
                    break
        if not collision:
            placed_positions.append((tx, ty))
            return round(tx, 3), round(ty, 3), rot_deg

    placed_positions.append((cand_x, cand_y))
    return round(cand_x, 3), round(cand_y, 3), rot_deg


def _write_ascii_dxf_fallback(story_data: Dict[str, Any], dxf_path: str) -> None:
    """
    Pure-Python standard ASCII DXF writer fallback when ezdxf is not installed.
    Writes layers, closed column polylines, beams, and color-coded non-overlapping tags.
    """
    lines = [
        "0", "SECTION", "2", "HEADER",
        "9", "$INSUNITS", "70", "6",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]
    placed_tags: List[Tuple[float, float]] = []
    columns = story_data.get("columns", [])
    for col in columns:
        if not col.get("active", True):
            continue
        cx, cy = float(col["x"]), float(col["y"])
        b, h = float(col.get("b_m", 0.25)), float(col.get("h_m", 0.50))
        cid = str(col["id"])
        tag_x = round(cx + b / 2.0 + 0.12, 3)
        tag_y = round(cy + h / 2.0 + 0.12, 3)
        placed_tags.append((tag_x, tag_y))
        lines.extend([
            "0", "TEXT", "8", "00-XD-TAG-COL", "62", "3",
            "10", str(tag_x), "20", str(tag_y), "30", "0.0",
            "40", "0.22", "1", cid,
        ])

    for bm in story_data.get("beams", []):
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 5.0)), float(bm.get("end_y", 0.0))
        b_kind = bm.get("beam_kind", "hidden")
        layer = "00-XD-BEAM-HID" if b_kind == "hidden" else "00-XD-BEAM-DROP"
        lines.extend([
            "0", "LINE", "8", layer,
            "10", str(sx), "20", str(sy), "30", "0.0",
            "11", str(ex), "21", str(ey), "31", "0.0",
        ])
        tx, ty, rot_deg = compute_smart_beam_tag_position(bm, columns, placed_tags)
        lines.extend([
            "0", "TEXT", "8", "00-XD-TAG-BEAM", "62", "30",
            "10", str(tx), "20", str(ty), "30", "0.0",
            "40", "0.25", "50", str(rot_deg), "1", str(bm["id"]),
        ])

    lines.extend(["0", "ENDSEC", "0", "EOF"])
    with open(dxf_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def sync_story_to_dxf(story_data: Dict[str, Any], dxf_path: str, role: str = "STORY_EXTRACTION") -> None:
    """
    Writes the complete story geometry and color-coded non-overlapping tags
    to a standard AutoCAD .DXF file ($INSUNITS = 6 Meters).
    """
    if ezdxf is None:
        _write_ascii_dxf_fallback(story_data, dxf_path)
        return

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6  # Meters

    if "XD_TAG_STYLE" not in doc.styles:
        doc.styles.add("XD_TAG_STYLE", font="arial.ttf")

    for layer_name, aci_color, ltype in STANDARD_LAYERS:
        if layer_name not in doc.layers:
            doc.layers.add(name=layer_name, color=aci_color)

    msp = doc.modelspace()

    # 1. Outer Slab Boundary (00-XD-EDGE)
    edge_pts = story_data.get("slab_edge_polygon", [])
    if len(edge_pts) >= 3:
        pts_2d = [(float(p[0]), float(p[1])) for p in edge_pts]
        poly = msp.add_lwpolyline(pts_2d, dxfattribs={"layer": "00-XD-EDGE"})
        poly.closed = True

    # 2. Columns (00-XD-COL) & Bright Green Column Tags (00-XD-TAG-COL)
    placed_tags: List[Tuple[float, float]] = []
    columns = story_data.get("columns", [])
    for col in columns:
        if not col.get("active", True):
            continue
        cx = float(col["x"])
        cy = float(col["y"])
        b = float(col.get("b_m", 0.25))
        h = float(col.get("h_m", 0.50))
        cid = str(col["id"])

        corners = [
            (cx - b / 2.0, cy - h / 2.0),
            (cx + b / 2.0, cy - h / 2.0),
            (cx + b / 2.0, cy + h / 2.0),
            (cx - b / 2.0, cy + h / 2.0),
        ]
        cpoly = msp.add_lwpolyline(corners, dxfattribs={"layer": "00-XD-COL", "color": 1})
        cpoly.closed = True

        # Place C# tag OUTSIDE the top-right corner in Bright Green (ACI Color 3)
        tag_x = round(cx + b / 2.0 + 0.12, 3)
        tag_y = round(cy + h / 2.0 + 0.12, 3)
        placed_tags.append((tag_x, tag_y))
        msp.add_text(
            cid,
            dxfattribs={
                "layer": "00-XD-TAG-COL",
                "style": "XD_TAG_STYLE",
                "height": 0.22,
                "color": 3,
                "insert": (tag_x, tag_y, 0.0),
            },
        )

    # 3. Beams (00-XD-BEAM-HID / 00-XD-BEAM-DROP) & Bright Orange Beam Tags (00-XD-TAG-BEAM)
    beams = story_data.get("beams", [])
    for bm in beams:
        sx = float(bm.get("start_x", 0.0))
        sy = float(bm.get("start_y", 0.0))
        ex = float(bm.get("end_x", 5.0))
        ey = float(bm.get("end_y", 0.0))
        b_kind = bm.get("beam_kind", "hidden")
        b_width = float(bm.get("width_m", 0.30 if b_kind == "hidden" else 0.20))
        layer = "00-XD-BEAM-HID" if b_kind == "hidden" else "00-XD-BEAM-DROP"
        color = 2 if b_kind == "hidden" else 3

        msp.add_lwpolyline(
            [(sx, sy), (ex, ey)],
            dxfattribs={"layer": layer, "color": color, "const_width": b_width},
        )

        # Place B# tag at clear-span midpoint in Bright Orange (ACI Color 30)
        tx, ty, rot_deg = compute_smart_beam_tag_position(bm, columns, placed_tags)
        msp.add_text(
            str(bm["id"]),
            dxfattribs={
                "layer": "00-XD-TAG-BEAM",
                "style": "XD_TAG_STYLE",
                "height": 0.25,
                "color": 30,
                "rotation": rot_deg,
                "insert": (tx, ty, 0.0),
            },
        )

    doc.saveas(dxf_path)


def propagate_ground_columns_to_all_stories(master_payload: Dict[str, Any], ground_columns: List[Dict[str, Any]]) -> None:
    """
    Propagates the approved Ground Floor columns (C1..Cn) with their exact IDs
    and coordinates into 00_TieBeams and all upper stories.
    """
    for s_entry in master_payload.get("stories", []):
        sid = s_entry["story_id"]
        if sid == "02_Ground_Floor":
            continue
        jpath = s_entry.get("json_file")
        dpath = s_entry.get("dxf_file")
        if not jpath or not os.path.isfile(jpath):
            continue
        with open(jpath, "r", encoding="utf-8") as f:
            sdata = json.load(f)

        existing_discontinued = {
            c["id"] for c in sdata.get("columns", []) if not c.get("active", True)
        }
        updated_cols = []
        for gc in ground_columns:
            c_copy = dict(gc)
            if c_copy["id"] in existing_discontinued:
                c_copy["active"] = False
            updated_cols.append(c_copy)

        sdata["columns"] = updated_cols
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(sdata, f, indent=2)
        if dpath:
            sync_story_to_dxf(sdata, dpath)


def import_arch_dxf_underlay(dxf_file_path: str) -> Dict[str, Any]:
    """
    Imports an external Architectural .DXF file for a single story as a unified,
    locked reference block (`arch_underlay_block`) containing clean 2D line segments
    and candidate architectural column rectangles so they never mix with structural entities.
    """
    if not os.path.isfile(dxf_file_path):
        raise FileNotFoundError(f"Architectural DXF file not found: {dxf_file_path}")

    segments: List[List[float]] = []  # [[x1, y1, x2, y2], ...]
    closed_rects: List[Dict[str, float]] = []

    if ezdxf is not None:
        doc = ezdxf.readfile(dxf_file_path)
        msp = doc.modelspace()
        for ent in msp:
            etype = ent.dxftype()
            if etype == "LINE":
                s = ent.dxf.start
                e = ent.dxf.end
                segments.append([round(float(s.x), 3), round(float(s.y), 3), round(float(e.x), 3), round(float(e.y), 3)])
            elif etype in ("LWPOLYLINE", "POLYLINE"):
                pts = []
                if etype == "LWPOLYLINE":
                    pts = [(float(p[0]), float(p[1])) for p in ent.get_points("xy")]
                    is_closed = bool(ent.closed)
                else:
                    pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
                    is_closed = bool(ent.is_closed)
                if len(pts) >= 2:
                    for idx in range(len(pts) - 1):
                        segments.append([
                            round(pts[idx][0], 3), round(pts[idx][1], 3),
                            round(pts[idx + 1][0], 3), round(pts[idx + 1][1], 3),
                        ])
                    if is_closed or (len(pts) >= 4 and pts[0] == pts[-1]):
                        segments.append([
                            round(pts[-1][0], 3), round(pts[-1][1], 3),
                            round(pts[0][0], 3), round(pts[0][1], 3),
                        ])
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        bw = round(max(xs) - min(xs), 3)
                        bh = round(max(ys) - min(ys), 3)
                        if 0.15 <= bw <= 1.20 and 0.15 <= bh <= 1.20:
                            closed_rects.append({
                                "x": round((min(xs) + max(xs)) / 2.0, 3),
                                "y": round((min(ys) + max(ys)) / 2.0, 3),
                                "b_m": bw,
                                "h_m": bh,
                            })
    else:
        # Lightweight ASCII DXF LINE parser fallback
        with open(dxf_file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = [line.strip() for line in f.readlines()]
        idx = 0
        n = len(raw_lines)
        while idx < n - 1:
            if raw_lines[idx] == "0" and raw_lines[idx + 1] == "LINE":
                idx += 2
                x1 = y1 = x2 = y2 = 0.0
                while idx < n - 1 and raw_lines[idx] != "0":
                    code = raw_lines[idx]
                    val = raw_lines[idx + 1]
                    if code == "10":
                        x1 = float(val)
                    elif code == "20":
                        y1 = float(val)
                    elif code == "11":
                        x2 = float(val)
                    elif code == "21":
                        y2 = float(val)
                    idx += 2
                segments.append([round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)])
            else:
                idx += 2

    return {
        "source_file": os.path.basename(dxf_file_path),
        "visible": True,
        "locked": True,
        "segments": segments,
        "candidate_columns": closed_rects,
    }

