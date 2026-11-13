# Xpert Structural Design Studio — Master Engineering & Architectural Blueprint

**Project Title:** `Xpert Structural Design Studio`  
**Lead Structural Engineer & Product Owner:** Eng. Yousef Mohammed Keshlaf  
**Initial Studio Release Tag:** `v1.0.0-studio-foundation`  
**UI Language & Direction Policy:** **100% English-Only UI (`LTR`)** across all windows, menus, toolbars, dialogs, CAD layers, plots, and calculation reports.

---

## 1. Executive Vision & Core Philosophy
`Xpert Structural Design Studio` is an all-in-one, standalone structural engineering desktop application (`Python PyQt6` + `ezdxf` + `numpy` + `shapely` + `matplotlib`) accompanied by a synchronized interactive Web Studio twin here in AI Studio.

Inspired by the integrated workflow of **ETABS**, **CSI SAFE**, and **Autodesk Robot Structural Analysis**, while retaining the **speed, comfort, and snapping simplicity of AutoCAD**, the application eliminates reliance on external AutoCAD plugins (`C# .bundle` / COM menus) and places the entire structural workflow inside one cohesive studio:
1. **Modal Project Definition (`New Project Dialog`)** $\rightarrow$
2. **Built-in 2D Structural CAD Modeling Studio (with Architectural `.DXF` Underlay & Live `.DXF` / `.JSON` Sync)** $\rightarrow$
3. **Automatic ACI 318 Deflection Thickness Control & Smart Engineering Optimization** $\rightarrow$
4. **1-Click Topological Story Beam Analysis (`Analyze All Beams`) & Interactive Beam Inspector** $\rightarrow$
5. **ACI 318 Structural Design (Beams via VBA logic, Columns with 4-Way Framing & P-M Diagrams + `SPColumn .cti`, Foundations) & Automated CAD Detailing (`.DXF`)** $\rightarrow$
6. **Master Printable Engineering Calculation Report & Bill of Quantities (`BOQ`)**.

---

## 2. User Interface & Workspace Architecture (Zero Ribbon Policy)
1. **Startup & Modal Project Setup (`File -> New Project...`):**
   - Starting a new project opens a dedicated **Modal Project Definition Dialog** (not a permanent tab).
   - Once the engineer enters the project parameters and clicks **`OK / Create Project`**:
     - The dialog closes automatically.
     - The application generates the `Stractural-<ProjectName>` workspace directory and all `<ProjectName>-` prefixed `.json` and `.dxf` files on disk.
     - The main studio opens directly on the mandatory starting floor: **`02_Ground_Floor`**.
2. **Classic Engineering Studio Layout (No Ribbon):**
   - **Top Classic Pull-Down Menu Bar (`Menu Bar`):**
     - `File` (New Project, Open Project, Import Arch DXF Underlay, Save Story & Sync DXF `Ctrl+S`, Export Drawings, Exit)
     - `Edit` (Undo, Redo, Delete Selected, Clear Story Tags)
     - `View` (Zoom Extents, Zoom Window, Toggle Grid, Toggle Ortho `F8`, Toggle OSNAP `F3`, Layer Visibility)
     - `Draw` (Draw Slab Boundary, Draw Slab Opening, Draw Column, Convert Arch Columns, Discontinue Column, Draw Hidden Beam, Draw Drop Beam, Set One-Way Rib Direction)
     - `Define` (Project Master Criteria, Materials & Soil, Story Hierarchy & Heights, Section Defaults)
     - `Analyze` (Check Story Model, Evaluate ACI 318 Thickness, **Analyze All Beams `F5`**, Analyze Selected Beam, Column Load Takedown)
     - `Design` (Design All Beams [ACI 318], Design Columns & P-M Diagrams, Export SPColumn `.cti`, Design Foundations)
     - `Detailing & CAD` (Generate Beam Reinforcement Drawings `.DXF`, Generate Foundations & Axes `.DXF`, Open Story `.DXF` Folder)
     - `Reports` (Generate Master Calculation Report, Export BOQ Quantities Report)
     - `Help` (Engineering Reference & Version History)
   - **Top Classic Standard & Mode Toolbar:**
     - Quick icons/buttons for New, Open, Save & Sync `.DXF`, Active Story Selector (`00_TieBeams`, `02_Ground_Floor`, `03_Typical_Floor`...), Workspace Mode Switcher (`[1] 2D CAD Modeler` | `[2] Beam Analysis` | `[3] R.C. Design & Detailing` | `[4] Calculation Report`), and **`Analyze All Beams (F5)`**.
   - **Left Vertical Classic CAD Drawing Toolbar:**
     - `Select / Pick`, `Pan`, `Zoom Extents`, `Import Arch DXF`, `Slab Edge`, `Opening`, `Draw Column`, `Convert Arch Column`, `Discontinue Column`, `Hidden Beam`, `Drop Beam`, `Rib Direction`, `Measure`.
   - **Left Explorer & Story Thickness Dock:**
     - Displays the Story Tree, the live **ACI 318 Calculated Min. Thickness (Read-Only)** + **Governing Critical Member**, the editable **Adopted Story Slab Thickness (`default = 30.0 cm`)**, the **Smart Drop-Beam Optimization Suggestion Banner**, and the Selected Element Properties table.

---

## 3. Project Folder & File Naming Specification (`Stractural-<ProjectName>`)
Every generated file inside `Stractural-<ProjectName>` is strictly prefixed with `<ProjectName>-` (zero unprefixed duplicates):
- **Root Master Files:**
  - `<ProjectName>-00_Project_Master.json`
  - `<ProjectName>-Columns_Load_Takedown.json`
  - `<ProjectName>-Foundations_Design.json`
  - `<ProjectName>-BOQ_Quantities.json`
- **`Stories_Data/` (JSON Structural Databases per Story):**
  - `<ProjectName>-00_TieBeams.json` (Tie-Beams / Grade Beams; zero slab load, all beams are Drop Beams)
  - `<ProjectName>-01_Basement_Slab.json` (Optional; created only if `Include Basement` is checked)
  - `<ProjectName>-02_Ground_Floor.json` (**Mandatory starting story** where master columns `C1..Cn` are established)
  - `<ProjectName>-03_Typical_Floor.json` (or `<ProjectName>-03_First_Floor.json`, `<ProjectName>-04_Second_Floor.json` if `Floors Above Ground > 0`)
  - `<ProjectName>-XX_Penthouse_Floor.json` (Optional; created only if `Include Roof Annex / Penthouse` is explicitly checked; `False` by default)
- **`CAD_Drawings/` (Synchronized Standard `.DXF` Drawings, `$INSUNITS = 6` Meters, $Z = 0$):**
  - `<ProjectName>-00_TieBeams.dxf`
  - `<ProjectName>-02_Ground_Floor.dxf` (and other active stories)
  - `<ProjectName>-Foundations_And_Axes.dxf`
  - `<ProjectName>-Beams_Reinforcement_Details.dxf`

---

## 4. Built-in 2D Structural CAD Studio & Smart Auto-Numbering Rules
1. **Smooth AutoCAD-Style Interaction (Without ETABS Grid Hassle):**
   - Dark CAD canvas (`#0D1117`), Scroll-Wheel Zoom at cursor, Middle-Button Pan, Crosshair cursor, `Ortho (F8)`, and magnetic `OSNAP (F3)` (Endpoint, Midpoint, Intersection, Column Center, Perpendicular).
   - **Import Architectural `.DXF` Underlay:** Load any external architectural `.dxf` plan as a locked gray reference layer to snap or convert elements directly.
   - **1-Click / Box-Select Column Conversion:** Click or drag a box over architectural column rectangles to convert them directly into structural columns `C1..Cn` with exact `(b, h, x, y)`.
   - **Magnetic Column-to-Column & Beam-to-Beam Drawing:** Clicking from column to column (or support beam) draws continuous multi-span Hidden Beams (`00-XD-BEAM-HID`, default min width `30 cm`) or Drop Beams (`00-XD-BEAM-DROP`, default width `20 cm`) and automatically records support types (`COLUMN` vs `BEAM`).
   - **Auto-Detected Slab Bays & One-Way Rib Direction:** Closed regions bounded by beams are detected as Hollow-Block Slab panels (`00-XD-SLAB`) where a single click sets the one-way rib direction (`0° Horizontal` or `90° Vertical`) or defines an opening (`00-XD-OPEN`).
2. **Color-Coded, Non-Overlapping Sequential Numbering (`C1..Cn` & `B1..Bm`):**
   - **Chronological Creation Order:** Elements are numbered sequentially in the order they are created (preserving existing IDs on edits, and filling deleted gaps on `02_Ground_Floor`).
   - **Ground Floor Column Propagation:** Saving/confirming `02_Ground_Floor` automatically propagates columns `C1..Cn` with their exact IDs to `00_TieBeams` and all upper stories. Discontinuing a column in an upper story removes it from that story and above **without changing remaining column IDs**.
   - **Visual Tag Separation (Both on Canvas and inside `.DXF` files):**
     - **Column Tags (`C1..Cn`):** Layer `00-XD-TAG-COL`, **Bright Green (ACI Color 3)**, `Arial` bold style (`height = 0.22m`), placed **outside the top-right corner of the column** (`+0.12m, +0.12m`) so it never collides with beam centerlines.
     - **Beam Tags (`B1..Bm`):** Layer `00-XD-TAG-BEAM`, **Bright Orange (ACI Color 30)**, `height = 0.25m`, rotated parallel to the beam (`0°` or `90°`), placed at the **midpoint of the first/longest clear span (strictly between columns, never on top of an intermediate column!)** and offset `+0.22m` perpendicular to the beam.

---

## 5. ACI 318 Automatic Thickness Control & Smart Optimization Advisor
1. **Silent Background Evaluation per Story:**
   - As soon as beams/slabs exist in a story, the engine computes face-to-face clear spans ($L_n = L_{c-c} - w_{\text{left}}/2 - w_{\text{right}}/2$) and required minimum thickness per ACI 318 ($L_n / 16$, $L_n / 18.5$, $L_n / 21$, $L_n / 8$ adjusted by $(0.4 + f_y/700)$).
   - If a story has no beams/slabs yet, it displays `-- (Awaiting CAD Elements)`.
2. **Read-Only Calculated vs. Editable Adopted Thickness (`30 cm` Default):**
   - Displays `Calculated Min. Thickness (cm)` and `Governing Critical Member` in read-only badges alongside the editable `Adopted Story Slab Thickness (cm)` (`default = 30.0 cm`).
   - If the engineer enters a value `< Calculated Min. Thickness`, a warning dialog informs them and gives full freedom to **`Continue with Entered Value`** or **`Modify Thickness`**.
   - Hollow-block height auto-adjusts: $t_s \le 24\text{ cm} \rightarrow h_{\text{block}} = 16\text{ cm}$; $t_s \ge 25\text{ cm} \rightarrow h_{\text{block}} = 20\text{ cm}$ (block footprint $40 \times 25\text{ cm}$, weight $0.10\text{ kN}$, default rib width $15\text{ cm}$).
3. **Smart Drop-Beam Optimization Suggestion:**
   - When `Calculated Min. Thickness > 30.0 cm` AND the critical element governing that thickness is a **Hidden Beam** while the rest of the floor requires $\le 30.0\text{ cm}$, an interactive banner recommends converting that specific Hidden Beam to a **Drop Beam** with one click so the slab thickness remains `30.0 cm`.

---

## 6. Topological Story Analysis, Column Connectivity & Load Takedown
1. **1-Click `Analyze All Beams` + Individual Beam Inspector:**
   - Topological sorting analyzes supported secondary beams first and transfers their reactions as concentrated loads ($P_u$) onto primary supporting beams.
   - Solves all continuous beams via the analytical **Slope-Deflection Method** (without exposing solver jargon in UI button labels).
   - Displays a **Master Story Beams Summary Table** (all beams at a glance) AND an interactive **Beam Diagram Inspector** showing:
     - 1D Analytical Beam Elevation with **Hinge ($\triangle$)** for Column supports and **Roller ($\triangle\circ\circ$)** for Beam supports.
     - Shear Force Diagram (`SFD`) and Bending Moment Diagram (`BMD`, positive sagging plotted downward).
     - Critical Forces Summary Table at support centerlines and **at Face of Support ($-M_{u,\text{face}}, V_{u,\text{face}}, R_u$)**.
2. **Comprehensive Column Load, End-Moment & 4-Way Framing Storage:**
   - Every column `C#` at every story stores:
     - Story axial loads ($P_D, P_L, P_u$) and cumulative multi-story takedown loads ($\sum P_D, \sum P_L, \sum P_u$) in `<ProjectName>-Columns_Load_Takedown.json`.
     - Transferred end moments ($M_{ux}, M_{uy}$) at top and bottom column joints.
     - **Framing Beams Connectivity (`North, South, East, West` at Upper & Lower Joints):** IDs, sections ($b \times h$), and clear lengths of all beams framing into the column from all sides.

---

## 7. Structural Design, CAD Detailing & Master Calculation Report
1. **ACI 318 Beam Design & Detailing:**
   - Integrates Eng. Yousef's Excel VBA ACI 318 beam design methodology (top/bottom flexural bars, shear stirrups, deflection check) and exports beam reinforcement drawings to `.dxf`.
2. **Column Design, P-M Interaction Diagrams & `SPColumn (.cti)` Export:**
   - Designs columns per ACI 318, plots **P-M Interaction Diagrams** for each column, and exports batch `.cti` files for `SPColumn`.
3. **Foundation Design & `<ProjectName>-Foundations_And_Axes.dxf`:**
   - Aggregates total column loads and moments at foundation level, designs footings against soil bearing capacity $q_{\text{all}}$, punching shear, one-way shear, and flexure, and automatically plots footings and structural grid axes (`1, 2...` / `A, B...`) into `<ProjectName>-Foundations_And_Axes.dxf`.
4. **Master Printable "Calculation Report" (`PDF / HTML`):**
   - Generates a complete, client- and municipality-ready **Structural Calculation Report** containing:
     - Design Criteria, Materials, Loads & ACI 318 Thickness Checks.
     - Full Beam Calculation Sheets (Load diagrams, SFD, BMD, support reactions, and flexural/shear reinforcement for every beam in the slab).
     - Column Load Takedown Tables, Framing Connectivity, Column Design & **P-M Interaction Diagrams**.
     - Foundation Design Calculation Sheets & Bill of Quantities (`BOQ`).
