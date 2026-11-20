"""
Xpert Structural Design Studio (v1.0.0)
Module: xpert_structural_engine.py
Lead Engineer: Eng. Yousef Mohammed Keshlaf

Core Structural Analysis, Optimization & ACI 318 Design Engine:
1. Automatic Per-Story ACI 318 Deflection Thickness Evaluator & Smart Drop-Beam
   Optimization Advisor.
2. Topological Beam Dependency Sort & Eng. Yousef's Analytical Slope-Deflection Solver
   with Face-of-Support Shear/Moment Extraction.
3. Multi-Story Column Load Takedown, End-Moment Transfer & 4-Way Framing Connectivity
   (North, South, East, West at Upper and Lower Story Joints).
4. ACI 318 Flexural & Shear Beam Design, Column P-M Interaction Diagram Generator,
   SPColumn (.cti) Exporter, Foundation Designer, and Printable Calculation Report.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple

try:
    from xpert_project_io import log_studio_event as _io_log_studio_event
except ImportError:
    def _io_log_studio_event(*args: Any, **kwargs: Any) -> None:
        pass


def _log_eng(category: str, message: str, details: Any = None, level: str = "INFO") -> None:
    _io_log_studio_event(category, message, details, level=level)


def _snap_drop_depth_m(depth_m: float, min_h_m: float = 0.40) -> float:
    """
    Ensures Drop Beam depths are clean multiples of 100 mm (0.40, 0.50, 0.60, ...),
    eliminating legacy non-standard heights such as 0.51 m (510 mm).
    """
    h_mm = round(float(depth_m) * 1000.0)
    min_mm_raw = max(400, round(float(min_h_m) * 1000.0))
    rem_min = min_mm_raw % 100
    min_mm = min_mm_raw if rem_min == 0 else ((min_mm_raw // 100) * 100 if rem_min <= 20 else ((min_mm_raw // 100) + 1) * 100)
    min_mm = max(400, min_mm)

    rem = h_mm % 100
    if rem == 0:
        snapped = h_mm
    elif rem <= 20:
        snapped = (h_mm // 100) * 100
    else:
        snapped = ((h_mm // 100) + 1) * 100
    return round(max(min_mm, snapped) / 1000.0, 3)


def get_aci_deflection_divisor(continuity_case: str) -> float:
    if continuity_case == "simply_supported":
        return 16.0
    if continuity_case == "one_end_continuous":
        return 18.5
    if continuity_case == "both_ends_continuous":
        return 21.0
    if continuity_case == "cantilever":
        return 8.0
    return 16.0


def evaluate_story_thickness_and_optimization(
    story_data: Dict[str, Any],
    fy_mpa: float = 350.0,
) -> Dict[str, Any]:
    """
    Evaluates minimum required slab & hidden-beam thickness per ACI 318 in the background.
    - Returns '-- (Awaiting CAD Data)' if no beams or slabs exist yet.
    - Detects if a single Hidden Beam governs t_req > 30 cm while the rest of the floor
      requires <= 30 cm, triggering the Smart Drop-Beam Optimization Suggestion.
    """
    beams = story_data.get("beams", [])
    slabs = story_data.get("slabs", [])
    story_type = story_data.get("story_type", "ground")

    if story_type == "tie_beams":
        return {
            "has_data": False,
            "calculated_min_thickness_cm": 0.0,
            "badge_text": "0.0 cm (Tie-Beams Level)",
            "governing_member": "Tie-Beams Story (No Slab — Drop Grade Beams Only)",
            "smart_optimization": None,
        }

    if len(beams) == 0 and len(slabs) == 0:
        return {
            "has_data": False,
            "calculated_min_thickness_cm": 0.0,
            "badge_text": "-- (Awaiting CAD Data)",
            "governing_member": "No beams or slabs drawn yet. Use the left CAD toolbar to model elements.",
            "smart_optimization": None,
        }

    fy_mod = 0.4 + (fy_mpa / 700.0)
    slab_reqs: List[Tuple[float, str]] = []
    hidden_beam_reqs: List[Tuple[float, str, str, float]] = []  # (req_cm, beam_id, desc, ln_m)

    for slb in slabs:
        sid = slb.get("id", "S1")
        axis_l = float(slb.get("axis_span_m", 4.0))
        lw = float(slb.get("left_support_w_m", 0.25))
        rw = float(slb.get("right_support_w_m", 0.25))
        is_cant = bool(slb.get("is_cantilever", False))
        conn_cant = bool(slb.get("connected_to_cantilever", False))
        ln = max(0.2, axis_l - lw / 2.0 - (0.0 if is_cant else rw / 2.0))
        cont = "cantilever" if is_cant else ("one_end_continuous" if conn_cant else "simply_supported")
        div = get_aci_deflection_divisor(cont)
        raw_cm = round((ln * 100.0 / div) * fy_mod, 2)
        req_cm = float(math.ceil(raw_cm - 1e-6))
        slab_reqs.append((req_cm, f"Slab Rib {sid} (Ln = {ln:.2f} m, L/{div:g} = {raw_cm:.1f} -> {req_cm:.0f} cm)"))

    for bm in beams:
        if bm.get("beam_kind", "hidden") != "hidden":
            continue
        bid = str(bm.get("id", "B1"))
        spans = bm.get("spans", [4.5])
        supports = bm.get("supports", [])
        c_left = float(bm.get("cantilever_left_m", 0.0))
        c_right = float(bm.get("cantilever_right_m", 0.0))
        ns = len(spans)

        for idx, sp_len in enumerate(spans):
            lw = float(supports[idx].get("width_m", 0.25)) if idx < len(supports) else 0.25
            rw = float(supports[idx + 1].get("width_m", 0.25)) if (idx + 1) < len(supports) else 0.25
            ln = max(0.2, float(sp_len) - lw / 2.0 - rw / 2.0)
            cont_l = idx > 0 or c_left > 0.01
            cont_r = idx < (ns - 1) or c_right > 0.01
            if cont_l and cont_r:
                cont = "both_ends_continuous"
            elif cont_l or cont_r:
                cont = "one_end_continuous"
            else:
                cont = "simply_supported"
            div = get_aci_deflection_divisor(cont)
            raw_cm = round((ln * 100.0 / div) * fy_mod, 2)
            req_cm = float(math.ceil(raw_cm - 1e-6))
            hidden_beam_reqs.append(
                (req_cm, bid, f"Hidden Beam {bid} (Span {idx + 1}, Ln = {ln:.2f} m, L/{div:g} = {raw_cm:.1f} -> {req_cm:.0f} cm)", ln)
            )

    all_candidates: List[Tuple[float, str]] = list(slab_reqs) + [(r[0], r[2]) for r in hidden_beam_reqs]
    if not all_candidates:
        return {
            "has_data": False,
            "calculated_min_thickness_cm": 0.0,
            "badge_text": "20 cm (Drop Beams Only)",
            "governing_member": "All beams are Drop Beams; minimum slab rib thickness applies.",
            "smart_optimization": None,
        }

    all_candidates.sort(key=lambda x: x[0], reverse=True)
    max_req_cm, gov_desc = all_candidates[0]
    max_req_cm = float(math.ceil(max_req_cm - 1e-6))

    # Check Smart Drop-Beam Optimization Rule:
    # If max_req_cm > 30.0 cm AND governed by a Hidden Beam while all slabs & other beams <= 30.0 cm
    smart_opt = None
    if max_req_cm > 30.0 and hidden_beam_reqs:
        hidden_beam_reqs.sort(key=lambda x: x[0], reverse=True)
        top_hb_cm, top_hb_id, top_hb_desc, top_hb_ln = hidden_beam_reqs[0]
        rest_max_cm = 0.0
        for req_cm, _ in slab_reqs:
            rest_max_cm = max(rest_max_cm, req_cm)
        for req_cm, bid, _, _ in hidden_beam_reqs:
            if bid != top_hb_id:
                rest_max_cm = max(rest_max_cm, req_cm)

        if top_hb_cm > 30.0 and rest_max_cm <= 30.0:
            smart_opt = {
                "beam_id": top_hb_id,
                "governing_ln_m": round(top_hb_ln, 2),
                "governing_req_cm": top_hb_cm,
                "rest_of_floor_req_cm": round(rest_max_cm, 0),
                "message": (
                    f"Optimization Suggestion: Hidden Beam {top_hb_id} (Ln = {top_hb_ln:.2f} m) "
                    f"governs the slab thickness at {top_hb_cm:.0f} cm (> 30 cm), whereas the rest "
                    f"of the floor requires only {rest_max_cm:.0f} cm (<= 30 cm). Converting {top_hb_id} "
                    f"to a Drop Beam (20x50 cm) keeps the entire slab thickness at 30 cm."
                ),
            }

    return {
        "has_data": True,
        "calculated_min_thickness_cm": max_req_cm,
        "badge_text": f"{max_req_cm:.0f} cm",
        "governing_member": gov_desc,
        "smart_optimization": smart_opt,
    }


def solve_continuous_beam_analytical(beam: Dict[str, Any], fc_mpa: float = 20.0, fy_mpa: float = 350.0) -> Dict[str, Any]:
    """
    Solves a multi-span continuous beam using Eng. Yousef's analytical Slope-Deflection
    algorithm and computes critical forces at both Support Centerlines and Faces of Support.
    Guaranteed crash-proof even for single-span, cantilever-only, or newly aligned/rotated beams.
    """
    raw_spans = [float(s) for s in beam.get("spans", []) if float(s) > 0.15]
    if not raw_spans:
        sx, sy = float(beam.get("start_x", 0.0)), float(beam.get("start_y", 0.0))
        ex, ey = float(beam.get("end_x", 4.0)), float(beam.get("end_y", 0.0))
        geom_len = round(max(0.50, math.hypot(ex - sx, ey - sy)), 3)
        raw_spans = [geom_len]
    spans = [max(0.35, round(s, 3)) for s in raw_spans]
    ns = len(spans)
    c_left = max(0.0, float(beam.get("cantilever_left_m", 0.0)))
    c_right = max(0.0, float(beam.get("cantilever_right_m", 0.0)))
    supports = beam.get("supports", [])
    loads = list(beam.get("loads", []))
    if not loads:
        default_w = 28.0 if beam.get("beam_kind") == "drop" else 34.0
        loads = [{"type": "dist", "x1": 0.0, "x2": round(c_left + sum(spans) + c_right, 3), "val": default_w}]

    L = [0.0] + spans
    span_starts = [c_left]
    for s_len in spans:
        span_starts.append(span_starts[-1] + s_len)
    right_start_x = span_starts[-1]

    CL_moment, CL_force = 0.0, 0.0
    CR_moment, CR_force = 0.0, 0.0
    W1: Dict[int, List[Dict[str, float]]] = {i: [] for i in range(1, ns + 1)}
    P1: Dict[int, List[Dict[str, float]]] = {i: [] for i in range(1, ns + 1)}

    for ld in loads:
        ltype = str(ld.get("type", "dist")).lower()
        val = float(ld.get("val", ld.get("mag", 0.0)))
        if ltype in ("dist", "d"):
            d_st = float(ld.get("x1", ld.get("start", 0.0)))
            d_en = float(ld.get("x2", ld.get("end", right_start_x + c_right)))
            if d_en <= d_st:
                d_en = right_start_x + c_right
            if c_left > 0 and d_st < c_left:
                ov_en = min(d_en, c_left)
                len_c = ov_en - d_st
                if len_c > 0:
                    fc_val = val * len_c
                    CL_force += fc_val
                    CL_moment += fc_val * (c_left - (d_st + len_c / 2.0))
            if c_right > 0 and d_en > right_start_x:
                ov_st = max(d_st, right_start_x)
                len_c = d_en - ov_st
                if len_c > 0:
                    fc_val = val * len_c
                    CR_force += fc_val
                    CR_moment += fc_val * (ov_st + len_c / 2.0 - right_start_x)
            for i in range(1, ns + 1):
                s_st, s_en = span_starts[i - 1], span_starts[i]
                ov_st, ov_en = max(d_st, s_st), min(d_en, s_en)
                if ov_st < ov_en:
                    W1[i].append({"w": val, "a": ov_st - s_st, "c": ov_en - ov_st})
        elif ltype in ("point", "p"):
            px = float(ld.get("x", ld.get("pos", 0.0)))
            if c_left > 0 and px < c_left:
                CL_force += val
                CL_moment += val * (c_left - px)
            elif c_right > 0 and px > right_start_x:
                CR_force += val
                CR_moment += val * (px - right_start_x)
            else:
                for i in range(1, ns + 1):
                    s_st, s_en = span_starts[i - 1], span_starts[i]
                    if s_st - 1e-6 <= px <= s_en + 1e-6:
                        P1[i].append({"p": val, "a": px - s_st})
                        break

    K2 = [0.0] * (ns + 2)
    for i in range(1, ns + 1):
        K2[i] = 1.0 / max(0.25, L[i])

    D = [0.0] * (ns + 3)
    E = [0.0] * (ns + 3)
    D[1] = 4.0 * K2[1]
    E[1] = 2.0 * K2[1]
    for i in range(2, ns + 1):
        D[i] = 4.0 * (K2[i - 1] + K2[i])
        E[i] = 2.0 * K2[i]
    D[ns + 1] = 4.0 * K2[ns]

    FL = [0.0] * (ns + 2)
    FR = [0.0] * (ns + 2)
    for i in range(1, ns + 1):
        Ll = max(0.25, L[i])
        for seg in W1[i]:
            ww = seg["w"] * seg["c"]
            ss = seg["a"] + seg["c"] / 2.0
            tt = Ll - ss
            cc = seg["c"]
            FL[i] += (ww * (ss * (tt ** 2) + ((ss - 2.0 * tt) * (cc ** 2)) / 12.0)) / (Ll ** 2)
            FR[i] += (ww * (tt * (ss ** 2) + ((tt - 2.0 * ss) * (cc ** 2)) / 12.0)) / (Ll ** 2)
        for pt in P1[i]:
            ww = pt["p"]
            ss = pt["a"]
            tt = Ll - ss
            FL[i] += (ww * (ss * (tt ** 2))) / (Ll ** 2)
            FR[i] += (ww * (tt * (ss ** 2))) / (Ll ** 2)

    F = [0.0] * (ns + 3)
    F[1] = CL_moment - FL[1]
    for i in range(2, ns + 1):
        F[i] = FR[i - 1] - FL[i]
    F[ns + 1] = FR[ns] - CR_moment

    R_rot = [0.0] * (ns + 3)
    d_temp = [0.0] * (ns + 3)
    f_temp = [0.0] * (ns + 3)
    d_temp[1] = max(1e-6, D[1])
    f_temp[1] = F[1]
    for i in range(2, ns + 2):
        m = E[i - 1] / max(1e-6, d_temp[i - 1])
        d_temp[i] = max(1e-6, D[i] - m * E[i - 1])
        f_temp[i] = F[i] - m * f_temp[i - 1]

    R_rot[ns + 1] = f_temp[ns + 1] / max(1e-6, d_temp[ns + 1])
    for i in range(ns, 0, -1):
        R_rot[i] = (f_temp[i] - E[i] * R_rot[i + 1]) / max(1e-6, d_temp[i])

    ML = [0.0] * (ns + 2)
    MR = [0.0] * (ns + 2)
    Mus = [0.0] * (ns + 3)
    for i in range(1, ns + 1):
        ML[i] = (4.0 * R_rot[i] + 2.0 * R_rot[i + 1]) * K2[i] + FL[i]
        MR[i] = (2.0 * R_rot[i] + 4.0 * R_rot[i + 1]) * K2[i] - FR[i]

    Mus[1] = -CL_moment
    for i in range(1, ns):
        Mus[i + 1] = MR[i]
    Mus[ns + 1] = -CR_moment

    RRR = [0.0] * (ns + 2)
    RRL = [0.0] * (ns + 2)
    RA = [0.0] * (ns + 3)
    for i in range(1, ns + 1):
        li_safe = max(0.25, L[i])
        rrr1 = -(ML[i] + MR[i]) / li_safe
        rrl1 = (ML[i] + MR[i]) / li_safe
        rrl2, rrr2, rrl3, rrr3 = 0.0, 0.0, 0.0, 0.0
        for seg in W1[i]:
            qw, dw = seg["w"], seg["c"]
            aw = seg["a"] + dw / 2.0
            bw = li_safe - aw
            rrl2 += (qw * dw * bw) / li_safe
            rrr2 += (qw * dw * aw) / li_safe
        for pt in P1[i]:
            qp, ap = pt["p"], pt["a"]
            bp = li_safe - ap
            rrr3 += (qp * ap) / li_safe
            rrl3 += (qp * bp) / li_safe
        RRR[i] = -(rrr1 + rrr2 + rrr3)
        RRL[i] = rrl1 + rrl2 + rrl3

    RA[1] = RRL[1] + CL_force
    for i in range(1, ns):
        RA[i + 1] = RRL[i + 1] - RRR[i]
    RA[ns + 1] = -RRR[ns] + CR_force

    total_len = max(0.35, c_left + sum(spans) + c_right)

    # Build station list with exact left/right discontinuity points (sx - 1e-6, sx + 1e-6)
    # at every support and point load so Shear Force Diagram (SFD) jumps are 100% vertical (90°)!
    raw_stations = [(idx / 400.0) * total_len for idx in range(401)]
    eps = 1e-6
    for sx in span_starts:
        if sx > eps:
            raw_stations.append(max(0.0, sx - eps))
        raw_stations.append(sx)
        if sx < total_len - eps:
            raw_stations.append(min(total_len, sx + eps))
    for ld in loads:
        if str(ld.get("type", "dist")).lower() in ("point", "p"):
            px = float(ld.get("x", ld.get("pos", 0.0)))
            if 0.0 <= px <= total_len:
                if px > eps:
                    raw_stations.append(max(0.0, px - eps))
                raw_stations.append(px)
                if px < total_len - eps:
                    raw_stations.append(min(total_len, px + eps))

    raw_stations.sort()
    filtered_stations: List[float] = []
    for st in raw_stations:
        if not filtered_stations or abs(st - filtered_stations[-1]) > 1e-9:
            filtered_stations.append(st)

    def eval_vm_at(xpos: float) -> Tuple[float, float]:
        vval, mval = 0.0, 0.0
        for s_i, sx in enumerate(span_starts):
            if xpos >= sx - 1e-9:
                vval += RA[s_i + 1]
                mval += RA[s_i + 1] * (xpos - sx)
        for ld in loads:
            ltype_c = str(ld.get("type", "dist")).lower()
            if ltype_c in ("point", "p"):
                lx = float(ld.get("x", ld.get("pos", 0.0)))
                lval = float(ld.get("val", ld.get("mag", 0.0)))
                if xpos >= lx - 1e-9:
                    vval -= lval
                    mval -= lval * (xpos - lx)
            else:
                lx1 = float(ld.get("x1", ld.get("start", 0.0)))
                lx2 = float(ld.get("x2", ld.get("end", total_len)))
                if lx2 <= lx1:
                    lx2 = total_len
                lval = float(ld.get("val", ld.get("mag", 0.0)))
                if xpos > lx1:
                    eff = min(xpos, lx2) - lx1
                    if eff > 0:
                        fw = lval * eff
                        vval -= fw
                        mval -= fw * (xpos - lx1 - eff / 2.0)
        return vval, mval

    x_full: List[float] = []
    v_full: List[float] = []
    m_full: List[float] = []
    for xpos in filtered_stations:
        vv, mv = eval_vm_at(xpos)
        x_full.append(round(xpos, 6))
        v_full.append(round(vv, 3))
        m_full.append(round(mv, 3))

    # Critical Forces at Support Centerlines AND Faces of Support
    support_critical_table = []
    for s_i, sx in enumerate(span_starts):
        sup_info = supports[s_i] if s_i < len(supports) else {"target_id": f"C{s_i+1}", "kind": "column", "width_m": 0.25}
        w_sup = float(sup_info.get("width_m", 0.25))
        x_face_left = max(0.0, sx - w_sup / 2.0)
        x_face_right = min(total_len, sx + w_sup / 2.0)

        _, m_fl = eval_vm_at(x_face_left)
        _, m_fr = eval_vm_at(x_face_right)
        m_face = min(m_fl, m_fr, Mus[s_i + 1] if w_sup <= 0.01 else 0.0)

        v_left_exact, _ = eval_vm_at(max(0.0, sx - 2e-6)) if sx > 1e-4 else (0.0, 0.0)
        v_right_exact, _ = eval_vm_at(min(total_len, sx + 2e-6)) if sx < total_len - 1e-4 else (0.0, 0.0)
        v_fl, _ = eval_vm_at(max(0.0, x_face_left - 2e-6)) if sx > 1e-4 else (0.0, 0.0)
        v_fr, _ = eval_vm_at(min(total_len, x_face_right + 2e-6)) if sx < total_len - 1e-4 else (0.0, 0.0)
        v_face = max(abs(v_fl), abs(v_fr), abs(v_left_exact), abs(v_right_exact))

        support_critical_table.append({
            "support_index": s_i + 1,
            "target_id": sup_info.get("target_id", f"C{s_i+1}"),
            "support_kind": sup_info.get("kind", "column"),
            "width_m": round(w_sup, 3),
            "depth_m": round(float(sup_info.get("depth_m", 0.40)), 3),
            "x_m": round(sx, 2),
            "reaction_ru_kn": round(RA[s_i + 1], 2),
            "reaction_kn": round(RA[s_i + 1], 2),
            "centerline_neg_mu_knm": round(Mus[s_i + 1], 2),
            "m_center_knm": round(Mus[s_i + 1], 2),
            "face_neg_mu_knm": round(m_face, 2),
            "face_vu_kn": round(v_face, 2),
            "v_left_kn": round(v_left_exact, 2),
            "v_right_kn": round(v_right_exact, 2),
        })

    span_positive_moments = []
    for s_i in range(ns):
        s_st, s_en = span_starts[s_i], span_starts[s_i + 1]
        # Evaluate strictly on interior stations of Span (s_st, s_en) plus left/right just-inside support faces
        # so an adjacent support shear jump (e.g. Span 2 reaction into Span 1 end) NEVER leaks into Span i!
        span_pts = [(x_full[k], m_full[k], v_full[k]) for k in range(len(x_full)) if (s_st + 1e-4) < x_full[k] < (s_en - 1e-4)]
        v_left_edge, _ = eval_vm_at(s_st + 2e-6)
        v_right_edge, _ = eval_vm_at(s_en - 2e-6)
        if span_pts:
            best_x, best_m, _ = max(span_pts, key=lambda t: t[1])
            v_max_span = max(abs(v_left_edge), abs(v_right_edge), max(abs(t[2]) for t in span_pts))
        else:
            best_x, best_m = s_st, 0.0
            v_max_span = max(abs(v_left_edge), abs(v_right_edge))
        v_start = v_left_edge
        v_end = v_right_edge
        span_positive_moments.append({
            "span_index": s_i + 1,
            "start_x_m": round(s_st, 2),
            "end_x_m": round(s_en, 2),
            "length_m": spans[s_i],
            "max_pos_mu_knm": round(max(0.0, best_m), 2),
            "m_max_pos_knm": round(max(0.0, best_m), 2),
            "at_x_m": round(best_x, 2),
            "x_at_m_max_m": round(best_x, 2),
            "v_left_kn": round(v_start, 2),
            "v_right_kn": round(v_end, 2),
            "max_abs_vu_kn": round(v_max_span, 2),
        })

    max_pos_val = max([s["max_pos_mu_knm"] for s in span_positive_moments] or [0.0])
    return {
        "beam_id": beam.get("id", "B1"),
        "spans": spans,
        "num_spans_excluding_cantilevers": ns,
        "cantilever_left_m": round(c_left, 3),
        "cantilever_right_m": round(c_right, 3),
        "span_starts": span_starts,
        "total_len": total_len,
        "loads_applied": [dict(ld) for ld in loads],
        "reactions": {i: round(RA[i], 2) for i in range(1, ns + 2)},
        "reactions_kn": [round(RA[i], 2) for i in range(1, ns + 2)],
        "support_moments": [round(Mus[i], 2) for i in range(1, ns + 2)],
        "support_critical_table": support_critical_table,
        "span_positive_moments": span_positive_moments,
        "span_critical_table": span_positive_moments,
        "max_pos_mu_knm": max_pos_val,
        "max_pos_moment": max_pos_val,
        "max_neg_face_mu_knm": min([s["face_neg_mu_knm"] for s in support_critical_table] or [0.0]),
        "max_neg_center_mu_knm": min([s["centerline_neg_mu_knm"] for s in support_critical_table] or [0.0]),
        "max_face_vu_kn": max([s["face_vu_kn"] for s in support_critical_table] or [0.0]),
        "x_full": x_full,
        "v_full": v_full,
        "m_full": m_full,
    }


def get_beam_span_segments(beam: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns ordered span/cantilever segments along the analytical beam coordinate system [0, total_len],
    where all distances are measured strictly between support centerlines.
    """
    raw_spans = [float(s) for s in beam.get("spans", []) if float(s) > 0.15]
    if not raw_spans:
        sx, sy = float(beam.get("start_x", 0.0)), float(beam.get("start_y", 0.0))
        ex, ey = float(beam.get("end_x", 4.0)), float(beam.get("end_y", 0.0))
        raw_spans = [round(max(0.50, math.hypot(ex - sx, ey - sy)), 3)]
    c_left = max(0.0, float(beam.get("cantilever_left_m", 0.0)))
    c_right = max(0.0, float(beam.get("cantilever_right_m", 0.0)))

    segments: List[Dict[str, Any]] = []
    cur_x = 0.0
    if c_left > 0.05:
        segments.append({
            "key": "cant_left",
            "label": "Left Cantilever",
            "short_label": f"LC = {c_left:.2f}m",
            "is_cantilever": True,
            "x1": 0.0,
            "x2": round(c_left, 3),
            "start_m": 0.0,
            "end_m": round(c_left, 3),
            "length_m": round(c_left, 3),
        })
        cur_x = round(c_left, 3)

    for idx, sp in enumerate(raw_spans):
        nx = round(cur_x + sp, 3)
        segments.append({
            "key": f"span_{idx + 1}",
            "label": f"Span {idx + 1}",
            "short_label": f"L{idx + 1} = {sp:.2f}m",
            "is_cantilever": False,
            "span_index": idx + 1,
            "x1": cur_x,
            "x2": nx,
            "start_m": cur_x,
            "end_m": nx,
            "length_m": round(sp, 3),
        })
        cur_x = nx

    if c_right > 0.05:
        nx = round(cur_x + c_right, 3)
        segments.append({
            "key": "cant_right",
            "label": "Right Cantilever",
            "short_label": f"RC = {c_right:.2f}m",
            "is_cantilever": True,
            "x1": cur_x,
            "x2": nx,
            "start_m": cur_x,
            "end_m": nx,
            "length_m": round(c_right, 3),
        })
    return segments


STANDARD_WALL_THICKNESSES_CM: List[int] = [10, 15, 20, 30, 40]


def snap_standard_wall_thickness_cm(val_cm: float) -> float:
    """
    Snaps any wall thickness value to the nearest standard masonry wall thickness:
    10 cm, 15 cm, 20 cm (default), 30 cm, or 40 cm.
    """
    raw = float(val_cm)
    nearest = min(STANDARD_WALL_THICKNESSES_CM, key=lambda t: abs(float(t) - raw))
    return float(nearest)


def ensure_beam_wall_flags(story_data: Dict[str, Any], beam: Dict[str, Any]) -> Dict[str, bool]:
    """
    Ensures `beam['span_wall_flags']` has a boolean flag for each span and cantilever of `beam`,
    initializing missing flags from `story_data['wall_load_policy']` ('all_beams' -> True, 'no_walls' -> False).
    Also initializes `beam['span_wall_thickness_cm']` (default 20.0 cm per span from standard [10, 15, 20, 30, 40]).
    """
    policy = str(story_data.get("wall_load_policy", "all_beams" if story_data.get("has_upper_floors", True) else "no_walls"))
    default_flag = (policy != "no_walls")
    default_t_cm = snap_standard_wall_thickness_cm(float(story_data.get("default_wall_thickness_cm", 20.0)))
    flags: Dict[str, bool] = beam.setdefault("span_wall_flags", {})
    thick_map: Dict[str, float] = beam.setdefault("span_wall_thickness_cm", {})
    for seg in get_beam_span_segments(beam):
        k = seg["key"]
        if k not in flags:
            flags[k] = default_flag
        if k not in thick_map:
            thick_map[k] = default_t_cm
        else:
            thick_map[k] = snap_standard_wall_thickness_cm(thick_map[k])
    return flags


def resolve_effective_wall_height_for_story(story_data: Dict[str, Any]) -> float:
    """
    Resolves the true physical height of walls CARRIED by the beams of this level:
    - 00_TieBeams: Carries the walls of the Ground Floor -> H_wall = ground_floor_height_m (default 3.20m, NOT 1.50m excavation depth!)
    - 02_Ground_Floor: Carries the walls of the First/Typical Upper Floor -> H_wall = upper_floor_height_m (default 3.00m)
    - Upper Floors: Carries the story above or Roof Parapet (1.50m)
    - Penthouse / Roof: Parapet wall height (1.50m)
    """
    if "wall_height_m" in story_data and float(story_data["wall_height_m"]) > 0.10:
        return float(story_data["wall_height_m"])
    st_type = str(story_data.get("story_type", "")).lower()
    st_id = str(story_data.get("story_id", "")).lower()
    if "tie" in st_type or "tie" in st_id or "00_" in st_id:
        return 3.20
    if "ground" in st_type or "ground" in st_id or "02_" in st_id:
        return 3.00 if story_data.get("has_upper_floors", True) else 0.0
    if "penthouse" in st_type or "penthouse" in st_id or "roof" in st_id:
        return 1.50
    return float(story_data.get("height_m", 3.00))


def set_story_wall_load_policy(
    story_data: Dict[str, Any],
    policy: str,
    wall_load_kn_m: Optional[float] = None,
    apply_to_all_existing_spans: bool = True,
    slab_load_kpa: Optional[float] = None,
    wall_thickness_cm: Optional[float] = None,
) -> Tuple[int, str]:
    """
    Sets the Story-Level General Wall & Slab Load Policy:
    - policy = 'all_beams': Default wall load ON for all beam spans.
    - policy = 'no_walls': Default wall load OFF for all beam spans (e.g., Roof slab, allowing selective stair walls).
    - Default wall load for a 20 cm wall: W_wall = 2.5 * (t_wall / 20.0) * H_effective_wall * 1.4.
    """
    clean_policy = "no_walls" if policy == "no_walls" else "all_beams"
    story_data["wall_load_policy"] = clean_policy
    story_h = float(story_data.get("height_m", 3.0))
    effective_wall_h = resolve_effective_wall_height_for_story(story_data)
    story_data["wall_height_m"] = effective_wall_h
    if wall_thickness_cm is not None:
        story_data["default_wall_thickness_cm"] = snap_standard_wall_thickness_cm(float(wall_thickness_cm))
    t_wall_def = snap_standard_wall_thickness_cm(float(story_data.get("default_wall_thickness_cm", 20.0)))
    story_data["default_wall_thickness_cm"] = t_wall_def
    formula_wall_w = round(2.5 * (t_wall_def / 20.0) * effective_wall_h * 1.4, 2)

    if wall_load_kn_m is not None:
        story_data["default_wall_load_kn_m"] = round(max(0.0, float(wall_load_kn_m)), 2)
        story_data["custom_wall_load_override"] = (abs(float(wall_load_kn_m) - formula_wall_w) > 0.05)
    else:
        story_data["default_wall_load_kn_m"] = formula_wall_w
        story_data["custom_wall_load_override"] = False

    if slab_load_kpa is not None:
        story_data["slab_factored_wu_kpa"] = round(max(1.0, float(slab_load_kpa)), 2)
        story_data["custom_slab_wu_override"] = True

    w_val = float(story_data.get("default_wall_load_kn_m", formula_wall_w))
    q_val = float(story_data.get("slab_factored_wu_kpa", 11.71))

    target_bool = (clean_policy == "all_beams")
    updated_spans = 0
    for bm in story_data.get("beams", []):
        flags = ensure_beam_wall_flags(story_data, bm)
        thick_map = bm.setdefault("span_wall_thickness_cm", {})
        if apply_to_all_existing_spans:
            for k in list(flags.keys()):
                flags[k] = target_bool
                if wall_thickness_cm is not None:
                    thick_map[k] = t_wall_def
                updated_spans += 1
        bm.pop("manual_loads_override", None)

    mode_desc = f"Wall Load ({w_val:.2f} kN/m, t={t_wall_def:.0f}cm) ON | Slab Wu = {q_val:.2f} kN/m²" if target_bool else f"Wall Load OFF by default | Slab Wu = {q_val:.2f} kN/m²"
    return updated_spans, f"Story Load Policy updated: {mode_desc}."


def set_beam_span_wall_flag(
    story_data: Dict[str, Any],
    beam_id: str,
    span_key: str,
    enabled: bool,
) -> Tuple[bool, str]:
    """
    Toggles masonry wall load ON/OFF for a specific span (`span_1`, `span_2`, `cant_left`, `cant_right`)
    of `beam_id` without affecting other spans!
    """
    bm = next((b for b in story_data.get("beams", []) if b.get("id") == beam_id), None)
    if not bm:
        return False, f"Beam {beam_id} not found."
    flags = ensure_beam_wall_flags(story_data, bm)
    flags[span_key] = bool(enabled)
    bm.pop("manual_loads_override", None)
    state_str = "ENABLED" if enabled else "DISABLED"
    return True, f"Beam {beam_id} ({span_key}): Masonry Wall Load {state_str}."


def set_beam_span_wall_thickness(
    story_data: Dict[str, Any],
    beam_id: str,
    span_key: Any,
    wall_thickness_cm: float,
) -> Tuple[bool, str]:
    """
    Sets standard masonry wall thickness `t_wall` (from [10, 15, 20, 30, 40] cm, default 20 cm)
    for a specific span (`span_1`, `span_2`, `cant_left`, `cant_right`, or integer index `1`, `2`) of `beam_id`,
    updating W_wall = (2.5 * H * 1.4) * (t_wall / 20.0).
    """
    bm = next((b for b in story_data.get("beams", []) if b.get("id") == beam_id), None)
    if not bm:
        return False, f"Beam {beam_id} not found."
    ensure_beam_wall_flags(story_data, bm)
    skey = f"span_{span_key}" if str(span_key).isdigit() else str(span_key)
    t_clean = snap_standard_wall_thickness_cm(float(wall_thickness_cm))
    bm.setdefault("span_wall_thickness_cm", {})[skey] = t_clean
    bm.pop("manual_loads_override", None)
    eff_h = resolve_effective_wall_height_for_story(story_data)
    w_wall = round((2.5 * eff_h * 1.4) * (t_clean / 20.0), 2)
    return True, f"Beam {beam_id} ({skey}): Wall thickness set to {t_clean:.0f} cm (W_wall = {w_wall:.2f} kN/m)."


def design_hollow_block_slab_rib(
    slab_obj: Dict[str, Any],
    story_data: Dict[str, Any],
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
    db_mm_override: Optional[int] = None,
    custom_span_l_m: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Designs a One-Way Hollow-Block (Hordi) Slab Rib strictly following Eng. Yousef's
    Excel sheet ('Design of rib slab'):
    1. Geometry & Material Inputs:
       - h = Story Slab Thickness (default 300 mm = 30.0 cm)
       - hs = Topping Slab Thickness (100 mm)
       - S = Block Width (400 mm), bw1 = 150 mm, bw2 = 150 mm, b = bw1 + S = 550 mm
       - γc = 24 kN/m³, W_finishing = 1.5 kN/m², LL = 2.0 kN/m², W_block = 0.10 kN (4 blocks/m = 0.40 kN/m'/rib)
       - dc = 20 mm concrete cover, ds = 6 mm triangular stirrup (triangular stirrup ∅6)
       - Top fixation bar = 1∅10 mm (single top bar for fixation only)
       - Bottom reinforcement diameter db in {12, 14, 16} mm (default 12 mm)
    2. Load Distinction:
       - Per-Rib Factored Load (used for Rib Flexure & Shear Design):
         Wu_rib = 1.4 * DL_rib + 1.7 * LL_rib  [kN/m'/rib]  (6.44 kN/m'/rib for h=300mm)
       - Per-Square-Meter Factored Load (transferred to Supporting Beams):
         Wu_m2 = Wu_rib / (b / 1000)           [kN/m²]      (11.71 kN/m² for h=300mm)
    3. Design Span L & Moment Mu:
       - L = Total Center-to-Center Span between carrying beams along the rib direction (NOT clear span).
       - Simply supported assumption for all slabs: Mu = Wu_rib * L² / 8  [kN.m/rib].
    4. Flexure & Shear Equations:
       - d = h - ds - dc - db/2
       - Ku = (Mu * 10^6) / (0.9 * (bw1 + S) * fc' * d²)
       - ω = (1 - sqrt(1 - 2.36 * Ku)) / 1.18
       - ρ = ω * (fc' / Fy)
       - As_min = (1.4 / Fy) * bw2 * d
       - As = max(ρ * b * d, As_min)
       - Nbar = As / (3.14 * db² / 4) -> adopted bars = max(2, ceil(Nbar))
       - Vc = 1.1 * sqrt(fc') * bw2 * d / 6000, φVc = 0.85 * Vc, Vu = Wu_rib * (L/2 - d/1000)
    """
    hb_cfg = story_data.get("hollow_block", {})
    h_cm = float(story_data.get("adopted_slab_thickness_cm", hb_cfg.get("total_thickness_cm", 30.0)))
    raw_block_h_cm = hb_cfg.get("block_height_cm", None)
    if raw_block_h_cm is not None and abs(float(raw_block_h_cm) - 16.0) < 0.5:
        block_h_cm = 16.0
    elif raw_block_h_cm is not None and abs(float(raw_block_h_cm) - 20.0) < 0.5:
        block_h_cm = 20.0
    else:
        block_h_cm = 20.0 if h_cm >= 25.0 else 16.0

    if h_cm < block_h_cm + 5.0:
        if h_cm >= 21.0:
            block_h_cm = 16.0
        else:
            h_cm = block_h_cm + 5.0
    hs_cm = round(max(5.0, h_cm - block_h_cm), 2)

    h_mm = round(h_cm * 10.0, 1)
    hs_mm = round(hs_cm * 10.0, 1)
    s_mm = round(float(hb_cfg.get("block_width_cm", 40.0)) * 10.0, 1)
    bw1_mm = round(float(hb_cfg.get("rib_width_top_cm", hb_cfg.get("rib_width_cm", 15.0))) * 10.0, 1)
    bw2_mm = round(float(hb_cfg.get("rib_width_cm", 15.0)) * 10.0, 1)
    b_mm = bw1_mm + s_mm
    b_m = b_mm / 1000.0

    gamma_c = float(hb_cfg.get("gamma_c_kn_m3", 24.0))
    w_finishing = float(hb_cfg.get("finishing_load_kpa", 1.5))
    ll_kpa = float(hb_cfg.get("live_load_kpa", 2.0))
    w_block_kn = float(hb_cfg.get("block_weight_kn", 0.10))
    blocks_per_m = int(hb_cfg.get("blocks_per_m", 4))

    if db_mm_override is not None and int(db_mm_override) in (12, 14, 16):
        db_mm = int(db_mm_override)
        slab_obj["rib_bar_dia_mm"] = db_mm
    else:
        raw_db = int(slab_obj.get("rib_bar_dia_mm", 12))
        db_mm = raw_db if raw_db in (12, 14, 16) else 12
        slab_obj["rib_bar_dia_mm"] = db_mm

    ds_mm = 6
    dc_mm = 20
    top_bar_dia_mm = 10

    # 1. Dead & Live Loads per Rib (kN/m'/rib)
    topping_wt_rib = round((hs_mm / 1000.0) * b_m * gamma_c, 4)
    rib_web_wt_rib = round(((bw1_mm + bw2_mm) / 2000.0) * ((h_mm - hs_mm) / 1000.0) * gamma_c, 4)
    block_wt_rib = round(blocks_per_m * w_block_kn, 4)
    finishing_wt_rib = round(w_finishing * b_m, 4)

    total_dl_rib = round(topping_wt_rib + rib_web_wt_rib + block_wt_rib + finishing_wt_rib, 4)
    factored_dl_rib = round(1.4 * total_dl_rib, 4)

    ll_rib = round(ll_kpa * b_m, 4)
    factored_ll_rib = round(1.7 * ll_rib, 4)

    wu_rib_exact = round(factored_dl_rib + factored_ll_rib, 4)
    wu_rib_display = round(wu_rib_exact, 2)
    wu_m2_kpa = round(wu_rib_exact / b_m, 2)

    # 2. Center-to-Center Design Span L (along the rib direction)
    rib_dir = int(slab_obj.get("rib_direction_deg", slab_obj.get("rib_angle_deg", 0)))
    if "min_x" in slab_obj and "max_x" in slab_obj:
        lx_cc = max(0.5, float(slab_obj["max_x"]) - float(slab_obj["min_x"]))
        ly_cc = max(0.5, float(slab_obj.get("max_y", 0.0)) - float(slab_obj.get("min_y", 0.0)))
    elif "x_min" in slab_obj and "x_max" in slab_obj:
        lx_cc = max(0.5, float(slab_obj["x_max"]) - float(slab_obj["x_min"]))
        ly_cc = max(0.5, float(slab_obj["y_max"]) - float(slab_obj["y_min"]))
    else:
        lx_cc = max(0.5, float(slab_obj.get("lx_m", 4.0)))
        ly_cc = max(0.5, float(slab_obj.get("ly_m", 4.0)))

    if custom_span_l_m is not None and float(custom_span_l_m) > 0.3:
        span_l_m = round(float(custom_span_l_m), 3)
    elif "custom_design_span_m" in slab_obj and float(slab_obj["custom_design_span_m"]) > 0.3:
        span_l_m = round(float(slab_obj["custom_design_span_m"]), 3)
    else:
        span_l_m = round(lx_cc if rib_dir == 0 else ly_cc, 3)

    # 3. Simply Supported Design Moment Mu = Wu_rib * L² / 8
    if "custom_mu_knm" in slab_obj and slab_obj["custom_mu_knm"] is not None:
        mu_knm_exact = float(slab_obj["custom_mu_knm"])
    else:
        mu_knm_exact = (wu_rib_exact * (span_l_m ** 2)) / 8.0
    mu_knm = round(mu_knm_exact, 2)

    # 4. Flexural Design per Excel Sheet
    d_mm = round(h_mm - ds_mm - dc_mm - (db_mm / 2.0), 1)
    ku_raw = (mu_knm_exact * 1_000_000.0) / max(1.0, 0.9 * b_mm * fc_mpa * (d_mm ** 2))
    ku_clamped = min(0.38, max(0.0001, ku_raw))
    ku_val = round(ku_clamped, 4)

    disc = max(0.0, 1.0 - 2.36 * ku_val)
    omega_raw = (1.0 - math.sqrt(disc)) / 1.18
    omega_val = round(omega_raw, 4)

    # Match Excel cell progression: ρ = ω * (fc' / Fy)
    rho_raw = omega_val * (fc_mpa / fy_mpa)
    rho_val = round(rho_raw, 6)

    beta1 = 0.85 if fc_mpa <= 28.0 else max(0.65, 0.85 - 0.05 * ((fc_mpa - 28.0) / 7.0))
    rho_max = round(0.85 * beta1 * (fc_mpa / fy_mpa) * (600.0 / (600.0 + fy_mpa)), 5)
    as_min_mm2 = round((1.4 / fy_mpa) * bw2_mm * d_mm, 1)
    as_max_mm2 = round(0.75 * rho_max * bw2_mm * d_mm, 1)

    as_calc_mm2 = round(rho_val * b_mm * d_mm, 2)
    as_req_mm2 = round(max(as_calc_mm2, as_min_mm2), 2)
    governs_min = (as_calc_mm2 < as_min_mm2)

    # Bar Area per Excel: pi * db² / 4 (gives Nbar = 1.76 for As=199.58, db=12)
    area_one_bar_mm2 = round(math.pi * (db_mm ** 2) / 4.0, 2)
    n_bar_exact = round(as_req_mm2 / max(1.0, area_one_bar_mm2), 2)
    n_bars_adopted = max(2, int(math.ceil(n_bar_exact - 1e-6)))
    as_provided_mm2 = round(n_bars_adopted * area_one_bar_mm2, 1)

    # 5. Shear Design per Excel Sheet
    vc_kn = round((1.1 * math.sqrt(fc_mpa) * bw2_mm * d_mm) / 6000.0, 2)
    phi_vc_kn = round(0.85 * vc_kn, 2)
    vu_kn = round(max(0.0, wu_rib_exact * ((span_l_m / 2.0) - (d_mm / 1000.0))), 2)
    shear_ok = (vu_kn <= phi_vc_kn)
    shear_status_note = (
        "No Stirrups are required for shear (Constructive ∅6 triangular stirrups @ 200mm used)"
        if shear_ok
        else "WARNING: Vu > φVc! Increase slab thickness (h) or widen rib web (bw)!"
    )

    result = {
        "slab_id": str(slab_obj.get("id", "S1")),
        "rib_direction_deg": rib_dir,
        "rib_direction_label": "X-Direction (0°)" if rib_dir == 0 else "Y-Direction (90°)",
        "span_l_m": span_l_m,
        "lx_m": round(lx_cc, 2),
        "ly_m": round(ly_cc, 2),
        "h_mm": h_mm,
        "hs_mm": hs_mm,
        "block_height_mm": round(h_mm - hs_mm, 1),
        "s_mm": s_mm,
        "bw1_mm": bw1_mm,
        "bw2_mm": bw2_mm,
        "b_mm": b_mm,
        "dc_mm": dc_mm,
        "ds_mm": ds_mm,
        "db_mm": db_mm,
        "top_bar_dia_mm": top_bar_dia_mm,
        "d_mm": d_mm,
        "fc_mpa": fc_mpa,
        "fy_mpa": fy_mpa,
        "gamma_c_kn_m3": gamma_c,
        "w_finishing_kpa": w_finishing,
        "ll_kpa": ll_kpa,
        "w_block_kn": w_block_kn,
        "blocks_per_m": blocks_per_m,
        "topping_wt_rib": round(topping_wt_rib, 3),
        "rib_web_wt_rib": round(rib_web_wt_rib, 3),
        "block_wt_rib": round(block_wt_rib, 3),
        "finishing_wt_rib": round(finishing_wt_rib, 3),
        "total_dl_rib": round(total_dl_rib, 3),
        "factored_dl_rib": round(factored_dl_rib, 3),
        "ll_rib": round(ll_rib, 3),
        "factored_ll_rib": round(factored_ll_rib, 3),
        "wu_rib_kn_m": wu_rib_display,
        "wu_rib_exact": wu_rib_exact,
        "wu_m2_kpa": wu_m2_kpa,
        "mu_knm": mu_knm,
        "mu_formula": f"Mu = Wu_rib × L² / 8 = {wu_rib_display:.2f} × {span_l_m:.2f}² / 8 = {mu_knm:.2f} kN.m/rib",
        "ku": ku_val,
        "omega": omega_val,
        "rho": rho_val,
        "beta1": round(beta1, 2),
        "rho_max": rho_max,
        "as_min_mm2": as_min_mm2,
        "as_max_mm2": as_max_mm2,
        "as_calc_mm2": as_calc_mm2,
        "as_req_mm2": as_req_mm2,
        "governs_min": governs_min,
        "area_one_bar_mm2": area_one_bar_mm2,
        "n_bar_exact": n_bar_exact,
        "n_bars_adopted": n_bars_adopted,
        "as_provided_mm2": as_provided_mm2,
        "bottom_rebar_callout": f"{n_bars_adopted}∅{db_mm} Bottom (per rib)",
        "top_rebar_callout": f"1∅{top_bar_dia_mm} Top (Fixation Bar)",
        "stirrup_callout": f"∅{ds_mm} @ 200 mm Open Triangular Stirrups",
        "vc_kn": vc_kn,
        "phi_vc_kn": phi_vc_kn,
        "vu_kn": vu_kn,
        "shear_ok": shear_ok,
        "shear_status_note": shear_status_note,
    }
    slab_obj["rib_design"] = result
    return result


def analyze_all_story_beams_and_columns(
    story_data: Dict[str, Any],
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
) -> Dict[str, Any]:
    """
    1-Click Story Analysis (v2.2.0-structural-bim-pro — Single-Pass Excel Philosophy):
    - First reconciles all beam supports and spans against the active columns and perpendicular carrier beams
      so deleted or moved columns are 100% reflected in beam spans and supports.
    - Synchronizes Hollow-Block (Hordi) slab weights from `adopted_slab_thickness_cm` (default 30.0 cm)
      using fixed commercial block height (20 cm for h >= 25 cm, 16 cm for h < 25 cm) & hs = h - block_h:
        * Wu_rib (kN/m'/rib) -> used to design each slab rib S1..Sn (Mu = Wu_rib * L² / 8).
        * Wu_m2 (kN/m²) = Wu_rib / (S + bw1) -> transferred to supporting beams (11.04 kN/m² for 28 cm, 11.71 kN/m² for 30 cm).
    - Single-Pass Load Evaluation (NO O.W re-calculation and NO slab rib L_rib reduction after sizing):
        * Computes Beam Self-Weight once from baseline dimensions: O.W = b_init * h_init * 24 * 1.4 [kN/m].
        * Computes Masonry Wall Load on enabled spans: W_wall = 2.5 * (t_wall_cm / 20.0) * H_story * 1.4 [kN/m].
        * Computes piecewise distributed slab loads along each span using full rib spans (splitting at slab/opening bounds).
    - Topologically sorts beams so secondary supported beams are solved before their carrier beams,
      transfers centerline point reactions (`type: "P"`), and applies VBA `Sub ReDesign_Sec()` (+100 mm step) post-analysis.
    """
    enforce_opening_adjacent_drop_beams_and_cascade(story_data)
    reconcile_all_story_beams_supports_and_spans(story_data)
    orig_beams = story_data.get("beams", [])
    beams = [dict(b) for b in orig_beams]
    columns = [dict(c) for c in story_data.get("columns", [])]
    slabs = story_data.get("slabs", [])
    openings = story_data.get("openings", [])
    story_h = float(story_data.get("height_m", 3.0))
    _log_eng(
        "ANALYSIS_START",
        f"Starting full story analysis for {story_data.get('story_id', 'Story')}",
        {
            "fc_mpa": fc_mpa,
            "fy_mpa": fy_mpa,
            "story_h_m": story_h,
            "adopted_slab_thickness_cm": story_data.get("adopted_slab_thickness_cm", 30.0),
            "num_columns": len([c for c in columns if c.get("active", True)]),
            "num_beams": len(beams),
            "num_slabs": len(slabs),
            "num_openings": len(openings),
        },
    )

    # Synchronize Hollow-Block (Hordi) parameters from story's adopted_slab_thickness_cm (default 30.0 cm)
    # using fixed commercial block height (20 cm for h >= 25 cm, 16 cm for h < 25 cm) and hs = h - block_h
    adopted_t_cm = float(story_data.get("adopted_slab_thickness_cm", 30.0))
    is_tie_story = str(story_data.get("story_type", "")).lower() == "tie_beams" or "tie" in str(story_data.get("story_id", "")).lower()
    if is_tie_story:
        adopted_t_cm = 0.0
    hb_prev = story_data.get("hollow_block", {})
    raw_blk_h = hb_prev.get("block_height_cm", None)
    if raw_blk_h is not None and abs(float(raw_blk_h) - 16.0) < 0.5:
        block_h_cm = 16.0
    elif raw_blk_h is not None and abs(float(raw_blk_h) - 20.0) < 0.5:
        block_h_cm = 20.0
    else:
        block_h_cm = 20.0 if adopted_t_cm >= 25.0 else 16.0
    if adopted_t_cm < block_h_cm + 5.0:
        if adopted_t_cm >= 21.0:
            block_h_cm = 16.0
        else:
            adopted_t_cm = block_h_cm + 5.0
    hs_cm = round(max(5.0, adopted_t_cm - block_h_cm), 2)
    bw_cm = float(hb_prev.get("rib_width_cm", 15.0))
    bw_top_cm = float(hb_prev.get("rib_width_top_cm", bw_cm))
    s_cm = float(hb_prev.get("block_width_cm", 40.0))
    gamma_c = float(hb_prev.get("gamma_c_kn_m3", 24.0))
    w_fin = float(hb_prev.get("finishing_load_kpa", 1.5))
    ll_kpa = float(hb_prev.get("live_load_kpa", 2.0))
    w_blk = float(hb_prev.get("block_weight_kn", 0.10))
    n_blk = int(hb_prev.get("blocks_per_m", 4))

    b_m_pitch = (s_cm + bw_top_cm) / 100.0
    dl_rib = (
        (hs_cm / 100.0) * b_m_pitch * gamma_c
        + ((bw_cm + bw_top_cm) / 200.0) * (block_h_cm / 100.0) * gamma_c
        + (n_blk * w_blk)
        + (w_fin * b_m_pitch)
    )
    wu_rib_kn_m = round(1.4 * dl_rib + 1.7 * (ll_kpa * b_m_pitch), 4)
    auto_slab_wu_kpa = round(wu_rib_kn_m / max(0.1, b_m_pitch), 2)

    hb_summary = {
        "total_thickness_cm": round(adopted_t_cm, 1),
        "topping_thickness_cm": round(hs_cm, 1),
        "block_height_cm": round(block_h_cm, 1),
        "rib_width_cm": round(bw_cm, 1),
        "rib_width_top_cm": round(bw_top_cm, 1),
        "block_width_cm": round(s_cm, 1),
        "rib_pitch_cm": round(s_cm + bw_top_cm, 1),
        "gamma_c_kn_m3": gamma_c,
        "finishing_load_kpa": w_fin,
        "live_load_kpa": ll_kpa,
        "block_weight_kn": w_blk,
        "blocks_per_m": n_blk,
        "dl_rib_kn_m": round(dl_rib, 3),
        "factored_dl_rib_kn_m": round(1.4 * dl_rib, 3),
        "ll_rib_kn_m": round(ll_kpa * b_m_pitch, 3),
        "factored_ll_rib_kn_m": round(1.7 * ll_kpa * b_m_pitch, 3),
        "wu_rib_kn_m": round(wu_rib_kn_m, 2),
        "factored_wu_kpa": auto_slab_wu_kpa,
    }
    story_data["hollow_block"] = hb_summary
    if not is_tie_story:
        _log_eng("HORDI_CALC", f"Slab h={adopted_t_cm:.1f}cm (block={block_h_cm:.0f}cm, hs={hs_cm:.1f}cm) -> Wu_rib={round(wu_rib_kn_m, 2):.2f} kN/m'/rib, Wu_m2={auto_slab_wu_kpa:.2f} kN/m²", hb_summary)

    if is_tie_story:
        auto_slab_wu_kpa = 0.0
        hb_summary["factored_wu_kpa"] = 0.0
        hb_summary["total_thickness_cm"] = 0.0
        hb_summary["wu_rib_kn_m"] = 0.0
        story_data["hollow_block"] = hb_summary
        story_data["slab_factored_wu_kpa"] = 0.0
    if not story_data.get("custom_slab_wu_override", False):
        story_data["slab_factored_wu_kpa"] = auto_slab_wu_kpa
    slab_wu_kpa = 0.0 if is_tie_story else float(story_data.get("slab_factored_wu_kpa", auto_slab_wu_kpa))

    default_t_wall_cm = float(story_data.get("default_wall_thickness_cm", 20.0))
    eff_wall_h = resolve_effective_wall_height_for_story(story_data)
    formula_wall_20cm = round(2.5 * eff_wall_h * 1.4, 2)
    if not story_data.get("custom_wall_load_override", False):
        story_data["default_wall_load_kn_m"] = round(formula_wall_20cm * (default_t_wall_cm / 20.0), 2)
    default_wall_w = float(story_data.get("default_wall_load_kn_m", formula_wall_20cm))

    # Design all Hollow-Block (Hordi) Slabs S1..Sn
    slab_designs: Dict[str, Dict[str, Any]] = {}
    for slb in slabs:
        if slb.get("is_void", False):
            continue
        sid = str(slb.get("id", f"S{len(slab_designs) + 1}"))
        slab_designs[sid] = design_hollow_block_slab_rib(slb, story_data, fc_mpa=fc_mpa, fy_mpa=fy_mpa)

    # Helper to find the world coordinate of Support 1's centerline for any beam
    col_coord_map = {c["id"]: (float(c["x"]), float(c["y"])) for c in columns if "id" in c}

    def get_beam_first_support_world_coord(bm_obj: Dict[str, Any]) -> float:
        bsx, bsy = float(bm_obj.get("start_x", 0.0)), float(bm_obj.get("start_y", 0.0))
        bex, bey = float(bm_obj.get("end_x", 0.0)), float(bm_obj.get("end_y", 0.0))
        b_horiz = abs(bex - bsx) >= abs(bey - bsy)
        sups = bm_obj.get("supports", [])
        if sups:
            s0 = sups[0]
            if "center_coord_m" in s0:
                return float(s0["center_coord_m"])
            if "coord" in s0:
                return float(s0["coord"])
            tid = s0.get("target_id")
            if tid in col_coord_map:
                return col_coord_map[tid][0] if b_horiz else col_coord_map[tid][1]
        c_left = max(0.0, float(bm_obj.get("cantilever_left_m", 0.0)))
        return (min(bsx, bex) + c_left) if b_horiz else (min(bsy, bey) + c_left)

    def extract_slab_bounds(slb_obj: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
        if "min_x" in slb_obj and "max_x" in slb_obj:
            return float(slb_obj["min_x"]), float(slb_obj["max_x"]), float(slb_obj["min_y"]), float(slb_obj["min_y"] if "max_y" not in slb_obj else slb_obj["max_y"])
        if "x_min" in slb_obj and "x_max" in slb_obj:
            return float(slb_obj["x_min"]), float(slb_obj["x_max"]), float(slb_obj["y_min"]), float(slb_obj["y_max"])
        if "origin_x" in slb_obj and "lx_m" in slb_obj:
            ox, oy = float(slb_obj.get("origin_x", 0.0)), float(slb_obj.get("origin_y", 0.0))
            return ox, ox + float(slb_obj.get("lx_m", 4.0)), oy, oy + float(slb_obj.get("ly_m", 4.0))
        return None

    beam_map: Dict[str, Dict[str, Any]] = {}
    for idx_b, b in enumerate(beams):
        bid = b["id"]
        b_copy = dict(b)
        b_kind_norm = str(b_copy.get("beam_kind", b_copy.get("kind", "hidden"))).lower()
        b_kind_norm = "drop" if "drop" in b_kind_norm else "hidden"
        b_copy["beam_kind"] = b_kind_norm
        b_copy["kind"] = b_kind_norm
        if idx_b < len(orig_beams):
            orig_beams[idx_b]["beam_kind"] = b_kind_norm
            orig_beams[idx_b]["kind"] = b_kind_norm

        raw_spans = [float(s) for s in b_copy.get("spans", []) if float(s) > 0.15]
        if not raw_spans:
            sx, sy = float(b_copy.get("start_x", 0.0)), float(b_copy.get("start_y", 0.0))
            ex, ey = float(b_copy.get("end_x", 4.0)), float(b_copy.get("end_y", 0.0))
            raw_spans = [round(max(0.50, math.hypot(ex - sx, ey - sy)), 3)]
        b_copy["spans"] = raw_spans
        beam_map[bid] = b_copy

    # Topological Sort FIRST: Secondary supported beams MUST be processed before the primary carrier beams they rest on!
    ordered_ids: List[str] = []
    visited = set()
    temp_visiting = set()

    dependents_on_carrier: Dict[str, List[str]] = {b["id"]: [] for b in beams}
    for b in beams:
        for sup in b.get("supports", []):
            if sup.get("kind") == "beam" and sup.get("target_id") in dependents_on_carrier:
                dependents_on_carrier[sup["target_id"]].append(b["id"])

    def visit_with_prereqs(bid: str):
        if bid in visited or bid not in beam_map:
            return
        if bid in temp_visiting:
            return
        temp_visiting.add(bid)
        for sec_id in dependents_on_carrier.get(bid, []):
            visit_with_prereqs(sec_id)
        temp_visiting.remove(bid)
        visited.add(bid)
        ordered_ids.append(bid)

    for b in beams:
        visit_with_prereqs(b["id"])

    # Record initial baseline beam dimensions BEFORE single-pass load evaluation:
    # Hidden beam minimum width = 0.40m (or story hb_cfg min_b_hidden), depth = slab thickness
    # Drop beam width = wall thickness (0.20m), minimum depth = 0.40m
    hb_cfg = story_data.get("hollow_block", {})
    min_b_hidden_m = max(0.30, float(hb_cfg.get("min_b_hidden_mm", 300.0)) / 1000.0)
    min_h_drop_m = max(0.30, float(hb_cfg.get("min_h_drop_mm", 400.0)) / 1000.0)
    slab_h_m = max(0.15, float(story_data.get("adopted_slab_thickness_cm", 30.0)) / 100.0)
    wall_b_m = max(0.15, default_t_wall_cm / 100.0)

    for idx_b, b in enumerate(beams):
        bid = b["id"]
        b_copy = beam_map[bid]
        b_kind = str(b_copy.get("beam_kind", "hidden")).lower()
        if not b_copy.get("lock_section_dimensions", False):
            if b_kind == "hidden":
                init_w = float(b_copy.get("initial_width_m", min_b_hidden_m))
                init_h = slab_h_m
            else:
                init_w = float(b_copy.get("initial_width_m", b_copy.get("width_m", wall_b_m)))
                raw_init_h = float(b_copy.get("initial_depth_m", b_copy.get("depth_m", min_h_drop_m)))
                if is_tie_story:
                    raw_init_h = min_h_drop_m
                init_h = _snap_drop_depth_m(max(min_h_drop_m, raw_init_h), min_h_drop_m)
            b_copy["initial_width_m"] = round(init_w, 3)
            b_copy["initial_depth_m"] = round(init_h, 3)
            b_copy["width_m"] = round(init_w, 3)
            b_copy["depth_m"] = round(init_h, 3)
        else:
            b_copy["initial_width_m"] = round(float(b_copy.get("width_m", 0.40)), 3)
            b_copy["initial_depth_m"] = round(float(b_copy.get("depth_m", 0.30)), 3)

    col_obj_map = {c["id"]: c for c in columns if "id" in c}

    def enforce_carrier_hierarchy_and_support_dims(sync_initial: bool = True) -> None:
        """
        STRUCTURAL CARRIER HIERARCHY RULE (Eng. Yousef Rule #9 & Drop-on-Hidden Prevention):
        1. A supporting (carrier) beam MUST have a section depth >= any supported (secondary) beam resting on it.
        2. A Drop Beam CANNOT rest on a Hidden Beam; upgrade carrier beam to Drop if needed.
        3. Populate accurate support dimensions on all beam supports.
        """
        for sec_id in ordered_ids:
            sec_bm = beam_map[sec_id]
            sec_d = float(sec_bm.get("depth_m", 0.30))
            sec_w = float(sec_bm.get("width_m", 0.20))
            for sup in sec_bm.get("supports", []):
                if sup.get("kind") == "beam":
                    car_id = sup.get("target_id")
                    if car_id in beam_map:
                        car_bm = beam_map[car_id]
                        car_d = float(car_bm.get("depth_m", 0.30))
                        if sec_bm.get("beam_kind") == "drop" and car_bm.get("beam_kind") == "hidden":
                            car_bm["beam_kind"] = "drop"
                            car_bm["kind"] = "drop"
                            car_bm["width_m"] = min(float(car_bm.get("width_m", 0.20)), 0.20)
                            car_bm["depth_m"] = _snap_drop_depth_m(max(0.40, sec_d), 0.40)
                            if sync_initial:
                                car_bm["initial_width_m"] = car_bm["width_m"]
                                car_bm["initial_depth_m"] = car_bm["depth_m"]
                            _log_eng("CASCADE", f"Carrier beam {car_id} converted Hidden -> Drop (supports Drop {sec_id})")
                        if car_d < sec_d:
                            new_car_d = _snap_drop_depth_m(sec_d, 0.40) if car_bm.get("beam_kind") == "drop" else round(sec_d, 3)
                            car_bm["depth_m"] = new_car_d
                            if sync_initial:
                                car_bm["initial_depth_m"] = max(float(car_bm.get("initial_depth_m", car_bm["depth_m"])), car_bm["depth_m"])
                        if car_bm.get("beam_kind") == "drop" and sec_bm.get("beam_kind") == "drop":
                            if float(car_bm.get("width_m", 0.20)) < sec_w:
                                car_bm["width_m"] = round(sec_w, 3)
                                if sync_initial:
                                    car_bm["initial_width_m"] = max(float(car_bm.get("initial_width_m", car_bm["width_m"])), car_bm["width_m"])
                        for orig_b in orig_beams:
                            if orig_b.get("id") == car_id:
                                orig_b["beam_kind"] = car_bm["beam_kind"]
                                orig_b["kind"] = car_bm["kind"]
                                orig_b["depth_m"] = car_bm["depth_m"]
                                orig_b["width_m"] = car_bm["width_m"]
                                if sync_initial:
                                    orig_b["initial_depth_m"] = car_bm.get("initial_depth_m", car_bm["depth_m"])
                                    orig_b["initial_width_m"] = car_bm.get("initial_width_m", car_bm["width_m"])
                                break

        for _bid, b_copy in beam_map.items():
            bsx, bsy = float(b_copy.get("start_x", 0.0)), float(b_copy.get("start_y", 0.0))
            bex, bey = float(b_copy.get("end_x", 0.0)), float(b_copy.get("end_y", 0.0))
            b_horiz = abs(bex - bsx) >= abs(bey - bsy)
            for sup in b_copy.get("supports", []):
                tid = sup.get("target_id")
                if sup.get("kind") == "beam" and tid in beam_map:
                    car_bm = beam_map[tid]
                    sup["width_m"] = round(float(car_bm.get("width_m", 0.20)), 3)
                    sup["depth_m"] = round(float(car_bm.get("depth_m", 0.50)), 3)
                elif sup.get("kind") == "column" and tid in col_obj_map:
                    c_obj = col_obj_map[tid]
                    w_along = float(c_obj.get("b_m", 0.20)) if b_horiz else float(c_obj.get("h_m", 0.40))
                    d_perp = float(c_obj.get("h_m", 0.40)) if b_horiz else float(c_obj.get("b_m", 0.20))
                    sup["width_m"] = round(max(0.15, w_along), 3)
                    sup["depth_m"] = round(max(0.15, d_perp), 3)

    enforce_carrier_hierarchy_and_support_dims(sync_initial=True)

    # Helper to clip a 1D interval [a, b] against a list of void-opening intervals [(v1, v2), ...]
    def subtract_void_intervals(a: float, b: float, voids: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        segs = [(a, b)]
        for v1, v2 in voids:
            next_segs: List[Tuple[float, float]] = []
            for s1, s2 in segs:
                if v2 <= s1 + 1e-4 or v1 >= s2 - 1e-4:
                    next_segs.append((s1, s2))
                else:
                    if v1 - s1 >= 0.30:
                        next_segs.append((s1, v1))
                    if s2 - v2 >= 0.30:
                        next_segs.append((v2, s2))
            segs = next_segs
        return segs

    def populate_all_beam_distributed_loads() -> None:
        """
        Computes piecewise distributed loads (Beam O.W + Exact Sub-Interval Slab Loads + Wall Loads)
        using baseline beam dimensions (`initial_width_m`, `initial_depth_m`) and full slab rib lengths
        (`lx_0` / `ly_0`) in a single pass per Eng. Yousef's Excel philosophy.
        """
        for idx_b, b in enumerate(beams):
            bid = b["id"]
            b_copy = beam_map[bid]
            c_left = max(0.0, float(b_copy.get("cantilever_left_m", 0.0)))

            bsx, bsy = float(b_copy.get("start_x", 0.0)), float(b_copy.get("start_y", 0.0))
            bex, bey = float(b_copy.get("end_x", 0.0)), float(b_copy.get("end_y", 0.0))
            b_horiz = abs(bex - bsx) >= abs(bey - bsy)
            b_w = float(b_copy.get("width_m", 0.40))
            b_h = float(b_copy.get("depth_m", 0.30))

            # Beam Self-Weight (always applied on all beams): O.W = b * h * 24.0 * 1.4
            w_sw = round(b_w * b_h * 24.0 * 1.4, 2)
            sw_eq_str = f"O.W = {b_w:.2f} × {b_h:.2f} × 24 × 1.4 = {w_sw:.2f} kN/m"
            sup1_world = get_beam_first_support_world_coord(b_copy)

            if b_copy.get("manual_loads_override") and b_copy.get("loads"):
                b_copy["loads"] = [dict(ld) for ld in b_copy["loads"] if not ld.get("is_transferred_reaction")]
            else:
                flags = ensure_beam_wall_flags(story_data, b_copy)
                thick_map = b_copy.setdefault("span_wall_thickness_cm", {})
                segments = get_beam_span_segments(b_copy)
                computed_loads: List[Dict[str, Any]] = []
                breakdown_list: List[Dict[str, Any]] = []

                for seg in segments:
                    skey = seg["key"]
                    sx1, sx2 = float(seg["x1"]), float(seg["x2"])
                    w_coord1 = sup1_world + (sx1 - c_left)
                    w_coord2 = sup1_world + (sx2 - c_left)
                    w_min, w_max = min(w_coord1, w_coord2), max(w_coord1, w_coord2)

                    # Identify void openings bordering this beam on Pos (+Y or +X) and Neg (-Y or -X) sides
                    voids_pos: List[Tuple[float, float]] = []
                    voids_neg: List[Tuple[float, float]] = []
                    for op in openings:
                        omin_x, omax_x = float(op.get("min_x", 0.0)), float(op.get("max_x", 0.0))
                        omin_y, omax_y = float(op.get("min_y", 0.0)), float(op.get("max_y", 0.0))
                        if b_horiz:
                            ov1, ov2 = max(w_min, omin_x), min(w_max, omax_x)
                            if ov2 - ov1 >= 0.30:
                                if abs(bsy - omin_y) <= 0.55 and (omin_y + omax_y) / 2.0 >= bsy:
                                    voids_pos.append((ov1, ov2))
                                elif abs(bsy - omax_y) <= 0.55 and (omin_y + omax_y) / 2.0 < bsy:
                                    voids_neg.append((ov1, ov2))
                        else:
                            ov1, ov2 = max(w_min, omin_y), min(w_max, omax_y)
                            if ov2 - ov1 >= 0.30:
                                if abs(bsx - omin_x) <= 0.55 and (omin_x + omax_x) / 2.0 >= bsx:
                                    voids_pos.append((ov1, ov2))
                                elif abs(bsx - omax_x) <= 0.55 and (omin_x + omax_x) / 2.0 < bsx:
                                    voids_neg.append((ov1, ov2))

                    # Collect exact slab load intervals [(ov1, ov2, add_w, tag_str, eq_str)] along [w_min, w_max]
                    slab_intervals: List[Tuple[float, float, float, str, str]] = []
                    for slb in slabs:
                        if slb.get("is_void", False):
                            continue
                        s_bounds = extract_slab_bounds(slb)
                        if s_bounds is None:
                            continue
                        smin_x, smax_x, smin_y, smax_y = s_bounds
                        lx_0 = max(0.5, smax_x - smin_x)
                        ly_0 = max(0.5, smax_y - smin_y)
                        rib_dir = int(slb.get("rib_direction_deg", slb.get("rib_angle_deg", 0)))
                        is_cant_slb = bool(slb.get("is_cantilever", False))
                        sid_lbl = str(slb.get("id", "S"))

                        # Full center-to-center / boundary rib span (no L_rib reduction per Excel philosophy)
                        if b_horiz and rib_dir == 90:
                            if abs(bsy - smin_y) <= 0.55 or abs(bsy - smax_y) <= 0.55:
                                ov1, ov2 = max(w_min, smin_x), min(w_max, smax_x)
                                if ov2 - ov1 >= 0.40:
                                    is_pos_side = ((smin_y + smax_y) / 2.0) >= bsy
                                    side_voids = voids_pos if is_pos_side else voids_neg
                                    trib_m = ly_0 if is_cant_slb else (ly_0 * 0.50)
                                    add_w = round(slab_wu_kpa * trib_m, 2)
                                    factor_txt = f"{ly_0:.2f}m[Cant]" if is_cant_slb else f"({ly_0:.2f}/2)m"
                                    eq_str = f"{sid_lbl}: {slab_wu_kpa:.2f}×{factor_txt}={add_w:.2f}"
                                    for c1, c2 in subtract_void_intervals(ov1, ov2, side_voids):
                                        slab_intervals.append((c1, c2, add_w, f"{sid_lbl}({add_w:.2f})", eq_str))
                        elif (not b_horiz) and rib_dir == 0:
                            if abs(bsx - smin_x) <= 0.55 or abs(bsx - smax_x) <= 0.55:
                                ov1, ov2 = max(w_min, smin_y), min(w_max, smax_y)
                                if ov2 - ov1 >= 0.40:
                                    is_pos_side = ((smin_x + smax_x) / 2.0) >= bsx
                                    side_voids = voids_pos if is_pos_side else voids_neg
                                    trib_m = lx_0 if is_cant_slb else (lx_0 * 0.50)
                                    add_w = round(slab_wu_kpa * trib_m, 2)
                                    factor_txt = f"{lx_0:.2f}m[Cant]" if is_cant_slb else f"({lx_0:.2f}/2)m"
                                    eq_str = f"{sid_lbl}: {slab_wu_kpa:.2f}×{factor_txt}={add_w:.2f}"
                                    for c1, c2 in subtract_void_intervals(ov1, ov2, side_voids):
                                        slab_intervals.append((c1, c2, add_w, f"{sid_lbl}({add_w:.2f})", eq_str))

                    # Build clean breakpoints along [w_min, w_max], snapping within 0.25m of span ends/joints
                    raw_cuts = [w_min, w_max]
                    for c1, c2, _, _, _ in slab_intervals:
                        raw_cuts.extend([c1, c2])
                    for v1, v2 in (voids_pos + voids_neg):
                        raw_cuts.extend([max(w_min, v1), min(w_max, v2)])
                    raw_cuts.sort()

                    clean_cuts = [w_min]
                    for pt in raw_cuts:
                        if pt <= w_min + 0.25:
                            continue
                        if pt >= w_max - 0.25:
                            continue
                        if pt - clean_cuts[-1] >= 0.30:
                            clean_cuts.append(round(pt, 3))
                    clean_cuts.append(w_max)

                    wall_on = bool(flags.get(skey, True))
                    t_wall_span_cm = float(thick_map.get(skey, default_t_wall_cm))
                    if not wall_on:
                        w_wall_seg = 0.0
                        wall_eq_str = "0.00 (No Wall)"
                    else:
                        if story_data.get("custom_wall_load_override", False) and abs(t_wall_span_cm - default_t_wall_cm) < 0.1:
                            w_wall_seg = round(default_wall_w, 2)
                            wall_eq_str = f"{w_wall_seg:.2f} kN/m"
                        else:
                            w_wall_seg = round(2.5 * (t_wall_span_cm / 20.0) * eff_wall_h * 1.4, 2)
                            if abs(t_wall_span_cm - 20.0) < 0.1:
                                wall_eq_str = f"2.5×{eff_wall_h:.1f}×1.4 = {w_wall_seg:.2f}"
                            else:
                                wall_eq_str = f"2.5×({t_wall_span_cm:.0f}/20)×{eff_wall_h:.1f}×1.4 = {w_wall_seg:.2f}"

                    sub_records: List[Dict[str, Any]] = []
                    for k_sub in range(len(clean_cuts) - 1):
                        sw1, sw2 = clean_cuts[k_sub], clean_cuts[k_sub + 1]
                        mid_w = (sw1 + sw2) / 2.0
                        w_slab_sub = 0.0
                        slab_tags: List[str] = []
                        slab_eq_parts: List[str] = []
                        for c1, c2, add_w, tag_s, eq_s in slab_intervals:
                            if c1 - 0.05 <= mid_w <= c2 + 0.05:
                                w_slab_sub = round(w_slab_sub + add_w, 2)
                                slab_tags.append(tag_s)
                                slab_eq_parts.append(eq_s)

                        sub_x1 = round(sx1 + (sw1 - w_min), 3)
                        sub_x2 = round(sx1 + (sw2 - w_min), 3)
                        if (
                            sub_records
                            and abs(sub_records[-1]["w_slab"] - w_slab_sub) < 0.01
                            and sub_records[-1]["slab_tags"] == slab_tags
                        ):
                            sub_records[-1]["x2"] = sub_x2
                            sub_records[-1]["end"] = sub_x2
                        else:
                            sub_records.append({
                                "x1": sub_x1,
                                "x2": sub_x2,
                                "start": sub_x1,
                                "end": sub_x2,
                                "w_slab": w_slab_sub,
                                "slab_tags": slab_tags,
                                "slab_eq_parts": slab_eq_parts,
                            })

                    for idx_sub, sr in enumerate(sub_records):
                        w_slab_seg = sr["w_slab"]
                        slab_tags = sr["slab_tags"]
                        slab_eq_parts = sr["slab_eq_parts"]
                        w_total_seg = round(w_sw + w_slab_seg + w_wall_seg, 2)

                        parts = [f"O.W={w_sw:.2f}"]
                        if w_slab_seg > 0.01:
                            parts.append(f"Slabs[{'+'.join(slab_tags)}]={w_slab_seg:.2f}")
                        else:
                            parts.append("Slabs=0.00")
                        if w_wall_seg > 0.01:
                            parts.append(f"Wall({t_wall_span_cm:.0f}cm)={w_wall_seg:.2f}")
                        else:
                            parts.append("Wall=0.00")

                        lbl_prefix = seg["label"] if len(sub_records) == 1 else f"{seg['label']} [{sr['x1']:.2f}->{sr['x2']:.2f}m]"
                        desc_label = f"{lbl_prefix}: {' + '.join(parts)} = {w_total_seg:.2f} kN/m"
                        formula_detail = (
                            f"w_total = O.W ({w_sw:.2f} [{b_w:.2f}×{b_h:.2f}×24×1.4]) + w_Slab ({w_slab_seg:.2f}"
                            f"{' [' + '; '.join(slab_eq_parts) + ']' if slab_eq_parts else ''}) + W_wall ({w_wall_seg:.2f} [{wall_eq_str}]) = {w_total_seg:.2f} kN/m"
                        )

                        computed_loads.append({
                            "type": "D",
                            "span_key": skey,
                            "span_label": lbl_prefix,
                            "x1": sr["x1"],
                            "x2": sr["x2"],
                            "start": sr["start"],
                            "end": sr["end"],
                            "val": w_total_seg,
                            "mag": w_total_seg,
                            "w_sw": w_sw,
                            "sw_eq": sw_eq_str,
                            "w_slab": w_slab_seg,
                            "slab_eq_parts": slab_eq_parts,
                            "w_wall": w_wall_seg,
                            "wall_thickness_cm": t_wall_span_cm,
                            "wall_eq": wall_eq_str,
                            "wall_enabled": wall_on,
                            "label": desc_label,
                            "formula_str": formula_detail,
                            "source_note": f"[{' + '.join(parts)}]",
                        })
                        breakdown_list.append(computed_loads[-1])

                for cld in b_copy.get("custom_loads", []):
                    computed_loads.append(dict(cld))

                b_copy["loads"] = computed_loads
                b_copy["load_breakdown"] = breakdown_list
                if idx_b < len(orig_beams):
                    orig_beams[idx_b]["span_wall_flags"] = dict(flags)
                    orig_beams[idx_b]["span_wall_thickness_cm"] = dict(thick_map)
                    orig_beams[idx_b]["loads"] = [dict(x) for x in computed_loads]
                    orig_beams[idx_b]["load_breakdown"] = [dict(x) for x in breakdown_list]
                    orig_beams[idx_b]["supports"] = [dict(s) for s in b_copy.get("supports", [])]

    beam_results: Dict[str, Dict[str, Any]] = {}
    beam_designs: Dict[str, Dict[str, Any]] = {}
    story_design_mode = str(story_data.get("beam_design_mode", "double_as_min"))
    story_main_db = int(story_data.get("default_main_bar_dia_mm", 16))
    story_stir_db = int(story_data.get("default_stirrup_dia_mm", 8))

    # Single-Pass Topological Analysis + Post-Analysis VBA Section Sizing (Eng. Yousef Excel Philosophy):
    # - Loads (O.W + w_Slab + W_wall) are computed ONCE from baseline beam dimensions and full slab spans.
    # - Secondary beams are solved first and transfer centerline point reactions onto carrier beams.
    # - After solving each beam's Mu/Vu once, design_beam_aci318 runs VBA Sub ReDesign_Sec (+100 mm step)
    #   purely during section design without feeding enlarged dimensions back into O.W or L_rib.
    populate_all_beam_distributed_loads()

    for bid in ordered_ids:
        bm = beam_map[bid]
        if "design_mode" not in bm:
            bm["design_mode"] = story_design_mode
        if "main_bar_dia_mm" not in bm:
            bm["main_bar_dia_mm"] = story_main_db
        if "stirrup_dia_mm" not in bm:
            bm["stirrup_dia_mm"] = int(story_data.get("default_stirrup_dia_mm", 6 if str(bm.get("beam_kind", "hidden")) == "hidden" else 8))

        prev_w = float(bm.get("width_m", 0.40))
        prev_h = float(bm.get("depth_m", 0.30))

        res = solve_continuous_beam_analytical(bm, fc_mpa, fy_mpa)
        res["loads_applied"] = [dict(ld) for ld in bm.get("loads", [])]
        beam_results[bid] = res
        des = design_beam_aci318(
            bm,
            res,
            fc_mpa,
            fy_mpa,
            design_mode=str(bm.get("design_mode", story_design_mode)),
            bar_dia_mm=int(bm.get("main_bar_dia_mm", story_main_db)),
            stirrup_dia_mm=int(bm.get("stirrup_dia_mm", story_stir_db)),
            auto_size_section=(not bm.get("lock_section_dimensions", False)),
        )
        beam_designs[bid] = des

        new_w = round(float(des.get("b_mm", prev_w * 1000.0)) / 1000.0, 3)
        new_h = round(float(des.get("h_mm", prev_h * 1000.0)) / 1000.0, 3)
        bm["width_m"] = new_w
        bm["depth_m"] = new_h

        _log_eng(
            "BEAM_SOLVE_DESIGN",
            f"Beam {bid} ({bm.get('beam_kind','hidden').upper()}) Init={bm.get('initial_width_m', new_w):.2f}x{bm.get('initial_depth_m', new_h):.2f} -> Designed={new_w:.2f}x{new_h:.2f}m",
            {
                "loads": [ld.get("label", ld.get("formula_str", "")) for ld in res.get("loads_applied", [])],
                "reactions": res.get("reactions"),
                "max_pos_mu_knm": res.get("max_pos_mu_knm"),
                "max_neg_face_mu_knm": res.get("max_neg_face_mu_knm"),
                "max_face_vu_kn": res.get("max_face_vu_kn"),
                "span_shears_kn": [s.get("max_abs_vu_kn") for s in res.get("span_positive_moments", [])],
                "stirrups": des.get("stirrups"),
                "sizing_iterations": des.get("sizing_iterations", []),
            },
        )

        # Sync updated loads and sized dimensions back to story_data["beams"]
        for orig_b in orig_beams:
            if orig_b.get("id") == bid:
                orig_b["width_m"] = bm["width_m"]
                orig_b["depth_m"] = bm["depth_m"]
                orig_b["initial_width_m"] = bm.get("initial_width_m", bm["width_m"])
                orig_b["initial_depth_m"] = bm.get("initial_depth_m", bm["depth_m"])
                orig_b["loads"] = [dict(ld) for ld in bm.get("loads", [])]
                orig_b["design_mode"] = bm["design_mode"]
                orig_b["main_bar_dia_mm"] = bm["main_bar_dia_mm"]
                orig_b["stirrup_dia_mm"] = bm["stirrup_dia_mm"]
                break

        # Transfer reactions from this secondary beam onto any carrier beam it rests on
        # Measuring position strictly from the Carrier Beam's Support Centerlines!
        bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        bm_horiz = abs(bex - bsx) >= abs(bey - bsy)
        sec_center_coord = bsy if bm_horiz else bsx

        for sup in bm.get("supports", []):
            if sup.get("kind") == "beam" and sup.get("target_id") in beam_map:
                s_idx = int(sup.get("support_index", 1))
                r_kn = round(float(res["reactions"].get(s_idx, 0.0)), 2)
                carrier = beam_map[sup["target_id"]]
                c_left_car = max(0.0, float(carrier.get("cantilever_left_m", 0.0)))
                car_sup1_world = get_beam_first_support_world_coord(carrier)
                car_tot_len = c_left_car + sum(float(s) for s in carrier.get("spans", [4.0])) + max(0.0, float(carrier.get("cantilever_right_m", 0.0)))

                # Exact distance along carrier from Carrier Support 1 Centerline to Secondary Beam Centerline
                dist_from_sup1 = round(abs(sec_center_coord - car_sup1_world), 3)
                pos_x = round(min(max(0.0, c_left_car + dist_from_sup1), car_tot_len), 3)
                sup["pos_on_carrier_m"] = pos_x

                carrier["loads"] = list(carrier.get("loads", [])) + [{
                    "type": "P",
                    "x": pos_x,
                    "pos": pos_x,
                    "dist_from_sup1_m": dist_from_sup1,
                    "val": r_kn,
                    "mag": r_kn,
                    "source_beam_id": bid,
                    "source_beam": bid,
                    "is_transferred_reaction": True,
                    "label": f"P = {r_kn:.2f} kN (from {bid} @ {pos_x:.2f}m)",
                    "formula_str": f"P({bid}) = {r_kn:.2f} kN transferred at x = {pos_x:.2f} m",
                }]

    # Ensure carrier beam final section depth remains >= any enlarged secondary beam without altering baseline initial_* dims
    enforce_carrier_hierarchy_and_support_dims(sync_initial=False)

    column_records = []
    for col in columns:
        if not col.get("active", True):
            continue
        cid = col["id"]
        cx, cy = float(col["x"]), float(col["y"])
        b_m, h_m = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))

        framing_directions: Dict[str, Optional[Dict[str, Any]]] = {
            "North": None,
            "South": None,
            "East": None,
            "West": None,
        }
        total_beam_reaction_kn = 0.0
        mux_knm = 0.0
        muy_knm = 0.0

        for bm in beam_map.values():
            bid = bm["id"]
            res = beam_results.get(bid)
            if not res:
                continue
            sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
            is_horiz = abs(ex - sx) >= abs(ey - sy)

            for sup in bm.get("supports", []):
                if sup.get("kind") == "column" and sup.get("target_id") == cid:
                    s_idx = int(sup.get("support_index", 1))
                    r_kn = res["reactions"].get(s_idx, 0.0)
                    m_end = res["support_moments"][s_idx - 1] if (s_idx - 1) < len(res["support_moments"]) else 0.0
                    total_beam_reaction_kn += r_kn

                    beam_info = {
                        "beam_id": bid,
                        "kind": bm.get("beam_kind", "hidden"),
                        "width_m": bm.get("width_m", 0.40),
                        "depth_m": bm.get("depth_m", 0.30),
                        "reaction_kn": round(r_kn, 2),
                    }
                    if is_horiz:
                        muy_knm += abs(m_end) * 0.5 + 8.5
                        mid_x = (sx + ex) / 2.0
                        if mid_x >= cx:
                            framing_directions["East"] = beam_info
                        if mid_x <= cx:
                            framing_directions["West"] = beam_info
                    else:
                        mux_knm += abs(m_end) * 0.5 + 6.5
                        mid_y = (sy + ey) / 2.0
                        if mid_y >= cy:
                            framing_directions["North"] = beam_info
                        if mid_y <= cy:
                            framing_directions["South"] = beam_info

        is_double_h = bool(col.get("double_height", False))
        col_eff_h = round(story_h * 2.0, 2) if is_double_h else round(story_h, 2)
        col["effective_height_m"] = col_eff_h
        self_wt_kn = round(b_m * h_m * col_eff_h * 25.0 * 1.2, 2)
        story_pu_kn = round(max(45.0, total_beam_reaction_kn) + self_wt_kn, 2)
        col_design = design_column_and_pm_curve(
            cid,
            b_m,
            h_m,
            story_pu_kn,
            round(mux_knm, 1),
            round(muy_knm, 1),
            fc_mpa,
            fy_mpa,
            lu_m=col_eff_h,
            double_height=is_double_h,
        )

        column_records.append({
            "column_id": cid,
            "x": cx,
            "y": cy,
            "b_m": b_m,
            "h_m": h_m,
            "double_height": is_double_h,
            "in_slab_opening": bool(col.get("in_slab_opening", False)),
            "effective_height_m": col_eff_h,
            "story_pu_kn": story_pu_kn,
            "mux_knm": round(mux_knm, 2),
            "muy_knm": round(muy_knm, 2),
            "framing_4way": framing_directions,
            "design": col_design,
        })

    # Post-sizing verification: if any enlarged Hidden beam expanded into an opening/boundary, convert & cascade safely
    conv_ids, conv_alerts = enforce_opening_adjacent_drop_beams_and_cascade(story_data)

    _log_eng(
        "ANALYSIS_DONE",
        f"Completed analysis for {story_data.get('story_id', 'Story')} ({len(beam_results)} beams, {len(column_records)} columns)",
        {"post_sizing_drop_conversions": conv_ids, "alerts": conv_alerts},
    )

    return {
        "ordered_beam_ids": ordered_ids,
        "beam_results": beam_results,
        "beam_designs": beam_designs,
        "column_records": column_records,
        "slab_designs": slab_designs,
        "hollow_block_summary": hb_summary,
        "post_sizing_alerts": conv_alerts,
    }


def design_beam_aci318(
    beam: Dict[str, Any],
    analysis_res: Dict[str, Any],
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
    design_mode: Optional[str] = None,
    bar_dia_mm: Optional[int] = None,
    main_bar_dia_mm: Optional[int] = None,
    stirrup_dia_mm: Optional[int] = None,
    auto_size_section: bool = True,
) -> Dict[str, Any]:
    """
    Designs a reinforced concrete Hidden or Drop beam per ACI 318, Eng. Yousef's Code PDFs,
    and the exact Excel VBA `Sub ReDesign_Sec()` / `Sub ReDesgin()` algorithm (`all_code_9bb47b25.txt` lines 11189–11703):
    1. Iterative Section Sizing (`+100 mm` step):
       - Governing absolute moment across all supports & mid-spans: `M_max = max(|M_i|)`
       - `dc = 25 mm`, `d0 = h - dc - ds - db/2`, `asb = 3.14 * db² / 4`
       - `pmin = 1.4 / fy` (`0.004` for `fy = 350 MPa`), `pmax = 0.75 * 0.85 * β1 * (fc'/fy) * (600/(600+fy))` (`0.01956`)
       - `nbs = int(((B + db) - (6 * ds + 45)) / (db + 25))` (max bars in 1 single row)
       - **Hidden Beam (`beam_kind == 'hidden'`):**
         Starts at `B_min = 400 mm` (or `initial_width_m * 1000`), `h = slab_thickness_mm`.
         Increments `B = B + 100 mm` whenever:
           a) `1 - 2.36 * Ku < 0` (concrete compression failure),
           b) `ρ > ρ_max`, or
           c) `nbr > nbs` (bars exceed 1 single layer — hidden beams must fit all bars in 1 single row!).
       - **Drop Beam (`beam_kind == 'drop'`):**
         Starts at `B = wall_width (200 mm)`, `h_min = 400 mm` (or `initial_depth_m * 1000`).
         Increments `h = h + 100 mm` whenever `1 - 2.36*Ku < 0` or `ρ > ρ_max`.
         When `nbr > nbs`, places bars in `nrow = ceil(nbr / nbs)` layers, computes weighted centroid
         `ddc = sum(n_i * d_i) / nbr` (with vertical spacing `25 + db` between layers), updates `d = h - ddc`,
         and repeats the loop (increasing `h = h + 100 mm` if `1 - 2.36*Ku < 0`, `ρ > ρ_max`, `nrow > 3`, or `ddc >= 0.45 * h`).
    2. Minimum & Maximum Constructive Bars per Excel Sheet4:
       - `min_bars = int((pmin * B * d) / asb) + 1` (minimum 2 bars)
       - `max_bars = int((pmax * B * d) / asb)`
    """
    raw_mode = str(design_mode or beam.get("design_mode", "double_as_min")).lower()
    mode_norm = "single" if raw_mode == "single" else "double_as_min"

    b_kind = str(beam.get("beam_kind", "hidden")).lower()
    default_db = 14 if b_kind == "hidden" else 16
    db_mm = int(bar_dia_mm or main_bar_dia_mm or beam.get("main_bar_dia_mm", default_db))
    if db_mm not in (12, 14, 16, 18, 20, 22, 25, 28, 32):
        db_mm = default_db
    dst_mm = int(stirrup_dia_mm or beam.get("stirrup_dia_mm", 6 if b_kind == "hidden" else 8))
    if dst_mm not in (6, 8, 10, 12):
        dst_mm = 6 if b_kind == "hidden" else 8

    # Minimum dimension floors per v2.4.3 / v2.4.10 standards
    kind_b = str(beam.get("beam_kind", "hidden")).lower()
    if kind_b == "hidden":
        floor_dim = float(beam.get("min_width_mm", 300.0))
        if auto_size_section and not beam.get("lock_section_dimensions", False):
            beam["initial_width_m"] = max(float(beam.get("initial_width_m", 0.30)), floor_dim / 1000.0)
    else:
        floor_dim = float(beam.get("min_depth_mm", 400.0))
        if auto_size_section and not beam.get("lock_section_dimensions", False):
            beam["initial_depth_m"] = max(float(beam.get("initial_depth_m", 0.40)), floor_dim / 1000.0)

    # Baseline dimensions for iterative sizing (reset to initial baseline if auto_size_section is True and not locked)
    if auto_size_section and not beam.get("lock_section_dimensions", False):
        init_w_m = float(beam.get("initial_width_m", 0.30 if b_kind == "hidden" else 0.20))
        init_h_m = float(beam.get("initial_depth_m", beam.get("depth_m", 0.30 if b_kind == "hidden" else 0.40)))
        if b_kind == "drop":
            init_h_m = _snap_drop_depth_m(init_h_m, 0.40)
        b_mm = round(max(300.0 if b_kind == "hidden" else 150.0, init_w_m * 1000.0))
        h_mm = round(max(200.0 if b_kind == "hidden" else 400.0, init_h_m * 1000.0))
    else:
        b_mm = round(float(beam.get("width_m", 0.40 if b_kind == "hidden" else 0.20)) * 1000.0)
        h_mm = round(float(beam.get("depth_m", 0.30 if b_kind == "hidden" else 0.40)) * 1000.0)

    init_b_mm = b_mm
    init_h_mm = h_mm

    dc_mm = 25.0  # Clear concrete cover per Excel Sheet4 (`dc = 25 mm`)
    d_single_layer_mm = round(max(100.0, h_mm - dc_mm - dst_mm - (db_mm / 2.0)), 1)
    d_prime_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 1)

    beta1 = 0.85 if fc_mpa <= 30.0 else max(0.65, round(0.85 - (0.05 / 7.0) * (fc_mpa - 30.0), 3))
    # Balanced reinforcement ratio: rho_b = 0.85 * beta1 * (fc'/fy) * (600 / (600 + fy))
    rho_b = 0.85 * beta1 * (fc_mpa / fy_mpa) * (600.0 / (600.0 + fy_mpa))
    # ACI 318 tension-controlled / maximum singly reinforced ratio: rho_max = 0.75 * rho_b
    rho_max = 0.75 * rho_b
    omega_max = rho_max * (fy_mpa / fc_mpa)
    # ku_max = omega_max * (1 - omega_max / 1.7) (~0.259 for C25/Gr420)
    ku_max = omega_max * (1.0 - omega_max / 1.7)
    pmin_excel = round(1.4 / fy_mpa, 5)
    pmax_excel = round(rho_max, 5)
    # Exact Excel bar area: 3.14 * db^2 / 4 (e.g. 153.86 mm² for Φ14)
    asb_excel = round(3.14 * (db_mm ** 2) / 4.0, 2)

    # Governing moment M_max across all support faces and span mid-spans
    pos_mu = float(analysis_res.get("max_pos_mu_knm", 0.0))
    neg_mu = abs(float(analysis_res.get("max_neg_center_mu_knm", analysis_res.get("max_neg_face_mu_knm", 0.0))))
    sup_table = analysis_res.get("support_critical_table", [])
    span_pos_list = analysis_res.get("span_positive_moments", analysis_res.get("span_critical_table", []))

    all_station_moments: List[float] = [abs(pos_mu), abs(neg_mu)]
    for sup in sup_table:
        all_station_moments.append(abs(float(sup.get("centerline_neg_mu_knm", sup.get("m_center_knm", sup.get("face_neg_mu_knm", 0.0))))))
    for sp_info in span_pos_list:
        all_station_moments.append(abs(float(sp_info.get("max_pos_mu_knm", 0.0))))
    m_max_gov = max(all_station_moments) if all_station_moments else 0.0

    sizing_iterations: List[Dict[str, Any]] = []
    ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
    nrow_gov = 1
    d_mm = d_single_layer_mm

    # Execute exact VBA `Sub ReDesign_Sec()` iterative section sizing (+100 mm step)
    if auto_size_section and not beam.get("lock_section_dimensions", False) and m_max_gov > 0.05:
        if b_kind == "hidden":
            # Hidden beam (bt = 0): depth h is fixed to slab thickness; width B increments by +100 mm
            d_mm = round(max(90.0, h_mm - dc_mm - dst_mm - (db_mm / 2.0)), 1)
            for _iter in range(25):
                if b_mm >= 3000.0:
                    break
                nbs_cur = max(2, int(math.floor(((b_mm + db_mm) - (6.0 * dst_mm + 45.0)) / max(1.0, db_mm + 25.0))))
                ku_cur = (m_max_gov * 1_000_000.0) / max(1.0, 0.90 * b_mm * fc_mpa * (d_mm ** 2))
                if (1.0 - 2.36 * ku_cur) < 0.0:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": "1 - 2.36*Ku < 0 -> B + 100 mm"})
                    b_mm = min(3000.0, b_mm + 100.0)
                    continue
                w_cur = (1.0 - math.sqrt(max(0.0, 1.0 - 2.36 * ku_cur))) / 1.18
                p_cur = w_cur * (fc_mpa / fy_mpa)
                if p_cur > pmax_excel:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": f"ρ ({p_cur:.5f}) > ρ_max ({pmax_excel:.5f}) -> B + 100 mm"})
                    b_mm = min(3000.0, b_mm + 100.0)
                    continue
                ast_cur = p_cur * b_mm * d_mm
                nbr_cur = int(math.floor(ast_cur / asb_excel)) + 1
                min_b_cur = int(math.floor((pmin_excel * b_mm * d_mm) / asb_excel)) + 1
                if nbr_cur < min_b_cur:
                    nbr_cur = min_b_cur
                if nbr_cur > nbs_cur:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": f"nbr ({nbr_cur}) > nbs ({nbs_cur}) -> B + 100 mm"})
                    b_mm = min(3000.0, b_mm + 100.0)
                    continue
                nrow_gov = 1
                break
        else:
            # Drop beam (bt = 1): width B is fixed; depth h increments by +100 mm, with multi-row centroid ddc
            nbs_cur = max(2, int(math.floor(((b_mm + db_mm) - (6.0 * dst_mm + 45.0)) / max(1.0, db_mm + 25.0))))
            ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
            d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
            for _iter in range(25):
                if h_mm >= 2000.0:
                    break
                if d_mm <= 60.0 or ddc_weighted_mm >= 0.45 * h_mm:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": "ddc >= 0.45*h -> h + 100 mm"})
                    h_mm = min(2000.0, h_mm + 100.0)
                    ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
                    d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
                    continue
                ku_cur = (m_max_gov * 1_000_000.0) / max(1.0, 0.90 * b_mm * fc_mpa * (d_mm ** 2))
                if (1.0 - 2.36 * ku_cur) < 0.0:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": "1 - 2.36*Ku < 0 -> h + 100 mm"})
                    h_mm = min(2000.0, h_mm + 100.0)
                    ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
                    d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
                    continue
                w_cur = (1.0 - math.sqrt(max(0.0, 1.0 - 2.36 * ku_cur))) / 1.18
                p_cur = w_cur * (fc_mpa / fy_mpa)
                if p_cur > pmax_excel:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": f"ρ ({p_cur:.5f}) > ρ_max ({pmax_excel:.5f}) -> h + 100 mm"})
                    h_mm = min(2000.0, h_mm + 100.0)
                    ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
                    d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
                    continue
                ast_cur = p_cur * b_mm * d_mm
                nbr_cur = int(math.floor(ast_cur / asb_excel)) + 1
                min_b_cur = int(math.floor((pmin_excel * b_mm * d_mm) / asb_excel)) + 1
                if nbr_cur < min_b_cur:
                    nbr_cur = min_b_cur
                if nbr_cur <= nbs_cur:
                    nrow_gov = 1
                    break
                # Multi-row calculation per VBA lines 11386–11408
                if nbr_cur % nbs_cur == 0:
                    nrow_try = nbr_cur // nbs_cur
                else:
                    nrow_try = (nbr_cur // nbs_cur) + 1
                if nrow_try > 3:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": f"nrow ({nrow_try}) > 3 rows -> h + 100 mm"})
                    h_mm += 100.0
                    ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
                    d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
                    continue
                rem_bars = nbr_cur
                dd_first = dc_mm + dst_mm + (db_mm / 2.0)
                sum_nd = 0.0
                for r_idx in range(1, nrow_try + 1):
                    bars_in_row = nbs_cur if (rem_bars - nbs_cur >= 0) else rem_bars
                    row_d = dd_first + (r_idx - 1) * (25.0 + db_mm)
                    sum_nd += bars_in_row * row_d
                    rem_bars = max(0, rem_bars - nbs_cur)
                new_ddc = round(sum_nd / max(1, nbr_cur), 2)
                new_d = round(h_mm - new_ddc, 1)
                if abs(new_d - d_mm) < 0.2:
                    # Also check ACI 318 Zone 5 Shear Limit (Vs <= 2/3 sqrt(fc') bw d) for Drop Beams
                    vu_max_abs = abs(float(analysis_res.get("max_face_vu_kn", 0.0)))
                    vc_try = (math.sqrt(fc_mpa) * b_mm * new_d) / 6000.0
                    vs_req_try = max(0.0, (vu_max_abs / 0.85) - vc_try)
                    vs2_lim_try = (2.0 * math.sqrt(fc_mpa) * b_mm * new_d) / 3000.0
                    if vs_req_try > vs2_lim_try and h_mm < 1900.0:
                        sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": f"Shear Zone 5 (Vs={vs_req_try:.1f} > 2/3√fc'bwd={vs2_lim_try:.1f}) -> h + 100 mm"})
                        h_mm += 100.0
                        ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 2)
                        d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
                        continue
                    nrow_gov = nrow_try
                    ddc_weighted_mm = new_ddc
                    d_mm = new_d
                    break
                nrow_gov = nrow_try
                ddc_weighted_mm = new_ddc
                d_mm = new_d

            # Final Zone 5 Shear check if loop exited via nrow_cur <= nbs_cur
            for _sh_iter in range(10):
                vu_max_abs = abs(float(analysis_res.get("max_face_vu_kn", 0.0)))
                vc_try = (math.sqrt(fc_mpa) * b_mm * d_mm) / 6000.0
                vs_req_try = max(0.0, (vu_max_abs / 0.85) - vc_try)
                vs2_lim_try = (2.0 * math.sqrt(fc_mpa) * b_mm * d_mm) / 3000.0
                if vs_req_try > vs2_lim_try and h_mm < 1900.0:
                    sizing_iterations.append({"b_mm": b_mm, "h_mm": h_mm, "reason": f"Shear Zone 5 (Vs={vs_req_try:.1f} > 2/3√fc'bwd={vs2_lim_try:.1f}) -> h + 100 mm"})
                    h_mm += 100.0
                    d_mm = round(max(100.0, h_mm - ddc_weighted_mm), 1)
                else:
                    break

    # Finalize section geometry after iterative sizing
    beam["width_m"] = round(b_mm / 1000.0, 3)
    beam["depth_m"] = round(h_mm / 1000.0, 3)

    if b_kind == "hidden":
        ddc_weighted_mm = round(dc_mm + dst_mm + (db_mm / 2.0), 1)
        d_mm = round(max(90.0, h_mm - ddc_weighted_mm), 1)

    n_max_single_layer = max(
        2,
        int(math.floor(((b_mm + db_mm) - (6.0 * dst_mm + 45.0)) / max(1.0, db_mm + 25.0))),
    )

    # Excel Sheet4 min bars & max bars:
    # min_bars = Int((pmin * B * D) / asb) + 1
    # max_bars = Int((pmax * B * D) / asb)
    as_min_mm2 = round(pmin_excel * b_mm * d_mm, 1)
    min_bars_excel = max(2, int(math.floor((pmin_excel * b_mm * d_mm) / max(1.0, asb_excel))) + 1)
    max_bars_excel = max(min_bars_excel, int(math.floor((pmax_excel * b_mm * d_mm) / max(1.0, asb_excel))))
    n_min_cont = min_bars_excel
    as_min_prov_mm2 = round(n_min_cont * asb_excel, 2)

    def eval_double_reinf_capacity_nmm(as_tension_mm2: float, as_comp_mm2: float) -> Dict[str, float]:
        denom = max(1.0, 0.85 * fc_mpa * b_mm * beta1)
        x1 = (as_tension_mm2 * fy_mpa - 600.0 * as_comp_mm2) / denom
        x2 = (600.0 * as_comp_mm2 * d_prime_mm) / denom
        disc = max(0.0, (x1 * x1) + 4.0 * x2)
        c_depth = max(1e-3, (x1 + math.sqrt(disc)) / 2.0)
        fs_prime = min(fy_mpa, max(0.0, 600.0 * ((c_depth - d_prime_mm) / c_depth)))
        as2 = (as_comp_mm2 * fs_prime) / fy_mpa
        as1 = max(0.0, as_tension_mm2 - as2)
        a_depth = (as1 * fy_mpa) / max(1.0, 0.85 * fc_mpa * b_mm)
        m1_nmm = as1 * fy_mpa * max(10.0, d_mm - a_depth / 2.0)
        m2_nmm = as_comp_mm2 * fs_prime * max(10.0, d_mm - d_prime_mm)
        mn_nmm = m1_nmm + m2_nmm
        return {
            "x1_mm": round(x1, 2),
            "x2_mm2": round(x2, 2),
            "c_mm": round(c_depth, 2),
            "C_mm": round(c_depth, 2),
            "a_mm": round(a_depth, 2),
            "fs_prime_mpa": round(fs_prime, 1),
            "comp_steel_yields": (fs_prime >= fy_mpa - 0.1),
            "as1_mm2": round(as1, 1),
            "as2_mm2": round(as2, 1),
            "phi_mn_knm": round(0.90 * mn_nmm / 1e6, 2),
        }

    def calc_flexural_section(mu_knm: float) -> Dict[str, Any]:
        """
        Matches Excel Sheet4 (`5_e8049e44.PNG`) & VBA `Sub ReDesign_Sec()` / `Sub ReDesgin()`:
        - Ku = (Mu * 10^6) / (0.9 * b * fc' * d^2)
        - ω  = (1 - sqrt(1 - 2.36 * Ku)) / 1.18
        - ρ  = ω * (fc' / fy)
        - As = ρ * (b * d)
        - Nbar = Int(As / As_one_bar) + 1 (clamped >= min_bars_excel)
        """
        mu_abs = abs(float(mu_knm))
        ku_raw = (mu_abs * 1_000_000.0) / max(1.0, 0.90 * b_mm * fc_mpa * (d_mm ** 2))
        ku_val = round(ku_raw, 5)
        disc_raw = 1.0 - 2.36 * ku_raw

        is_locked_sec = bool(beam.get("lock_section_dimensions", False)) or (not auto_size_section)
        # Item 3: In locked section mode, if ku_raw > ku_max or (1 - 2.36*ku_raw) < 0, warn and set As_req = None
        if is_locked_sec and (ku_raw > ku_max or disc_raw < 0.0):
            over_msg = "OVER-REINFORCED (ρ>ρmax): INCREASE SECTION OR ADD COMPRESSION STEEL"
            return {
                "mu_knm": round(mu_abs, 2),
                "ku": ku_val,
                "omega": None,
                "rho": None,
                "rho_act": None,
                "as_calc_mm2": None,
                "as_single_calc_mm2": None,
                "as_min_mm2": as_min_mm2,
                "as_req_mm2": None,
                "as_prov_mm2": None,
                "as_one_bar_mm2": asb_excel,
                "as_prime_mm2": 0.0,
                "n_min_cont": min_bars_excel,
                "n_additional": 0,
                "n_total": min_bars_excel,
                "n_max_per_layer": n_max_single_layer,
                "num_layers": 1,
                "bars_short": "OVER-REINFORCED",
                "bars_callout": over_msg,
                "additional_bars": "None",
                "x1_mm": 0.0,
                "x2_mm2": 0.0,
                "c_mm": 0.0,
                "C_mm": 0.0,
                "a_mm": 0.0,
                "fs_prime_mpa": 0.0,
                "comp_steel_yields": False,
                "phi_mn_knm": 0.0,
                "over_reinforced": True,
                "status": over_msg,
            }

        disc_s = max(0.0, disc_raw)
        omega_raw = (1.0 - math.sqrt(disc_s)) / 1.18
        omega_val = round(omega_raw, 5)
        rho_raw = omega_raw * (fc_mpa / fy_mpa)
        rho_single = round(rho_raw, 4)
        as_single_calc = round(rho_single * b_mm * d_mm, 2)

        if mu_abs <= 0.05:
            as_calc = 0.0
            n_total = min_bars_excel
        else:
            as_calc = as_single_calc
            n_from_as = int(math.floor(as_calc / max(1.0, asb_excel))) + 1
            n_total = max(min_bars_excel, n_from_as)

        as_req = round(max(as_calc, as_min_mm2), 2)
        n_additional = max(0, n_total - min_bars_excel)
        as_prov = round(n_total * asb_excel, 1)
        rho_act = round(as_prov / max(1.0, b_mm * d_mm), 5)
        num_layers = 1 if n_total <= n_max_single_layer else int(math.ceil(n_total / max(1, n_max_single_layer)))

        as_comp_used = as_min_prov_mm2 if mode_norm == "double_as_min" else 0.0
        eq_prov = eval_double_reinf_capacity_nmm(as_prov, as_comp_used)

        if n_additional > 0:
            bars_callout = f"{n_total}Φ{db_mm} ({min_bars_excel}Φ{db_mm} Cont. + {n_additional}Φ{db_mm} Add.)"
            add_short = f"{n_additional} Φ {db_mm}"
        else:
            bars_callout = f"{n_total}Φ{db_mm} ({min_bars_excel}Φ{db_mm} Cont.)"
            add_short = "None"
        bars_short = f"{n_total} Φ {db_mm}"

        return {
            "mu_knm": round(mu_abs, 2),
            "ku": ku_val,
            "omega": omega_val,
            "rho": rho_single,
            "rho_act": rho_act,
            "as_calc_mm2": as_calc,
            "as_single_calc_mm2": as_single_calc,
            "as_min_mm2": as_min_mm2,
            "as_req_mm2": as_req,
            "as_prov_mm2": as_prov,
            "as_one_bar_mm2": asb_excel,
            "as_prime_mm2": round(as_comp_used, 1),
            "n_min_cont": min_bars_excel,
            "n_additional": n_additional,
            "n_total": n_total,
            "n_max_per_layer": n_max_single_layer,
            "num_layers": num_layers,
            "bars_short": bars_short,
            "bars_callout": bars_callout,
            "additional_bars": add_short,
            "x1_mm": eq_prov["x1_mm"],
            "x2_mm2": eq_prov["x2_mm2"],
            "c_mm": eq_prov["c_mm"],
            "C_mm": eq_prov["C_mm"],
            "a_mm": eq_prov["a_mm"],
            "fs_prime_mpa": eq_prov["fs_prime_mpa"],
            "comp_steel_yields": eq_prov["comp_steel_yields"],
            "phi_mn_knm": eq_prov["phi_mn_knm"],
        }

    # Page 13 Shear Stirrup Design: Vc = (1/6) * sqrt(fc') * bw * d, φ = 0.85
    vc_kn = round((math.sqrt(fc_mpa) * b_mm * d_mm) / 6000.0, 2)
    phi_shear = 0.85
    phi_vc = round(phi_shear * vc_kn, 2)
    n_legs = 4 if b_mm >= 350.0 else 2
    av_mm2 = round(n_legs * (3.14 * (dst_mm ** 2) / 4.0), 2)

    def calc_stirrups_detail(v_kn: float) -> Dict[str, Any]:
        vu_val = abs(float(v_kn))
        vs1_limit_kn = round((math.sqrt(fc_mpa) * b_mm * d_mm) / 3000.0, 2)
        vs2_limit_kn = round((2.0 * math.sqrt(fc_mpa) * b_mm * d_mm) / 3000.0, 2)
        s_min_reinf = (av_mm2 * fy_mpa) / max(1.0, 0.35 * b_mm)

        if vu_val <= 0.5 * phi_vc:
            s_max = min(d_mm / 2.0, 600.0, 200.0)
            s_adopt = max(100, int(math.floor(s_max / 10.0) * 10))
            zone_lbl = "Zone 1 (Vu <= 0.5 φVc)"
            vs_req_kn = 0.0
        elif vu_val <= phi_vc:
            s_max = min(s_min_reinf, d_mm / 2.0, 600.0, 200.0)
            s_adopt = max(100, int(math.floor(s_max / 10.0) * 10))
            zone_lbl = "Zone 2 (0.5 φVc < Vu <= φVc)"
            vs_req_kn = 0.0
        else:
            vs_req_kn = round((vu_val / phi_shear) - vc_kn, 2)
            s_req = (av_mm2 * fy_mpa * d_mm) / max(1.0, vs_req_kn * 1000.0)
            if vs_req_kn <= vs1_limit_kn:
                s_max = min(s_req, d_mm / 2.0, 600.0, s_min_reinf, 200.0)
                zone_lbl = "Zone 3 (Vs <= 1/3 √fc' bw d)"
            elif vs_req_kn <= vs2_limit_kn:
                s_max = min(s_req, d_mm / 4.0, 300.0, s_min_reinf, 150.0)
                zone_lbl = "Zone 4 (Vs <= 2/3 √fc' bw d)"
            else:
                s_max = 80.0
                zone_lbl = "Zone 5 (Section Inadequate: Vs > 2/3 √fc' bw d!)"
            s_adopt = max(75, int(math.floor(s_max / 10.0) * 10))

        callout = f"Φ {dst_mm} @ {s_adopt} mm ({n_legs}-Legs)"
        return {
            "callout": callout,
            "spacing_mm": s_adopt,
            "n_legs": n_legs,
            "av_mm2": av_mm2,
            "vs_req_kn": vs_req_kn,
            "zone_label": zone_lbl,
        }

    vu_kn = float(analysis_res.get("max_face_vu_kn", 0.0))
    bot_sec = calc_flexural_section(pos_mu)
    top_sec = calc_flexural_section(neg_mu)
    gov_signed_mu = -neg_mu if abs(neg_mu) >= abs(pos_mu) else pos_mu
    gov_sec = calc_flexural_section(m_max_gov)
    stir_sec = calc_stirrups_detail(vu_kn)

    spans = analysis_res.get("spans", beam.get("spans", [4.0]))

    support_designs = []
    for sup in sup_table:
        m_neg = abs(float(sup.get("centerline_neg_mu_knm", sup.get("m_center_knm", sup.get("face_neg_mu_knm", 0.0)))))
        v_f = float(sup.get("face_vu_kn", sup.get("vu_face_max_kn", 0.0)))
        s_flex = calc_flexural_section(m_neg)
        s_stir = calc_stirrups_detail(v_f)
        support_designs.append({
            "support_index": sup.get("support_index", 1),
            "target_id": sup.get("target_id", "C1"),
            "x_m": sup.get("x_m", 0.0),
            "reaction_ru_kn": sup.get("reaction_ru_kn", 0.0),
            "face_neg_mu_knm": abs(float(sup.get("face_neg_mu_knm", 0.0))),
            "mu_neg_face_knm": abs(float(sup.get("face_neg_mu_knm", 0.0))),
            "centerline_neg_mu_knm": m_neg,
            "mu_neg_center_knm": m_neg,
            "face_vu_kn": v_f,
            "top_ast_mm2": s_flex["as_req_mm2"],
            "top_as_prov_mm2": s_flex["as_prov_mm2"],
            "top_n_bars": s_flex["n_total"],
            "top_n_cont": s_flex["n_min_cont"],
            "top_n_add": s_flex["n_additional"],
            "top_bars": s_flex["bars_short"],
            "top_bars_callout": s_flex["bars_callout"],
            "top_additional_bars": s_flex["additional_bars"],
            "c_mm": s_flex["c_mm"],
            "fs_prime_mpa": s_flex["fs_prime_mpa"],
            "phi_mn_knm": s_flex["phi_mn_knm"],
            "stirrups_end": s_stir["callout"],
            "shear_zone": s_stir["zone_label"],
        })

    span_designs = []
    for idx, sp_info in enumerate(span_pos_list):
        m_pos = float(sp_info.get("max_pos_mu_knm", 0.0))
        v_sp = float(sp_info.get("max_abs_vu_kn", sp_info.get("max_face_vu_kn", 0.0)))
        b_flex = calc_flexural_section(m_pos)
        b_stir = calc_stirrups_detail(v_sp)
        left_sup = support_designs[idx] if idx < len(support_designs) else None
        right_sup = support_designs[idx + 1] if (idx + 1) < len(support_designs) else None
        neg_ctrl = max(
            abs(float(left_sup.get("centerline_neg_mu_knm", left_sup["face_neg_mu_knm"]))) if left_sup else 0.0,
            abs(float(right_sup.get("centerline_neg_mu_knm", right_sup["face_neg_mu_knm"]))) if right_sup else 0.0,
        )
        t_flex_sp = calc_flexural_section(neg_ctrl)
        span_designs.append({
            "span_index": idx + 1,
            "zone_label": f"Span {idx + 1}",
            "length_m": sp_info.get("length_m", spans[idx] if idx < len(spans) else 4.0),
            "start_x_m": sp_info.get("start_x_m", 0.0),
            "end_x_m": sp_info.get("end_x_m", 4.0),
            "pos_mu_knm": m_pos,
            "mu_pos_knm": m_pos,
            "at_x_m": sp_info.get("at_x_m", 2.0),
            "bottom_ast_mm2": b_flex["as_req_mm2"],
            "bottom_as_prov_mm2": b_flex["as_prov_mm2"],
            "bottom_n_bars": b_flex["n_total"],
            "bottom_n_cont": b_flex["n_min_cont"],
            "bottom_n_add": b_flex["n_additional"],
            "bottom_bars": b_flex["bars_short"],
            "bottom_bars_callout": b_flex["bars_callout"],
            "bottom_additional_bars": b_flex["additional_bars"],
            "c_mm": b_flex["c_mm"],
            "fs_prime_mpa": b_flex["fs_prime_mpa"],
            "phi_mn_knm": b_flex["phi_mn_knm"],
            "neg_mu_knm": round(-neg_ctrl, 2),
            "top_ast_mm2": t_flex_sp["as_req_mm2"],
            "top_n_bars": t_flex_sp["n_total"],
            "top_n_cont": t_flex_sp["n_min_cont"],
            "top_n_add": t_flex_sp["n_additional"],
            "top_bars": t_flex_sp["bars_short"],
            "top_bars_callout": t_flex_sp["bars_callout"],
            "top_additional_bars": t_flex_sp["additional_bars"],
            "max_vu_kn": v_sp,
            "vu_kn": v_sp,
            "stirrups": b_stir["callout"],
            "shear_zone": b_stir["zone_label"],
        })

    # Build Excel Sheet4 Station-by-Station Table (`For M = ... at support / mid span use n Φ db`)
    station_design_table: List[Dict[str, Any]] = []
    n_tot_stations = max(len(support_designs) + len(span_designs), 1)
    for idx_s in range(max(len(support_designs), len(span_designs))):
        if idx_s < len(support_designs):
            sd = support_designs[idx_s]
            m_signed = -round(abs(float(sd.get("centerline_neg_mu_knm", sd["face_neg_mu_knm"]))), 2) if abs(float(sd.get("centerline_neg_mu_knm", sd["face_neg_mu_knm"]))) > 0.05 else 0.0
            station_design_table.append({
                "station_type": "support",
                "station_label": f"moment at support {sd['target_id']}",
                "target_id": sd["target_id"],
                "mu_signed_knm": m_signed,
                "n_bars": sd["top_n_bars"],
                "bars_str": f"{sd['top_n_bars']} Φ {db_mm}",
                "line_text": f"For M = {m_signed:g} ( moment at support {sd['target_id']} ) use   {sd['top_n_bars']} Φ {db_mm}",
            })
        if idx_s < len(span_designs):
            spd = span_designs[idx_s]
            m_pos_val = round(float(spd["pos_mu_knm"]), 2)
            station_design_table.append({
                "station_type": "mid_span",
                "station_label": f"moment at mid span {spd['span_index']}",
                "target_id": str(spd["span_index"]),
                "mu_signed_knm": m_pos_val,
                "n_bars": spd["bottom_n_bars"],
                "bars_str": f"{spd['bottom_n_bars']} Φ {db_mm}",
                "shear_vu_kn": spd["max_vu_kn"],
                "line_text": f"For M = {m_pos_val:g} ( moment at mid span {spd['span_index']} ) use   {spd['bottom_n_bars']} Φ {db_mm}",
            })

    mode_label = (
        "VBA Iterative Section Sizing (+100mm) + Double Reinf."
        if mode_norm == "double_as_min"
        else "VBA Iterative Section Sizing (+100mm) + Single Reinf."
    )

    res = {
        "beam_id": beam.get("id", "B1"),
        "beam_kind": b_kind,
        "design_mode": "double" if mode_norm == "double_as_min" else "single",
        "design_mode_key": mode_norm,
        "design_mode_label": mode_label,
        "main_bar_dia_mm": db_mm,
        "stirrup_dia_mm": dst_mm,
        "num_spans": len(spans),
        "cantilever_left_m": float(beam.get("cantilever_left_m", 0.0)),
        "cantilever_right_m": float(beam.get("cantilever_right_m", 0.0)),
        "initial_b_mm": round(init_b_mm),
        "initial_h_mm": round(init_h_mm),
        "b_mm": round(b_mm),
        "h_mm": round(h_mm),
        "section_enlarged": (round(b_mm) > round(init_b_mm) or round(h_mm) > round(init_h_mm)),
        "sizing_iterations": sizing_iterations,
        "dc_mm": dc_mm,
        "d_mm": d_mm,
        "ddc_weighted_mm": ddc_weighted_mm,
        "d_prime_mm": d_prime_mm,
        "nrow_gov": nrow_gov,
        "beta1": beta1,
        "rho_min": pmin_excel,
        "rho_max_single": pmax_excel,
        "rho_act": gov_sec["rho_act"],
        "as_one_bar_mm2": asb_excel,
        "as_min_mm2": as_min_mm2,
        "as_min_prov_mm2": as_min_prov_mm2,
        "min_bars_excel": min_bars_excel,
        "max_bars_excel": max_bars_excel,
        "n_min_cont": n_min_cont,
        "n_bars_min_cont": n_min_cont,
        "continuous_min_bars": f"{n_min_cont} Φ {db_mm}",
        "continuous_bars_callout": f"{n_min_cont}Φ{db_mm} Continuous (Top & Bot, Start -> End)",
        "n_max_per_layer": n_max_single_layer,
        "governing_mu_signed_knm": round(gov_signed_mu, 2),
        "governing_mu_abs_knm": round(m_max_gov, 2),
        "governing_flexure_details": gov_sec,
        "station_design_table": station_design_table,
        "bottom_ast_mm2": bot_sec["as_req_mm2"],
        "as_pos_req_mm2": bot_sec["as_req_mm2"],
        "as_pos_single_mm2": bot_sec["as_single_calc_mm2"],
        "bottom_as_prov_mm2": bot_sec["as_prov_mm2"],
        "bottom_n_bars": bot_sec["n_total"],
        "n_bars_pos_total": bot_sec["n_total"],
        "bottom_n_cont": bot_sec["n_min_cont"],
        "bottom_n_add": bot_sec["n_additional"],
        "bottom_num_layers": bot_sec["num_layers"],
        "bottom_bars": bot_sec["bars_short"],
        "bottom_bars_callout": bot_sec["bars_callout"],
        "bottom_additional_bars": bot_sec["additional_bars"],
        "bot_c_mm": bot_sec["c_mm"],
        "bot_fs_prime_mpa": bot_sec["fs_prime_mpa"],
        "bot_phi_mn_knm": bot_sec["phi_mn_knm"],
        "pos_flexure_details": bot_sec,
        "top_ast_mm2": top_sec["as_req_mm2"],
        "as_neg_req_mm2": top_sec["as_req_mm2"],
        "as_neg_single_mm2": top_sec["as_single_calc_mm2"],
        "top_as_prov_mm2": top_sec["as_prov_mm2"],
        "top_n_bars": top_sec["n_total"],
        "n_bars_neg_total": top_sec["n_total"],
        "top_n_cont": top_sec["n_min_cont"],
        "top_n_add": top_sec["n_additional"],
        "top_num_layers": top_sec["num_layers"],
        "top_bars": top_sec["bars_short"],
        "top_bars_callout": top_sec["bars_callout"],
        "top_additional_bars": top_sec["additional_bars"],
        "top_c_mm": top_sec["c_mm"],
        "top_fs_prime_mpa": top_sec["fs_prime_mpa"],
        "top_phi_mn_knm": top_sec["phi_mn_knm"],
        "neg_flexure_details": top_sec,
        "vc_kn": vc_kn,
        "phi_vc_kn": phi_vc,
        "stirrups": stir_sec["callout"],
        "shear_zone": stir_sec["zone_label"],
        "status": f"OK ({mode_label})",
        "span_designs": span_designs,
        "support_designs": support_designs,
    }

    # If section was locked and over-reinforced, surface warning and set as_req = None
    if gov_sec.get("over_reinforced", False):
        res["status"] = gov_sec["status"]
        res["as_pos_req_mm2"] = bot_sec.get("as_req_mm2")
        res["as_neg_req_mm2"] = top_sec.get("as_req_mm2")
        res["bottom_ast_mm2"] = bot_sec.get("as_req_mm2")
        res["top_ast_mm2"] = top_sec.get("as_req_mm2")

    # Enforce minimum dimension floors (300mm hidden / 400mm drop)
    kind_chk = str(beam.get("beam_kind", "hidden")).lower()
    if kind_chk == "hidden":
        f_min = float(beam.get("min_width_mm", 300.0))
        if float(res.get("b_mm", 0)) < f_min:
            res["b_mm"] = round(f_min)
            beam["width_m"] = round(f_min / 1000.0, 3)
    else:
        f_min = float(beam.get("min_depth_mm", 400.0))
        if float(res.get("h_mm", 0)) < f_min:
            res["h_mm"] = round(f_min)
            beam["depth_m"] = round(f_min / 1000.0, 3)

    return res


def design_column_and_pm_curve(
    column_id: str,
    b_m: float,
    h_m: float,
    pu_kn: float,
    mux_knm: float,
    muy_knm: float,
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
    lu_m: Optional[float] = None,
    double_height: bool = False,
) -> Dict[str, Any]:
    """
    Designs column per ACI 318 using Strain-Compatibility P-M numerical sweep
    and Bresler reciprocal load formula for biaxial safety check.
    Supports Double-Height (2H) columns located inside slab openings (`lu_m = 2 * story_h`).
    """
    b_mm = round(b_m * 1000.0)
    h_mm = round(h_m * 1000.0)
    ag = b_mm * h_mm
    eff_lu_m = round(float(lu_m if lu_m is not None else 3.0), 2)
    r_min_m = 0.30 * min(b_m, h_m)
    slenderness_kl_r = round(eff_lu_m / max(0.01, r_min_m), 1)

    es_mpa = 200000.0
    beta1 = 0.85 if fc_mpa <= 28.0 else max(0.65, 0.85 - 0.05 * (fc_mpa - 28.0) / 7.0)

    # Steel requirement per axial capacity baseline
    ast_req = max(0.01 * ag, ((pu_kn * 1000.0) / (0.65 * 0.80) - 0.85 * fc_mpa * ag) / (fy_mpa - 0.85 * fc_mpa))
    n_bars = max(6, math.ceil(ast_req / 201.06 / 2.0) * 2)
    ast_prov = n_bars * 201.06

    # Nominal pure compression P0 and pure tension Pnt
    p0_kn = (0.85 * fc_mpa * (ag - ast_prov) + fy_mpa * ast_prov) / 1000.0
    pnt_kn = -(fy_mpa * ast_prov) / 1000.0
    pn_max_kn = 0.80 * p0_kn
    phi_pn_max_kn = 0.65 * pn_max_kn

    # Numerical strain-compatibility generator for rectangular section
    def build_pm_diagram(b_w: float, h_d: float):
        ds = 45.0  # Cover to centroid of outer steel layer (mm)
        d = h_d - ds
        as_layer = ast_prov / 2.0
        # Exact balanced neutral axis depth: cb = 600 * d / (600 + fy)
        cb = (600.0 / (600.0 + fy_mpa)) * d

        def eval_strain(c_val: float):
            c_clamped = max(0.1, c_val)
            a_val = min(float(h_d), beta1 * c_clamped)
            cc_kn = 0.85 * fc_mpa * b_w * a_val / 1000.0
            mc_knm = cc_kn * (h_d / 2.0 - a_val / 2.0) / 1000.0

            # Layer 1: compression face (at ds)
            eps_s1 = 0.003 * (c_clamped - ds) / c_clamped
            fs1 = max(-fy_mpa, min(fy_mpa, es_mpa * eps_s1))
            fc_disp1 = 0.85 * fc_mpa if ds <= a_val else 0.0
            fs_1_kn = as_layer * (fs1 - fc_disp1) / 1000.0
            ms_1_knm = fs_1_kn * (h_d / 2.0 - ds) / 1000.0

            # Layer 2: tension face (at d)
            eps_s2 = 0.003 * (c_clamped - d) / c_clamped
            fs2 = max(-fy_mpa, min(fy_mpa, es_mpa * eps_s2))
            fc_disp2 = 0.85 * fc_mpa if d <= a_val else 0.0
            fs_2_kn = as_layer * (fs2 - fc_disp2) / 1000.0
            ms_2_knm = fs_2_kn * (h_d / 2.0 - d) / 1000.0

            pn = cc_kn + fs_1_kn + fs_2_kn
            mn = mc_knm + ms_1_knm + ms_2_knm

            # ACI strength reduction factor phi transition
            eps_t = abs(min(0.0, eps_s2))
            eps_y = fy_mpa / es_mpa
            if eps_t <= eps_y:
                phi = 0.65
            elif eps_t >= 0.005:
                phi = 0.90
            else:
                phi = 0.65 + 0.25 * (eps_t - eps_y) / max(1e-5, (0.005 - eps_y))

            return pn, mn, phi, eps_t

        # 1. Balanced point
        pnb, mnb, phib, _ = eval_strain(cb)

        # 2. Pure bending (Pn = 0)
        c_low, c_high = 1.0, float(h_d)
        for _ in range(50):
            c_mid = (c_low + c_high) / 2.0
            p_val, _, _, _ = eval_strain(c_mid)
            if p_val > 0.0:
                c_high = c_mid
            else:
                c_low = c_mid
        c0 = (c_low + c_high) / 2.0
        _, mn0, phi0, _ = eval_strain(c0)

        # 3. Intermediate compression (c = 1.5 cb)
        pn_comp, mn_comp, phi_comp, _ = eval_strain(1.5 * cb)

        # 4. Tension transition (eps_t = 0.005 -> c = 3/8 d)
        c_tens = (3.0 / 8.0) * d
        pn_tens, mn_tens, phi_tens, _ = eval_strain(c_tens)

        # Build nominal envelope (Pn, Mn) ordered from P0 down to pure bending
        pts_nominal = [
            (p0_kn, 0.0),
            (pn_comp, mn_comp),
            (pnb, mnb),
            (pn_tens, mn_tens),
            (0.0, mn0),
            (pnt_kn, 0.0)
        ]

        # Build design / factored envelope (phi*Pn, phi*Mn)
        pts_factored = [
            (phi_pn_max_kn, 0.0),
            (min(phi_pn_max_kn, phi_comp * pn_comp), phi_comp * mn_comp),
            (phib * pnb, phib * mnb),
            (phi_tens * pn_tens, phi_tens * mn_tens),
            (0.0, phi0 * mn0),
            (0.90 * pnt_kn, 0.0)
        ]

        return pts_nominal, pts_factored, pnb, mnb, phib * mnb, phi0 * mn0, cb

    nom_x, phi_x, pnb_x, mnb_x, phi_mb_x, phi_m0_x, cb_x = build_pm_diagram(b_mm, h_mm)
    nom_y, phi_y, pnb_y, mnb_y, phi_mb_y, phi_m0_y, cb_y = build_pm_diagram(h_mm, b_mm)

    # Ray intersection to find nominal capacity Pn for a given eccentricity e = M / P
    def get_pn_for_eccentricity(pts_nom, e_meters: float) -> float:
        if e_meters <= 1e-4:
            return pts_nom[0][0]
        for i in range(len(pts_nom) - 1):
            p1, m1 = pts_nom[i]
            p2, m2 = pts_nom[i + 1]
            if p1 <= 0.0 and p2 <= 0.0:
                continue
            dp = p2 - p1
            dm = m2 - m1
            if abs(dp) < 1e-6:
                continue
            slope = dm / dp
            if abs(e_meters - slope) < 1e-9:
                continue
            p_inter = (m1 - slope * p1) / (e_meters - slope)
            if min(p1, p2) - 1e-3 <= p_inter <= max(p1, p2) + 1e-3:
                return max(0.0, p_inter)
        return max(0.0, pts_nom[-2][0])

    # Item 1: Bresler Reciprocal Load Biaxial Check
    abs_pu = max(0.0, float(pu_kn))
    abs_mux = abs(float(mux_knm))
    abs_muy = abs(float(muy_knm))

    ex = (abs_mux / abs_pu) if abs_pu > 0.05 else 0.0
    ey = (abs_muy / abs_pu) if abs_pu > 0.05 else 0.0

    pnx = get_pn_for_eccentricity(nom_x, ex)
    pny = get_pn_for_eccentricity(nom_y, ey)
    pn0 = p0_kn

    # Bresler formula: 1/Pn_biax = 1/Pnx + 1/Pny - 1/Pn0
    if abs_pu <= 0.05:
        # Pure bending / near zero axial: check against pure bending capacities
        safe_x = abs_mux <= phi_m0_x
        safe_y = abs_muy <= phi_m0_y
        util_x = abs_mux / max(0.01, phi_m0_x)
        util_y = abs_muy / max(0.01, phi_m0_y)
        utilization = max(util_x, util_y)
        status = "SAFE" if (safe_x and safe_y) else "INCREASE SECTION (BIAXIAL)"
        pn_biax = None
        phi_pn_biax = None
    elif abs_mux <= 0.01 and abs_muy <= 0.01:
        # Pure axial load
        pn_biax = pn0
        phi_pn_biax = phi_pn_max_kn
        utilization = abs_pu / max(0.01, phi_pn_max_kn)
        status = "SAFE" if abs_pu <= phi_pn_max_kn else "INCREASE SECTION"
    else:
        # Biaxial bending with axial compression
        if pnx > 0.0 and pny > 0.0 and pn0 > 0.0:
            inv_pn_biax = (1.0 / pnx) + (1.0 / pny) - (1.0 / pn0)
            if inv_pn_biax > 0.0:
                pn_biax = 1.0 / inv_pn_biax
            else:
                pn_biax = min(pnx, pny)
        else:
            pn_biax = min(pnx, pny)

        phi_pn_biax = 0.65 * pn_biax
        util_axial = abs_pu / max(0.01, phi_pn_max_kn)
        util_biax = abs_pu / max(0.01, phi_pn_biax)
        utilization = max(util_axial, util_biax)

        if abs_pu <= phi_pn_max_kn and abs_pu <= phi_pn_biax:
            status = "SAFE"
        elif abs_pu > phi_pn_max_kn and abs_pu <= phi_pn_biax:
            status = "INCREASE SECTION"
        else:
            status = "INCREASE SECTION (BIAXIAL)"

    # Format P-M curve points (positive M and positive P compression envelope)
    pm_curve_points = [
        {"m_knm": round(m, 1), "p_kn": round(p, 1)}
        for p, m in phi_x if p >= -0.01 and m >= -0.01
    ]

    return {
        "column_id": column_id,
        "section_mm": f"{b_mm} x {h_mm} mm",
        "chosen_bars": f"{n_bars} Phi 16 mm",
        "rho_pct": round((ast_prov / ag) * 100.0, 2),
        "phi_pn_max_kn": round(phi_pn_max_kn, 1),
        "phi_mb_knm": round(phi_mb_x, 1),
        "lu_m": eff_lu_m,
        "double_height": bool(double_height),
        "effective_height_note": f"2H Double-Height ({eff_lu_m:.2f}m, kL/r={slenderness_kl_r})" if double_height else f"1H ({eff_lu_m:.2f}m)",
        "slenderness_kl_r": slenderness_kl_r,
        "pm_curve_points": pm_curve_points,
        "status": status,
        "utilization": round(utilization, 3),
        "p0_kn": round(p0_kn, 1),
        "pnt_kn": round(pnt_kn, 1),
        "phi_pnb_kn": round(0.65 * pnb_x, 1),
        "phi_mnb_knm": round(phi_mb_x, 1),
        "cb_mm": round(cb_x, 1),
        "pn_biax_kn": round(pn_biax, 1) if pn_biax is not None else None,
        "phi_pn_biax_kn": round(phi_pn_biax, 1) if phi_pn_biax is not None else None,
    }


# ==============================================================================
# PHASE 2: STRICT CAD MODELING WORKFLOW, BOUNDARY RULES, PICK AREA & MOVE TOOLS
# ==============================================================================

def get_slab_bounding_box(slab_edge_polygon: List[List[float]]) -> Tuple[bool, float, float, float, float]:
    """
    Returns (has_valid_boundary, min_x, min_y, max_x, max_y) from slab_edge_polygon.
    """
    if not slab_edge_polygon or len(slab_edge_polygon) < 3:
        return False, 0.0, 0.0, 0.0, 0.0
    xs = [float(p[0]) for p in slab_edge_polygon]
    ys = [float(p[1]) for p in slab_edge_polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if (max_x - min_x) < 0.5 or (max_y - min_y) < 0.5:
        return False, min_x, min_y, max_x, max_y
    return True, min_x, min_y, max_x, max_y


def enforce_column_inside_slab_boundary(
    col: Dict[str, Any],
    slab_edge_polygon: List[List[float]],
    mode: str = "clamp",
) -> Tuple[Dict[str, Any], List[List[float]], str]:
    """
    Enforces strict rule: No column may lie outside the Outer Slab Boundary (00-XD-EDGE).
    Crash-proof: if no boundary exists yet, returns the column safely without raising an unhandled exception.
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(slab_edge_polygon)
    if not has_bnd:
        return dict(col), list(slab_edge_polygon or []), "Column placed (draw Outer Slab Boundary to clamp faces)."

    cx = float(col.get("x", 0.0))
    cy = float(col.get("y", 0.0))
    b = float(col.get("b_m", 0.20))
    h = float(col.get("h_m", 0.40))
    half_b = b / 2.0
    half_h = h / 2.0

    col_min_x, col_max_x = cx - half_b, cx + half_b
    col_min_y, col_max_y = cy - half_h, cy + half_h

    is_outside = (
        col_min_x < min_x - 1e-6
        or col_max_x > max_x + 1e-6
        or col_min_y < min_y - 1e-6
        or col_max_y > max_y + 1e-6
    )

    updated_col = dict(col)
    if not is_outside:
        return updated_col, slab_edge_polygon, "Column is strictly inside slab boundary."

    if mode == "expand":
        new_min_x = round(min(min_x, col_min_x), 3)
        new_max_x = round(max(max_x, col_max_x), 3)
        new_min_y = round(min(min_y, col_min_y), 3)
        new_max_y = round(max(max_y, col_max_y), 3)
        new_poly = [
            [new_min_x, new_min_y],
            [new_max_x, new_min_y],
            [new_max_x, new_max_y],
            [new_min_x, new_max_y],
        ]
        return (
            updated_col,
            new_poly,
            f"Slab boundary expanded to [{new_min_x}, {new_min_y}] - [{new_max_x}, {new_max_y}] to contain column {col.get('id', '')}.",
        )

    # Default mode == 'clamp': shift column flush with slab edge
    clamped_x = min(max(cx, min_x + half_b), max_x - half_b)
    clamped_y = min(max(cy, min_y + half_h), max_y - half_h)
    updated_col["x"] = round(clamped_x, 3)
    updated_col["y"] = round(clamped_y, 3)
    return (
        updated_col,
        slab_edge_polygon,
        f"Column {col.get('id', '')} clamped flush to slab boundary at ({updated_col['x']:.2f}, {updated_col['y']:.2f}).",
    )


def check_duplicate_column(
    x: float,
    y: float,
    b_m: float,
    h_m: float,
    existing_columns: List[Dict[str, Any]],
    ignore_id: Optional[str] = None,
) -> Optional[str]:
    """
    Returns the ID of an existing active column if placing a column at (x, y)
    would overlap an existing column on the same spot.
    """
    for col in existing_columns:
        if not col.get("active", True) or col.get("id") == ignore_id:
            continue
        cx, cy = float(col["x"]), float(col["y"])
        cb, ch = float(col.get("b_m", 0.20)), float(col.get("h_m", 0.40))
        if abs(x - cx) < (b_m + cb) * 0.48 and abs(y - cy) < (h_m + ch) * 0.48:
            return str(col["id"])
    return None


def renumber_story_columns_sequentially(story_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Ensures all active columns in `story_data['columns']` are numbered sequentially
    `C1, C2, C3, ..., Cn` with ZERO gaps (e.g., after deleting C4, C5..C9 become C4..C8),
    and updates all column support references (`target_id`) across `story_data['beams']`.
    Returns a dictionary mapping `{old_col_id: new_col_id}`.
    """
    cols = story_data.get("columns", [])
    active_cols = [c for c in cols if c.get("active", True)]
    id_map: Dict[str, str] = {}
    for idx, col in enumerate(active_cols):
        old_id = str(col.get("id", f"C{idx + 1}"))
        new_id = f"C{idx + 1}"
        id_map[old_id] = new_id
        col["id"] = new_id

    story_data["columns"] = active_cols
    for bm in story_data.get("beams", []):
        for sup in bm.get("supports", []):
            if sup.get("kind") == "column":
                old_tid = str(sup.get("target_id", ""))
                if old_tid in id_map:
                    sup["target_id"] = id_map[old_tid]
    return id_map


def reconcile_all_story_beams_supports_and_spans(story_data: Dict[str, Any]) -> None:
    """
    Dynamically re-evaluates all beams' supports (`columns` and perpendicular carrier `beams`),
    `spans`, and `cantilever_left_m` / `cantilever_right_m` from live 2D geometry in `story_data`.
    Fixes:
    1. When a column in the middle of a 2-span beam (e.g. B6) is deleted, B6 immediately becomes
       a 1-span beam (`[9.30m]`) between its remaining end columns (`C7` and `C8`/`C9`), and any
       perpendicular beam (e.g. B5) that used to frame into that deleted column automatically
       switches its support to Carrier Beam B6 (`Roller`)!
    2. Preserves synthetic unit-test beams that have no 2D coordinates or no story columns.
    """
    beams = story_data.get("beams", [])
    if not beams:
        return
    active_cols = [c for c in story_data.get("columns", []) if c.get("active", True)]
    if not active_cols and len(beams) <= 1:
        return

    # First pass: determine which beams have column supports and 2D geometry
    for bm in beams:
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        total_len = round(math.hypot(ex - sx, ey - sy), 3)
        if total_len < 0.40:
            continue

        is_horizontal = abs(ex - sx) >= abs(ey - sy)
        if is_horizontal and sx > ex:
            sx, ex = ex, sx
        elif (not is_horizontal) and sy > ey:
            sy, ey = ey, sy

        width_m = float(bm.get("width_m", 0.30))
        half_w = width_m / 2.0
        snap_tol = max(0.45, half_w + 0.28)
        prev_sup_beam_ids = {
            str(s.get("target_id"))
            for s in bm.get("supports", [])
            if s.get("kind") == "beam"
        }

        supports_raw: List[Dict[str, Any]] = []
        for col in active_cols:
            cx, cy = float(col["x"]), float(col["y"])
            b_col = float(col.get("b_m", 0.20))
            h_col = float(col.get("h_m", 0.40))
            if is_horizontal:
                if abs(cy - sy) <= max(snap_tol, h_col / 2.0 + half_w + 0.15) and (sx - b_col / 2.0 - 0.35) <= cx <= (ex + b_col / 2.0 + 0.35):
                    supports_raw.append({
                        "coord": cx,
                        "x": cx,
                        "y": sy,
                        "kind": "column",
                        "target_id": str(col["id"]),
                        "width_m": b_col,
                        "depth_m": h_col,
                    })
            else:
                if abs(cx - sx) <= max(snap_tol, b_col / 2.0 + half_w + 0.15) and (sy - h_col / 2.0 - 0.35) <= cy <= (ey + h_col / 2.0 + 0.35):
                    supports_raw.append({
                        "coord": cy,
                        "x": sx,
                        "y": cy,
                        "kind": "column",
                        "target_id": str(col["id"]),
                        "width_m": h_col,
                        "depth_m": b_col,
                    })

        # Second: check perpendicular beams for T-junction or previously-registered carrier beam supports
        for ob in beams:
            if ob.get("id") == bm.get("id"):
                continue
            osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
            oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
            if math.hypot(oex - osx, oey - osy) < 0.40:
                continue
            ob_horiz = abs(oex - osx) >= abs(oey - osy)
            if is_horizontal and not ob_horiz:
                bx = osx
                omin_y, omax_y = min(osy, oey), max(osy, oey)
                if (sx - 0.30) <= bx <= (ex + 0.30) and (omin_y - 0.30) <= sy <= (omax_y + 0.30):
                    if any(abs(s["coord"] - bx) < 0.35 for s in supports_raw):
                        continue
                    d_bm_end = min(abs(bx - sx), abs(bx - ex))
                    d_ob_end = min(abs(sy - omin_y), abs(sy - omax_y))
                    # ob is Carrier if bm terminates on ob's interior (T-junction) OR ob was already supporting bm
                    is_t_junction_on_ob = (d_bm_end <= 0.55 and d_ob_end > 0.45)
                    ob_supports_bm_already = (str(ob.get("id")) in prev_sup_beam_ids) and not (d_ob_end <= 0.55 and d_bm_end > 0.45)
                    if is_t_junction_on_ob or ob_supports_bm_already:
                        supports_raw.append({
                            "coord": bx,
                            "x": bx,
                            "y": sy,
                            "kind": "beam",
                            "target_id": str(ob["id"]),
                            "width_m": float(ob.get("width_m", 0.30)),
                            "depth_m": float(ob.get("depth_m", 0.30)),
                            "pos_on_carrier_m": round(abs(sy - omin_y), 3),
                        })
            elif (not is_horizontal) and ob_horiz:
                by = osy
                omin_x, omax_x = min(osx, oex), max(osx, oex)
                if (sy - 0.30) <= by <= (ey + 0.30) and (omin_x - 0.30) <= sx <= (omax_x + 0.30):
                    if any(abs(s["coord"] - by) < 0.35 for s in supports_raw):
                        continue
                    d_bm_end = min(abs(by - sy), abs(by - ey))
                    d_ob_end = min(abs(sx - omin_x), abs(sx - omax_x))
                    is_t_junction_on_ob = (d_bm_end <= 0.55 and d_ob_end > 0.45)
                    ob_supports_bm_already = (str(ob.get("id")) in prev_sup_beam_ids) and not (d_ob_end <= 0.55 and d_bm_end > 0.45)
                    if is_t_junction_on_ob or ob_supports_bm_already:
                        supports_raw.append({
                            "coord": by,
                            "x": sx,
                            "y": by,
                            "kind": "beam",
                            "target_id": str(ob["id"]),
                            "width_m": float(ob.get("width_m", 0.30)),
                            "depth_m": float(ob.get("depth_m", 0.30)),
                            "pos_on_carrier_m": round(abs(sx - omin_x), 3),
                        })

        supports_raw.sort(key=lambda s: s["coord"])
        if not supports_raw:
            continue

        first_sup = supports_raw[0]
        last_sup = supports_raw[-1]
        first_outer_edge = round(first_sup["coord"] - float(first_sup["width_m"]) / 2.0, 3)
        last_outer_edge = round(last_sup["coord"] + float(last_sup["width_m"]) / 2.0, 3)

        start_coord = sx if is_horizontal else sy
        end_coord = ex if is_horizontal else ey
        raw_cant_left = round(first_sup["coord"] - start_coord, 3)
        raw_cant_right = round(end_coord - last_sup["coord"], 3)
        overhang_beyond_first_face = round(first_outer_edge - start_coord, 3)
        overhang_beyond_last_face = round(end_coord - last_outer_edge, 3)

        cant_left = raw_cant_left if overhang_beyond_first_face > 0.25 else 0.0
        cant_right = raw_cant_right if overhang_beyond_last_face > 0.25 else 0.0

        new_spans: List[float] = []
        for idx in range(len(supports_raw) - 1):
            sp = round(supports_raw[idx + 1]["coord"] - supports_raw[idx]["coord"], 3)
            if sp >= 0.30:
                new_spans.append(sp)

        if not new_spans:
            if cant_left > 0.35:
                new_spans = [cant_left]
            elif cant_right > 0.35:
                new_spans = [cant_right]
            else:
                new_spans = [round(max(0.50, total_len), 3)]

        formatted_supports = []
        for idx, sup in enumerate(supports_raw):
            entry: Dict[str, Any] = {
                "support_index": idx + 1,
                "kind": sup["kind"],
                "target_id": sup["target_id"],
                "width_m": round(float(sup["width_m"]), 3),
                "depth_m": round(float(sup.get("depth_m", 0.30)), 3),
                "coord": round(float(sup["coord"]), 3),
                "center_coord_m": round(float(sup["coord"]), 3),
            }
            if "pos_on_carrier_m" in sup:
                entry["pos_on_carrier_m"] = sup["pos_on_carrier_m"]
            formatted_supports.append(entry)

        old_spans = [round(float(x), 2) for x in bm.get("spans", [])]
        new_spans_rounded = [round(float(x), 2) for x in new_spans]
        bm["supports"] = formatted_supports
        bm["spans"] = new_spans
        bm["cantilever_left_m"] = cant_left if len(supports_raw) >= 2 else 0.0
        bm["cantilever_right_m"] = cant_right if len(supports_raw) >= 2 else 0.0

        if old_spans != new_spans_rounded:
            bm.pop("manual_loads_override", None)
            ensure_beam_wall_flags(story_data, bm)



def _dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    L2 = dx*dx + dy*dy
    if L2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def validate_cantilever_tip(
    tip_pt: Tuple[float, float],
    cant_len: float,
    story_data: Dict[str, Any],
    active_cols: List[Dict[str, Any]],
    existing_beams: List[Dict[str, Any]],
    slab_edge_poly: List[List[float]],
    openings: Optional[List[Dict[str, Any]]] = None,
    tol2: float = 0.025,
) -> Tuple[bool, Optional[str]]:
    """
    Modification 3 — Cantilever Tip Validation Rule (TOL2 = 25 mm):
    A cantilever tip is valid if ANY of the following holds:
      (a) on a support node (column or supporting beam);
      (b) on any slab boundary edge (outer boundary or opening edge);
      (c) outside all slab and opening polygons (projecting outward);
      (d) on an existing beam line.
    Otherwise rejects with descriptive hint:
      '...tip lies inside slab {id} at (x,y); move it to a slab edge, a support, or outside the slab.'
    """
    tx, ty = float(tip_pt[0]), float(tip_pt[1])

    # (a) On a support node
    for col in active_cols:
        cx, cy = float(col["x"]), float(col["y"])
        b = float(col.get("b_m", 0.20))
        h = float(col.get("h_m", 0.40))
        if abs(tx - cx) <= (b / 2.0 + tol2) and abs(ty - cy) <= (h / 2.0 + tol2):
            return True, None
    for ob in existing_beams:
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        w = float(ob.get("width_m", 0.30))
        if _dist_point_to_segment(tx, ty, osx, osy, oex, oey) <= (w / 2.0 + tol2):
            return True, None

    # (b) On any slab boundary edge (outer boundary or opening edge)
    if slab_edge_poly and len(slab_edge_poly) >= 3:
        n = len(slab_edge_poly)
        for i in range(n):
            p1 = slab_edge_poly[i]
            p2 = slab_edge_poly[(i + 1) % n]
            if _dist_point_to_segment(tx, ty, p1[0], p1[1], p2[0], p2[1]) <= tol2:
                return True, None
    if openings:
        for op in openings:
            poly = op.get("polygon", [])
            if not poly and "min_x" in op:
                poly = [[op["min_x"], op["min_y"]], [op["max_x"], op["min_y"]], [op["max_x"], op["max_y"]], [op["min_x"], op["max_y"]]]
            if poly and len(poly) >= 3:
                m = len(poly)
                for i in range(m):
                    p1 = poly[i]
                    p2 = poly[(i + 1) % m]
                    if _dist_point_to_segment(tx, ty, p1[0], p1[1], p2[0], p2[1]) <= tol2:
                        return True, None
    for slb in story_data.get("slabs", []):
        poly = slb.get("polygon", [])
        if poly and len(poly) >= 3:
            k = len(poly)
            for i in range(k):
                p1 = poly[i]
                p2 = poly[(i + 1) % k]
                if _dist_point_to_segment(tx, ty, p1[0], p1[1], p2[0], p2[1]) <= tol2:
                    return True, None

    # (c) Outside all slab and opening polygons
    in_outer = False
    if slab_edge_poly and len(slab_edge_poly) >= 3:
        in_outer = _point_in_polygon_2d(tx, ty, slab_edge_poly)
        d_outer = _min_dist_to_poly_edges(tx, ty, slab_edge_poly)
        if not in_outer and d_outer > tol2:
            return True, None  # Outside building footprint

    if openings:
        for op in openings:
            poly = op.get("polygon", [])
            if not poly and "min_x" in op:
                poly = [[op["min_x"], op["min_y"]], [op["max_x"], op["min_y"]], [op["max_x"], op["max_y"]], [op["min_x"], op["max_y"]]]
            if poly and len(poly) >= 3:
                if _point_in_polygon_2d(tx, ty, poly):
                    return True, None  # Inside void opening

    # (d) On an existing beam line
    for ob in existing_beams:
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        if _dist_point_to_segment(tx, ty, osx, osy, oex, oey) <= tol2:
            return True, None

    # Otherwise: tip lies inside a slab!
    slab_id = "Slab"
    for slb in story_data.get("slabs", []):
        poly = slb.get("polygon", [])
        if poly and len(poly) >= 3 and _point_in_polygon_2d(tx, ty, poly):
            slab_id = slb.get("id", "Slab")
            break

    return False, (
        f"Invalid Interior Cantilever: Overhang ({cant_len:.2f} m) tip lies inside slab {slab_id} at ({tx:.2f}, {ty:.2f}); "
        "move it to a slab edge, a support, or outside the slab."
    )


def extend_beam_with_target(
    story_data: Dict[str, Any],
    beam_id: str,
    target_pt: Tuple[float, float],
    tol: float = 0.010,
    tol2: float = 0.150,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Modification 2 — Extend Beam Command:
    Extends beam to an existing support node (adds a span) or a free point (creates cantilever).
    Rejects if off-axis (M3) or overlapping another collinear beam (M4/D2).
    """
    beams = story_data.get("beams", [])
    bm = next((b for b in beams if b.get("id") == beam_id), None)
    if not bm:
        return False, None, f"Beam {beam_id} not found."

    sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
    ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
    is_horizontal = abs(ex - sx) >= abs(ey - sy)
    tx, ty = float(target_pt[0]), float(target_pt[1])

    # Check: Target point must lie on beam infinite axis line
    if is_horizontal:
        if abs(ty - sy) > tol2:
            return False, None, "Target point must lie on the beam axis line."
        tx = round(tx, 3)
        ty = sy
    else:
        if abs(tx - sx) > tol2:
            return False, None, "Target point must lie on the beam axis line."
        ty = round(ty, 3)
        tx = sx

    # Check: Target point must be outside current beam interval
    if is_horizontal:
        min_x, max_x = min(sx, ex), max(sx, ex)
        if (min_x - tol) <= tx <= (max_x + tol):
            return False, None, "Target point must be outside the current beam length."
        extending_right = (tx > max_x)
        ext_start, ext_end = (max_x, tx) if extending_right else (tx, min_x)
    else:
        min_y, max_y = min(sy, ey), max(sy, ey)
        if (min_y - tol) <= ty <= (max_y + tol):
            return False, None, "Target point must be outside the current beam length."
        extending_right = (ty > max_y)
        ext_start, ext_end = (max_y, ty) if extending_right else (ty, min_y)

    # Check D2 Overlap with existing collinear beams (Scenario M4)
    for ob in beams:
        if ob.get("id") == beam_id:
            continue
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        ob_horiz = abs(oex - osx) >= abs(oey - osy)
        if is_horizontal and ob_horiz and abs(sy - osy) <= 0.025:
            ob_a, ob_b = min(osx, oex), max(osx, oex)
            ov = min(ext_end, ob_b) - max(ext_start, ob_a)
            if ov > tol:
                return False, None, f"Overlapping beam: overlaps {ob['id']}; adjust ends or use Extend"
        elif (not is_horizontal) and (not ob_horiz) and abs(sx - osx) <= 0.025:
            ob_a, ob_b = min(osy, oey), max(osy, oey)
            ov = min(ext_end, ob_b) - max(ext_start, ob_a)
            if ov > tol:
                return False, None, f"Overlapping beam: overlaps {ob['id']}; adjust ends or use Extend"

    # Support Discovery at target point (Scenario M1)
    target_coord = tx if is_horizontal else ty
    active_cols = [c for c in story_data.get("columns", []) if c.get("active", True)]
    target_support = None

    for col in active_cols:
        cx, cy = float(col["x"]), float(col["y"])
        b = float(col.get("b_m", 0.20))
        h = float(col.get("h_m", 0.40))
        snap_r = max(b, h) / 2.0 + 0.15
        if math.hypot(tx - cx, ty - cy) <= snap_r:
            target_support = {
                "kind": "column",
                "target_id": str(col["id"]),
                "width_m": b if is_horizontal else h,
                "depth_m": h if is_horizontal else b,
                "coord": cx if is_horizontal else cy,
            }
            break

    if not target_support:
        for ob in beams:
            if ob.get("id") == beam_id:
                continue
            osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
            oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
            ob_horiz = abs(oex - osx) >= abs(oey - osy)
            if is_horizontal and (not ob_horiz):
                if abs(tx - osx) <= tol2 and min(osy, oey) - 0.25 <= ty <= max(osy, oey) + 0.25:
                    target_support = {
                        "kind": "beam",
                        "target_id": str(ob["id"]),
                        "width_m": float(ob.get("width_m", 0.30)),
                        "depth_m": float(ob.get("depth_m", 0.30)),
                        "coord": osx,
                    }
                    break
            elif (not is_horizontal) and ob_horiz:
                if abs(ty - osy) <= tol2 and min(osx, oex) - 0.25 <= tx <= max(osx, oex) + 0.25:
                    target_support = {
                        "kind": "beam",
                        "target_id": str(ob["id"]),
                        "width_m": float(ob.get("width_m", 0.30)),
                        "depth_m": float(ob.get("depth_m", 0.30)),
                        "coord": osy,
                    }
                    break

    supports = bm.setdefault("supports", [])
    spans = bm.setdefault("spans", [])

    if target_support:
        if extending_right:
            last_sup_coord = float(supports[-1].get("coord", supports[-1].get("center_coord_m", max_x))) if supports else max_x
            new_span = round(abs(target_support["coord"] - last_sup_coord), 3)
            spans.append(new_span)
            target_support["support_index"] = len(supports) + 1
            supports.append(target_support)
            bm["cantilever_right_m"] = 0.0
            if is_horizontal:
                bm["end_x"] = tx
            else:
                bm["end_y"] = ty
        else:
            first_sup_coord = float(supports[0].get("coord", supports[0].get("center_coord_m", min_x))) if supports else min_x
            new_span = round(abs(first_sup_coord - target_support["coord"]), 3)
            spans.insert(0, new_span)
            supports.insert(0, target_support)
            bm["cantilever_left_m"] = 0.0
            if is_horizontal:
                bm["start_x"] = tx
            else:
                bm["start_y"] = ty
        for i, s in enumerate(supports):
            s["support_index"] = i + 1
    else:
        # Free point extension (Scenario M2)
        poly = story_data.get("slab_edge_polygon", [])
        ops = story_data.get("openings", [])
        end_sup_coord = float(supports[-1].get("coord", max_x)) if extending_right else float(supports[0].get("coord", min_x))
        cant_len = round(abs(target_coord - end_sup_coord), 3)

        ok_tip, tip_msg = validate_cantilever_tip(
            (tx, ty),
            cant_len,
            story_data,
            active_cols,
            beams,
            poly,
            ops,
            tol2=tol2,
        )
        if not ok_tip:
            return False, None, tip_msg

        if extending_right:
            bm["cantilever_right_m"] = cant_len
            if is_horizontal:
                bm["end_x"] = tx
            else:
                bm["end_y"] = ty
        else:
            bm["cantilever_left_m"] = cant_len
            if is_horizontal:
                bm["start_x"] = tx
            else:
                bm["start_y"] = ty

    bm.pop("manual_loads_override", None)
    reconcile_all_story_beams_supports_and_spans(story_data)
    return True, bm, f"Beam {beam_id} extended successfully."


def validate_and_build_beam_with_cantilevers(
    beam_id: str,
    start_pt: Tuple[float, float],
    end_pt: Tuple[float, float],
    beam_kind: str,
    width_m: float,
    depth_m: float,
    columns: List[Dict[str, Any]],
    existing_beams: List[Dict[str, Any]],
    slab_edge_polygon: List[List[float]],
    is_tie_beam_story: bool = False,
    openings: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validates strict Revit-style structural beam rules:
    1. Outer Slab Boundary (Polyline) must exist on Slab stories, UNLESS `is_tie_beam_story=True`
       (00_TieBeams), where Tie Beams can be drawn directly between columns without a boundary!
    2. On `00_TieBeams`, only Drop Beams (Grade/Tie Beams) are allowed (Hidden Beams are forbidden).
    3. Opening-Adjacent Rule: A Hidden Beam crossing an opening void or trapped with no expansion room is
       automatically converted to a Drop Beam (`0.20 × 0.40 m`) so its width never expands into the void!
    4. Structural Hierarchy Rule: A Drop Beam (`drop`) CANNOT rest on a Hidden Beam (`hidden`)!
    5. Full Outer-Face Column Bearing & Full-Width Beam Boundary Shift.
    6. Duplicate Overlapping Beam Prevention & Continuous Multi-Span Recognition.
    """
    if is_tie_beam_story and str(beam_kind).lower() == "hidden":
        return (
            False,
            None,
            "Tie-Beams Story Rule: Hidden beams are not allowed on the Tie-Beams story (00_TieBeams). Use Drop Beams (Grade/Tie Beams).",
        )

    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(slab_edge_polygon)
    if not has_bnd and not is_tie_beam_story:
        return False, None, "Draw the Outer Building Boundary Polyline (00-XD-EDGE) first before drawing beams."

    active_cols = [c for c in columns if c.get("active", True)]
    if not active_cols:
        return False, None, "Place or import Structural Columns (00-XD-COL) before drawing beams."

    sx, sy = round(float(start_pt[0]), 3), round(float(start_pt[1]), 3)
    ex, ey = round(float(end_pt[0]), 3), round(float(end_pt[1]), 3)

    tol = 0.35
    if has_bnd:
        if sx < min_x - tol or sx > max_x + tol or sy < min_y - tol or sy > max_y + tol:
            return False, None, f"Beam start point ({sx:.2f}, {sy:.2f}) is outside the Building Boundary."
        if ex < min_x - tol or ex > max_x + tol or ey < min_y - tol or ey > max_y + tol:
            return False, None, f"Beam end point ({ex:.2f}, {ey:.2f}) is outside the Building Boundary."

    half_w = float(width_m) / 2.0
    shifted_note = ""
    if abs(ex - sx) >= abs(ey - sy):
        ey = sy
        if sx > ex:
            sx, ex = ex, sx
        is_horizontal = True
        if has_bnd:
            clamped_y = min(max(sy, min_y + half_w), max_y - half_w)
            if abs(clamped_y - sy) > 1e-4:
                shifted_note = f" [Shifted beam axis Y from {sy:.2f}m to {clamped_y:.2f}m so full width ({width_m:.2f}m) stays inside building boundary]"
                sy = ey = round(clamped_y, 3)
    else:
        ex = sx
        if sy > ey:
            sy, ey = ey, sy
        is_horizontal = False
        if has_bnd:
            clamped_x = min(max(sx, min_x + half_w), max_x - half_w)
            if abs(clamped_x - sx) > 1e-4:
                shifted_note = f" [Shifted beam axis X from {sx:.2f}m to {clamped_x:.2f}m so full width ({width_m:.2f}m) stays inside building boundary]"
                sx = ex = round(clamped_x, 3)

    # Discover all supporting columns and perpendicular beams along the beam path
    supports_raw: List[Dict[str, Any]] = []
    snap_tol = max(0.45, half_w + 0.28)

    for col in active_cols:
        cx, cy = float(col["x"]), float(col["y"])
        b_col = float(col.get("b_m", 0.20))
        h_col = float(col.get("h_m", 0.40))
        if is_horizontal:
            if abs(cy - sy) <= max(snap_tol, h_col / 2.0 + half_w + 0.15) and (sx - b_col / 2.0 - 0.35) <= cx <= (ex + b_col / 2.0 + 0.35):
                supports_raw.append({
                    "coord": cx,
                    "x": cx,
                    "y": sy,
                    "kind": "column",
                    "target_id": col["id"],
                    "width_m": b_col,
                    "depth_m": h_col,
                })
        else:
            if abs(cx - sx) <= max(snap_tol, b_col / 2.0 + half_w + 0.15) and (sy - h_col / 2.0 - 0.35) <= cy <= (ey + h_col / 2.0 + 0.35):
                supports_raw.append({
                    "coord": cy,
                    "x": sx,
                    "y": cy,
                    "kind": "column",
                    "target_id": col["id"],
                    "width_m": h_col,
                    "depth_m": b_col,
                })

    for ob in existing_beams:
        if ob.get("id") == beam_id:
            continue
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        ob_horiz = abs(oex - osx) >= abs(oey - osy)
        ob_kind = "drop" if "drop" in str(ob.get("beam_kind", ob.get("kind", "hidden"))).lower() else "hidden"
        if is_horizontal and not ob_horiz:
            bx = osx
            omin_y, omax_y = min(osy, oey), max(osy, oey)
            if (sx - 0.28) <= bx <= (ex + 0.28) and omin_y - 0.28 <= sy <= omax_y + 0.28:
                if not any(abs(s["coord"] - bx) < 0.30 for s in supports_raw):
                    d_bm_end = min(abs(bx - sx), abs(bx - ex))
                    d_ob_end = min(abs(sy - omin_y), abs(sy - omax_y))
                    if not (d_ob_end <= 0.45 and d_bm_end > 0.45):
                        supports_raw.append({
                            "coord": bx,
                            "x": bx,
                            "y": sy,
                            "kind": "beam",
                            "target_id": ob["id"],
                            "beam_kind": ob_kind,
                            "width_m": float(ob.get("width_m", 0.30)),
                            "depth_m": float(ob.get("depth_m", 0.30)),
                            "pos_on_carrier_m": round(abs(sy - omin_y), 3),
                        })
        elif not is_horizontal and ob_horiz:
            by = osy
            omin_x, omax_x = min(osx, oex), max(osx, oex)
            if (sy - 0.28) <= by <= (ey + 0.28) and omin_x - 0.28 <= sx <= omax_x + 0.28:
                if not any(abs(s["coord"] - by) < 0.30 for s in supports_raw):
                    d_bm_end = min(abs(by - sy), abs(by - ey))
                    d_ob_end = min(abs(sx - omin_x), abs(sx - omax_x))
                    if not (d_ob_end <= 0.45 and d_bm_end > 0.45):
                        supports_raw.append({
                            "coord": by,
                            "x": sx,
                            "y": by,
                            "kind": "beam",
                            "target_id": ob["id"],
                            "beam_kind": ob_kind,
                            "width_m": float(ob.get("width_m", 0.30)),
                            "depth_m": float(ob.get("depth_m", 0.30)),
                            "pos_on_carrier_m": round(abs(sx - omin_x), 3),
                        })

    supports_raw.sort(key=lambda s: s["coord"])
    if len(supports_raw) == 0:
        return False, None, "Beam must rest on at least one Column or Supporting Beam."

    # Check if beam borders an opening when drawn as Hidden -> force to Drop Beam (0.20 x 0.40 m) with alert note
    opening_note = ""
    if openings and str(beam_kind).lower() == "hidden":
        probe_bm = {
            "id": beam_id,
            "beam_kind": beam_kind,
            "width_m": width_m,
            "depth_m": depth_m,
            "start_x": sx,
            "start_y": sy,
            "end_x": ex,
            "end_y": ey,
        }
        crossing_ops = [
            str(op.get("id", "OP"))
            for op in openings
            if beam_borders_or_crosses_opening(probe_bm, op) == "crosses"
        ]
        has_room = beam_has_solid_slab_expansion_room(
            {"slab_edge_polygon": slab_edge_polygon, "openings": openings},
            probe_bm,
        )
        if crossing_ops or not has_room:
            beam_kind = "drop"
            width_m = 0.20
            depth_m = 0.40
            half_w = width_m / 2.0
            opening_note = (
                f" [Opening Rule: Beam {beam_id} converted to Drop Beam (0.20x0.40m) "
                f"because it cuts across opening void or lacks solid slab expansion room]"
            )
            _log_eng("OPENING_BEAM_RULE", f"Beam {beam_id} drawn near void forced to Drop 0.20x0.40m")

    # STRICT STRUCTURAL RULE: A Drop Beam CANNOT rest on a Hidden Beam!
    if str(beam_kind).lower() == "drop":
        hidden_carriers = [
            str(s["target_id"])
            for s in supports_raw
            if s.get("kind") == "beam" and s.get("beam_kind") == "hidden"
        ]
        if hidden_carriers and not opening_note:
            return (
                False,
                None,
                f"Structural Hierarchy Error: Drop Beam {beam_id} cannot rest on Hidden Beam(s) {', '.join(hidden_carriers)}! "
                f"Convert {', '.join(hidden_carriers)} to a Drop Beam first, or draw {beam_id} as a Hidden Beam.",
            )

    # REVIT FULL-COLUMN-FACE EXTENSION + STRICT BOUNDARY CLAMPING:
    first_sup = supports_raw[0]
    last_sup = supports_raw[-1]
    first_outer_edge = round(first_sup["coord"] - float(first_sup["width_m"]) / 2.0, 3)
    last_outer_edge = round(last_sup["coord"] + float(last_sup["width_m"]) / 2.0, 3)

    if is_horizontal:
        if sx >= first_outer_edge - 0.05 and abs(sx - first_sup["coord"]) <= float(first_sup["width_m"]) + 0.30:
            sx = max(min_x, first_outer_edge) if has_bnd else first_outer_edge
        if ex <= last_outer_edge + 0.05 and abs(ex - last_sup["coord"]) <= float(last_sup["width_m"]) + 0.30:
            ex = min(max_x, last_outer_edge) if has_bnd else last_outer_edge
        if has_bnd:
            sx = round(min(max(sx, min_x), max_x), 3)
            ex = round(min(max(ex, min_x), max_x), 3)
            sy = ey = round(min(max(sy, min_y + half_w), max_y - half_w), 3)
        else:
            sx, ex, sy, ey = round(sx, 3), round(ex, 3), round(sy, 3), round(ey, 3)
    else:
        if sy >= first_outer_edge - 0.05 and abs(sy - first_sup["coord"]) <= float(first_sup["width_m"]) + 0.30:
            sy = max(min_y, first_outer_edge) if has_bnd else first_outer_edge
        if ey <= last_outer_edge + 0.05 and abs(ey - last_sup["coord"]) <= float(last_sup["width_m"]) + 0.30:
            ey = min(max_y, last_outer_edge) if has_bnd else last_outer_edge
        if has_bnd:
            sy = round(min(max(sy, min_y), max_y), 3)
            ey = round(min(max(ey, min_y), max_y), 3)
            sx = ex = round(min(max(sx, min_x + half_w), max_x - half_w), 3)
        else:
            sx, ex, sy, ey = round(sx, 3), round(ex, 3), round(sy, 3), round(ey, 3)

    total_len = round(math.hypot(ex - sx, ey - sy), 3)
    if total_len < 0.40:
        return False, None, "Beam length is too short (< 0.40 m)."

    TOL = 0.010  # 10 mm
    shared_notes: List[str] = []
    for ob in existing_beams:
        if ob.get("id") == beam_id:
            continue
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        ob_horiz = abs(oex - osx) >= abs(oey - osy)

        if is_horizontal and ob_horiz and abs(sy - osy) <= 0.025:
            new_a, new_b = min(sx, ex), max(sx, ex)
            old_a, old_b = min(osx, oex), max(osx, oex)

            for s in supports_raw:
                s_id = str(s.get("target_id", ""))
                s_coord = float(s.get("coord", 0.0))
                if any(str(osup.get("target_id")) == s_id for osup in ob.get("supports", [])):
                    shared_notes.append(f"{beam_id} shares {s_id} with {ob['id']}; modeled independently.")
                    if abs(old_b - new_a) <= float(s.get("width_m", 0.40)) + 0.05 and old_a < s_coord < new_b:
                        old_b = s_coord
                        new_a = s_coord
                    elif abs(new_b - old_a) <= float(s.get("width_m", 0.40)) + 0.05 and new_a < s_coord < old_b:
                        new_b = s_coord
                        old_a = s_coord

            if abs(new_a - old_a) <= TOL and abs(new_b - old_b) <= TOL:
                return False, None, f"Duplicate beam: same segment as {ob['id']}"

            ov = min(new_b, old_b) - max(new_a, old_a)
            if ov > TOL:
                return False, None, f"Overlapping beam: overlaps {ob['id']}; adjust ends or use Extend"

        elif (not is_horizontal) and (not ob_horiz) and abs(sx - osx) <= 0.025:
            new_a, new_b = min(sy, ey), max(sy, ey)
            old_a, old_b = min(osy, oey), max(osy, oey)

            for s in supports_raw:
                s_id = str(s.get("target_id", ""))
                s_coord = float(s.get("coord", 0.0))
                if any(str(osup.get("target_id")) == s_id for osup in ob.get("supports", [])):
                    shared_notes.append(f"{beam_id} shares {s_id} with {ob['id']}; modeled independently.")
                    if abs(old_b - new_a) <= float(s.get("width_m", 0.40)) + 0.05 and old_a < s_coord < new_b:
                        old_b = s_coord
                        new_a = s_coord
                    elif abs(new_b - old_a) <= float(s.get("width_m", 0.40)) + 0.05 and new_a < s_coord < old_b:
                        new_b = s_coord
                        old_a = s_coord

            if abs(new_a - old_a) <= TOL and abs(new_b - old_b) <= TOL:
                return False, None, f"Duplicate beam: same segment as {ob['id']}"

            ov = min(new_b, old_b) - max(new_a, old_a)
            if ov > TOL:
                return False, None, f"Overlapping beam: overlaps {ob['id']}; adjust ends or use Extend"

    start_coord = sx if is_horizontal else sy
    end_coord = ex if is_horizontal else ey
    supports_along: List[Dict[str, Any]] = []
    for s in supports_raw:
        s_copy = dict(s)
        s_copy["pos_m"] = round(max(0.0, min(total_len, s["coord"] - start_coord)), 3)
        supports_along.append(s_copy)

    # Calculate true cantilevers strictly beyond the outer face of the first/last support
    raw_cant_left = round(first_sup["coord"] - start_coord, 3)
    raw_cant_right = round(end_coord - last_sup["coord"], 3)
    overhang_beyond_first_face = round(first_outer_edge - start_coord, 3)
    overhang_beyond_last_face = round(end_coord - last_outer_edge, 3)

    cant_left = raw_cant_left if overhang_beyond_first_face > 0.25 else 0.0
    cant_right = raw_cant_right if overhang_beyond_last_face > 0.25 else 0.0

    tip_left = (sx, sy)
    tip_right = (ex, ey)
    story_dummy = {"slabs": [], "columns": columns, "beams": existing_beams, "slab_edge_polygon": slab_edge_polygon, "openings": openings or []}

    if has_bnd and cant_left > 0.25:
        ok_tip, tip_err = validate_cantilever_tip(tip_left, cant_left, story_dummy, active_cols, existing_beams, slab_edge_polygon, openings, tol2=0.025)
        if not ok_tip:
            return False, None, tip_err
    if has_bnd and cant_right > 0.25:
        ok_tip, tip_err = validate_cantilever_tip(tip_right, cant_right, story_dummy, active_cols, existing_beams, slab_edge_polygon, openings, tol2=0.025)
        if not ok_tip:
            return False, None, tip_err

    spans: List[float] = []
    for idx in range(len(supports_along) - 1):
        sp = round(supports_along[idx + 1]["coord"] - supports_along[idx]["coord"], 3)
        if sp >= 0.30:
            spans.append(sp)

    if not spans:
        if cant_left > 0.35:
            spans = [cant_left]
        elif cant_right > 0.35:
            spans = [cant_right]
        else:
            return False, None, "Beam must span between at least two supports or project as a valid boundary cantilever."

    formatted_supports = []
    for idx, sup in enumerate(supports_along):
        entry = {
            "support_index": idx + 1,
            "kind": sup["kind"],
            "target_id": sup["target_id"],
            "width_m": sup["width_m"],
            "center_coord_m": round(sup["coord"], 3),
        }
        if "pos_on_carrier_m" in sup:
            entry["pos_on_carrier_m"] = sup["pos_on_carrier_m"]
        formatted_supports.append(entry)

    default_w = 28.0 if beam_kind == "drop" else 34.0
    sup_names = " -> ".join(s["target_id"] for s in formatted_supports)
    beam_dict = {
        "id": beam_id,
        "shared_node_note": (" | ".join(shared_notes) if shared_notes else ""),
        "beam_kind": beam_kind,
        "width_m": width_m,
        "depth_m": depth_m,
        "start_x": sx,
        "start_y": sy,
        "end_x": ex,
        "end_y": ey,
        "room_bounding": True,
        "cantilever_left_m": cant_left if len(supports_along) >= 2 else 0.0,
        "cantilever_right_m": cant_right if len(supports_along) >= 2 else 0.0,
        "spans": spans,
        "supports": formatted_supports,
        "loads": [{"type": "dist", "x1": 0.0, "x2": round(sum(spans), 3), "val": default_w}],
    }
    return (
        True,
        beam_dict,
        f"Beam {beam_id} created ({len(spans)} span(s) [{', '.join(f'{s:.2f}m' for s in spans)}] over {sup_names}, full outer-column bearing [{sx:.2f},{sy:.2f}]->[{ex:.2f},{ey:.2f}]).{shifted_note}{opening_note}",
    )


def _point_in_polygon_2d(px: float, py: float, poly: List[List[float]]) -> bool:
    """
    Ray-casting point-in-polygon check with boundary tolerance (0.15m) so L-shaped and stepped
    building polygons accurately exclude exterior void corners while including perimeter bays.
    """
    n = len(poly)
    if n < 3:
        return True
    # Check if point is within 0.15m of any polygon edge
    for idx in range(n):
        x1, y1 = float(poly[idx][0]), float(poly[idx][1])
        x2, y2 = float(poly[(idx + 1) % n][0]), float(poly[(idx + 1) % n][1])
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 > 1e-6:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg2))
            if math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)) <= 0.15:
                return True

    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = float(poly[i][0]), float(poly[i][1])
        xj, yj = float(poly[j][0]), float(poly[j][1])
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def has_beam_on_segment(story_data: Dict[str, Any], x1: float, y1: float, x2: float, y2: float) -> Optional[Dict[str, Any]]:
    """
    Checks if a physical beam exists along the line segment (x1, y1) -> (x2, y2).
    Uses tighter end tolerance (+0.05m instead of +0.35m) to prevent phantom overlap
    from beams terminating at an intersection from bleeding into adjacent segments.
    """
    beams = story_data.get("beams", [])
    is_seg_horiz = abs(x2 - x1) >= abs(y2 - y1)
    seg_len = max(0.10, abs(x2 - x1) if is_seg_horiz else abs(y2 - y1))
    for bm in beams:
        bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        b_width = float(bm.get("width_m", 0.40))
        tol_lat = max(0.20, b_width / 2.0 + 0.08)
        b_horiz = abs(bex - bsx) >= abs(bey - bsy)
        if is_seg_horiz and b_horiz and abs(bsy - y1) <= tol_lat:
            b_min, b_max = min(bsx, bex), max(bsx, bex)
            s_min, s_max = min(x1, x2), max(x1, x2)
            ov = min(b_max + 0.05, s_max) - max(b_min - 0.05, s_min)
            if ov >= seg_len * 0.60:
                return bm
        elif (not is_seg_horiz) and (not b_horiz) and abs(bsx - x1) <= tol_lat:
            b_min, b_max = min(bsy, bey), max(bsy, bey)
            s_min, s_max = min(y1, y2), max(y1, y2)
            ov = min(b_max + 0.05, s_max) - max(b_min - 0.05, s_min)
            if ov >= seg_len * 0.60:
                return bm
    return None


def detect_story_grid_bays(story_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Revit Room-Bounding Bay Detection with True Physical Beam-Bounded Room Merging:
    - NEVER creates slab bays from the Outer Building Boundary alone! At least 3 beams must exist.
    - Eliminates Phantom Beam Splitting: A partial beam in one bay (such as a stair trimmer beam B8 or B9)
      NEVER splits an adjacent bay unless a physical beam actually exists along the shared edge!
    - Supports L-Shaped and Stepped Building Polygons by verifying each cell center against `slab_edge_polygon`.
    - Subtracts the physical footprint (`width_m / 2`) of bounding North, South, East, and West beams
      to provide `clear_min_x, clear_max_x, clear_min_y, clear_max_y` so slabs and ribs NEVER draw
      over the body of any beam (`room_bounding = True`).
    """
    poly = story_data.get("slab_edge_polygon", [])
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(poly)
    if not has_bnd:
        return []

    beams = story_data.get("beams", [])
    if len(beams) < 3:
        return []

    xs = [round(min_x, 3), round(max_x, 3)]
    ys = [round(min_y, 3), round(max_y, 3)]

    # Include polygon vertices for L-shaped or stepped boundaries
    for pt in poly:
        vx, vy = round(float(pt[0]), 3), round(float(pt[1]), 3)
        if min_x < vx < max_x and all(abs(vx - ex) > 0.45 for ex in xs):
            xs.append(vx)
        if min_y < vy < max_y and all(abs(vy - ey) > 0.45 for ey in ys):
            ys.append(vy)

    for bm in beams:
        sx, sy = round(float(bm.get("start_x", 0.0)), 3), round(float(bm.get("start_y", 0.0)), 3)
        ex, ey = round(float(bm.get("end_x", 0.0)), 3), round(float(bm.get("end_y", 0.0)), 3)
        b_width = float(bm.get("width_m", 0.40))
        edge_snap_margin = max(0.45, b_width + 0.15)
        if abs(ex - sx) >= abs(ey - sy):
            if abs(sy - min_y) <= edge_snap_margin or abs(sy - max_y) <= edge_snap_margin:
                continue
            if min_y < sy < max_y and all(abs(sy - existing_y) > 0.45 for existing_y in ys):
                ys.append(sy)
        else:
            if abs(sx - min_x) <= edge_snap_margin or abs(sx - max_x) <= edge_snap_margin:
                continue
            if min_x < sx < max_x and all(abs(sx - existing_x) > 0.45 for existing_x in xs):
                xs.append(sx)

    sorted_x = sorted(xs)
    sorted_y = sorted(ys)

    def has_beam_on_segment(x1: float, y1: float, x2: float, y2: float) -> Optional[Dict[str, Any]]:
        return globals()["has_beam_on_segment"](story_data, x1, y1, x2, y2)

    def has_poly_edge_on_segment(x1: float, y1: float, x2: float, y2: float) -> bool:
        is_seg_horiz = abs(x2 - x1) >= abs(y2 - y1)
        seg_len = max(0.10, abs(x2 - x1) if is_seg_horiz else abs(y2 - y1))
        n = len(poly)
        for idx in range(n):
            px1, py1 = float(poly[idx][0]), float(poly[idx][1])
            px2, py2 = float(poly[(idx + 1) % n][0]), float(poly[(idx + 1) % n][1])
            p_horiz = abs(px2 - px1) >= abs(py2 - py1)
            if is_seg_horiz and p_horiz and abs(py1 - y1) <= 0.25:
                p_min, p_max = min(px1, px2), max(px1, px2)
                s_min, s_max = min(x1, x2), max(x1, x2)
                ov = min(p_max + 0.05, s_max) - max(p_min - 0.05, s_min)
                if ov >= seg_len * 0.60:
                    return True
            elif (not is_seg_horiz) and (not p_horiz) and abs(px1 - x1) <= 0.25:
                p_min, p_max = min(py1, py2), max(py1, py2)
                s_min, s_max = min(y1, y2), max(y1, y2)
                ov = min(p_max + 0.05, s_max) - max(p_min - 0.05, s_min)
                if ov >= seg_len * 0.60:
                    return True
        return False

    # Step 1: Build elementary cells inside the building boundary polygon
    raw_rects: List[Dict[str, Any]] = []
    for j in range(len(sorted_y) - 1):
        y_bot, y_top = sorted_y[j], sorted_y[j + 1]
        if (y_top - y_bot) < 0.65:
            continue
        for i in range(len(sorted_x) - 1):
            x_left, x_right = sorted_x[i], sorted_x[i + 1]
            if (x_right - x_left) < 0.65:
                continue
            cx, cy = (x_left + x_right) / 2.0, (y_bot + y_top) / 2.0
            if not _point_in_polygon_2d(cx, cy, poly):
                continue
            raw_rects.append({
                "min_x": x_left,
                "max_x": x_right,
                "min_y": y_bot,
                "max_y": y_top,
                "grid_i": i,
                "grid_j": j,
            })

    # Step 2: Iteratively coalesce adjacent rectangles that do NOT have a physical beam or boundary edge
    # separating their shared border! This guarantees that partial beams in one bay NEVER slice neighboring bays!
    merged_changed = True
    while merged_changed:
        merged_changed = False
        n_r = len(raw_rects)
        used = [False] * n_r
        next_rects: List[Dict[str, Any]] = []

        for a_idx in range(n_r):
            if used[a_idx]:
                continue
            ra = dict(raw_rects[a_idx])
            for b_idx in range(a_idx + 1, n_r):
                if used[b_idx]:
                    continue
                rb = raw_rects[b_idx]
                # Case A: Same Y-interval [min_y, max_y] and touching horizontally at X = ra["max_x"] == rb["min_x"]
                if (
                    abs(ra["min_y"] - rb["min_y"]) < 1e-4
                    and abs(ra["max_y"] - rb["max_y"]) < 1e-4
                    and abs(ra["max_x"] - rb["min_x"]) < 1e-4
                ):
                    shared_x = ra["max_x"]
                    if (
                        has_beam_on_segment(shared_x, ra["min_y"], shared_x, ra["max_y"]) is None
                        and not has_poly_edge_on_segment(shared_x, ra["min_y"], shared_x, ra["max_y"])
                    ):
                        ra["max_x"] = rb["max_x"]
                        used[b_idx] = True
                        merged_changed = True
                # Case B: Same X-interval [min_x, max_x] and touching vertically at Y = ra["max_y"] == rb["min_y"]
                elif (
                    abs(ra["min_x"] - rb["min_x"]) < 1e-4
                    and abs(ra["max_x"] - rb["max_x"]) < 1e-4
                    and abs(ra["max_y"] - rb["min_y"]) < 1e-4
                ):
                    shared_y = ra["max_y"]
                    if (
                        has_beam_on_segment(ra["min_x"], shared_y, ra["max_x"], shared_y) is None
                        and not has_poly_edge_on_segment(ra["min_x"], shared_y, ra["max_x"], shared_y)
                    ):
                        ra["max_y"] = rb["max_y"]
                        used[b_idx] = True
                        merged_changed = True
            used[a_idx] = True
            next_rects.append(ra)
        raw_rects = next_rects

    # Sort top-to-bottom (or bottom-to-top, left-to-right) deterministically
    raw_rects.sort(key=lambda r: (round(r["min_y"], 2), round(r["min_x"], 2)))

    bays: List[Dict[str, Any]] = []
    bay_counter = 1
    for rc in raw_rects:
        x_left, x_right = rc["min_x"], rc["max_x"]
        y_bot, y_top = rc["min_y"], rc["max_y"]
        lx = round(x_right - x_left, 3)
        ly = round(y_top - y_bot, 3)
        if lx < 0.85 or ly < 0.85:
            continue

        bm_top = has_beam_on_segment(x_left, y_top, x_right, y_top)
        bm_bot = has_beam_on_segment(x_left, y_bot, x_right, y_bot)
        bm_left = has_beam_on_segment(x_left, y_bot, x_left, y_top)
        bm_right = has_beam_on_segment(x_right, y_bot, x_right, y_top)

        poly_top = has_poly_edge_on_segment(x_left, y_top, x_right, y_top)
        poly_bot = has_poly_edge_on_segment(x_left, y_bot, x_right, y_bot)
        poly_left = has_poly_edge_on_segment(x_left, y_bot, x_left, y_top)
        poly_right = has_poly_edge_on_segment(x_right, y_bot, x_right, y_top)

        bounding_sides = {
            "North": bm_top["id"] if bm_top else None,
            "South": bm_bot["id"] if bm_bot else None,
            "West": bm_left["id"] if bm_left else None,
            "East": bm_right["id"] if bm_right else None,
        }
        poly_sides = {
            "North": poly_top,
            "South": poly_bot,
            "West": poly_left,
            "East": poly_right,
        }
        beam_count = sum(1 for v in bounding_sides.values() if v is not None)
        closed_edge_count = sum(1 for k in ("North", "South", "West", "East") if (bounding_sides[k] is not None or poly_sides[k]))
        effective_beam_count = 3 if (beam_count >= 1 and closed_edge_count == 4 and min(lx, ly) <= 2.60) else beam_count

        # Compute Room-Bounding Clear Inner Face Coordinates (excluding beam widths)
        w_left_in = (float(bm_left.get("width_m", 0.20)) / 2.0) if bm_left else 0.0
        w_right_in = (float(bm_right.get("width_m", 0.20)) / 2.0) if bm_right else 0.0
        w_bot_in = (float(bm_bot.get("width_m", 0.40)) / 2.0) if bm_bot else 0.0
        w_top_in = (float(bm_top.get("width_m", 0.40)) / 2.0) if bm_top else 0.0

        if bm_left and float(bm_left.get("start_x", x_left)) > x_left:
            clear_min_x = round(float(bm_left.get("start_x", x_left)) + w_left_in, 3)
        else:
            clear_min_x = round(x_left + w_left_in, 3)

        if bm_right and float(bm_right.get("start_x", x_right)) < x_right:
            clear_max_x = round(float(bm_right.get("start_x", x_right)) - w_right_in, 3)
        else:
            clear_max_x = round(x_right - w_right_in, 3)

        if bm_bot and float(bm_bot.get("start_y", y_bot)) > y_bot:
            clear_min_y = round(float(bm_bot.get("start_y", y_bot)) + w_bot_in, 3)
        else:
            clear_min_y = round(y_bot + w_bot_in, 3)

        if bm_top and float(bm_top.get("start_y", y_top)) < y_top:
            clear_max_y = round(float(bm_top.get("start_y", y_top)) - w_top_in, 3)
        else:
            clear_max_y = round(y_top - w_top_in, 3)

        bays.append({
            "bay_key": f"BAY_{round(x_left*10)}_{round(y_bot*10)}_{round(x_right*10)}_{round(y_top*10)}",
            "default_id": f"S{bay_counter}",
            "grid_i": rc["grid_i"],
            "grid_j": rc["grid_j"],
            "min_x": x_left,
            "max_x": x_right,
            "min_y": y_bot,
            "max_y": y_top,
            "clear_min_x": clear_min_x,
            "clear_max_x": clear_max_x,
            "clear_min_y": clear_min_y,
            "clear_max_y": clear_max_y,
            "lx_m": lx,
            "ly_m": ly,
            "bounding_beams": bounding_sides,
            "poly_sides": poly_sides,
            "beam_count": effective_beam_count,
            "raw_beam_count": beam_count,
        })
        bay_counter += 1
    return bays


def _find_adjacent_backspan_bays(
    target_bay: Dict[str, Any],
    all_bays: List[Dict[str, Any]],
    cantilever_free_side: str,
) -> List[Dict[str, Any]]:
    """
    Finds all bays that share the interior supporting beam opposite to `cantilever_free_side`
    using exact geometric boundary overlap (never relying on grid_i/grid_j indices).
    """
    tmin_x, tmax_x = float(target_bay["min_x"]), float(target_bay["max_x"])
    tmin_y, tmax_y = float(target_bay["min_y"]), float(target_bay["max_y"])
    matches: List[Dict[str, Any]] = []

    for b in all_bays:
        if b["bay_key"] == target_bay["bay_key"]:
            continue
        bmin_x, bmax_x = float(b["min_x"]), float(b["max_x"])
        bmin_y, bmax_y = float(b["min_y"]), float(b["max_y"])
        ov_x = min(tmax_x, bmax_x) - max(tmin_x, bmin_x)
        ov_y = min(tmax_y, bmax_y) - max(tmin_y, bmin_y)

        if cantilever_free_side == "South":
            # Supporting carrier beam is on the North edge of target_bay (y = tmax_y)
            if abs(bmin_y - tmax_y) <= 0.35 and ov_x >= 0.40:
                matches.append(b)
        elif cantilever_free_side == "North":
            # Supporting carrier beam is on the South edge of target_bay (y = tmin_y)
            if abs(bmax_y - tmin_y) <= 0.35 and ov_x >= 0.40:
                matches.append(b)
        elif cantilever_free_side == "East":
            # Supporting carrier beam is on the West edge of target_bay (x = tmin_x)
            if abs(bmax_x - tmin_x) <= 0.35 and ov_y >= 0.40:
                matches.append(b)
        elif cantilever_free_side == "West":
            # Supporting carrier beam is on the East edge of target_bay (x = tmax_x)
            if abs(bmin_x - tmax_x) <= 0.35 and ov_y >= 0.40:
                matches.append(b)
    return matches


def _detect_cantilever_free_side(
    story_data: Dict[str, Any],
    target_bay: Dict[str, Any],
    all_bays: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Determines if `target_bay` is a structural cantilever overhang (and returns which outer edge is free:
    'South', 'North', 'East', or 'West').
    Handles:
    1. 3-Beam Bays where one perimeter side has no beam (`sides[side] is None`).
    2. Pure Cantilever Balcony Bays bounded by 1 carrier beam + 3 building boundary edges.
    3. Overhanging Cantilever Bays that project beyond the outer column line (where side beams have
       cantilever overhangs or no columns exist along the outer perimeter edge while a carrier beam
       separates it from an interior back-span bay).
    """
    sides = target_bay["bounding_beams"]
    raw_bc = int(target_bay.get("raw_beam_count", target_bay["beam_count"]))
    if raw_bc == 3:
        for side_name in ("South", "North", "East", "West"):
            if sides.get(side_name) is None:
                return side_name
    elif raw_bc == 1:
        if sides.get("North") is not None and _find_adjacent_backspan_bays(target_bay, all_bays, "South"):
            return "South"
        if sides.get("South") is not None and _find_adjacent_backspan_bays(target_bay, all_bays, "North"):
            return "North"
        if sides.get("West") is not None and _find_adjacent_backspan_bays(target_bay, all_bays, "East"):
            return "East"
        if sides.get("East") is not None and _find_adjacent_backspan_bays(target_bay, all_bays, "West"):
            return "West"

    # Check if this bay is an overhanging balcony/cantilever projecting on the OUTER perimeter of the building
    # (meaning there is NO bay on the free side, it lies on the outer building perimeter, and an interior back-span bay exists on the opposite side).
    cols = [c for c in story_data.get("columns", []) if c.get("active", True)]
    tmin_x, tmax_x = float(target_bay["min_x"]), float(target_bay["max_x"])
    tmin_y, tmax_y = float(target_bay["min_y"]), float(target_bay["max_y"])
    lx, ly = float(target_bay["lx_m"]), float(target_bay["ly_m"])
    has_bnd, poly_min_x, poly_min_y, poly_max_x, poly_max_y = get_slab_bounding_box(
        story_data.get("slab_edge_polygon", [])
    )

    def has_col_near_edge(x1: float, y1: float, x2: float, y2: float) -> bool:
        is_h = abs(x2 - x1) >= abs(y2 - y1)
        for c in cols:
            cx, cy = float(c["x"]), float(c["y"])
            if is_h and abs(cy - y1) <= 0.45 and (min(x1, x2) - 0.35) <= cx <= (max(x1, x2) + 0.35):
                return True
            if (not is_h) and abs(cx - x1) <= 0.45 and (min(y1, y2) - 0.35) <= cy <= (max(y1, y2) + 0.35):
                return True
        return False

    if ly <= 2.60:
        if (
            (not has_bnd or abs(tmin_y - poly_min_y) <= 0.35)
            and not has_col_near_edge(tmin_x, tmin_y, tmax_x, tmin_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "North")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "South")
        ):
            return "South"
        if (
            (not has_bnd or abs(tmax_y - poly_max_y) <= 0.35)
            and not has_col_near_edge(tmin_x, tmax_y, tmax_x, tmax_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "South")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "North")
        ):
            return "North"
    if lx <= 2.60:
        if (
            (not has_bnd or abs(tmax_x - poly_max_x) <= 0.35)
            and not has_col_near_edge(tmax_x, tmin_y, tmax_x, tmax_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "West")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "East")
        ):
            return "East"
        if (
            (not has_bnd or abs(tmin_x - poly_min_x) <= 0.35)
            and not has_col_near_edge(tmin_x, tmin_y, tmin_x, tmax_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "East")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "West")
        ):
            return "West"
    return None


def _find_controlling_cantilever_slabs_for_bay(
    story_data: Dict[str, Any],
    target_bay: Dict[str, Any],
    all_bays: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Dynamically checks live geometry across all existing slabs in `story_data['slabs']` to determine
    if `target_bay` is currently acting as the back-span extension (Cantilever Back-Span Continuity) for any
    adjacent Cantilever Slab whose ribs are oriented perpendicular to the shared carrier beam.
    Immune to slab splitting, beam additions, or creation order!
    """
    t_key = target_bay["bay_key"]
    bay_by_key = {b["bay_key"]: b for b in all_bays}
    controlling: List[Dict[str, Any]] = []

    for slb in story_data.get("slabs", []):
        if "min_x" not in slb:
            continue
        s_key = slb.get("bay_key")
        other_bay = bay_by_key.get(s_key)
        if other_bay is None:
            scx = (float(slb["min_x"]) + float(slb["max_x"])) / 2.0
            scy = (float(slb["min_y"]) + float(slb["max_y"])) / 2.0
            for b in all_bays:
                if b["min_x"] - 0.10 <= scx <= b["max_x"] + 0.10 and b["min_y"] - 0.10 <= scy <= b["max_y"] + 0.10:
                    other_bay = b
                    break
        if other_bay is None or other_bay["bay_key"] == t_key:
            continue

        c_side = _detect_cantilever_free_side(story_data, other_bay, all_bays)
        if c_side is None:
            continue
        c_perp_dir = 90 if c_side in ("South", "North") else 0
        cur_rib_dir = int(slb.get("rib_direction_deg", c_perp_dir))
        if cur_rib_dir == c_perp_dir:
            adj_backs = _find_adjacent_backspan_bays(other_bay, all_bays, c_side)
            if any(ab["bay_key"] == t_key for ab in adj_backs):
                controlling.append(slb)

    return controlling


def reconcile_and_split_slabs_after_beam_change(story_data: Dict[str, Any]) -> Tuple[int, str]:
    """
    SMART AUTOMATIC SLAB SPLITTING & CANTILEVER BACK-SPAN RECONCILIATION:
    When a user draws or deletes a beam, safely updates slabs to match the true physical beam-bounded bays
    and dynamically refreshes Cantilever <-> Back-Span continuity locks without ever crashing.
    """
    try:
        old_slabs = list(story_data.get("slabs", []))
        if not old_slabs:
            return 0, ""

        new_bays = detect_story_grid_bays(story_data)
        if not new_bays:
            story_data["slabs"] = []
            return 0, ""

        reconciled_slabs: List[Dict[str, Any]] = []
        used_bay_keys = set()
        split_count = 0

        for old_s in old_slabs:
            if "min_x" not in old_s:
                continue
            omin_x, omax_x = float(old_s["min_x"]), float(old_s["max_x"])
            omin_y, omax_y = float(old_s["min_y"]), float(old_s["max_y"])
            old_dir = int(old_s.get("rib_direction_deg", 0))

            matching_bays = []
            for b in new_bays:
                bcx = (b["min_x"] + b["max_x"]) / 2.0
                bcy = (b["min_y"] + b["max_y"]) / 2.0
                if (
                    (omin_x - 0.15) <= bcx <= (omax_x + 0.15)
                    and (omin_y - 0.15) <= bcy <= (omax_y + 0.15)
                    and float(b["min_x"]) >= (omin_x - 0.45)
                    and float(b["max_x"]) <= (omax_x + 0.45)
                    and float(b["min_y"]) >= (omin_y - 0.45)
                    and float(b["max_y"]) <= (omax_y + 0.45)
                ):
                    if b["beam_count"] >= 3:
                        matching_bays.append(b)

            if not matching_bays:
                # If a dividing beam was removed/moved and the bay expanded to a larger room:
                expanded_bay = next(
                    (
                        b for b in new_bays
                        if b["beam_count"] >= 3
                        and float(b["min_x"]) <= omin_x + 0.35
                        and float(b["max_x"]) >= omax_x - 0.35
                        and float(b["min_y"]) <= omin_y + 0.35
                        and float(b["max_y"]) >= omax_y - 0.35
                    ),
                    None,
                )
                if expanded_bay is not None and expanded_bay["bay_key"] not in used_bay_keys:
                    matching_bays = [expanded_bay]
                else:
                    reconciled_slabs.append(dict(old_s))
                    continue

            if len(matching_bays) > 1:
                split_count += len(matching_bays)

            for idx_mb, mb in enumerate(matching_bays):
                bkey = mb["bay_key"]
                if bkey in used_bay_keys:
                    continue
                used_bay_keys.add(bkey)
                lx, ly = mb["lx_m"], mb["ly_m"]
                c_side = _detect_cantilever_free_side(story_data, mb, new_bays)
                c_perp = (90 if c_side in ("South", "North") else 0) if c_side else None
                rib_dir = old_dir
                is_cant = bool(c_side is not None and rib_dir == c_perp)
                axis_span = lx if rib_dir == 0 else ly
                preserved_id = str(old_s.get("id", f"S{len(reconciled_slabs) + 1}")) if len(matching_bays) == 1 else f"S{len(reconciled_slabs) + 1}"
                reconciled_slabs.append({
                    "id": preserved_id,
                    "bay_key": bkey,
                    "min_x": mb["min_x"],
                    "max_x": mb["max_x"],
                    "min_y": mb["min_y"],
                    "max_y": mb["max_y"],
                    "clear_min_x": mb["clear_min_x"],
                    "clear_max_x": mb["clear_max_x"],
                    "clear_min_y": mb["clear_min_y"],
                    "clear_max_y": mb["clear_max_y"],
                    "lx_m": lx,
                    "ly_m": ly,
                    "rib_direction_deg": rib_dir,
                    "rib_angle_deg": rib_dir,
                    "axis_span_m": axis_span,
                    "left_support_w_m": 0.30,
                    "right_support_w_m": 0.30,
                    "is_cantilever": is_cant,
                    "cantilever_free_edge": c_side if is_cant else None,
                    "connected_to_cantilever": False,
                    "backspan_bay_key": None,
                    "backspan_bay_keys": [],
                })

        story_data["slabs"] = reconciled_slabs

        # Second pass: refresh back-span links and enforce cantilever continuity dynamically
        bay_by_key = {b["bay_key"]: b for b in new_bays}
        for slb in reconciled_slabs:
            mb = bay_by_key.get(slb["bay_key"])
            if not mb:
                continue
            c_side = _detect_cantilever_free_side(story_data, mb, new_bays)
            c_perp = (90 if c_side in ("South", "North") else 0) if c_side else None
            if c_side is not None and int(slb["rib_direction_deg"]) == c_perp:
                adj_backs = _find_adjacent_backspan_bays(mb, new_bays, c_side)
                if adj_backs:
                    slb["is_cantilever"] = True
                    slb["cantilever_free_edge"] = c_side
                    slb["backspan_bay_key"] = adj_backs[0]["bay_key"]
                    slb["backspan_bay_keys"] = [ab["bay_key"] for ab in adj_backs]
                    for ab in adj_backs:
                        back_slb = next((s for s in reconciled_slabs if s["bay_key"] == ab["bay_key"]), None)
                        if back_slb is not None:
                            back_slb["rib_direction_deg"] = c_perp
                            back_slb["axis_span_m"] = back_slb["lx_m"] if c_perp == 0 else back_slb["ly_m"]
                            back_slb["connected_to_cantilever"] = True

        if split_count > 0:
            return split_count, f"Automatically split existing slab into {len(reconciled_slabs)} independent bays along the dividing beam."
        return 0, ""
    except Exception as exc:
        return 0, f"Slab reconciliation note: {exc}"


def poly_area(points: List[Tuple[float, float]]) -> float:
    """Calculates polygon area via shoelace formula."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1] - points[j][0] * points[i][1]
    return abs(area) / 2.0


from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union

def validate_geometry_before_inference(story_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    v2.4.13 Pre-Inference Geometric Sanity Validator:
    Verifies that the building boundary (00-XD-EDGE) exists and is a valid closed polygon,
    and that all beams have valid finite coordinates.
    """
    raw_poly = story_data.get("slab_edge_polygon", [])
    if not isinstance(raw_poly, list) or len(raw_poly) < 3:
        return False, ["Draw Outer Slab Boundary (00-XD-EDGE) and Beams first before Auto-Filling Slabs."]
    try:
        p_roof = Polygon(raw_poly)
        if not p_roof.is_valid:
            p_roof = p_roof.buffer(0)
            if not p_roof.is_valid or p_roof.area < 1e-3:
                return False, ["Slab edge polygon is self-intersecting or invalid."]
    except Exception as e:
        return False, [f"Invalid slab edge polygon: {e}"]

    beams = story_data.get("beams", [])
    for b in beams:
        try:
            sx = float(b.get("start_x", 0.0))
            sy = float(b.get("start_y", 0.0))
            ex = float(b.get("end_x", 0.0))
            ey = float(b.get("end_y", 0.0))
            if not (math.isfinite(sx) and math.isfinite(sy) and math.isfinite(ex) and math.isfinite(ey)):
                return False, [f"Beam {b.get('id', '?')} has non-finite coordinates."]
        except Exception:
            return False, [f"Beam {b.get('id', '?')} has invalid coordinates."]

    return True, []

def infer_story_slabs_face_based(
    story: Optional[Dict[str, Any]] = None,
    preserve_existing_ids: bool = True,
    story_data: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    v2.4.13 Robust Face-Based Slab Inference Engine (Shapely 2D CAD Boolean Subtraction):
    Infers hollow-block slab panels and overhangs as connected geometric components:
    Slabs = Building Boundary (00-XD-EDGE) - Openings (00-XD-OPEN) - Beams (00-XD-BEAM).
    Classifies all supporting edges, detects cantilevers, locks backspan continuity,
    and returns (inferred_slabs, warnings).
    """
    actual_story = story if story is not None else story_data
    if actual_story is None:
        return [], ["No story data provided."]
    story_data = actual_story

    is_valid, issues = validate_geometry_before_inference(story_data)
    if not is_valid:
        return [], issues

    raw_poly = story_data["slab_edge_polygon"]
    roof_pts = [(round(float(x), 4), round(float(y), 4)) for x, y in raw_poly]
    roof_poly = Polygon(roof_pts)
    if not roof_poly.is_valid:
        roof_poly = roof_poly.buffer(0)

    min_roof_x, min_roof_y, max_roof_x, max_roof_y = roof_poly.bounds

    # Openings
    openings = story_data.get("openings", [])
    op_polys = []
    op_geom_list = []
    for op in openings:
        pts = [(round(float(x), 4), round(float(y), 4)) for x, y in op.get("polygon", [])]
        if len(pts) >= 3:
            op_p = Polygon(pts)
            if not op_p.is_valid:
                op_p = op_p.buffer(0)
            op_polys.append((op.get("id", "OP"), pts, op_p))
            op_geom_list.append(op_p)
    openings_union = unary_union(op_geom_list) if op_geom_list else Polygon()

    # Beams
    beams = story_data.get("beams", [])
    opts = story_data.get("options", {}).get("hollow_block_slab", {})
    def_hid_w = float(opts.get("hidden_beam_min_width_cm", 30.0)) / 100.0
    def_drop_w = float(opts.get("drop_beam_width_cm", 20.0)) / 100.0

    beam_records = []
    beam_geoms = []

    for b in beams:
        b_id = str(b.get("id", "B"))
        b_kind = str(b.get("beam_kind", "drop")).lower()
        def_w = def_hid_w if "hid" in b_kind else def_drop_w
        w = round(float(b.get("width_m", def_w)), 4)
        hw = round(w / 2.0, 4)
        sx = round(float(b.get("start_x", 0.0)), 4)
        sy = round(float(b.get("start_y", 0.0)), 4)
        ex = round(float(b.get("end_x", 0.0)), 4)
        ey = round(float(b.get("end_y", 0.0)), 4)
        L = math.hypot(ex - sx, ey - sy)
        if L < 0.05:
            continue

        is_horiz = abs(ex - sx) >= abs(ey - sy)
        dx = (ex - sx) / L
        dy = (ey - sy) / L
        nx = -dy * hw
        ny = dx * hw

        p1 = (round(sx + nx, 4), round(sy + ny, 4))
        p2 = (round(ex + nx, 4), round(ey + ny, 4))
        p3 = (round(ex - nx, 4), round(ey - ny, 4))
        p4 = (round(sx - nx, 4), round(sy - ny, 4))
        b_poly = Polygon([p1, p2, p3, p4])
        if not b_poly.is_valid:
            b_poly = b_poly.buffer(0)

        beam_records.append({
            "id": b_id,
            "kind": b_kind,
            "is_horiz": is_horiz,
            "width_m": w,
            "depth_m": float(b.get("depth_m", 0.40)),
            "poly": b_poly,
            "sx": sx, "sy": sy, "ex": ex, "ey": ey,
            "axis_coord": sy if is_horiz else sx,
            "raw_beam": b,
        })
        beam_geoms.append(b_poly)

    beams_union = unary_union(beam_geoms) if beam_geoms else Polygon()

    warnings: List[str] = []

    # Check beam-opening overlap
    for br in beam_records:
        for op_id, _, op_p in op_polys:
            inter = br["poly"].intersection(op_p)
            if inter.area > 0.01:
                warnings.append(
                    f"Beam {br['id']} overlaps with Opening {op_id} (overlap area: {inter.area:.3f} m² > 0.01 m²)"
                )

    # Boolean subtraction
    net = roof_poly.difference(openings_union).difference(beams_union)

    raw_polys: List[Polygon] = []
    if net.geom_type == 'Polygon':
        raw_polys = [net]
    elif net.geom_type == 'MultiPolygon':
        raw_polys = list(net.geoms)
    elif net.geom_type == 'GeometryCollection':
        raw_polys = [g for g in net.geoms if isinstance(g, Polygon)]

    cleaned_polys: List[Polygon] = []
    for p in raw_polys:
        if p.area < 1e-4:
            continue
        p_clean = p.simplify(0.002, preserve_topology=True)
        if p_clean.area >= 1e-4:
            cleaned_polys.append(p_clean)

    # Sliver merging policy: merge any sliver into an adjacent slab if no beam separates them
    merged = list(cleaned_polys)
    changed = True
    while changed:
        changed = False
        for i in range(len(merged)):
            pi = merged[i]
            min_xi, min_yi, max_xi, max_yi = pi.bounds
            is_sliver_i = (pi.area < 0.30 or min(max_xi - min_xi, max_yi - min_yi) < 0.15)
            if not is_sliver_i:
                continue
            for j in range(len(merged)):
                if i == j: continue
                pj = merged[j]
                if pi.distance(pj) < 0.005:
                    u = unary_union([pi, pj])
                    if isinstance(u, Polygon) and u.is_valid:
                        if beams_union.is_empty or u.intersection(beams_union).area < 1e-4:
                            merged.pop(max(i, j))
                            merged.pop(min(i, j))
                            merged.append(u)
                            changed = True
                            break
            if changed:
                break

    components_data = []
    for p in merged:
        min_x, min_y, max_x, max_y = p.bounds
        lx = round(max_x - min_x, 4)
        ly = round(max_y - min_y, 4)
        cx = round(p.centroid.x, 4)
        cy = round(p.centroid.y, 4)
        area = round(p.area, 4)
        coords = [(round(pt[0], 4), round(pt[1], 4)) for pt in p.exterior.coords]
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]

        components_data.append({
            "polygon": coords,
            "geom": p,
            "area_m2": area,
            "cx": cx, "cy": cy,
            "min_x": round(min_x, 4), "max_x": round(max_x, 4),
            "min_y": round(min_y, 4), "max_y": round(max_y, 4),
            "lx_m": lx, "ly_m": ly,
        })

    # Sort deterministically: X then Y
    components_data.sort(key=lambda c: (round(c["cx"], 2), round(c["cy"], 2)))

    cols = [c for c in story_data.get("columns", []) if c.get("active", True)]
    def has_col_near_edge(x1: float, y1: float, x2: float, y2: float) -> bool:
        is_h = abs(x2 - x1) >= abs(y2 - y1)
        for c in cols:
            cx, cy = float(c["x"]), float(c["y"])
            if is_h and abs(cy - y1) <= 0.45 and (min(x1, x2) - 0.35) <= cx <= (max(x1, x2) + 0.35):
                return True
            if (not is_h) and abs(cx - x1) <= 0.45 and (min(y1, y2) - 0.35) <= cy <= (max(y1, y2) + 0.35):
                return True
        return False

    final_slabs = []
    cantilever_slabs = []

    for idx, c in enumerate(components_data):
        s_id = f"S{idx + 1}"
        pts = c["polygon"]
        edges = []
        sup_beams: Dict[str, Dict[str, Any]] = {}
        axis_bounds = {"min_x": c["min_x"], "max_x": c["max_x"], "min_y": c["min_y"], "max_y": c["max_y"]}

        # Check touching beams
        p_geom = c["geom"]
        for br in beam_records:
            if p_geom.distance(br["poly"]) < 0.025:
                inter = p_geom.buffer(0.02).intersection(br["poly"])
                if inter.area > 0.001 or p_geom.boundary.distance(br["poly"]) < 0.015:
                    sup_beams[br["id"]] = br
                    if br["is_horiz"]:
                        if br["sy"] >= c["cy"]:
                            side = "North"
                            axis_bounds["max_y"] = br["axis_coord"]
                        else:
                            side = "South"
                            axis_bounds["min_y"] = br["axis_coord"]
                    else:
                        if br["sx"] >= c["cx"]:
                            side = "East"
                            axis_bounds["max_x"] = br["axis_coord"]
                        else:
                            side = "West"
                            axis_bounds["min_x"] = br["axis_coord"]
                    edges.append({
                        "kind": "beam_face",
                        "beam_id": br["id"],
                        "beam_kind": br["kind"],
                        "side": side,
                    })

        # Check touching openings
        for op_id, _, op_p in op_polys:
            if p_geom.distance(op_p) < 0.025:
                inter = p_geom.buffer(0.02).intersection(op_p)
                if inter.area > 0.001 or p_geom.boundary.distance(op_p) < 0.015:
                    edges.append({
                        "kind": "opening_edge",
                        "opening_id": op_id,
                        "side": "Unknown"
                    })
                    warnings.append(f"Slab {s_id} borders Opening {op_id} without a trim beam edge")

        n_sup = len(sup_beams)
        is_sliver = (c["area_m2"] < 0.30 or min(c["lx_m"], c["ly_m"]) < 0.15)
        if is_sliver:
            warnings.append(
                f"Sliver slab at ({c['cx']:.2f}, {c['cy']:.2f}) [ID: {s_id}, Area: {c['area_m2']:.3f} m², Dim: {c['lx_m']:.2f}×{c['ly_m']:.2f} m]"
            )

        if n_sup == 0:
            warnings.append(f"Zero-support slab at ({c['cx']:.2f}, {c['cy']:.2f}) [ID: {s_id}] with 0 supporting beams")

        # Cantilever detection & rib direction
        is_cantilever = False
        cant_free_edge = None
        rib_dir = 0
        locked = False

        sup_sides = {ed["side"] for ed in edges if ed["kind"] == "beam_face"}

        # 1. Check overhanging edge beyond column line on the EXTERIOR building perimeter
        has_cant_edge = False
        if len(cols) >= 2:
            if "South" in sup_sides and c["min_y"] <= min_roof_y + 0.15 and not has_col_near_edge(c["min_x"], c["min_y"], c["max_x"], c["min_y"]):
                if "North" in sup_sides and has_col_near_edge(c["min_x"], axis_bounds["max_y"], c["max_x"], axis_bounds["max_y"]):
                    is_cantilever = True
                    cant_free_edge = "South"
                    rib_dir = 90
                    locked = True
                    has_cant_edge = True
            elif "North" in sup_sides and c["max_y"] >= max_roof_y - 0.15 and not has_col_near_edge(c["min_x"], c["max_y"], c["max_x"], c["max_y"]):
                if "South" in sup_sides and has_col_near_edge(c["min_x"], axis_bounds["min_y"], c["max_x"], axis_bounds["min_y"]):
                    is_cantilever = True
                    cant_free_edge = "North"
                    rib_dir = 90
                    locked = True
                    has_cant_edge = True
            elif "East" in sup_sides and c["max_x"] >= max_roof_x - 0.15 and not has_col_near_edge(c["max_x"], c["min_y"], c["max_x"], c["max_y"]):
                if "West" in sup_sides and has_col_near_edge(axis_bounds["min_x"], c["min_y"], axis_bounds["min_x"], c["max_y"]):
                    is_cantilever = True
                    cant_free_edge = "East"
                    rib_dir = 0
                    locked = True
                    has_cant_edge = True
            elif "West" in sup_sides and c["min_x"] <= min_roof_x + 0.15 and not has_col_near_edge(c["min_x"], c["min_y"], c["min_x"], c["max_y"]):
                if "East" in sup_sides and has_col_near_edge(axis_bounds["max_x"], c["min_y"], axis_bounds["max_x"], c["max_y"]):
                    is_cantilever = True
                    cant_free_edge = "West"
                    rib_dir = 0
                    locked = True
                    has_cant_edge = True

        if not has_cant_edge:
            if len(sup_sides) == 3:
                all_4 = {"North", "South", "East", "West"}
                missing_side = (all_4 - sup_sides).pop()
                is_cantilever = True
                cant_free_edge = missing_side
                if missing_side in ("North", "South"):
                    rib_dir = 90
                else:
                    rib_dir = 0
                locked = True
            elif len(sup_sides) == 1:
                is_cantilever = True
                carrier_beam = next(iter(sup_beams.values()))
                sup_side = next(iter(sup_sides))
                opp = {"North": "South", "South": "North", "East": "West", "West": "East"}.get(sup_side, "East")
                cant_free_edge = opp
                rib_dir = 90 if carrier_beam["is_horiz"] else 0
                locked = True
            elif len(sup_sides) == 2:
                if "North" in sup_sides and "South" in sup_sides:
                    rib_dir = 90
                    locked = True
                elif "East" in sup_sides and "West" in sup_sides:
                    rib_dir = 0
                    locked = True
                else:
                    is_cantilever = True
                    if "West" in sup_sides:
                        rib_dir = 0
                        cant_free_edge = "East"
                    elif "East" in sup_sides:
                        rib_dir = 0
                        cant_free_edge = "West"
                    else:
                        rib_dir = 90
                        cant_free_edge = "South" if "North" in sup_sides else "North"
                    locked = True
            else:
                rib_dir = 0 if c["lx_m"] <= c["ly_m"] else 90
                locked = False

        ln_m = c["lx_m"] if rib_dir == 0 else c["ly_m"]

        slab_obj = {
            "id": s_id,
            "bay_key": f"SLAB_{round(axis_bounds['min_x'],1)}_{round(axis_bounds['min_y'],1)}_{round(axis_bounds['max_x'],1)}_{round(axis_bounds['max_y'],1)}",
            "polygon": c["polygon"],
            "area_m2": c["area_m2"],
            "cx": c["cx"], "cy": c["cy"],
            "min_x": axis_bounds["min_x"], "max_x": axis_bounds["max_x"],
            "min_y": axis_bounds["min_y"], "max_y": axis_bounds["max_y"],
            "clear_min_x": c["min_x"], "clear_max_x": c["max_x"],
            "clear_min_y": c["min_y"], "clear_max_y": c["max_y"],
            "lx_m": c["lx_m"], "ly_m": c["ly_m"],
            "ln_m": ln_m,
            "rib_direction_deg": rib_dir,
            "rib_direction_label": "X-Direction (0°)" if rib_dir == 0 else "Y-Direction (90°)",
            "rib_direction_locked": locked,
            "is_cantilever": is_cantilever,
            "cantilever_free_edge": cant_free_edge,
            "is_sliver": is_sliver,
            "supporting_beams": [
                {"id": sb["id"], "kind": sb["kind"], "width_m": sb["width_m"], "depth_m": sb["depth_m"]}
                for sb in sup_beams.values()
            ],
            "supporting_beam_count": n_sup,
            "edges": edges,
            "backspan_to_cantilever_id": None,
        }

        if is_cantilever:
            cantilever_slabs.append(slab_obj)
        final_slabs.append(slab_obj)

    # Backspan continuity lock: lock adjacent slab rib direction
    for cant in cantilever_slabs:
        c_sup_beam_ids = {sb["id"] for sb in cant["supporting_beams"]}
        c_dir = cant["rib_direction_deg"]
        for slb in final_slabs:
            if slb["id"] == cant["id"] or slb["is_cantilever"]:
                continue
            s_sup_ids = {sb["id"] for sb in slb["supporting_beams"]}
            shared = c_sup_beam_ids.intersection(s_sup_ids)
            if shared:
                slb["rib_direction_deg"] = c_dir
                slb["rib_direction_label"] = "X-Direction (0°)" if c_dir == 0 else "Y-Direction (90°)"
                slb["rib_direction_locked"] = True
                slb["backspan_to_cantilever_id"] = cant["id"]
                slb["lock_reason"] = (
                    f"Cantilever Back-Span Lock: Slab {slb['id']} acts as continuity back-span for Cantilever {cant['id']}."
                )

    return final_slabs, warnings

def auto_fill_all_story_slabs(story_data: Dict[str, Any]) -> Tuple[int, str]:
    """
    1-Click Productivity Tool (v2.4.13 Face-Based Slab Inference Engine):
    Automatically populates all closed slab components using face-based geometric boolean subtraction:
    Slabs = Slab Edge (00-XD-EDGE) - Openings (00-XD-OPEN) - Beams (00-XD-BEAM)
    """
    is_valid, issues = validate_geometry_before_inference(story_data)
    if not is_valid:
        return 0, issues[0] if issues else "Draw Outer Slab Boundary and Beams first before Auto-Filling Slabs."

    slabs, warnings = infer_story_slabs_face_based(story_data)
    story_data["slab_inference_warnings"] = warnings
    if not slabs:
        return 0, warnings[0] if warnings else "No closed slab panels could be inferred."

    story_data["slabs"] = slabs
    return len(slabs), f"Auto-Generated {len(slabs)} Slab bay(s) across the story."

_COL_LOCK_MSG = "Column Lock: regular columns are edited ONLY on the Ground Floor. Upper stories inherit them (use Modify > Discontinue/Restore). Tie-Beams accept Neck Columns (NC#) only."

def _col_edit_allowed_v244(story_data: Dict[str, Any], col: Dict[str, Any]) -> bool:
    """
    Column edit permissions per story policy:
    - Ground floor (02_Ground_Floor): Master editable
    - Neck columns on TieBeams (00_TieBeams): Editable locally
    - Basement-local columns (01_Basement_Slab): Editable locally
    - Upper / inherited columns: Read-only
    """
    sid = str(story_data.get("story_id", ""))
    st = str(story_data.get("story_type", ""))
    if col.get("neck"):
        return st == "tie_beams" or sid.startswith("00_")
    if col.get("basement_local"):
        return st == "basement" or sid.startswith("01_")
    if st in ("tie_beams", "typical", "standard", "penthouse", "basement") or (sid and not sid.startswith("02_")):
        return False
    return True

def rotate_column_90_deg(story_data: Dict[str, Any], column_id: str, boundary_mode: str = "clamp", *a, **k) -> Tuple[bool, str]:
    """
    Rotates a selected column by 90 degrees (swapping b_m and h_m, e.g. 0.20x0.40 <-> 0.40x0.20),
    re-clamps it safely inside the building boundary (without ever crashing), and updates connected
    beams' support widths while keeping all beams 100% strictly orthogonal (never skewed/slanted)
    and strictly inside the slab boundary!
    """
    cols = story_data.get("columns", [])
    target = next((c for c in cols if str(c.get("id")) == str(column_id)), None)
    if not target:
        return False, f"Column {column_id} not found."
    if not _col_edit_allowed_v244(story_data, target):
        return False, _COL_LOCK_MSG
    old_b, old_h = float(target.get("b_m", 0.20)), float(target.get("h_m", 0.40))
    target["b_m"] = round(old_h, 3)
    target["h_m"] = round(old_b, 3)

    poly = story_data.get("slab_edge_polygon", [])
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(poly)
    if has_bnd:
        updated_col, updated_poly, _ = enforce_column_inside_slab_boundary(
            target, poly, mode=boundary_mode
        )
        target["x"], target["y"] = updated_col["x"], updated_col["y"]
        story_data["slab_edge_polygon"] = updated_poly
        has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(updated_poly)

    # Update support width on any beam resting on this rotated column while keeping beams strictly orthogonal!
    for bm in story_data.get("beams", []):
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        half_w = float(bm.get("width_m", 0.30)) / 2.0
        is_horiz = abs(ex - sx) >= abs(ey - sy)
        if is_horiz:
            ey = sy
            if has_bnd:
                sy = ey = round(min(max(sy, min_y + half_w), max_y - half_w), 3)
                sx = round(min(max(sx, min_x), max_x), 3)
                ex = round(min(max(ex, min_x), max_x), 3)
        else:
            ex = sx
            if has_bnd:
                sx = ex = round(min(max(sx, min_x + half_w), max_x - half_w), 3)
                sy = round(min(max(sy, min_y), max_y), 3)
                ey = round(min(max(ey, min_y), max_y), 3)
        bm["start_x"], bm["start_y"] = sx, sy
        bm["end_x"], bm["end_y"] = ex, ey

        for sup in bm.get("supports", []):
            if sup.get("kind") == "column" and sup.get("target_id") == column_id:
                sup["width_m"] = target["b_m"] if is_horiz else target["h_m"]
                sup["depth_m"] = target["h_m"] if is_horiz else target["b_m"]
                sup["coord"] = float(target["x"]) if is_horiz else float(target["y"])

    reconcile_and_split_slabs_after_beam_change(story_data)
    return True, f"Rotated Column {column_id} by 90° -> {target['b_m']:.2f} × {target['h_m']:.2f} m at ({target['x']:.2f}, {target['y']:.2f})."


def pick_area_create_or_update_slab(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    target_mode: str = "SLAB",
    requested_rib_dir_deg: Optional[int] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    v2.4.13 Face-Based Pick Area Tool:
    Infers slab panels using face-based boolean subtraction and creates/updates
    the slab panel containing the clicked point (click_x, click_y).
    """
    is_val, issues = validate_geometry_before_inference(story_data)
    if not is_val:
        return False, issues[0] if issues else "Draw Outer Slab Boundary and Beams first before using Pick Area.", None

    inferred_slabs, warns = infer_story_slabs_face_based(story_data, preserve_existing_ids=True)
    if not inferred_slabs:
        return False, "Draw Outer Slab Boundary and Beams first before using Pick Area.", None

    pt = Point(click_x, click_y)
    for op in story_data.get("openings", []):
        poly_pts = op.get("polygon", [])
        if len(poly_pts) >= 3 and Polygon(poly_pts).contains(pt):
            return False, f"Clicked point ({click_x:.2f}, {click_y:.2f}) is inside an Opening.", None

    target_slab = None
    for s in inferred_slabs:
        sp = Polygon(s["polygon"])
        if sp.contains(pt) or sp.distance(pt) < 0.001:
            target_slab = dict(s)
            break

    if target_slab is None:
        return False, f"Clicked point ({click_x:.2f}, {click_y:.2f}) is outside bounded slab bays.", None

    slabs = story_data.setdefault("slabs", [])
    openings = story_data.setdefault("openings", [])

    existing_slab = next((es for es in slabs if es.get("id") == target_slab["id"] or es.get("bay_key") == target_slab["bay_key"]), None)

    # Check active cantilevers in story_data["slabs"]
    t_sup_ids = {sb["id"] for sb in target_slab.get("supporting_beams", [])}
    controlling_cant = None
    if not target_slab.get("is_cantilever"):
        for es in slabs:
            if es.get("is_cantilever") and es is not existing_slab:
                es_sup_ids = {sb["id"] for sb in es.get("supporting_beams", [])}
                if t_sup_ids.intersection(es_sup_ids):
                    c_dir = es.get("rib_direction_deg", 90)
                    if es.get("cantilever_free_edge") in ("North", "South") and c_dir == 90:
                        controlling_cant = es
                        break
                    elif es.get("cantilever_free_edge") in ("East", "West") and c_dir == 0:
                        controlling_cant = es
                        break

    if target_mode == "TOGGLE_OPENING" or target_mode == "OPENING":
        if controlling_cant is not None:
            return False, f"Cannot convert to Opening: Cantilever Slab {controlling_cant['id']} depends on this bay for back-span continuity!", None
        if existing_slab:
            slabs.remove(existing_slab)
        new_op = {
            "id": f"OP{len(openings) + 1}",
            "bay_key": target_slab["bay_key"],
            "polygon": target_slab["polygon"],
            "min_x": target_slab["min_x"], "max_x": target_slab["max_x"],
            "min_y": target_slab["min_y"], "max_y": target_slab["max_y"],
        }
        openings.append(new_op)
        return True, f"Bay set as Void Opening ({new_op['id']}).", new_op

    if target_slab.get("is_cantilever"):
        chosen_dir = target_slab["rib_direction_deg"]
    elif controlling_cant is not None:
        chosen_dir = controlling_cant["rib_direction_deg"]
        target_slab["rib_direction_locked"] = True
    else:
        chosen_dir = 0 if target_slab["lx_m"] <= target_slab["ly_m"] else 90
        target_slab["rib_direction_locked"] = False

    if target_mode == "FLIP_RIB":
        if controlling_cant is not None:
            return False, f"Cantilever Back-Span Lock: Slab {target_slab['id']} is the back-span extension for Cantilever Slab {controlling_cant['id']}.", existing_slab or target_slab
        cur_dir = (existing_slab or target_slab).get("rib_direction_deg", chosen_dir)
        chosen_dir = 90 if cur_dir == 0 else 0
    elif requested_rib_dir_deg is not None:
        chosen_dir = requested_rib_dir_deg

    target_slab["rib_direction_deg"] = chosen_dir
    target_slab["rib_direction_label"] = "X-Direction (0°)" if chosen_dir == 0 else "Y-Direction (90°)"

    if existing_slab is not None:
        existing_slab.update(target_slab)
        chosen_slab = existing_slab
    else:
        slabs.append(target_slab)
        chosen_slab = target_slab

    if chosen_slab.get("is_cantilever"):
        c_sup_beam_ids = {sb["id"] for sb in chosen_slab.get("supporting_beams", [])}
        c_dir = chosen_slab["rib_direction_deg"]
        for s in slabs:
            if s.get("id") == chosen_slab.get("id") or s.get("is_cantilever"):
                continue
            s_sup_ids = {sb["id"] for sb in s.get("supporting_beams", [])}
            if c_sup_beam_ids.intersection(s_sup_ids):
                if chosen_slab["rib_direction_deg"] == 90:
                    s["rib_direction_deg"] = c_dir
                    s["rib_direction_label"] = "X-Direction (0°)" if c_dir == 0 else "Y-Direction (90°)"
                    s["rib_direction_locked"] = True
                    s["backspan_to_cantilever_id"] = chosen_slab.get("id")
                else:
                    s["rib_direction_locked"] = False
                    s["backspan_to_cantilever_id"] = None

    return True, f"Slab {chosen_slab['id']} set with Rib Direction = {chosen_slab['rib_direction_deg']}.", chosen_slab

def flip_slab_rib_by_id(
    story_data: Dict[str, Any],
    slab_id: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Directly flips the rib direction (0° <-> 90°) of a specific selected Slab by its exact ID (`slab_id`),
    never accidentally targeting a neighboring or larger overlapping slab!
    """
    slabs = story_data.get("slabs", [])
    target_slb = next((s for s in slabs if str(s.get("id")) == str(slab_id)), None)
    if target_slb is None:
        return False, f"Slab '{slab_id}' not found.", None

    smin_x = float(target_slb.get("min_x", target_slb.get("x_min", 0.0)))
    smax_x = float(target_slb.get("max_x", target_slb.get("x_max", 4.0)))
    smin_y = float(target_slb.get("min_y", target_slb.get("y_min", 0.0)))
    smax_y = float(target_slb.get("max_y", target_slb.get("y_max", 4.0)))
    cx = (smin_x + smax_x) / 2.0
    cy = (smin_y + smax_y) / 2.0

    bays = detect_story_grid_bays(story_data)
    if bays:
        slb_lx = float(target_slb.get("lx_m", smax_x - smin_x))
        slb_ly = float(target_slb.get("ly_m", smax_y - smin_y))
        matching_bay = next(
            (
                b for b in bays
                if (
                    b.get("bay_key") == target_slb.get("bay_key")
                    or (
                        abs(float(b["min_x"]) - smin_x) <= 0.35
                        and abs(float(b["max_x"]) - smax_x) <= 0.35
                        and abs(float(b["min_y"]) - smin_y) <= 0.35
                        and abs(float(b["max_y"]) - smax_y) <= 0.35
                    )
                )
                and abs(float(b["lx_m"]) - slb_lx) <= 0.50
                and abs(float(b["ly_m"]) - slb_ly) <= 0.50
            ),
            None,
        )
        if matching_bay is not None:
            ok, msg, updated = pick_area_create_or_update_slab(story_data, cx, cy, target_mode="FLIP_RIB")
            if ok and updated is not None and str(updated.get("id")) == str(slab_id):
                updated["rib_angle_deg"] = int(updated.get("rib_direction_deg", 0))
                return ok, msg, updated
            if not ok and ("Cantilever" in msg):
                return ok, msg, updated

    cur_dir = int(target_slb.get("rib_direction_deg", target_slb.get("rib_angle_deg", 0)))
    new_dir = 90 if cur_dir == 0 else 0
    target_slb["rib_direction_deg"] = new_dir
    target_slb["rib_angle_deg"] = new_dir
    lx = float(target_slb.get("lx_m", smax_x - smin_x))
    ly = float(target_slb.get("ly_m", smax_y - smin_y))
    target_slb["axis_span_m"] = lx if new_dir == 0 else ly
    return True, f"Slab {slab_id} ({lx:.2f}×{ly:.2f} m) flipped to Rib Direction = {new_dir}°.", target_slb


def toggle_slab_rib_by_label_click(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    hit_radius_m: float = 0.75,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Checks if the user clicked near any Slab's center rib label/arrow on the canvas (or inside the slab).
    Prioritizes:
      1) Slabs whose clear interior bounds contain `(click_x, click_y)`,
      2) Smallest slab area (`lx * ly`),
      3) Closest distance from `(click_x, click_y)` to the slab's center `(cx, cy)`.
    This guarantees clicking inside or on a small sub-slab (like S5 next to a stair) NEVER flips S3 or S2!
    """
    candidates: List[Tuple[int, float, float, Dict[str, Any]]] = []
    for slb in story_data.get("slabs", []):
        if "min_x" not in slb and "x_min" not in slb:
            continue
        smin_x = float(slb.get("min_x", slb.get("x_min", 0.0)))
        smax_x = float(slb.get("max_x", slb.get("x_max", 0.0)))
        smin_y = float(slb.get("min_y", slb.get("y_min", 0.0)))
        smax_y = float(slb.get("max_y", slb.get("y_max", 0.0)))
        cmin_x = float(slb.get("clear_min_x", smin_x))
        cmax_x = float(slb.get("clear_max_x", smax_x))
        cmin_y = float(slb.get("clear_min_y", smin_y))
        cmax_y = float(slb.get("clear_max_y", smax_y))
        cx = (smin_x + smax_x) / 2.0
        cy = (smin_y + smax_y) / 2.0
        dist = math.hypot(click_x - cx, click_y - cy)
        in_clear = cmin_x <= click_x <= cmax_x and cmin_y <= click_y <= cmax_y
        in_bounds = smin_x <= click_x <= smax_x and smin_y <= click_y <= smax_y
        if in_clear or in_bounds or dist <= hit_radius_m:
            area = max(0.1, (smax_x - smin_x) * (smax_y - smin_y))
            rank = 0 if in_clear else (1 if in_bounds else 2)
            candidates.append((rank, area, dist, slb))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        best_slb = candidates[0][3]
        return flip_slab_rib_by_id(story_data, str(best_slb.get("id")))

    return pick_area_create_or_update_slab(story_data, click_x, click_y, target_mode="FLIP_RIB")


def delete_selected_element_from_story(
    story_data: Dict[str, Any],
    kind: str,
    element_id: str,
    *a, **k,
) -> Tuple[bool, str]:
    """
    Crash-proof universal deletion algorithm for any selected object (`column`, `beam`, `slab`, `opening`,
    `dimension`, or `slab_edge`) from `story_data`:
    - When deleting a Column `C_del`:
      1. Removes `C_del` from `story_data['columns']`.
      2. Renumbers remaining active columns sequentially `C1, C2, ..., Cn` with zero gaps.
      3. Reconciles all beams' supports & spans (`reconcile_all_story_beams_supports_and_spans`) so multi-span
         beams (like B6) merge spans into a single span (`9.30m`) and intersecting beams (like B5) switch their
         support to the perpendicular carrier beam (`B6`).
    - When deleting a Beam `B_del` that has secondary beams resting on it:
      automatically cleans up support references & transferred point loads in those secondary beams
      and recalculates their spans safely so the app NEVER crashes!
    """
    try:
        eid = str(element_id)
        if kind == "column":
            cols = story_data.get("columns", [])
            target_col = next((c for c in cols if str(c.get("id")) == eid), None)
            if target_col is not None and not _col_edit_allowed_v244(story_data, target_col):
                return False, _COL_LOCK_MSG
            before = len(cols)
            story_data["columns"] = [c for c in cols if str(c.get("id")) != eid]
            if len(story_data["columns"]) < before:
                for bm in story_data.get("beams", []):
                    sups = [s for s in bm.get("supports", []) if not (s.get("kind") == "column" and str(s.get("target_id")) == eid)]
                    for idx_s, s_obj in enumerate(sups):
                        s_obj["support_index"] = idx_s + 1
                    bm["supports"] = sups
                renumber_story_columns_sequentially(story_data)
                reconcile_all_story_beams_supports_and_spans(story_data)
                return True, f"Deleted Column {eid} (Renumbered remaining columns C1..C{len(story_data['columns'])} & updated connected beam spans)."

        elif kind == "beam":
            beams = story_data.get("beams", [])
            before = len(beams)
            story_data["beams"] = [b for b in beams if str(b.get("id")) != eid]
            if len(story_data["beams"]) < before:
                detached_beams: List[str] = []
                for ob in story_data["beams"]:
                    old_sups = ob.get("supports", [])
                    new_sups = [
                        s for s in old_sups
                        if not (s.get("kind") == "beam" and str(s.get("target_id")) == eid)
                    ]
                    if len(new_sups) < len(old_sups):
                        detached_beams.append(str(ob.get("id")))
                        for idx_s, s_obj in enumerate(new_sups):
                            s_obj["support_index"] = idx_s + 1
                        ob["supports"] = new_sups
                        coords = sorted(float(s.get("coord", s.get("center_coord_m", 0.0))) for s in new_sups)
                        valid_spans = [
                            round(coords[k + 1] - coords[k], 3)
                            for k in range(len(coords) - 1)
                            if (coords[k + 1] - coords[k]) >= 0.35
                        ]
                        if valid_spans:
                            ob["spans"] = valid_spans
                        else:
                            bsx, bsy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
                            bex, bey = float(ob.get("end_x", 4.0)), float(ob.get("end_y", 0.0))
                            ob["spans"] = [round(max(0.50, math.hypot(bex - bsx, bey - bsy)), 3)]
                    if "loads" in ob and isinstance(ob["loads"], list):
                        ob["loads"] = [
                            ld for ld in ob["loads"]
                            if str(ld.get("source_beam", ld.get("source_beam_id", ""))) != eid
                        ]

                reconcile_all_story_beams_supports_and_spans(story_data)
                reconcile_and_split_slabs_after_beam_change(story_data)
                note = f" (Updated supported beam(s): {', '.join(detached_beams)})" if detached_beams else ""
                return True, f"Deleted Beam {eid}{note}."

        elif kind == "slab":
            slabs = story_data.get("slabs", [])
            before = len(slabs)
            story_data["slabs"] = [s for s in slabs if str(s.get("id")) != eid]
            if len(story_data["slabs"]) < before:
                bays = detect_story_grid_bays(story_data)
                bay_by_key = {b["bay_key"]: b for b in bays}
                for s_rem in story_data["slabs"]:
                    mb = bay_by_key.get(s_rem.get("bay_key"))
                    if mb:
                        ctrls = _find_controlling_cantilever_slabs_for_bay(story_data, mb, bays)
                        s_rem["connected_to_cantilever"] = bool(ctrls)
                return True, f"Deleted Slab {eid}."

        elif kind == "opening":
            opens = story_data.get("openings", [])
            before = len(opens)
            story_data["openings"] = [o for o in opens if str(o.get("id")) != eid]
            if len(story_data["openings"]) < before:
                return True, f"Deleted Opening {eid}."

        elif kind == "dimension":
            dims = story_data.get("dimensions", [])
            before = len(dims)
            story_data["dimensions"] = [d for d in dims if str(d.get("id")) != eid]
            if len(story_data["dimensions"]) < before:
                return True, f"Deleted Dimension {eid}."

        elif kind == "slab_edge":
            story_data["slab_edge_polygon"] = []
            return True, "Deleted Outer Building Boundary Polyline."

        return False, f"Element {kind} '{eid}' not found."
    except Exception as exc:
        return False, f"Safe delete error handler: {exc}"


def move_column_and_sync_connected_beams(
    story_data: Dict[str, Any],
    column_id: str,
    new_x: float,
    new_y: float,
    boundary_mode: str = "clamp",
    *a, **k,
) -> Tuple[bool, str]:
    """
    Moves a column to (new_x, new_y), enforces the Outer Slab Boundary rule ('clamp' or 'expand'),
    and updates all beams supported by this column while keeping beams strictly orthogonal.
    """
    columns = story_data.get("columns", [])
    target_col = next((c for c in columns if str(c.get("id")) == str(column_id)), None)
    if not target_col:
        return False, f"Column {column_id} not found."
    if not _col_edit_allowed_v244(story_data, target_col):
        return False, _COL_LOCK_MSG

    old_x, old_y = float(target_col["x"]), float(target_col["y"])
    candidate = dict(target_col)
    candidate["x"] = round(float(new_x), 3)
    candidate["y"] = round(float(new_y), 3)

    slab_poly = story_data.get("slab_edge_polygon", [])
    updated_col, updated_poly, msg = enforce_column_inside_slab_boundary(candidate, slab_poly, mode=boundary_mode)
    story_data["slab_edge_polygon"] = updated_poly
    target_col["x"] = updated_col["x"]
    target_col["y"] = updated_col["y"]

    dx = round(target_col["x"] - old_x, 3)
    dy = round(target_col["y"] - old_y, 3)

    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(updated_poly)

    for bm in story_data.get("beams", []):
        sup_ids = [s.get("target_id") for s in bm.get("supports", []) if s.get("kind") == "column"]
        if column_id not in sup_ids:
            continue
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        half_w = float(bm.get("width_m", 0.30)) / 2.0
        is_horiz = abs(ex - sx) >= abs(ey - sy)
        if is_horiz:
            new_sy = round(sy + dy, 3)
            if has_bnd:
                new_sy = round(min(max(new_sy, min_y + half_w), max_y - half_w), 3)
            bm["start_y"] = bm["end_y"] = new_sy
            if abs(sx - old_x) < 0.35:
                bm["start_x"] = round(target_col["x"] - float(target_col.get("b_m", 0.20)) / 2.0, 3)
            if abs(ex - old_x) < 0.35:
                bm["end_x"] = round(target_col["x"] + float(target_col.get("b_m", 0.20)) / 2.0, 3)
            if has_bnd:
                bm["start_x"] = round(min(max(float(bm["start_x"]), min_x), max_x), 3)
                bm["end_x"] = round(min(max(float(bm["end_x"]), min_x), max_x), 3)
        else:
            new_sx = round(sx + dx, 3)
            if has_bnd:
                new_sx = round(min(max(new_sx, min_x + half_w), max_x - half_w), 3)
            bm["start_x"] = bm["end_x"] = new_sx
            if abs(sy - old_y) < 0.35:
                bm["start_y"] = round(target_col["y"] - float(target_col.get("h_m", 0.40)) / 2.0, 3)
            if abs(ey - old_y) < 0.35:
                bm["end_y"] = round(target_col["y"] + float(target_col.get("h_m", 0.40)) / 2.0, 3)
            if has_bnd:
                bm["start_y"] = round(min(max(float(bm["start_y"]), min_y), max_y), 3)
                bm["end_y"] = round(min(max(float(bm["end_y"]), min_y), max_y), 3)

    reconcile_all_story_beams_supports_and_spans(story_data)
    return True, msg


def move_beam_within_slab_boundary(
    story_data: Dict[str, Any],
    beam_id: str,
    dx: float,
    dy: float,
) -> Tuple[bool, str]:
    """
    Moves a beam by (dx, dy) while clamping its full width (width_m) strictly inside the Outer Slab Boundary
    (when a boundary exists; on Tie-Beams story without a boundary, moves freely).
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))

    beams = story_data.get("beams", [])
    bm = next((b for b in beams if b.get("id") == beam_id), None)
    if not bm:
        return False, f"Beam {beam_id} not found."

    half_w = float(bm.get("width_m", 0.30)) / 2.0
    sx, sy = float(bm.get("start_x", 0.0)) + dx, float(bm.get("start_y", 0.0)) + dy
    ex, ey = float(bm.get("end_x", 0.0)) + dx, float(bm.get("end_y", 0.0)) + dy
    is_horiz = abs(ex - sx) >= abs(ey - sy)

    if is_horiz:
        if has_bnd:
            sx = min(max(sx, min_x), max_x)
            ex = min(max(ex, min_x), max_x)
            sy = ey = min(max(sy, min_y + half_w), max_y - half_w)
        else:
            ey = sy
    else:
        if has_bnd:
            sy = min(max(sy, min_y), max_y)
            ey = min(max(ey, min_y), max_y)
            sx = ex = min(max(sx, min_x + half_w), max_x - half_w)
        else:
            ex = sx

    bm["start_x"] = round(sx, 3)
    bm["start_y"] = round(sy, 3)
    bm["end_x"] = round(ex, 3)
    bm["end_y"] = round(ey, 3)
    reconcile_all_story_beams_supports_and_spans(story_data)
    return True, f"Beam {beam_id} moved to ({bm['start_x']:.2f}, {bm['start_y']:.2f}) -> ({bm['end_x']:.2f}, {bm['end_y']:.2f})."


def compute_dimension_geometry(dim: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes exact world coordinates (`dx1, dy1, dx2, dy2, mx, my, length, kind`) of a Dimension's offset line:
    - 'horizontal': offset_m > 0 is UP (+Y, North); offset_m < 0 is DOWN (-Y, South).
    - 'vertical': offset_m < 0 is LEFT (-X, West); offset_m > 0 is RIGHT (+X, East).
    - 'aligned': perpendicular normal (-dy/L, dx/L) * offset_m.
    """
    x1, y1 = float(dim.get("x1", 0.0)), float(dim.get("y1", 0.0))
    x2, y2 = float(dim.get("x2", 0.0)), float(dim.get("y2", 0.0))
    off = float(dim.get("offset_m", 0.65))
    dk = str(dim.get("kind", "aligned")).lower()
    dx, dy = x2 - x1, y2 - y1
    length = max(0.01, math.hypot(dx, dy))

    if dk == "horizontal":
        dx1, dy1 = x1, y1 + off
        dx2, dy2 = x2, y2 + off
    elif dk == "vertical":
        dx1, dy1 = x1 + off, y1
        dx2, dy2 = x2 + off, y2
    else:
        nx, ny = -dy / length, dx / length
        dx1, dy1 = x1 + nx * off, y1 + ny * off
        dx2, dy2 = x2 + nx * off, y2 + ny * off

    mx, my = (dx1 + dx2) / 2.0, (dy1 + dy2) / 2.0
    return {
        "x1": round(x1, 3),
        "y1": round(y1, 3),
        "x2": round(x2, 3),
        "y2": round(y2, 3),
        "dx1": round(dx1, 3),
        "dy1": round(dy1, 3),
        "dx2": round(dx2, 3),
        "dy2": round(dy2, 3),
        "mx": round(mx, 3),
        "my": round(my, 3),
        "length": round(length, 3),
        "kind": dk,
    }


def select_elements_by_box(
    story_data: Dict[str, Any],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    crossing: Optional[bool] = None,
) -> List[Tuple[str, str]]:
    """
    AutoCAD / Revit Window & Crossing Selection across ALL element types (`column`, `beam`, `slab`, `opening`, `dimension`):
    - Drag Left-to-Right (`x2 >= x1`) -> `crossing = False` (Window Selection: 100% enclosed).
    - Drag Right-to-Left (`x2 < x1`) -> `crossing = True` (Crossing Selection: enclosed OR touching/intersecting).
    """
    is_crossing = (x2 < x1) if crossing is None else bool(crossing)
    bmin_x, bmax_x = min(float(x1), float(x2)), max(float(x1), float(x2))
    bmin_y, bmax_y = min(float(y1), float(y2)), max(float(y1), float(y2))

    def box_match(emin_x: float, emin_y: float, emax_x: float, emax_y: float) -> bool:
        if not is_crossing:
            return emin_x >= bmin_x - 1e-6 and emax_x <= bmax_x + 1e-6 and emin_y >= bmin_y - 1e-6 and emax_y <= bmax_y + 1e-6
        return not (emax_x < bmin_x - 1e-6 or emin_x > bmax_x + 1e-6 or emax_y < bmin_y - 1e-6 or emin_y > bmax_y + 1e-6)

    selected: List[Tuple[str, str]] = []
    for col in story_data.get("columns", []):
        if not col.get("active", True):
            continue
        cx, cy = float(col["x"]), float(col["y"])
        hb = float(col.get("b_m", 0.20)) / 2.0
        hh = float(col.get("h_m", 0.40)) / 2.0
        if box_match(cx - hb, cy - hh, cx + hb, cy + hh):
            selected.append(("column", str(col["id"])))

    for bm in story_data.get("beams", []):
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        hw = float(bm.get("width_m", 0.30)) / 2.0
        if abs(ex - sx) >= abs(ey - sy):
            emin_x, emax_x = min(sx, ex), max(sx, ex)
            emin_y, emax_y = sy - hw, sy + hw
        else:
            emin_x, emax_x = sx - hw, sx + hw
            emin_y, emax_y = min(sy, ey), max(sy, ey)
        if box_match(emin_x, emin_y, emax_x, emax_y):
            selected.append(("beam", str(bm["id"])))

    for slb in story_data.get("slabs", []):
        if "min_x" in slb:
            if box_match(float(slb["min_x"]), float(slb["min_y"]), float(slb["max_x"]), float(slb["max_y"])):
                selected.append(("slab", str(slb["id"])))

    for op in story_data.get("openings", []):
        if "min_x" in op:
            if box_match(float(op["min_x"]), float(op["min_y"]), float(op["max_x"]), float(op["max_y"])):
                selected.append(("opening", str(op["id"])))

    for dim in story_data.get("dimensions", []):
        g = compute_dimension_geometry(dim)
        dmin_x, dmax_x = min(g["dx1"], g["dx2"]), max(g["dx1"], g["dx2"])
        dmin_y, dmax_y = min(g["dy1"], g["dy2"]), max(g["dy1"], g["dy2"])
        if box_match(dmin_x, dmin_y, dmax_x, dmax_y):
            selected.append(("dimension", str(dim["id"])))

    return selected


def align_element_face_to_reference(
    story_data: Dict[str, Any],
    target_kind: str,
    target_id: str,
    target_face: str,
    ref_axis: str,
    ref_coord: float,
    lock_constraint: bool = False,
    boundary_mode: str = "clamp",
    *a, **k,
) -> Tuple[bool, str]:
    """
    Revit-Style Align Tool (`Modify -> Align [AL]`):
    Moves the target Column or Beam so its chosen face sits 100% flush with `ref_coord`
    and synchronizes connected beams/slabs cleanly (no padlock clutter).
    """
    axis = ref_axis.lower().strip()
    face = target_face.lower().strip()
    rc = round(float(ref_coord), 3)

    if target_kind == "column":
        cols = story_data.get("columns", [])
        col = next((c for c in cols if c.get("id") == target_id), None)
        if not col:
            return False, f"Column {target_id} not found."
        if not _col_edit_allowed_v244(story_data, col):
            return False, _COL_LOCK_MSG
        half_b = float(col.get("b_m", 0.20)) / 2.0
        half_h = float(col.get("h_m", 0.40)) / 2.0
        new_x, new_y = float(col["x"]), float(col["y"])

        if axis == "x":
            if face == "left":
                new_x = rc + half_b
            elif face == "right":
                new_x = rc - half_b
            else:
                new_x = rc
        elif axis == "y":
            if face == "bottom":
                new_y = rc + half_h
            elif face == "top":
                new_y = rc - half_h
            else:
                new_y = rc
        else:
            return False, f"Invalid reference axis '{ref_axis}'."

        ok, msg = move_column_and_sync_connected_beams(story_data, target_id, new_x, new_y, boundary_mode=boundary_mode)
        col["moves_with_grids"] = True
        col["room_bounding"] = True
        locks = col.setdefault("locked_alignments", {})
        locks[axis] = {"face": face, "ref_coord": rc, "locked": bool(lock_constraint)}
        reconcile_and_split_slabs_after_beam_change(story_data)
        return ok, f"Aligned Column {target_id} ({face} face) to {axis.upper()} = {rc:.2f} m. {msg}"

    elif target_kind == "beam":
        beams = story_data.get("beams", [])
        bm = next((b for b in beams if b.get("id") == target_id), None)
        if not bm:
            return False, f"Beam {target_id} not found."
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        half_w = float(bm.get("width_m", 0.30)) / 2.0
        is_horiz = abs(ex - sx) >= abs(ey - sy)
        dx, dy = 0.0, 0.0

        if is_horiz and axis == "y":
            if face == "bottom":
                target_y = rc + half_w
            elif face == "top":
                target_y = rc - half_w
            else:
                target_y = rc
            dy = round(target_y - sy, 3)
        elif (not is_horiz) and axis == "x":
            if face == "left":
                target_x = rc + half_w
            elif face == "right":
                target_x = rc - half_w
            else:
                target_x = rc
            dx = round(target_x - sx, 3)
        else:
            return False, f"Beam {target_id} orientation does not match reference axis {axis.upper()}."

        ok, msg = move_beam_within_slab_boundary(story_data, target_id, dx, dy)
        bm["room_bounding"] = True
        locks = bm.setdefault("locked_alignments", {})
        locks[axis] = {"face": face, "ref_coord": rc, "locked": bool(lock_constraint)}
        reconcile_and_split_slabs_after_beam_change(story_data)
        return ok, f"Aligned Beam {target_id} ({face} face) to {axis.upper()} = {rc:.2f} m. {msg}"

    return False, f"Unsupported element kind '{target_kind}' for Align."


def move_selected_elements_by_delta(
    story_data: Dict[str, Any],
    selected_items: List[Tuple[str, str]],
    dx: float,
    dy: float,
    boundary_mode: str = "clamp",
) -> Tuple[int, str]:
    """
    Moves one or more selected Columns, Beams, or Dimensions by `(dx, dy)` and reconciles slabs.
    """
    if not selected_items:
        return 0, "No elements selected to move."

    moved_count = 0
    moved_col_ids = {eid for kind, eid in selected_items if kind == "column"}
    moved_struct = False

    for kind, eid in selected_items:
        if kind == "column":
            col = next((c for c in story_data.get("columns", []) if c.get("id") == eid), None)
            if col:
                ok, _ = move_column_and_sync_connected_beams(
                    story_data, eid, float(col["x"]) + dx, float(col["y"]) + dy, boundary_mode=boundary_mode
                )
                if ok:
                    moved_count += 1
                    moved_struct = True
        elif kind == "beam":
            bm = next((b for b in story_data.get("beams", []) if b.get("id") == eid), None)
            if bm:
                sup_cols = {s.get("target_id") for s in bm.get("supports", []) if s.get("kind") == "column"}
                if not (sup_cols & moved_col_ids):
                    ok, _ = move_beam_within_slab_boundary(story_data, eid, dx, dy)
                    if ok:
                        moved_count += 1
                        moved_struct = True
        elif kind == "dimension":
            dim = next((d for d in story_data.get("dimensions", []) if str(d.get("id")) == str(eid)), None)
            if dim:
                dk = str(dim.get("kind", "aligned")).lower()
                if dk == "horizontal":
                    dim["offset_m"] = round(float(dim.get("offset_m", 0.65)) + dy, 3)
                elif dk == "vertical":
                    dim["offset_m"] = round(float(dim.get("offset_m", -0.65)) + dx, 3)
                else:
                    dim["x1"] = round(float(dim.get("x1", 0.0)) + dx, 3)
                    dim["y1"] = round(float(dim.get("y1", 0.0)) + dy, 3)
                    dim["x2"] = round(float(dim.get("x2", 0.0)) + dx, 3)
                    dim["y2"] = round(float(dim.get("y2", 0.0)) + dy, 3)
                g = compute_dimension_geometry(dim)
                dim.update({
                    "dx1": g["dx1"], "dy1": g["dy1"],
                    "dx2": g["dx2"], "dy2": g["dy2"],
                    "mx": g["mx"], "my": g["my"],
                })
                moved_count += 1

    if moved_struct:
        reconcile_and_split_slabs_after_beam_change(story_data)
    return moved_count, f"Moved {moved_count} selected element(s) by ΔX = {dx:+.2f} m, ΔY = {dy:+.2f} m."


def measure_distance_2d(p1: Tuple[float, float], p2: Tuple[float, float]) -> Dict[str, float]:
    """
    Computes exact 2D distance L, ΔX, ΔY, and angle (deg) between two points for the Measure Tool (DI).
    """
    dx = round(float(p2[0]) - float(p1[0]), 3)
    dy = round(float(p2[1]) - float(p1[1]), 3)
    dist = round(math.hypot(dx, dy), 3)
    ang = round(math.degrees(math.atan2(dy, dx)), 1)
    return {
        "distance_m": dist,
        "dx_m": dx,
        "dy_m": dy,
        "angle_deg": ang,
    }


def create_linear_dimension(
    story_data: Dict[str, Any],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    offset_m: float = 0.65,
    dim_kind: str = "aligned",
    offset_click_pt: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """
    Creates a persistent CAD Dimension annotation (`story_data['dimensions']`) between `p1` and `p2`,
    storing exact offset line coordinates (`dx1, dy1, dx2, dy2`) so rendering and selection are 100% consistent.
    If `offset_click_pt` is provided (from a 3-click AutoCAD dimension placement), computes `offset_m` from it.
    """
    dims = story_data.setdefault("dimensions", [])
    x1, y1 = round(float(p1[0]), 3), round(float(p1[1]), 3)
    x2, y2 = round(float(p2[0]), 3), round(float(p2[1]), 3)
    if dim_kind == "linear":
        dim_kind = "horizontal" if abs(x2 - x1) >= abs(y2 - y1) else "vertical"
    if dim_kind == "horizontal":
        y2 = y1
    elif dim_kind == "vertical":
        x2 = x1
    length_m = round(math.hypot(x2 - x1, y2 - y1), 3)

    computed_off = float(offset_m)
    if offset_click_pt is not None:
        ox, oy = float(offset_click_pt[0]), float(offset_click_pt[1])
        if dim_kind == "horizontal":
            computed_off = oy - y1
        elif dim_kind == "vertical":
            computed_off = ox - x1
        else:
            dx, dy = x2 - x1, y2 - y1
            L = max(0.01, math.hypot(dx, dy))
            nx, ny = -dy / L, dx / L
            computed_off = (ox - x1) * nx + (oy - y1) * ny
        if abs(computed_off) < 0.25:
            computed_off = 0.65 if computed_off >= 0 else -0.65

    dim_obj: Dict[str, Any] = {
        "id": f"D{len(dims) + 1}",
        "kind": dim_kind,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "offset_m": round(computed_off, 3),
        "length_m": length_m,
        "value_m": length_m,
        "text": f"{length_m:.2f} m",
    }
    g = compute_dimension_geometry(dim_obj)
    dim_obj.update({
        "dx1": g["dx1"], "dy1": g["dy1"],
        "dx2": g["dx2"], "dy2": g["dy2"],
        "mx": g["mx"], "my": g["my"],
    })
    dims.append(dim_obj)
    return dim_obj


def auto_generate_exterior_dimensions(story_data: Dict[str, Any]) -> Tuple[int, str]:
    """
    1-Click Dimension Tool: Automatically generates clean exterior building boundary dimensions
    and column grid span dimensions strictly OUTSIDE the perimeter of the story:
    - Top Horizontal Dimensions: placed above `max_y` (`offset_m = +0.65` for grid spans, `+1.25` for overall width).
    - Left Vertical Dimensions: placed to the left of `min_x` (`offset_m = -0.65` for grid spans, `-1.25` for overall height).
    """
    poly = story_data.get("slab_edge_polygon", [])
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(poly)
    if not has_bnd:
        return 0, "Draw Building Boundary Polyline first before generating dimensions."

    dims = story_data.setdefault("dimensions", [])
    dims.clear()

    # 1. Overall Top (+Y outside) & Left (-X outside) Exterior Dimensions
    create_linear_dimension(story_data, (min_x, max_y), (max_x, max_y), offset_m=1.25, dim_kind="horizontal")
    create_linear_dimension(story_data, (min_x, min_y), (min_x, max_y), offset_m=-1.25, dim_kind="vertical")

    # 2. Intermediate Column Grid X & Y Span Dimensions (strictly outside perimeter)
    cols = [c for c in story_data.get("columns", []) if c.get("active", True)]
    col_xs = sorted({round(float(c["x"]), 2) for c in cols})
    col_ys = sorted({round(float(c["y"]), 2) for c in cols})

    grid_x: List[float] = []
    for x in col_xs:
        if not grid_x or abs(x - grid_x[-1]) >= 0.45:
            grid_x.append(x)
    grid_y: List[float] = []
    for y in col_ys:
        if not grid_y or abs(y - grid_y[-1]) >= 0.45:
            grid_y.append(y)

    for i in range(len(grid_x) - 1):
        create_linear_dimension(story_data, (grid_x[i], max_y), (grid_x[i + 1], max_y), offset_m=0.65, dim_kind="horizontal")
    for j in range(len(grid_y) - 1):
        create_linear_dimension(story_data, (min_x, grid_y[j]), (min_x, grid_y[j + 1]), offset_m=-0.65, dim_kind="vertical")

    return len(dims), f"Generated {len(dims)} Exterior & Column-Grid Dimensions strictly outside the building boundary."


def _raycast_point_in_poly(px: float, py: float, poly: List[List[float]]) -> bool:
    n = len(poly)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = float(poly[i][0]), float(poly[i][1])
        xj, yj = float(poly[j][0]), float(poly[j][1])
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _min_dist_to_poly_edges(px: float, py: float, poly: List[List[float]]) -> float:
    n = len(poly)
    if n < 2:
        return 1e9
    best = 1e9
    for idx in range(n):
        x1, y1 = float(poly[idx][0]), float(poly[idx][1])
        x2, y2 = float(poly[(idx + 1) % n][0]), float(poly[(idx + 1) % n][1])
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-9:
            d = math.hypot(px - x1, py - y1)
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg2))
            d = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
        if d < best:
            best = d
    return best


def normalize_opening_dict(op: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures every opening dict has valid `polygon` (closed vertex loop), bounding box
    `min_x, max_x, min_y, max_y`, and `sub_rects`.
    """
    poly = op.get("polygon")
    if isinstance(poly, list) and len(poly) >= 3:
        clean_poly = [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in poly]
        xs = [p[0] for p in clean_poly]
        ys = [p[1] for p in clean_poly]
        min_x, max_x = round(min(xs), 3), round(max(xs), 3)
        min_y, max_y = round(min(ys), 3), round(max(ys), 3)
        op["polygon"] = clean_poly
        op["min_x"], op["max_x"], op["min_y"], op["max_y"] = min_x, max_x, min_y, max_y
    else:
        min_x = round(float(op.get("min_x", op.get("x_min", 0.0))), 3)
        max_x = round(float(op.get("max_x", op.get("x_max", 0.0))), 3)
        min_y = round(float(op.get("min_y", op.get("y_min", 0.0))), 3)
        max_y = round(float(op.get("max_y", op.get("y_max", 0.0))), 3)
        if min_x > max_x:
            min_x, max_x = max_x, min_x
        if min_y > max_y:
            min_y, max_y = max_y, min_y
        op["min_x"], op["max_x"], op["min_y"], op["max_y"] = min_x, max_x, min_y, max_y
        op["polygon"] = [
            [min_x, min_y],
            [max_x, min_y],
            [max_x, max_y],
            [min_x, max_y],
        ]
    if not op.get("sub_rects"):
        if len(op["polygon"]) == 4:
            op["sub_rects"] = [[op["min_x"], op["min_y"], op["max_x"], op["max_y"]]]
    return op


def is_point_in_opening(
    px: float,
    py: float,
    op: Dict[str, Any],
    include_edge: bool = False,
    tol: float = 0.08,
) -> bool:
    """
    Accurate geometric test for whether `(px, py)` lies inside an opening (supports
    rectangular, merged multi-wing orthogonal, and general polygonal openings).
    - `include_edge=False`: strictly interior (`dist_to_edge >= tol`).
    - `include_edge=True`: interior or within `tol` of opening edge.
    """
    normalize_opening_dict(op)
    poly = op["polygon"]
    inside = _raycast_point_in_poly(px, py, poly)
    dist_e = _min_dist_to_poly_edges(px, py, poly)
    if include_edge:
        return inside or (dist_e <= tol)
    return inside and (dist_e >= tol)


def _trace_union_polygon_from_rects(rects: List[List[float]]) -> List[List[float]]:
    """
    Computes an exact closed orthogonal boundary loop from a list of touching/overlapping
    rectangles `[x1, y1, x2, y2]` using elementary grid decomposition + boundary walk.
    """
    if not rects:
        return []
    if len(rects) == 1:
        r = rects[0]
        return [[r[0], r[1]], [r[2], r[1]], [r[2], r[3]], [r[0], r[3]]]

    xs = sorted({round(float(r[0]), 3) for r in rects} | {round(float(r[2]), 3) for r in rects})
    ys = sorted({round(float(r[1]), 3) for r in rects} | {round(float(r[3]), 3) for r in rects})
    nx = len(xs) - 1
    ny = len(ys) - 1
    if nx <= 0 or ny <= 0:
        return []

    filled = [[False] * nx for _ in range(ny)]
    for j in range(ny):
        cy = (ys[j] + ys[j + 1]) / 2.0
        for i in range(nx):
            cx = (xs[i] + xs[i + 1]) / 2.0
            for r in rects:
                if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                    filled[j][i] = True
                    break

    # Directed CCW boundary edges around filled cells
    edges: Dict[Tuple[float, float], List[Tuple[float, float]]] = {}

    def add_edge(p1: Tuple[float, float], p2: Tuple[float, float]) -> None:
        edges.setdefault(p1, []).append(p2)

    for j in range(ny):
        for i in range(nx):
            if not filled[j][i]:
                continue
            if j == 0 or not filled[j - 1][i]:
                add_edge((xs[i], ys[j]), (xs[i + 1], ys[j]))
            if i == nx - 1 or not filled[j][i + 1]:
                add_edge((xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]))
            if j == ny - 1 or not filled[j + 1][i]:
                add_edge((xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1]))
            if i == 0 or not filled[j][i - 1]:
                add_edge((xs[i], ys[j + 1]), (xs[i], ys[j]))

    if not edges:
        return []

    # Start at bottom-most, left-most vertex
    start_v = min(edges.keys(), key=lambda p: (p[1], p[0]))
    loop: List[Tuple[float, float]] = [start_v]
    cur = start_v
    for _ in range(len(edges) * 4 + 10):
        nxt_list = edges.get(cur)
        if not nxt_list:
            break
        nxt = nxt_list.pop(0)
        if nxt == start_v:
            break
        loop.append(nxt)
        cur = nxt

    if len(loop) < 3:
        return [[xs[0], ys[0]], [xs[-1], ys[0]], [xs[-1], ys[-1]], [xs[0], ys[-1]]]

    # Simplify collinear points
    simplified: List[List[float]] = []
    m = len(loop)
    for k in range(m):
        p_prev = loop[(k - 1) % m]
        p_curr = loop[k]
        p_next = loop[(k + 1) % m]
        dx1, dy1 = p_curr[0] - p_prev[0], p_curr[1] - p_prev[1]
        dx2, dy2 = p_next[0] - p_curr[0], p_next[1] - p_curr[1]
        if abs(dx1 * dy2 - dy1 * dx2) < 1e-6:
            continue
        simplified.append([round(p_curr[0], 3), round(p_curr[1], 3)])
    return simplified if len(simplified) >= 3 else [[round(p[0], 3), round(p[1], 3)] for p in loop]


def _beam_lies_between_openings(
    op_a: Dict[str, Any],
    op_b: Dict[str, Any],
    beams: List[Dict[str, Any]],
) -> bool:
    """
    Returns True if a physical beam separates the touching border of `op_a` and `op_b`.
    """
    normalize_opening_dict(op_a)
    normalize_opening_dict(op_b)
    rects_a = op_a.get("sub_rects") or [[op_a["min_x"], op_a["min_y"], op_a["max_x"], op_a["max_y"]]]
    rects_b = op_b.get("sub_rects") or [[op_b["min_x"], op_b["min_y"], op_b["max_x"], op_b["max_y"]]]

    for ra in rects_a:
        for rb in rects_b:
            # Shared vertical interface
            if abs(ra[2] - rb[0]) <= 0.18 or abs(rb[2] - ra[0]) <= 0.18:
                shared_x = (ra[2] + rb[0]) / 2.0 if abs(ra[2] - rb[0]) <= 0.18 else (rb[2] + ra[0]) / 2.0
                ov_y1 = max(ra[1], rb[1])
                ov_y2 = min(ra[3], rb[3])
                if ov_y2 - ov_y1 >= 0.30:
                    for bm in beams:
                        bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                        bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
                        if abs(bex - bsx) < abs(bey - bsy):
                            if abs(bsx - shared_x) <= max(0.30, float(bm.get("width_m", 0.30)) / 2.0 + 0.15):
                                b_ov = min(max(bsy, bey), ov_y2) - max(min(bsy, bey), ov_y1)
                                if b_ov >= (ov_y2 - ov_y1) * 0.40:
                                    return True
            # Shared horizontal interface
            if abs(ra[3] - rb[1]) <= 0.18 or abs(rb[3] - ra[1]) <= 0.18:
                shared_y = (ra[3] + rb[1]) / 2.0 if abs(ra[3] - rb[1]) <= 0.18 else (rb[3] + ra[1]) / 2.0
                ov_x1 = max(ra[0], rb[0])
                ov_x2 = min(ra[2], rb[2])
                if ov_x2 - ov_x1 >= 0.30:
                    for bm in beams:
                        bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
                        bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
                        if abs(bex - bsx) >= abs(bey - bsy):
                            if abs(bsy - shared_y) <= max(0.30, float(bm.get("width_m", 0.30)) / 2.0 + 0.15):
                                b_ov = min(max(bsx, bex), ov_x2) - max(min(bsx, bex), ov_x1)
                                if b_ov >= (ov_x2 - ov_x1) * 0.40:
                                    return True
    return False


def _openings_touch_or_overlap(op_a: Dict[str, Any], op_b: Dict[str, Any], gap_tol: float = 0.15) -> bool:
    normalize_opening_dict(op_a)
    normalize_opening_dict(op_b)
    rects_a = op_a.get("sub_rects") or [[op_a["min_x"], op_a["min_y"], op_a["max_x"], op_a["max_y"]]]
    rects_b = op_b.get("sub_rects") or [[op_b["min_x"], op_b["min_y"], op_b["max_x"], op_b["max_y"]]]
    for ra in rects_a:
        for rb in rects_b:
            ov_x = min(ra[2], rb[2]) - max(ra[0], rb[0])
            ov_y = min(ra[3], rb[3]) - max(ra[1], rb[1])
            if (ov_x >= -gap_tol and ov_y >= 0.25) or (ov_y >= -gap_tol and ov_x >= 0.25) or (ov_x >= 0.10 and ov_y >= 0.10):
                return True
    return False


def coalesce_adjacent_openings(story_data: Dict[str, Any]) -> Tuple[int, List[str]]:
    """
    Automatically merges touching or overlapping openings whenever NO physical beam
    separates their shared border, forming one unified polygonal/orthogonal opening (`OP#`).
    """
    openings = story_data.get("openings", [])
    beams = story_data.get("beams", [])
    if len(openings) <= 1:
        for idx, op in enumerate(openings):
            normalize_opening_dict(op)
            op["id"] = f"OP{idx + 1}"
        return 0, []

    for op in openings:
        normalize_opening_dict(op)

    merged_events: List[str] = []
    merges = 0
    changed = True
    while changed:
        changed = False
        n = len(openings)
        for i in range(n):
            for j in range(i + 1, n):
                oa, ob = openings[i], openings[j]
                if _openings_touch_or_overlap(oa, ob) and not _beam_lies_between_openings(oa, ob, beams):
                    rects_a = oa.get("sub_rects") or [[oa["min_x"], oa["min_y"], oa["max_x"], oa["max_y"]]]
                    rects_b = ob.get("sub_rects") or [[ob["min_x"], ob["min_y"], ob["max_x"], ob["max_y"]]]
                    combined_rects = list(rects_a) + list(rects_b)
                    # Snap near-touching rectangle edges together cleanly (gap <= 0.15m)
                    for idx_r in range(len(rects_a)):
                        for idx_s in range(len(rects_b)):
                            ra = combined_rects[idx_r]
                            rb = combined_rects[len(rects_a) + idx_s]
                            if 0.0 < abs(rb[0] - ra[2]) <= 0.15:
                                rb[0] = ra[2]
                            elif 0.0 < abs(ra[0] - rb[2]) <= 0.15:
                                ra[0] = rb[2]
                            if 0.0 < abs(rb[1] - ra[3]) <= 0.15:
                                rb[1] = ra[3]
                            elif 0.0 < abs(ra[1] - rb[3]) <= 0.15:
                                ra[1] = rb[3]
                    new_poly = _trace_union_polygon_from_rects(combined_rects)
                    if not new_poly:
                        # Fallback to bounding hull of non-orthogonal polylines
                        all_pts = list(oa["polygon"]) + list(ob["polygon"])
                        nmin_x, nmax_x = min(p[0] for p in all_pts), max(p[0] for p in all_pts)
                        nmin_y, nmax_y = min(p[1] for p in all_pts), max(p[1] for p in all_pts)
                        new_poly = [[nmin_x, nmin_y], [nmax_x, nmin_y], [nmax_x, nmax_y], [nmin_x, nmax_y]]
                    oa["sub_rects"] = combined_rects
                    oa["polygon"] = new_poly
                    oa["merged_from"] = [str(oa.get("id")), str(ob.get("id"))]
                    normalize_opening_dict(oa)
                    merged_events.append(f"Merged adjacent openings ({oa.get('id')} + {ob.get('id')}) into a unified opening because no dividing beam separates them.")
                    openings.pop(j)
                    merges += 1
                    changed = True
                    break
            if changed:
                break

    for idx, op in enumerate(openings):
        op["id"] = f"OP{idx + 1}"
    if merges > 0:
        _log_eng("OPENING_MERGE", f"Merged {merges} adjacent opening(s)", merged_events)
    return merges, merged_events


def beam_borders_or_crosses_opening(
    bm: Dict[str, Any],
    op: Dict[str, Any],
    edge_tol: float = 0.25,
) -> Optional[str]:
    """
    Determines the geometric relationship between beam `bm` and opening `op`:
    - `'crosses'`: beam centerline cuts strictly through the interior of `op`.
    - `'borders'`: beam runs parallel along/adjacent to an edge of `op` (or lies between two openings),
      where a Hidden Beam's width would expand into the opening void!
    - `None`: completely clear of `op`.
    """
    normalize_opening_dict(op)
    sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
    ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
    is_horiz = abs(ex - sx) >= abs(ey - sy)
    half_w = float(bm.get("width_m", 0.30)) / 2.0
    poly = op["polygon"]

    # Sample 9 interior points strictly along the beam centerline
    inside_hits = 0
    for k in range(1, 10):
        t = k / 10.0
        px = sx + (ex - sx) * t
        py = sy + (ey - sy) * t
        if is_point_in_opening(px, py, op, include_edge=False, tol=0.14):
            inside_hits += 1
    if inside_hits >= 2:
        return "crosses"

    # Check if beam borders any parallel edge of `op` or touches an opening edge with its width
    n_v = len(poly)
    b_min_x, b_max_x = min(sx, ex), max(sx, ex)
    b_min_y, b_max_y = min(sy, ey), max(sy, ey)
    prox = max(edge_tol, half_w + 0.10)

    for idx in range(n_v):
        x1, y1 = float(poly[idx][0]), float(poly[idx][1])
        x2, y2 = float(poly[(idx + 1) % n_v][0]), float(poly[(idx + 1) % n_v][1])
        e_horiz = abs(x2 - x1) >= abs(y2 - y1)
        if is_horiz and e_horiz:
            ov = min(b_max_x, max(x1, x2)) - max(b_min_x, min(x1, x2))
            if ov >= 0.35 and abs(sy - ((y1 + y2) / 2.0)) <= prox:
                return "borders"
        elif (not is_horiz) and (not e_horiz):
            ov = min(b_max_y, max(y1, y2)) - max(b_min_y, min(y1, y2))
            if ov >= 0.35 and abs(sx - ((x1 + x2) / 2.0)) <= prox:
                return "borders"

    # Also check if widened Hidden Beam section crosses outside L-shaped/recessed opening bounds
    omin_x, omax_x = float(op["min_x"]), float(op["max_x"])
    omin_y, omax_y = float(op["min_y"]), float(op["max_y"])
    if is_horiz and (min(b_max_x, omax_x) - max(b_min_x, omin_x)) >= 0.35:
        if omin_y - prox <= sy <= omax_y + prox:
            # Verify midpoint near opening edge
            mid_x = (max(b_min_x, omin_x) + min(b_max_x, omax_x)) / 2.0
            if is_point_in_opening(mid_x, sy + half_w * 0.9, op, include_edge=True, tol=0.05) or is_point_in_opening(mid_x, sy - half_w * 0.9, op, include_edge=True, tol=0.05):
                return "borders"
    elif (not is_horiz) and (min(b_max_y, omax_y) - max(b_min_y, omin_y)) >= 0.35:
        if omin_x - prox <= sx <= omax_x + prox:
            mid_y = (max(b_min_y, omin_y) + min(b_max_y, omax_y)) / 2.0
            if is_point_in_opening(sx + half_w * 0.9, mid_y, op, include_edge=True, tol=0.05) or is_point_in_opening(sx - half_w * 0.9, mid_y, op, include_edge=True, tol=0.05):
                return "borders"
    return None


def beam_has_solid_slab_expansion_room(
    story_data: Dict[str, Any],
    bm: Dict[str, Any],
    test_offset_m: float = 0.35,
) -> bool:
    """
    Checks if a beam has solid slab space on at least one lateral side
    (strictly inside slab_edge_polygon and outside all openings) to expand as a Hidden Beam.
    If BOTH lateral sides are voids or exterior boundaries, the beam is trapped and MUST be a Drop Beam.
    """
    poly = story_data.get("slab_edge_polygon", [])
    openings = story_data.get("openings", [])
    if len(poly) < 3:
        return True

    bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
    bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
    mx, my = (bsx + bex) / 2.0, (bsy + bey) / 2.0
    is_horiz = abs(bex - bsx) >= abs(bey - bsy)

    if is_horiz:
        probes = [(mx, my + test_offset_m), (mx, my - test_offset_m)]
    else:
        probes = [(mx + test_offset_m, my), (mx - test_offset_m, my)]

    for px, py in probes:
        if not _point_in_polygon_2d(px, py, poly):
            continue
        in_any_op = any(
            is_point_in_opening(px, py, op, include_edge=True, tol=0.04)
            for op in openings
        )
        if not in_any_op:
            return True

    return False


def enforce_opening_adjacent_drop_beams_and_cascade(story_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Selective Opening Drop Beam Enforcement & Recursive Carrier Cascade (v2.4.0):
    1. A beam is converted to a Drop Beam ONLY if:
       - It cuts directly across a slab opening void (`crosses`), OR
       - It is trapped between two voids/openings with NO solid slab expansion room on either side, OR
       - Its cross-section width physically overflows outside the outer building boundary.
       Parallel boundary/trimmer beams (such as B8 or B9) that have solid slab on the opposite side
       CAN remain Hidden Beams and are NOT auto-converted to Drop!
    2. Recursive Carrier Cascade: Whenever any beam becomes a Drop Beam (such as secondary B7),
       EVERY carrier beam supporting it (`sup['kind'] == 'beam'`) MUST also convert from Hidden Beam -> Drop Beam,
       cascading upstream (e.g. Carrier B6 becomes Drop because B7 rests on it).
    """
    beams = story_data.get("beams", [])
    openings = story_data.get("openings", [])
    if not beams:
        return [], []

    reconcile_all_story_beams_supports_and_spans(story_data)
    beam_by_id = {str(b.get("id")): b for b in beams if b.get("id")}
    slab_poly = story_data.get("slab_edge_polygon", [])
    has_bnd, pmin_x, pmin_y, pmax_x, pmax_y = get_slab_bounding_box(slab_poly)
    slab_h_m = max(0.25, float(story_data.get("adopted_slab_thickness_cm", 30.0)) / 100.0)

    converted_ids: List[str] = []
    alerts: List[str] = []

    # Step 1: Convert Hidden beam crossing opening void or trapped with no expansion room -> Drop Beam
    for bm in beams:
        bid = str(bm.get("id", ""))
        b_kind = "drop" if "drop" in str(bm.get("beam_kind", bm.get("kind", "hidden"))).lower() else "hidden"
        if b_kind != "hidden":
            continue

        crossing_ops: List[str] = []
        bordering_ops: List[str] = []
        for op in openings:
            rel = beam_borders_or_crosses_opening(bm, op)
            if rel == "crosses":
                crossing_ops.append(str(op.get("id", "OP")))
            elif rel == "borders":
                bordering_ops.append(str(op.get("id", "OP")))

        has_room = beam_has_solid_slab_expansion_room(story_data, bm)

        overflows_boundary = False
        if has_bnd and float(bm.get("width_m", 0.40)) > 0.405:
            bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
            hw = float(bm.get("width_m", 0.40)) / 2.0
            if abs(bex - bsx) >= abs(bey - bsy):
                if (bsy - hw) < (pmin_y - 0.05) or (bsy + hw) > (pmax_y + 0.05):
                    overflows_boundary = True
            else:
                if (bsx - hw) < (pmin_x - 0.05) or (bsx + hw) > (pmax_x + 0.05):
                    overflows_boundary = True

        must_convert = False
        reason_msg = ""
        if crossing_ops:
            must_convert = True
            reason_msg = (
                f"Opening Rule: Beam {bid} converted to Drop Beam (0.20x0.40m) "
                f"because it cuts directly across opening void(s) {', '.join(crossing_ops)}."
            )
        elif not has_room and bordering_ops:
            must_convert = True
            reason_msg = (
                f"Opening Boundary Rule: Beam {bid} converted to Drop Beam (0.20x0.40m) "
                f"because both lateral sides are voids ({', '.join(bordering_ops)}) with no solid slab expansion room."
            )
        elif overflows_boundary:
            must_convert = True
            reason_msg = (
                f"Building Boundary Rule: Beam {bid} section width expands outside building perimeter "
                f"and was converted to Drop Beam (0.20x0.40m)."
            )

        if must_convert:
            bm["beam_kind"] = "drop"
            bm["kind"] = "drop"
            bm["width_m"] = 0.20
            bm["depth_m"] = _snap_drop_depth_m(max(0.40, slab_h_m), 0.40)
            bm["initial_width_m"] = 0.20
            bm["initial_depth_m"] = bm["depth_m"]
            bm.pop("manual_loads_override", None)
            converted_ids.append(bid)
            alerts.append(reason_msg)
            _log_eng("OPENING_DROP_FORCE", reason_msg, {"beam_id": bid, "openings": crossing_ops or bordering_ops})

    # Step 2: Recursive Upstream Carrier Cascade (Drop secondary beam -> Drop carrier beam!)
    changed = True
    while changed:
        changed = False
        for bm in beams:
            bid = str(bm.get("id", ""))
            b_kind = "drop" if "drop" in str(bm.get("beam_kind", bm.get("kind", "hidden"))).lower() else "hidden"
            if b_kind != "drop":
                continue
            b_depth = float(bm.get("depth_m", 0.40))
            for sup in bm.get("supports", []):
                if sup.get("kind") == "beam":
                    car_id = str(sup.get("target_id", ""))
                    car_bm = beam_by_id.get(car_id)
                    if car_bm is None:
                        continue
                    car_kind = "drop" if "drop" in str(car_bm.get("beam_kind", car_bm.get("kind", "hidden"))).lower() else "hidden"
                    if car_kind == "hidden":
                        car_bm["beam_kind"] = "drop"
                        car_bm["kind"] = "drop"
                        car_bm["width_m"] = 0.20
                        car_bm["depth_m"] = _snap_drop_depth_m(max(0.40, b_depth, slab_h_m), 0.40)
                        car_bm["initial_width_m"] = 0.20
                        car_bm["initial_depth_m"] = car_bm["depth_m"]
                        car_bm.pop("manual_loads_override", None)
                        if car_id not in converted_ids:
                            converted_ids.append(car_id)
                        cmsg = (
                            f"Structural Carrier Cascade: Carrier Beam {car_id} automatically converted to Drop Beam "
                            f"(0.20x{car_bm['depth_m']:.2f}m) because Secondary Drop Beam {bid} rests on it."
                        )
                        alerts.append(cmsg)
                        _log_eng("CARRIER_CASCADE", cmsg, {"secondary": bid, "carrier": car_id})
                        changed = True

    if converted_ids:
        reconcile_all_story_beams_supports_and_spans(story_data)
    return converted_ids, alerts


def find_nearest_solid_edge_for_column(
    story_data: Dict[str, Any],
    col: Dict[str, Any],
    op: Dict[str, Any],
) -> Tuple[float, float]:
    """
    Computes the nearest valid solid position `(new_x, new_y)` just outside opening `op`
    and strictly inside `slab_edge_polygon` so a conflicting column can be shifted cleanly.
    """
    normalize_opening_dict(op)
    cx, cy = float(col.get("x", 0.0)), float(col.get("y", 0.0))
    hb = float(col.get("b_m", 0.20)) / 2.0
    hh = float(col.get("h_m", 0.40)) / 2.0
    has_bnd, pmin_x, pmin_y, pmax_x, pmax_y = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))

    poly = op["polygon"]
    candidates: List[Tuple[float, float, float]] = []
    n_v = len(poly)
    for idx in range(n_v):
        x1, y1 = float(poly[idx][0]), float(poly[idx][1])
        x2, y2 = float(poly[(idx + 1) % n_v][0]), float(poly[(idx + 1) % n_v][1])
        # Project point onto segment and step outward by column half-size + 0.01m
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-8:
            continue
        t = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / seg2))
        px = x1 + t * dx
        py = y1 + t * dy
        L = math.sqrt(seg2)
        # Try both normals to find whichever side is outside `op`
        nx, ny = -dy / L, dx / L
        for sgn in (1.0, -1.0):
            cand_x = px + sgn * nx * (hb + 0.02)
            cand_y = py + sgn * ny * (hh + 0.02)
            if has_bnd:
                cand_x = min(max(cand_x, pmin_x + hb), pmax_x - hb)
                cand_y = min(max(cand_y, pmin_y + hh), pmax_y - hh)
            if not is_point_in_opening(cand_x, cand_y, op, include_edge=False, tol=0.04):
                candidates.append((math.hypot(cand_x - cx, cand_y - cy), round(cand_x, 3), round(cand_y, 3)))

    if candidates:
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1], candidates[0][2]

    # Bounding-box fallback
    c_left = (float(op["min_x"]) - hb, cy)
    c_right = (float(op["max_x"]) + hb, cy)
    c_bot = (cx, float(op["min_y"]) - hh)
    c_top = (cx, float(op["max_y"]) + hh)
    best_c = min([c_left, c_right, c_bot, c_top], key=lambda pt: math.hypot(pt[0] - cx, pt[1] - cy))
    nx_f, ny_f = best_c
    if has_bnd:
        nx_f = min(max(nx_f, pmin_x + hb), pmax_x - hb)
        ny_f = min(max(ny_f, pmin_y + hh), pmax_y - hh)
    return round(nx_f, 3), round(ny_f, 3)


def create_opening_with_priority_resolution(
    story_data: Dict[str, Any],
    points_or_rect: Any,
    is_polygon: bool = False,
) -> Dict[str, Any]:
    """
    Creates a Rectangular or Polygonal Slab Opening (`OP#`) with **Opening Priority**:
    1. Automatically merges adjacent touching/overlapping openings when no beam separates them.
    2. If any existing beam cuts across the opening interior, attempts to shift it cleanly
       to the nearest solid edge of the opening and converts it to a Drop Beam (`0.20 × 0.40 m`).
    3. Enforces Opening-Adjacent Drop Beam + Recursive Carrier Cascade (`B7 -> B6`).
    4. Removes any Slab object completely covered by the new opening.
    5. Detects any existing Column inside the opening and returns interactive choices
       (`suggested_edge` vs `Double-Height 2H`) in `conflicting_columns` for UI confirmation.
    """
    openings = story_data.setdefault("openings", [])
    if is_polygon:
        pts = [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in points_or_rect]
        if len(pts) < 3:
            return {"ok": False, "error": "Polygon opening requires at least 3 points."}
        new_op: Dict[str, Any] = {
            "id": f"OP{len(openings) + 1}",
            "shape": "polygon",
            "polygon": pts,
        }
        # Also detect axis-aligned bounding rectangle sub_rect if pure rectangle
        xs = {p[0] for p in pts}
        ys = {p[1] for p in pts}
        if len(pts) == 4 and len(xs) == 2 and len(ys) == 2:
            new_op["sub_rects"] = [[min(xs), min(ys), max(xs), max(ys)]]
    else:
        p1, p2 = points_or_rect[0], points_or_rect[1]
        x1, y1 = round(min(float(p1[0]), float(p2[0])), 3), round(min(float(p1[1]), float(p2[1])), 3)
        x2, y2 = round(max(float(p1[0]), float(p2[0])), 3), round(max(float(p1[1]), float(p2[1])), 3)

        # Smart flush alignment with nearby bounding beams (v2.4.0):
        # Snap flush to beam inner faces so the opening does not expand into beams by half_w
        for bm_cand in story_data.get("beams", []):
            bw_c = float(bm_cand.get("width_m", 0.20))
            hw_c = bw_c / 2.0
            bsx_c, bsy_c = float(bm_cand.get("start_x", 0.0)), float(bm_cand.get("start_y", 0.0))
            bex_c, bey_c = float(bm_cand.get("end_x", 0.0)), float(bm_cand.get("end_y", 0.0))
            if abs(bex_c - bsx_c) >= abs(bey_c - bsy_c):
                # Horizontal beam
                if max(bsx_c, bex_c) + 0.10 > x1 and min(bsx_c, bex_c) - 0.10 < x2:
                    if abs(y1 - bsy_c) <= hw_c + 0.08 or abs(y1 - (bsy_c + hw_c)) <= 0.08:
                        y1 = round(bsy_c + hw_c, 3)
                    elif abs(y2 - bsy_c) <= hw_c + 0.08 or abs(y2 - (bsy_c - hw_c)) <= 0.08:
                        y2 = round(bsy_c - hw_c, 3)
            else:
                # Vertical beam
                if max(bsy_c, bey_c) + 0.10 > y1 and min(bsy_c, bey_c) - 0.10 < y2:
                    if abs(x1 - bsx_c) <= hw_c + 0.08 or abs(x1 - (bsx_c + hw_c)) <= 0.08:
                        x1 = round(bsx_c + hw_c, 3)
                    elif abs(x2 - bsx_c) <= hw_c + 0.08 or abs(x2 - (bsx_c - hw_c)) <= 0.08:
                        x2 = round(bsx_c - hw_c, 3)

        if (x2 - x1) < 0.25 or (y2 - y1) < 0.25:
            return {"ok": False, "error": "Opening width and height must be at least 0.25 m."}
        new_op = {
            "id": f"OP{len(openings) + 1}",
            "shape": "rectangle",
            "min_x": x1,
            "max_x": x2,
            "min_y": y1,
            "max_y": y2,
            "sub_rects": [[x1, y1, x2, y2]],
            "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    normalize_opening_dict(new_op)
    openings.append(new_op)

    merges, merge_msgs = coalesce_adjacent_openings(story_data)
    alerts: List[str] = list(merge_msgs)

    # Resolve any beam cutting straight across any opening by shifting to nearest solid opening edge + converting to Drop Beam
    shifted_beams: List[str] = []
    beams = story_data.get("beams", [])
    has_bnd, pmin_x, pmin_y, pmax_x, pmax_y = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))

    for bm in beams:
        bid = str(bm.get("id", ""))
        for op in story_data.get("openings", []):
            rel = beam_borders_or_crosses_opening(bm, op)
            if rel != "crosses":
                continue
            sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
            is_h = abs(ex - sx) >= abs(ey - sy)
            # First convert to Drop Beam (width 0.20, half_w 0.10)
            bm["beam_kind"] = "drop"
            bm["kind"] = "drop"
            bm["width_m"] = 0.20
            bm["depth_m"] = _snap_drop_depth_m(max(0.40, float(bm.get("depth_m", 0.40))), 0.40)
            bm["initial_width_m"] = 0.20
            bm["initial_depth_m"] = bm["depth_m"]

            if is_h:
                cand_ys = [round(float(op["min_y"]) - 0.10, 3), round(float(op["max_y"]) + 0.10, 3)]
                if has_bnd:
                    cand_ys = [min(max(cy_c, pmin_y + 0.10), pmax_y - 0.10) for cy_c in cand_ys]
                best_y = min(cand_ys, key=lambda cy_c: abs(cy_c - sy))
                bm["start_y"] = bm["end_y"] = best_y
                shifted_beams.append(bid)
                alerts.append(f"Opening Priority: Beam {bid} cut through opening {op['id']}; shifted to solid edge (Y={best_y:.2f}m) and converted to Drop Beam.")
            else:
                cand_xs = [round(float(op["min_x"]) - 0.10, 3), round(float(op["max_x"]) + 0.10, 3)]
                if has_bnd:
                    cand_xs = [min(max(cx_c, pmin_x + 0.10), pmax_x - 0.10) for cx_c in cand_xs]
                best_x = min(cand_xs, key=lambda cx_c: abs(cx_c - sx))
                bm["start_x"] = bm["end_x"] = best_x
                shifted_beams.append(bid)
                alerts.append(f"Opening Priority: Beam {bid} cut through opening {op['id']}; shifted to solid edge (X={best_x:.2f}m) and converted to Drop Beam.")

    # Enforce Opening-Adjacent Drop Beam & Carrier Cascade
    conv_ids, cascade_alerts = enforce_opening_adjacent_drop_beams_and_cascade(story_data)
    alerts.extend(cascade_alerts)

    # Remove slabs whose centers lie inside any opening
    rem_slabs: List[str] = []
    kept_slabs: List[Dict[str, Any]] = []
    for slb in story_data.get("slabs", []):
        if "min_x" in slb:
            scx = (float(slb["min_x"]) + float(slb["max_x"])) / 2.0
            scy = (float(slb["min_y"]) + float(slb["max_y"])) / 2.0
            if any(is_point_in_opening(scx, scy, op, include_edge=False, tol=0.05) for op in story_data.get("openings", [])):
                rem_slabs.append(str(slb.get("id", "S")))
                continue
        kept_slabs.append(slb)
    if rem_slabs:
        story_data["slabs"] = kept_slabs
        alerts.append(f"Removed slabs overlapping opening: {', '.join(rem_slabs)}.")

    # Detect any conflicting columns strictly inside any opening
    conflicting_columns: List[Dict[str, Any]] = []
    for col in story_data.get("columns", []):
        if not col.get("active", True) or col.get("double_height", False):
            continue
        cx, cy = float(col["x"]), float(col["y"])
        for op in story_data.get("openings", []):
            if is_point_in_opening(cx, cy, op, include_edge=False, tol=0.05):
                edge_x, edge_y = find_nearest_solid_edge_for_column(story_data, col, op)
                conflicting_columns.append({
                    "column_id": str(col["id"]),
                    "opening_id": str(op["id"]),
                    "current_pos": (cx, cy),
                    "suggested_edge": (edge_x, edge_y),
                })
                break

    final_op = story_data["openings"][-1] if story_data.get("openings") else new_op
    _log_eng(
        "OPENING_CREATED",
        f"Opening {final_op.get('id')} created ({final_op.get('shape','rect')})",
        {
            "shifted_beams": shifted_beams,
            "converted_drop_beams": conv_ids,
            "conflicting_columns": conflicting_columns,
            "alerts": alerts,
        },
    )
    return {
        "ok": True,
        "opening": final_op,
        "merged_count": merges,
        "shifted_beams": shifted_beams,
        "converted_drop_beams": conv_ids,
        "conflicting_columns": conflicting_columns,
        "alerts": alerts,
    }


def convert_beam_kind_and_section(
    story_data: Dict[str, Any],
    beam_id: str,
    new_kind: Optional[str] = None,
    new_width_m: Optional[float] = None,
    new_depth_m: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Converts a beam between Hidden Beam ('hidden', e.g., 0.40x0.30m) and Drop Beam ('drop', e.g., 0.20x0.40m)
    or updates its cross-section, clamps it inside the building boundary, and reconciles adjacent slabs.
    Enforces:
    - Opening Rule: A beam cutting across an opening or trapped between voids cannot be Hidden!
    - Structural Hierarchy Rule: A Carrier Beam cannot be Hidden if a Drop Beam rests on it!
    - If converting a Secondary Beam to Drop, automatically cascades Hidden Carrier Beam(s) -> Drop Beam!
    """
    reconcile_all_story_beams_supports_and_spans(story_data)
    beams = story_data.get("beams", [])
    bm = next((b for b in beams if b.get("id") == beam_id), None)
    if not bm:
        return False, f"Beam {beam_id} not found."

    cur_kind_raw = str(bm.get("beam_kind", bm.get("kind", "hidden"))).lower()
    cur_kind = "drop" if "drop" in cur_kind_raw else "hidden"
    target_kind = new_kind if new_kind in ("hidden", "drop") else ("drop" if cur_kind == "hidden" else "hidden")

    beam_by_id = {str(b.get("id")): b for b in beams if b.get("id")}

    # Rule 0: Check Opening Relations
    if target_kind == "hidden":
        crossing_ops: List[str] = []
        trapped_ops: List[str] = []
        for op in story_data.get("openings", []):
            rel = beam_borders_or_crosses_opening(bm, op)
            if rel == "crosses":
                crossing_ops.append(str(op.get("id", "OP")))
            elif rel == "borders":
                trapped_ops.append(str(op.get("id", "OP")))

        if crossing_ops:
            return (
                False,
                f"Opening Boundary Rule: Cannot convert Beam {beam_id} to a Hidden Beam "
                f"because it cuts directly across opening void(s) ({', '.join(crossing_ops)})!",
            )
        if trapped_ops and not beam_has_solid_slab_expansion_room(story_data, bm):
            return (
                False,
                f"Opening Boundary Rule: Cannot convert Beam {beam_id} to a Hidden Beam "
                f"because both lateral sides are voids ({', '.join(trapped_ops)}) with no solid slab expansion room!",
            )

    # Rule A: Prevent converting Carrier Beam `beam_id` to Hidden if any Secondary Drop Beam rests on it
    if target_kind == "hidden":
        supported_drop_beams: List[str] = []
        for other_b in beams:
            if other_b.get("id") == beam_id:
                continue
            other_kind = "drop" if "drop" in str(other_b.get("beam_kind", other_b.get("kind", "hidden"))).lower() else "hidden"
            if other_kind == "drop":
                for sup in other_b.get("supports", []):
                    if sup.get("kind") == "beam" and str(sup.get("target_id")) == str(beam_id):
                        supported_drop_beams.append(str(other_b.get("id")))
                        break
        if supported_drop_beams:
            return (
                False,
                f"Structural Hierarchy Error: Cannot convert Carrier Beam {beam_id} to a Hidden Beam "
                f"because Drop Beam(s) {', '.join(supported_drop_beams)} rest on it! Convert {', '.join(supported_drop_beams)} to Hidden Beam(s) first.",
            )

    # Rule B: When converting Secondary Beam `beam_id` to Drop while resting on Hidden Carrier(s),
    # check if any carrier is Hidden — reject only if explicit conflict, OR auto-cascade via enforce_opening_adjacent_drop_beams_and_cascade
    if target_kind == "drop":
        hidden_carriers: List[str] = []
        for sup in bm.get("supports", []):
            if sup.get("kind") == "beam":
                car_id = str(sup.get("target_id", ""))
                car_bm = beam_by_id.get(car_id)
                if car_bm is not None:
                    car_kind = "drop" if "drop" in str(car_bm.get("beam_kind", car_bm.get("kind", "hidden"))).lower() else "hidden"
                    if car_kind == "hidden":
                        hidden_carriers.append(car_id)
        if hidden_carriers:
            return (
                False,
                f"Structural Hierarchy Error: Cannot convert Beam {beam_id} to a Drop Beam "
                f"because it rests on Hidden Carrier Beam(s) {', '.join(hidden_carriers)}! Convert {', '.join(hidden_carriers)} to a Drop Beam first.",
            )

    bm["beam_kind"] = target_kind
    bm["kind"] = target_kind

    min_supported_depth = 0.25
    for other_b in beams:
        if other_b.get("id") == beam_id:
            continue
        for sup in other_b.get("supports", []):
            if sup.get("kind") == "beam" and sup.get("target_id") == beam_id:
                min_supported_depth = max(min_supported_depth, float(other_b.get("depth_m", 0.30)))

    if new_width_m is not None and new_depth_m is not None:
        bm["width_m"] = round(max(0.12, float(new_width_m)), 3)
        bm["depth_m"] = round(max(min_supported_depth, float(new_depth_m)), 3)
    else:
        slab_t_m = round(float(story_data.get("adopted_slab_thickness_cm", 30.0)) / 100.0, 3)
        if target_kind == "drop":
            bm["width_m"] = 0.20
            bm["depth_m"] = _snap_drop_depth_m(max(0.40, slab_t_m, min_supported_depth), 0.40)
        else:
            bm["width_m"] = 0.30
            bm["depth_m"] = max(0.25, slab_t_m, min_supported_depth)

    bm["initial_width_m"] = bm["width_m"]
    bm["initial_depth_m"] = bm["depth_m"]
    bm.pop("manual_loads_override", None)
    move_beam_within_slab_boundary(story_data, beam_id, 0.0, 0.0)
    reconcile_and_split_slabs_after_beam_change(story_data)
    _log_eng("BEAM_CONVERT", f"Converted Beam {beam_id} -> {target_kind.upper()} ({bm['width_m']:.2f} x {bm['depth_m']:.2f} m)")
    return (
        True,
        f"Converted Beam {beam_id} to {target_kind.upper()} ({bm['width_m']:.2f} × {bm['depth_m']:.2f} m).",
    )


# ===== v2.4.3-r2 additive: full-width footprint containment + min-dimension floors =====
def reclamp_beam_full_width_inside_boundary(story_data, beam_id):
    bm = next((b for b in story_data.get("beams", []) if str(b.get("id")) == str(beam_id)), None)
    if bm is None: return True, False, ""
    has_bnd, minx, miny, maxx, maxy = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))
    ops = story_data.get("openings", [])
    hw = float(bm.get("width_m", 0.30)) / 2.0
    sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
    ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
    horiz = abs(ex - sx) >= abs(ey - sy)
    shifted = False
    TOL = 1e-4
    if horiz:
        lo = (miny + hw) if has_bnd else sy - hw
        hi = (maxy - hw) if has_bnd else sy + hw
        xlo, xhi = min(sx, ex), max(sx, ex)
        for _pass in range(3):
            moved = False
            for op in ops:
                oxlo, oxhi = float(op.get("min_x", 0.0)), float(op.get("max_x", 0.0))
                oylo, oyhi = float(op.get("min_y", 0.0)), float(op.get("max_y", 0.0))
                if min(xhi, oxhi) - max(xlo, oxlo) < 0.30: continue
                if (sy - hw) <= oyhi + TOL and (sy + hw) >= oylo - TOL:
                    opts = [c for c in (oylo - hw, oyhi + hw) if lo + TOL <= c <= hi - TOL]
                    if not opts: return False, shifted, "trapped between boundary/opening"
                    ny = min(opts, key=lambda c: abs(c - sy))
                    if abs(ny - sy) > 1e-9:
                        sy = ny; ey = sy; moved = True; shifted = True
            if not moved: break
        if has_bnd:
            cl = min(max(sy, lo), hi)
            if abs(cl - sy) > 1e-6: sy = ey = round(cl, 3); shifted = True
        bm["start_y"] = bm["end_y"] = round(sy, 3)
    else:
        lo = (minx + hw) if has_bnd else sx - hw
        hi = (maxx - hw) if has_bnd else sx + hw
        ylo, yhi = min(sy, ey), max(sy, ey)
        for _pass in range(3):
            moved = False
            for op in ops:
                oxlo, oxhi = float(op.get("min_x", 0.0)), float(op.get("max_x", 0.0))
                oylo, oyhi = float(op.get("min_y", 0.0)), float(op.get("max_y", 0.0))
                if min(yhi, oyhi) - max(ylo, oylo) < 0.30: continue
                if (sx - hw) <= oxhi + TOL and (sx + hw) >= oxlo - TOL:
                    opts = [c for c in (oxlo - hw, oxhi + hw) if lo + TOL <= c <= hi - TOL]
                    if not opts: return False, shifted, "trapped between boundary/opening"
                    nx = min(opts, key=lambda c: abs(c - sx))
                    if abs(nx - sx) > 1e-9:
                        sx = nx; ex = sx; moved = True; shifted = True
            if not moved: break
        if has_bnd:
            cl = min(max(sx, lo), hi)
            if abs(cl - sx) > 1e-6: sx = ex = round(cl, 3); shifted = True
        bm["start_x"] = bm["end_x"] = round(sx, 3)
    return True, shifted, "shifted full width inside boundary/openings" if shifted else ""

def enforce_beam_footprint_and_cascade(story_data):
    converted, alerts = [], []
    slab_h = max(0.25, float(story_data.get("adopted_slab_thickness_cm", 30.0)) / 100.0)
    for bm in list(story_data.get("beams", [])):
        bid = str(bm.get("id", ""))
        ok, shifted, msg = reclamp_beam_full_width_inside_boundary(story_data, bid)
        kind = "drop" if "drop" in str(bm.get("beam_kind", bm.get("kind", "hidden"))).lower() else "hidden"
        if not ok and kind == "hidden":
            bm["beam_kind"] = "drop"; bm["kind"] = "drop"
            bm["width_m"] = 0.20
            bm["depth_m"] = _snap_drop_depth_m(max(0.40, slab_h), 0.40)
            bm["initial_width_m"] = 0.20; bm["initial_depth_m"] = bm["depth_m"]
            bm.pop("manual_loads_override", None)
            converted.append(bid)
            alerts.append(f"Boundary/Opening Footprint Rule: Beam {bid} converted to Drop (0.20x{bm['depth_m']:.2f}m) - no room to expand as Hidden.")
            _log_eng("FOOTPRINT_DROP_FORCE", alerts[-1], {"beam_id": bid})
        elif shifted:
            reconcile_all_story_beams_supports_and_spans(story_data)
    if converted:
        c2, a2 = enforce_opening_adjacent_drop_beams_and_cascade(story_data)
        converted.extend([c for c in c2 if c not in converted]); alerts.extend(a2)
    return converted, alerts
