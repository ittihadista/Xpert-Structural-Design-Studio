# Xpert Structural Design Studio — Version History & Changelog

This file tracks all releases of **Xpert Structural Design Studio** for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`).

---

## Current Release: `v2.4.0-structural-bim-pro` (2026-11-18)
**Release Title:** Selective Opening Drop Enforcement, Inner Beam Face Flush Snapping, 100% English-Only UI, Non-Clipping Tabs 2 & 3 Viewports, Floor-by-Floor Wall Load Elevation Calibration, and Phantom Slab Gap Elimination.

### Key Features & Advancements in `v2.4.0-structural-bim-pro`:
1. **Selective Opening Drop Enforcement (`Selective Opening Drop Enforcement`):**
   - Beams bordering slab openings (such as B8 and B9) remain Hidden Beams and can be freely converted between Hidden and Drop sections by the user whenever solid slab expansion room exists on the opposite side (`beam_has_solid_slab_expansion_room`).
   - Beams without solid slab room (such as B7 bounded by openings/voids) are strictly enforced as Drop Beams ($0.20 \times 0.40\text{ m}$).
   - Primary carrier beams supporting secondary drop beams (such as B6 carrying B7) are strictly protected by the structural hierarchy rule (`Carrier Cascade`); converting carrier beams to Hidden is blocked with descriptive engineering errors.
2. **Inner Beam Face Flush Snapping (`Inner Beam Face Flush Snapping`):**
   - Rectangular opening drafting automatically snaps to the clear inner faces of bordering beams (`Top Face`, `Bottom Face`, `Left Face`, `Right Face`), ensuring openings fit tightly within the clear room boundary without intersecting the beam core.
3. **100% English-Only LTR UI:**
   - Standardized all menus, dialogs, status bar messages, tabs, callouts, and diagnostic logs strictly in 100% professional structural engineering English.
4. **Viewport Scaling & Zero Horizontal Scrollbars:**
   - Eliminated distracting horizontal scrollbars (`ScrollBarAlwaysOff`) in Tabs 2 and 3.
   - Dynamic `sceneRect` and bounding-box calculation guarantees that beam elevation diagrams, shear force/bending moment envelopes, and Section A-A cross-sections render completely without right-side clipping.
5. **Calibrated Multi-Story Wall Load Heights:**
   - Corrected physical wall heights across floor levels:
     - `00_TieBeams` (Tie Beams) carries Ground Floor walls: $H_{\text{wall}} = H_{\text{ground}} = 3.20\text{ m} \rightarrow W_{\text{wall}} = 11.20\text{ kN/m}$.
     - `02_Ground_Floor` (Ground Floor Slab) carries Upper Floor walls: $H_{\text{wall}} = H_{\text{upper}} = 3.00\text{ m} \rightarrow W_{\text{wall}} = 10.50\text{ kN/m}$.
     - Standard initial Drop Beam depth unified at $0.40\text{ m}$ ($400\text{ mm}$).
6. **Phantom Slab Gap Elimination:**
   - Reduced longitudinal overlap tolerance in `has_beam_on_segment` to $0.05\text{ m}$, preventing false beam interceptions and eliminating accidental splitting of continuous slab panels (such as S5).
7. **Automated Unit Test Suite:**
   - 20 unit tests in `test_studio_engine.py` (20/20 pass in ~1.8s) including `test_v240_selective_drop_opening_wall_heights_and_viewport_fit`.

---

## Previous Release: `v2.3.0-structural-bim-pro` (2026-11-17)
**Release Title:** Independent Slab Openings CAD Engine, Opening-Over-Framing Priority, Double-Height Columns (2H), Recursive Carrier Beam Cascade, Standard 100mm Drop Beam Depth Snapping, Span-Isolated Shear Envelope, Non-Clipping Section A-A Scaling, and Real-Time Diagnostic Logging (`xpert_studio_session.log`).

### Key Features & Advancements in `v2.3.0-structural-bim-pro`:
1. **Independent Slab Opening Tool (`DRAW_OPENING`):**
   - Dedicated 2D CAD drafting tool supporting both 2-Click Orthogonal Box mode and Multi-Vertex Closed Polygon mode (`Spacebar` to toggle modes, `Enter` or Right-Click to close).
   - Smart topological coalescing (`coalesce_adjacent_openings`): adjacent or overlapping openings automatically merge into a single unified polygon when no beam separates them.
   - Clean AutoCAD DXF export to layer `00-XD-OPEN` (Color 6, Magenta) as closed `LWPOLYLINE` with structural crossing diagonal lines.
2. **Opening Priority over Framing & Double-Height Column Support (2H):**
   - Opening Priority rule (`Opening Priority`): beams crossing inside slab openings are automatically shifted to the nearest solid slab edge and converted to drop beams.
   - Column in opening conflict resolution: user can either displace the column with attached framing to the nearest solid edge or designate it as a **Double-Height Column (`(2H)`)**.
   - Double-Height columns calculate effective unbraced length $L_u = 2 \times H_{\text{story}}$ for slenderness and column capacity, rendered with `(2H)` badge in Tab 4 and AutoCAD DXF tag `C# (2H)` on layer `00-XD-TAG-COL`.
3. **Opening-Adjacent Beam Conversion & Recursive Carrier Cascade (`B7 -> B6`):**
   - Prohibits hidden beams along opening perimeters or extending outside the slab boundary; automatically converts them to Drop Beams ($0.20 \times 0.40\text{ m}$) with user notification.
   - Recursive Carrier Cascade (`enforce_opening_adjacent_drop_beams_and_cascade`): any hidden beam supporting a drop beam is automatically escalated into a drop beam.
4. **Standard 100mm Drop Beam Depth Snapping & Shear Zone 5 Sizing:**
   - Drop beam section depths strictly snapped to multiples of $100\text{ mm}$ via `_snap_drop_depth_m` ($0.40, 0.50, 0.60\text{ m}$), eliminating legacy non-standard $0.51\text{ m}$ ($510\text{ mm}$) heights.
   - Shear Zone 5 (+100mm step): when shear stress exceeds ACI 318 limits, depth is stepped up in $+100\text{ mm}$ increments.
   - Span-isolated shear envelope: strictly limits peak shear search to open span intervals `(s_st + 1e-4, s_en - 1e-4)`, preventing shear spikes from leaking between adjacent spans (`Span 1 -> Span 2`).
5. **Enhanced UI Drafting, Tab 2/3 Section Scaling & Real-Time Diagnostics:**
   - Tab 2 title dynamically shows initial and designed beam dimensions: `Init b×h → Designed b×h`.
   - Tab 3 horizontal scaling covers full physical beam width `(ext_left + tot_l + ext_right)`, ensuring Section A-A detail never clips on the right viewport edge.
   - Real-time diagnostic session logging system (`xpert_studio_session.log`) recording all events (`PROJECT_INIT`, `HORDI_CALC`, `ANALYSIS_START`, `BEAM_SOLVE_DESIGN`, `CASCADE`, `ANALYSIS_DONE`), viewable directly via `View -> Open Session Diagnostic Log (سجل الأحداث والأعطال)...`.
6. **Comprehensive Automated Test Coverage:**
   - 19 passing unit tests in `test_studio_engine.py` (19/19 OK in ~1.6s) including `test_v230_openings_priority_cascade_clean_drop_depth_shear_and_logging`.

---

## Previous Release: `v2.2.1-structural-bim-pro` (2026-11-17)
**Release Title:** Crash-Proof Plan Drafting, Global Qt Exception Hook, Debounced Viewport Resizing (40ms), Single-Pass Analysis Philosophy, and Commercial Hollow-Block Standard Sizing

### Key Features & Advancements in `v2.2.1-structural-bim-pro`:
1. **Immediate Crash Fix After Plan Drafting (`TypeError` in `_check_and_apply_slab_thickness`):**
   - Eliminated the critical call collision where `hb_src` dictionary was passed along with keyword argument `slab_thickness_cm` into `compute_hollow_block_parameters()`.
   - Added automated static AST signature verification (`test_v221_regression_no_slab_thickness_typeerror_and_ast_signatures`) to inspect all function call sites between the UI and structural engines, preventing parameter mismatch regressions.
2. **Global Qt Exception Hook & Safe Error Reporting:**
   - Implemented `_install_global_excepthook` and `_report_studio_exception` to intercept unhandled exceptions and log them to `xpert_studio_crash.log` without abruptly crashing the application or losing unsaved CAD drafting data.
3. **Debounced Viewport Resizing & Re-Entrancy Crash Shield (40ms QTimer):**
   - Decoupled diagram canvas and calculation sheet resizing using single-shot `QTimer` (40ms debounce delay) with recursion guards, preventing PyQt6 layout deadlock or re-entrant crash loops when resizing or maximizing the window.
4. **Single-Pass Structural Analysis & Section Sizing (Excel Philosophy Alignment):**
   - Strictly decoupled the structural load distribution phase from the reinforced concrete section sizing phase per Eng. Yousef's Excel methodology:
     - Distributed loads (Beam O.W, Wall loads, tributary slab loads) are calculated once using baseline beam sections and full slab rib spans.
     - Section auto-sizing (+100 mm step per VBA `Sub ReDesign_Sec`) operates purely during section design without feeding back into O.W or reducing slab rib tributary length.
5. **Standard Commercial Hollow-Block Sizes & Automatic Compression Topping:**
   - Standard commercial block height strictly maintained at $200\text{ mm}$ ($20\text{ cm}$) for $h \ge 25\text{ cm}$ (or $160\text{ mm}$ for $h < 25\text{ cm}$).
   - Compression topping layer dynamically computes $h_s = h - h_{\text{block}}$ ($8\text{ cm}$ for $h=28\text{ cm}$, $9\text{ cm}$ for $h=29\text{ cm}$, $10\text{ cm}$ for $h=30\text{ cm}$) matching Eng. Yousef's Excel sheet 100%.

---

## Previous Release: `v2.2.0-structural-bim-pro` (2026-11-17)
**Release Title:** Standard Commercial Hordi Block Sizing, VBA-Compliant Section Auto-Sizing (+100 mm step), Coupled Equilibrium Load Convergence, Right-Edge Canvas Clipping Fix, and Excel Sheet4 Flexural Calculation Sheet

### Key Features & Advancements in `v2.2.0-structural-bim-pro`:
1. **Standard Commercial Hollow-Block Heights & Dynamic Topping Layer:**
   - Hollow block height is strictly standardized to $200\text{ mm}$ ($20\text{ cm}$) for slab thickness $h \ge 25\text{ cm}$ (or $160\text{ mm}$ for $h < 25\text{ cm}$).
   - Concrete compression topping layer dynamically adjusts: $h_s = h - h_{\text{block}}$.
   - Exact 100% numerical match with Eng. Yousef's Excel sheet (`Design of rib slab` / `4_17463a4e.PNG`):
     - At $h = 28\text{ cm}$: $h_{\text{block}} = 20\text{ cm}, h_s = 8\text{ cm} \rightarrow W_u(\text{rib}) = 6.07\text{ kN/m'/rib}, W_u(\text{m}\times\text{m}) = 11.04\text{ kN/m}^2$.
     - At $h = 29\text{ cm}$: $h_{\text{block}} = 20\text{ cm}, h_s = 9\text{ cm} \rightarrow W_u(\text{rib}) = 6.26\text{ kN/m'/rib}, W_u(\text{m}\times\text{m}) = 11.38\text{ kN/m}^2$.
     - At $h = 30\text{ cm}$: $h_{\text{block}} = 20\text{ cm}, h_s = 10\text{ cm} \rightarrow W_u(\text{rib}) = 6.44\text{ kN/m'/rib}, W_u(\text{m}\times\text{m}) = 11.71\text{ kN/m}^2$.
2. **VBA-Compliant Iterative Section Sizing Loop (`Sub ReDesign_Sec()` / `+100 mm` Step):**
   - Hidden Beams: depth $h$ is fixed to slab thickness; width $B$ automatically increments by $+100\text{ mm}$ (e.g. $400 \rightarrow 500 \rightarrow 600\text{ mm}$) whenever concrete capacity is exceeded ($1 - 2.36 K_u < 0$), tension steel exceeds max allowable single-layer limit ($\rho > \rho_{\text{max}}$), or required bars exceed single-layer capacity ($n_{\text{bars}} > n_{\text{max}}$).
   - Drop Beams: width $b$ is fixed to wall thickness; depth $h$ increments by $+100\text{ mm}$ (e.g. $400 \rightarrow 500 \rightarrow 600\text{ mm}$) with multi-row placement ($n_{\text{row}} \le 3$, $d_{\text{dc}} < 0.45 h$).
3. **Coupled Iterative Equilibrium Loop between Beam Sizing & Slab Rib Length Reduction:**
   - In `analyze_all_story_beams_and_columns`, when supporting beams widen by $\Delta B = B_{\text{sized}} - B_{\text{initial}}$, beam self-weight is recomputed ($O.W = B \cdot h \cdot 24 \cdot 1.4$) and tributary slab rib length is reduced by $\Delta B / 2$ at each support ($L_{\text{rib,eff}} = L_0 - \Delta B / 2$).
   - This iteratively decrements the transferred load ($w_{\text{Slab}}$) and repeats analysis until beam sections, self-weights, and slab loads reach perfect physical equilibrium.
4. **Canvas Viewport Right-Edge Clipping Fix (Analysis & Design Tabs):**
   - In Tab 2 (`BeamDiagramsViewWidget`) and Tab 3 (`BeamDesignDetailWidget`), dynamic scaling and right margin ($92\text{ px}$) prevent clipping of the rightmost support reactions, shear and moment diagrams, and rebar callouts.
5. **Interactive Excel Sheet4 Flexural Design Calculation Sheet (`5_e8049e44.PNG`):**
   - Integrated full flexural design report widget beside Section A-A and longitudinal rebar elevations, rendering $h, b, d, d_c, d_b, d_s, \beta_1, n_{\text{max}}, \rho_{\text{min}}, \rho_{\text{max}}, \rho_{\text{act}}, \text{min bars}, \text{max bars}, M_u, K_u, \omega, A_s$, bar counts, and station distribution $[n_1, n_2, n_3, n_4, n_5]$.

---

## Previous Release: `v2.1.0-structural-bim-pro` (2026-11-16)
**Release Title:** Fullscreen Mode by Default, Standard Rebar Table Φ6-Φ32, Safe Dialogs, Single-Notice Thickness Warning with Math.Ceil, Unified Excel Finishing Loads, Standard Masonry Wall Dropdowns, and Complete Beam Flexural & Shear Code Implementation

### Key Features & Advancements in `v2.1.0-structural-bim-pro`:
1. **Maximized Window Launch (`win.showMaximized()`):**
   - The desktop studio automatically launches in maximized fullscreen mode on startup, providing an expansive, distraction-free CAD drafting and calculation workspace.
2. **Comprehensive Standard Rebar Diameters Table (Φ6 through Φ32):**
   - `DEFAULT_REBAR_DIAMETERS_TABLE` now officially incorporates $\Phi 6\text{ mm}$ for slab rib and beam stirrups (`Stirrups (كانات الأعصاب والكمرات)`) and $\Phi 32\text{ mm}$ for heavy longitudinal reinforcement (`Longitudinal (Heavy Beams & Columns)`), appearing in both Startup Defaults and Settings dialogs.
3. **Rock-Solid Dialog Stability:**
   - Eliminated application crash bugs when opening `Options > Materials & Hollow-Block Slab Options` or the `Slab Rib Design` dialog, ensuring seamless headless and GUI workflows.
4. **Intelligent Single-Notice Slab Thickness Warning with Ceiling Logic:**
   - If an engineer inputs a story slab thickness below the ACI 318 calculated minimum, the warning dialog appears only once per entered value (`thickness_warning_acknowledged_cm`), preventing intrusive repeated popups.
   - All minimum required slab and beam deflection thicknesses are strictly rounded up to the nearest whole centimeter using `math.ceil` (e.g. $28.125\text{ cm} \rightarrow 29\text{ cm}$).
5. **Unified Excel Finishing Loads & Exact Load Parity:**
   - Standardized finishing dead load to $W_{\text{finishing}} = 1.5\text{ kN/m}^2$, maintaining exact parity with Eng. Yousef's reference Excel sheet: $W_u(\text{rib}) = 6.44\text{ kN/m'/rib}$ and $W_u(\text{m}\times\text{m}) = 11.71\text{ kN/m}^2$.
6. **Standard Masonry Wall Thickness Dropdown Selector:**
   - Replaced free-form text input with a standard dropdown (`10 cm, 15 cm, 20 cm, 30 cm, 40 cm`), instantly computing scaled wall load:
     $$W_{\text{wall}} = 2.5 \cdot \left(\frac{t_{\text{wall}}}{20}\right) \cdot H \cdot 1.4\text{ kN/m}$$
7. **Full PDF Code Implementation for Beam Flexural & Shear Design:**
   - **Continuous $A_{s,\text{min}}$ Requirement:** Continuous top and bottom reinforcement ($n_{\text{min}} \Phi d_b$) extends uninterrupted from beam start to end.
   - **Double Reinforcement with Continuous $A_{s,\text{min}}$ (`double_as_min`):** Solves exact quadratic equilibrium equations ($x_1, x_2, c, f_s' = 600 \cdot (c - d') / c, A_{s1}, M_n, \Phi M_n$) utilizing continuous top bars as compression steel.
   - **Single Reinforcement Mode:** Full switchable support for singly reinforced sections ($K_u, \omega, \rho, A_{s,\text{calc}}, A_{s,\text{min}}$).
   - **Maximum Rebar per Layer ($n_{\text{max}}$):** Strictly calculates maximum bar count per layer based on beam width, clear cover, and bar spacing per code equations.
   - **4-Zone Shear Stirrup Design:** Complete classification across Zones 1–4 based on $V_u, \Phi V_c, V_s$ and maximum stirrup spacing limits.
8. **Reference v2.0.0 Backup Preserved:**
   - Complete reference backup of the previous release maintained in `xpert_studio_desktop/reference_v2_0_0/`.

---

## Previous Release: `v2.0.0-structural-bim-pro` (2026-11-16)
**Release Title:** Full Excel Hordi Rib Design Dialog, Live Story Slab Thickness Linkage & Warning, Dedicated Rib vs Area Load Distinction, Persistent Beam Self-Weight & Masonry Wall Policies

### Key Features & Advancements in `v2.0.0-structural-bim-pro`:
1. **Live Story Slab Thickness Linkage & Intelligent Warning Dialog:**
   - Story slab design and hollow-block dead loads dynamically adapt to the selected story slab thickness (`30.0 cm` default).
   - If an engineer inputs a slab thickness less than the calculated minimum required by ACI 318 deflection criteria, an actionable two-choice dialog appears: `Proceed with entered thickness` or `Adjust thickness to calculated minimum`.
2. **Strict Distinction Between Per-Rib Load vs Area Load to Supporting Beams:**
   - Per-Rib Factored Load $W_u(\text{rib}) = 6.44\text{ kN/m'/rib}$ ($1.4 DL + 1.7 LL$) is strictly dedicated to rib flexural and shear design:
     $$M_u = \frac{W_u(\text{rib}) \cdot L^2}{8}$$
     using the true center-to-center span $L$ between supporting beams.
   - Total square meter load $W_u(\text{m}\times\text{m}) = \frac{W_u(\text{rib})}{S + b_{w1}} = \frac{6.441}{0.55} = 11.71\text{ kN/m}^2$ is dedicated to transferring tributary slab loads onto supporting beams.
3. **Interactive Hollow-Block Slab Rib Design Dialog (`SlabRibDesignDialog`):**
   - Accessible via double-click or right-click context menu on any slab panel `S#` on the 2D CAD canvas or via the `Slab Rib Design` toolbar action.
   - Displays full step-by-step calculations matching Eng. Yousef's reference Excel sheet (`Design of rib slab`).
   - Rebar selector for bottom longitudinal bars ($d_b \in \{12, 14, 16\}\text{ mm}$), live calculation of $K_u, \omega, \rho, A_{s,\text{min}}, A_{s,\text{req}}$, adopted bars ($2\Phi 12$), top fixation bar ($1\Phi 10$), and open triangular stirrups ($\Phi 6\text{ @ }200\text{mm}$).
   - Renders a cross-section drawing of the rib showing concrete topping ($h_s$), hollow blocks ($S$), bottom rebar, open triangular stirrup, and top fixation bar.
4. **Universal Beam Self-Weight & Masonry Wall Load Formulation:**
   - Enforces beam self-weight $O.W = b \cdot h \cdot 24 \cdot 1.4\text{ kN/m}$ across all beams unconditionally.
   - Masonry wall load $W_{\text{wall}} = 2.5 \cdot (t_{\text{wall}} / 20) \cdot H \cdot 1.4\text{ kN/m}$ with span-by-span toggle and custom thickness $t_{\text{wall}}\text{ (cm)}$.
5. **Collision-Free Beam Tag Placement on 2D Canvas:**
   - Advanced geometric scoring for placing `B1..Bn` tags away from beam boundary lines, intersecting columns, and stair void openings.
6. **Reference v1.9.0 Backup Preserved:**
   - Complete reference backup of the previous release maintained in `xpert_studio_desktop/reference_v1_9_0/`.

---

## Previous Release: `v1.9.0-structural-bim-pro` (2026-11-15)
**Release Title:** Full Automatic Column Deletion & Support Reconciler, Long Single-Span Governing Slab Optimization, Drop-on-Hidden Beam Safety Lock, Piecewise Opening/Sub-Slab Load Partitioning, Ground Tie-Beams Mode & Rebar/Materials Options Dialogs

### Key Features & Advancements in `v1.9.0-structural-bim-pro`:
1. **Automatic Beam Support & Span Reconciliation (`reconcile_all_story_beams_supports_and_spans`):**
   - When deleting or shifting any column (e.g. deleting the middle column under B6 and end of B5), all intersecting beams automatically reconcile spans and support hierarchy. B6 immediately simplifies into a single continuous 9.30m span, while B5 automatically resets its lower support to carrier beam B6 (Roller) and its upper support to column C2 (Hinge).
2. **Long Single-Span Governing Slab Thickness Calculation (`evaluate_story_thickness_and_optimization`):**
   - Accurately identifies long single-span hidden beams (such as B6 at 9.30m) as the governing member (`Governing Member`) controlling minimum story thickness ($L/16$ for simple span hidden beams), triggering actionable design recommendations to convert long hidden beams into drop beams to optimize structural ceiling height and rebar quantities.
3. **Sequential Automatic Column Renumbering (`renumber_story_columns_sequentially`):**
   - Automatically maintains a clean, continuous sequence of columns from `C1` to `Cn` with zero gaps or phantom missing labels when columns are deleted or added, updating all referencing beam supports.
4. **Strict Drop-on-Hidden Beam Structural Safety Guard:**
   - Enforces core structural hierarchy rules: rejects converting a carrier beam to hidden if it supports secondary drop beams, and rejects drawing or converting a secondary drop beam supported by a hidden carrier beam (`Drop Beam on Hidden Beam` prohibited).
5. **Piecewise Sub-Interval Load Partitioning for Slabs & Openings (`Piecewise Sub-Interval Load Partitioning`):**
   - Beam spans are subdivided at opening boundaries and sub-slab partitions, guaranteeing that openings (`OP#`) and parallel slabs (0° ribs) contribute exactly zero load ($w_{slab} = 0.00\text{ kN/m}$), while adjacent sub-slabs (e.g. `S5` next to stairs) apply full tributary loads ($q_u \cdot L_y / 2$) strictly within their physical span interval.
6. **Tie-Beams Story Specialized CAD Mode (`00_TieBeams — مسقط السملات`):**
   - Streamlines the ground tie-beams drafting workflow: freezes all slab tools, hidden beams, openings, and slab thickness controls; allows direct placement of columns and drop tie beams (`3B. + Drop Beam`) immediately without requiring an outer boundary polyline.
7. **SFD Chart Title & Peak Value Collision Prevention:**
   - Clean visual layout on the Shear Force Diagram (`Shear Force Diagram - SFD (kN)`) ensuring title text never collides with or overlaps high left reaction/shear values (`27.3` or `103.8 kN`).
8. **Startup Defaults & Engineering Options Dialogs:**
   - Integrated `Startup Defaults` dialog (default project directory and rebar diameter table $\Phi 8 \dots \Phi 32$) and `Options` dialog (concrete $f'_c$, rebar $F_y$, hollow-block unit weights, flooring finishes, and wall loads) accessible both from the startup splash screen and the main menu bar.
9. **Reference v1.8.0 Backup Preserved:**
   - Standalone reference backup of the previous release maintained in `xpert_studio_desktop/reference_v1_8_0/`.

---

## Previous Release: `v1.8.0-structural-bim-pro` (2026-11-15)
**Release Title:** Carrier Beam Depth Hierarchy Auto-Enforcement, Isolated Sub-Slab Rib Flipping & Robust Bidirectional Beam Type Conversion

### Key Features & Advancements in `v1.8.0-structural-bim-pro`:
1. **Carrier Beam Depth Hierarchy Auto-Enforcement (`h_carrier >= max(h_supported)`):**
   - Implements Eng. Yousef's core structural rule #9: a primary carrier beam supporting secondary beams must have a cross-section depth greater than or equal to any secondary beam resting on it.
   - Automatically upgrades the carrier beam depth (`depth_m`) and updates all corresponding support dimension records (`depth_m`) on secondary beams during analytical topological resolution.
2. **Bidirectional Beam Type & Section Conversion (`Hidden <-> Drop`):**
   - `convert_beam_kind_and_section` fully synchronizes both `beam["beam_kind"]` and `beam["kind"]` keys when toggling Drop $\leftrightarrow$ Hidden, ensuring zero divergence between UI representation, CAD canvas rendering, and engine solvers.
3. **Targeted Sub-Slab Rib Flipping (`flip_slab_rib_by_id` & `toggle_slab_rib_by_label_click`):**
   - Enables independent flipping of small sub-slab panels (such as `S5` adjacent to internal stair openings) without unintentionally triggering re-alignment or flipping of neighboring primary slabs (e.g. `S3`).
4. **Reference v1.7.0 Backup Preserved:**
   - Standalone reference backup of the previous release maintained in `xpert_studio_desktop/reference_v1_7_0/`.

---

## Previous Release: `v1.7.0-structural-bim-pro` (2026-11-15)
**Release Title:** Single .XSD Master Standard, Crash-Proof Carrier Beam Deletion, Strict Cantilever Rib Locking, 90° Vertical SFD Jumps & Modular Multi-Workspace Architecture

### Key Features & Advancements in `v1.7.0-structural-bim-pro`:
1. **Single Unified `.xsd` Master Standard & Legacy File Cleanup:**
   - Standardized strictly on `<ProjectName>-00_Project_Master.xsd` as the single authoritative project master file.
   - `load_studio_project_from_master_file` automatically converts and cleans up legacy `.xpert` and `.json` master files.
2. **Crash-Proof Element Deletion Engine:**
   - Deleting a primary carrier beam automatically cleans up referencing supports on secondary beams without runtime errors.
   - Fully protected deletion of dimensions, slabs, and columns.
3. **Strict Structural Backspan-Cantilever Rib Direction Lock:**
   - Enforces structural safety: a back-span slab cannot have its rib direction flipped if an adjoining cantilever depends on it (cantilever ribs oriented at 90° into the backspan).
   - Prevents unreinforced cantilever failures; backspan slab is only unlocked once the cantilever ribs are safely oriented onto side beams (0°).
4. **Guaranteed Exterior CAD Dimensions Offset:**
   - Automatic exterior dimension generation (`auto_generate_exterior_dimensions`) places dimension lines strictly outside the outer slab boundary ($dy_1 > \max(Y)$ and $dx_1 < \min(X)$).
5. **Exact 90° Vertical SFD Shear Jumps & Load Formula Badges:**
   - Analytical beam solver introduces precise left/right discontinuity stations at interior supports and point loads, ensuring vertical 90° shear force jumps.
   - Distinct support classifications (`column` vs `beam`).
   - Clear analytical formula strings (`formula_str`) on all applied loads.
6. **Refactored Modular Multi-Workspace Architecture:**
   - Split complex tabs into dedicated, maintainable widgets: `BeamDiagramsViewWidget`, `BeamDesignDetailWidget`, and `SchedulesAndReportsWidget`.

---

## Previous Release: `v1.6.0-structural-bim-pro` (2026-11-14)
**Release Title:** Advanced Continuous Beam Analytical Solver, Dynamic Wall Load Policies, Interactive SFD/BMD Hover Tracker, Longitudinal R.C. Elevation, 4-Mode Stacked Workspaces & Element Context Menus

### Key Features & Advancements in `v1.6.0-structural-bim-pro`:
1. **Beam Span Segments, Support Reactions & Analytical Critical Tables:**
   - Introduced `get_beam_span_segments(beam)` decomposing continuous beams into distinct centerline segments (`cant_left`, `span_1`, `span_2`, ..., `cant_right`).
   - Enhanced `solve_continuous_beam_analytical` returning:
     - `num_spans_excluding_cantilevers`: True number of spans without cantilevers.
     - `reactions_kn`: Analytical support reactions array $[R_1, R_2, ...]$.
     - `v_left_kn`, `v_right_kn`, and `m_center_knm` in `support_critical_table`.
     - `m_max_pos_knm` and `x_at_m_max_m` in `span_critical_table`.
     - Support for both `"point"` and `"P"` load types with `dist_from_sup1_m`.
2. **Dynamic Wall Load Policies & Slab Tributary Load Transfers:**
   - Span-specific wall toggles (`set_beam_span_wall_flag`, `ensure_beam_wall_flags`) and story-wide wall policies (`set_story_wall_load_policy`: `all_beams`, `perimeter_only`, `none`).
   - Dynamic tributary slab load distribution respecting one-way hollow-block rib orientations (0° vs 90°).
   - Topological sorting of beams transferring secondary beam reactions directly as concentrated point loads onto primary carrier beams.
   - Section and kind conversion engine (`convert_beam_kind_and_section`).
3. **Dedicated 4-Mode Stacked Workspace (`QStackedWidget`):**
   - **Mode 0 (`1. 2D Structural Drawing`):** 2D CAD canvas with drawing, modify, and dimensioning toolbars.
   - **Mode 1 (`2. Beam Analysis (Loads, SFD & BMD)`):** Beam selector dropdown, story wall policy buttons, dynamic per-span wall toggles, and white-background analytical diagram widget with real-time mouse hover tracker ($X$, $V$, $M$), hatched SFD (`#1D70B8`), and hatched BMD (`#C81E1E` tension face down).
   - **Mode 2 (`3. Beam R.C. Design & Elevation`):** Beam longitudinal reinforcement elevation display (bottom & top bars, bar curtailment, stirrups) and Section A-A cross-sectional view.
   - **Mode 3 (`4. Schedules & Report`):** ACI 318 beam reinforcement schedule featuring `No. of Spans (Excl. Cantilevers)` placed between `Beam ID` and `Section (b x h)` with each span on a separate row, column design table, and master calculation report.
   - Automatic toolbar visibility switching (drawing toolbars hidden outside Mode 0).
4. **Interactive CAD Canvas Upgrades & Context Menus:**
   - Selection safety: Slab clicking in `SELECT` mode selects without accidental rib flipping.
   - Translucent live preview of column placement in `DRAW_COL` mode with Spacebar rotation toggle (0.20×0.40m ↔ 0.40×0.20m) and `NoFocus` policy on toolbar buttons.
   - Contextual Right-Click Menus (`_show_element_context_menu`) on canvas for Columns (Rotate 90°, Delete), Beams (Convert Hidden ↔ Drop, Delete), and Slabs (Flip Rib Direction 0° ↔ 90°, Delete).
   - Smart tool-adaptive cursors: Arrow for Selection, PointingHand for modify/pick, Crosshair for draw/dim, and Hand for pan.

---

## Previous Release: `v1.5.0-structural-bim-pro` (2026-11-14)
**Release Title:** Structural BIM Pro, Persistent CAD Dimensions, Analytical SFD & BMD Interactive Diagrams, Separated Toolbars & Physical Room Coalescing

### Key Features & Advancements in `v1.5.0-structural-bim-pro`:
1. **Persistent CAD Dimensions Layer (`00-XD-DIM`):**
   - Added standard layer `00-XD-DIM` in DXF export with extension lines, 45° ticks, and dimension text badges.
   - Interactive 2-click linear and aligned dimension drawing tools (`DIM_LINEAR`, `DIM_ALIGNED`).
   - One-click `Auto Exterior Dims` (`auto_generate_exterior_dimensions`) and `Clear Dims`.
2. **Crash-Proof Continuous Beam Analytical Solver & Tributary Load Transfer:**
   - 100% crash-proof analytical solver (`solve_continuous_beam_analytical`) using the exact Three-Moment Equation with empty span fallbacks.
   - Computes tributary one-way hollow-block slab loads onto supporting beams.
   - Topologically sorts beams so secondary beams are solved first and reactions transferred to carrier beams.
   - Support centerline and face-of-support moments and shears calculation ($M_u$, $V_u$).
3. **Interactive Analytical Beam Diagrams Widget (`BeamDiagramsViewWidget` in Tab 2):**
   - High-performance QPainter widget rendering Shear Force Diagram ($V_u$ in kN) and Bending Moment Diagram ($M_u$ in kN.m with positive tension downward).
   - Zero baselines, support markers, peak value badges, and real-time beam dropdown selection.
   - Fully synchronized with beam table row selection and 1-Click `Run Analysis & Design (F5)`.
4. **Separated 4-Group Classic Toolbars Layout:**
   - **Row 1 (Project & Workspace Bar):** `New Project`, `Open (*.xsd)`, `Import Arch .DXF`, `Save & Sync (Ctrl+S)`, `Story Combo`, 4 Tab Buttons, and `Run Analysis & Design (F5)`.
   - **Row 2 (Separated Toolbars):** Modify Tools (`Select`, `Align`, `Move`, `Move ΔX,ΔY`, `Rotate Col 90°`, `Delete`), Dimensions Tools (`Linear Dim`, `Aligned Dim`, `Auto Exterior Dims`, `Measure`, `Clear Dims`), and Zoom & View Tools (`Zoom Win`, `Zoom Extents`, `Pan`, `Zoom +`, `Zoom -`).
   - **Left Toolbar:** Structural BIM Modeling Tools (`Polyline Boundary`, `Place Column`, `Hidden Beam`, `Drop Beam`, `Pick Slab`, `Flip Rib`, `Pick Opening`, `Auto-Fill All Slabs`, `Demo Layout`).
   - **Row 3:** Thickness banner with `lbl_gov_member.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)` preventing off-screen clipping.
5. **Glowing Toggleable Status Bar Buttons:**
   - Converted `OSNAP [F3]` (Amber `#FACC15`), `ORTHO [F8]` (Cyan `#38BDF8`), and `GRID 0.1m [F9]` (Emerald `#4ADE80`) to checkable `QPushButton` with vibrant active states.
6. **Full-Range CAD Canvas Navigation:**
   - Unlimited panning and navigation with coordinate grid spanning -30m to +52m.
   - `Zoom Window` tool (`fitInView`) with interactive rubber-band selection.
   - Seamless cursor anchors (`AnchorUnderMouse`) and always-visible scrollbars.
   - Cleaned canvas rendering removing temporary padlock icons.
7. **Physical Beam-Bounded Room Coalescing in `detect_story_grid_bays`:**
   - Coalesces adjacent bays without physical dividing beams into single structural slab panels.
   - Preserves 2-way cantilever backspan continuity and equilibrium rules.

---

## Previous Releases

### Release: `v1.4.0-revit-bim-ux` (2026-11-14)
**Release Title:** Revit BIM UX, Custom `.xsd` Master Project Extension, Full-Face Column Bearing, Room-Bounding Clear Slabs, Window/Crossing Selection & Align/Move/Measure Tools

### Key Features & Advancements in `v1.4.0-revit-bim-ux`:
1. **Custom `.xsd` Master Project File (`<ProjectName>-00_Project_Master.xsd`):**
   - Standardized project master file extension to `.xsd` (`MASTER_FILE_EXT = ".xsd"`) with backward compatibility for `.xpert` and `.json`.
   - Updated `initialize_studio_project` and `load_studio_project_from_master_file` to support double-click launching and direct path resolution.
   - Cleaned unprefixed duplicates including `.xsd`.
2. **Revit-Style Full Outer-Face Column Bearing:**
   - When drawing beams between column centers, beam ends automatically project to the column outer faces (`sx = cx1 - b1/2` to `ex = cx2 + b2/2`).
   - Lateral boundary shift: If beam lateral face protrudes outside the building boundary, the beam axis automatically shifts inward flush with the perimeter.
   - Collinear overlapping beam prevention & duplicate column collision detection.
3. **Revit Room-Bounding Bay & Slab Detection:**
   - Slabs are never generated from the outer boundary polyline alone; at least 3 beams are required.
   - Calculates clear inner bounds (`clear_min_x, clear_max_x, clear_min_y, clear_max_y`) by subtracting beam widths so ribs and slab bodies never overlap beam concrete.
4. **AutoCAD Window vs Crossing Selection (`SELECT`):**
   - Dragging Left-to-Right produces a Blue solid box selecting only items fully enclosed inside.
   - Dragging Right-to-Left produces a Green dashed box selecting any items crossing or touched by the window.
5. **Revit-Style Align (`AL`), Move (`MV`) & Measure (`DI`) Tools:**
   - **Align [AL]:** Aligns column/beam faces (left, right, top, bottom) to reference coordinates with optional lock constraints (`locked_alignments`).
   - **Move [MV]:** Interactive base-point to target-point movement and numeric delta input dialog (`MoveNumericDeltaDialog`).
   - **Measure [DI]:** Instant 2D distance, delta X, delta Y, and angle measurement in status prompt.
6. **Startup Welcome Dialog (`StartupWelcomeDialog`):**
   - Clean launch screen offering: "Start a New Structural Project" or "Open an Existing Project (*.xsd)".

---

## Previous Release: `v1.3.0-smart-cad-intelligence` (2026-11-14)
**Release Title:** Smart CAD Intelligence, Architectural DXF Underlay Block, Layer Visibility & Freeze Control, Zero Duplicates & Automated Multi-Span / Slab Splitting

### Key Features & Advancements in `v1.3.0-smart-cad-intelligence`:
1. **Architectural DXF Underlay Block (`import_arch_dxf_underlay`):**
   - High-fidelity extraction of `LINE`, `LWPOLYLINE`, `POLYLINE`, and `CIRCLE` entities from architectural `.DXF` files into a dedicated `arch_underlay_block` per story.
   - Top toolbar **`Import Arch .DXF`** button for the active story.
   - Rendered in CAD Canvas as a locked reference block in quiet slate gray (`#64748B`), unaffected by deletion tools, with magnetic snap integration (OSNAP).

2. **Layer Visibility & Freeze Control Bar:**
   - Interactive checkbox bar above CAD canvas controlling: `Arch DXF Block`, `Columns`, `Beams`, `Slabs & Ribs`, and `Labels`.
   - Freezing `Slabs & Ribs` turns off slab rendering and completely freezes slab snapping/clicking for obstruction-free beam drawing.

3. **Updated Default Hidden Beam Width (`0.40 m`):**
   - Hidden beams default width reduced from `0.60 m` to `0.40 m` (`40 cm`), while drop beams remain standard `0.20 m` (`20 cm`).

4. **Strict Tool Isolation:**
   - 1-click rib direction toggling is strictly isolated to `SELECT` and `PICK_FLIP_RIB` tools when the `Slabs & Ribs` layer is active, preventing accidental rib flips when placing columns or drawing beams.

5. **Zero Duplicates & Zero Sliver Bays (`xpert_structural_engine.py`):**
   - `check_duplicate_column`: Blocks column overlapping or duplication.
   - `check_duplicate_beam`: Rejects duplicate overlapping beams on the same axis.
   - Automatic continuous multi-span beam subdivision: 2-click beam placement detects all intermediate column and beam supports, computing consecutive spans automatically.
   - `detect_story_grid_bays`: Merges perimeter beams within `max(0.45, width_m + 0.15)` with the outer boundary and discards sliver bays where `lx < 0.85 m` or `ly < 0.85 m`.

6. **Smart Automatic Slab Splitting on Cutting Beam (`reconcile_and_split_slabs_after_beam_change`):**
   - When a beam cuts through an existing slab, the engine automatically splits the parent slab into independent sub-slabs supported by the new beam and recalculates ACI 318 deflection thicknesses immediately.

7. **Column Containment, Cursors & Productivity Actions:**
   - 100% column cross-section containment inside the building boundary (including `Demo Layout`).
   - Context-sensitive cursors: `ArrowCursor` in `SELECT`, `OpenHandCursor`/`ClosedHandCursor` in `PAN`, `CrossCursor` in drawing tools.
   - **`Rotate Col 90° (R)`**: Rotates selected column by 90 degrees with boundary re-clamping.
   - **`Auto-Fill All Slabs`**: 1-click automatic furnishing of all detected bays with code-default slabs.

---

## Previous Release: `v1.0.0-studio-foundation` (2026-11-13)
**Release Title:** Standalone All-in-One Structural CAD, Analysis & Design Studio (ETABS / SAFE / Robot Paradigm with Built-in AutoCAD-Style 2D Modeler)

### Major Architectural Pivot & Achievements in `v1.0.0-studio-foundation`:
1. **100% Standalone Studio Architecture (Zero External AutoCAD Plugin Dependency):**
   - Replaced the legacy C# AutoCAD plugin bundle with a built-in interactive 2D Structural CAD Modeler inside **Xpert Structural Design Studio** (`PyQt6` Desktop App in `/xpert_studio_desktop/` + Web Studio Twin in `/src/`).
   - **100% English-Only Application Interface (`LTR`):** All menus, toolbars, dialogs, CAD layers, engineering tables, diagrams, and calculation sheets are strictly in English.
   - **Zero Ribbon Policy:** Uses a classic top pull-down Menu Bar (`File | Draw & CAD Modeler | Define Criteria | Analyze | Design | Detailing | Reports | GitHub & VS Code Sync`), a top Standard Toolbar, and a Left Vertical CAD Drawing Toolbar.

2. **Modal New Project Initialization & Clean `<ProjectName>-` File Sync:**
   - **Modal New Project Setup Dialog:** Collects Project Name, Engineer Name, Floors Configuration (`Basement`, `Ground Floor [Mandatory]`, `Floors Above Ground`, `Typical Floor Mode`, `Ground Floor Height [Mandatory]`, `Typical Story Height`, `Foundation Depth`), Material & Load Criteria (`f'c`, `fy` up to `1000 MPa`, `q_all` up to `2000 kN/m²`), and Geometry Defaults (`Default Slab Thickness = 30 cm`, `Hidden Beam Width = 30 cm`, `Drop Beam = 20×40 cm`).
   - Clicking **`OK — Create Project & Open Studio`** generates `Stractural-<ProjectName>/` with `00_Project_Master.json`, `Stories_Data/<ProjectName>-<Story>.json`, and `CAD_Drawings/<ProjectName>-<Story>.dxf`.
   - **Zero Duplicate Unprefixed Files:** Automatically removes any legacy unprefixed `.dxf` / `.json` files and prevents duplicate `02_Roof_Floor` creation when `Floors Above Ground = 0`.
   - Opens the studio directly on **`02_Ground_Floor` (`Ground Floor Slab`)**.

3. **Built-in 2D CAD Modeler & Non-Overlapping Color-Coded Tagging:**
   - Supports Architectural `.DXF` Underlay import, OSNAP (`Endpoint`, `Midpoint`, `Column Center`), Ortho (`F8`), Interactive Column Placement (`C1..Cn`), Column Orientation Toggle (`H`/`V`), Upper-Story Column Discontinuation (`Active` / `Stopped` without shifting IDs), Continuous Polyline Beams (`Hidden` & `Drop`), Hollow-Block Slab Rib Orientation (`0°` / `90°`), and Void Openings.
   - **Distinct Non-Overlapping Tags (Visible on Screen & Saved inside `.DXF`):**
     - **Columns (`C1..Cn`):** Layer `00-XD-TAG-COL`, **Bright Green (`#4ADE80` / ACI Color 3)**, placed **outside the top-right corner of the column** so they never collide with beam centerlines.
     - **Beams (`B1..Bm`):** Layer `00-XD-TAG-BEAM`, **Bright Orange (`#FB923C` / ACI Color 30)**, rotated parallel to the beam and placed at the **midpoint of the first clear span (strictly between columns, never on top of an intermediate column!)**.

4. **Automatic Background ACI 318 Thickness Control & Smart Optimization Advisor:**
   - Continuously evaluates clear spans ($L_n$) for all one-way ribs and beams on the active story.
   - Displays a Read-Only `Calculated Min. Thickness` and `Governing Critical Case` alongside the user's `Adopted Story Slab Thickness (default = 30 cm)`, with a warning prompt if `Adopted < Calculated`.
   - **Smart Drop-Beam Advisor:** If a single long Hidden Beam requires $> 30\text{ cm}$ while the rest of the floor requires $\le 30\text{ cm}$, offers a 1-click conversion of that Hidden Beam into a Drop Beam (`20×50 cm`) to preserve the `30 cm` slab thickness.

5. **1-Click `Analyze All Beams (F5)` + Interactive Beam Inspector:**
   - Performs topological sort (`Secondary / Carried Beams` $\rightarrow$ `Primary / Carrying Beams`), transfers point reactions automatically, and solves all beams using the `Slope-Deflection` engine.
   - Displays an **All-Beams Master Summary Table** alongside an interactive **Single-Beam Inspector** with **1D Analytical Elevation** (`Hinge △` for Column, `Roller △○○` for Beam), **Shear Force Diagram (SFD)**, **Bending Moment Diagram (BMD, positive downward)**, and **Face-of-Support Critical Forces Table**.

6. **R.C. Design, Column 4-Way Framing Connectivity, P-M Interaction & Master Calculation Report:**
   - Designs all beams according to `ACI 318` (flexural reinforcement + shear stirrups).
   - Tracks for every column: story load, cumulative axial load ($\sum P_u$), end moments ($M_{ux}, M_{uy}$), and **4-Way Framing Beams (`North, South, East, West`)**, generates **ACI 318 P-M Interaction Diagrams**, and exports `SPColumn (.cti)` files.
   - Designs isolated footings (`Foundations_Design.json`) and generates a printable **Master Calculation Report** (`Ctrl+P`).

## v2.4.1-structural-bim-pro (2026-11-18)
- CENTERLINE design moments for beams & slabs (permanent Eng. Yousef rule); face values kept for display only.
- Wall-load routing fixed: TieBeams carry ground walls (3.20m -> 11.20 kN/m); Ground carries first-floor walls (3.00m -> 10.50 kN/m).
- Hidden beam baseline width 300mm (Excel Con.Beam), stirrups ds=6 hidden / ds=8 drop.
- Tie-beam drop baseline depth 400mm (legacy 500mm removed); TieBeams skip phantom Hordi slab.
- Opening merge respects 0.20m trimmer dividers; slab bays subtract openings.
- Options > Project Data: edit story count / heights / foundation depth / materials post-creation (columns preserved).
- Regression suite expanded 20 -> 24 tests (centerline Excel parity, wall routing, hidden300/ds6, trimmer divider + project regen).
- Backup of v2.4.0 preserved in xpert_studio_desktop/reference_v2_4_0/.

## v2.4.2-structural-bim-pro (2026-11-18)
- Persistent editable Minimum Beam Sections (Hidden width / Drop depth) via Sections menu, project-wide.
- Auto-migration of OLD projects on load (wall policy, min sections, flush slab clear bounds, tie purge).
- No-upper-floor => ground beams default NO wall load (per-span checkbox still available).
- Tie-beam plan fully purged of slab loads/openings.
- Slab clear bounds flush to ACTUAL beam widths (closes rib/beam gaps).
- CAD canvas sceneRect bounded + fit-on-load (no off-screen overflow).
- 28 regression tests.
