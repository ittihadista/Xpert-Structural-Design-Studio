"""
Xpert Structural Design Studio (v2.5.0-structural-bim-pro)
Module: xpert_project_io.py
Lead Engineer: Eng. Yousef Mohammed Keshlaf

Handles:
1. Project Name Validation & Stractural-<ProjectName> Workspace Initialization.
2. Strict <ProjectName>- File Prefixing with Zero Unprefixed Duplicates.
3. Two-Way Live Synchronization between In-Memory Story Models, JSON Databases,
   and Standard AutoCAD .DXF Drawings ($INSUNITS = 6 Meters, Z = 0).
4. Ground-to-Upper Column Propagation, Continuity Cascade, and Tie-Beams Neck Columns.
5. Color-Coded Non-Overlapping CAD Tags:
   - Columns (00-XD-TAG-COL): Bright Green (ACI Color 3), outside top-right corner.
   - Beams (00-XD-TAG-BEAM): Bright Orange (ACI Color 30), parallel to beam at
     the midpoint of the first clear span (strictly between columns).
"""

from __future__ import annotations
import datetime
import json
import os
import re
import threading
import uuid
from typing import Dict, Any, List, Optional, Tuple

try:
    import ezdxf
except ImportError:
    ezdxf = None


STUDIO_VERSION = "v2.5.0-structural-bim-pro"
MASTER_FILE_EXT = ".xsd"

_LOG_LOCK = threading.Lock()
_ACTIVE_PROJECT_LOG_DIR: Optional[str] = None


def set_active_project_log_dir(project_dir: Optional[str]) -> None:
    global _ACTIVE_PROJECT_LOG_DIR
    if project_dir and os.path.isdir(project_dir):
        _ACTIVE_PROJECT_LOG_DIR = os.path.abspath(project_dir)
    else:
        _ACTIVE_PROJECT_LOG_DIR = None


def get_studio_log_file_path(project_dir: Optional[str] = None) -> str:
    if project_dir and os.path.isdir(project_dir):
        abs_dir = os.path.abspath(project_dir)
        stories_sub = os.path.join(abs_dir, "Stories_Data")
        if os.path.isdir(stories_sub):
            return os.path.join(stories_sub, "xpert_studio_session.log")
        return os.path.join(abs_dir, "xpert_studio_session.log")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "xpert_studio_session.log")


def log_studio_event(
    category: str,
    message: str,
    details: Optional[Any] = None,
    level: str = "INFO",
) -> None:
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entry = f"[{ts}] [{STUDIO_VERSION}] [{level.upper()}] [{category.upper()}] {message}"
        if details is not None:
            if isinstance(details, str):
                det_str = details.strip()
            else:
                try:
                    det_str = json.dumps(details, ensure_ascii=False, indent=2, default=str)
                except Exception:
                    det_str = str(details)
            if det_str:
                indented = "\n".join(f"    {ln}" for ln in det_str.splitlines())
                entry = f"{entry}\n{indented}"
        entry += "\n"

        targets = [get_studio_log_file_path()]
        if _ACTIVE_PROJECT_LOG_DIR:
            proj_log = get_studio_log_file_path(_ACTIVE_PROJECT_LOG_DIR)
            if proj_log not in targets:
                targets.append(proj_log)

        with _LOG_LOCK:
            for tpath in targets:
                try:
                    os.makedirs(os.path.dirname(tpath), exist_ok=True)
                    with open(tpath, "a", encoding="utf-8") as lf:
                        lf.write(entry)
                except OSError:
                    pass
    except Exception:
        pass


def read_studio_log_tail(max_lines: int = 500, project_dir: Optional[str] = None) -> str:
    path = get_studio_log_file_path(project_dir)
    if not os.path.isfile(path):
        return f"No diagnostic log recorded yet at: {path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as lf:
            lines = lf.readlines()
        if max_lines > 0 and len(lines) > max_lines:
            lines = lines[-max_lines:]
        return "".join(lines)
    except OSError as exc:
        return f"Unable to read log file {path}: {exc}"


def clear_studio_log(project_dir: Optional[str] = None) -> None:
    path = get_studio_log_file_path(project_dir)
    try:
        with _LOG_LOCK:
            with open(path, "w", encoding="utf-8") as lf:
                lf.write("")
    except OSError:
        pass


DEFAULT_REBAR_DIAMETERS_TABLE: List[Dict[str, Any]] = [
    {"active": True, "enabled": True, "label": "Φ 6", "bar_name": "Φ6", "dia_mm": 6, "diameter_mm": 6, "area_mm2": 28.27, "weight_kg_m": 0.222, "role": "Stirrups (Ribs & Beams)"},
    {"active": True, "enabled": True, "label": "Φ 8", "bar_name": "Φ8", "dia_mm": 8, "diameter_mm": 8, "area_mm2": 50.27, "weight_kg_m": 0.395, "role": "Stirrups (Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 10", "bar_name": "Φ10", "dia_mm": 10, "diameter_mm": 10, "area_mm2": 78.54, "weight_kg_m": 0.617, "role": "Stirrups / Top Fixation Bar"},
    {"active": True, "enabled": True, "label": "Φ 12", "bar_name": "Φ12", "dia_mm": 12, "diameter_mm": 12, "area_mm2": 113.10, "weight_kg_m": 0.888, "role": "Longitudinal / Slab Ribs"},
    {"active": True, "enabled": True, "label": "Φ 14", "bar_name": "Φ14", "dia_mm": 14, "diameter_mm": 14, "area_mm2": 153.94, "weight_kg_m": 1.208, "role": "Longitudinal / Slab Ribs"},
    {"active": True, "enabled": True, "label": "Φ 16", "bar_name": "Φ16", "dia_mm": 16, "diameter_mm": 16, "area_mm2": 201.06, "weight_kg_m": 1.578, "role": "Longitudinal (Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 18", "bar_name": "Φ18", "dia_mm": 18, "diameter_mm": 18, "area_mm2": 254.47, "weight_kg_m": 1.998, "role": "Longitudinal (Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 20", "bar_name": "Φ20", "dia_mm": 20, "diameter_mm": 20, "area_mm2": 314.16, "weight_kg_m": 2.466, "role": "Longitudinal (Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 22", "bar_name": "Φ22", "dia_mm": 22, "diameter_mm": 22, "area_mm2": 380.13, "weight_kg_m": 2.984, "role": "Longitudinal (Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 25", "bar_name": "Φ25", "dia_mm": 25, "diameter_mm": 25, "area_mm2": 490.87, "weight_kg_m": 3.853, "role": "Longitudinal (Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 28", "bar_name": "Φ28", "dia_mm": 28, "diameter_mm": 28, "area_mm2": 615.75, "weight_kg_m": 4.834, "role": "Longitudinal (Heavy Beams & Columns)"},
    {"active": True, "enabled": True, "label": "Φ 32", "bar_name": "Φ32", "dia_mm": 32, "diameter_mm": 32, "area_mm2": 804.25, "weight_kg_m": 6.313, "role": "Longitudinal (Heavy Beams & Columns)"},
]


def _get_global_settings_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "xpert_studio_defaults.json")


def _normalize_rebar_table(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_dia: Dict[int, Dict[str, Any]] = {}
    for r in DEFAULT_REBAR_DIAMETERS_TABLE:
        d = int(r["dia_mm"])
        by_dia[d] = dict(r)
    for r in (rows or []):
        try:
            d = int(r.get("diameter_mm", r.get("dia_mm", 0)))
        except Exception:
            continue
        if d <= 0:
            continue
        en = bool(r.get("enabled", r.get("active", True)))
        lbl = str(r.get("bar_name", r.get("label", f"Φ{d}")))
        area = float(r.get("area_mm2", round(3.14159265 * d * d / 4.0, 2)))
        wt = float(r.get("weight_kg_m", round(d * d / 162.2, 3)))
        role = str(r.get("role", by_dia.get(d, {}).get("role", "Longitudinal")))
        by_dia[d] = {
            "active": en,
            "enabled": en,
            "label": lbl,
            "bar_name": lbl,
            "dia_mm": d,
            "diameter_mm": d,
            "area_mm2": area,
            "weight_kg_m": wt,
            "role": role,
        }
    return [by_dia[d] for d in sorted(by_dia.keys())]


def load_studio_global_settings() -> Dict[str, Any]:
    default_root = os.path.abspath("./XpertStudio_Projects")
    mat_defaults = {
        "fc_mpa": 20.0,
        "fy_mpa": 350.0,
        "fyt_mpa": 280.0,
        "fy_stirrups_mpa": 280.0,
        "gamma_c_kn_m3": 24.0,
        "concrete_unit_weight_kn_m3": 24.0,
        "soil_bearing_qall_kn_m2": 150.0,
        "beam_compression_steel_mode": "double_as_min",
    }
    hb_defaults = {
        "slab_thickness_cm": 30.0,
        "top_flange_cm": 10.0,
        "top_compression_slab_cm": 10.0,
        "block_height_cm": 20.0,
        "block_width_cm": 40.0,
        "block_length_cm": 25.0,
        "rib_width_cm": 15.0,
        "rib_bw2_cm": 15.0,
        "slab_cover_mm": 20.0,
        "rib_bar_dia_mm": 12,
        "rib_stirrup_dia_mm": 6,
        "block_weight_kn": 0.10,
        "finish_load_kn_m2": 1.5,
        "finishing_load_kpa": 1.5,
        "live_load_kn_m2": 2.0,
        "live_load_kpa": 2.0,
        "dl_factor": 1.4,
        "ll_factor": 1.7,
        "wu_rib_kn_m": 6.44,
        "slab_factored_wu_kpa": 11.71,
        "wall_thickness_cm": 20.0,
        "wall_unit_wt_20cm_kn_m2": 2.5,
        "default_wall_load_kn_m": 10.50,
        "hidden_beam_min_width_cm": 40.0,
        "drop_beam_width_cm": 20.0,
        "drop_beam_min_depth_cm": 40.0,
        "drop_beam_depth_cm": 40.0,
    }
    rebar_table = _normalize_rebar_table(DEFAULT_REBAR_DIAMETERS_TABLE)

    defaults: Dict[str, Any] = {
        "schema_version": "2.5.0",
        "default_projects_root_folder": default_root,
        "default_stirrup_bar_mm": 6,
        "default_main_bar_mm": 16,
        "rebar_diameters_table": rebar_table,
        "materials_and_soil": dict(mat_defaults),
        "hollow_block_slab_data": dict(hb_defaults),
        "startup_defaults": {
            "default_projects_root_dir": default_root,
            "default_stirrup_dia_mm": 6,
            "default_beam_main_dia_mm": 16,
            "default_col_main_dia_mm": 16,
            "rebar_diameters_table": rebar_table,
        },
        "options": {
            "materials": dict(mat_defaults),
            "hollow_block_slab": dict(hb_defaults),
        },
    }
    fpath = _get_global_settings_file_path()
    if os.path.isfile(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                is_modern = str(saved.get("schema_version", "")).startswith("2.")
                if "default_projects_root_folder" in saved:
                    defaults["default_projects_root_folder"] = saved["default_projects_root_folder"]
                if "default_stirrup_bar_mm" in saved:
                    defaults["default_stirrup_bar_mm"] = int(saved["default_stirrup_bar_mm"])
                if "default_main_bar_mm" in saved:
                    defaults["default_main_bar_mm"] = int(saved["default_main_bar_mm"])
                if isinstance(saved.get("rebar_diameters_table"), list):
                    defaults["rebar_diameters_table"] = _normalize_rebar_table(saved["rebar_diameters_table"])
                if isinstance(saved.get("materials_and_soil"), dict):
                    defaults["materials_and_soil"].update(saved["materials_and_soil"])
                if isinstance(saved.get("hollow_block_slab_data"), dict):
                    defaults["hollow_block_slab_data"].update(saved["hollow_block_slab_data"])
                if isinstance(saved.get("startup_defaults"), dict):
                    defaults["startup_defaults"].update(saved["startup_defaults"])
                    if isinstance(saved["startup_defaults"].get("rebar_diameters_table"), list):
                        defaults["rebar_diameters_table"] = _normalize_rebar_table(saved["startup_defaults"]["rebar_diameters_table"])
                if isinstance(saved.get("options"), dict):
                    if isinstance(saved["options"].get("materials"), dict):
                        defaults["materials_and_soil"].update(saved["options"]["materials"])
                    if isinstance(saved["options"].get("hollow_block_slab"), dict):
                        defaults["hollow_block_slab_data"].update(saved["options"]["hollow_block_slab"])

                if not is_modern:
                    defaults["materials_and_soil"]["concrete_unit_weight_kn_m3"] = 24.0
                    defaults["materials_and_soil"]["gamma_c_kn_m3"] = 24.0
                    defaults["hollow_block_slab_data"]["finish_load_kn_m2"] = 1.5
                    defaults["hollow_block_slab_data"]["finishing_load_kpa"] = 1.5
                    defaults["hollow_block_slab_data"]["top_compression_slab_cm"] = 10.0
                    defaults["hollow_block_slab_data"]["top_flange_cm"] = 10.0
                    defaults["hollow_block_slab_data"]["block_height_cm"] = 20.0
                    defaults["hollow_block_slab_data"]["slab_factored_wu_kpa"] = 11.71
                    defaults["hollow_block_slab_data"]["default_wall_load_kn_m"] = 10.50

                defaults["startup_defaults"]["rebar_diameters_table"] = defaults["rebar_diameters_table"]
                defaults["options"]["materials"] = dict(defaults["materials_and_soil"])
                defaults["options"]["hollow_block_slab"] = dict(defaults["hollow_block_slab_data"])
        except Exception:
            pass
    return defaults


def save_studio_global_settings(settings: Dict[str, Any]) -> str:
    settings["schema_version"] = "2.5.0"
    if "rebar_diameters_table" in settings:
        settings["rebar_diameters_table"] = _normalize_rebar_table(settings["rebar_diameters_table"])
    fpath = _get_global_settings_file_path()
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass
    return fpath


STANDARD_LAYERS = [
    ("00-XD-EDGE", 4, "Continuous"),
    ("00-XD-OPEN", 6, "Continuous"),
    ("00-XD-COL", 1, "Continuous"),
    ("00-XD-BEAM-HID", 2, "DASHED"),
    ("00-XD-BEAM-DROP", 3, "Continuous"),
    ("00-XD-SLAB", 40, "Continuous"),
    ("00-XD-TAG-COL", 3, "Continuous"),
    ("00-XD-TAG-BEAM", 30, "Continuous"),
    ("00-XD-DIM", 7, "Continuous"),
    ("00-XD-ARCH-REF", 8, "Continuous"),
]


def validate_project_name(name: str) -> Tuple[bool, str, str, str]:
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


def resolve_standard_hordi_block_and_topping_cm(
    slab_thickness_cm: float,
    requested_block_height_cm: Optional[float] = None,
) -> Tuple[float, float]:
    h_cm = max(18.0, float(slab_thickness_cm))
    if requested_block_height_cm is not None and round(float(requested_block_height_cm), 1) in (16.0, 20.0):
        cand_blk = round(float(requested_block_height_cm), 1)
        if h_cm - cand_blk >= 4.0:
            return cand_blk, round(h_cm - cand_blk, 2)
    block_h_cm = 20.0 if h_cm >= 25.0 else 16.0
    hs_cm = round(max(4.0, h_cm - block_h_cm), 2)
    return block_h_cm, hs_cm


def compute_hollow_block_parameters(
    slab_thickness_cm: Any = 30.0,
    rib_width_cm: float = 15.0,
    block_width_cm: float = 40.0,
    block_length_cm: float = 25.0,
    block_weight_kn: float = 0.10,
    finish_load_kn_m2: float = 1.5,
    live_load_kn_m2: float = 2.0,
    top_flange_cm: Optional[float] = None,
    rib_bw2_cm: Optional[float] = None,
    gamma_c_kn_m3: float = 24.0,
    dl_factor: float = 1.4,
    ll_factor: float = 1.7,
    block_height_cm: Optional[float] = None,
) -> Dict[str, float]:
    req_blk_h = block_height_cm
    if isinstance(slab_thickness_cm, dict):
        d_in = slab_thickness_cm
        slab_thickness_cm = float(d_in.get("total_slab_thickness_cm", d_in.get("slab_thickness_cm", d_in.get("total_thickness_cm", 30.0))))
        rib_width_cm = float(d_in.get("rib_width_cm", rib_width_cm))
        block_width_cm = float(d_in.get("block_width_cm", block_width_cm))
        block_length_cm = float(d_in.get("block_length_cm", block_length_cm))
        block_weight_kn = float(d_in.get("block_weight_kn", block_weight_kn))
        finish_load_kn_m2 = float(d_in.get("finish_load_kn_m2", d_in.get("finishing_load_kpa", finish_load_kn_m2)))
        live_load_kn_m2 = float(d_in.get("live_load_kn_m2", d_in.get("live_load_kpa", live_load_kn_m2)))
        if "block_height_cm" in d_in and round(float(d_in["block_height_cm"]), 1) in (16.0, 20.0):
            req_blk_h = float(d_in["block_height_cm"])
        gamma_c_kn_m3 = float(d_in.get("gamma_c_kn_m3", d_in.get("concrete_unit_weight_kn_m3", gamma_c_kn_m3)))

    h_cm = max(18.0, float(slab_thickness_cm))
    block_height_cm_val, hs_cm = resolve_standard_hordi_block_and_topping_cm(h_cm, req_blk_h)

    s_cm = max(20.0, float(block_width_cm))
    bw1_cm = max(8.0, float(rib_width_cm))
    bw2_cm = max(8.0, float(rib_bw2_cm if rib_bw2_cm is not None else bw1_cm))
    rib_spacing_cm = round(s_cm + bw1_cm, 2)

    hs_m = hs_cm / 100.0
    blk_h_m = block_height_cm_val / 100.0
    s_m = s_cm / 100.0
    bw1_m = bw1_cm / 100.0
    bw2_m = bw2_cm / 100.0
    b_space_m = s_m + bw1_m
    blk_len_m = max(0.10, float(block_length_cm) / 100.0)
    gamma_rc = max(18.0, float(gamma_c_kn_m3))

    topping_wt_rib = round(hs_m * b_space_m * gamma_rc, 4)
    rib_web_wt_rib = round(((bw1_m + bw2_m) / 2.0) * blk_h_m * gamma_rc, 4)
    blocks_per_m_rib = round(1.0 / blk_len_m, 3)
    block_wt_rib = round(blocks_per_m_rib * float(block_weight_kn), 4)
    finishing_wt_rib = round(float(finish_load_kn_m2) * b_space_m, 4)

    total_dl_rib = round(topping_wt_rib + rib_web_wt_rib + block_wt_rib + finishing_wt_rib, 4)
    factored_dl_rib = round(float(dl_factor) * total_dl_rib, 4)

    ll_rib = round(float(live_load_kn_m2) * b_space_m, 4)
    factored_ll_rib = round(float(ll_factor) * ll_rib, 4)

    wu_rib_kn_m = round(factored_dl_rib + factored_ll_rib, 4)
    wu_m2_kpa = round((factored_dl_rib + factored_ll_rib) / max(0.20, b_space_m), 2)

    blocks_per_m2 = (1.0 / b_space_m) * blocks_per_m_rib
    self_weight_kn_m2 = round((topping_wt_rib + rib_web_wt_rib + block_wt_rib) / b_space_m, 2)
    total_dead_kn_m2 = round(total_dl_rib / b_space_m, 2)
    total_service_kn_m2 = round(total_dead_kn_m2 + float(live_load_kn_m2), 2)

    return {
        "slab_thickness_cm": round(h_cm, 2),
        "total_slab_thickness_cm": round(h_cm, 2),
        "top_flange_cm": round(hs_cm, 2),
        "top_compression_slab_cm": round(hs_cm, 2),
        "block_height_cm": round(block_height_cm_val, 2),
        "block_width_cm": round(s_cm, 2),
        "block_length_cm": round(blk_len_m * 100.0, 2),
        "rib_width_cm": round(bw1_cm, 2),
        "rib_bw2_cm": round(bw2_cm, 2),
        "rib_spacing_cm": rib_spacing_cm,
        "gamma_c_kn_m3": round(gamma_rc, 2),
        "finish_load_kn_m2": round(float(finish_load_kn_m2), 2),
        "live_load_kn_m2": round(float(live_load_kn_m2), 2),
        "dl_factor": round(float(dl_factor), 2),
        "ll_factor": round(float(ll_factor), 2),
        "topping_wt_rib_kn_m": round(topping_wt_rib, 3),
        "rib_web_wt_rib_kn_m": round(rib_web_wt_rib, 3),
        "block_wt_rib_kn_m": round(block_wt_rib, 3),
        "finishing_wt_rib_kn_m": round(finishing_wt_rib, 3),
        "total_dl_rib_kn_m": round(total_dl_rib, 3),
        "factored_dl_rib_kn_m": round(factored_dl_rib, 4),
        "ll_rib_kn_m": round(ll_rib, 3),
        "factored_ll_rib_kn_m": round(factored_ll_rib, 3),
        "wu_rib_kn_m": round(wu_rib_kn_m, 2),
        "rib_factored_wu_kn_m": round(wu_rib_kn_m, 2),
        "wu_rib_exact_kn_m": wu_rib_kn_m,
        "blocks_per_m2": round(blocks_per_m2, 2),
        "self_weight_kn_m2": self_weight_kn_m2,
        "total_dead_kn_m2": total_dead_kn_m2,
        "total_service_kn_m2": total_service_kn_m2,
        "total_factored_wu_kn_m2": wu_m2_kpa,
        "area_factored_qu_kn_m2": wu_m2_kpa,
    }


compute_hollow_block_slab_loads = compute_hollow_block_parameters


def cleanup_unprefixed_duplicates(project_dir: str, clean_project_name: str) -> None:
    prefix = f"{clean_project_name}-"
    canonical_master_name = f"{clean_project_name}-00_Project_Master.xsd"
    for sub in ["", "CAD_Drawings", "Stories_Data"]:
        target_dir = os.path.join(project_dir, sub) if sub else project_dir
        if not os.path.isdir(target_dir):
            continue
        for fname in os.listdir(target_dir):
            full_p = os.path.join(target_dir, fname)
            if not os.path.isfile(full_p):
                continue
            if sub == "":
                if fname != canonical_master_name and fname.endswith((".json", ".xpert", ".xsd", ".dxf")):
                    try:
                        os.remove(full_p)
                    except OSError:
                        pass
            else:
                if fname.endswith((".dxf", ".json", ".xpert", ".xsd")) and not fname.startswith(prefix):
                    try:
                        os.remove(full_p)
                    except OSError:
                        pass


def load_studio_project_from_master_file(master_path: str) -> Dict[str, Any]:
    abs_path = os.path.abspath(master_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Master project file not found: {abs_path}")

    with open(abs_path, "r", encoding="utf-8") as f:
        master_payload = json.load(f)

    project_dir = os.path.dirname(abs_path)
    clean_name = master_payload.get("project_name", "Project")
    canonical_xsd = os.path.join(project_dir, f"{clean_name}-00_Project_Master{MASTER_FILE_EXT}")

    master_payload["studio_version"] = STUDIO_VERSION
    master_payload["project_dir"] = project_dir
    master_payload["master_file"] = canonical_xsd

    mats = master_payload.setdefault("materials_and_soil", {})
    if float(mats.get("gamma_c_kn_m3", 24.0)) == 25.0:
        mats["gamma_c_kn_m3"] = 24.0
    loads_def = master_payload.setdefault("loads_and_defaults", {})
    if abs(float(loads_def.get("finish_load_kn_m2", 1.5)) - 2.0) < 0.05:
        loads_def["finish_load_kn_m2"] = 1.5
    hordi_recalc = compute_hollow_block_parameters(
        slab_thickness_cm=float(loads_def.get("default_slab_thickness_cm", 30.0)),
        rib_width_cm=float(loads_def.get("rib_width_cm", 15.0)),
        finish_load_kn_m2=float(loads_def.get("finish_load_kn_m2", 1.5)),
        live_load_kn_m2=float(loads_def.get("live_load_kn_m2", 2.0)),
        top_flange_cm=10.0,
        gamma_c_kn_m3=float(mats.get("gamma_c_kn_m3", 24.0)),
    )
    loads_def["hollow_block_defaults"] = hordi_recalc

    stories_dir = os.path.join(project_dir, "Stories_Data")
    cad_dir = os.path.join(project_dir, "CAD_Drawings")

    for sm in master_payload.get("stories", []):
        sid = sm["story_id"]
        j_path = os.path.join(stories_dir, f"{clean_name}-{sid}.json")
        sm["json_file"] = j_path
        sm["dxf_file"] = os.path.join(cad_dir, f"{clean_name}-{sid}.dxf")
        if os.path.isfile(j_path):
            try:
                with open(j_path, "r", encoding="utf-8") as sf:
                    s_data = json.load(sf)
                hb_s = s_data.get("hollow_block", {})
                if isinstance(hb_s, dict) and abs(float(hb_s.get("finishing_load_kpa", 1.5)) - 2.0) < 0.05:
                    hb_s["finishing_load_kpa"] = 1.5
                if float(s_data.get("slab_factored_wu_kpa", 11.71)) in (10.0, 12.66) and not s_data.get("custom_slab_wu_override", False):
                    st_t = float(s_data.get("adopted_slab_thickness_cm", 30.0))
                    st_hordi = compute_hollow_block_parameters(
                        slab_thickness_cm=st_t if st_t >= 14.0 else 30.0,
                        rib_width_cm=float(loads_def.get("rib_width_cm", 15.0)),
                        finish_load_kn_m2=float(loads_def.get("finish_load_kn_m2", 1.5)),
                        live_load_kn_m2=float(loads_def.get("live_load_kn_m2", 2.0)),
                        top_flange_cm=10.0,
                        gamma_c_kn_m3=float(mats.get("gamma_c_kn_m3", 24.0)),
                    )
                    s_data["slab_factored_wu_kpa"] = st_hordi["total_factored_wu_kn_m2"]
                    s_data["hollow_block_params"] = dict(st_hordi)
                with open(j_path, "w", encoding="utf-8") as sf_out:
                    json.dump(s_data, sf_out, indent=2)
            except Exception:
                pass

    try:
        with open(canonical_xsd, "w", encoding="utf-8") as f:
            json.dump(master_payload, f, indent=2)
        cleanup_unprefixed_duplicates(project_dir, clean_name)
    except OSError:
        pass

    return master_payload


def initialize_studio_project(config: Dict[str, Any]) -> Dict[str, Any]:
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
    upper_mode = config.get("upper_floors_mode", "typical")
    include_penthouse = bool(config.get("include_penthouse", False))

    stories_meta: List[Dict[str, Any]] = []

    stories_meta.append({
        "story_id": "00_TieBeams",
        "story_label": "00 - Tie Beams & Grade Beams",
        "story_type": "tie_beams",
        "multiplier": 1,
        "height_m": foundation_depth,
        "wall_height_m": ground_h,
        "adopted_slab_thickness_cm": 0.0,
        "allow_hidden_beams": False,
        "allow_slabs": False,
        "status": "PENDING_GROUND_COLUMNS",
    })

    if include_basement:
        stories_meta.append({
            "story_id": "01_Basement_Slab",
            "story_label": "01 - Basement Floor Slab",
            "story_type": "basement",
            "multiplier": 1,
            "height_m": basement_h,
            "wall_height_m": ground_h,
            "adopted_slab_thickness_cm": 30.0,
            "allow_hidden_beams": True,
            "allow_slabs": True,
            "status": "PENDING_GROUND_COLUMNS",
        })

    ground_wall_h = upper_h if floors_above_ground > 0 else (penthouse_h if include_penthouse else 1.50)
    stories_meta.append({
        "story_id": "02_Ground_Floor",
        "story_label": "02 - Ground Floor Slab (Mandatory Start)",
        "story_type": "ground",
        "multiplier": 1,
        "height_m": ground_h,
        "wall_height_m": ground_wall_h,
        "adopted_slab_thickness_cm": 30.0,
        "allow_hidden_beams": True,
        "allow_slabs": True,
        "status": "ACTIVE_START",
    })

    next_code = 3
    if floors_above_ground > 0:
        if upper_mode == "typical" and floors_above_ground >= 1:
            stories_meta.append({
                "story_id": f"{next_code:02d}_Typical_Floor",
                "story_label": f"{next_code:02d} - Typical Upper Floor (x{floors_above_ground})",
                "story_type": "typical",
                "multiplier": floors_above_ground,
                "height_m": upper_h,
                "wall_height_m": upper_h if include_penthouse else 1.50,
                "adopted_slab_thickness_cm": 30.0,
                "allow_hidden_beams": True,
                "allow_slabs": True,
                "status": "PENDING_GROUND_COLUMNS",
            })
            next_code += 1
        else:
            for idx in range(floors_above_ground):
                is_last_upper = (idx == floors_above_ground - 1)
                u_wall_h = upper_h if (not is_last_upper or include_penthouse) else 1.50
                stories_meta.append({
                    "story_id": f"{next_code:02d}_Upper_Floor_{idx + 1}",
                    "story_label": f"{next_code:02d} - Upper Floor #{idx + 1}",
                    "story_type": "standard",
                    "multiplier": 1,
                    "height_m": upper_h,
                    "wall_height_m": u_wall_h,
                    "adopted_slab_thickness_cm": 30.0,
                    "allow_hidden_beams": True,
                    "allow_slabs": True,
                    "status": "PENDING_GROUND_COLUMNS",
                })
                next_code += 1

    if include_penthouse:
        stories_meta.append({
            "story_id": f"{next_code:02d}_Penthouse_Floor",
            "story_label": f"{next_code:02d} - Roof Annex / Penthouse Slab",
            "story_type": "penthouse",
            "multiplier": 1,
            "height_m": penthouse_h,
            "wall_height_m": 1.50,
            "adopted_slab_thickness_cm": 30.0,
            "allow_hidden_beams": True,
            "allow_slabs": True,
            "status": "PENDING_GROUND_COLUMNS",
        })

    hordi_defaults = compute_hollow_block_parameters(
        slab_thickness_cm=30.0,
        rib_width_cm=float(config.get("rib_width_cm", 15.0)),
        finish_load_kn_m2=float(config.get("finish_load_kn_m2", 1.5)),
        live_load_kn_m2=float(config.get("live_load_kn_m2", 2.0)),
        top_flange_cm=float(config.get("top_flange_cm", 10.0)),
        gamma_c_kn_m3=float(config.get("gamma_c_kn_m3", 24.0)),
    )

    master_xsd_file = os.path.join(project_dir, f"{clean_name}-00_Project_Master{MASTER_FILE_EXT}")

    master_payload = {
        "studio_version": STUDIO_VERSION,
        "file_format": "XPERT_STRUCTURAL_PROJECT_MASTER",
        "project_uuid": f"XPERT-{uuid.uuid4().hex[:8].upper()}",
        "project_name": clean_name,
        "folder_name": folder_name,
        "project_dir": project_dir,
        "master_file": master_xsd_file,
        "mandatory_start_story_id": "02_Ground_Floor",
        "column_overrides": {},
        "materials_and_soil": {
            "fc_mpa": float(config.get("fc_mpa", 20.0)),
            "fy_mpa": float(config.get("fy_mpa", 350.0)),
            "gamma_c_kn_m3": float(config.get("gamma_c_kn_m3", 24.0)),
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
            "finish_load_kn_m2": float(config.get("finish_load_kn_m2", 1.5)),
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

        st_h = float(sm["height_m"])
        st_wall_h = float(sm.get("wall_height_m", st_h))
        st_wall_w = round(2.5 * st_wall_h * 1.4, 2)

        sm_entry = dict(sm)
        sm_entry["wall_height_m"] = st_wall_h
        sm_entry["default_wall_load_kn_m"] = st_wall_w
        sm_entry["json_file"] = json_path
        sm_entry["dxf_file"] = dxf_path
        master_payload["stories"].append(sm_entry)

        story_data = {
            "project_name": clean_name,
            "story_id": sid,
            "story_label": sm["story_label"],
            "story_type": sm["story_type"],
            "multiplier": sm["multiplier"],
            "height_m": st_h,
            "wall_height_m": st_wall_h,
            "adopted_slab_thickness_cm": sm["adopted_slab_thickness_cm"],
            "slab_factored_wu_kpa": hordi_defaults["total_factored_wu_kn_m2"],
            "default_wall_thickness_cm": 20.0,
            "default_wall_load_kn_m": st_wall_w,
            "hollow_block_params": dict(hordi_defaults),
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

    takedown_file = os.path.join(stories_dir, f"{clean_name}-Columns_Load_Takedown.json")
    foundations_file = os.path.join(stories_dir, f"{clean_name}-Foundations_Design.json")
    boq_file = os.path.join(stories_dir, f"{clean_name}-BOQ_Quantities.json")
    foundations_dxf = os.path.join(cad_dir, f"{clean_name}-Foundations_And_Axes.dxf")

    master_payload["stories_meta"] = master_payload["stories"]
    with open(master_xsd_file, "w", encoding="utf-8") as f:
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
    set_active_project_log_dir(project_dir)
    log_studio_event(
        "PROJECT_INIT",
        f"Initialized project Stractural-{clean_name} with {len(stories_meta)} stories",
        {"project_dir": project_dir, "master_file": master_xsd_file},
    )
    return master_payload


def compute_smart_beam_tag_position(
    beam: Dict[str, Any],
    columns: List[Dict[str, Any]],
    placed_positions: List[Tuple[float, float]],
    all_beams: Optional[List[Dict[str, Any]]] = None,
    slabs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[float, float, float]:
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
    nx = -uy
    ny = ux

    is_vertical = abs(dy) > abs(dx)
    rot_deg = 90.0 if is_vertical else 0.0
    perp_offset = (b_width / 2.0) + 0.24

    junction_stations: List[float] = [0.0, length]
    for col in columns:
        if not col.get("active", True):
            continue
        cx, cy = float(col.get("x", 0.0)), float(col.get("y", 0.0))
        proj = (cx - sx) * ux + (cy - sy) * uy
        perp = abs((cx - sx) * nx + (cy - sy) * ny)
        if perp <= b_width / 2.0 + 0.35 and -0.25 <= proj <= length + 0.25:
            junction_stations.append(min(max(0.0, proj), length))

    if all_beams:
        for ob in all_beams:
            if ob.get("id") == beam.get("id"):
                continue
            osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
            oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
            ob_vert = abs(oey - osy) > abs(oex - osx)
            if ob_vert != is_vertical:
                if is_vertical:
                    if min(osx, oex) - 0.30 <= sx <= max(osx, oex) + 0.30 and min(sy, ey) - 0.30 <= osy <= max(sy, ey) + 0.30:
                        junction_stations.append(min(max(0.0, abs(osy - sy)), length))
                else:
                    if min(sx, ex) - 0.30 <= osx <= max(sx, ex) + 0.30 and min(osy, oey) - 0.30 <= sy <= max(osy, oey) + 0.30:
                        junction_stations.append(min(max(0.0, abs(osx - sx)), length))

    junction_stations = sorted(set(round(s, 2) for s in junction_stations))
    cand_stations: List[float] = []
    segs = [
        (junction_stations[i], junction_stations[i + 1])
        for i in range(len(junction_stations) - 1)
        if (junction_stations[i + 1] - junction_stations[i]) >= 0.65
    ]
    segs.sort(key=lambda ab: ab[1] - ab[0], reverse=True)
    for a, b in segs:
        mid = (a + b) * 0.50
        cand_stations.extend([mid, a + (b - a) * 0.35, a + (b - a) * 0.65])
    if not cand_stations:
        cand_stations = [length * 0.50, length * 0.32, length * 0.68]

    obstacles: List[Tuple[float, float, float]] = []
    for col in columns:
        if col.get("active", True):
            obstacles.append((float(col.get("x", 0.0)), float(col.get("y", 0.0)), 0.52))
    if slabs:
        for slb in slabs:
            if "min_x" in slb:
                cmin_x = float(slb.get("clear_min_x", slb["min_x"]))
                cmax_x = float(slb.get("clear_max_x", slb["max_x"]))
                cmin_y = float(slb.get("clear_min_y", slb["min_y"]))
                cmax_y = float(slb.get("clear_max_y", slb["max_y"]))
                obstacles.append(((cmin_x + cmax_x) / 2.0, (cmin_y + cmax_y) / 2.0, 0.82))
    for px, py in placed_positions:
        obstacles.append((float(px), float(py), 0.55))

    best_pt = (sx + ux * cand_stations[0] + nx * perp_offset, sy + uy * cand_stations[0] + ny * perp_offset)
    best_score = -1e9

    for side_sign in (1.0, -1.0):
        for st in cand_stations:
            tx = sx + ux * st + nx * (perp_offset * side_sign)
            ty = sy + uy * st + ny * (perp_offset * side_sign)
            min_clearance = 99.0
            for ox, oy, req_d in obstacles:
                d = ((tx - ox) ** 2 + (ty - oy) ** 2) ** 0.5
                clearance_margin = d - req_d
                if clearance_margin < min_clearance:
                    min_clearance = clearance_margin
            side_bonus = 0.08 if side_sign > 0 else 0.0
            score = min(min_clearance, 0.60) + side_bonus
            if min_clearance >= 0.0 and score > best_score:
                best_score = score
                best_pt = (tx, ty)
                if side_sign > 0 and min_clearance >= 0.25:
                    placed_positions.append((round(tx, 3), round(ty, 3)))
                    return round(tx, 3), round(ty, 3), rot_deg
            elif score > best_score:
                best_score = score
                best_pt = (tx, ty)

    placed_positions.append((round(best_pt[0], 3), round(best_pt[1], 3)))
    return round(best_pt[0], 3), round(best_pt[1], 3), rot_deg


def _write_ascii_dxf_fallback(story_data: Dict[str, Any], dxf_path: str) -> None:
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
        b, h = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
        cid = str(col["id"]) + (" (2H)" if col.get("double_height") else "")
        tag_x = round(cx + b / 2.0 + 0.12, 3)
        tag_y = round(cy + h / 2.0 + 0.12, 3)
        placed_tags.append((tag_x, tag_y))
        lines.extend([
            "0", "TEXT", "8", "00-XD-TAG-COL", "62", "3",
            "10", str(tag_x), "20", str(tag_y), "30", "0.0",
            "40", "0.22", "1", cid,
        ])

    for op in story_data.get("openings", []):
        pts = op.get("polygon") or [
            [float(op.get("min_x", 0.0)), float(op.get("min_y", 0.0))],
            [float(op.get("max_x", 0.0)), float(op.get("min_y", 0.0))],
            [float(op.get("max_x", 0.0)), float(op.get("max_y", 0.0))],
            [float(op.get("min_x", 0.0)), float(op.get("max_y", 0.0))],
        ]
        for k_p in range(len(pts)):
            p1 = pts[k_p]
            p2 = pts[(k_p + 1) % len(pts)]
            lines.extend([
                "0", "LINE", "8", "00-XD-OPEN", "62", "6",
                "10", str(p1[0]), "20", str(p1[1]), "30", "0.0",
                "11", str(p2[0]), "21", str(p2[1]), "31", "0.0",
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
    if ezdxf is None:
        _write_ascii_dxf_fallback(story_data, dxf_path)
        return

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6  # Meters

    if "XD_TAG_STYLE" not in doc.styles:
        doc.styles.add("XD_TAG_STYLE", font="arial.ttf")

    for layer_name, aci_color, _ltype in STANDARD_LAYERS:
        if layer_name not in doc.layers:
            doc.layers.add(name=layer_name, color=aci_color)

    msp = doc.modelspace()

    edge_pts = story_data.get("slab_edge_polygon", [])
    if len(edge_pts) >= 3:
        pts_2d = [(float(p[0]), float(p[1])) for p in edge_pts]
        poly = msp.add_lwpolyline(pts_2d, dxfattribs={"layer": "00-XD-EDGE"})
        poly.closed = True

    placed_tags: List[Tuple[float, float]] = []
    columns = story_data.get("columns", [])
    for col in columns:
        if not col.get("active", True):
            continue
        cx = float(col["x"])
        cy = float(col["y"])
        b = float(col.get("b_m", 0.20))
        h = float(col.get("h_m", 0.40))
        is_neck = bool(col.get("neck") or col.get("is_neck_column"))
        cid = str(col["id"]) + (" (2H)" if col.get("double_height") else "")

        corners = [
            (cx - b / 2.0, cy - h / 2.0),
            (cx + b / 2.0, cy - h / 2.0),
            (cx + b / 2.0, cy + h / 2.0),
            (cx - b / 2.0, cy + h / 2.0),
        ]
        cpoly = msp.add_lwpolyline(corners, dxfattribs={"layer": "00-XD-COL", "color": 4 if is_neck else 1})
        cpoly.closed = True

        tag_x = round(cx + b / 2.0 + 0.12, 3)
        tag_y = round(cy + h / 2.0 + 0.12, 3)
        placed_tags.append((tag_x, tag_y))
        msp.add_text(
            cid,
            dxfattribs={
                "layer": "00-XD-TAG-COL",
                "style": "XD_TAG_STYLE",
                "height": 0.22,
                "color": 4 if is_neck else 3,
                "insert": (tag_x, tag_y, 0.0),
            },
        )

    for op in story_data.get("openings", []):
        pts = op.get("polygon") or [
            [float(op.get("min_x", 0.0)), float(op.get("min_y", 0.0))],
            [float(op.get("max_x", 0.0)), float(op.get("min_y", 0.0))],
            [float(op.get("max_x", 0.0)), float(op.get("max_y", 0.0))],
            [float(op.get("min_x", 0.0)), float(op.get("max_y", 0.0))],
        ]
        if len(pts) >= 3:
            opoly = msp.add_lwpolyline([(float(p[0]), float(p[1])) for p in pts], dxfattribs={"layer": "00-XD-OPEN", "color": 6})
            opoly.closed = True
            omin_x, omax_x = float(op.get("min_x", 0.0)), float(op.get("max_x", 0.0))
            omin_y, omax_y = float(op.get("min_y", 0.0)), float(op.get("max_y", 0.0))
            msp.add_line((omin_x, omin_y), (omax_x, omax_y), dxfattribs={"layer": "00-XD-OPEN", "color": 6})
            msp.add_line((omin_x, omax_y), (omax_x, omin_y), dxfattribs={"layer": "00-XD-OPEN", "color": 6})

    beams = story_data.get("beams", [])
    for bm in beams:
        sx = float(bm.get("start_x", 0.0))
        sy = float(bm.get("start_y", 0.0))
        ex = float(bm.get("end_x", 5.0))
        ey = float(bm.get("end_y", 0.0))
        b_kind = bm.get("beam_kind", "hidden")
        b_width = float(bm.get("width_m", 0.40 if b_kind == "hidden" else 0.20))
        layer = "00-XD-BEAM-HID" if b_kind == "hidden" else "00-XD-BEAM-DROP"
        color = 2 if b_kind == "hidden" else 3

        msp.add_lwpolyline(
            [(sx, sy), (ex, ey)],
            dxfattribs={"layer": layer, "color": color, "const_width": b_width},
        )

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


def set_column_story_override(
    master_payload: Dict[str, Any],
    col_id: str,
    story_id: str,
    active: Optional[bool] = None,
    b_m: Optional[float] = None,
    h_m: Optional[float] = None,
) -> Dict[str, Any]:
    ov = master_payload.setdefault("column_overrides", {}).setdefault(str(col_id), {}).setdefault(str(story_id), {})
    if active is not None:
        ov["active"] = bool(active)
    if b_m is not None:
        ov["b_m"] = float(b_m)
    if h_m is not None:
        ov["h_m"] = float(h_m)
    return master_payload


def set_column_continuity_cascade(
    master_payload: Dict[str, Any],
    col_id: str,
    story_id: str,
    active: bool,
    upper_story_ids: List[str],
) -> Tuple[bool, str]:
    ov = master_payload.setdefault("column_overrides", {}).setdefault(str(col_id), {})
    if story_id not in upper_story_ids:
        return False, "Story is not an upper story."
    idx = upper_story_ids.index(story_id)
    if active:
        for lower in upper_story_ids[:idx]:
            if ov.get(lower, {}).get("active", True) is False:
                return False, f"Cannot continue {col_id} at {story_id}: it is discontinued at lower story {lower}."
        ov.setdefault(story_id, {})["active"] = True
        return True, f"Column {col_id} continued at {story_id}."
    for sid in upper_story_ids[idx:]:
        ov.setdefault(sid, {})["active"] = False
    return True, f"Column {col_id} discontinued at {story_id} and all higher stories."


def propagate_ground_columns_to_all_stories(
    master_payload: Dict[str, Any],
    ground_columns: List[Dict[str, Any]],
) -> None:
    all_stories = (master_payload or {}).get("stories", [])
    story_ids = [str(s.get("story_id")) for s in all_stories if s.get("story_id")]
    ov_all = (master_payload or {}).get("column_overrides", {})

    regular_ground_cols = [
        dict(gc) for gc in (ground_columns or [])
        if not (gc.get("neck") or gc.get("is_neck_column"))
    ]

    for s_entry in all_stories:
        sid = str(s_entry.get("story_id", ""))
        jpath = s_entry.get("json_file")
        dpath = s_entry.get("dxf_file")
        if not jpath or not os.path.isfile(jpath):
            continue

        with open(jpath, "r", encoding="utf-8") as f:
            sdata = json.load(f)

        local_necks = []
        if sid == "00_TieBeams":
            local_necks = [
                c for c in sdata.get("columns", [])
                if c.get("neck") or c.get("is_neck_column")
            ]

        updated_cols: List[Dict[str, Any]] = []
        for gc in regular_ground_cols:
            c_copy = dict(gc)
            cid = str(c_copy.get("id", ""))
            vis_map: Dict[str, bool] = {}
            for other_sid in story_ids:
                if other_sid in ("02_Ground_Floor", "00_TieBeams", "01_Basement_Slab"):
                    vis_map[other_sid] = True
                else:
                    vis_map[other_sid] = bool(ov_all.get(cid, {}).get(other_sid, {}).get("active", True))

            c_copy["visible_in_story"] = vis_map
            c_copy["active"] = bool(vis_map.get(sid, True))

            ov = ov_all.get(cid, {}).get(sid)
            if isinstance(ov, dict):
                if "b_m" in ov:
                    c_copy["b_m"] = float(ov["b_m"])
                if "h_m" in ov:
                    c_copy["h_m"] = float(ov["h_m"])

            updated_cols.append(c_copy)

        if sid == "00_TieBeams":
            existing_ids = {str(c.get("id")) for c in updated_cols}
            for nc in local_necks:
                if str(nc.get("id")) not in existing_ids:
                    nc["visible_in_story"] = {other_sid: (other_sid == "00_TieBeams") for other_sid in story_ids}
                    updated_cols.append(nc)

        sdata["columns"] = updated_cols
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(sdata, f, indent=2)
        if dpath:
            sync_story_to_dxf(sdata, dpath)


def import_arch_dxf_underlay(dxf_file_path: str) -> Dict[str, Any]:
    if not os.path.isfile(dxf_file_path):
        raise FileNotFoundError(f"Architectural DXF file not found: {dxf_file_path}")

    segments: List[List[float]] = []
    closed_rects: List[Dict[str, float]] = []
    circles: List[Dict[str, float]] = []

    if ezdxf is not None:
        doc = ezdxf.readfile(dxf_file_path)
        msp = doc.modelspace()
        for ent in msp:
            etype = ent.dxftype()
            if etype == "LINE":
                s = ent.dxf.start
                e = ent.dxf.end
                segments.append([round(float(s.x), 3), round(float(s.y), 3), round(float(e.x), 3), round(float(e.y), 3)])
            elif etype in ("CIRCLE", "ARC"):
                circles.append({
                    "x": round(float(ent.dxf.center.x), 3),
                    "y": round(float(ent.dxf.center.y), 3),
                    "r": round(float(ent.dxf.radius), 3),
                })
            elif etype in ("LWPOLYLINE", "POLYLINE"):
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
        "circles": circles,
    }
