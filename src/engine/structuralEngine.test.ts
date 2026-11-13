import test from 'node:test';
import assert from 'node:assert/strict';
import {
  validateProjectName,
  computeHollowBlockParameters,
  generateProjectWorkspace,
  verifyAutoCadPluginVisibility,
  computeClearSpanAndACIDeflection,
  runSequentialFloorAnalysis,
  designColumnAciAndExportSpColumn,
  exportStoryToDxfContent,
  type StructuralBeamModel,
  type StructuralColumnModel,
  type SlabPanelModel,
} from './structuralEngine';

test('validateProjectName accepts alphanumeric names and rejects special symbols', () => {
  const validEn = validateProjectName('Alittihad Tower 1');
  assert.equal(validEn.valid, true);
  assert.equal(validEn.folderName, 'Stractural-Alittihad_Tower_1');

  const invalidSym = validateProjectName('Tower@#2026!');
  assert.equal(invalidSym.valid, false);
});

test('computeHollowBlockParameters selects 20cm block for slab >= 25cm and 16cm block for <= 24cm', () => {
  const slab30 = computeHollowBlockParameters(30);
  assert.equal(slab30.blockHeightCm, 20);
  assert.equal(slab30.topFlangeCm, 10);
  assert.equal(slab30.ribSpacingCm, 55);

  const slab24 = computeHollowBlockParameters(24);
  assert.equal(slab24.blockHeightCm, 16);
  assert.equal(slab24.topFlangeCm, 8);
});

test('generateProjectWorkspace prefixes all files with <ProjectName>- and avoids duplicate Roof when upperStoriesCount=0', () => {
  const wsSingle = generateProjectWorkspace({
    projectName: 'VillaTest',
    rootDirectory: 'D:\\EngineeringProjects',
    upperStoriesCount: 0,
    hasBasement: false,
    hasTypicalFloor: false,
    typicalFloorCount: 0,
    slabThicknessCm: 30,
    ribWidthCm: 15,
    hiddenBeamMinWidthCm: 30,
    dropBeamWidthCm: 20,
    dropBeamMinDepthCm: 40,
    wallWidthCm: 20,
    storyHeightM: 3.2,
    fcMpa: 20,
    fyMpa: 350,
    finishLoadKnM2: 2.0,
    liveLoadKnM2: 2.0,
    soilBearingCapacityKnM2: 150,
    foundationDepthM: 1.5,
  });

  assert.equal(wsSingle.folderName, 'Stractural-VillaTest');
  assert.equal(wsSingle.mandatoryStartStoryId, '02_Ground_Floor');
  assert.ok(wsSingle.filesTree.masterFile.endsWith('VillaTest-00_Project_Master.json'));
  assert.equal(wsSingle.filesTree.stories.length, 2); // Only 00_TieBeams and 02_Ground_Floor!
  assert.ok(wsSingle.filesTree.stories[1].cadFilePath.endsWith('VillaTest-02_Ground_Floor.dxf'));
});

test('verifyAutoCadPluginVisibility hides tools on external files and Foundations CAD file', () => {
  const extCheck = verifyAutoCadPluginVisibility({
    fileName: 'Drawing1.dwg',
    isInsideStracturalProjectFolder: false,
    hasMasterJsonSibling: false,
    hasValidXpertSignature: false,
    drawingRole: 'EXTERNAL_UNMANAGED',
  });
  assert.equal(extCheck.isRibbonVisible, false);

  const foundCheck = verifyAutoCadPluginVisibility({
    fileName: 'Foundations_And_Axes.dxf',
    isInsideStracturalProjectFolder: true,
    hasMasterJsonSibling: true,
    hasValidXpertSignature: true,
    drawingRole: 'FOUNDATION_PLOT_ONLY',
  });
  assert.equal(foundCheck.isRibbonVisible, false);
});

test('computeClearSpanAndACIDeflection calculates clear span Ln and triggers Smart Drop-Beam Optimization when hidden beam > 30cm', () => {
  const beams: StructuralBeamModel[] = [
    {
      id: 'B1',
      beamKind: 'hidden',
      layerName: '00-XD-BEAM-HID',
      widthM: 0.8,
      depthM: 0.3,
      cantilevers: { left: 0, right: 0 },
      spans: [6.8, 5.0],
      supports: [
        { supportIndex: 1, kind: 'column', targetId: 'C1', widthAlongBeamM: 0.4 },
        { supportIndex: 2, kind: 'column', targetId: 'C2', widthAlongBeamM: 0.4 },
        { supportIndex: 3, kind: 'column', targetId: 'C3', widthAlongBeamM: 0.4 },
      ],
      loads: [],
      startCoord: { x: 0, y: 0 },
      endCoord: { x: 11.8, y: 0 },
    },
  ];

  const slabs: SlabPanelModel[] = [
    {
      id: 'S1',
      ribDirectionDeg: 90,
      axisSpanCenterM: 4.5,
      leftSupportBeamId: 'B1',
      rightSupportBeamId: 'B2',
      leftSupportWidthM: 0.8,
      rightSupportWidthM: 0.3,
      isCantileverSlab: false,
      connectedToCantilever: false,
      areaM2: 22.5,
    },
  ];

  const defReport = computeClearSpanAndACIDeflection(beams, slabs, 350);
  const b1Span1 = defReport.checks.find((c) => c.elementId === 'B1' && c.spanLabel === 'Span L1');
  assert.ok(b1Span1);
  assert.equal(b1Span1.clearLengthLnM, 6.4);
  assert.equal(b1Span1.continuityCase, 'one_end_continuous');
  assert.ok(defReport.recommendedUnifiedSlabAndHiddenCm > 30);
  assert.ok(defReport.smartOptimization);
  assert.equal(defReport.smartOptimization.beamId, 'B1');
});

test('runSequentialFloorAnalysis solves secondary beams first, computes 4-way column framing, and exports DXF & SPColumn', () => {
  const columns: StructuralColumnModel[] = [
    { id: 'C1', x: 0, y: 0, bM: 0.3, hM: 0.5, activeInStory: true },
    { id: 'C2', x: 6, y: 0, bM: 0.3, hM: 0.5, activeInStory: true },
    { id: 'C3', x: 3, y: 4, bM: 0.3, hM: 0.5, activeInStory: true },
  ];

  const beams: StructuralBeamModel[] = [
    {
      id: 'B1',
      beamKind: 'drop',
      layerName: '00-XD-BEAM-DROP',
      widthM: 0.2,
      depthM: 0.5,
      cantilevers: { left: 0, right: 0 },
      spans: [6.0],
      supports: [
        { supportIndex: 1, kind: 'column', targetId: 'C1', widthAlongBeamM: 0.3 },
        { supportIndex: 2, kind: 'column', targetId: 'C2', widthAlongBeamM: 0.3 },
      ],
      loads: [{ id: 'L_B1', type: 'dist', x1: 0, x2: 6.0, val: 10.0, category: 'self_weight' }],
      startCoord: { x: 0, y: 0 },
      endCoord: { x: 6, y: 0 },
    },
    {
      id: 'B2',
      beamKind: 'hidden',
      layerName: '00-XD-BEAM-HID',
      widthM: 0.4,
      depthM: 0.3,
      cantilevers: { left: 0, right: 0 },
      spans: [4.0],
      supports: [
        { supportIndex: 1, kind: 'column', targetId: 'C3', widthAlongBeamM: 0.3 },
        {
          supportIndex: 2,
          kind: 'beam',
          targetId: 'B1',
          widthAlongBeamM: 0.2,
          positionOnSupportingBeamM: 3.0,
        },
      ],
      loads: [{ id: 'L_B2', type: 'dist', x1: 0, x2: 4.0, val: 20.0, category: 'slab' }],
      startCoord: { x: 3, y: 4 },
      endCoord: { x: 3, y: 0 },
    },
  ];

  const seq = runSequentialFloorAnalysis(beams, columns, 'ground', 3.0, 20, 350);
  assert.deepEqual(seq.orderedBeamIds, ['B2', 'B1']);
  assert.equal(seq.transferredReactionsLog.length, 1);
  assert.equal(seq.transferredReactionsLog[0].reactionKn, 40);

  const b1Res = seq.beamResults['B1'];
  assert.ok(b1Res.solved);
  assert.equal(b1Res.reactions[1], 50);
  assert.equal(b1Res.reactions[2], 50);
  assert.ok(b1Res.supportCriticalTable.length === 2);

  const c1Rec = seq.columnReactionsSummary.find((c) => c.columnId === 'C1');
  assert.ok(c1Rec);
  assert.ok(c1Rec.framing4Way.East);

  const spCol = designColumnAciAndExportSpColumn('C1', 0.3, 0.5, 850, 20, 15, 25, 400);
  assert.equal(spCol.status, 'SAFE');
  assert.equal(spCol.pmCurvePoints.length, 4);

  const dxfStr = exportStoryToDxfContent(columns, beams);
  assert.ok(dxfStr.includes('00-XD-TAG-COL'));
  assert.ok(dxfStr.includes('00-XD-TAG-BEAM'));
});
