# Xpert Structural Design Studio — Version History & Changelog

This file tracks all releases of **Xpert Structural Design Studio** for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`).

---

## Current Release: `v2.4.14-structural-bim-pro` (2026-11-20)
**Release Title:** Polish & Edge-Case Override (Boundary Sliver Absorption into Adjacent Panels, Modal Dialog Suppression on Auto-Fill with Non-Blocking Warnings, Cantilever Back-Span Padlock 🔒 Badges & Cantilever-ID Flip Lock UX, Default Rib Direction Along Shorter Dimension, 89/89 Unit Tests Passed, Frozen Cores Preserved 100%).

### Key Features & Polish in `v2.4.14-structural-bim-pro`:
1. **Suppression of Modal Dialog on Auto-Fill (FIX #1):**
   - Eliminated the intrusive modal `SlabInferenceWarningsDialog` popup on normal 1-Click Auto-Fill when only non-blocking warnings (boundary slivers, untrimmed opening edges) exist.
   - Replaced with a clean, informative status bar and contextual prompt message: `"Auto-Fill complete: {N} Slab bays created. {M} warnings (check diagnostics log)."`.
   - Retained modal dialog only on critical geometric failure (0 slab bays created).
   - Added on-demand menu actions under `Draw > View Slab Inference Warnings & Audit...` and `View > Slab Inference Warnings & Geometry Audit...` for manual review anytime.
2. **Boundary Sliver Absorption Engine (FIX #2):**
   - In `infer_story_slabs_face_based`, after Pass 1 touching-sliver merge, added Pass 2 Boundary Sliver Absorption:
     - Detects boundary sliver polygons (area $\le 0.50\text{ m}^2$ or minimum dimension $\le 0.15\text{ m}$) touching the exterior building boundary within $0.05\text{ m}$.
     - Absorbs each boundary sliver cleanly into its nearest adjacent room panel.
     - Slabs count on the project fixture is refined from 20 to 15 real, well-proportioned room bays (absorbing S1, S3, S4, S14, S20).
     - Exact mathematical coverage equation holds with zero error ($\text{diff} = 0.000000\text{ m}^2 \le 0.001\text{ m}^2$).
     - Guarantees $0.0000\text{ m}^2$ beam-slab overlap across all absorbed parts.
3. **Cantilever Back-Span Lock UX & Padlock 🔒 Badge (FIX #3):**
   - Canvas slab badges for locked cantilevers and back-span panels now display a crisp gold padlock icon: e.g. `S1 🔒 (1.6m, 4.4m)`, `S8 🔒 (3.5m, 5.0m)`, `S12 🔒 (5.8m, 4.9m)`.
   - Upgraded badge text rendering to native Segoe UI Bold with automatic dynamic badge width sizing.
   - When the user attempts to flip a locked back-span slab, the flip is strictly rejected, and the prompt explicitly names the controlling cantilever ID: `"Cantilever Back-Span Lock: Slab {target_id} is the back-span extension for Cantilever Slab {cantilever_id}."`.
4. **Default Rib Direction Along Shorter Dimension (FIX #4):**
   - Verified and enforced for all non-cantilever slabs that ribs span across the shorter dimension ($\text{width} \le \text{height} \implies 0^\circ$ [X-direction], $\text{width} > \text{height} \implies 90^\circ$ [Y-direction]).
   - Dashed rib line hatching and center directional arrows visually match this orientation on the 2D CAD canvas.
5. **Strict Preservation of Frozen Analytical Cores:**
   - Lines 194 to 2632 in `xpert_structural_engine.py` remain $100\%$ untouched, matching reference SHA-256 hashes byte-for-byte.
6. **Test Suite Expansion (89/89 Tests Passed):**
   - Added Test 89 (`test_v2414_boundary_sliver_merging_and_backspan_lock`) covering all 5 items.
   - All 89 tests pass cleanly in 4.48s.

---

## Previous Release: `v2.4.13-structural-bim-pro` (2026-11-20)
**Release Title:** Face-Based Slab Inference Engine (Robust Shapely 2.0+ 2D CAD Boolean Subtraction, Coverage Equation $\le 0.01\text{ m}^2$, Zero Beam-Slab Overlap, Slivers Policy, Cantilever Rib Perpendicularity & Backspan Continuity Lock, 88/88 Tests Passed, Frozen Cores Preserved 100%).

### Key Features & Advancements in `v2.4.13-structural-bim-pro`:
0. **UI & CAD Rendering Pipeline Overhaul (`xpert_studio_app.py`):**
   - **Exact Polygon Rendering (`addPolygon`):** Switched slab canvas rendering from bounding-box rectangles (`addRect`) to exact 2D CAD polygons (`self.scene_2d.addPolygon(qpoly)`). Blue slab edges now align 100% flush against the inner faces of yellow hatched beams with zero centerline overlap.
   - **Dynamic Slab Dimension Labels:** Fixed slab tag badges to display true clear dimensions `lx_m` and `ly_m` (e.g. `S16 (5.8m, 4.9m)`), completely eliminating `0.0m` placeholders.
   - **Missing Import Fixed:** Imported `QListWidget` from `PyQt6.QtWidgets`, eliminating `NameError: QListWidget is not defined` when displaying `SlabInferenceWarningsDialog`.
1. **Shapely 2.0+ 2D CAD Boolean Subtraction (`infer_story_slabs_face_based`):**
   - Completely replaced Qt `QPainterPath` boolean subtractions with exact CAD geometric topology via `shapely.ops.unary_union` and `difference`.
   - Formula: $\text{Slabs} = \text{Building Boundary (00-XD-EDGE)} - \text{Openings (00-XD-OPEN)} - \text{Beams (00-XD-BEAM)}$.
   - Solved topological clipping bugs that previously caused dropped bays (e.g. top-left bay at $X=1.5, Y=15.0$) and dropped interior void openings.
2. **Pre-Inference Geometric Validator (`validate_geometry_before_inference`):**
   - Validates existence and closure of the building boundary polygon (`00-XD-EDGE`).
   - Ensures all beam endpoint coordinates are valid finite numbers prior to running inference or interactive pick operations.
   - Fully integrated at the entrance of `auto_fill_all_story_slabs` and canvas pick handlers (`pick_slab_at_point`, `PICK_OPENING`).
3. **Interactive Pick Area Tool Unification (`pick_area_create_or_update_slab`):**
   - The manual canvas Pick Area workflow now runs the exact same face-based boolean algorithm as Auto-Fill, ensuring $100\%$ polygon and property parity between automated and manual workflows.
4. **Sliver Merging Policy & True Panel Bounding:**
   - Any geometric sliver panel ($< 0.30\text{ m}^2$ or minimum dimension $< 0.15\text{ m}$) sharing a boundary with an adjacent panel without a dividing beam is automatically merged into a single contiguous panel.
   - Slabs 2 & 4 in the ground floor project are now unified into one contiguous $28.41\text{ m}^2$ ($5.80\text{ m} \times 4.90\text{ m}$) panel.
5. **Exterior Cantilever Boundary & Support Detection:**
   - Exact identification of exterior cantilever overhangs along the outer building perimeter.
   - Automated rib perpendicularity: Vertical carrier beam $\implies 0^\circ$ (X-Direction), Horizontal carrier beam $\implies 90^\circ$ (Y-Direction).
6. **Cantilever Backspan Continuity Lock:**
   - Automatically detects adjacent backspan panels sharing the carrier beam and locks rib direction to align with the cantilever.
   - Disallows converting backspan bays to void openings or flipping ribs in conflict with cantilever structural equilibrium.
7. **Strict Preservation of Frozen Analytical & Design Cores:**
   - All 5 calculation core functions in `xpert_structural_engine.py` (lines 194-515, 733-960, 961-1730, 1731-2397, 2398-2632) remain $100\%$ byte-for-byte SHA-256 identical to their reference baselines.
8. **Test Suite Expansion (88/88 Tests Passed):**
   - 82 baseline tests + 6 new geometric tests (Tests A-F: inner faces vs centerlines, zero beam-slab overlap, cantilever rib perpendicularity, backspan continuity lock, sliver merging, coverage equation exactness).
   - $100\%$ clean pass across all 88 tests with zero ResourceWarnings.
9. **Live Fixture Verification (Step 8 Criteria):**
   - Verified on `ground_floor_fixture_v2410.json`: 20 slabs auto-generated, coverage equation exact difference $= 0.00000000\text{ m}^2 \le 0.01\text{ m}^2$, max beam-slab overlap $= 0.00000000\text{ m}^2$, 20 unique IDs, top-right cantilever S18 oriented at $0^\circ$, and Slabs 2 & 4 unified.

---

## Previous Release: `v2.4.12-structural-bim-pro` (2026-11-20)
**Release Title:** GUI Hotfix — `push_undo_snapshot` Defined & Multi-Step Undo, Point-in-Component Slab Picking (`_point_in_polygon` Ray-Casting & Physical Beam Rectangles), Bounded-Slab-Bays Prompt Removed, 82/82 Unit Tests, Engine Frozen from v2.4.11.

### Key Features & Fixes in `v2.4.12-structural-bim-pro`:
1. **Multi-Step Undo Snapshot Infrastructure (`push_undo_snapshot`):**
   - Explicitly defined `push_undo_snapshot(self)` on `XpertStudioMainWindow` to capture deepcopy state of `current_story_data`.
   - Wired directly into `AUTO_FILL_SLABS` before running `auto_fill_all_story_slabs` / `infer_story_slabs_face_based`.
   - Bounded stack trimming to maximum 20 snapshots (`self._undo_stack.pop(0)`).
   - Standardized `undo_action` (Ctrl+Z) to pop snapshots, restore active story memory, sync, and refresh the UI.
2. **Point-in-Component Slab Picking (`pick_slab_at_point`):**
   - Replaced legacy bay-detection and beam-counting logic with pure point-in-component geometric ray-casting (`_point_in_polygon` and `_point_in_beam_rect`).
   - Priority hierarchy on canvas click in `PICK_SLAB` mode:
     1. Openings (`00-XD-OPEN`) $\to$ `"Clicked on Opening: {id}"`.
     2. Beams (`00-XD-BEAM`) actual physical rectangle $\to$ `"Clicked on Beam: {id} ({kind})"`.
     3. Slabs in `story['slabs']` $\to$ Selects slab (`self.selected_items = [("slab", id)]`), renders, and displays properties: area, dimensions, and rib direction.
     4. Boundary (`00-XD-EDGE`) $\to$ `"Clicked outside building boundary"`.
     5. Interior fallback $\to$ Informational prompt.
   - Completely eliminated the outdated message `"Clicked point is outside bounded slab bays."`.
3. **AST Quality & Method Integrity Check:**
   - Full AST verification confirms zero undefined `self.<method>()` calls in `XpertStudioMainWindow`.
4. **Strict Engine Freeze Preserved:**
   - `xpert_structural_engine.py` remains 100% byte-for-byte SHA-256 identical to `reference_v2_4_11` (`f7bd503a2a52979d34a289cc2b7e544e013b6fc066a5799aaa494cd773678fb8`).
5. **Test Suite Expansion (82/82 Passed):**
   - 78 legacy tests + 4 new behavioral GUI tests (`test_v2412_push_undo_snapshot_defined_and_callable`, `test_v2412_undo_stack_grows_and_trims`, `test_v2412_pick_point_in_slab_selects_it`, `test_v2412_pick_point_in_beam_shows_beam_message`).

---

## Previous Release: `v2.4.11-structural-bim-pro` (2026-11-20)
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
