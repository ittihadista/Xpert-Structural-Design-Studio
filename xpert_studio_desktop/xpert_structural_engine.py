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
) -> Optional[str]:
    """
    Verifies if a new or moved column at (x, y) with dimensions (b_m, h_m)
    collides with or duplicates an existing column.
    Returns the colliding column ID if duplicate/collision detected, else None.
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
            return cid

        # Or heavy bounding box overlap
        overlap_x = max(0.0, (b_m + cb) / 2.0 - dx)
        overlap_y = max(0.0, (h_m + ch) / 2.0 - dy)
        if overlap_x > 0.6 * min(b_m, cb) and overlap_y > 0.6 * min(h_m, ch):
            return cid

    return None


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
    dup_col_id = check_duplicate_column(final_x, final_y, new_b, new_h, columns, ignore_id=col_id)
    if dup_col_id:
        return False, f"Cannot rotate: Column collides with {dup_col_id}."

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




def get_slab_bounding_box(slab_edge_polygon: List[List[float]]) -> Tuple[bool, float, float, float, float]:
    """
    Returns (has_boundary, min_x, min_y, max_x, max_y) for the outer slab boundary polyline.
    """
    if not slab_edge_polygon or len(slab_edge_polygon) < 3:
        return False, 0.0, 0.0, 0.0, 0.0
    xs = [float(p[0]) for p in slab_edge_polygon]
    ys = [float(p[1]) for p in slab_edge_polygon]
    return True, min(xs), min(ys), max(xs), max(ys)


def enforce_column_inside_slab_boundary(
    col: Dict[str, Any],
    slab_edge_polygon: List[List[float]],
    mode: str = "clamp",
) -> Tuple[Dict[str, Any], List[List[float]], str]:
    """
    Enforces that column center and body stay inside the slab boundary.
    """
    c = dict(col)
    cx = float(c.get("x", 0.0))
    cy = float(c.get("y", 0.0))
    b = float(c.get("b_m", 0.25))
    h = float(c.get("h_m", 0.50))
    final_x, final_y, updated_poly, msg = clamp_or_expand_column_boundary(
        cx, cy, b, h, slab_edge_polygon, rule=mode
    )
    c["x"] = final_x
    c["y"] = final_y
    return c, updated_poly, msg


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
    existing_by_bay_key = {s.get("bay_key"): s for s in existing_slabs if "bay_key" in s}

    new_slabs: List[Dict[str, Any]] = []
    count_added = 0

    for idx, bay in enumerate(bays):
        bkey = bay["bay_key"]
        min_x, max_x = bay["min_x"], bay["max_x"]
        min_y, max_y = bay["min_y"], bay["max_y"]
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0

        # Check if inside opening
        is_op = False
        for op in openings:
            op_min_x = float(op.get("min_x", op.get("polygon", [[0,0]])[0][0]))
            op_max_x = float(op.get("max_x", op.get("polygon", [[0,0]])[1][0] if len(op.get("polygon", [])) > 1 else op_min_x))
            op_min_y = float(op.get("min_y", op.get("polygon", [[0,0]])[0][1]))
            op_max_y = float(op.get("max_y", op.get("polygon", [[0,0]])[2][1] if len(op.get("polygon", [])) > 2 else op_min_y))
            if (min_x >= op_min_x - 0.1) and (max_x <= op_max_x + 0.1) and (min_y >= op_min_y - 0.1) and (max_y <= op_max_y + 0.1):
                is_op = True
                break
        if is_op:
            continue

        matched = existing_by_bay_key.get(bkey)
        if not matched:
            for s in existing_slabs:
                scx = (float(s.get("min_x", 0)) + float(s.get("max_x", 0))) / 2.0
                scy = (float(s.get("min_y", 0)) + float(s.get("max_y", 0))) / 2.0
                if abs(scx - cx) < 0.2 and abs(scy - cy) < 0.2:
                    matched = s
                    break

        lx = bay["lx_m"]
        ly = bay["ly_m"]
        rib_dir = 0.0 if lx <= ly else 90.0

        if matched:
            matched["bay_key"] = bkey
            matched["min_x"] = min_x
            matched["max_x"] = max_x
            matched["min_y"] = min_y
            matched["max_y"] = max_y
            matched["clear_min_x"] = bay["clear_min_x"]
            matched["clear_max_x"] = bay["clear_max_x"]
            matched["clear_min_y"] = bay["clear_min_y"]
            matched["clear_max_y"] = bay["clear_max_y"]
            matched["lx_m"] = lx
            matched["ly_m"] = ly
            matched["axis_span_m"] = lx if matched.get("rib_direction_deg", rib_dir) == 0.0 else ly
            new_slabs.append(matched)
        else:
            slab_id = f"S{len(new_slabs) + 1}"
            new_slabs.append({
                "id": slab_id,
                "bay_key": bkey,
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
                "clear_min_x": bay["clear_min_x"],
                "clear_max_x": bay["clear_max_x"],
                "clear_min_y": bay["clear_min_y"],
                "clear_max_y": bay["clear_max_y"],
                "lx_m": lx,
                "ly_m": ly,
                "axis_span_m": lx if rib_dir == 0.0 else ly,
                "rib_direction_deg": rib_dir,
                "left_support_w_m": 0.30,
                "right_support_w_m": 0.30,
                "is_cantilever": False,
                "is_opening": False,
            })
            count_added += 1

    story["slabs"] = new_slabs
    evaluate_story_thickness_and_optimization(story)
    return count_added, f"Auto-filled {count_added} new slab bays (Total: {len(new_slabs)} active slabs)."


def pick_area_create_or_update_slab(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    target_mode: str = "SLAB",
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Step 4A: Pick Area: Slab or Toggle Opening.
    Detects the bay enclosing (click_x, click_y).
    Includes clear_min_x, clear_max_x, clear_min_y, clear_max_y.
    """
    bays = detect_story_grid_bays(story_data)
    target_bay = None
    for b in bays:
        if (b["min_x"] - 0.05 <= click_x <= b["max_x"] + 0.05) and (b["min_y"] - 0.05 <= click_y <= b["max_y"] + 0.05):
            target_bay = b
            break

    if not target_bay:
        return False, f"Click at ({click_x:.2f}, {click_y:.2f}) is outside any closed grid bay.", None

    openings = story_data.setdefault("openings", [])
    slabs = story_data.setdefault("slabs", [])
    bkey = target_bay["bay_key"]
    lx, ly = target_bay["lx_m"], target_bay["ly_m"]

    if target_mode == "TOGGLE_OPENING":
        op_idx = None
        for idx, op in enumerate(openings):
            if op.get("bay_key") == bkey or (
                float(op.get("min_x", -999)) <= click_x <= float(op.get("max_x", -999)) and
                float(op.get("min_y", -999)) <= click_y <= float(op.get("max_y", -999))
            ):
                op_idx = idx
                break

        if op_idx is not None:
            openings.pop(op_idx)
            return True, f"Removed Opening at {bkey}.", None
        else:
            story_data["slabs"] = [s for s in slabs if s.get("bay_key") != bkey]
            op_record = {
                "id": f"OP_{bkey}",
                "bay_key": bkey,
                "min_x": target_bay["min_x"],
                "max_x": target_bay["max_x"],
                "min_y": target_bay["min_y"],
                "max_y": target_bay["max_y"],
                "clear_min_x": target_bay.get("clear_min_x", target_bay["min_x"]),
                "clear_max_x": target_bay.get("clear_max_x", target_bay["max_x"]),
                "clear_min_y": target_bay.get("clear_min_y", target_bay["min_y"]),
                "clear_max_y": target_bay.get("clear_max_y", target_bay["max_y"]),
                "polygon": [
                    [target_bay["min_x"], target_bay["min_y"]],
                    [target_bay["max_x"], target_bay["min_y"]],
                    [target_bay["max_x"], target_bay["max_y"]],
                    [target_bay["min_x"], target_bay["max_y"]],
                ],
            }
            openings.append(op_record)
            return True, f"Converted bay to Opening [00-XD-OPEN].", op_record

    story_data["openings"] = [
        op for op in openings
        if op.get("bay_key") != bkey and not (
            float(op.get("min_x", -999)) <= click_x <= float(op.get("max_x", -999)) and
            float(op.get("min_y", -999)) <= click_y <= float(op.get("max_y", -999))
        )
    ]

    existing_idx = None
    for idx, s in enumerate(slabs):
        if s.get("bay_key") == bkey or (
            float(s.get("min_x", -999)) <= click_x <= float(s.get("max_x", -999)) and
            float(s.get("min_y", -999)) <= click_y <= float(s.get("max_y", -999))
        ):
            existing_idx = idx
            break

    rib_dir = 0.0 if lx <= ly else 90.0
    slab_obj = {
        "id": f"S{existing_idx + 1}" if existing_idx is not None else f"S{len(slabs) + 1}",
        "bay_key": bkey,
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
        "rib_direction_deg": rib_dir if existing_idx is None else slabs[existing_idx].get("rib_direction_deg", rib_dir),
        "axis_span_m": lx if rib_dir == 0.0 else ly,
        "left_support_w_m": 0.30,
        "right_support_w_m": 0.30,
        "is_cantilever": False,
        "is_opening": False,
    }

    if existing_idx is not None:
        slabs[existing_idx] = slab_obj
    else:
        slabs.append(slab_obj)

    evaluate_story_thickness_and_optimization(story_data)
    return True, f"Assigned Slab {slab_obj['id']}: Ribs at {slab_obj['rib_direction_deg']:.0f}°.", slab_obj


def toggle_slab_rib_by_label_click(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    hit_radius_m: float = 0.50,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Toggles rib direction (0° <-> 90°) for the slab clicked at or near (click_x, click_y).
    """
    slabs = story_data.get("slabs", [])
    target_slab = None
    for s in slabs:
        min_x, max_x = float(s.get("min_x", 0)), float(s.get("max_x", 0))
        min_y, max_y = float(s.get("min_y", 0)), float(s.get("max_y", 0))
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        if ((click_x - cx) ** 2 + (click_y - cy) ** 2) ** 0.5 <= hit_radius_m or (
            (min_x - 0.05 <= click_x <= max_x + 0.05) and (min_y - 0.05 <= click_y <= max_y + 0.05)
        ):
            target_slab = s
            break

    if not target_slab:
        return False, "", None

    cur_dir = float(target_slab.get("rib_direction_deg", 0.0))
    new_dir = 90.0 if cur_dir == 0.0 else 0.0
    target_slab["rib_direction_deg"] = new_dir
    lx = float(target_slab.get("lx_m", target_slab.get("axis_span_m", 4.0)))
    ly = float(target_slab.get("ly_m", target_slab.get("axis_span_m", 4.0)))
    target_slab["axis_span_m"] = ly if new_dir == 90.0 else lx

    evaluate_story_thickness_and_optimization(story_data)
    return True, f"Slab {target_slab.get('id', 'S')} ribs flipped to {new_dir:.0f}°.", target_slab


def move_column_and_sync_connected_beams(
    story_data: Dict[str, Any],
    col_id: str,
    new_x: float,
    new_y: float,
    boundary_mode: str = "clamp",
) -> Tuple[bool, str]:
    """
    Moves column and automatically synchronizes all connected beam ends and intermediate supports.
    """
    cols = story_data.get("columns", [])
    beams = story_data.get("beams", [])
    poly = story_data.get("slab_edge_polygon", [])
    ok, msg, updated_cols, updated_beams, updated_poly = move_column_and_update_connected_beams(
        col_id, new_x, new_y, cols, beams, poly, rule=boundary_mode
    )
    if ok:
        story_data["columns"] = updated_cols
        story_data["beams"] = updated_beams
        story_data["slab_edge_polygon"] = updated_poly
    return ok, msg


def move_beam_within_slab_boundary(
    story_data: Dict[str, Any],
    beam_id: str,
    dx: float,
    dy: float,
) -> Tuple[bool, str]:
    """
    Moves beam while enforcing that it stays within outer slab boundary.
    """
    beams = story_data.get("beams", [])
    poly = story_data.get("slab_edge_polygon", [])
    ok, msg, updated_beams = move_beam_and_update(beam_id, dx, dy, beams, poly)
    if ok:
        story_data["beams"] = updated_beams
    return ok, msg



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

    supports_raw: List[Dict[str, Any]] = []
    snap_tol = max(0.45, half_w + 0.25)

    for col in active_cols:
        cx, cy = float(col["x"]), float(col["y"])
        b_col = float(col.get("b_m", 0.20))
        h_col = float(col.get("h_m", 0.40))
        if is_horizontal:
            if abs(cy - sy) <= max(snap_tol, h_col / 2.0 + half_w + 0.08) and (sx - b_col / 2.0 - 0.30) <= cx <= (ex + b_col / 2.0 + 0.30):
                supports_raw.append({
                    "coord": cx,
                    "x": cx,
                    "y": sy,
                    "kind": "column",
                    "target_id": col["id"],
                    "width_m": b_col,
                })
        else:
            if abs(cx - sx) <= max(snap_tol, b_col / 2.0 + half_w + 0.08) and (sy - h_col / 2.0 - 0.30) <= cy <= (ey + h_col / 2.0 + 0.30):
                supports_raw.append({
                    "coord": cy,
                    "x": sx,
                    "y": cy,
                    "kind": "column",
                    "target_id": col["id"],
                    "width_m": h_col,
                })

    for ob in existing_beams:
        if ob.get("id") == beam_id:
            continue
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        ob_horiz = abs(oex - osx) >= abs(oey - osy)
        if is_horizontal and not ob_horiz:
            bx = osx
            if (sx - 0.25) <= bx <= (ex + 0.25) and min(osy, oey) - 0.25 <= sy <= max(osy, oey) + 0.25:
                if not any(abs(s["coord"] - bx) < 0.30 for s in supports_raw):
                    supports_raw.append({
                        "coord": bx,
                        "x": bx,
                        "y": sy,
                        "kind": "beam",
                        "target_id": ob["id"],
                        "width_m": float(ob.get("width_m", 0.30)),
                        "pos_on_carrier_m": round(abs(sy - min(osy, oey)), 3),
                    })
        elif not is_horizontal and ob_horiz:
            by = osy
            if (sy - 0.25) <= by <= (ey + 0.25) and min(osx, oex) - 0.25 <= sx <= max(osx, oex) + 0.25:
                if not any(abs(s["coord"] - by) < 0.30 for s in supports_raw):
                    supports_raw.append({
                        "coord": by,
                        "x": sx,
                        "y": by,
                        "kind": "beam",
                        "target_id": ob["id"],
                        "width_m": float(ob.get("width_m", 0.30)),
                        "pos_on_carrier_m": round(abs(sx - min(osx, oex)), 3),
                    })

    supports_raw.sort(key=lambda s: s["coord"])
    if len(supports_raw) == 0:
        return False, None, "Beam must rest on at least one Column or Supporting Beam."

    # REVIT FULL-COLUMN-FACE EXTENSION:
    first_sup = supports_raw[0]
    last_sup = supports_raw[-1]
    first_outer_edge = round(first_sup["coord"] - float(first_sup["width_m"]) / 2.0, 3)
    last_outer_edge = round(last_sup["coord"] + float(last_sup["width_m"]) / 2.0, 3)

    if is_horizontal:
        if sx >= first_outer_edge - 0.05 and abs(sx - first_sup["coord"]) <= float(first_sup["width_m"]) + 0.25:
            sx = max(min_x, first_outer_edge)
        if ex <= last_outer_edge + 0.05 and abs(ex - last_sup["coord"]) <= float(last_sup["width_m"]) + 0.25:
            ex = min(max_x, last_outer_edge)
        sx = round(min(max(sx, min_x), max_x), 3)
        ex = round(min(max(ex, min_x), max_x), 3)
    else:
        if sy >= first_outer_edge - 0.05 and abs(sy - first_sup["coord"]) <= float(first_sup["width_m"]) + 0.25:
            sy = max(min_y, first_outer_edge)
        if ey <= last_outer_edge + 0.05 and abs(ey - last_sup["coord"]) <= float(last_sup["width_m"]) + 0.25:
            ey = min(max_y, last_outer_edge)
        sy = round(min(max(sy, min_y), max_y), 3)
        ey = round(min(max(ey, min_y), max_y), 3)

    total_len = round(math.hypot(ex - sx, ey - sy), 3)
    if total_len < 0.40:
        return False, None, "Beam length is too short (< 0.40 m)."

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


def detect_story_grid_bays(story_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Revit Room-Bounding Bay Detection:
    - NEVER creates slab bays from the Outer Building Boundary alone! At least 3 beams must exist
      before any slab bay can be formed.
    - Subtracts the physical footprint (`width_m / 2`) of bounding North, South, East, and West beams
      to provide `clear_min_x, clear_max_x, clear_min_y, clear_max_y` so slabs and ribs NEVER draw
      over the body of any beam (`room_bounding = True`).
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))
    if not has_bnd:
        return []

    beams = story_data.get("beams", [])
    if len(beams) < 3:
        return []

    xs = [round(min_x, 3), round(max_x, 3)]
    ys = [round(min_y, 3), round(max_y, 3)]

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
        for bm in beams:
            bsx, bsy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
            bex, bey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
            b_width = float(bm.get("width_m", 0.40))
            tol_lat = max(0.48, b_width + 0.15)
            b_horiz = abs(bex - bsx) >= abs(bey - bsy)
            if is_seg_horiz and b_horiz and abs(bsy - y1) <= tol_lat:
                if min(bsx, bex) - 0.45 <= min(x1, x2) and max(bsx, bex) + 0.45 >= max(x1, x2):
                    return bm
            elif not is_seg_horiz and not b_horiz and abs(bsx - x1) <= tol_lat:
                if min(bsy, bey) - 0.45 <= min(y1, y2) and max(bsy, bey) + 0.45 >= max(y1, y2):
                    return bm
        return None

    bays: List[Dict[str, Any]] = []
    bay_counter = 1
    for j in range(len(sorted_y) - 1):
        y_bot, y_top = sorted_y[j], sorted_y[j + 1]
        ly = round(y_top - y_bot, 3)
        if ly < 0.85:
            continue
        for i in range(len(sorted_x) - 1):
            x_left, x_right = sorted_x[i], sorted_x[i + 1]
            lx = round(x_right - x_left, 3)
            if lx < 0.85:
                continue

            bm_top = has_beam_on_segment(x_left, y_top, x_right, y_top)
            bm_bot = has_beam_on_segment(x_left, y_bot, x_right, y_bot)
            bm_left = has_beam_on_segment(x_left, y_bot, x_left, y_top)
            bm_right = has_beam_on_segment(x_right, y_bot, x_right, y_top)

            bounding_sides = {
                "North": bm_top["id"] if bm_top else None,
                "South": bm_bot["id"] if bm_bot else None,
                "West": bm_left["id"] if bm_left else None,
                "East": bm_right["id"] if bm_right else None,
            }
            beam_count = sum(1 for v in bounding_sides.values() if v is not None)

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
                "bay_key": f"BAY_{i}_{j}",
                "default_id": f"S{bay_counter}",
                "grid_i": i,
                "grid_j": j,
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
                "beam_count": beam_count,
            })
            bay_counter += 1
    return bays


def reconcile_and_split_slabs_after_beam_change(story_data: Dict[str, Any]) -> Tuple[int, str]:
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
            rib_dir = old_dir
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
                "is_cantilever": bool(old_s.get("is_cantilever", False)) if len(matching_bays) == 1 else False,
                "connected_to_cantilever": bool(old_s.get("connected_to_cantilever", False)),
                "backspan_bay_key": old_s.get("backspan_bay_key") if len(matching_bays) == 1 else None,
            })

    story_data["slabs"] = reconciled_slabs
    if split_count > 0:
        return split_count, f"Automatically split existing slab into {len(reconciled_slabs)} independent bays along the new dividing beam."
    return 0, ""




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


def select_elements_by_box(
    story_data: Dict[str, Any],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    crossing: Optional[bool] = None,
) -> List[Tuple[str, str]]:
    """
    AutoCAD / Revit Window & Crossing Selection:
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
        lock_tag = " [LOCKED 🔒]" if lock_constraint else " [UNLOCKED 🔓]"
        return ok, f"Aligned Column {target_id} ({face} face) to {axis.upper()} = {rc:.2f} m.{lock_tag} {msg}"

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
        lock_tag = " [LOCKED 🔒]" if lock_constraint else " [UNLOCKED 🔓]"
        return ok, f"Aligned Beam {target_id} ({face} face) to {axis.upper()} = {rc:.2f} m.{lock_tag} {msg}"

    return False, f"Unsupported element kind '{target_kind}' for Align."


def move_selected_elements_by_delta(
    story_data: Dict[str, Any],
    selected_items: List[Tuple[str, str]],
    dx: float,
    dy: float,
    boundary_mode: str = "clamp",
) -> Tuple[int, str]:
    if not selected_items:
        return 0, "No elements selected to move."

    moved_count = 0
    moved_col_ids = {eid for kind, eid in selected_items if kind == "column"}

    for kind, eid in selected_items:
        if kind == "column":
            col = next((c for c in story_data.get("columns", []) if c.get("id") == eid), None)
            if col:
                ok, _ = move_column_and_sync_connected_beams(
                    story_data, eid, float(col["x"]) + dx, float(col["y"]) + dy, boundary_mode=boundary_mode
                )
                if ok:
                    moved_count += 1
        elif kind == "beam":
            bm = next((b for b in story_data.get("beams", []) if b.get("id") == eid), None)
            if bm:
                sup_cols = {s.get("target_id") for s in bm.get("supports", []) if s.get("kind") == "column"}
                if not (sup_cols & moved_col_ids):
                    ok, _ = move_beam_within_slab_boundary(story_data, eid, dx, dy)
                    if ok:
                        moved_count += 1

    reconcile_and_split_slabs_after_beam_change(story_data)
    return moved_count, f"Moved {moved_count} selected element(s) by ΔX = {dx:+.2f} m, ΔY = {dy:+.2f} m."


def measure_distance_2d(p1: Tuple[float, float], p2: Tuple[float, float]) -> Dict[str, float]:
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
