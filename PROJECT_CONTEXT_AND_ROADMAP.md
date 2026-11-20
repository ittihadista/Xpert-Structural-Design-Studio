# Xpert Structural Design Studio — Master Context & VS Code / Antigravity Roadmap (`v1.0.0-studio-foundation`)

This document is the primary reference for **Eng. Yousef Mohammed Keshlaf** (`xpert.tifosamp@gmail.com`) and the **Antigravity AI Agent inside VS Code**. Read this file together with `/STUDIO_MASTER_BLUEPRINT.md` before modifying any module.

---

## 1. Project Identity & Core Architecture
- **Application Name:** `Xpert Structural Design Studio`
- **Current Release:** `v2.4.14-structural-bim-pro`
- **Architectural Paradigm:** Standalone structural engineering studio inspired by **ETABS / SAFE / Autodesk Robot**, featuring a built-in AutoCAD-comfort 2D CAD modeler, topological load distributor, Slope-Deflection continuous beam solver, ACI 318 R.C. designer, column 4-way framing & P-M interaction engine, foundation designer, and master calculation report generator.
- **Language Rule:** **100% English-Only UI (`LTR`)** across all menus, toolbars, dialogs, CAD layers, diagrams, and calculation reports.

---

## 2. Repository Structure
1. **`/STUDIO_MASTER_BLUEPRINT.md`**
   - Comprehensive specification of the studio's architecture, UI layout, file naming rules, color-coded CAD tagging rules, ACI 318 thickness advisor, and analysis/design workflows.
2. **`/xpert_studio_desktop/` (Standalone Python PyQt6 Desktop Studio for Windows/macOS/Linux):**
   - `xpert_studio_app.py`: Main PyQt6 application window with Modal New Project Setup Dialog, Classic Top Pull-Down Menu Bar (`Zero Ribbon`), Top Standard Toolbar, Left Vertical CAD Drawing Toolbar, Interactive 2D QGraphicsView CAD Canvas, 1-Click `Analyze All Beams (F5)`, Beam SFD/BMD Inspector, Column 4-Way Framing & P-M Curve Viewer, and Printable Calculation Report.
   - `xpert_project_io.py`: Project folder initializer (`Stractural-<ProjectName>`) and direct `.JSON` + `.DXF` reader/writer with `<ProjectName>-` file prefixing, zero duplicate files, and non-overlapping color-coded tags (`Green C#` outside top-right corner, `Orange B#` at midpoint of first clear span).
   - `xpert_structural_engine.py`: Pure Python structural engine (ACI 318 clear-span thickness calculator & smart optimization advisor, topological beam sort, Slope-Deflection solver, face-of-support shear/moment extractor, ACI 318 beam/column design, P-M curve generator, and `SPColumn .cti` exporter).
   - `test_studio_engine.py`: Automated Python unit test suite (`python3 xpert_studio_desktop/test_studio_engine.py -v`).
   - `requirements.txt`: Python dependencies (`PyQt6`, `matplotlib`, `numpy`, `ezdxf`).
3. **`/src/` (Interactive Web Studio Twin in TypeScript + React):**
   - `src/App.tsx`: Full Web Studio interface mirroring the desktop workflow.
   - `src/components/CadFloorPlanCanvas.tsx`: Interactive 2D Structural CAD Canvas with Left Vertical Classic Toolbar, OSNAP, Ortho, column/beam drawing, and non-overlapping Green/Orange tags.
   - `src/components/BeamDiagramsCanvas.tsx`: 1D Analytical Elevation (`Hinge △` / `Roller △○○`), SFD, BMD, and Face-of-Support Critical Forces Table.
   - `src/components/VsCodeExportTab.tsx`: GitHub & VS Code Synchronization Center with 1-click script downloads and Antigravity prompt copy.
   - `src/engine/structuralEngine.ts` & `src/engine/structuralEngine.test.ts`: TypeScript structural engine and automated unit tests (`npx tsx --test src/engine/structuralEngine.test.ts`).
4. **`/public/assets/aistudio/main_66c6cd7f.py`:**
   - Original reference Slope-Deflection continuous beam solver by Eng. Yousef Mohammed Keshlaf.
