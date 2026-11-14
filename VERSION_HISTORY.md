# Xpert Structural Design Studio — Version History & Changelog

This file tracks all releases of **Xpert Structural Design Studio** for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`).

---

## Current Release: `v1.6.0-structural-bim-pro` (2026-11-14)
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
