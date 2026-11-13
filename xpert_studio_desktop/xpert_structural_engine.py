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
    Modes:
    - 'clamp': Automatically shifts/clamps column center (x, y) so its outer faces
               (x +/- b/2, y +/- h/2) sit flush inside the slab boundary.
    - 'expand': Expands the rectangular slab boundary to encompass the protruding column faces.
    Returns: (updated_column, updated_slab_edge_polygon, action_message)
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(slab_edge_polygon)
    if not has_bnd:
        raise ValueError("Cannot place or move columns before drawing the Outer Slab Boundary (00-XD-EDGE).")

    cx = float(col.get("x", 0.0))
    cy = float(col.get("y", 0.0))
    b = float(col.get("b_m", 0.25))
    h = float(col.get("h_m", 0.50))
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
    Validates strict beam drawing rules:
    1. Outer Slab Boundary (Polyline) must exist.
    2. Full-Width Beam Boundary Shift: Because a beam is drawn as a rectangle with full width `width_m`
       (default 0.40m for Hidden Beam, 0.20m for Drop Beam), if its outer lateral face (+/- width_m / 2)
       protrudes outside the building boundary, the beam axis is automatically shifted inward so its
       outer face sits 100% flush with the building boundary!
    3. Duplicate Overlapping Beam Prevention: Rejects drawing a beam on top of an existing collinear beam.
    4. Continuous Multi-Span Recognition from 2 Clicks: Drawing a single line from the first support
       to the last support automatically detects all intermediate columns/beams along the path!
    5. Cantilever Overhang Validation: Overhang beyond end column is valid ONLY if its tip is a Free End
       at the building perimeter.
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(slab_edge_polygon)
    if not has_bnd:
        return False, None, "Draw the Outer Building Boundary Polyline (00-XD-EDGE) first before drawing beams."

    active_cols = [c for c in columns if c.get("active", True)]
    if not active_cols:
        return False, None, "Place or import Structural Columns (00-XD-COL) before drawing beams."

    sx, sy = round(float(start_pt[0]), 3), round(float(start_pt[1]), 3)
    ex, ey = round(float(end_pt[0]), 3), round(float(end_pt[1]), 3)

    tol = 0.30
    if sx < min_x - tol or sx > max_x + tol or sy < min_y - tol or sy > max_y + tol:
        return False, None, f"Beam start point ({sx:.2f}, {sy:.2f}) is outside the Building Boundary."
    if ex < min_x - tol or ex > max_x + tol or ey < min_y - tol or ey > max_y + tol:
        return False, None, f"Beam end point ({ex:.2f}, {ey:.2f}) is outside the Building Boundary."

    # Enforce orthogonal orientation (Horizontal or Vertical)
    half_w = float(width_m) / 2.0
    shifted_note = ""
    if abs(ex - sx) >= abs(ey - sy):
        ey = sy
        if sx > ex:
            sx, ex = ex, sx
        is_horizontal = True
        # Snap endpoints to building boundary if they started on a perimeter column near the edge
        if abs(sx - min_x) <= 0.35:
            sx = round(min_x, 3)
        if abs(ex - max_x) <= 0.35:
            ex = round(max_x, 3)
        sx = min(max(sx, min_x), max_x)
        ex = min(max(ex, min_x), max_x)
        # Auto-shift horizontal beam inward if its full width (sy +/- width_m/2) protrudes outside building boundary
        clamped_y = min(max(sy, min_y + half_w), max_y - half_w)
        if abs(clamped_y - sy) > 1e-4:
            shifted_note = f" [Shifted beam axis Y from {sy:.2f}m to {clamped_y:.2f}m so full width ({width_m:.2f}m) stays inside building boundary]"
            sy = ey = round(clamped_y, 3)
    else:
        ex = sx
        if sy > ey:
            sy, ey = ey, sy
        is_horizontal = False
        if abs(sy - min_y) <= 0.35:
            sy = round(min_y, 3)
        if abs(ey - max_y) <= 0.35:
            ey = round(max_y, 3)
        sy = min(max(sy, min_y), max_y)
        ey = min(max(ey, min_y), max_y)
        # Auto-shift vertical beam inward if its full width (sx +/- width_m/2) protrudes outside building boundary
        clamped_x = min(max(sx, min_x + half_w), max_x - half_w)
        if abs(clamped_x - sx) > 1e-4:
            shifted_note = f" [Shifted beam axis X from {sx:.2f}m to {clamped_x:.2f}m so full width ({width_m:.2f}m) stays inside building boundary]"
            sx = ex = round(clamped_x, 3)

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

    # Find all supports (columns and perpendicular beams) along the line segment
    supports_along: List[Dict[str, Any]] = []
    snap_tol = max(0.45, half_w + 0.25)

    for col in active_cols:
        cx, cy = float(col["x"]), float(col["y"])
        b_col = float(col.get("b_m", 0.20))
        h_col = float(col.get("h_m", 0.40))
        if is_horizontal:
            if abs(cy - sy) <= max(snap_tol, h_col / 2.0 + half_w + 0.08) and (sx - 0.30) <= cx <= (ex + 0.30):
                supports_along.append({
                    "pos_m": round(max(0.0, min(total_len, cx - sx)), 3),
                    "x": cx,
                    "y": sy,
                    "kind": "column",
                    "target_id": col["id"],
                    "width_m": b_col,
                })
        else:
            if abs(cx - sx) <= max(snap_tol, b_col / 2.0 + half_w + 0.08) and (sy - 0.30) <= cy <= (ey + 0.30):
                supports_along.append({
                    "pos_m": round(max(0.0, min(total_len, cy - sy)), 3),
                    "x": sx,
                    "y": cy,
                    "kind": "column",
                    "target_id": col["id"],
                    "width_m": h_col,
                })

    # Check perpendicular supporting beams if endpoints land on another beam
    for ob in existing_beams:
        if ob.get("id") == beam_id:
            continue
        osx, osy = float(ob.get("start_x", 0.0)), float(ob.get("start_y", 0.0))
        oex, oey = float(ob.get("end_x", 0.0)), float(ob.get("end_y", 0.0))
        ob_horiz = abs(oex - osx) >= abs(oey - osy)
        if is_horizontal and not ob_horiz:
            bx = osx
            if (sx - 0.25) <= bx <= (ex + 0.25) and min(osy, oey) - 0.25 <= sy <= max(osy, oey) + 0.25:
                if not any(abs(s["pos_m"] - (bx - sx)) < 0.30 for s in supports_along):
                    supports_along.append({
                        "pos_m": round(max(0.0, min(total_len, bx - sx)), 3),
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
                if not any(abs(s["pos_m"] - (by - sy)) < 0.30 for s in supports_along):
                    supports_along.append({
                        "pos_m": round(max(0.0, min(total_len, by - sy)), 3),
                        "x": sx,
                        "y": by,
                        "kind": "beam",
                        "target_id": ob["id"],
                        "width_m": float(ob.get("width_m", 0.30)),
                        "pos_on_carrier_m": round(abs(sx - min(osx, oex)), 3),
                    })

    supports_along.sort(key=lambda s: s["pos_m"])
    if len(supports_along) == 0:
        return False, None, "Beam must rest on at least one Column or Supporting Beam."

    first_sup_pos = supports_along[0]["pos_m"]
    last_sup_pos = supports_along[-1]["pos_m"]
    # Note: If the first support is a perimeter column flush with the edge (e.g. pos_m <= 0.30m),
    # that 0.10-0.25m column half-width is NOT a cantilever overhang!
    cant_left = round(first_sup_pos, 3) if first_sup_pos > 0.35 else 0.0
    cant_right = round(total_len - last_sup_pos, 3) if (total_len - last_sup_pos) > 0.35 else 0.0

    # Strict Cantilever Validation:
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
        sp = round(supports_along[idx + 1]["pos_m"] - supports_along[idx]["pos_m"], 3)
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
        "cantilever_left_m": cant_left if len(supports_along) >= 2 else 0.0,
        "cantilever_right_m": cant_right if len(supports_along) >= 2 else 0.0,
        "spans": spans,
        "supports": formatted_supports,
        "loads": [{"type": "dist", "x1": 0.0, "x2": total_len, "val": default_w}],
    }
    return (
        True,
        beam_dict,
        f"Beam {beam_id} created ({len(spans)} span(s) [{', '.join(f'{s:.2f}m' for s in spans)}] over {sup_names}).{shifted_note}",
    )


def detect_story_grid_bays(story_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Partitions the Outer Slab Boundary using all horizontal and vertical beams/edges
    to identify real structural bays for the 'Pick Area' tool.
    CRITICAL FIX:
    - Any perimeter beam whose centerline is within `max(0.45m, width_m + 0.15m)` of the outer
      building boundary snaps its grid coordinate to the outer boundary so ZERO fake sliver bays
      (like 0.1m or 0.3m strips) are ever created between a shifted perimeter beam and the slab edge!
    - Requires every valid structural slab bay to have both Lx >= 0.85m and Ly >= 0.85m.
    """
    has_bnd, min_x, min_y, max_x, max_y = get_slab_bounding_box(story_data.get("slab_edge_polygon", []))
    if not has_bnd:
        return []

    xs = [round(min_x, 3), round(max_x, 3)]
    ys = [round(min_y, 3), round(max_y, 3)]

    beams = story_data.get("beams", [])
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

            bays.append({
                "bay_key": f"BAY_{i}_{j}",
                "default_id": f"S{bay_counter}",
                "grid_i": i,
                "grid_j": j,
                "min_x": x_left,
                "max_x": x_right,
                "min_y": y_bot,
                "max_y": y_top,
                "lx_m": lx,
                "ly_m": ly,
                "bounding_beams": bounding_sides,
                "beam_count": beam_count,
            })
            bay_counter += 1
    return bays


def reconcile_and_split_slabs_after_beam_change(story_data: Dict[str, Any]) -> Tuple[int, str]:
    """
    SMART AUTOMATIC SLAB SPLITTING:
    When a user draws a new beam across an existing Slab (for example, dividing a 9.0m slab
    in half with an intermediate beam into two 4.5m bays), this function automatically splits
    the old Slab into the newly formed sub-bays, recalculates their rib spans (4.5m each),
    renumbers S1..Sn cleanly, and prevents any overlapping/duplicate slabs!
    """
    old_slabs = list(story_data.get("slabs", []))
    if not old_slabs:
        return 0, ""

    new_bays = detect_story_grid_bays(story_data)
    if not new_bays:
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

        # Find all current grid bays whose center lies inside this old slab's footprint
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
            # Keep user's rib orientation if valid, or pick shorter span if 4-beam bay was split perpendicular to ribs
            rib_dir = old_dir
            axis_span = lx if rib_dir == 0 else ly
            reconciled_slabs.append({
                "id": f"S{len(reconciled_slabs) + 1}",
                "bay_key": bkey,
                "min_x": mb["min_x"],
                "max_x": mb["max_x"],
                "min_y": mb["min_y"],
                "max_y": mb["max_y"],
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


def auto_fill_all_story_slabs(story_data: Dict[str, Any]) -> Tuple[int, str]:
    """
    1-Click Productivity Tool: Automatically populates all closed beam-bounded bays (>= 3 beams)
    that are not Void Openings with Hollow-Block Slabs using optimal default rib directions.
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
    Rotates a selected column by 90 degrees (swapping b_m and h_m, e.g. 0.20x0.40 <-> 0.40x0.20)
    and re-clamps it inside the building boundary so no corner protrudes outside.
    """
    cols = story_data.get("columns", [])
    target = next((c for c in cols if c.get("id") == column_id), None)
    if not target:
        return False, f"Column {column_id} not found."
    old_b, old_h = float(target.get("b_m", 0.20)), float(target.get("h_m", 0.40))
    target["b_m"] = round(old_h, 3)
    target["h_m"] = round(old_b, 3)
    updated_col, updated_poly, _ = enforce_column_inside_slab_boundary(
        target, story_data.get("slab_edge_polygon", []), mode=boundary_mode
    )
    target["x"], target["y"] = updated_col["x"], updated_col["y"]
    story_data["slab_edge_polygon"] = updated_poly
    return True, f"Rotated Column {column_id} to {target['b_m']:.2f} x {target['h_m']:.2f} m at ({target['x']:.2f}, {target['y']:.2f})."


def pick_area_create_or_update_slab(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    target_mode: str = "SLAB",
    requested_rib_dir_deg: Optional[int] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Handles the 'Pick Area' tool for creating/toggling Slabs (00-XD-SLAB) and Openings (00-XD-OPEN),
    implementing Eng. Yousef's exact structural rules:
    1. 4-Beam Bay:
       - Default rib orientation is along the SHORTER span (0 deg if Lx <= Ly else 90 deg).
    2. 3-Beam Bay (1 free edge):
       - Default rib orientation runs between the TWO OPPOSITE PARALLEL BEAMS:
         * If West & East have beams (and North or South is free) -> default is 0 deg (Horizontal).
         * If North & South have beams (and West or East is free) -> default is 90 deg (Vertical).
       - If the user flips the rib direction in a 3-Beam Bay so ribs run perpendicular to the single
         supporting beam toward the free edge (Cantilever Slab), the adjacent back-span slab across
         that supporting beam MUST exist (not an opening) and its ribs are automatically aligned
         to be continuous in the same direction for structural equilibrium!
    3. Slab <-> Opening Toggle:
       - Any picked Slab can be switched to an Opening and vice-versa.
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
    existing_open = next((o for o in openings if o.get("bay_key") == bay_key), None)

    # Toggle Slab <-> Opening if requested
    if target_mode == "TOGGLE_OPENING" or (target_mode == "OPENING"):
        if existing_open and target_mode == "TOGGLE_OPENING":
            openings.remove(existing_open)
            target_mode = "SLAB"
        else:
            for s in slabs:
                if s.get("backspan_bay_key") == bay_key and s.get("is_cantilever"):
                    return (
                        False,
                        f"Cannot convert {bay_key} to an Opening because Cantilever Slab {s['id']} depends on it for back-span continuity!",
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

    if beam_count == 4:
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

    is_cantilever = False
    backspan_bay_key: Optional[str] = None
    continuity_note = ""

    if beam_count == 3 and chosen_dir != default_dir:
        is_cantilever = True
        gi, gj = target_bay["grid_i"], target_bay["grid_j"]
        if sides["North"] is None:
            adj_i, adj_j = gi, gj - 1
        elif sides["South"] is None:
            adj_i, adj_j = gi, gj + 1
        elif sides["East"] is None:
            adj_i, adj_j = gi - 1, gj
        else:
            adj_i, adj_j = gi + 1, gj

        adj_bay = next((b for b in bays if b["grid_i"] == adj_i and b["grid_j"] == adj_j), None)
        if not adj_bay:
            return (
                False,
                "Cantilever Equilibrium Error: Cannot orient 3-beam slab as a cantilever because there is no back-span bay behind the supporting beam.",
                None,
            )

        backspan_bay_key = adj_bay["bay_key"]
        if any(o.get("bay_key") == backspan_bay_key for o in openings):
            return (
                False,
                f"Cantilever Equilibrium Error: Adjacent back-span bay ({backspan_bay_key}) is a Void Opening! "
                "A cantilever slab requires a continuous solid/ribbed back-span slab in the same direction.",
                None,
            )

        adj_slab = next((s for s in slabs if s.get("bay_key") == backspan_bay_key), None)
        if adj_slab is None:
            adj_axis_span = adj_bay["lx_m"] if chosen_dir == 0 else adj_bay["ly_m"]
            adj_slab = {
                "id": adj_bay["default_id"],
                "bay_key": backspan_bay_key,
                "min_x": adj_bay["min_x"],
                "max_x": adj_bay["max_x"],
                "min_y": adj_bay["min_y"],
                "max_y": adj_bay["max_y"],
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
            adj_slab["axis_span_m"] = adj_bay["lx_m"] if chosen_dir == 0 else adj_bay["ly_m"]
            adj_slab["connected_to_cantilever"] = True

        continuity_note = (
            f" [Cantilever Slab: Back-span {adj_slab['id']} automatically aligned to {chosen_dir}° for continuity & equilibrium]"
        )

    axis_span_m = lx if chosen_dir == 0 else ly
    if existing_slab:
        existing_slab.update({
            "min_x": target_bay["min_x"],
            "max_x": target_bay["max_x"],
            "min_y": target_bay["min_y"],
            "max_y": target_bay["max_y"],
            "lx_m": lx,
            "ly_m": ly,
            "rib_direction_deg": chosen_dir,
            "axis_span_m": axis_span_m,
            "is_cantilever": is_cantilever,
            "backspan_bay_key": backspan_bay_key,
        })
        slab_obj = existing_slab
    else:
        slab_obj = {
            "id": target_bay["default_id"],
            "bay_key": bay_key,
            "min_x": target_bay["min_x"],
            "max_x": target_bay["max_x"],
            "min_y": target_bay["min_y"],
            "max_y": target_bay["max_y"],
            "lx_m": lx,
            "ly_m": ly,
            "rib_direction_deg": chosen_dir,
            "axis_span_m": axis_span_m,
            "left_support_w_m": 0.30,
            "right_support_w_m": 0.30,
            "is_cantilever": is_cantilever,
            "connected_to_cantilever": False,
            "backspan_bay_key": backspan_bay_key,
        }
        slabs.append(slab_obj)

    return (
        True,
        f"Slab {slab_obj['id']} ({lx:.2f}x{ly:.2f} m, {beam_count} beams) set with Rib Direction = {chosen_dir}°.{continuity_note}",
        slab_obj,
    )


def toggle_slab_rib_by_label_click(
    story_data: Dict[str, Any],
    click_x: float,
    click_y: float,
    hit_radius_m: float = 0.75,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Checks if the user clicked near any Slab's center rib label/arrow on the canvas.
    If so, immediately flips its rib direction (0 deg <-> 90 deg) while enforcing
    3-beam cantilever continuity rules!
    """
    for slb in story_data.get("slabs", []):
        if "min_x" not in slb:
            continue
        cx = (float(slb["min_x"]) + float(slb["max_x"])) / 2.0
        cy = (float(slb["min_y"]) + float(slb["max_y"])) / 2.0
        if math.hypot(click_x - cx, click_y - cy) <= hit_radius_m:
            return pick_area_create_or_update_slab(story_data, cx, cy, target_mode="FLIP_RIB")
    return False, "", None


def delete_selected_element_from_story(
    story_data: Dict[str, Any],
    kind: str,
    element_id: str,
) -> Tuple[bool, str]:
    """
    Deletes a selected object (column, beam, slab, opening, or slab_edge) from story_data.
    """
    if kind == "column":
        cols = story_data.get("columns", [])
        before = len(cols)
        story_data["columns"] = [c for c in cols if c.get("id") != element_id]
        if len(story_data["columns"]) < before:
            return True, f"Deleted Column {element_id}."
    elif kind == "beam":
        beams = story_data.get("beams", [])
        before = len(beams)
        story_data["beams"] = [b for b in beams if b.get("id") != element_id]
        if len(story_data["beams"]) < before:
            return True, f"Deleted Beam {element_id}."
    elif kind == "slab":
        slabs = story_data.get("slabs", [])
        target = next((s for s in slabs if s.get("id") == element_id), None)
        if target:
            bay_key = target.get("bay_key")
            for other in slabs:
                if other.get("backspan_bay_key") == bay_key and other.get("is_cantilever"):
                    return (
                        False,
                        f"Cannot delete Slab {element_id} because Cantilever Slab {other['id']} depends on it for back-span equilibrium.",
                    )
            story_data["slabs"] = [s for s in slabs if s.get("id") != element_id]
            return True, f"Deleted Slab {element_id}."
    elif kind == "opening":
        opens = story_data.get("openings", [])
        before = len(opens)
        story_data["openings"] = [o for o in opens if o.get("id") != element_id]
        if len(story_data["openings"]) < before:
            return True, f"Deleted Opening {element_id}."
    elif kind == "slab_edge":
        story_data["slab_edge_polygon"] = []
        return True, "Deleted Outer Building Boundary Polyline."
    return False, f"Element {kind} '{element_id}' not found."


def move_column_and_sync_connected_beams(
    story_data: Dict[str, Any],
    column_id: str,
    new_x: float,
    new_y: float,
    boundary_mode: str = "clamp",
) -> Tuple[bool, str]:
    """
    Moves a column to (new_x, new_y), enforces the Outer Slab Boundary rule ('clamp' or 'expand'),
    and updates all beams supported by this column.
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

    for bm in story_data.get("beams", []):
        sup_ids = [s.get("target_id") for s in bm.get("supports", []) if s.get("kind") == "column"]
        if column_id not in sup_ids:
            continue
        sx, sy = float(bm.get("start_x", 0.0)), float(bm.get("start_y", 0.0))
        ex, ey = float(bm.get("end_x", 0.0)), float(bm.get("end_y", 0.0))
        is_horiz = abs(ex - sx) >= abs(ey - sy)
        if is_horiz:
            bm["start_y"] = round(sy + dy, 3)
            bm["end_y"] = round(ey + dy, 3)
            if abs(sx - old_x) < 0.35:
                bm["start_x"] = target_col["x"]
            if abs(ex - old_x) < 0.35:
                bm["end_x"] = target_col["x"]
        else:
            bm["start_x"] = round(sx + dx, 3)
            bm["end_x"] = round(ex + dx, 3)
            if abs(sy - old_y) < 0.35:
                bm["start_y"] = target_col["y"]
            if abs(ey - old_y) < 0.35:
                bm["end_y"] = target_col["y"]

        col_coords = []
        for s in bm.get("supports", []):
            if s.get("kind") == "column":
                c_obj = next((c for c in columns if c["id"] == s.get("target_id")), None)
                if c_obj:
                    col_coords.append(float(c_obj["x"]) if is_horiz else float(c_obj["y"]))
        col_coords.sort()
        if len(col_coords) >= 2:
            bm["spans"] = [round(col_coords[k + 1] - col_coords[k], 3) for k in range(len(col_coords) - 1)]

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


