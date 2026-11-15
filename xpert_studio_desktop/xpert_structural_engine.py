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
from typing import Dict, Any, List, Tuple


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
        req_cm = round((ln * 100.0 / div) * fy_mod, 2)
        slab_reqs.append((req_cm, f"Slab Rib {sid} (Ln = {ln:.2f} m, L/{div:g})"))

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
            req_cm = round((ln * 100.0 / div) * fy_mod, 2)
            hidden_beam_reqs.append(
                (req_cm, bid, f"Hidden Beam {bid} (Span {idx + 1}, Ln = {ln:.2f} m, L/{div:g})", ln)
            )

    all_candidates: List[Tuple[float, str]] = list(slab_reqs) + [(r[0], r[2]) for r in hidden_beam_reqs]
    if not all_candidates:
        return {
            "has_data": False,
            "calculated_min_thickness_cm": 0.0,
            "badge_text": "20.0 cm (Drop Beams Only)",
            "governing_member": "All beams are Drop Beams; minimum slab rib thickness applies.",
            "smart_optimization": None,
        }

    all_candidates.sort(key=lambda x: x[0], reverse=True)
    max_req_cm, gov_desc = all_candidates[0]

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
                "rest_of_floor_req_cm": round(rest_max_cm, 1),
                "message": (
                    f"Optimization Suggestion: Hidden Beam {top_hb_id} (Ln = {top_hb_ln:.2f} m) "
                    f"governs the slab thickness at {top_hb_cm:.1f} cm (> 30 cm), whereas the rest "
                    f"of the floor requires only {rest_max_cm:.1f} cm (<= 30 cm). Converting {top_hb_id} "
                    f"to a Drop Beam (20x50 cm) keeps the entire slab thickness at 30.0 cm."
                ),
            }

    return {
        "has_data": True,
        "calculated_min_thickness_cm": max_req_cm,
        "badge_text": f"{max_req_cm:.1f} cm",
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
        span_pts = [(x_full[k], m_full[k], v_full[k]) for k in range(len(x_full)) if s_st <= x_full[k] <= s_en]
        best_x, best_m, _ = max(span_pts, key=lambda t: t[1]) if span_pts else (s_st, 0.0, 0.0)
        v_max_span = max([ abs(t[2]) for t in span_pts ] or [0.0])
        v_start = span_pts[0][2] if span_pts else 0.0
        v_end = span_pts[-1][2] if span_pts else 0.0
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


def ensure_beam_wall_flags(story_data: Dict[str, Any], beam: Dict[str, Any]) -> Dict[str, bool]:
    """
    Ensures `beam['span_wall_flags']` has a boolean flag for each span and cantilever of `beam`,
    initializing missing flags from `story_data['wall_load_policy']` ('all_beams' -> True, 'no_walls' -> False).
    """
    policy = str(story_data.get("wall_load_policy", "all_beams"))
    default_flag = (policy != "no_walls")
    flags: Dict[str, bool] = beam.setdefault("span_wall_flags", {})
    for seg in get_beam_span_segments(beam):
        k = seg["key"]
        if k not in flags:
            flags[k] = default_flag
    return flags


def set_story_wall_load_policy(
    story_data: Dict[str, Any],
    policy: str,
    wall_load_kn_m: Optional[float] = None,
    apply_to_all_existing_spans: bool = True,
    slab_load_kpa: Optional[float] = None,
) -> Tuple[int, str]:
    """
    Sets the Story-Level General Wall & Slab Load Policy:
    - policy = 'all_beams': Default wall load ON for all beam spans.
    - policy = 'no_walls': Default wall load OFF for all beam spans (e.g., Roof slab, allowing selective stair walls).
    """
    clean_policy = "no_walls" if policy == "no_walls" else "all_beams"
    story_data["wall_load_policy"] = clean_policy
    if wall_load_kn_m is not None:
        story_data["default_wall_load_kn_m"] = round(max(0.0, float(wall_load_kn_m)), 2)
    if slab_load_kpa is not None:
        story_data["slab_factored_wu_kpa"] = round(max(1.0, float(slab_load_kpa)), 2)
    w_val = float(story_data.get("default_wall_load_kn_m", 10.0))
    q_val = float(story_data.get("slab_factored_wu_kpa", 8.5))

    target_bool = (clean_policy == "all_beams")
    updated_spans = 0
    for bm in story_data.get("beams", []):
        flags = ensure_beam_wall_flags(story_data, bm)
        if apply_to_all_existing_spans:
            for k in list(flags.keys()):
                flags[k] = target_bool
                updated_spans += 1
        bm.pop("manual_loads_override", None)

    mode_desc = f"Wall Load ({w_val:.1f} kN/m) ON | Slab q = {q_val:.1f} kN/m²" if target_bool else f"Wall Load OFF by default | Slab q = {q_val:.1f} kN/m²"
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


def analyze_all_story_beams_and_columns(
    story_data: Dict[str, Any],
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
) -> Dict[str, Any]:
    """
    1-Click Story Analysis (v1.7.0):
    - Dynamically computes span-by-span distributed loads (Beam Self-Weight + Tributary One-Way Slab Load
      based on current Slab Rib Directions + Per-Span Masonry Wall Load Policy) with realistic default loads
      (q_slab = 8.5 kN/m², w_wall = 10.0 kN/m) and full mathematical equation breakdowns.
    - Topologically sorts beams so secondary supported beams are solved before their carrier beams.
    - Transfers secondary beam reactions onto primary carrier beams at exact distances measured strictly
      from Support Centerlines.
    - Solves all beams with exact vertical (90°) shear jumps and computes ACI 318 reinforcement design.
    """
    orig_beams = story_data.get("beams", [])
    beams = [dict(b) for b in orig_beams]
    columns = [dict(c) for c in story_data.get("columns", [])]
    slabs = story_data.get("slabs", [])
    story_h = float(story_data.get("height_m", 3.0))

    # Realistic default slab load (8.5 kN/m²) and wall load (10.0 kN/m) matching classic Xpert Beam Analysis (~30-35 kN/m)
    slab_wu_kpa = float(story_data.get("slab_factored_wu_kpa", 8.5))
    default_wall_w = float(story_data.get("default_wall_load_kn_m", 10.0))
    has_geometric_slabs = bool(slabs)
    has_wall_policy = ("wall_load_policy" in story_data) or any("span_wall_flags" in b for b in beams)

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
        raw_spans = [float(s) for s in b_copy.get("spans", []) if float(s) > 0.15]
        if not raw_spans:
            sx, sy = float(b_copy.get("start_x", 0.0)), float(b_copy.get("start_y", 0.0))
            ex, ey = float(b_copy.get("end_x", 4.0)), float(b_copy.get("end_y", 0.0))
            raw_spans = [round(max(0.50, math.hypot(ex - sx, ey - sy)), 3)]
        b_copy["spans"] = raw_spans

        c_left = max(0.0, float(b_copy.get("cantilever_left_m", 0.0)))
        c_right = max(0.0, float(b_copy.get("cantilever_right_m", 0.0)))
        tot_l = round(c_left + sum(raw_spans) + c_right, 3)

        bsx, bsy = float(b_copy.get("start_x", 0.0)), float(b_copy.get("start_y", 0.0))
        bex, bey = float(b_copy.get("end_x", 0.0)), float(b_copy.get("end_y", 0.0))
        b_horiz = abs(bex - bsx) >= abs(bey - bsy)
        b_w = float(b_copy.get("width_m", 0.40))
        b_h = float(b_copy.get("depth_m", 0.30))

        # Beam Self-Weight: w_SW = 25.0 kN/m³ * b * h
        w_sw = round(max(2.5, 25.0 * b_w * b_h), 2)
        sw_eq_str = f"w_SW = 25 × {b_w:.2f} × {b_h:.2f} = {w_sw:.2f} kN/m"
        sup1_world = get_beam_first_support_world_coord(b_copy)

        if b_copy.get("manual_loads_override") and b_copy.get("loads"):
            b_copy["loads"] = [dict(ld) for ld in b_copy["loads"] if not ld.get("is_transferred_reaction")]
        else:
            flags = ensure_beam_wall_flags(story_data, b_copy)
            segments = get_beam_span_segments(b_copy)
            computed_loads: List[Dict[str, Any]] = []
            breakdown_list: List[Dict[str, Any]] = []

            for seg in segments:
                skey = seg["key"]
                sx1, sx2 = float(seg["x1"]), float(seg["x2"])
                w_coord1 = sup1_world + (sx1 - c_left)
                w_coord2 = sup1_world + (sx2 - c_left)
                w_min, w_max = min(w_coord1, w_coord2), max(w_coord1, w_coord2)
                seg_len = max(0.20, w_max - w_min)

                w_slab_seg = 0.0
                slab_tags: List[str] = []
                slab_eq_parts: List[str] = []
                for slb in slabs:
                    if slb.get("is_void", False):
                        continue
                    s_bounds = extract_slab_bounds(slb)
                    if s_bounds is None:
                        continue
                    smin_x, smax_x, smin_y, smax_y = s_bounds
                    lx = max(0.5, smax_x - smin_x)
                    ly = max(0.5, smax_y - smin_y)
                    rib_dir = int(slb.get("rib_direction_deg", 0))
                    is_cant_slb = bool(slb.get("is_cantilever", False))
                    sid_lbl = str(slb.get("id", "S"))

                    if b_horiz and rib_dir == 90:
                        if abs(bsy - smin_y) <= 0.55 or abs(bsy - smax_y) <= 0.55:
                            ov = min(w_max, smax_x) - max(w_min, smin_x)
                            if ov >= min(0.35, seg_len * 0.25):
                                trib_m = ly if is_cant_slb else (ly * 0.50)
                                ratio = min(1.0, ov / seg_len)
                                add_w = round(slab_wu_kpa * trib_m * ratio, 2)
                                w_slab_seg = round(w_slab_seg + add_w, 2)
                                slab_tags.append(f"{sid_lbl}({add_w:.2f})")
                                factor_txt = f"{ly:.2f}m[Cant]" if is_cant_slb else f"({ly:.2f}/2)m"
                                slab_eq_parts.append(f"{sid_lbl}: {slab_wu_kpa:.1f}×{factor_txt}={add_w:.2f}")
                    elif (not b_horiz) and rib_dir == 0:
                        if abs(bsx - smin_x) <= 0.55 or abs(bsx - smax_x) <= 0.55:
                            ov = min(w_max, smax_y) - max(w_min, smin_y)
                            if ov >= min(0.35, seg_len * 0.25):
                                trib_m = lx if is_cant_slb else (lx * 0.50)
                                ratio = min(1.0, ov / seg_len)
                                add_w = round(slab_wu_kpa * trib_m * ratio, 2)
                                w_slab_seg = round(w_slab_seg + add_w, 2)
                                slab_tags.append(f"{sid_lbl}({add_w:.2f})")
                                factor_txt = f"{lx:.2f}m[Cant]" if is_cant_slb else f"({lx:.2f}/2)m"
                                slab_eq_parts.append(f"{sid_lbl}: {slab_wu_kpa:.1f}×{factor_txt}={add_w:.2f}")

                wall_on = bool(flags.get(skey, True))
                w_wall_seg = round(default_wall_w if wall_on else 0.0, 2)
                w_total_seg = round(w_sw + w_slab_seg + w_wall_seg, 2)

                parts = [f"SW={w_sw:.2f}"]
                if w_slab_seg > 0.01:
                    parts.append(f"Slabs[{'+'.join(slab_tags)}]={w_slab_seg:.2f}")
                else:
                    parts.append("Slabs=0.00")
                if w_wall_seg > 0.01:
                    parts.append(f"Wall={w_wall_seg:.2f}")
                else:
                    parts.append("Wall=0.00")
                desc_label = f"{seg['label']}: {' + '.join(parts)} = {w_total_seg:.2f} kN/m"
                formula_detail = (
                    f"w_total = w_SW ({w_sw:.2f}) + w_Slab ({w_slab_seg:.2f}"
                    f"{' [' + '; '.join(slab_eq_parts) + ']' if slab_eq_parts else ''}) + w_Wall ({w_wall_seg:.2f}) = {w_total_seg:.2f} kN/m"
                )

                computed_loads.append({
                    "type": "D",
                    "span_key": skey,
                    "span_label": seg["label"],
                    "x1": round(sx1, 3),
                    "x2": round(sx2, 3),
                    "start": round(sx1, 3),
                    "end": round(sx2, 3),
                    "val": w_total_seg,
                    "mag": w_total_seg,
                    "w_sw": w_sw,
                    "sw_eq": sw_eq_str,
                    "w_slab": w_slab_seg,
                    "slab_eq_parts": slab_eq_parts,
                    "w_wall": w_wall_seg,
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
                orig_beams[idx_b]["loads"] = [dict(x) for x in computed_loads]
                orig_beams[idx_b]["load_breakdown"] = [dict(x) for x in breakdown_list]

        beam_map[bid] = b_copy

    # Topological Sort: Secondary supported beams MUST be solved before the primary carrier beams they rest on!
    ordered_ids: List[str] = []
    visited = set()
    temp_visiting = set()

    # Map carrier_id -> list of secondary beam_ids that rest on carrier_id
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
        # First solve all secondary beams that rest on `bid`
        for sec_id in dependents_on_carrier.get(bid, []):
            visit_with_prereqs(sec_id)
        temp_visiting.remove(bid)
        visited.add(bid)
        ordered_ids.append(bid)

    for b in beams:
        visit_with_prereqs(b["id"])

    beam_results: Dict[str, Dict[str, Any]] = {}
    beam_designs: Dict[str, Dict[str, Any]] = {}

    for bid in ordered_ids:
        bm = beam_map[bid]
        res = solve_continuous_beam_analytical(bm, fc_mpa, fy_mpa)
        res["loads_applied"] = [dict(ld) for ld in bm.get("loads", [])]
        beam_results[bid] = res
        beam_designs[bid] = design_beam_aci318(bm, res, fc_mpa, fy_mpa)

        # Sync updated loads (including transferred point loads) back to story_data["beams"]
        for orig_b in orig_beams:
            if orig_b.get("id") == bid:
                orig_b["loads"] = [dict(ld) for ld in bm.get("loads", [])]
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
                }]

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

        self_wt_kn = round(b_m * h_m * story_h * 25.0 * 1.2, 2)
        story_pu_kn = round(max(45.0, total_beam_reaction_kn) + self_wt_kn, 2)
        col_design = design_column_and_pm_curve(cid, b_m, h_m, story_pu_kn, round(mux_knm, 1), round(muy_knm, 1), fc_mpa, fy_mpa)

        column_records.append({
            "column_id": cid,
            "x": cx,
            "y": cy,
            "b_m": b_m,
            "h_m": h_m,
            "story_pu_kn": story_pu_kn,
            "mux_knm": round(mux_knm, 2),
            "muy_knm": round(muy_knm, 2),
            "framing_4way": framing_directions,
            "design": col_design,
        })

    return {
        "ordered_beam_ids": ordered_ids,
        "beam_results": beam_results,
        "beam_designs": beam_designs,
        "column_records": column_records,
    }


def design_beam_aci318(
    beam: Dict[str, Any],
    analysis_res: Dict[str, Any],
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
) -> Dict[str, Any]:
    """
    Designs a reinforced concrete Hidden or Drop beam per ACI 318 (matching Eng. Yousef's methodology),
    including detailed per-span bottom reinforcement, per-support top reinforcement, and stirrup zones
    for longitudinal section detailing and multi-span schedules.
    """
    b_mm = float(beam.get("width_m", 0.30)) * 1000.0
    h_mm = float(beam.get("depth_m", 0.30)) * 1000.0
    d_mm = max(120.0, h_mm - 45.0)

    pos_mu = float(analysis_res.get("max_pos_mu_knm", 0.0))
    neg_mu = abs(float(analysis_res.get("max_neg_face_mu_knm", 0.0)))
    vu_kn = float(analysis_res.get("max_face_vu_kn", 0.0))

    def calc_ast(mu_knm: float) -> Tuple[float, int, str]:
        as_min = max(0.25 * math.sqrt(fc_mpa) / fy_mpa, 1.4 / fy_mpa) * b_mm * d_mm
        if abs(mu_knm) <= 0.1:
            ast = as_min
        else:
            rn = (abs(mu_knm) * 1e6) / (0.90 * b_mm * (d_mm ** 2))
            term = max(0.05, 1.0 - (2.0 * rn) / (0.85 * fc_mpa))
            rho = (0.85 * fc_mpa / fy_mpa) * (1.0 - math.sqrt(term))
            ast = max(as_min, rho * b_mm * d_mm)
        area_16 = 201.06
        min_bars = 4 if b_mm >= 350 else (3 if b_mm >= 250 else 2)
        n_bars = max(min_bars, math.ceil(ast / area_16))
        return round(ast, 1), n_bars, f"{n_bars} Φ 16 mm"

    def calc_stirrups(v_kn: float) -> str:
        vc = (0.17 * math.sqrt(fc_mpa) * b_mm * d_mm) / 1000.0
        p_vc = 0.75 * vc
        n_legs = 4 if b_mm >= 350 else 2
        if v_kn <= p_vc:
            return f"Φ 8 @ 180 mm ({n_legs}-Legs)"
        elif v_kn <= p_vc * 1.6:
            return f"Φ 8 @ 140 mm ({n_legs}-Legs)"
        else:
            return f"Φ 10 @ 110 mm ({n_legs}-Legs)"

    ast_bot, n_bot, bars_bot = calc_ast(pos_mu)
    ast_top, n_top, bars_top = calc_ast(neg_mu)

    vc_kn = (0.17 * math.sqrt(fc_mpa) * b_mm * d_mm) / 1000.0
    phi_vc = 0.75 * vc_kn
    stirrups = calc_stirrups(vu_kn)

    spans = analysis_res.get("spans", beam.get("spans", [4.0]))
    sup_table = analysis_res.get("support_critical_table", [])
    span_pos_list = analysis_res.get("span_positive_moments", [])

    support_designs = []
    for sup in sup_table:
        m_neg = abs(float(sup.get("face_neg_mu_knm", 0.0)))
        v_f = float(sup.get("face_vu_kn", 0.0))
        a_t, nb_t, b_str = calc_ast(m_neg)
        support_designs.append({
            "support_index": sup.get("support_index", 1),
            "target_id": sup.get("target_id", "C1"),
            "x_m": sup.get("x_m", 0.0),
            "reaction_ru_kn": sup.get("reaction_ru_kn", 0.0),
            "face_neg_mu_knm": sup.get("face_neg_mu_knm", 0.0),
            "face_vu_kn": v_f,
            "top_ast_mm2": a_t,
            "top_n_bars": nb_t,
            "top_bars": b_str,
            "stirrups_end": calc_stirrups(v_f),
        })

    span_designs = []
    for idx, sp_info in enumerate(span_pos_list):
        m_pos = float(sp_info.get("max_pos_mu_knm", 0.0))
        v_sp = float(sp_info.get("max_abs_vu_kn", 0.0))
        a_b, nb_b, b_str = calc_ast(m_pos)
        left_sup = support_designs[idx] if idx < len(support_designs) else None
        right_sup = support_designs[idx + 1] if (idx + 1) < len(support_designs) else None
        neg_ctrl = max(
            abs(float(left_sup["face_neg_mu_knm"])) if left_sup else 0.0,
            abs(float(right_sup["face_neg_mu_knm"])) if right_sup else 0.0,
        )
        a_t_sp, nb_t_sp, b_top_sp = calc_ast(neg_ctrl)
        span_designs.append({
            "span_index": idx + 1,
            "zone_label": f"Span {idx + 1}",
            "length_m": sp_info.get("length_m", spans[idx] if idx < len(spans) else 4.0),
            "start_x_m": sp_info.get("start_x_m", 0.0),
            "end_x_m": sp_info.get("end_x_m", 4.0),
            "pos_mu_knm": m_pos,
            "at_x_m": sp_info.get("at_x_m", 2.0),
            "bottom_ast_mm2": a_b,
            "bottom_n_bars": nb_b,
            "bottom_bars": b_str,
            "neg_mu_knm": round(-neg_ctrl, 2),
            "top_ast_mm2": a_t_sp,
            "top_n_bars": nb_t_sp,
            "top_bars": b_top_sp,
            "max_vu_kn": v_sp,
            "stirrups": calc_stirrups(v_sp),
        })

    return {
        "beam_id": beam.get("id", "B1"),
        "beam_kind": beam.get("beam_kind", "hidden"),
        "num_spans": len(spans),
        "cantilever_left_m": float(beam.get("cantilever_left_m", 0.0)),
        "cantilever_right_m": float(beam.get("cantilever_right_m", 0.0)),
        "b_mm": round(b_mm),
        "h_mm": round(h_mm),
        "d_mm": round(d_mm),
        "bottom_ast_mm2": ast_bot,
        "bottom_n_bars": n_bot,
        "bottom_bars": bars_bot,
        "top_ast_mm2": ast_top,
        "top_n_bars": n_top,
        "top_bars": bars_top,
        "phi_vc_kn": round(phi_vc, 1),
        "stirrups": stirrups,
        "span_designs": span_designs,
        "support_designs": support_designs,
    }


def design_column_and_pm_curve(
    column_id: str,
    b_m: float,
    h_m: float,
    pu_kn: float,
    mux_knm: float,
    muy_knm: float,
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
) -> Dict[str, Any]:
    """
    Designs column per ACI 318 and generates P-M Interaction Diagram envelope points.
    """
    b_mm = round(b_m * 1000.0)
    h_mm = round(h_m * 1000.0)
    ag = b_mm * h_mm
    ast_req = max(0.01 * ag, ((pu_kn * 1000.0) / (0.65 * 0.80) - 0.85 * fc_mpa * ag) / (fy_mpa - 0.85 * fc_mpa))
    n_bars = max(6, math.ceil(ast_req / 201.06 / 2.0) * 2)
    ast_prov = n_bars * 201.06

    phi_pn_max = 0.65 * 0.80 * (0.85 * fc_mpa * (ag - ast_prov) + fy_mpa * ast_prov) / 1000.0
    phi_pb = 0.42 * phi_pn_max
    phi_mb = (0.65 * (0.22 * fc_mpa * b_mm * (h_mm ** 2) + fy_mpa * ast_prov * 0.35 * h_mm)) / 1e6
    phi_m0 = 0.90 * (fy_mpa * ast_prov * 0.40 * h_mm) / 1e6

    pm_curve_points = [
        {"m_knm": 0.0, "p_kn": round(phi_pn_max, 1)},
        {"m_knm": round(phi_mb * 0.55, 1), "p_kn": round(phi_pn_max * 0.85, 1)},
        {"m_knm": round(phi_mb, 1), "p_kn": round(phi_pb, 1)},
        {"m_knm": round(phi_m0, 1), "p_kn": 0.0},
    ]

    return {
        "column_id": column_id,
        "section_mm": f"{b_mm} x {h_mm} mm",
        "chosen_bars": f"{n_bars} Phi 16 mm",
        "rho_pct": round((ast_prov / ag) * 100.0, 2),
        "phi_pn_max_kn": round(phi_pn_max, 1),
        "phi_mb_knm": round(phi_mb, 1),
        "pm_curve_points": pm_curve_points,
        "status": "SAFE" if pu_kn <= phi_pn_max else "INCREASE SECTION",
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
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validates strict Revit-style structural beam rules:
    1. Outer Slab Boundary (Polyline) must exist.
    2. Full Outer-Face Column Bearing: When a user clicks the center of a start column and
       an end column, the physical beam automatically extends from the OUTER FACE of the first
       column to the OUTER FACE of the last column (`sx = cx1 - b1/2` to `ex = cx2 + b2/2`),
       so the beam never stops awkwardly at the column center!
    3. Full-Width Beam Boundary Shift: If the beam's lateral outer face (+/- width_m / 2)
       protrudes outside the building boundary, the beam axis is automatically shifted inward so its
       outer face sits 100% flush with the building boundary.
    4. Duplicate Overlapping Beam Prevention: Rejects drawing a beam on top of an existing collinear beam.
    5. Continuous Multi-Span Recognition from 2 Clicks: Automatically detects all intermediate columns/beams.
    6. Cantilever Overhang Validation: Overhang beyond the outer face of the end column is valid ONLY if its tip
       is a Free End at the building perimeter.
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(slab_edge_polygon)
    if not has_bnd:
        return False, None, "Draw the Outer Building Boundary Polyline (00-XD-EDGE) first before drawing beams."

    active_cols = [c for c in columns if c.get("active", True)]
    if not active_cols:
        return False, None, "Place or import Structural Columns (00-XD-COL) before drawing beams."

    sx, sy = round(float(start_pt[0]), 3), round(float(start_pt[1]), 3)
    ex, ey = round(float(end_pt[0]), 3), round(float(end_pt[1]), 3)

    tol = 0.35
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
        clamped_y = min(max(sy, min_y + half_w), max_y - half_w)
        if abs(clamped_y - sy) > 1e-4:
            shifted_note = f" [Shifted beam axis Y from {sy:.2f}m to {clamped_y:.2f}m so full width ({width_m:.2f}m) stays inside building boundary]"
            sy = ey = round(clamped_y, 3)
    else:
        ex = sx
        if sy > ey:
            sy, ey = ey, sy
        is_horizontal = False
        clamped_x = min(max(sx, min_x + half_w), max_x - half_w)
        if abs(clamped_x - sx) > 1e-4:
            shifted_note = f" [Shifted beam axis X from {sx:.2f}m to {clamped_x:.2f}m so full width ({width_m:.2f}m) stays inside building boundary]"
            sx = ex = round(clamped_x, 3)

    # Discover all supporting columns and perpendicular beams along the beam path
    # Rule: If ANY part of a column's rectangular cross-section [cx-b/2, cx+b/2] x [cy-h/2, cy+h/2]
    # touches or overlaps the beam's physical footprint (or is within snap tolerance), that column
    # acts as a valid support for the beam while keeping the beam strictly orthogonal (0° or 90°)!
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
        if is_horizontal and not ob_horiz:
            bx = osx
            if (sx - 0.28) <= bx <= (ex + 0.28) and min(osy, oey) - 0.28 <= sy <= max(osy, oey) + 0.28:
                if not any(abs(s["coord"] - bx) < 0.30 for s in supports_raw):
                    supports_raw.append({
                        "coord": bx,
                        "x": bx,
                        "y": sy,
                        "kind": "beam",
                        "target_id": ob["id"],
                        "width_m": float(ob.get("width_m", 0.30)),
                        "depth_m": float(ob.get("depth_m", 0.30)),
                        "pos_on_carrier_m": round(abs(sy - min(osy, oey)), 3),
                    })
        elif not is_horizontal and ob_horiz:
            by = osy
            if (sy - 0.28) <= by <= (ey + 0.28) and min(osx, oex) - 0.28 <= sx <= max(osx, oex) + 0.28:
                if not any(abs(s["coord"] - by) < 0.30 for s in supports_raw):
                    supports_raw.append({
                        "coord": by,
                        "x": sx,
                        "y": by,
                        "kind": "beam",
                        "target_id": ob["id"],
                        "width_m": float(ob.get("width_m", 0.30)),
                        "depth_m": float(ob.get("depth_m", 0.30)),
                        "pos_on_carrier_m": round(abs(sx - min(osx, oex)), 3),
                    })

    supports_raw.sort(key=lambda s: s["coord"])
    if len(supports_raw) == 0:
        return False, None, "Beam must rest on at least one Column or Supporting Beam."

    # REVIT FULL-COLUMN-FACE EXTENSION + STRICT BOUNDARY CLAMPING:
    # Extend the physical beam start/end across the full width/depth of the first and last support,
    # and strictly clamp within [min_x, max_x] x [min_y, max_y] so no beam ever protrudes outside the slab boundary!
    first_sup = supports_raw[0]
    last_sup = supports_raw[-1]
    first_outer_edge = round(first_sup["coord"] - float(first_sup["width_m"]) / 2.0, 3)
    last_outer_edge = round(last_sup["coord"] + float(last_sup["width_m"]) / 2.0, 3)

    if is_horizontal:
        if sx >= first_outer_edge - 0.05 and abs(sx - first_sup["coord"]) <= float(first_sup["width_m"]) + 0.30:
            sx = max(min_x, first_outer_edge)
        if ex <= last_outer_edge + 0.05 and abs(ex - last_sup["coord"]) <= float(last_sup["width_m"]) + 0.30:
            ex = min(max_x, last_outer_edge)
        sx = round(min(max(sx, min_x), max_x), 3)
        ex = round(min(max(ex, min_x), max_x), 3)
        sy = ey = round(min(max(sy, min_y + half_w), max_y - half_w), 3)
    else:
        if sy >= first_outer_edge - 0.05 and abs(sy - first_sup["coord"]) <= float(first_sup["width_m"]) + 0.30:
            sy = max(min_y, first_outer_edge)
        if ey <= last_outer_edge + 0.05 and abs(ey - last_sup["coord"]) <= float(last_sup["width_m"]) + 0.30:
            ey = min(max_y, last_outer_edge)
        sy = round(min(max(sy, min_y), max_y), 3)
        ey = round(min(max(ey, min_y), max_y), 3)
        sx = ex = round(min(max(sx, min_x + half_w), max_x - half_w), 3)

    total_len = round(math.hypot(ex - sx, ey - sy), 3)
    if total_len < 0.40:
        return False, None, "Beam length is too short (< 0.40 m)."

    # Prevent Duplicate Overlapping Beams along the same axis
    for ob in existing_beams:
        if ob.get("id") == beam_id:
            continue
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        ob_horiz = abs(oex - osx) >= abs(oey - osy)
        if is_horizontal and ob_horiz and abs(sy - osy) <= 0.25:
            ov = min(ex, max(osx, oex)) - max(sx, min(osx, oex))
            if ov > 0.35:
                return False, None, f"Duplicate Beam Prevented: Overlaps existing horizontal beam {ob['id']}."
        elif (not is_horizontal) and (not ob_horiz) and abs(sx - osx) <= 0.25:
            ov = min(ey, max(osy, oey)) - max(sy, min(osy, oey))
            if ov > 0.35:
                return False, None, f"Duplicate Beam Prevented: Overlaps existing vertical beam {ob['id']}."

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

    edge_margin = 0.45
    if cant_left > 0.35:
        tip_at_boundary = (abs(sx - min_x) <= edge_margin) if is_horizontal else (abs(sy - min_y) <= edge_margin)
        if not tip_at_boundary:
            return (
                False,
                None,
                f"Invalid Interior Cantilever: Left overhang ({cant_left:.2f} m) ends inside the slab at ({sx:.2f}, {sy:.2f}). "
                "A cantilever must terminate at a free outer slab boundary edge or rest on a support.",
            )
    if cant_right > 0.35:
        tip_at_boundary = (abs(ex - max_x) <= edge_margin) if is_horizontal else (abs(ey - max_y) <= edge_margin)
        if not tip_at_boundary:
            return (
                False,
                None,
                f"Invalid Interior Cantilever: Right overhang ({cant_right:.2f} m) ends inside the slab at ({ex:.2f}, {ey:.2f}). "
                "A cantilever must terminate at a free outer slab boundary edge or rest on a support.",
            )

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
        f"Beam {beam_id} created ({len(spans)} span(s) [{', '.join(f'{s:.2f}m' for s in spans)}] over {sup_names}, full outer-column bearing [{sx:.2f},{sy:.2f}]->[{ex:.2f},{ey:.2f}]).{shifted_note}",
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
        is_seg_horiz = abs(x2 - x1) >= abs(y2 - y1)
        seg_len = max(0.10, abs(x2 - x1) if is_seg_horiz else abs(y2 - y1))
        for bm in beams:
            bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
            b_width = float(bm.get("width_m", 0.40))
            tol_lat = max(0.48, b_width + 0.15)
            b_horiz = abs(bex - bsx) >= abs(bey - bsy)
            if is_seg_horiz and b_horiz and abs(bsy - y1) <= tol_lat:
                ov = min(max(bsx, bex) + 0.35, max(x1, x2)) - max(min(bsx, bex) - 0.35, min(x1, x2))
                if ov >= seg_len * 0.65:
                    return bm
            elif (not is_seg_horiz) and (not b_horiz) and abs(bsx - x1) <= tol_lat:
                ov = min(max(bsy, bey) + 0.35, max(y1, y2)) - max(min(bsy, bey) - 0.35, min(y1, y2))
                if ov >= seg_len * 0.65:
                    return bm
        return None

    def has_poly_edge_on_segment(x1: float, y1: float, x2: float, y2: float) -> bool:
        is_seg_horiz = abs(x2 - x1) >= abs(y2 - y1)
        seg_len = max(0.10, abs(x2 - x1) if is_seg_horiz else abs(y2 - y1))
        n = len(poly)
        for idx in range(n):
            px1, py1 = float(poly[idx][0]), float(poly[idx][1])
            px2, py2 = float(poly[(idx + 1) % n][0]), float(poly[(idx + 1) % n][1])
            p_horiz = abs(px2 - px1) >= abs(py2 - py1)
            if is_seg_horiz and p_horiz and abs(py1 - y1) <= 0.35:
                ov = min(max(px1, px2) + 0.25, max(x1, x2)) - max(min(px1, px2) - 0.25, min(x1, x2))
                if ov >= seg_len * 0.65:
                    return True
            elif (not is_seg_horiz) and (not p_horiz) and abs(px1 - x1) <= 0.35:
                ov = min(max(py1, py2) + 0.25, max(y1, y2)) - max(min(py1, py2) - 0.25, min(y1, y2))
                if ov >= seg_len * 0.65:
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
    # (meaning there is NO bay on the free side, while an interior back-span bay exists on the opposite side).
    cols = [c for c in story_data.get("columns", []) if c.get("active", True)]
    tmin_x, tmax_x = float(target_bay["min_x"]), float(target_bay["max_x"])
    tmin_y, tmax_y = float(target_bay["min_y"]), float(target_bay["max_y"])
    lx, ly = float(target_bay["lx_m"]), float(target_bay["ly_m"])

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
            not has_col_near_edge(tmin_x, tmin_y, tmax_x, tmin_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "North")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "South")
        ):
            return "South"
        if (
            not has_col_near_edge(tmin_x, tmax_y, tmax_x, tmax_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "South")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "North")
        ):
            return "North"
    if lx <= 2.60:
        if (
            not has_col_near_edge(tmax_x, tmin_y, tmax_x, tmax_y)
            and not _find_adjacent_backspan_bays(target_bay, all_bays, "West")
            and _find_adjacent_backspan_bays(target_bay, all_bays, "East")
        ):
            return "East"
        if (
            not has_col_near_edge(tmin_x, tmin_y, tmin_x, tmax_y)
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
    if `target_bay` is currently acting as the back-span extension (`بلاطة امتداد الكابولي`) for any
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
                if (omin_x - 0.15) <= bcx <= (omax_x + 0.15) and (omin_y - 0.15) <= bcy <= (omax_y + 0.15):
                    if b["beam_count"] >= 3:
                        matching_bays.append(b)

            if len(matching_bays) > 1:
                split_count += len(matching_bays)

            for mb in matching_bays:
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
                reconciled_slabs.append({
                    "id": f"S{len(reconciled_slabs) + 1}",
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


def auto_fill_all_story_slabs(story_data: Dict[str, Any]) -> Tuple[int, str]:
    """
    1-Click Productivity Tool: Automatically populates all closed beam-bounded bays (>= 3 beams)
    that are not Void Openings with Hollow-Block Slabs using optimal default rib directions
    and enforces Cantilever Back-Span continuity.
    """
    bays = detect_story_grid_bays(story_data)
    if not bays:
        return 0, "Draw Building Boundary and Beams first before Auto-Filling Slabs."

    open_keys = {o.get("bay_key") for o in story_data.get("openings", [])}
    created = 0
    for b in bays:
        if b["beam_count"] >= 3 and b["bay_key"] not in open_keys:
            cx = (b["min_x"] + b["max_x"]) / 2.0
            cy = (b["min_y"] + b["max_y"]) / 2.0
            ok, _, _ = pick_area_create_or_update_slab(story_data, cx, cy, target_mode="SLAB")
            if ok:
                created += 1

    # Renumber sequentially S1..Sn
    for idx, s in enumerate(story_data.get("slabs", [])):
        s["id"] = f"S{idx + 1}"

    return created, f"Auto-Generated {created} Slab bay(s) across the story."


def rotate_column_90_deg(story_data: Dict[str, Any], column_id: str, boundary_mode: str = "clamp") -> Tuple[bool, str]:
    """
    Rotates a selected column by 90 degrees (swapping b_m and h_m, e.g. 0.20x0.40 <-> 0.40x0.20),
    re-clamps it safely inside the building boundary (without ever crashing), and updates connected
    beams' support widths while keeping all beams 100% strictly orthogonal (never skewed/slanted)
    and strictly inside the slab boundary!
    """
    cols = story_data.get("columns", [])
    target = next((c for c in cols if c.get("id") == column_id), None)
    if not target:
        return False, f"Column {column_id} not found."
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
    Handles the 'Pick Area' tool for creating/toggling Slabs (00-XD-SLAB) and Openings (00-XD-OPEN),
    implementing Eng. Yousef's exact structural rules + Bidirectional Cantilever Back-Span Continuity:
    1. True Physical Bay Detection (never split by neighboring bays' partial beams).
    2. Strict Dynamic Cantilever Back-Span Equilibrium Lock (`بلاطة امتداد الكابولي`):
       - Whenever a Cantilever Slab (e.g. S4) has its ribs oriented perpendicular to its interior carrier beam,
         the adjacent Back-Span Slab (e.g. S3) is automatically aligned to the same rib direction AND strictly
         locked against flipping unless S4's ribs are first flipped onto two side beams (0°/90°) or S4 is deleted!
    """
    bays = detect_story_grid_bays(story_data)
    if not bays:
        return False, "Draw Outer Slab Boundary and Beams first before using Pick Area.", None

    target_bay = None
    for b in bays:
        if b["min_x"] <= click_x <= b["max_x"] and b["min_y"] <= click_y <= b["max_y"]:
            target_bay = b
            break

    if not target_bay:
        return False, f"Clicked point ({click_x:.2f}, {click_y:.2f}) is outside bounded slab bays.", None

    beam_count = target_bay["beam_count"]
    if beam_count < 3:
        return (
            False,
            f"Selected region is bounded by only {beam_count} beam(s). At least 3 bounding beams are required to pick a Slab or Opening.",
            None,
        )

    slabs: List[Dict[str, Any]] = story_data.setdefault("slabs", [])
    openings: List[Dict[str, Any]] = story_data.setdefault("openings", [])
    bay_key = target_bay["bay_key"]

    existing_slab = next((s for s in slabs if s.get("bay_key") == bay_key), None)
    if existing_slab is None:
        # Also match by center coordinate in case bay_key changed after a beam edit
        tcx = (target_bay["min_x"] + target_bay["max_x"]) / 2.0
        tcy = (target_bay["min_y"] + target_bay["max_y"]) / 2.0
        for s in slabs:
            if "min_x" in s and float(s["min_x"]) <= tcx <= float(s["max_x"]) and float(s["min_y"]) <= tcy <= float(s["max_y"]):
                existing_slab = s
                existing_slab["bay_key"] = bay_key
                break

    existing_open = next((o for o in openings if o.get("bay_key") == bay_key), None)

    # Dynamic check: Does an existing adjacent Cantilever Slab rely on `target_bay` as its back-span (`بلاطة امتداد الكابولي`)?
    controlling_cantilevers = _find_controlling_cantilever_slabs_for_bay(story_data, target_bay, bays)
    controlling_cantilever_slab = controlling_cantilevers[0] if controlling_cantilevers else None

    # Toggle Slab <-> Opening if requested
    if target_mode == "TOGGLE_OPENING" or (target_mode == "OPENING"):
        if existing_open and target_mode == "TOGGLE_OPENING":
            openings.remove(existing_open)
            target_mode = "SLAB"
        else:
            if controlling_cantilever_slab is not None:
                return (
                    False,
                    f"Cannot convert {bay_key} to an Opening because Cantilever Slab {controlling_cantilever_slab['id']} depends on it for back-span continuity!",
                    None,
                )
            if existing_slab:
                slabs.remove(existing_slab)
            if not existing_open:
                new_open = {
                    "id": f"OP{len(openings) + 1}",
                    "bay_key": bay_key,
                    "min_x": target_bay["min_x"],
                    "max_x": target_bay["max_x"],
                    "min_y": target_bay["min_y"],
                    "max_y": target_bay["max_y"],
                }
                openings.append(new_open)
                return True, f"Bay {bay_key} set as Void Opening ({new_open['id']}).", new_open
            return True, f"Bay {bay_key} is already an Opening.", existing_open

    if existing_open:
        openings.remove(existing_open)

    sides = target_bay["bounding_beams"]
    lx, ly = target_bay["lx_m"], target_bay["ly_m"]

    cant_free_side = _detect_cantilever_free_side(story_data, target_bay, bays)
    cant_perp_dir: Optional[int] = None
    if cant_free_side in ("South", "North"):
        cant_perp_dir = 90
    elif cant_free_side in ("East", "West"):
        cant_perp_dir = 0

    if controlling_cantilever_slab is not None:
        default_dir = int(controlling_cantilever_slab.get("rib_direction_deg", 90))
    elif cant_free_side is not None and cant_perp_dir is not None:
        adj_back_bays = _find_adjacent_backspan_bays(target_bay, bays, cant_free_side)
        cant_span_len = ly if cant_perp_dir == 90 else lx
        if adj_back_bays and cant_span_len <= 2.60:
            default_dir = cant_perp_dir
        elif beam_count == 3:
            default_dir = 0 if (sides["West"] is not None and sides["East"] is not None) else 90
        else:
            default_dir = 0 if lx <= ly else 90
    elif beam_count == 4:
        default_dir = 0 if lx <= ly else 90
    else:
        if sides["West"] is not None and sides["East"] is not None:
            default_dir = 0
        else:
            default_dir = 90

    if requested_rib_dir_deg is not None:
        chosen_dir = requested_rib_dir_deg
    elif existing_slab is not None and target_mode == "FLIP_RIB":
        chosen_dir = 90 if int(existing_slab.get("rib_direction_deg", default_dir)) == 0 else 0
    elif existing_slab is not None:
        chosen_dir = int(existing_slab.get("rib_direction_deg", default_dir))
    else:
        chosen_dir = default_dir

    # STRICT RULE 1: If this bay is the back-span (`بلاطة امتداد الكابولي`) of an active Cantilever Slab,
    # it CANNOT be flipped perpendicular to the cantilever unless the cantilever slab itself is first flipped
    # onto two side drop beams or deleted!
    if controlling_cantilever_slab is not None:
        req_c_dir = int(controlling_cantilever_slab.get("rib_direction_deg", 90))
        if chosen_dir != req_c_dir:
            if target_mode == "FLIP_RIB" or requested_rib_dir_deg is not None:
                alt_dir = 0 if req_c_dir == 90 else 90
                return (
                    False,
                    f"Cantilever Back-Span Lock (قفل بلاطة امتداد الكابولي): Slab {existing_slab['id'] if existing_slab else bay_key} "
                    f"is the back-span extension for Cantilever Slab {controlling_cantilever_slab['id']} ({req_c_dir}°). "
                    f"Its ribs CANNOT be changed unless {controlling_cantilever_slab['id']} is first flipped to {alt_dir}° (on two side beams) or deleted!",
                    existing_slab,
                )
            chosen_dir = req_c_dir

    # STRICT RULE 2: If this bay is a cantilever bay and the user wants to flip it parallel to the free edge
    # (`chosen_dir != cant_perp_dir`), verify that two opposite side beams exist to carry the ribs!
    if cant_free_side is not None and cant_perp_dir is not None and chosen_dir != cant_perp_dir:
        has_side_beams = (
            (sides.get("West") is not None and sides.get("East") is not None)
            if chosen_dir == 0
            else (sides.get("North") is not None and sides.get("South") is not None)
        )
        if not has_side_beams:
            return (
                False,
                f"Cantilever Support Error: Slab cannot be oriented at {chosen_dir}° because it lacks two opposite side beams to carry the ribs!",
                existing_slab,
            )

    is_cantilever = False
    backspan_bay_key: Optional[str] = None
    backspan_bay_keys: List[str] = []
    continuity_note = ""

    # If this bay is oriented as a cantilever toward its free/overhang edge, automatically align all back-span slabs across the carrier beam!
    if cant_free_side is not None and chosen_dir == cant_perp_dir:
        adj_bays = _find_adjacent_backspan_bays(target_bay, bays, cant_free_side)
        if not adj_bays and beam_count == 3:
            return (
                False,
                "Cantilever Equilibrium Error: Cannot orient 3-beam slab as a cantilever because there is no back-span bay behind the supporting beam.",
                None,
            )
        if adj_bays:
            for ab in adj_bays:
                b_k = ab["bay_key"]
                if any(o.get("bay_key") == b_k for o in openings):
                    return (
                        False,
                        f"Cantilever Equilibrium Error: Adjacent back-span bay ({b_k}) is a Void Opening! "
                        "A cantilever slab requires a continuous solid/ribbed back-span slab in the same direction.",
                        None,
                    )

            is_cantilever = True
            backspan_bay_key = adj_bays[0]["bay_key"]
            backspan_bay_keys = [ab["bay_key"] for ab in adj_bays]
            aligned_ids: List[str] = []

            for adj_bay in adj_bays:
                b_k = adj_bay["bay_key"]
                adj_slab = next((s for s in slabs if s.get("bay_key") == b_k), None)
                adj_axis_span = adj_bay["lx_m"] if chosen_dir == 0 else adj_bay["ly_m"]
                if adj_slab is None:
                    adj_slab = {
                        "id": f"S{len(slabs) + 1}",
                        "bay_key": b_k,
                        "min_x": adj_bay["min_x"],
                        "max_x": adj_bay["max_x"],
                        "min_y": adj_bay["min_y"],
                        "max_y": adj_bay["max_y"],
                        "clear_min_x": adj_bay.get("clear_min_x", adj_bay["min_x"]),
                        "clear_max_x": adj_bay.get("clear_max_x", adj_bay["max_x"]),
                        "clear_min_y": adj_bay.get("clear_min_y", adj_bay["min_y"]),
                        "clear_max_y": adj_bay.get("clear_max_y", adj_bay["max_y"]),
                        "lx_m": adj_bay["lx_m"],
                        "ly_m": adj_bay["ly_m"],
                        "rib_direction_deg": chosen_dir,
                        "axis_span_m": adj_axis_span,
                        "left_support_w_m": 0.30,
                        "right_support_w_m": 0.30,
                        "is_cantilever": False,
                        "connected_to_cantilever": True,
                    }
                    slabs.append(adj_slab)
                else:
                    adj_slab["rib_direction_deg"] = chosen_dir
                    adj_slab["axis_span_m"] = adj_axis_span
                    adj_slab["connected_to_cantilever"] = True
                aligned_ids.append(str(adj_slab["id"]))

            continuity_note = (
                f" [Cantilever Slab: Back-span {', '.join(aligned_ids)} automatically rotated to {chosen_dir}° & locked for equilibrium]"
            )
    elif cant_free_side is not None and chosen_dir != cant_perp_dir:
        # User flipped the cantilever bay to rest on its two side beams! Unlock its former back-span slabs!
        adj_bays = _find_adjacent_backspan_bays(target_bay, bays, cant_free_side)
        unlocked_ids: List[str] = []
        for adj_bay in adj_bays:
            b_k = adj_bay["bay_key"]
            adj_slab = next((s for s in slabs if s.get("bay_key") == b_k), None)
            if adj_slab is not None:
                adj_slab["connected_to_cantilever"] = False
                unlocked_ids.append(str(adj_slab["id"]))
        if unlocked_ids:
            continuity_note = f" [Resting on Side Beams: Back-span {', '.join(unlocked_ids)} is now unlocked and can be flipped freely]"

    axis_span_m = lx if chosen_dir == 0 else ly
    if existing_slab:
        existing_slab.update({
            "min_x": target_bay["min_x"],
            "max_x": target_bay["max_x"],
            "min_y": target_bay["min_y"],
            "max_y": target_bay["max_y"],
            "clear_min_x": target_bay.get("clear_min_x", target_bay["min_x"]),
            "clear_max_x": target_bay.get("clear_max_x", target_bay["max_x"]),
            "clear_min_y": target_bay.get("clear_min_y", target_bay["min_y"]),
            "clear_max_y": target_bay.get("clear_max_y", target_bay["max_y"]),
            "lx_m": lx,
            "ly_m": ly,
            "rib_direction_deg": chosen_dir,
            "axis_span_m": axis_span_m,
            "is_cantilever": is_cantilever,
            "cantilever_free_edge": cant_free_side if is_cantilever else None,
            "connected_to_cantilever": bool(controlling_cantilever_slab is not None),
            "backspan_bay_key": backspan_bay_key,
            "backspan_bay_keys": backspan_bay_keys,
        })
        slab_obj = existing_slab
    else:
        slab_obj = {
            "id": f"S{len(slabs) + 1}",
            "bay_key": bay_key,
            "min_x": target_bay["min_x"],
            "max_x": target_bay["max_x"],
            "min_y": target_bay["min_y"],
            "max_y": target_bay["max_y"],
            "clear_min_x": target_bay.get("clear_min_x", target_bay["min_x"]),
            "clear_max_x": target_bay.get("clear_max_x", target_bay["max_x"]),
            "clear_min_y": target_bay.get("clear_min_y", target_bay["min_y"]),
            "clear_max_y": target_bay.get("clear_max_y", target_bay["max_y"]),
            "lx_m": lx,
            "ly_m": ly,
            "rib_direction_deg": chosen_dir,
            "axis_span_m": axis_span_m,
            "left_support_w_m": 0.30,
            "right_support_w_m": 0.30,
            "is_cantilever": is_cantilever,
            "cantilever_free_edge": cant_free_side if is_cantilever else None,
            "connected_to_cantilever": bool(controlling_cantilever_slab is not None),
            "backspan_bay_key": backspan_bay_key,
            "backspan_bay_keys": backspan_bay_keys,
        }
        slabs.append(slab_obj)

    if controlling_cantilever_slab is not None and not continuity_note:
        continuity_note = (
            f" [Back-Span Continuity: Automatically aligned to {chosen_dir}° to balance Cantilever Slab {controlling_cantilever_slab['id']}]"
        )

    return (
        True,
        f"Slab {slab_obj['id']} ({lx:.2f}×{ly:.2f} m) set with Rib Direction = {chosen_dir}°.{continuity_note}",
        slab_obj,
    )


def toggle_slab_rib_by_label_click(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    hit_radius_m: float = 0.75,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Checks if the user clicked near any Slab's center rib label/arrow on the canvas (or inside the slab).
    If so, flips its rib direction (0 deg <-> 90 deg) while strictly enforcing
    cantilever & back-span continuity rules!
    """
    for slb in story_data.get("slabs", []):
        if "min_x" not in slb:
            continue
        smin_x, smax_x = float(slb["min_x"]), float(slb["max_x"])
        smin_y, smax_y = float(slb["min_y"]), float(slb["max_y"])
        cx = (smin_x + smax_x) / 2.0
        cy = (smin_y + smax_y) / 2.0
        if math.hypot(click_x - cx, click_y - cy) <= hit_radius_m or (
            smin_x <= click_x <= smax_x and smin_y <= click_y <= smax_y
        ):
            return pick_area_create_or_update_slab(story_data, cx, cy, target_mode="FLIP_RIB")
    return False, "", None


def delete_selected_element_from_story(
    story_data: Dict[str, Any],
    kind: str,
    element_id: str,
) -> Tuple[bool, str]:
    """
    Crash-proof universal deletion algorithm for any selected object (`column`, `beam`, `slab`, `opening`,
    `dimension`, or `slab_edge`) from `story_data`:
    - When deleting a Beam `B_del` that has secondary beams resting on it:
      automatically cleans up support references & transferred point loads in those secondary beams
      and recalculates their spans safely so the app NEVER crashes!
    - When deleting a Slab `S_del`: removes `S_del` cleanly and clears any stale cantilever links on adjacent slabs.
    - When deleting a Dimension `D_del`: removes `D_del` cleanly.
    """
    try:
        eid = str(element_id)
        if kind == "column":
            cols = story_data.get("columns", [])
            before = len(cols)
            story_data["columns"] = [c for c in cols if str(c.get("id")) != eid]
            if len(story_data["columns"]) < before:
                # Clean up column support references in beams safely
                for bm in story_data.get("beams", []):
                    sups = [s for s in bm.get("supports", []) if not (s.get("kind") == "column" and str(s.get("target_id")) == eid)]
                    for idx_s, s_obj in enumerate(sups):
                        s_obj["support_index"] = idx_s + 1
                    bm["supports"] = sups
                return True, f"Deleted Column {eid}."

        elif kind == "beam":
            beams = story_data.get("beams", [])
            before = len(beams)
            story_data["beams"] = [b for b in beams if str(b.get("id")) != eid]
            if len(story_data["beams"]) < before:
                # Clean up any secondary beams that were resting on this deleted beam!
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
                        # Recompute spans safely from remaining supports
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
                    # Also remove any transferred point loads that came from the deleted beam
                    if "loads" in ob and isinstance(ob["loads"], list):
                        ob["loads"] = [
                            ld for ld in ob["loads"]
                            if str(ld.get("source_beam", ld.get("source_beam_id", ""))) != eid
                        ]

                reconcile_and_split_slabs_after_beam_change(story_data)
                note = f" (Updated supported beam(s): {', '.join(detached_beams)})" if detached_beams else ""
                return True, f"Deleted Beam {eid}{note}."

        elif kind == "slab":
            slabs = story_data.get("slabs", [])
            before = len(slabs)
            story_data["slabs"] = [s for s in slabs if str(s.get("id")) != eid]
            if len(story_data["slabs"]) < before:
                # Refresh remaining slabs' cantilever/back-span flags safely
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
) -> Tuple[bool, str]:
    """
    Moves a column to (new_x, new_y), enforces the Outer Slab Boundary rule ('clamp' or 'expand'),
    and updates all beams supported by this column while keeping beams strictly orthogonal.
    """
    columns = story_data.get("columns", [])
    target_col = next((c for c in columns if c.get("id") == column_id), None)
    if not target_col:
        return False, f"Column {column_id} not found."

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

        col_coords = []
        for s in bm.get("supports", []):
            if s.get("kind") == "column":
                c_obj = next((c for c in columns if c["id"] == s.get("target_id")), None)
                if c_obj:
                    c_val = float(c_obj["x"]) if is_horiz else float(c_obj["y"])
                    s["coord"] = c_val
                    col_coords.append(c_val)
        col_coords.sort()
        valid_spans = [
            round(col_coords[k + 1] - col_coords[k], 3)
            for k in range(len(col_coords) - 1)
            if (col_coords[k + 1] - col_coords[k]) >= 0.35
        ]
        if valid_spans:
            bm["spans"] = valid_spans

    return True, msg


def move_beam_within_slab_boundary(
    story_data: Dict[str, Any],
    beam_id: str,
    dx: float,
    dy: float,
) -> Tuple[bool, str]:
    """
    Moves a beam by (dx, dy) while clamping its full width (width_m) strictly inside the Outer Slab Boundary.
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))
    if not has_bnd:
        return False, "No Outer Slab Boundary defined."

    beams = story_data.get("beams", [])
    bm = next((b for b in beams if b.get("id") == beam_id), None)
    if not bm:
        return False, f"Beam {beam_id} not found."

    half_w = float(bm.get("width_m", 0.30)) / 2.0
    sx, sy = float(bm.get("start_x", 0.0)) + dx, float(bm.get("start_y", 0.0)) + dy
    ex, ey = float(bm.get("end_x", 0.0)) + dx, float(bm.get("end_y", 0.0)) + dy
    is_horiz = abs(ex - sx) >= abs(ey - sy)

    if is_horiz:
        sx = min(max(sx, min_x), max_x)
        ex = min(max(ex, min_x), max_x)
        sy = ey = min(max(sy, min_y + half_w), max_y - half_w)
    else:
        sy = min(max(sy, min_y), max_y)
        ey = min(max(ey, min_y), max_y)
        sx = ex = min(max(sx, min_x + half_w), max_x - half_w)

    bm["start_x"] = round(sx, 3)
    bm["start_y"] = round(sy, 3)
    bm["end_x"] = round(ex, 3)
    bm["end_y"] = round(ey, 3)
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


def convert_beam_kind_and_section(
    story_data: Dict[str, Any],
    beam_id: str,
    new_kind: Optional[str] = None,
    new_width_m: Optional[float] = None,
    new_depth_m: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Converts a beam between Hidden Beam ('hidden', e.g., 0.40x0.30m) and Drop Beam ('drop', e.g., 0.20x0.50m)
    or updates its cross-section, clamps it inside the building boundary, and reconciles adjacent slabs.
    """
    beams = story_data.get("beams", [])
    bm = next((b for b in beams if b.get("id") == beam_id), None)
    if not bm:
        return False, f"Beam {beam_id} not found."

    cur_kind = bm.get("beam_kind", "hidden")
    target_kind = new_kind if new_kind in ("hidden", "drop") else ("drop" if cur_kind == "hidden" else "hidden")
    bm["beam_kind"] = target_kind

    if new_width_m is not None and new_depth_m is not None:
        bm["width_m"] = round(max(0.12, float(new_width_m)), 3)
        bm["depth_m"] = round(max(0.20, float(new_depth_m)), 3)
    else:
        slab_t_m = round(float(story_data.get("adopted_slab_thickness_cm", 25.0)) / 100.0, 3)
        if target_kind == "drop":
            bm["width_m"] = 0.20
            bm["depth_m"] = max(0.50, round(slab_t_m + 0.25, 2))
        else:
            bm["width_m"] = 0.40
            bm["depth_m"] = max(0.25, slab_t_m)

    bm.pop("manual_loads_override", None)
    move_beam_within_slab_boundary(story_data, beam_id, 0.0, 0.0)
    reconcile_and_split_slabs_after_beam_change(story_data)
    return (
        True,
        f"Converted Beam {beam_id} to {target_kind.upper()} ({bm['width_m']:.2f} × {bm['depth_m']:.2f} m).",
    )
