# Xpert Structural Design Studio — Version History & Changelog

This file tracks all releases of **Xpert Structural Design Studio** (`v1.0.0-studio-foundation`) for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`).

---

## Current Release: `v1.3.0-smart-cad-intelligence` (2026-11-14)
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
