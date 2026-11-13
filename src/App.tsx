import React, { useState, useMemo } from 'react';
import {
  generateProjectWorkspace,
  computeClearSpanAndACIDeflection,
  runSequentialFloorAnalysis,
  designColumnAciAndExportSpColumn,
  exportStoryToDxfContent,
  type ProjectMasterConfig,
  type StructuralBeamModel,
  type StructuralColumnModel,
  type SlabPanelModel,
} from './engine/structuralEngine';
import {
  DEFAULT_MASTER_CONFIG,
  INITIAL_COLUMNS,
  INITIAL_BEAMS,
  INITIAL_SLABS,
} from './engine/demoStructuralProject';
import { CadFloorPlanCanvas } from './components/CadFloorPlanCanvas';
import { BeamDiagramsCanvas } from './components/BeamDiagramsCanvas';
import { VsCodeExportTab } from './components/VsCodeExportTab';

type StudioMode = 'CAD_MODELER' | 'BEAM_ANALYSIS' | 'RC_DESIGN' | 'CALC_REPORT' | 'GITHUB_SYNC';

export function App() {
  const [config, setConfig] = useState<ProjectMasterConfig>(DEFAULT_MASTER_CONFIG);
  const [draftConfig, setDraftConfig] = useState<ProjectMasterConfig>(DEFAULT_MASTER_CONFIG);
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState<boolean>(false);

  const [studioMode, setStudioMode] = useState<StudioMode>('CAD_MODELER');
  const [activeStoryId, setActiveStoryId] = useState<string>('02_Ground_Floor');

  const [columns, setColumns] = useState<StructuralColumnModel[]>(INITIAL_COLUMNS);
  const [beams, setBeams] = useState<StructuralBeamModel[]>(INITIAL_BEAMS);
  const [slabs, setSlabs] = useState<SlabPanelModel[]>(INITIAL_SLABS);

  const [selectedBeamId, setSelectedBeamId] = useState<string>('B2');
  const [selectedColumnId, setSelectedColumnId] = useState<string>('C5');

  const [adoptedSlabThicknessCm, setAdoptedSlabThicknessCm] = useState<number>(30);
  const [thicknessWarningMsg, setThicknessWarningMsg] = useState<string | null>(null);

  const workspace = useMemo(() => generateProjectWorkspace(config), [config]);
  const activeStoryEntry = useMemo(
    () =>
      workspace.filesTree.stories.find((s) => s.storyId === activeStoryId) ||
      workspace.filesTree.stories[0],
    [workspace, activeStoryId]
  );

  // Automatic Background ACI 318 Deflection Thickness Evaluation
  const deflectionReport = useMemo(
    () => computeClearSpanAndACIDeflection(beams, slabs, config.fyMpa),
    [beams, slabs, config.fyMpa]
  );

  // 1-Click Topological Floor Analysis
  const floorAnalysis = useMemo(
    () =>
      runSequentialFloorAnalysis(
        beams,
        columns,
        activeStoryEntry.storyType,
        activeStoryEntry.heightM,
        config.fcMpa,
        config.fyMpa
      ),
    [beams, columns, activeStoryEntry, config.fcMpa, config.fyMpa]
  );

  const activeBeam = useMemo(
    () =>
      floorAnalysis.updatedBeams.find((b) => b.id === selectedBeamId) ||
      floorAnalysis.updatedBeams[0],
    [floorAnalysis, selectedBeamId]
  );

  const activeBeamResult = useMemo(
    () => (activeBeam ? floorAnalysis.beamResults[activeBeam.id] : undefined),
    [floorAnalysis, activeBeam]
  );

  const activeColSummary = useMemo(
    () =>
      floorAnalysis.columnReactionsSummary.find((c) => c.columnId === selectedColumnId) ||
      floorAnalysis.columnReactionsSummary[0],
    [floorAnalysis, selectedColumnId]
  );

  const totalStoriesMultiplier = useMemo(
    () => workspace.filesTree.stories.reduce((acc, s) => acc + s.multiplier, 0),
    [workspace]
  );

  const activeColDesign = useMemo(() => {
    if (!activeColSummary) return null;
    const cumulativePuKn = Number(
      (activeColSummary.totalFloorLoadKn * Math.max(1, totalStoriesMultiplier - 1)).toFixed(1)
    );
    return {
      cumulativePuKn,
      ...designColumnAciAndExportSpColumn(
        activeColSummary.columnId,
        activeColSummary.bM,
        activeColSummary.hM,
        cumulativePuKn,
        activeColSummary.muxKnM,
        activeColSummary.muyKnM,
        config.fcMpa,
        config.fyMpa
      ),
    };
  }, [activeColSummary, totalStoriesMultiplier, config.fcMpa, config.fyMpa]);

  // Handlers
  const handleCreateOrUpdateProject = (e: React.FormEvent) => {
    e.preventDefault();
    setConfig(draftConfig);
    setActiveStoryId('02_Ground_Floor');
    setIsNewProjectModalOpen(false);
    setStudioMode('CAD_MODELER');
  };

  const handleApplyThickness = (valCm: number) => {
    const reqCm = deflectionReport.recommendedUnifiedSlabAndHiddenCm;
    if (beams.length > 0 && valCm < reqCm) {
      setThicknessWarningMsg(
        `Entered slab thickness (${valCm.toFixed(1)} cm) is less than the ACI 318 calculated minimum thickness (${reqCm.toFixed(1)} cm) governed by ${
          deflectionReport.maxRequiredHiddenBeamThicknessCm >= deflectionReport.maxRequiredSlabThicknessCm
            ? deflectionReport.governingHiddenBeamElement
            : deflectionReport.governingSlabElement
        }. You may continue with ${valCm.toFixed(1)} cm at your engineering discretion or modify it.`
      );
    } else {
      setThicknessWarningMsg(null);
    }
    setAdoptedSlabThicknessCm(valCm);
    setConfig((prev) => ({ ...prev, slabThicknessCm: valCm }));
  };

  const handleConvertCriticalBeamToDrop = (beamId: string) => {
    setBeams((prev) =>
      prev.map((b) =>
        b.id === beamId
          ? {
              ...b,
              beamKind: 'drop',
              layerName: '00-XD-BEAM-DROP',
              widthM: 0.2,
              depthM: 0.5,
            }
          : b
      )
    );
    setThicknessWarningMsg(null);
  };

  const handleTriggerLongSpanHiddenBeamDemo = () => {
    // Sets B2 first span to 6.8m so required thickness exceeds 30 cm and demonstrates the Smart Drop-Beam Advisor
    setBeams((prev) =>
      prev.map((b) =>
        b.id === 'B2'
          ? {
              ...b,
              beamKind: 'hidden',
              layerName: '00-XD-BEAM-HID',
              widthM: 0.7,
              depthM: 0.3,
              spans: [6.8, 4.6],
            }
          : b
      )
    );
  };

  const handleAddColumnAt = (xM: number, yM: number) => {
    const nextNum = columns.length + 1;
    const newCol: StructuralColumnModel = {
      id: `C${nextNum}`,
      x: xM,
      y: yM,
      bM: 0.25,
      hM: 0.5,
      activeInStory: true,
    };
    setColumns((prev) => [...prev, newCol]);
  };

  const handleAddBeamBetweenColumns = (
    colStartId: string,
    colEndId: string,
    kind: 'hidden' | 'drop'
  ) => {
    const c1 = columns.find((c) => c.id === colStartId);
    const c2 = columns.find((c) => c.id === colEndId);
    if (!c1 || !c2) return;
    const dx = c2.x - c1.x;
    const dy = c2.y - c1.y;
    const spanLen = Number(Math.max(1.5, Math.hypot(dx, dy)).toFixed(2));
    const nextId = `B${beams.length + 1}`;
    const newBeam: StructuralBeamModel = {
      id: nextId,
      beamKind: kind,
      layerName: kind === 'hidden' ? '00-XD-BEAM-HID' : '00-XD-BEAM-DROP',
      widthM: kind === 'hidden' ? 0.3 : 0.2,
      depthM: kind === 'hidden' ? adoptedSlabThicknessCm / 100 : 0.5,
      cantilevers: { left: 0, right: 0 },
      spans: [spanLen],
      supports: [
        { supportIndex: 1, kind: 'column', targetId: c1.id, widthAlongBeamM: c1.bM },
        { supportIndex: 2, kind: 'column', targetId: c2.id, widthAlongBeamM: c2.bM },
      ],
      loads: [
        {
          id: `${nextId}_L1`,
          type: 'dist',
          x1: 0,
          x2: spanLen,
          val: 22.5,
          sourceLabel: 'Self-Weight + Tributary Slab Load',
          category: 'slab',
        },
      ],
      startCoord: { x: c1.x, y: c1.y },
      endCoord: { x: c2.x, y: c2.y },
    };
    setBeams((prev) => [...prev, newBeam]);
    setSelectedBeamId(nextId);
  };

  const handleToggleColumnContinuity = (colId: string) => {
    setColumns((prev) =>
      prev.map((c) => (c.id === colId ? { ...c, activeInStory: !c.activeInStory } : c))
    );
  };

  const handleToggleSlabRibDirection = (slabId: string) => {
    setSlabs((prev) =>
      prev.map((s) =>
        s.id === slabId ? { ...s, ribDirectionDeg: s.ribDirectionDeg === 90 ? 0 : 90 } : s
      )
    );
  };

  const handleExportDxf = () => {
    const dxfContent = exportStoryToDxfContent(columns, beams);
    const blob = new Blob([dxfContent], { type: 'application/dxf' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workspace.projectName}-${activeStoryId}.dxf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div dir="ltr" className="min-h-screen bg-slate-100 text-slate-900 flex flex-col font-sans">
      {/* =====================================================================
          1. CLASSIC TOP MENU BAR (NO RIBBON!)
         ===================================================================== */}
      <header className="bg-slate-950 text-slate-200 border-b border-slate-800 select-none">
        <div className="flex items-center justify-between px-4 py-1.5 border-b border-slate-900">
          <div className="flex items-center gap-3">
            <span className="px-2 py-0.5 bg-sky-600 text-white font-mono font-bold text-xs rounded">
              XD STUDIO
            </span>
            <h1 className="text-sm font-bold tracking-tight text-white">
              Xpert Structural Design Studio — <span className="text-sky-400 font-mono">v1.0.0</span>
            </h1>
            <span className="text-xs text-slate-400 font-mono hidden md:inline">
              | Project: Stractural-{workspace.projectName}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="text-slate-400">
              f&apos;c={config.fcMpa} MPa · Reinforcement Fy={config.fyMpa} MPa · q_all={config.soilBearingCapacityKnM2} kN/m²
            </span>
          </div>
        </div>

        {/* Classic Pull-Down Style Menu Strip */}
        <nav className="flex flex-wrap items-center gap-1 px-3 py-1 bg-slate-900 text-xs font-medium border-b border-slate-800">
          <button
            type="button"
            onClick={() => {
              setDraftConfig(config);
              setIsNewProjectModalOpen(true);
            }}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            File (New / Setup)
          </button>
          <button
            type="button"
            onClick={() => setStudioMode('CAD_MODELER')}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            Draw &amp; CAD Modeler
          </button>
          <button
            type="button"
            onClick={() => {
              setDraftConfig(config);
              setIsNewProjectModalOpen(true);
            }}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            Define Criteria
          </button>
          <button
            type="button"
            onClick={() => setStudioMode('BEAM_ANALYSIS')}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            Analyze (All Beams)
          </button>
          <button
            type="button"
            onClick={() => setStudioMode('RC_DESIGN')}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            Design (Beams / Columns / Footings)
          </button>
          <button
            type="button"
            onClick={handleExportDxf}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            Detailing (.DXF Export)
          </button>
          <button
            type="button"
            onClick={() => setStudioMode('CALC_REPORT')}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-slate-200"
          >
            Reports (Master Calculation Report)
          </button>
          <button
            type="button"
            onClick={() => setStudioMode('GITHUB_SYNC')}
            className="px-2.5 py-1 hover:bg-slate-800 rounded text-emerald-400 font-semibold"
          >
            GitHub &amp; VS Code Sync
          </button>
        </nav>

        {/* =====================================================================
            2. CLASSIC STANDARD TOOLBAR (Story Selector + Mode Switcher + 1-Click Analyze All)
           ===================================================================== */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-slate-800 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setDraftConfig(config);
                setIsNewProjectModalOpen(true);
              }}
              className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded transition"
              data-testid="open-new-project-modal-btn"
            >
              New / Edit Project...
            </button>

            <button
              type="button"
              onClick={handleExportDxf}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-100 font-semibold rounded transition"
            >
              Save &amp; Sync .DXF
            </button>

            <div className="flex items-center gap-1.5 ml-2">
              <span className="text-slate-300 font-semibold">Active Story:</span>
              <select
                value={activeStoryId}
                onChange={(e) => setActiveStoryId(e.target.value)}
                className="bg-slate-900 text-white border border-slate-700 rounded px-2.5 py-1 font-mono text-xs"
                data-testid="active-story-select"
              >
                {workspace.filesTree.stories.map((st) => (
                  <option key={st.storyId} value={st.storyId}>
                    {st.storyNameAr}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Workspace Mode Switcher + 1-Click Analyze All Beams */}
          <div className="flex flex-wrap items-center gap-1.5">
            {(
              [
                ['CAD_MODELER', '1. 2D CAD Modeler'],
                ['BEAM_ANALYSIS', '2. Beam Analysis'],
                ['RC_DESIGN', '3. R.C. Design & Columns P-M'],
                ['CALC_REPORT', '4. Calculation Report'],
                ['GITHUB_SYNC', '5. GitHub & VS Code'],
              ] as [StudioMode, string][]
            ).map(([mKey, mLabel]) => (
              <button
                key={mKey}
                type="button"
                onClick={() => setStudioMode(mKey)}
                className={`px-3 py-1.5 rounded font-semibold transition ${
                  studioMode === mKey
                    ? 'bg-white text-slate-950 shadow-sm'
                    : 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                }`}
              >
                {mLabel}
              </button>
            ))}

            <button
              type="button"
              onClick={() => setStudioMode('BEAM_ANALYSIS')}
              className="ml-2 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded transition"
              data-testid="analyze-all-beams-btn"
            >
              Analyze All Beams (F5)
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          3. AUTOMATIC BACKGROUND ACI 318 SLAB THICKNESS & SMART OPTIMIZATION BAR
         ===================================================================== */}
      <section className="bg-white border-b border-slate-200 px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Calculated Min. Thickness (ACI 318):
              </span>
              <span
                className="px-2.5 py-1 rounded bg-sky-50 border border-sky-200 font-mono text-xs font-bold text-sky-900 tabular-nums"
                data-testid="calculated-min-thickness-badge"
              >
                {activeStoryEntry.storyType === 'tie_beams'
                  ? '0.0 cm (Tie-Beams Level)'
                  : beams.length === 0 && slabs.length === 0
                  ? '-- (Awaiting CAD Data)'
                  : `${deflectionReport.recommendedUnifiedSlabAndHiddenCm.toFixed(1)} cm`}
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold text-slate-500">Governing Critical Case:</span>
              <span className="font-mono font-semibold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                {activeStoryEntry.storyType === 'tie_beams'
                  ? 'Tie-Beams Grade Level (Drop Beams Only)'
                  : deflectionReport.maxRequiredHiddenBeamThicknessCm >=
                    deflectionReport.maxRequiredSlabThicknessCm
                  ? `Hidden Beam ${deflectionReport.governingHiddenBeamElement}`
                  : `Slab Rib ${deflectionReport.governingSlabElement}`}
              </span>
            </div>
          </div>

          {activeStoryEntry.storyType !== 'tie_beams' && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleTriggerLongSpanHiddenBeamDemo}
                className="text-[11px] font-medium text-amber-700 hover:underline"
              >
                [Test Long-Span Hidden Beam &gt; 30cm]
              </button>

              <div className="flex items-center gap-2">
                <label className="text-xs font-bold text-slate-700">
                  Adopted Story Slab Thickness (cm):
                </label>
                <input
                  type="number"
                  min={14}
                  max={100}
                  step={1}
                  value={adoptedSlabThicknessCm}
                  onChange={(e) => handleApplyThickness(Number(e.target.value) || 30)}
                  className="w-20 px-2 py-1 border border-slate-300 rounded font-mono text-xs font-bold text-slate-900 tabular-nums"
                />
                <span className="text-xs font-mono text-slate-500">
                  (Block: {adoptedSlabThicknessCm >= 25 ? '20 cm' : '16 cm'})
                </span>
              </div>
            </div>
          )}
        </div>

        {/* User Override Warning Banner (if Adopted < Calculated) */}
        {thicknessWarningMsg && (
          <div className="mt-2 p-2.5 bg-rose-50 border border-rose-300 rounded flex flex-wrap items-center justify-between gap-3 text-xs text-rose-900">
            <span>
              <strong>ACI 318 Deflection Notice:</strong> {thicknessWarningMsg}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setThicknessWarningMsg(null)}
                className="px-2.5 py-1 bg-rose-700 text-white rounded font-semibold"
              >
                Continue with {adoptedSlabThicknessCm} cm
              </button>
              <button
                type="button"
                onClick={() =>
                  handleApplyThickness(Math.ceil(deflectionReport.recommendedUnifiedSlabAndHiddenCm))
                }
                className="px-2.5 py-1 bg-white border border-rose-400 text-rose-900 rounded font-semibold"
              >
                Adopt Calculated ({Math.ceil(deflectionReport.recommendedUnifiedSlabAndHiddenCm)} cm)
              </button>
            </div>
          </div>
        )}

        {/* Smart Drop-Beam Optimization Suggestion Banner (when Hidden Beam governs > 30 cm) */}
        {deflectionReport.smartOptimization && (
          <div
            className="mt-2 p-2.5 bg-amber-50 border border-amber-300 rounded flex flex-wrap items-center justify-between gap-3 text-xs text-amber-950"
            data-testid="smart-optimization-banner"
          >
            <div>
              <strong className="font-bold">Smart Engineering Advisor: </strong>
              {deflectionReport.smartOptimization.message}
            </div>
            <button
              type="button"
              onClick={() =>
                handleConvertCriticalBeamToDrop(deflectionReport.smartOptimization!.beamId)
              }
              className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white font-bold rounded shrink-0"
            >
              Convert {deflectionReport.smartOptimization.beamId} to Drop Beam (20×50 cm)
            </button>
          </div>
        )}
      </section>

      {/* =====================================================================
          4. MAIN STUDIO WORKSPACE (MODES 1 TO 5)
         ===================================================================== */}
      <main className="flex-1 p-4 max-w-[1600px] w-full mx-auto space-y-4">
        {/* MODE 1: 2D STRUCTURAL CAD MODELER */}
        {studioMode === 'CAD_MODELER' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-8">
              <CadFloorPlanCanvas
                columns={columns}
                beams={floorAnalysis.updatedBeams}
                slabs={slabs}
                selectedBeamId={selectedBeamId}
                onSelectBeam={(bid) => setSelectedBeamId(bid)}
                onToggleColumnContinuity={handleToggleColumnContinuity}
                onAddColumnAt={handleAddColumnAt}
                onAddBeamBetweenColumns={handleAddBeamBetweenColumns}
                onToggleSlabRibDirection={handleToggleSlabRibDirection}
                onExportDxf={handleExportDxf}
                storyType={activeStoryEntry.storyType}
                storyLabel={activeStoryEntry.storyNameAr}
              />
            </div>

            {/* Right Dock: Story Files & Live Element Inspector */}
            <div className="lg:col-span-4 space-y-4">
              <div className="bg-white border border-slate-200 rounded p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Synchronized Project Files (&lt;ProjectName&gt;- Prefix)
                  </h3>
                  <span className="text-[11px] font-mono text-emerald-700 font-semibold">
                    Zero Duplicates
                  </span>
                </div>
                <div className="text-xs font-mono space-y-1 text-slate-700 bg-slate-50 p-2.5 rounded border border-slate-200 max-h-44 overflow-y-auto">
                  <div className="font-bold text-slate-900">{workspace.folderName}/</div>
                  <div className="pl-3 text-sky-800">
                    ├─ {workspace.projectName}-00_Project_Master.json
                  </div>
                  <div className="pl-3 text-slate-600">
                    ├─ {workspace.projectName}-Columns_Load_Takedown.json
                  </div>
                  <div className="pl-3 text-slate-600">
                    ├─ {workspace.projectName}-Foundations_Design.json
                  </div>
                  <div className="pl-3 text-slate-600">
                    ├─ {workspace.projectName}-BOQ_Quantities.json
                  </div>
                  <div className="pl-3 font-semibold text-slate-800">├─ CAD_Drawings/</div>
                  {workspace.filesTree.stories.map((st) => (
                    <div key={st.storyId} className="pl-6 text-emerald-700">
                      ├─ {workspace.projectName}-{st.storyId}.dxf
                    </div>
                  ))}
                  <div className="pl-6 text-amber-700">
                    └─ {workspace.projectName}-Foundations_And_Axes.dxf
                  </div>
                </div>
              </div>

              {/* Quick Selected Beam Preview Card */}
              {activeBeam && activeBeamResult && (
                <div className="bg-white border border-slate-200 rounded p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Selected Beam Quick Summary — {activeBeam.id}
                    </h3>
                    <button
                      type="button"
                      onClick={() => setStudioMode('BEAM_ANALYSIS')}
                      className="text-xs font-bold text-sky-700 hover:underline"
                    >
                      Open Diagrams →
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs font-mono tabular-nums">
                    <div className="p-2 bg-slate-50 rounded border border-slate-200">
                      <div className="text-[10px] text-slate-500">Max +Mu (Span)</div>
                      <div className="font-bold text-slate-900">
                        +{Math.max(0, ...activeBeamResult.maxPositiveMoments.map((m) => m.maxMomentKnM)).toFixed(1)} kN·m
                      </div>
                    </div>
                    <div className="p-2 bg-rose-50 rounded border border-rose-200">
                      <div className="text-[10px] text-rose-700">Face -Mu</div>
                      <div className="font-bold text-rose-900">
                        {activeBeamResult.maxFaceNegMomentKnM.toFixed(1)} kN·m
                      </div>
                    </div>
                    <div className="p-2 bg-blue-50 rounded border border-blue-200">
                      <div className="text-[10px] text-blue-700">Face Vu</div>
                      <div className="font-bold text-blue-900">
                        {activeBeamResult.maxFaceShearKn.toFixed(1)} kN
                      </div>
                    </div>
                  </div>
                  {activeBeamResult.aciDesign && (
                    <div className="text-xs font-mono bg-emerald-50 border border-emerald-200 rounded p-2.5 text-emerald-950 space-y-1">
                      <div>
                        <strong>Bottom Bars:</strong> {activeBeamResult.aciDesign.bottomBarsLabel}
                      </div>
                      <div>
                        <strong>Top Support Bars:</strong> {activeBeamResult.aciDesign.topBarsLabel}
                      </div>
                      <div>
                        <strong>Shear Stirrups:</strong> {activeBeamResult.aciDesign.stirrupsLabel}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* MODE 2: 1-CLICK ALL BEAMS ANALYSIS & INTERACTIVE BEAM INSPECTOR */}
        {studioMode === 'BEAM_ANALYSIS' && (
          <div className="space-y-4">
            {/* Master All-Beams Summary Table (View All Beams Without Stepping One by One) */}
            <div className="bg-white border border-slate-200 rounded overflow-hidden">
              <div className="px-4 py-3 bg-slate-900 text-white flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold">
                    All Story Beams — Topological Analysis Summary ({activeStoryEntry.storyNameAr})
                  </h3>
                  <p className="text-xs text-slate-300">
                    Execution Order: {floorAnalysis.orderedBeamIds.join(' → ')} (Click any beam row to inspect its SFD &amp; BMD diagrams below)
                  </p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono tabular-nums">
                  <thead className="bg-slate-100 border-b border-slate-200 text-slate-700">
                    <tr>
                      <th className="px-3 py-2">Beam ID</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Section (cm)</th>
                      <th className="px-3 py-2">Spans (m)</th>
                      <th className="px-3 py-2">Supports</th>
                      <th className="px-3 py-2 text-emerald-700">Max +Mu (kN·m)</th>
                      <th className="px-3 py-2 text-rose-700">Face -Mu (kN·m)</th>
                      <th className="px-3 py-2 text-blue-700">Face Vu (kN)</th>
                      <th className="px-3 py-2">ACI Bottom / Top Bars</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {floorAnalysis.updatedBeams.map((bm) => {
                      const res = floorAnalysis.beamResults[bm.id];
                      const maxPos = res
                        ? Math.max(0, ...res.maxPositiveMoments.map((m) => m.maxMomentKnM))
                        : 0;
                      const isSel = bm.id === selectedBeamId;
                      return (
                        <tr
                          key={bm.id}
                          onClick={() => setSelectedBeamId(bm.id)}
                          className={`cursor-pointer transition ${
                            isSel ? 'bg-sky-50 font-semibold' : 'hover:bg-slate-50'
                          }`}
                        >
                          <td className="px-3 py-2 font-bold text-slate-900">{bm.id}</td>
                          <td className="px-3 py-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                bm.beamKind === 'hidden'
                                  ? 'bg-amber-100 text-amber-900'
                                  : 'bg-emerald-100 text-emerald-900'
                              }`}
                            >
                              {bm.beamKind.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            {Math.round(bm.widthM * 100)}×{Math.round(bm.depthM * 100)}
                          </td>
                          <td className="px-3 py-2">{bm.spans.map((s) => s.toFixed(2)).join(' + ')}</td>
                          <td className="px-3 py-2">
                            {bm.supports
                              .map((s) => `${s.targetId}(${s.kind === 'column' ? '△' : '△○○'})`)
                              .join(' - ')}
                          </td>
                          <td className="px-3 py-2 font-bold text-emerald-700">+{maxPos.toFixed(2)}</td>
                          <td className="px-3 py-2 font-bold text-rose-700">
                            {res ? res.maxFaceNegMomentKnM.toFixed(2) : '0.00'}
                          </td>
                          <td className="px-3 py-2 font-bold text-blue-700">
                            {res ? res.maxFaceShearKn.toFixed(2) : '0.00'}
                          </td>
                          <td className="px-3 py-2 text-slate-800">
                            {res?.aciDesign
                              ? `Bot: ${res.aciDesign.bottomBarsLabel} | Top: ${res.aciDesign.topBarsLabel}`
                              : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Interactive Beam Diagrams Canvas for Selected Beam */}
            {activeBeam && activeBeamResult && (
              <BeamDiagramsCanvas beam={activeBeam} result={activeBeamResult} />
            )}
          </div>
        )}

        {/* MODE 3: R.C. DESIGN, COLUMN 4-WAY FRAMING & P-M INTERACTION DIAGRAMS */}
        {studioMode === 'RC_DESIGN' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Columns Load Takedown & 4-Way Framing Connectivity Table */}
            <div className="lg:col-span-7 bg-white border border-slate-200 rounded overflow-hidden">
              <div className="px-4 py-3 bg-slate-900 text-white">
                <h3 className="text-sm font-bold">
                  Columns Load Takedown, End Moments &amp; 4-Way Framing Connectivity
                </h3>
                <p className="text-xs text-slate-300">
                  Stores cumulative axial load (ΣPu), transferred moments (Mux, Muy), and connected beams (North, South, East, West). Click any column to view its P-M Diagram.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono tabular-nums">
                  <thead className="bg-slate-100 border-b border-slate-200 text-slate-700">
                    <tr>
                      <th className="px-3 py-2">Col ID</th>
                      <th className="px-3 py-2">Section (mm)</th>
                      <th className="px-3 py-2">Story Pu (kN)</th>
                      <th className="px-3 py-2">Cumulative ΣPu (kN)</th>
                      <th className="px-3 py-2">Moments (Mux, Muy)</th>
                      <th className="px-3 py-2">4-Way Framing Beams (N / S / E / W)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {floorAnalysis.columnReactionsSummary.map((col) => {
                      const cumPu = Number(
                        (col.totalFloorLoadKn * Math.max(1, totalStoriesMultiplier - 1)).toFixed(1)
                      );
                      const f4 = col.framing4Way;
                      const f4Text =
                        [
                          f4.North ? `N:${f4.North}` : null,
                          f4.South ? `S:${f4.South}` : null,
                          f4.East ? `E:${f4.East}` : null,
                          f4.West ? `W:${f4.West}` : null,
                        ]
                          .filter(Boolean)
                          .join(' | ') || 'Unframed';

                      return (
                        <tr
                          key={col.columnId}
                          onClick={() => setSelectedColumnId(col.columnId)}
                          className={`cursor-pointer ${
                            col.columnId === selectedColumnId
                              ? 'bg-sky-50 font-semibold'
                              : 'hover:bg-slate-50'
                          }`}
                        >
                          <td className="px-3 py-2 font-bold text-slate-900">{col.columnId}</td>
                          <td className="px-3 py-2">
                            {Math.round(col.bM * 1000)}×{Math.round(col.hM * 1000)}
                          </td>
                          <td className="px-3 py-2">{col.totalFloorLoadKn.toFixed(1)}</td>
                          <td className="px-3 py-2 font-bold text-emerald-700">{cumPu}</td>
                          <td className="px-3 py-2">
                            ({col.muxKnM.toFixed(1)}, {col.muyKnM.toFixed(1)})
                          </td>
                          <td className="px-3 py-2 text-[11px]">{f4Text}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Selected Column P-M Interaction Diagram & SPColumn (.cti) Export */}
            <div className="lg:col-span-5 space-y-4">
              {activeColSummary && activeColDesign && (
                <div className="bg-white border border-slate-200 rounded p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">
                        ACI 318 P-M Interaction Diagram — Column {activeColSummary.columnId}
                      </h4>
                      <p className="text-xs text-slate-500">
                        Section {Math.round(activeColSummary.bM * 1000)}×
                        {Math.round(activeColSummary.hM * 1000)} mm · Reinforcement:{' '}
                        <strong>{activeColDesign.chosenBarsLabel}</strong> (ρ ={' '}
                        {activeColDesign.usedSteelRatioPct}%)
                      </p>
                    </div>
                    <span className="px-2.5 py-1 bg-emerald-100 text-emerald-900 font-mono text-xs font-bold rounded">
                      {activeColDesign.status}
                    </span>
                  </div>

                  {/* SVG P-M Interaction Curve */}
                  <svg
                    direction="ltr"
                    viewBox="0 0 420 260"
                    className="w-full h-auto bg-slate-50 border border-slate-200 rounded"
                  >
                    <line x1="55" y1="20" x2="55" y2="225" stroke="#334155" strokeWidth="1.5" />
                    <line x1="55" y1="225" x2="395" y2="225" stroke="#334155" strokeWidth="1.5" />
                    <text x="18" y="30" fontSize="10" fontWeight="bold" fill="#334155">
                      φPn (kN)
                    </text>
                    <text x="330" y="245" fontSize="10" fontWeight="bold" fill="#334155">
                      φMn (kN·m)
                    </text>

                    {(() => {
                      const maxP = Math.max(100, activeColDesign.axialCapacityPhiPnKn * 1.1);
                      const maxM = Math.max(50, activeColDesign.balancedMomentPhiMbKnM * 1.25);
                      const pToY = (p: number) => 225 - (p / maxP) * 190;
                      const mToX = (m: number) => 55 + (m / maxM) * 310;

                      const pts = activeColDesign.pmCurvePoints
                        .map((pt) => `${mToX(pt.mKnM).toFixed(1)},${pToY(pt.pKn).toFixed(1)}`)
                        .join(' ');
                      const polyPts = `55,225 55,${pToY(activeColDesign.axialCapacityPhiPnKn).toFixed(1)} ${pts}`;

                      const demandX = mToX(
                        Math.hypot(activeColSummary.muxKnM, activeColSummary.muyKnM)
                      );
                      const demandY = pToY(activeColDesign.cumulativePuKn);

                      return (
                        <>
                          <polygon
                            points={polyPts}
                            fill="#0284c7"
                            fillOpacity="0.15"
                            stroke="#0284c7"
                            strokeWidth="2.2"
                          />
                          <circle cx={demandX} cy={demandY} r="5" fill="#dc2626" />
                          <text
                            x={demandX + 8}
                            y={demandY - 6}
                            fontSize="10"
                            fontWeight="bold"
                            fill="#dc2626"
                          >
                            Demand (Pu={activeColDesign.cumulativePuKn}kN, Mu=
                            {Math.hypot(activeColSummary.muxKnM, activeColSummary.muyKnM).toFixed(1)}
                            kN·m)
                          </text>
                        </>
                      );
                    })()}
                  </svg>

                  <details className="text-xs">
                    <summary className="cursor-pointer font-semibold text-sky-700">
                      View / Copy SPColumn (.cti) Export File for {activeColSummary.columnId}
                    </summary>
                    <pre className="mt-2 p-2.5 bg-slate-900 text-slate-100 rounded font-mono text-[11px] overflow-x-auto">
                      {activeColDesign.spColumnCtiContent}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </div>
        )}

        {/* MODE 4: MASTER PRINTABLE CALCULATION REPORT */}
        {studioMode === 'CALC_REPORT' && (
          <div className="bg-white border border-slate-300 rounded p-6 space-y-6 max-w-5xl mx-auto">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-slate-900 pb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-950">
                  STRUCTURAL CALCULATION REPORT — {workspace.projectName.toUpperCase()}
                </h2>
                <p className="text-xs text-slate-600 font-mono">
                  Generated by Xpert Structural Design Studio (v1.0.0) · Code: ACI 318-19 · Lead Engineer: Eng. Yousef Mohammed Keshlaf
                </p>
              </div>
              <button
                type="button"
                onClick={() => window.print()}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded"
              >
                Print / Save Report as PDF
              </button>
            </div>

            {/* Section 1: Design Criteria & Slab Thickness */}
            <div className="space-y-2">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 bg-slate-100 px-3 py-1.5 rounded">
                1. Project Design Criteria &amp; ACI 318 Slab Thickness Verification
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono p-2">
                <div>Concrete f&apos;c: {config.fcMpa} MPa</div>
                <div>Reinforcement Fy: {config.fyMpa} MPa</div>
                <div>Soil Bearing q_all: {config.soilBearingCapacityKnM2} kN/m²</div>
                <div>Foundation Depth: {config.foundationDepthM.toFixed(2)} m</div>
                <div>Ground Story Height: {config.storyHeightM.toFixed(2)} m</div>
                <div>Calculated Min. Slab: {deflectionReport.recommendedUnifiedSlabAndHiddenCm.toFixed(1)} cm</div>
                <div>Adopted Slab Thickness: {adoptedSlabThicknessCm.toFixed(1)} cm</div>
                <div>Hollow-Block Height: {adoptedSlabThicknessCm >= 25 ? '20 cm' : '16 cm'}</div>
              </div>
            </div>

            {/* Section 2: All Story Beams Analysis & ACI 318 Reinforcement */}
            <div className="space-y-2">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 bg-slate-100 px-3 py-1.5 rounded">
                2. Story Beams Analysis Forces &amp; ACI 318 Flexural / Shear Reinforcement
              </h3>
              <table className="w-full text-left text-xs font-mono border border-slate-200">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="p-2">Beam</th>
                    <th className="p-2">Type &amp; Section</th>
                    <th className="p-2">Spans (m)</th>
                    <th className="p-2">Max +Mu (kN·m)</th>
                    <th className="p-2">Face -Mu (kN·m)</th>
                    <th className="p-2">Face Vu (kN)</th>
                    <th className="p-2">Bottom Steel</th>
                    <th className="p-2">Top Steel</th>
                    <th className="p-2">Stirrups</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {floorAnalysis.updatedBeams.map((bm) => {
                    const res = floorAnalysis.beamResults[bm.id];
                    const posM = res
                      ? Math.max(0, ...res.maxPositiveMoments.map((m) => m.maxMomentKnM))
                      : 0;
                    return (
                      <tr key={bm.id}>
                        <td className="p-2 font-bold">{bm.id}</td>
                        <td className="p-2">
                          {bm.beamKind.toUpperCase()} ({Math.round(bm.widthM * 100)}×
                          {Math.round(bm.depthM * 100)} cm)
                        </td>
                        <td className="p-2">{bm.spans.join(', ')}</td>
                        <td className="p-2">+{posM.toFixed(2)}</td>
                        <td className="p-2">{res?.maxFaceNegMomentKnM.toFixed(2)}</td>
                        <td className="p-2">{res?.maxFaceShearKn.toFixed(2)}</td>
                        <td className="p-2">{res?.aciDesign?.bottomBarsLabel}</td>
                        <td className="p-2">{res?.aciDesign?.topBarsLabel}</td>
                        <td className="p-2">{res?.aciDesign?.stirrupsLabel}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Section 3: Columns Load Takedown & Footing Design Summary */}
            <div className="space-y-2">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 bg-slate-100 px-3 py-1.5 rounded">
                3. Columns Cumulative Load Takedown, 4-Way Framing &amp; Isolated Footing Sizing
              </h3>
              <table className="w-full text-left text-xs font-mono border border-slate-200">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="p-2">Col ID</th>
                    <th className="p-2">Col Section</th>
                    <th className="p-2">Cumulative ΣPu (kN)</th>
                    <th className="p-2">Framing Beams</th>
                    <th className="p-2">Footing B×L×H (m)</th>
                    <th className="p-2">Reinforcement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {floorAnalysis.columnReactionsSummary.map((col) => {
                    const cumPu = Number(
                      (col.totalFloorLoadKn * Math.max(1, totalStoriesMultiplier - 1)).toFixed(1)
                    );
                    const pService = cumPu / 1.35;
                    const reqArea = Math.max(1.44, pService / config.soilBearingCapacityKnM2);
                    const sideB = (Math.ceil(Math.sqrt(reqArea) * 10) / 10).toFixed(2);
                    return (
                      <tr key={col.columnId}>
                        <td className="p-2 font-bold">{col.columnId}</td>
                        <td className="p-2">
                          {Math.round(col.bM * 1000)}×{Math.round(col.hM * 1000)} mm
                        </td>
                        <td className="p-2 font-bold">{cumPu} kN</td>
                        <td className="p-2">
                          {col.contributingBeams.map((cb) => cb.beamId).join(', ') || '—'}
                        </td>
                        <td className="p-2">
                          {sideB} × {sideB} × 0.50 m
                        </td>
                        <td className="p-2">7 Φ 16 / m (Both Ways)</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* MODE 5: GITHUB & VS CODE SYNC */}
        {studioMode === 'GITHUB_SYNC' && <VsCodeExportTab projectName={workspace.projectName} />}
      </main>

      {/* =====================================================================
          5. MODAL NEW PROJECT SETUP DIALOG (CLOSES ON OK -> OPENS STUDIO)
         ===================================================================== */}
      {isNewProjectModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/70 flex items-center justify-center p-4"
          data-testid="new-project-modal"
        >
          <div className="bg-white rounded-lg border border-slate-300 shadow-2xl max-w-2xl w-full overflow-hidden">
            <div className="bg-slate-900 text-white px-5 py-3.5 flex items-center justify-between">
              <h2 className="text-sm font-bold">
                New Structural Project Setup — Xpert Structural Design Studio
              </h2>
              <button
                type="button"
                onClick={() => setIsNewProjectModalOpen(false)}
                className="text-slate-400 hover:text-white text-xs font-mono"
              >
                [ESC / Close]
              </button>
            </div>

            <form onSubmit={handleCreateOrUpdateProject} className="p-5 space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Project Name:</label>
                  <input
                    type="text"
                    required
                    value={draftConfig.projectName}
                    onChange={(e) =>
                      setDraftConfig((p) => ({ ...p, projectName: e.target.value }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Root Projects Directory:
                  </label>
                  <input
                    type="text"
                    value={draftConfig.rootDirectory}
                    onChange={(e) =>
                      setDraftConfig((p) => ({ ...p, rootDirectory: e.target.value }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>
              </div>

              <div className="border-t border-slate-200 pt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Ground Floor Height (Mandatory, m):
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="2.5"
                    max="12.0"
                    value={draftConfig.storyHeightM}
                    onChange={(e) =>
                      setDraftConfig((p) => ({
                        ...p,
                        storyHeightM: Number(e.target.value) || 3.2,
                      }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Floors Above Ground (Count):
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="50"
                    value={draftConfig.upperStoriesCount}
                    onChange={(e) =>
                      setDraftConfig((p) => ({
                        ...p,
                        upperStoriesCount: Math.max(0, Number(e.target.value) || 0),
                      }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Foundation / Excavation Depth (m):
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.5"
                    max="25.0"
                    value={draftConfig.foundationDepthM}
                    onChange={(e) =>
                      setDraftConfig((p) => ({
                        ...p,
                        foundationDepthM: Number(e.target.value) || 1.5,
                      }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>
              </div>

              <div className="border-t border-slate-200 pt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Concrete f&apos;c (MPa) [15–100]:
                  </label>
                  <input
                    type="number"
                    min="15"
                    max="100"
                    value={draftConfig.fcMpa}
                    onChange={(e) =>
                      setDraftConfig((p) => ({ ...p, fcMpa: Number(e.target.value) || 20 }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Reinforcement Fy (MPa) [200–1000]:
                  </label>
                  <input
                    type="number"
                    min="200"
                    max="1000"
                    value={draftConfig.fyMpa}
                    onChange={(e) =>
                      setDraftConfig((p) => ({ ...p, fyMpa: Number(e.target.value) || 350 }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Soil Bearing q_all (kN/m²) [50–2000]:
                  </label>
                  <input
                    type="number"
                    min="50"
                    max="2000"
                    value={draftConfig.soilBearingCapacityKnM2}
                    onChange={(e) =>
                      setDraftConfig((p) => ({
                        ...p,
                        soilBearingCapacityKnM2: Number(e.target.value) || 150,
                      }))
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono"
                  />
                </div>
              </div>

              <div className="border-t border-slate-200 pt-4 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsNewProjectModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded"
                >
                  OK — Create Project &amp; Open Studio
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
