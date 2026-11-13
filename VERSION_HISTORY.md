# Xpert Structural Design Studio — Version History & Changelog

This file tracks all releases of **Xpert Structural Design Studio** (`v1.0.0-studio-foundation`) for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`).

---

## Current Release: `v1.0.0-studio-foundation` (2026-11-13)
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
