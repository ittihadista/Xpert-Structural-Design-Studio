# Xpert Structural Design Studio — Version History & Changelog

This file tracks all releases of **Xpert Structural Design Studio** for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`).

---

## Current Release: `v2.4.11-structural-bim-pro` (2026-11-20)
**Release Title:** Face-Based Slab Inference Engine (2D CAD Boolean Subtraction, Slivers Policy, Roof Area Coverage Equation $\le 0.01\text{ m}^2$, Extend Beam 2-Step Workflow with 150mm OSNAP Snap & Hover Highlight, Backward Compatibility Verbatim Load, 78/78 Unit Tests, and 4 Frozen Calculation Cores).

### Key Features & Advancements in `v2.4.11-structural-bim-pro`:
1. **Face-Based Slab Inference Engine (`infer_story_slabs_face_based`):**
   - Implemented exact 2D geometric boolean subtraction: $\text{Slabs} = \text{Building Boundary (00-XD-EDGE)} - \text{Openings (00-XD-OPEN)} - \text{Beams (00-XD-BEAM)}$.
   - Completely replaces old axis-grid cell approximations, eliminating phantom grid splitting and supporting staggered, irregular, stepped, and L-shaped panels with 0.1mm coordinate rounding.
   - Deterministic sorting by centroid $(X \to Y)$, producing exact sequentially-labeled slab components ($S_1 \dots S_n$).
2. **Coverage Equation Verification ($\le 0.01\text{ m}^2$):**
   - Rigorously satisfies the coverage equation for all stories:
     $$\sum \text{Area}(\text{Slabs}) + \text{Area}(\text{Beam Strips in Roof}) + \text{Area}(\text{Openings in Roof}) = \text{Area}(\text{Roof})$$
   - Ground Floor Fixture verified: Total roof area $234.6600\text{ m}^2 = 158.2146\text{ m}^2 (\text{Slabs}) + 56.9490\text{ m}^2 (\text{Beams}) + 19.4964\text{ m}^2 (\text{Openings})$, Difference = $0.00000000\text{ m}^2$.
3. **Slivers Management Policy (Condition B):**
   - Any geometric component with $\text{Area} < 0.30\text{ m}^2$ or minimum dimension $< 0.15\text{ m}$ is explicitly retained in the model with `is_sliver = True`.
   - Never silently deleted or absorbed; contributes fully to the coverage equation.
   - Generates non-blocking warnings surfaced via `SlabInferenceWarningsDialog` (4 slivers on Ground Floor fixture: S2, S3, S13, S19).
4. **Interactive Extend Beam (EX) 2-Step Workflow (Condition D):**
   - Step 1/2: Status bar and contextual prompt `"Step 1/2: pick beam to extend"` with real-time cyan hover highlight (`_hovered_extend_beam_id`).
   - Step 2/2: Status bar `"Step 2/2: pick extension limit for beam B# (click node/point/edge)"`.
   - Expanded snap tolerance to $150\text{ mm}$ (`tol2 = 0.150`), seamlessly accepting OSNAP column centers, corner nodes, and intersecting beams.
   - Explicit rejection error dialogs (`QMessageBox.warning`) detailing exact geometric reasons upon rejection.
   - Validated via behavioral 2-click unit test (B6 selection $\to$ C18 snap $\to$ 2 spans).
5. **Strict Backward Compatibility (Condition C):**
   - Opening an existing project (e.g. saved under v2.4.10) loads all slabs and elements verbatim without auto-inference or accidental modification.
   - Auto-Fill runs strictly on explicit user action with full 1-step Undo (`push_undo_snapshot()`).
6. **Geometry Audit & Warnings Dialog (`SlabInferenceWarningsDialog`):**
   - Automatically surfaces slivers, beam-opening overlaps ($> 0.01\text{ m}^2$), untrimmed opening edges, and support anomalies upon Auto-Fill completion.
7. **Strict Frozen Core Protection (Condition 0):**
   - 100% byte-for-byte line and SHA-256 preservation across all 4 critical engine blocks:
     - Block 1 (lines 194–515, `solve_continuous_beam_analytical`): `351d9de788087a301ec6efc6f25bdcacb571d9e06b4e903e43ca93847484ee42`
     - Block 2 (lines 733–960, `design_hollow_block_slab_rib`): `b853e8d467d48d7471e132235943d0e578a15092ff7c74c092ebec21cf922a98`
     - Block 3 (lines 961–1730, `analyze_all_story_beams_and_columns`): `f3594ce1480c88c745094d364521962db77f61e6e88a844a631e8f76ee4d721d`
     - Block 4A (lines 1731–2397, `design_beam_aci318`): `5ef415460e2ba578998716eb9cd29030768b2c36396486995efa903818fde27a`
     - Block 4B (lines 2398–2632, `design_column_and_pm_curve`): `e711ee21f0f5245f3624656ca1567395bf2b98d1625ad8ee883fb884eaf6d8fa`
8. **Automated Test Suite Expansion (78/78 Tests):**
   - Expanded from 64 to 78 tests ($64 + 14 = 78$), all passing under `python -W error::ResourceWarning` with 0 warnings in ~3.3s.

---

## Previous Release: `v2.4.10-structural-bim-pro` (2026-11-20)
**Release Title:** Comprehensive Structural Engine Audit & Hardening (Bresler Biaxial Column Check, AST Deduplication, $\rho_{\max}$ Over-Reinforced Section Guard, RAII File Leaks Elimination, Strain-Compatibility Column P-M Curve, and 3-Moment/Transfer Frozen Cores).

### Key Features & Advancements in `v2.4.10-structural-bim-pro`:
1. **Bresler Reciprocal Biaxial Interaction Check (Item 1):**
   - Implemented rigorous Bresler reciprocal load method ($1/P_{n,\text{biax}} = 1/P_{nx} + 1/P_{ny} - 1/P_0$) within `design_column_and_pm_curve` in `xpert_structural_engine.py`.
   - Biaxial capacity is evaluated by ray-eccentricity interpolation along both principal bending axes ($e_x = M_{uy}/P_u, e_y = M_{ux}/P_u$).
   - If factored axial load exceeds design biaxial strength ($P_u > \phi P_{n,\text{biax}}$), status is unequivocally set to `INCREASE SECTION (BIAXIAL)` with full reporting of $P_{n,\text{biax}}$, $\phi P_{n,\text{biax}}$, and utilization ratio $P_u / (\phi P_{n,\text{biax}})$.
   - Robust numerical guards protect against zero division when $M_{ux} \approx 0$, $M_{uy} \approx 0$, or $P_u \le 0$.
2. **AST Deduplication of Shadowed Top-Level Engine Functions (Item 2):**
   - Cleaned up duplicate top-level function definitions in `xpert_structural_engine.py`.
   - Verified 0 shadowed top-level functions using Abstract Syntax Tree (AST) inspection in automated test suite.
   - Architectural Option B strictly adhered to: preserved the frozen load-transfer and 3-moment core (lines 961–1730) intact without modification; `enforce_beam_footprint_and_cascade` is invoked directly from the desktop application analysis orchestration pipeline.
3. **Beam Ductility $\rho_{\max} = 0.75 \rho_b$ Terminology & Locked-Section Safety (Item 3):**
   - Replaced empirical $\rho_{\max}$ with standard ACI 318 balanced reinforcement ratio: $\rho_b = 0.85 \beta_1 \frac{f'_c}{f_y} \left(\frac{600}{600 + f_y}\right)$ and $\rho_{\max} = 0.75 \rho_b$, resulting in $k_{u,\max} \approx 0.259$ for $f'_c = 25\text{ MPa}, f_y = 420\text{ MPa}$.
   - Eliminated silent artificial clamping of reinforcement for locked sections (`lock_section_dimensions = True`).
   - If required depth exceeds capacity under $k_{u,\max}$, locked sections explicitly warn: `OVER-REINFORCED: increase depth/width or unlock dimensions` and return $A_{s,\text{req}} = \text{None}$, preventing dangerous under-design while auto-sizing beams enlarge normally.
4. **RAII File Handle Management & ResourceWarning Elimination (Item 4):**
   - Refactored unclosed file pointers across the test suite and I/O modules into clean Python context managers (`with open(...) as f:`).
   - Test suite runs under strict warning escalation `python -W error::ResourceWarning` with 0 warnings emitted.
5. **Strain-Compatibility Numerical Column P-M Interaction Curve (Item 5):**
   - Replaced approximate empirical interaction formulas with rigorous cross-section strain compatibility analysis.
   - Accurately captures pure compression capacity $P_0 = 0.85 f'_c (A_g - A_{st}) + f_y A_{st}$ (within 0.5% numerical tolerance), balanced point ($c_b = \frac{600}{600+f_y} d, P_b, M_b$), tension-controlled transition ($\epsilon_t \ge 0.005$), pure bending moment capacity $M_0$, and pure tension capacity $P_{nt} = -f_y A_{st}$.
6. **Strict Frozen Core Protection (Item 0):**
   - Guaranteed line-exact SHA-256 integrity for the three core calculation blocks against reference `reference_v2_4_9`:
     - `solve_continuous_beam_analytical` (lines 194–515, SHA-256: `351d9de788087a301ec6efc6f25bdcacb571d9e06b4e903e43ca93847484ee42`)
     - `design_hollow_block_slab_rib` (lines 733–960, SHA-256: `b853e8d467d48d7471e132235943d0e578a15092ff7c74c092ebec21cf922a98`)
     - `analyze_all_story_beams_and_columns` (lines 961–1730, SHA-256: `f3594ce1480c88c745094d364521962db77f61e6e88a844a631e8f76ee4d721d`)
7. **Comprehensive Automated Unit Test Suite:**
   - Expanded test suite from 56 to 64 tests in `test_studio_engine.py` (64/64 pass in ~3.7s).
   - Added dedicated tests for biaxial safety/failure, AST zero-shadowing, locked-section over-reinforced warnings, auto-sizing ductility, RAII ResourceWarnings, $P_0$/$P_{nt}$ axial limits, balanced depth $c_b$, and frozen SHA-256 hash preservation.
