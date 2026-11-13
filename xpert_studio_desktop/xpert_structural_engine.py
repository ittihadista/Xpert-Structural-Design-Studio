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
from typing import Dict, Any, List, Tuple, Optional

try:
    from shapely.geometry import Polygon, Point, LineString, box
    from shapely.ops import polygonize, unary_union
except ImportError:
    Polygon = Point = LineString = box = polygonize = unary_union = None


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
    """
    spans = [float(s) for s in beam.get("spans", [5.0])]
    ns = len(spans)
    c_left = float(beam.get("cantilever_left_m", 0.0))
    c_right = float(beam.get("cantilever_right_m", 0.0))
    supports = beam.get("supports", [])
    loads = beam.get("loads", [])

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
        ltype = ld.get("type", "dist")
        val = float(ld.get("val", 0.0))
        if ltype == "dist":
            d_st = float(ld.get("x1", 0.0))
            d_en = float(ld.get("x2", right_start_x + c_right))
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
        elif ltype == "point":
            px = float(ld.get("x", 0.0))
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
        K2[i] = 1.0 / max(0.1, L[i])

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
        Ll = L[i]
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
    d_temp[1] = D[1]
    f_temp[1] = F[1]
    for i in range(2, ns + 2):
        m = E[i - 1] / d_temp[i - 1]
        d_temp[i] = D[i] - m * E[i - 1]
        f_temp[i] = F[i] - m * f_temp[i - 1]

    R_rot[ns + 1] = f_temp[ns + 1] / d_temp[ns + 1]
    for i in range(ns, 0, -1):
        R_rot[i] = (f_temp[i] - E[i] * R_rot[i + 1]) / d_temp[i]

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
        rrr1 = -(ML[i] + MR[i]) / L[i]
        rrl1 = (ML[i] + MR[i]) / L[i]
        rrl2, rrr2, rrl3, rrr3 = 0.0, 0.0, 0.0, 0.0
        for seg in W1[i]:
            qw, dw = seg["w"], seg["c"]
            aw = seg["a"] + dw / 2.0
            bw = L[i] - aw
            rrl2 += (qw * dw * bw) / L[i]
            rrr2 += (qw * dw * aw) / L[i]
        for pt in P1[i]:
            qp, ap = pt["p"], pt["a"]
            bp = L[i] - ap
            rrr3 += (qp * ap) / L[i]
            rrl3 += (qp * bp) / L[i]
        RRR[i] = -(rrr1 + rrr2 + rrr3)
        RRL[i] = rrl1 + rrl2 + rrl3

    RA[1] = RRL[1] + CL_force
    for i in range(1, ns):
        RA[i + 1] = RRL[i + 1] - RRR[i]
    RA[ns + 1] = -RRR[ns] + CR_force

    total_len = c_left + sum(spans) + c_right
    num_pts = 401
    x_full: List[float] = []
    v_full: List[float] = []
    m_full: List[float] = []

    for idx in range(num_pts):
        xpos = (idx / (num_pts - 1)) * total_len
        vval, mval = 0.0, 0.0
        for s_i, sx in enumerate(span_starts):
            if xpos >= sx - 1e-9:
                vval += RA[s_i + 1]
                mval += RA[s_i + 1] * (xpos - sx)
        for ld in loads:
            if ld.get("type") == "point":
                lx = float(ld.get("x", 0.0))
                lval = float(ld.get("val", 0.0))
                if xpos >= lx - 1e-9:
                    vval -= lval
                    mval -= lval * (xpos - lx)
            else:
                lx1 = float(ld.get("x1", 0.0))
                lx2 = float(ld.get("x2", total_len))
                lval = float(ld.get("val", 0.0))
                if xpos > lx1:
                    eff = min(xpos, lx2) - lx1
                    if eff > 0:
                        fw = lval * eff
                        vval -= fw
                        mval -= fw * (xpos - lx1 - eff / 2.0)
        x_full.append(round(xpos, 4))
        v_full.append(round(vval, 3))
        m_full.append(round(mval, 3))

    # Critical Forces at Support Centerlines AND Faces of Support
    support_critical_table = []
    for s_i, sx in enumerate(span_starts):
        sup_info = supports[s_i] if s_i < len(supports) else {"target_id": f"S{s_i+1}", "kind": "column", "width_m": 0.25}
        w_sup = float(sup_info.get("width_m", 0.25))
        x_face_left = max(0.0, sx - w_sup / 2.0)
        x_face_right = min(total_len, sx + w_sup / 2.0)

        # Interpolate moment & shear at face
        m_face = min(
            [m_full[k] for k in range(len(x_full)) if abs(x_full[k] - x_face_left) <= 0.08 or abs(x_full[k] - x_face_right) <= 0.08]
            or [Mus[s_i + 1]]
        )
        v_face = max(
            [abs(v_full[k]) for k in range(len(x_full)) if abs(x_full[k] - x_face_left) <= 0.08 or abs(x_full[k] - x_face_right) <= 0.08]
            or [abs(RA[s_i + 1])]
        )
        support_critical_table.append({
            "support_index": s_i + 1,
            "target_id": sup_info.get("target_id", f"C{s_i+1}"),
            "support_kind": sup_info.get("kind", "column"),
            "x_m": round(sx, 2),
            "reaction_ru_kn": round(RA[s_i + 1], 2),
            "centerline_neg_mu_knm": round(Mus[s_i + 1], 2),
            "face_neg_mu_knm": round(m_face, 2),
            "face_vu_kn": round(v_face, 2),
        })

    span_positive_moments = []
    for s_i in range(ns):
        s_st, s_en = span_starts[s_i], span_starts[s_i + 1]
        span_pts = [(x_full[k], m_full[k]) for k in range(len(x_full)) if s_st <= x_full[k] <= s_en]
        best_x, best_m = max(span_pts, key=lambda t: t[1]) if span_pts else (s_st, 0.0)
        span_positive_moments.append({
            "span_index": s_i + 1,
            "length_m": spans[s_i],
            "max_pos_mu_knm": round(max(0.0, best_m), 2),
            "at_x_m": round(best_x, 2),
        })

    return {
        "beam_id": beam.get("id", "B1"),
        "reactions": {i: round(RA[i], 2) for i in range(1, ns + 2)},
        "support_moments": [round(Mus[i], 2) for i in range(1, ns + 2)],
        "support_critical_table": support_critical_table,
        "span_positive_moments": span_positive_moments,
        "max_pos_mu_knm": max([s["max_pos_mu_knm"] for s in span_positive_moments] or [0.0]),
        "max_neg_face_mu_knm": min([s["face_neg_mu_knm"] for s in support_critical_table] or [0.0]),
        "max_face_vu_kn": max([s["face_vu_kn"] for s in support_critical_table] or [0.0]),
        "x_full": x_full,
        "v_full": v_full,
        "m_full": m_full,
    }


def analyze_all_story_beams_and_columns(
    story_data: Dict[str, Any],
    fc_mpa: float = 20.0,
    fy_mpa: float = 350.0,
) -> Dict[str, Any]:
    """
    1-Click Story Analysis:
    - Topologically sorts beams so secondary supported beams are solved first.
    - Transfers secondary beam reactions onto primary carrier beams.
    - Solves all beams and computes ACI 318 reinforcement design.
    - Builds comprehensive Column Load, End-Moment & 4-Way Framing Connectivity records.
    """
    beams = [dict(b) for b in story_data.get("beams", [])]
    columns = [dict(c) for c in story_data.get("columns", [])]
    story_h = float(story_data.get("height_m", 3.0))

    beam_map = {b["id"]: b for b in beams}
    # Topological sort: secondary beams resting on carrier beams first
    ordered_ids: List[str] = []
    visited = set()

    def visit(bid: str):
        if bid in visited or bid not in beam_map:
            return
        visited.add(bid)
        ordered_ids.append(bid)

    # First visit beams that rest on other beams
    for b in beams:
        if any(s.get("kind") == "beam" for s in b.get("supports", [])):
            visit(b["id"])
    for b in beams:
        visit(b["id"])

    beam_results: Dict[str, Dict[str, Any]] = {}
    beam_designs: Dict[str, Dict[str, Any]] = {}

    for bid in ordered_ids:
        bm = beam_map[bid]
        res = solve_continuous_beam_analytical(bm, fc_mpa, fy_mpa)
        beam_results[bid] = res
        beam_designs[bid] = design_beam_aci318(bm, res, fc_mpa, fy_mpa)

        # Transfer reaction to carrier beam if support kind == 'beam'
        for sup in bm.get("supports", []):
            if sup.get("kind") == "beam" and sup.get("target_id") in beam_map:
                s_idx = int(sup.get("support_index", 1))
                r_kn = res["reactions"].get(s_idx, 0.0)
                pos_x = float(sup.get("pos_on_carrier_m", 2.0))
                carrier = beam_map[sup["target_id"]]
                carrier["loads"] = list(carrier.get("loads", [])) + [{
                    "type": "point",
                    "x": pos_x,
                    "val": r_kn,
                    "label": f"Transferred Reaction from {bid}",
                }]

    # Build 4-Way Column Framing Connectivity, Reactions & End Moments
    column_records = []
    for col in columns:
        cid = col["id"]
        cx, cy = float(col["x"]), float(col["y"])
        b_m, h_m = float(col.get("b_m", 0.25)), float(col.get("h_m", 0.50))

        framing_directions: Dict[str, Optional[Dict[str, Any]]] = {
            "North": None,
            "South": None,
            "East": None,
            "West": None,
        }
        total_beam_reaction_kn = 0.0
        mux_knm = 0.0
        muy_knm = 0.0

        for bm in beams:
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
                        "width_m": bm.get("width_m", 0.30),
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
        story_pu_kn = round(total_beam_reaction_kn + self_wt_kn, 2)
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
    Designs a reinforced concrete Hidden or Drop beam per ACI 318 (matching Eng. Yousef's VBA methodology).
    """
    b_mm = float(beam.get("width_m", 0.30)) * 1000.0
    h_mm = float(beam.get("depth_m", 0.30)) * 1000.0
    d_mm = max(120.0, h_mm - 45.0)

    pos_mu = float(analysis_res.get("max_pos_mu_knm", 0.0))
    neg_mu = abs(float(analysis_res.get("max_neg_face_mu_knm", 0.0)))
    vu_kn = float(analysis_res.get("max_face_vu_kn", 0.0))

    def calc_ast(mu_knm: float) -> Tuple[float, str]:
        as_min = max(0.25 * math.sqrt(fc_mpa) / fy_mpa, 1.4 / fy_mpa) * b_mm * d_mm
        if mu_knm <= 0.1:
            ast = as_min
        else:
            rn = (mu_knm * 1e6) / (0.90 * b_mm * (d_mm ** 2))
            term = max(0.05, 1.0 - (2.0 * rn) / (0.85 * fc_mpa))
            rho = (0.85 * fc_mpa / fy_mpa) * (1.0 - math.sqrt(term))
            ast = max(as_min, rho * b_mm * d_mm)
        area_16 = 201.06
        n_bars = max(3 if b_mm >= 300 else 2, math.ceil(ast / area_16))
        return round(ast, 1), f"{n_bars} Phi 16 mm"

    ast_bot, bars_bot = calc_ast(pos_mu)
    ast_top, bars_top = calc_ast(neg_mu)

    vc_kn = (0.17 * math.sqrt(fc_mpa) * b_mm * d_mm) / 1000.0
    phi_vc = 0.75 * vc_kn
    stirrups = "Phi 8 @ 150 mm (2-Branches)" if vu_kn <= phi_vc * 1.5 else "Phi 10 @ 120 mm (4-Branches)"

    return {
        "beam_id": beam.get("id", "B1"),
        "b_mm": round(b_mm),
        "h_mm": round(h_mm),
        "bottom_ast_mm2": ast_bot,
        "bottom_bars": bars_bot,
        "top_ast_mm2": ast_top,
        "top_bars": bars_top,
        "phi_vc_kn": round(phi_vc, 1),
        "stirrups": stirrups,
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


# ============================================================================
# Interactive CAD Modeling, Boundary Control & Equilibrium Engine
# ============================================================================

def check_duplicate_column(
    x: float,
    y: float,
    b_m: float,
    h_m: float,
    existing_columns: List[Dict[str, Any]],
    ignore_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verifies if a new or moved column at (x, y) with dimensions (b_m, h_m)
    collides with or duplicates an existing column.
    Rejects overlapping column positions with an informative error message.
    """
    for col in existing_columns:
        cid = str(col.get("id", ""))
        if ignore_id and cid == str(ignore_id):
            continue
        if not col.get("active", True):
            continue
        cx = float(col.get("x", 0.0))
        cy = float(col.get("y", 0.0))
        cb = float(col.get("b_m", 0.20))
        ch = float(col.get("h_m", 0.40))

        dx = abs(x - cx)
        dy = abs(y - cy)
        dist = (dx * dx + dy * dy) ** 0.5

        # Check collision: center distance smaller than 75% of minimum column dimension
        min_dim = min(b_m, h_m, cb, ch)
        if dist < min_dim * 0.75:
            return False, f"Duplicate Column Rejected: Position ({x:.2f}, {y:.2f}) coincides with existing column {cid}."

        # Or heavy bounding box overlap
        overlap_x = max(0.0, (b_m + cb) / 2.0 - dx)
        overlap_y = max(0.0, (h_m + ch) / 2.0 - dy)
        if overlap_x > 0.6 * min(b_m, cb) and overlap_y > 0.6 * min(h_m, ch):
            return False, f"Duplicate Column Rejected: Column at ({x:.2f}, {y:.2f}) heavily overlaps with existing column {cid}."

    return True, ""


def clamp_or_expand_column_boundary(
    col_x: float,
    col_y: float,
    b_m: float,
    h_m: float,
    slab_edge_polygon: List[List[float]],
    rule: str = "clamp",
) -> Tuple[float, float, List[List[float]], bool]:
    """
    Enforces that column (b_m x h_m) centered at (col_x, col_y) does not exceed slab boundary.
    - If rule == 'clamp': clamps (col_x, col_y) flush inside the slab boundary.
    - If rule == 'expand': expands slab_edge_polygon bounding box to encompass the column outer face.
    Returns: (final_x, final_y, final_polygon, was_modified)
    """
    if not slab_edge_polygon or len(slab_edge_polygon) < 3:
        return col_x, col_y, slab_edge_polygon, False

    xs = [float(p[0]) for p in slab_edge_polygon]
    ys = [float(p[1]) for p in slab_edge_polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    half_b = b_m / 2.0
    half_h = h_m / 2.0

    if rule == "expand":
        new_min_x = min(min_x, col_x - half_b)
        new_max_x = max(max_x, col_x + half_b)
        new_min_y = min(min_y, col_y - half_h)
        new_max_y = max(max_y, col_y + half_h)
        was_modified = (
            abs(new_min_x - min_x) > 1e-4
            or abs(new_max_x - max_x) > 1e-4
            or abs(new_min_y - min_y) > 1e-4
            or abs(new_max_y - max_y) > 1e-4
        )
        new_poly = [
            [round(new_min_x, 3), round(new_min_y, 3)],
            [round(new_max_x, 3), round(new_min_y, 3)],
            [round(new_max_x, 3), round(new_max_y, 3)],
            [round(new_min_x, 3), round(new_max_y, 3)],
        ]
        return col_x, col_y, new_poly, was_modified

    # rule == 'clamp' (default):
    allow_min_x = min_x + half_b
    allow_max_x = max_x - half_b
    allow_min_y = min_y + half_h
    allow_max_y = max_y - half_h

    if allow_max_x < allow_min_x:
        allow_min_x = allow_max_x = (min_x + max_x) / 2.0
    if allow_max_y < allow_min_y:
        allow_min_y = allow_max_y = (min_y + max_y) / 2.0

    clamped_x = max(allow_min_x, min(allow_max_x, col_x))
    clamped_y = max(allow_min_y, min(allow_max_y, col_y))
    was_modified = (abs(clamped_x - col_x) > 1e-4 or abs(clamped_y - col_y) > 1e-4)

    return round(clamped_x, 3), round(clamped_y, 3), slab_edge_polygon, was_modified


def rotate_column_90_deg(
    col_id: str,
    story: Dict[str, Any],
    rule: str = "clamp",
) -> Tuple[bool, str]:
    """
    Rotates a selected column by 90 degrees by swapping b_m and h_m,
    then re-clamps it flush inside the slab boundary.
    """
    columns = story.get("columns", [])
    target_col = None
    for col in columns:
        if str(col.get("id")) == str(col_id):
            target_col = col
            break

    if not target_col:
        return False, f"Column {col_id} not found in story."

    old_b = float(target_col.get("b_m", 0.20))
    old_h = float(target_col.get("h_m", 0.40))
    new_b = old_h
    new_h = old_b

    edge = story.get("slab_edge_polygon", [])
    final_x, final_y, updated_poly, was_mod = clamp_or_expand_column_boundary(
        float(target_col["x"]), float(target_col["y"]), new_b, new_h, edge, rule=rule
    )

    # Check duplicate collision with other columns
    dup_ok, dup_msg = check_duplicate_column(final_x, final_y, new_b, new_h, columns, ignore_id=col_id)
    if not dup_ok:
        return False, dup_msg

    target_col["b_m"] = round(new_b, 3)
    target_col["h_m"] = round(new_h, 3)
    target_col["x"] = final_x
    target_col["y"] = final_y
    if updated_poly != edge:
        story["slab_edge_polygon"] = updated_poly

    # Update supports on connected beams
    for bm in story.get("beams", []):
        for sup in bm.get("supports", []):
            if str(sup.get("target_id")) == str(col_id):
                sup["width_m"] = new_b
                sup["x"] = final_x
                sup["y"] = final_y

    return True, f"Column {col_id} rotated 90° to {new_b:.2f}x{new_h:.2f} m at ({final_x:.2f}, {final_y:.2f})."


def validate_beam_cantilevers_and_boundary(
    beam: Dict[str, Any],
    columns: List[Dict[str, Any]],
    all_beams: List[Dict[str, Any]],
    slab_edge_polygon: List[List[float]],
    openings: Optional[List[Dict[str, Any]]] = None,
    tolerance_m: float = 0.25,
) -> Tuple[bool, str]:
    """
    Validates:
    1. Beam start and end points must reside inside or on the slab boundary polygon.
    2. Cantilever overhangs extending past the outermost column support must have a true
       free end reaching the outer slab boundary edge (or an opening edge), or rest
       on a supporting girder beam.
       Unsupported overhangs terminating in the mid-slab interior are rejected
       with 'Invalid Interior Cantilever'.
    """
    if not slab_edge_polygon or len(slab_edge_polygon) < 3:
        return True, "No slab boundary defined."

    sx = float(beam.get("start_x", 0.0))
    sy = float(beam.get("start_y", 0.0))
    ex = float(beam.get("end_x", 0.0))
    ey = float(beam.get("end_y", 0.0))

    if Polygon is None:
        return True, "Shapely not installed."

    edge_poly = Polygon(slab_edge_polygon)
    edge_ext = edge_poly.exterior

    # 1. Start and end must not be outside outer boundary
    if edge_poly.distance(Point(sx, sy)) > tolerance_m:
        return False, f"Beam start point ({sx:.2f}, {sy:.2f}) is outside the slab boundary [00-XD-EDGE]."
    if edge_poly.distance(Point(ex, ey)) > tolerance_m:
        return False, f"Beam end point ({ex:.2f}, {ey:.2f}) is outside the slab boundary [00-XD-EDGE]."

    beam_line = LineString([(sx, sy), (ex, ey)])
    beam_len = beam_line.length
    if beam_len < 0.20:
        return False, "Beam length must be at least 0.20 m."

    # Find columns lying along this beam
    sup_cols = []
    for col in columns:
        if not col.get("active", True):
            continue
        cx, cy = float(col["x"]), float(col["y"])
        c_pt = Point(cx, cy)
        dist = beam_line.distance(c_pt)
        if dist <= max(float(col.get("b_m", 0.25)), float(col.get("h_m", 0.50))) / 1.5:
            proj = beam_line.project(c_pt)
            sup_cols.append((proj, col))

    sup_cols.sort(key=lambda item: item[0])

    def is_supported_by_another_beam(pt: Point) -> bool:
        b_id = str(beam.get("id", ""))
        for ob in all_beams:
            if str(ob.get("id", "")) == b_id:
                continue
            ob_line = LineString([(float(ob["start_x"]), float(ob["start_y"])), (float(ob["end_x"]), float(ob["end_y"]))])
            if ob_line.distance(pt) <= 0.20:
                return True
        return False

    def is_near_boundary_or_opening(pt: Point) -> bool:
        if edge_ext.distance(pt) <= tolerance_m:
            return True
        if openings:
            for op in openings:
                op_poly = Polygon(op.get("polygon", [])) if op.get("polygon") else None
                if op_poly and op_poly.exterior.distance(pt) <= tolerance_m:
                    return True
        return False

    if sup_cols:
        d_first = sup_cols[0][0]
        d_last = beam_len - sup_cols[-1][0]

        # Check left overhang
        if d_first > 0.35:
            start_pt = Point(sx, sy)
            if not is_supported_by_another_beam(start_pt) and not is_near_boundary_or_opening(start_pt):
                return False, (
                    f"Invalid Interior Cantilever: Beam {beam.get('id', 'B')} starts with an overhang of "
                    f"{d_first:.2f} m at ({sx:.2f}, {sy:.2f}) terminating in the interior slab without "
                    f"a supporting beam or boundary edge."
                )

        # Check right overhang
        if d_last > 0.35:
            end_pt = Point(ex, ey)
            if not is_supported_by_another_beam(end_pt) and not is_near_boundary_or_opening(end_pt):
                return False, (
                    f"Invalid Interior Cantilever: Beam {beam.get('id', 'B')} ends with an overhang of "
                    f"{d_last:.2f} m at ({ex:.2f}, {ey:.2f}) terminating in the interior slab without "
                    f"a supporting beam or boundary edge."
                )
    else:
        # No columns along beam - both ends must be supported by other beams or reach boundary
        start_pt = Point(sx, sy)
        end_pt = Point(ex, ey)
        if not is_supported_by_another_beam(start_pt) and not is_near_boundary_or_opening(start_pt):
            return False, f"Invalid Beam: Start at ({sx:.2f}, {sy:.2f}) has neither column support nor carrying beam."
        if not is_supported_by_another_beam(end_pt) and not is_near_boundary_or_opening(end_pt):
            return False, f"Invalid Beam: End at ({ex:.2f}, {ey:.2f}) has neither column support nor carrying beam."

    return True, "Beam geometry and cantilever overhangs are valid."


def check_duplicate_beam(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    existing_beams: List[Dict[str, Any]],
    ignore_id: Optional[str] = None,
    tol: float = 0.15,
) -> Tuple[bool, str]:
    """
    Checks if a proposed beam between (sx, sy) and (ex, ey) overlaps or duplicates
    an existing beam along the same axis.
    """
    b_len = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
    if b_len < 0.05:
        return False, "Beam length must be at least 0.20 m."

    b_line = LineString([(sx, sy), (ex, ey)]) if LineString is not None else None

    for ob in existing_beams:
        oid = str(ob.get("id", ""))
        if ignore_id and oid == str(ignore_id):
            continue
        osx = float(ob.get("start_x", 0.0))
        osy = float(ob.get("start_y", 0.0))
        oex = float(ob.get("end_x", 0.0))
        oey = float(ob.get("end_y", 0.0))

        # Check endpoints match in forward direction
        d_sf = ((sx - osx) ** 2 + (sy - osy) ** 2) ** 0.5
        d_ef = ((ex - oex) ** 2 + (ey - oey) ** 2) ** 0.5
        if d_sf <= tol and d_ef <= tol:
            return False, f"Duplicate Beam Rejected: Axis coincides with existing beam {oid}."

        # Check endpoints match in reverse direction
        d_sr = ((sx - oex) ** 2 + (sy - oey) ** 2) ** 0.5
        d_er = ((ex - osx) ** 2 + (ey - osy) ** 2) ** 0.5
        if d_sr <= tol and d_er <= tol:
            return False, f"Duplicate Beam Rejected: Axis coincides with existing beam {oid}."

        # Collinear overlap
        if b_line is not None:
            ob_line = LineString([(osx, osy), (oex, oey)])
            dist_s = ob_line.distance(Point(sx, sy))
            dist_e = ob_line.distance(Point(ex, ey))
            if dist_s <= tol and dist_e <= tol:
                return False, f"Duplicate Beam Rejected: Beam lies entirely along existing beam {oid}."
            dist_os = b_line.distance(Point(osx, osy))
            dist_oe = b_line.distance(Point(oex, oey))
            if dist_os <= tol and dist_oe <= tol:
                return False, f"Duplicate Beam Rejected: Axis overlaps existing beam {oid}."

    return True, ""


def validate_and_build_beam_with_cantilevers(
    start_pt: Tuple[float, float],
    end_pt: Tuple[float, float],
    b_kind: str,
    width_m: float,
    depth_m: float,
    story: Dict[str, Any],
    beam_id: Optional[str] = None,
    ignore_id: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates geometry, rejects duplicate beams along the same axis, clamps flush inside boundary,
    detects all intermediate columns and supporting beams along the axis, and subdivides
    into consecutive spans for continuous beam modeling.
    """
    edge = story.get("slab_edge_polygon", [])
    cols = story.get("columns", [])
    existing_beams = story.get("beams", [])
    openings = story.get("openings", [])

    sx, sy = start_pt
    ex, ey = end_pt

    # 1. Check duplicate beam
    dup_ok, dup_msg = check_duplicate_beam(sx, sy, ex, ey, existing_beams, ignore_id=ignore_id)
    if not dup_ok:
        return False, dup_msg, None

    if beam_id is None:
        beam_id = f"B{len(existing_beams) + 1}"

    temp_beam = {
        "id": beam_id,
        "beam_kind": b_kind,
        "width_m": width_m,
        "depth_m": depth_m,
        "start_x": sx,
        "start_y": sy,
        "end_x": ex,
        "end_y": ey,
    }

    # 2. Auto-clamp beam centerline inward if protruding outside building edge
    temp_beam, was_clamped = clamp_beam_inside_boundary(temp_beam, edge)

    # 3. Validate cantilevers & boundary
    valid_geom, geom_err = validate_beam_cantilevers_and_boundary(
        temp_beam, cols, existing_beams, edge, openings=openings
    )
    if not valid_geom:
        return False, geom_err, None

    bx1, by1 = temp_beam["start_x"], temp_beam["start_y"]
    bx2, by2 = temp_beam["end_x"], temp_beam["end_y"]
    beam_line = LineString([(bx1, by1), (bx2, by2)]) if LineString is not None else None
    beam_len = ((bx2 - bx1) ** 2 + (by2 - by1) ** 2) ** 0.5

    # 4. Detect all intermediate supports along this continuous beam line
    sup_list = []
    if beam_line is not None:
        for c in cols:
            if not c.get("active", True):
                continue
            c_pt = Point(float(c["x"]), float(c["y"]))
            c_reach = max(float(c.get("b_m", 0.20)), float(c.get("h_m", 0.40))) / 1.5 + width_m / 2.0
            if beam_line.distance(c_pt) <= c_reach:
                proj = beam_line.project(c_pt)
                sup_list.append((proj, "column", c))

        # Detect intermediate intersecting/supporting beams
        for ob in existing_beams:
            if ignore_id and str(ob.get("id", "")) == str(ignore_id):
                continue
            osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
            oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
            ob_line = LineString([(osx, osy), (oex, oey)])
            inter = beam_line.intersection(ob_line)
            if inter and not inter.is_empty:
                if inter.geom_type == "Point":
                    ipt = inter
                elif hasattr(inter, "geoms") and len(inter.geoms) > 0:
                    ipt = inter.geoms[0]
                else:
                    continue
                proj = beam_line.project(ipt)
                if not any(abs(proj - s[0]) < 0.35 for s in sup_list):
                    sup_list.append((proj, "beam", {
                        "id": ob.get("id", "Bm"),
                        "x": ipt.x,
                        "y": ipt.y,
                        "width_m": float(ob.get("width_m", 0.20)),
                    }))

    sup_list.sort(key=lambda s: s[0])

    supports = []
    spans = []
    if sup_list:
        for s_i, (proj, stype, sobj) in enumerate(sup_list):
            supports.append({
                "support_index": s_i + 1,
                "kind": stype,
                "target_id": sobj["id"],
                "width_m": float(sobj.get("width_m", sobj.get("b_m", 0.20))),
                "x": float(sobj["x"]),
                "y": float(sobj["y"]),
            })
        if len(supports) >= 2:
            for s_i in range(len(supports) - 1):
                p1 = (supports[s_i]["x"], supports[s_i]["y"])
                p2 = (supports[s_i + 1]["x"], supports[s_i + 1]["y"])
                spans.append(round(((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5, 2))
        else:
            spans = [round(beam_len, 2)]
    else:
        spans = [round(beam_len, 2)]

    c_left = round(sup_list[0][0], 2) if (sup_list and sup_list[0][0] > 0.05) else 0.0
    c_right = round(beam_len - sup_list[-1][0], 2) if (sup_list and (beam_len - sup_list[-1][0]) > 0.05) else 0.0

    temp_beam["supports"] = supports
    temp_beam["spans"] = spans
    temp_beam["cantilever_left_m"] = c_left
    temp_beam["cantilever_right_m"] = c_right
    temp_beam["loads"] = [{"type": "dist", "x1": 0.0, "x2": round(beam_len, 2), "val": 30.0}]

    return True, "Beam built successfully", temp_beam


def detect_bays_and_determine_ribs(
    slab_edge_polygon: List[List[float]],
    beams: List[Dict[str, Any]],
    slabs: Optional[List[Dict[str, Any]]] = None,
    openings: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Subdivides the floor bounded by slab_edge_polygon and beams into bays.
    Determines bounding beams, bay type (4_beam vs 3_beam), and default rib directions:
    - 4-Beam Bounded Bay: default rib along shorter span (0° if Lx <= Ly else 90°).
    - 3-Beam Bounded Bay: default rib between opposing parallel beams.
    Preserves overrides from existing slabs & openings.
    """
    if not slab_edge_polygon or len(slab_edge_polygon) < 3 or Polygon is None:
        return []

    slabs = slabs or []
    openings = openings or []

    edge_poly = Polygon(slab_edge_polygon)
    edge_coords = list(edge_poly.exterior.coords)
    edge_lines = [
        LineString([edge_coords[i], edge_coords[i + 1]])
        for i in range(len(edge_coords) - 1)
    ]

    beam_lines = []
    beam_objs = []
    for bm in beams:
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        if ((sx - ex) ** 2 + (sy - ey) ** 2) ** 0.5 > 0.10:
            bl = LineString([(sx, sy), (ex, ey)])
            beam_objs.append((bm.get("id", "B"), bl, bm))

            # Merge perimeter beams within max(0.45, width_m + 0.15) of boundary
            b_w = float(bm.get("width_m", 0.20))
            snap_dist = max(0.45, b_w + 0.15)
            mid_pt = bl.interpolate(0.5, normalized=True)
            if (
                edge_poly.exterior.distance(Point(sx, sy)) <= snap_dist
                and edge_poly.exterior.distance(Point(ex, ey)) <= snap_dist
                and edge_poly.exterior.distance(mid_pt) <= snap_dist
            ):
                continue
            beam_lines.append(bl)

    all_network = unary_union(edge_lines + beam_lines)
    raw_bays = list(polygonize(all_network))

    # Keep only valid structural bays: inside edge_poly, excluding sliver bays (< 0.85m)
    valid_bays = []
    for b in raw_bays:
        if edge_poly.contains(b.centroid) and b.area > 0.05:
            minx, miny, maxx, maxy = b.bounds
            lx = round(maxx - minx, 2)
            ly = round(maxy - miny, 2)
            if lx < 0.85 or ly < 0.85 or b.area < (0.85 * 0.85):
                continue
            valid_bays.append(b)

    valid_bays.sort(key=lambda p: (-p.centroid.y, p.centroid.x))

    result_bays: List[Dict[str, Any]] = []

    for idx, bay_poly in enumerate(valid_bays):
        bay_id = f"S{idx + 1}"
        minx, miny, maxx, maxy = bay_poly.bounds
        lx = round(maxx - minx, 2)
        ly = round(maxy - miny, 2)
        cx, cy = round(bay_poly.centroid.x, 2), round(bay_poly.centroid.y, 2)
        poly_pts = [[round(p[0], 2), round(p[1], 2)] for p in list(bay_poly.exterior.coords)[:-1]]

        # Analyze edges to find bounding beams
        coords = list(bay_poly.exterior.coords)
        beam_sides = []
        carrying_beams = {}

        for k in range(len(coords) - 1):
            seg = LineString([coords[k], coords[k + 1]])
            mid = seg.interpolate(0.5, normalized=True)

            dx = abs(coords[k + 1][0] - coords[k][0])
            dy = abs(coords[k + 1][1] - coords[k][1])
            if dx >= dy:
                side = "NORTH" if mid.y >= (miny + maxy) / 2.0 else "SOUTH"
            else:
                side = "EAST" if mid.x >= (minx + maxx) / 2.0 else "WEST"

            hit_beam_id = None
            for bid, bline, bdict in beam_objs:
                hit_tol = max(0.45, float(bdict.get("width_m", 0.20)) + 0.15)
                if bline.distance(mid) <= hit_tol:
                    hit_beam_id = bid
                    break

            if hit_beam_id:
                if side not in beam_sides:
                    beam_sides.append(side)
                    carrying_beams[side] = hit_beam_id

        # Determine Bay Type & Default Ribs
        if len(beam_sides) >= 4:
            bay_type = "4_beam"
            free_side = None
            default_rib_deg = 0.0 if lx <= ly else 90.0  # Shorter span
            carrying_side = None
            carrying_beam_id = None
        elif len(beam_sides) == 3:
            bay_type = "3_beam"
            all_s = {"NORTH", "SOUTH", "EAST", "WEST"}
            free_side = list(all_s - set(beam_sides))[0]
            if free_side in ("EAST", "WEST"):
                default_rib_deg = 90.0  # Opposing horizontal beams North & South
                carrying_side = "WEST" if free_side == "EAST" else "EAST"
            else:
                default_rib_deg = 0.0  # Opposing vertical beams East & West
                carrying_side = "SOUTH" if free_side == "NORTH" else "NORTH"
            carrying_beam_id = carrying_beams.get(carrying_side)
        else:
            bay_type = "cantilever" if len(beam_sides) == 1 else "other"
            free_side = None
            default_rib_deg = 0.0 if lx <= ly else 90.0
            carrying_side = beam_sides[0] if beam_sides else None
            carrying_beam_id = carrying_beams.get(carrying_side) if carrying_side else None

        # Check existing slab matching this centroid
        matched_slab = None
        for s in slabs:
            spoly = Polygon(s.get("polygon", [])) if s.get("polygon") else None
            if spoly and spoly.contains(Point(cx, cy)):
                matched_slab = s
                break
            elif abs(float(s.get("center_x", -999)) - cx) < 0.4 and abs(float(s.get("center_y", -999)) - cy) < 0.4:
                matched_slab = s
                break

        # Check existing opening matching this centroid
        is_opening = False
        for op in openings:
            op_poly = Polygon(op.get("polygon", [])) if op.get("polygon") else None
            if op_poly and op_poly.contains(Point(cx, cy)):
                is_opening = True
                break

        rib_deg = float(matched_slab["rib_direction_deg"]) if matched_slab else default_rib_deg
        is_cant = bool(matched_slab.get("is_cantilever", False)) if matched_slab else False
        supports_cant = matched_slab.get("supports_cantilever_for") if matched_slab else None

        result_bays.append({
            "id": matched_slab.get("id", bay_id) if matched_slab else bay_id,
            "polygon": poly_pts,
            "bounds": (minx, miny, maxx, maxy),
            "center": (cx, cy),
            "lx": lx,
            "ly": ly,
            "bay_type": bay_type,
            "beam_sides": beam_sides,
            "free_side": free_side,
            "carrying_side": carrying_side,
            "carrying_beam_id": carrying_beam_id,
            "default_rib_direction_deg": default_rib_deg,
            "rib_direction_deg": rib_deg,
            "is_cantilever": is_cant,
            "is_opening": is_opening,
            "supports_cantilever_for": supports_cant,
        })

    return result_bays


def detect_story_grid_bays(story: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Subdivides the story floor bounded by slab_edge_polygon and beams into structural bays.
    Perimeter beams within max(0.45, width_m + 0.15) are merged with the outer boundary,
    and sliver bays with lx < 0.85m or ly < 0.85m are excluded.
    """
    edge = story.get("slab_edge_polygon", [])
    beams = story.get("beams", [])
    slabs = story.get("slabs", [])
    openings = story.get("openings", [])
    return detect_bays_and_determine_ribs(edge, beams, slabs, openings)


def reconcile_and_split_slabs_after_beam_change(story: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Reconciles existing slabs after a beam is added, moved, or deleted.
    If a new beam cuts an existing slab bay into multiple sub-bays, the old slab is
    automatically split into independent sub-slabs supported by the new beam.
    Updates ACI 318 thickness evaluation immediately.
    """
    new_bays = detect_story_grid_bays(story)
    existing_slabs = list(story.get("slabs", []))

    if not existing_slabs or not new_bays:
        return existing_slabs

    assigned_bay_ids = set()
    result_slabs: List[Dict[str, Any]] = []

    for old_slab in existing_slabs:
        old_poly = Polygon(old_slab.get("polygon", [])) if old_slab.get("polygon") else None
        old_cx = float(old_slab.get("center_x", 0.0))
        old_cy = float(old_slab.get("center_y", 0.0))
        old_pt = Point(old_cx, old_cy)

        matching_bays = []
        for bay in new_bays:
            if bay["id"] in assigned_bay_ids:
                continue
            b_poly = Polygon(bay["polygon"]) if bay.get("polygon") else None
            if b_poly is None:
                continue
            b_center = Point(bay["center"][0], bay["center"][1])
            is_match = False
            if old_poly and (old_poly.contains(b_center) or old_poly.intersection(b_poly).area > 0.40 * b_poly.area):
                is_match = True
            elif ((b_center.x - old_cx) ** 2 + (b_center.y - old_cy) ** 2) ** 0.5 < 0.40:
                is_match = True

            if is_match:
                matching_bays.append(bay)

        if len(matching_bays) >= 2:
            # Smart Slab Splitting: old slab was divided into 2+ sub-bays by a new beam!
            for s_idx, mb in enumerate(matching_bays):
                assigned_bay_ids.add(mb["id"])
                sub_id = f"{old_slab['id']}_{s_idx + 1}" if s_idx > 0 else old_slab["id"]
                sub_slab = {
                    "id": sub_id,
                    "polygon": mb["polygon"],
                    "center_x": mb["center"][0],
                    "center_y": mb["center"][1],
                    "lx": mb["lx"],
                    "ly": mb["ly"],
                    "axis_span_m": mb["lx"] if mb["default_rib_direction_deg"] == 0.0 else mb["ly"],
                    "rib_direction_deg": mb["default_rib_direction_deg"],
                    "bay_type": mb["bay_type"],
                    "carrying_beam_id": mb.get("carrying_beam_id"),
                    "is_cantilever": False,
                    "is_opening": False,
                    "supports_cantilever_for": None,
                }
                result_slabs.append(sub_slab)
        elif len(matching_bays) == 1:
            mb = matching_bays[0]
            assigned_bay_ids.add(mb["id"])
            updated_slab = dict(old_slab)
            updated_slab["polygon"] = mb["polygon"]
            updated_slab["center_x"] = mb["center"][0]
            updated_slab["center_y"] = mb["center"][1]
            updated_slab["lx"] = mb["lx"]
            updated_slab["ly"] = mb["ly"]
            updated_slab["bay_type"] = mb["bay_type"]
            updated_slab["carrying_beam_id"] = mb.get("carrying_beam_id")
            if "rib_direction_deg" not in updated_slab:
                updated_slab["rib_direction_deg"] = mb["default_rib_direction_deg"]
            updated_slab["axis_span_m"] = mb["lx"] if updated_slab["rib_direction_deg"] == 0.0 else mb["ly"]
            result_slabs.append(updated_slab)
        else:
            for bay in new_bays:
                if bay["id"] in assigned_bay_ids:
                    continue
                b_poly = Polygon(bay["polygon"]) if bay.get("polygon") else None
                if b_poly and b_poly.contains(old_pt):
                    assigned_bay_ids.add(bay["id"])
                    updated_slab = dict(old_slab)
                    updated_slab["polygon"] = bay["polygon"]
                    updated_slab["center_x"] = bay["center"][0]
                    updated_slab["center_y"] = bay["center"][1]
                    updated_slab["lx"] = bay["lx"]
                    updated_slab["ly"] = bay["ly"]
                    updated_slab["axis_span_m"] = bay["lx"] if updated_slab.get("rib_direction_deg", 0.0) == 0.0 else bay["ly"]
                    result_slabs.append(updated_slab)
                    break

    # Ensure clean sequential/unique IDs
    seen_ids = set()
    for s in result_slabs:
        sid = s.get("id", "S1")
        if sid in seen_ids:
            new_id = f"S{len(seen_ids) + 1}"
            s["id"] = new_id
        seen_ids.add(s["id"])

    story["slabs"] = result_slabs
    evaluate_story_thickness_and_optimization(story)
    return result_slabs


def auto_fill_all_story_slabs(story: Dict[str, Any]) -> Tuple[int, str]:
    """
    Detects all closed bays bounded by beams and outer boundary,
    and populates every non-opening bay with a solid hollow-block slab
    with code-compliant default rib directions in one click.
    """
    bays = detect_story_grid_bays(story)
    if not bays:
        return 0, "No closed beam bays detected to fill."

    openings = story.get("openings", [])
    existing_slabs = story.get("slabs", [])
    existing_by_center = {}
    for s in existing_slabs:
        cx = float(s.get("center_x", -999))
        cy = float(s.get("center_y", -999))
        existing_by_center[(round(cx, 2), round(cy, 2))] = s

    new_slabs: List[Dict[str, Any]] = []
    count_added = 0

    for idx, bay in enumerate(bays):
        bc = (round(bay["center"][0], 2), round(bay["center"][1], 2))
        pt = Point(bay["center"][0], bay["center"][1])

        # Skip if bay is an opening
        is_op = False
        for op in openings:
            op_poly = Polygon(op.get("polygon", [])) if op.get("polygon") else None
            if op_poly and op_poly.contains(pt):
                is_op = True
                break
        if is_op:
            continue

        matched = None
        for (ex, ey), s in existing_by_center.items():
            if ((ex - bc[0]) ** 2 + (ey - bc[1]) ** 2) ** 0.5 < 0.40:
                matched = s
                break

        if matched:
            matched["polygon"] = bay["polygon"]
            matched["center_x"] = bay["center"][0]
            matched["center_y"] = bay["center"][1]
            matched["lx"] = bay["lx"]
            matched["ly"] = bay["ly"]
            matched["bay_type"] = bay["bay_type"]
            matched["carrying_beam_id"] = bay.get("carrying_beam_id")
            new_slabs.append(matched)
        else:
            slab_id = f"S{len(new_slabs) + 1}"
            new_slabs.append({
                "id": slab_id,
                "polygon": bay["polygon"],
                "center_x": bay["center"][0],
                "center_y": bay["center"][1],
                "lx": bay["lx"],
                "ly": bay["ly"],
                "axis_span_m": bay["lx"] if bay["default_rib_direction_deg"] == 0.0 else bay["ly"],
                "rib_direction_deg": bay["default_rib_direction_deg"],
                "bay_type": bay["bay_type"],
                "carrying_beam_id": bay.get("carrying_beam_id"),
                "is_cantilever": False,
                "is_opening": False,
            })
            count_added += 1

    story["slabs"] = new_slabs
    evaluate_story_thickness_and_optimization(story)
    return count_added, f"Auto-filled {count_added} new slab bays (Total: {len(new_slabs)} active slabs)."


def pick_area_slab(
    click_pt: Tuple[float, float],
    slab_edge_polygon: List[List[float]],
    beams: List[Dict[str, Any]],
    slabs: List[Dict[str, Any]],
    openings: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Step 4A: Pick Area: Slab.
    Detects the bay enclosing click_pt, assigns default rib direction
    (shorter span for 4-beam, opposing beams for 3-beam), and creates or updates the slab.
    If the bay was an opening, converts it back to a solid slab.
    """
    openings = list(openings or [])
    slabs = list(slabs or [])
    bays = detect_bays_and_determine_ribs(slab_edge_polygon, beams, slabs, openings)

    target_bay = None
    pt = Point(click_pt[0], click_pt[1])
    for b in bays:
        poly = Polygon(b["polygon"])
        if poly.contains(pt) or poly.exterior.distance(pt) < 0.05:
            target_bay = b
            break

    if not target_bay:
        return False, f"Click at ({click_pt[0]:.2f}, {click_pt[1]:.2f}) is outside any closed beam bay.", slabs, openings

    # Remove from openings if present
    openings = [
        op for op in openings
        if not (Polygon(op.get("polygon", [])).contains(pt) if op.get("polygon") else False)
    ]

    # Create/update slab entry
    existing_idx = None
    for idx, s in enumerate(slabs):
        spoly = Polygon(s.get("polygon", [])) if s.get("polygon") else None
        if spoly and (spoly.contains(pt) or spoly.exterior.distance(pt) < 0.05):
            existing_idx = idx
            break

    slab_record = {
        "id": target_bay["id"],
        "polygon": target_bay["polygon"],
        "center_x": target_bay["center"][0],
        "center_y": target_bay["center"][1],
        "axis_span_m": target_bay["lx"] if target_bay["default_rib_direction_deg"] == 0.0 else target_bay["ly"],
        "rib_direction_deg": target_bay["default_rib_direction_deg"],
        "bay_type": target_bay["bay_type"],
        "is_cantilever": False,
        "is_opening": False,
        "left_support_w_m": 0.25,
        "right_support_w_m": 0.25,
    }

    if existing_idx is not None:
        slabs[existing_idx] = slab_record
    else:
        slabs.append(slab_record)

    return (
        True,
        f"Assigned Slab {slab_record['id']} ({target_bay['bay_type']}): Ribs at {slab_record['rib_direction_deg']:.0f}°.",
        slabs,
        openings,
    )


def flip_rib_direction_with_equilibrium(
    click_pt: Tuple[float, float],
    slab_edge_polygon: List[List[float]],
    beams: List[Dict[str, Any]],
    slabs: List[Dict[str, Any]],
    openings: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Step 4B: Pick: Flip Rib Direction.
    - If 4-beam bay: toggles between 0° and 90°.
    - If 3-beam bay currently with default ribs:
      User flips it to Cantilever Slab pointing to the free edge.
      Enforces Cantilever Slab Equilibrium Rule:
      1. Finds back-span slab directly behind carrying beam.
      2. Validates that back-span slab exists and is NOT an opening.
      3. Automatically synchronizes back-span ribs to be continuous in the exact same direction.
      4. Tags back-span slab as supporting the cantilever.
    - If 3-beam bay is already cantilever: restores default supported ribs.
    """
    openings = list(openings or [])
    slabs = list(slabs or [])
    bays = detect_bays_and_determine_ribs(slab_edge_polygon, beams, slabs, openings)

    target_bay = None
    pt = Point(click_pt[0], click_pt[1])
    for b in bays:
        poly = Polygon(b["polygon"])
        if poly.contains(pt) or poly.exterior.distance(pt) < 0.05:
            target_bay = b
            break

    if not target_bay:
        return False, f"Click at ({click_pt[0]:.2f}, {click_pt[1]:.2f}) is outside any closed bay.", slabs

    if target_bay["is_opening"]:
        return False, "Cannot flip rib direction on a void opening [00-XD-OPEN].", slabs

    bay_type = target_bay["bay_type"]

    target_slab = None
    for s in slabs:
        spoly = Polygon(s.get("polygon", [])) if s.get("polygon") else None
        if spoly and (spoly.contains(pt) or spoly.exterior.distance(pt) < 0.05):
            target_slab = s
            break

    if not target_slab:
        target_slab = {
            "id": target_bay["id"],
            "polygon": target_bay["polygon"],
            "center_x": target_bay["center"][0],
            "center_y": target_bay["center"][1],
            "axis_span_m": target_bay["lx"] if target_bay["default_rib_direction_deg"] == 0.0 else target_bay["ly"],
            "rib_direction_deg": target_bay["default_rib_direction_deg"],
            "bay_type": target_bay["bay_type"],
            "is_cantilever": False,
        }
        slabs.append(target_slab)

    if bay_type == "4_beam":
        new_deg = 90.0 if float(target_slab.get("rib_direction_deg", 0.0)) == 0.0 else 0.0
        target_slab["rib_direction_deg"] = new_deg
        target_slab["axis_span_m"] = target_bay["ly"] if new_deg == 90.0 else target_bay["lx"]
        return True, f"Flipped 4-Beam Slab {target_slab['id']} ribs to {new_deg:.0f}°.", slabs

    if bay_type == "3_beam":
        currently_cant = bool(target_slab.get("is_cantilever", False))
        if not currently_cant:
            free_side = target_bay.get("free_side", "EAST")
            carrying_side = target_bay.get("carrying_side", "WEST")
            cant_rib_deg = 0.0 if free_side in ("EAST", "WEST") else 90.0

            minx, miny, maxx, maxy = target_bay["bounds"]
            if carrying_side == "WEST":
                probe_pt = Point(minx - 0.5, (miny + maxy) / 2.0)
            elif carrying_side == "EAST":
                probe_pt = Point(maxx + 0.5, (miny + maxy) / 2.0)
            elif carrying_side == "SOUTH":
                probe_pt = Point((minx + maxx) / 2.0, miny - 0.5)
            else:  # NORTH
                probe_pt = Point((minx + maxx) / 2.0, maxy + 0.5)

            back_bay = None
            for b in bays:
                if b["id"] != target_bay["id"]:
                    bpoly = Polygon(b["polygon"])
                    if bpoly.contains(probe_pt) or bpoly.exterior.distance(probe_pt) < 0.10:
                        back_bay = b
                        break

            if not back_bay:
                return False, (
                    f"Cantilever Equilibrium Violation: Cannot flip to cantilever slab. "
                    f"No adjacent back-span bay exists behind carrying beam on {carrying_side} side."
                ), slabs

            for op in openings:
                op_poly = Polygon(op.get("polygon", [])) if op.get("polygon") else None
                if op_poly and (op_poly.contains(probe_pt) or op_poly.exterior.distance(probe_pt) < 0.10):
                    return False, (
                        f"Cantilever Equilibrium Violation: Cannot flip to cantilever slab. "
                        f"The adjacent back-span area behind carrying beam ({carrying_side}) is a Void Opening [00-XD-OPEN]."
                    ), slabs

            back_slab = None
            for s in slabs:
                spoly = Polygon(s.get("polygon", [])) if s.get("polygon") else None
                if spoly and (spoly.contains(probe_pt) or spoly.exterior.distance(probe_pt) < 0.10):
                    back_slab = s
                    break

            if not back_slab:
                back_slab = {
                    "id": back_bay["id"],
                    "polygon": back_bay["polygon"],
                    "center_x": back_bay["center"][0],
                    "center_y": back_bay["center"][1],
                    "axis_span_m": back_bay["lx"] if cant_rib_deg == 0.0 else back_bay["ly"],
                    "rib_direction_deg": cant_rib_deg,
                    "bay_type": back_bay["bay_type"],
                    "is_cantilever": False,
                }
                slabs.append(back_slab)

            target_slab["rib_direction_deg"] = cant_rib_deg
            target_slab["is_cantilever"] = True
            target_slab["cantilever_direction"] = free_side
            target_slab["carrying_beam_id"] = target_bay.get("carrying_beam_id")

            back_slab["rib_direction_deg"] = cant_rib_deg
            back_slab["connected_to_cantilever"] = True
            back_slab["supports_cantilever_for"] = target_slab["id"]

            return True, (
                f"Flipped to Cantilever Slab {target_slab['id']} pointing {free_side}. "
                f"Back-Span Slab {back_slab['id']} ribs automatically synchronized to {cant_rib_deg:.0f}° for structural equilibrium."
            ), slabs
        else:
            def_deg = target_bay["default_rib_direction_deg"]
            target_slab["rib_direction_deg"] = def_deg
            target_slab["is_cantilever"] = False
            target_slab["cantilever_direction"] = None
            target_slab["carrying_beam_id"] = None

            for s in slabs:
                if s.get("supports_cantilever_for") == target_slab["id"]:
                    s["supports_cantilever_for"] = None
                    s["connected_to_cantilever"] = False

            return True, f"Restored 3-Beam Slab {target_slab['id']} to supported ribs at {def_deg:.0f}°.", slabs

    curr = float(target_slab.get("rib_direction_deg", 0.0))
    target_slab["rib_direction_deg"] = 90.0 if curr == 0.0 else 0.0
    return True, f"Toggled Slab {target_slab['id']} ribs to {target_slab['rib_direction_deg']:.0f}°.", slabs


def toggle_bay_slab_or_opening(
    click_pt: Tuple[float, float],
    slab_edge_polygon: List[List[float]],
    beams: List[Dict[str, Any]],
    slabs: List[Dict[str, Any]],
    openings: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Step 4C: Pick: Toggle Slab <-> Opening [00-XD-OPEN].
    - Converts solid slab to void opening with diagonal X, OR vice-versa.
    - Cantilever Protection Rule: Strictly prohibits converting any slab that acts
      as a back-span for an active cantilever slab into an opening.
    """
    openings = list(openings or [])
    slabs = list(slabs or [])
    bays = detect_bays_and_determine_ribs(slab_edge_polygon, beams, slabs, openings)

    target_bay = None
    pt = Point(click_pt[0], click_pt[1])
    for b in bays:
        poly = Polygon(b["polygon"])
        if poly.contains(pt) or poly.exterior.distance(pt) < 0.05:
            target_bay = b
            break

    if not target_bay:
        return False, f"Click at ({click_pt[0]:.2f}, {click_pt[1]:.2f}) is outside any closed bay.", slabs, openings

    is_op = False
    op_match_idx = None
    for idx, op in enumerate(openings):
        op_poly = Polygon(op.get("polygon", [])) if op.get("polygon") else None
        if op_poly and (op_poly.contains(pt) or op_poly.exterior.distance(pt) < 0.05):
            is_op = True
            op_match_idx = idx
            break

    if is_op and op_match_idx is not None:
        openings.pop(op_match_idx)
        new_slab = {
            "id": target_bay["id"],
            "polygon": target_bay["polygon"],
            "center_x": target_bay["center"][0],
            "center_y": target_bay["center"][1],
            "axis_span_m": target_bay["lx"] if target_bay["default_rib_direction_deg"] == 0.0 else target_bay["ly"],
            "rib_direction_deg": target_bay["default_rib_direction_deg"],
            "bay_type": target_bay["bay_type"],
            "is_cantilever": False,
        }
        slabs.append(new_slab)
        return True, f"Converted Void Opening to Solid Slab {new_slab['id']} [00-XD-SLAB].", slabs, openings

    # Protection check: Does this slab act as back-span for any cantilever?
    for s in slabs:
        spoly = Polygon(s.get("polygon", [])) if s.get("polygon") else None
        if spoly and (spoly.contains(pt) or spoly.exterior.distance(pt) < 0.05):
            if s.get("supports_cantilever_for"):
                cant_id = s.get("supports_cantilever_for")
                return False, (
                    f"Structural Equilibrium Restriction: Cannot convert Slab {s['id']} to an Opening. "
                    f"This slab serves as the balancing back-span for Cantilever Slab {cant_id}."
                ), slabs, openings

    for b in bays:
        if b.get("is_cantilever") and b.get("supports_cantilever_for") == target_bay["id"]:
            return False, (
                f"Structural Equilibrium Restriction: Cannot convert bay to an Opening. "
                f"It is required as the balancing back-span for Cantilever Slab {b['id']}."
            ), slabs, openings

    slabs = [
        s for s in slabs
        if not (Polygon(s.get("polygon", [])).contains(pt) if s.get("polygon") else False)
    ]

    openings.append({
        "id": f"OPEN_{target_bay['id']}",
        "polygon": target_bay["polygon"],
        "center_x": target_bay["center"][0],
        "center_y": target_bay["center"][1],
    })

    return True, f"Converted bay to Void Opening {target_bay['id']} [00-XD-OPEN].", slabs, openings


def move_column_and_update_connected_beams(
    col_id: str,
    new_x: float,
    new_y: float,
    columns: List[Dict[str, Any]],
    beams: List[Dict[str, Any]],
    slab_edge_polygon: List[List[float]],
    rule: str = "clamp",
) -> Tuple[bool, str, List[Dict[str, Any]], List[Dict[str, Any]], List[List[float]]]:
    """
    Moves column col_id to (new_x, new_y) applying slab boundary rule (clamp or expand).
    Automatically updates start/end coordinates and spans for all beams connected to this column.
    """
    target_col = None
    for c in columns:
        if c.get("id") == col_id:
            target_col = c
            break

    if not target_col:
        return False, f"Column {col_id} not found.", columns, beams, slab_edge_polygon

    b_m = float(target_col.get("b_m", 0.25))
    h_m = float(target_col.get("h_m", 0.50))
    old_x, old_y = float(target_col["x"]), float(target_col["y"])

    final_x, final_y, updated_poly, _ = clamp_or_expand_column_boundary(
        new_x, new_y, b_m, h_m, slab_edge_polygon, rule=rule
    )

    target_col["x"] = final_x
    target_col["y"] = final_y

    col_map = {c["id"]: (float(c["x"]), float(c["y"])) for c in columns}
    updated_beams_count = 0

    for bm in beams:
        bm_modified = False
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))

        if ((sx - old_x) ** 2 + (sy - old_y) ** 2) ** 0.5 <= max(b_m, h_m):
            bm["start_x"] = final_x
            bm["start_y"] = final_y
            bm_modified = True

        if ((ex - old_x) ** 2 + (ey - old_y) ** 2) ** 0.5 <= max(b_m, h_m):
            bm["end_x"] = final_x
            bm["end_y"] = final_y
            bm_modified = True

        for sup in bm.get("supports", []):
            if sup.get("target_id") == col_id:
                sup["x"] = final_x
                sup["y"] = final_y
                bm_modified = True

        if bm_modified:
            updated_beams_count += 1
            pts = []
            for sup in bm.get("supports", []):
                tid = sup.get("target_id")
                if tid in col_map:
                    pts.append(col_map[tid])
            if len(pts) >= 2:
                bm["spans"] = [
                    round(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5, 2)
                    for i in range(len(pts) - 1)
                ]
            else:
                total_len = ((float(bm["end_x"]) - float(bm["start_x"])) ** 2 + (float(bm["end_y"]) - float(bm["start_y"])) ** 2) ** 0.5
                bm["spans"] = [round(total_len, 2)]

    return (
        True,
        f"Moved Column {col_id} to ({final_x:.2f}, {final_y:.2f}) m. Updated {updated_beams_count} connected beam(s).",
        columns,
        beams,
        updated_poly,
    )


def move_beam_and_update(
    beam_id: str,
    dx: float,
    dy: float,
    beams: List[Dict[str, Any]],
    slab_edge_polygon: List[List[float]],
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Moves beam beam_id by (dx, dy) while enforcing that it stays inside slab_edge_polygon.
    """
    target_beam = None
    for b in beams:
        if b.get("id") == beam_id:
            target_beam = b
            break

    if not target_beam:
        return False, f"Beam {beam_id} not found.", beams

    new_sx = float(target_beam["start_x"]) + dx
    new_sy = float(target_beam["start_y"]) + dy
    new_ex = float(target_beam["end_x"]) + dx
    new_ey = float(target_beam["end_y"]) + dy

    if slab_edge_polygon and len(slab_edge_polygon) >= 3 and Polygon is not None:
        poly = Polygon(slab_edge_polygon)
        if poly.distance(Point(new_sx, new_sy)) > 0.10 or poly.distance(Point(new_ex, new_ey)) > 0.10:
            return False, f"Cannot move Beam {beam_id}: Move would place beam outside outer slab boundary [00-XD-EDGE].", beams

    target_beam["start_x"] = round(new_sx, 3)
    target_beam["start_y"] = round(new_sy, 3)
    target_beam["end_x"] = round(new_ex, 3)
    target_beam["end_y"] = round(new_ey, 3)

    for sup in target_beam.get("supports", []):
        if "x" in sup and "y" in sup:
            sup["x"] = round(sup["x"] + dx, 3)
            sup["y"] = round(sup["y"] + dy, 3)

    return True, f"Moved Beam {beam_id} by ({dx:.2f}, {dy:.2f}) m.", beams


def clamp_beam_inside_boundary(
    beam: Dict[str, Any],
    slab_edge_polygon: List[List[float]],
    tolerance_m: float = 0.005,
) -> Tuple[Dict[str, Any], bool]:
    """
    Checks if any lateral edge of a full-width beam rectangle (width_m)
    protrudes outside the slab_edge_polygon.
    If protruding, automatically shifts the beam centerline inward perpendicular
    to the beam axis by the protrusion distance so the outer face is flush with
    the building boundary (analogous to column clamping).
    Returns (updated_beam_dict, was_modified).
    """
    if not slab_edge_polygon or len(slab_edge_polygon) < 3 or Polygon is None:
        return beam, False

    edge_poly = Polygon(slab_edge_polygon)
    if not edge_poly.is_valid:
        return beam, False

    updated_beam = dict(beam)
    sx = float(updated_beam.get("start_x", 0.0))
    sy = float(updated_beam.get("start_y", 0.0))
    ex = float(updated_beam.get("end_x", 5.0))
    ey = float(updated_beam.get("end_y", 0.0))

    b_kind = updated_beam.get("beam_kind", "hidden")
    def_w = 0.40 if b_kind == "hidden" else 0.20
    width_m = float(updated_beam.get("width_m", def_w))
    half_w = width_m / 2.0

    dx = ex - sx
    dy = ey - sy
    length = (dx * dx + dy * dy) ** 0.5
    if length < 0.05:
        return beam, False

    ux = dx / length
    uy = dy / length
    # Normal vector perpendicular to beam axis
    nx = -uy
    ny = ux

    # Sample points along both lateral edges: Side 1 (+n * half_w) and Side 2 (-n * half_w)
    sample_ts = [0.0, 0.25, 0.5, 0.75, 1.0]
    side1_protrusion = 0.0
    side2_protrusion = 0.0

    for t in sample_ts:
        mx = sx + ux * (length * t)
        my = sy + uy * (length * t)

        p1 = Point(mx + nx * half_w, my + ny * half_w)
        if not edge_poly.contains(p1) and edge_poly.exterior.distance(p1) > tolerance_m:
            dist = edge_poly.distance(p1)
            if dist > side1_protrusion:
                side1_protrusion = dist

        p2 = Point(mx - nx * half_w, my - ny * half_w)
        if not edge_poly.contains(p2) and edge_poly.exterior.distance(p2) > tolerance_m:
            dist = edge_poly.distance(p2)
            if dist > side2_protrusion:
                side2_protrusion = dist

    shift_x = 0.0
    shift_y = 0.0
    was_modified = False

    if side1_protrusion > tolerance_m and side2_protrusion <= tolerance_m:
        # Shift inward in direction -n
        shift_amount = min(half_w, side1_protrusion)
        shift_x = -nx * shift_amount
        shift_y = -ny * shift_amount
        was_modified = True
    elif side2_protrusion > tolerance_m and side1_protrusion <= tolerance_m:
        # Shift inward in direction +n
        shift_amount = min(half_w, side2_protrusion)
        shift_x = nx * shift_amount
        shift_y = ny * shift_amount
        was_modified = True

    if was_modified:
        updated_beam["start_x"] = round(sx + shift_x, 3)
        updated_beam["start_y"] = round(sy + shift_y, 3)
        updated_beam["end_x"] = round(ex + shift_x, 3)
        updated_beam["end_y"] = round(ey + shift_y, 3)
        if "supports" in updated_beam:
            for sup in updated_beam["supports"]:
                if "x" in sup and "y" in sup:
                    sup["x"] = round(sup["x"] + shift_x, 3)
                    sup["y"] = round(sup["y"] + shift_y, 3)

    return updated_beam, was_modified


def delete_selected_element_from_story(
    story_data: Dict[str, Any],
    element: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Deletes a selected element from the story data:
    - "column": removes column, unlinks and recalculates spans of connected beams.
    - "beam": removes beam from beams list.
    - "slab": checks cantilever equilibrium: if an adjacent cantilever relies on this
      slab for negative moment equilibrium, deletion is blocked!
    - "opening": removes opening from openings list.
    - "edge": clears slab_edge_polygon.
    Returns (ok, message).
    """
    if not element or "type" not in element:
        return False, "No element selected for deletion."

    elem_type = str(element.get("type", "")).lower()
    elem_id = str(element.get("id", ""))

    if elem_type == "column":
        cols = story_data.get("columns", [])
        matched = [c for c in cols if str(c.get("id")) == elem_id]
        if not matched:
            return False, f"Column {elem_id} not found."
        story_data["columns"] = [c for c in cols if str(c.get("id")) != elem_id]

        # Update connected beams
        for bm in story_data.get("beams", []):
            old_sups = bm.get("supports", [])
            new_sups = [s for s in old_sups if str(s.get("target_id")) != elem_id]
            if len(new_sups) != len(old_sups):
                for s_i, sup in enumerate(new_sups):
                    sup["support_index"] = s_i + 1
                bm["supports"] = new_sups
                if len(new_sups) >= 2:
                    new_spans = []
                    for s_i in range(len(new_sups) - 1):
                        p1 = (new_sups[s_i]["x"], new_sups[s_i]["y"])
                        p2 = (new_sups[s_i + 1]["x"], new_sups[s_i + 1]["y"])
                        new_spans.append(round(((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5, 2))
                    bm["spans"] = new_spans
                else:
                    bm_len = ((bm["end_x"] - bm["start_x"])**2 + (bm["end_y"] - bm["start_y"])**2)**0.5
                    bm["spans"] = [round(bm_len, 2)]

        return True, f"Deleted Column {elem_id} and updated connected beams."

    elif elem_type == "beam":
        bms = story_data.get("beams", [])
        matched = [b for b in bms if str(b.get("id")) == elem_id]
        if not matched:
            return False, f"Beam {elem_id} not found."
        story_data["beams"] = [b for b in bms if str(b.get("id")) != elem_id]
        return True, f"Deleted Beam {elem_id}."

    elif elem_type == "slab":
        slabs = story_data.get("slabs", [])
        target_slab = None
        for s in slabs:
            if str(s.get("id")) == elem_id:
                target_slab = s
                break
        if target_slab:
            if target_slab.get("supports_cantilever_for"):
                return False, (
                    f"Cannot delete Slab {elem_id}: It acts as the back-span moment anchor "
                    f"for Cantilever Slab {target_slab['supports_cantilever_for']}."
                )

        story_data["slabs"] = [s for s in slabs if str(s.get("id")) != elem_id]
        return True, f"Deleted Slab {elem_id}."

    elif elem_type == "opening":
        ops = story_data.get("openings", [])
        if "id" in element and element["id"]:
            story_data["openings"] = [op for op in ops if str(op.get("id")) != elem_id]
        elif "point" in element:
            px, py = element["point"]
            story_data["openings"] = [
                op for op in ops
                if not (Polygon(op.get("polygon", [])).contains(Point(px, py)) if op.get("polygon") else False)
            ]
        return True, "Deleted Opening [00-XD-OPEN]."

    elif elem_type in ("edge", "boundary"):
        story_data["slab_edge_polygon"] = []
        return True, "Deleted Outer Slab Boundary [00-XD-EDGE]."

    return False, f"Unknown element type: {elem_type}."
