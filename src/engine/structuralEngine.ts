// =============================================================================
// Xpert Structural Design Studio — Core CAD, Topology, Analysis & ACI 318 Engine
// Version: v1.0.0-studio-foundation
// Lead Structural Engineer: Eng. Yousef Mohammed Keshlaf
// =============================================================================

export type SupportKind = 'column' | 'beam';
export type BeamKind = 'hidden' | 'drop';
export type SpanContinuityCase =
  | 'simply_supported'
  | 'one_end_continuous'
  | 'both_ends_continuous'
  | 'cantilever';

export type StoryType = 'tie_beams' | 'basement' | 'ground' | 'typical' | 'standard' | 'roof';

export interface ProjectMasterConfig {
  projectName: string;
  rootDirectory: string;
  upperStoriesCount: number;
  hasBasement: boolean;
  basementHeightM?: number;
  hasTypicalFloor: boolean;
  typicalFloorCount: number;
  includePenthouse?: boolean;
  slabThicknessCm: number;
  ribWidthCm: number;
  hiddenBeamMinWidthCm: number;
  dropBeamWidthCm: number;
  dropBeamMinDepthCm: number;
  wallWidthCm: number;
  storyHeightM: number;
  upperStoryHeightM?: number;
  fcMpa: number;
  fyMpa: number;
  finishLoadKnM2: number;
  liveLoadKnM2: number;
  soilBearingCapacityKnM2: number;
  foundationDepthM: number;
}

export interface SupportNodeInfo {
  supportIndex: number; // 1-based index (1 .. NS+1)
  kind: SupportKind;    // 'column' -> Hinge (△), 'beam' -> Roller (△○○)
  targetId: string;     // e.g. 'C1', 'C2' or 'B2'
  widthAlongBeamM: number;
  positionOnSupportingBeamM?: number;
}

export interface BeamLoadItem {
  id: string;
  type: 'dist' | 'point';
  x?: number;
  x1?: number;
  x2?: number;
  val: number;
  sourceLabel?: string;
  category?: 'slab' | 'wall' | 'self_weight' | 'transferred_reaction' | 'manual';
}

export interface StructuralBeamModel {
  id: string; // 'B1', 'B2', ...
  beamKind: BeamKind; // 'hidden' (00-XD-BEAM-HID) or 'drop' (00-XD-BEAM-DROP)
  layerName: string;
  widthM: number;
  depthM: number;
  cantilevers: {
    left: number;
    right: number;
  };
  spans: number[];
  supports: SupportNodeInfo[];
  loads: BeamLoadItem[];
  startCoord: { x: number; y: number };
  endCoord: { x: number; y: number };
}

export interface StructuralColumnModel {
  id: string; // 'C1', 'C2', ...
  x: number;
  y: number;
  bM: number;
  hM: number;
  activeInStory: boolean;
  terminatedAtStoryId?: string | null;
}

export interface SlabPanelModel {
  id: string;
  ribDirectionDeg: number; // 0 = Horizontal (X), 90 = Vertical (Y)
  axisSpanCenterM: number;
  leftSupportBeamId: string;
  rightSupportBeamId: string;
  leftSupportWidthM: number;
  rightSupportWidthM: number;
  isCantileverSlab: boolean;
  connectedToCantilever: boolean;
  areaM2: number;
}

export interface SupportCriticalForceRow {
  supportIndex: number;
  targetId: string;
  kind: SupportKind;
  xM: number;
  reactionRuKn: number;
  centerlineNegMuKnM: number;
  faceNegMuKnM: number;
  centerlineVuKn: number;
  faceVuKn: number;
}

export interface BeamAciDesignResult {
  beamId: string;
  bMm: number;
  hMm: number;
  dMm: number;
  bottomAstMm2: number;
  bottomBarsLabel: string;
  topAstMm2: number;
  topBarsLabel: string;
  phiVcKn: number;
  stirrupsLabel: string;
  status: 'SAFE' | 'INCREASE_DEPTH';
}

export interface SlopeDeflectionResult {
  solved: boolean;
  error?: string;
  reactions: Record<number, number>;
  supportMoments: number[];
  supportCriticalTable: SupportCriticalForceRow[];
  maxPositiveMoments: { spanIndex: number; maxMomentKnM: number; xLocalM: number; xGlobalM: number }[];
  maxAbsShearKn: number;
  maxAbsMomentKnM: number;
  maxFaceShearKn: number;
  maxFaceNegMomentKnM: number;
  xFull: number[];
  vFull: number[];
  mFull: number[];
  academicReport: string;
  aciDesign?: BeamAciDesignResult;
}

export interface DeflectionSpanCheck {
  elementId: string;
  elementCategory: 'rib' | 'hidden_beam' | 'drop_beam';
  spanLabel: string;
  continuityCase: SpanContinuityCase;
  centerLengthM: number;
  clearLengthLnM: number;
  aciDivisor: number;
  fyModifier: number;
  requiredMinThicknessCm: number;
}

export interface SmartDropBeamSuggestion {
  beamId: string;
  governingLnM: number;
  governingReqCm: number;
  restOfFloorReqCm: number;
  message: string;
}

export interface DeflectionSummaryReport {
  fyModifier: number;
  checks: DeflectionSpanCheck[];
  maxRequiredSlabThicknessCm: number;
  governingSlabElement: string;
  maxRequiredHiddenBeamThicknessCm: number;
  governingHiddenBeamElement: string;
  recommendedUnifiedSlabAndHiddenCm: number;
  practicalUnifiedThicknessCm: number;
  maxRequiredDropBeamDepthCm: number;
  governingDropBeamElement: string;
  smartOptimization: SmartDropBeamSuggestion | null;
}

export interface GeneratedStoryFileEntry {
  storyId: string;
  storyNameAr: string;
  storyType: StoryType;
  multiplier: number;
  heightM: number;
  dataFilePath: string;
  cadFilePath: string;
  allowHiddenBeams: boolean;
  allowSlabs: boolean;
  pluginVisibility: 'VISIBLE_AUTHORIZED' | 'HIDDEN_LOCKED';
  status: 'ACTIVE_START' | 'PENDING_GROUND_COLUMNS' | 'ANALYZED';
}

export interface GeneratedProjectWorkspace {
  version: string;
  projectUuid: string;
  projectName: string;
  folderName: string;
  fullFolderPath: string;
  hollowBlockHeightCm: number;
  topSlabThicknessCm: number;
  hordiSelfWeightKnM2: number;
  totalSlabUltimateOrServiceLoadKnM2: number;
  mandatoryStartStoryId: string;
  filesTree: {
    masterFile: string;
    columnsTakedownFile: string;
    foundationsDesignFile: string;
    foundationsCadFile: string;
    boqQuantitiesFile: string;
    stories: GeneratedStoryFileEntry[];
  };
  masterJsonContent: Record<string, unknown>;
}

// =============================================================================
// 1. PROJECT NAME VALIDATION & HOLLOW BLOCK RULES
// =============================================================================

export function validateProjectName(name: string): {
  valid: boolean;
  cleanName: string;
  folderName: string;
  errorAr?: string;
} {
  const trimmed = (name || '').trim();
  if (!trimmed) {
    return {
      valid: false,
      cleanName: '',
      folderName: '',
      errorAr: 'Project Name cannot be empty.',
    };
  }

  const validRegex = /^[\u0600-\u06FFa-zA-Z0-9\s]+$/;
  if (!validRegex.test(trimmed)) {
    return {
      valid: false,
      cleanName: '',
      folderName: '',
      errorAr: 'Project Name must contain letters, digits, and spaces only (no special symbols).',
    };
  }

  const cleanName = trimmed.replace(/\s+/g, '_');
  return {
    valid: true,
    cleanName,
    folderName: `Stractural-${cleanName}`,
  };
}

export function computeHollowBlockParameters(
  slabThicknessCm: number,
  ribWidthCm = 15,
  blockWidthCm = 40,
  blockLengthCm = 25,
  blockWeightKn = 0.10,
  finishLoadKnM2 = 2.0,
  liveLoadKnM2 = 2.0
) {
  const blockHeightCm = slabThicknessCm >= 25 ? 20 : 16;
  const topFlangeCm = Math.max(5, slabThicknessCm - blockHeightCm);
  const ribSpacingCm = blockWidthCm + ribWidthCm;

  const gammaConcrete = 25.0;
  const topSlabWeightKnM2 = (topFlangeCm / 100.0) * gammaConcrete;
  const ribVolumePerMeterOfRib = (ribWidthCm / 100.0) * (blockHeightCm / 100.0);
  const ribsPerMeterWidth = 100.0 / ribSpacingCm;
  const ribsWeightKnM2 = ribVolumePerMeterOfRib * ribsPerMeterWidth * gammaConcrete;

  const blocksPerM2 = (100.0 / ribSpacingCm) * (100.0 / blockLengthCm);
  const blocksWeightKnM2 = blocksPerM2 * blockWeightKn;

  const hordiSelfWeightKnM2 = Number(
    (topSlabWeightKnM2 + ribsWeightKnM2 + blocksWeightKnM2).toFixed(2)
  );
  const totalDeadLoadKnM2 = Number((hordiSelfWeightKnM2 + finishLoadKnM2).toFixed(2));
  const totalServiceLoadKnM2 = Number((totalDeadLoadKnM2 + liveLoadKnM2).toFixed(2));

  return {
    blockHeightCm,
    topFlangeCm,
    ribSpacingCm,
    blocksPerM2: Number(blocksPerM2.toFixed(2)),
    hordiSelfWeightKnM2,
    totalDeadLoadKnM2,
    totalServiceLoadKnM2,
  };
}

// =============================================================================
// 2. WORKSPACE & <ProjectName>- PREFIXED FILE TREE GENERATOR
// =============================================================================

export function generateProjectWorkspace(config: ProjectMasterConfig): GeneratedProjectWorkspace {
  const validation = validateProjectName(config.projectName);
  if (!validation.valid) {
    throw new Error(validation.errorAr || 'Invalid project name');
  }

  const prefix = `${validation.cleanName}-`;
  const rootClean = (config.rootDirectory || 'C:\\XpertStudio_Projects').replace(/[\\/]+$/, '');
  const fullFolderPath = `${rootClean}\\${validation.folderName}`;
  const projectUuid = `XPERT-${Math.abs(hashCode(validation.folderName + '-2026')).toString(16).toUpperCase()}-V100`;

  const hordi = computeHollowBlockParameters(
    config.slabThicknessCm,
    config.ribWidthCm,
    40,
    25,
    0.10,
    config.finishLoadKnM2,
    config.liveLoadKnM2
  );

  const stories: GeneratedStoryFileEntry[] = [];
  const groundH = config.storyHeightM || 3.2;
  const upperH = config.upperStoryHeightM || 3.0;
  const basementH = config.basementHeightM || 3.0;

  // 00 - Tie Beams
  stories.push({
    storyId: '00_TieBeams',
    storyNameAr: '00 - Tie Beams & Grade Beams (00_TieBeams)',
    storyType: 'tie_beams',
    multiplier: 1,
    heightM: config.foundationDepthM,
    dataFilePath: `${fullFolderPath}\\Stories_Data\\${prefix}00_TieBeams.json`,
    cadFilePath: `${fullFolderPath}\\CAD_Drawings\\${prefix}00_TieBeams.dxf`,
    allowHiddenBeams: false,
    allowSlabs: false,
    pluginVisibility: 'VISIBLE_AUTHORIZED',
    status: 'PENDING_GROUND_COLUMNS',
  });

  // 01 - Optional Basement
  if (config.hasBasement) {
    stories.push({
      storyId: '01_Basement_Slab',
      storyNameAr: '01 - Basement Floor Slab (01_Basement_Slab)',
      storyType: 'basement',
      multiplier: 1,
      heightM: basementH,
      dataFilePath: `${fullFolderPath}\\Stories_Data\\${prefix}01_Basement_Slab.json`,
      cadFilePath: `${fullFolderPath}\\CAD_Drawings\\${prefix}01_Basement_Slab.dxf`,
      allowHiddenBeams: true,
      allowSlabs: true,
      pluginVisibility: 'VISIBLE_AUTHORIZED',
      status: 'PENDING_GROUND_COLUMNS',
    });
  }

  // 02 - Mandatory Ground Floor
  stories.push({
    storyId: '02_Ground_Floor',
    storyNameAr: '02 - Ground Floor Slab (Mandatory Start)',
    storyType: 'ground',
    multiplier: 1,
    heightM: groundH,
    dataFilePath: `${fullFolderPath}\\Stories_Data\\${prefix}02_Ground_Floor.json`,
    cadFilePath: `${fullFolderPath}\\CAD_Drawings\\${prefix}02_Ground_Floor.dxf`,
    allowHiddenBeams: true,
    allowSlabs: true,
    pluginVisibility: 'VISIBLE_AUTHORIZED',
    status: 'ACTIVE_START',
  });

  // Upper stories (Only if upperStoriesCount > 0 — no duplicate Roof Floor when 0!)
  const upperCount = Math.max(0, Math.floor(config.upperStoriesCount));
  if (upperCount > 0) {
    if (config.hasTypicalFloor && upperCount >= 2) {
      const repeatCount = Math.max(1, Math.min(upperCount - 1, config.typicalFloorCount));
      stories.push({
        storyId: '03_Typical_Floor',
        storyNameAr: `03 - Typical Upper Floor (Repeated x${repeatCount})`,
        storyType: 'typical',
        multiplier: repeatCount,
        heightM: upperH,
        dataFilePath: `${fullFolderPath}\\Stories_Data\\${prefix}03_Typical_Floor.json`,
        cadFilePath: `${fullFolderPath}\\CAD_Drawings\\${prefix}03_Typical_Floor.dxf`,
        allowHiddenBeams: true,
        allowSlabs: true,
        pluginVisibility: 'VISIBLE_AUTHORIZED',
        status: 'PENDING_GROUND_COLUMNS',
      });
      stories.push({
        storyId: '04_Roof_Floor',
        storyNameAr: '04 - Top Upper Floor Slab (04_Roof_Floor)',
        storyType: 'roof',
        multiplier: 1,
        heightM: upperH,
        dataFilePath: `${fullFolderPath}\\Stories_Data\\${prefix}04_Roof_Floor.json`,
        cadFilePath: `${fullFolderPath}\\CAD_Drawings\\${prefix}04_Roof_Floor.dxf`,
        allowHiddenBeams: true,
        allowSlabs: true,
        pluginVisibility: 'VISIBLE_AUTHORIZED',
        status: 'PENDING_GROUND_COLUMNS',
      });
    } else {
      for (let i = 0; i < upperCount; i++) {
        const isLast = i === upperCount - 1;
        const numCode = String(i + 3).padStart(2, '0');
        const storyId = isLast ? `${numCode}_Roof_Floor` : `${numCode}_Floor_${i + 1}`;
        stories.push({
          storyId,
          storyNameAr: `${numCode} - Upper Floor #${i + 1} (${storyId})`,
          storyType: isLast ? 'roof' : 'standard',
          multiplier: 1,
          heightM: upperH,
          dataFilePath: `${fullFolderPath}\\Stories_Data\\${prefix}${storyId}.json`,
          cadFilePath: `${fullFolderPath}\\CAD_Drawings\\${prefix}${storyId}.dxf`,
          allowHiddenBeams: true,
          allowSlabs: true,
          pluginVisibility: 'VISIBLE_AUTHORIZED',
          status: 'PENDING_GROUND_COLUMNS',
        });
      }
    }
  }

  const masterJsonContent = {
    appVersion: 'v1.0.0-studio-foundation',
    projectUuid,
    projectName: validation.cleanName,
    folderName: validation.folderName,
    mandatoryStartStoryId: '02_Ground_Floor',
    defaults: {
      slabThicknessCm: config.slabThicknessCm,
      hollowBlockHeightCm: hordi.blockHeightCm,
      hollowBlockDimensionsCm: '40x25',
      hollowBlockWeightKn: 0.1,
      ribWidthCm: config.ribWidthCm,
      hiddenBeamMinWidthCm: config.hiddenBeamMinWidthCm,
      dropBeamWidthCm: config.dropBeamWidthCm,
      dropBeamMinDepthCm: config.dropBeamMinDepthCm,
      wallWidthCm: config.wallWidthCm,
      groundStoryHeightM: groundH,
      upperStoryHeightM: upperH,
      fcMpa: config.fcMpa,
      fyMpa: config.fyMpa,
      finishLoadKnM2: config.finishLoadKnM2,
      liveLoadKnM2: config.liveLoadKnM2,
      soilBearingCapacityKnM2: config.soilBearingCapacityKnM2,
      foundationDepthM: config.foundationDepthM,
    },
    stories: stories.map((s) => ({
      storyId: s.storyId,
      storyLabel: s.storyNameAr,
      storyType: s.storyType,
      multiplier: s.multiplier,
      heightM: s.heightM,
      dataFile: s.dataFilePath,
      cadFile: s.cadFilePath,
      allowHiddenBeams: s.allowHiddenBeams,
      allowSlabs: s.allowSlabs,
      status: s.status,
    })),
  };

  return {
    version: 'v1.0.0-studio-foundation',
    projectUuid,
    projectName: validation.cleanName,
    folderName: validation.folderName,
    fullFolderPath,
    hollowBlockHeightCm: hordi.blockHeightCm,
    topSlabThicknessCm: hordi.topFlangeCm,
    hordiSelfWeightKnM2: hordi.hordiSelfWeightKnM2,
    totalSlabUltimateOrServiceLoadKnM2: hordi.totalServiceLoadKnM2,
    mandatoryStartStoryId: '02_Ground_Floor',
    filesTree: {
      masterFile: `${fullFolderPath}\\${prefix}00_Project_Master.json`,
      columnsTakedownFile: `${fullFolderPath}\\${prefix}Columns_Load_Takedown.json`,
      foundationsDesignFile: `${fullFolderPath}\\${prefix}Foundations_Design.json`,
      foundationsCadFile: `${fullFolderPath}\\CAD_Drawings\\${prefix}Foundations_And_Axes.dxf`,
      boqQuantitiesFile: `${fullFolderPath}\\${prefix}BOQ_Quantities.json`,
      stories,
    },
    masterJsonContent,
  };
}

// =============================================================================
// 3. CAD FILE AUTHORIZATION & MODE VERIFIER
// =============================================================================

export interface CadFileAuthorizationInput {
  fileName: string;
  isInsideStracturalProjectFolder: boolean;
  hasMasterJsonSibling: boolean;
  hasValidXpertSignature: boolean;
  drawingRole: 'STORY_EXTRACTION' | 'FOUNDATION_PLOT_ONLY' | 'EXTERNAL_UNMANAGED';
  storyType?: StoryType;
}

export function verifyAutoCadPluginVisibility(input: CadFileAuthorizationInput) {
  const allDisabled = {
    setupLayers: false,
    drawColumns: false,
    drawSlabBoundary: false,
    drawDropBeam: false,
    drawHiddenBeam: false,
    drawOpenings: false,
    drawSlabsAndRibs: false,
    checkDrawing: false,
    generateData: false,
  };

  if (!input.hasValidXpertSignature || input.drawingRole === 'EXTERNAL_UNMANAGED') {
    return {
      isRibbonVisible: false,
      statusTitleAr: 'Tools Locked (External Unmanaged CAD File)',
      reasonAr: 'File does not carry XPERT_AUTH_SIGNATURE.',
      enabledTools: allDisabled,
    };
  }

  if (!input.isInsideStracturalProjectFolder || !input.hasMasterJsonSibling) {
    return {
      isRibbonVisible: false,
      statusTitleAr: 'Tools Locked (Outside Stractural Project Folder)',
      reasonAr: 'File was moved outside its Stractural-<ProjectName> workspace.',
      enabledTools: allDisabled,
    };
  }

  if (input.drawingRole === 'FOUNDATION_PLOT_ONLY') {
    return {
      isRibbonVisible: false,
      statusTitleAr: 'Tools Locked (Foundations Output Sheet Only)',
      reasonAr: 'Foundations_And_Axes.dxf is an automated output drawing.',
      enabledTools: allDisabled,
    };
  }

  const isTieBeams = input.storyType === 'tie_beams';

  return {
    isRibbonVisible: true,
    statusTitleAr: isTieBeams
      ? 'Studio Active (Tie-Beams Mode — Drop Grade Beams Only)'
      : 'Studio Active (Authorized Story Structural Sheet)',
    reasonAr: isTieBeams
      ? 'Hidden beams, slabs, and openings are disabled at Tie-Beams level.'
      : 'All structural modeling, numbering, and DXF sync tools are active.',
    enabledTools: {
      setupLayers: true,
      drawColumns: true,
      drawSlabBoundary: !isTieBeams,
      drawDropBeam: true,
      drawHiddenBeam: !isTieBeams,
      drawOpenings: !isTieBeams,
      drawSlabsAndRibs: !isTieBeams,
      checkDrawing: true,
      generateData: true,
    },
  };
}

// =============================================================================
// 4. CLEAR SPAN (Ln), ACI 318 THICKNESS & SMART DROP-BEAM ADVISOR
// =============================================================================

export function getAciDeflectionDivisor(
  _elementCategory: 'rib' | 'hidden_beam' | 'drop_beam',
  continuityCase: SpanContinuityCase
): number {
  switch (continuityCase) {
    case 'simply_supported':
      return 16.0;
    case 'one_end_continuous':
      return 18.5;
    case 'both_ends_continuous':
      return 21.0;
    case 'cantilever':
      return 8.0;
  }
}

export function computeClearSpanAndACIDeflection(
  beams: StructuralBeamModel[],
  slabs: SlabPanelModel[],
  fyMpa = 350
): DeflectionSummaryReport {
  const fyModifier = Number((0.4 + fyMpa / 700.0).toFixed(4));
  const checks: DeflectionSpanCheck[] = [];

  for (const slab of slabs) {
    const clearLn = Math.max(
      0.2,
      Number(
        (
          slab.axisSpanCenterM -
          slab.leftSupportWidthM / 2.0 -
          (slab.isCantileverSlab ? 0 : slab.rightSupportWidthM / 2.0)
        ).toFixed(3)
      )
    );

    const continuity: SpanContinuityCase = slab.isCantileverSlab
      ? 'cantilever'
      : slab.connectedToCantilever
      ? 'one_end_continuous'
      : 'simply_supported';

    const divisor = getAciDeflectionDivisor('rib', continuity);
    const reqThicknessCm = Number(((clearLn * 100.0 / divisor) * fyModifier).toFixed(2));

    checks.push({
      elementId: slab.id,
      elementCategory: 'rib',
      spanLabel: slab.isCantileverSlab ? 'Cantilever Rib' : 'One-Way Hordi Rib',
      continuityCase: continuity,
      centerLengthM: slab.axisSpanCenterM,
      clearLengthLnM: clearLn,
      aciDivisor: divisor,
      fyModifier,
      requiredMinThicknessCm: reqThicknessCm,
    });
  }

  for (const beam of beams) {
    const category: 'hidden_beam' | 'drop_beam' =
      beam.beamKind === 'hidden' ? 'hidden_beam' : 'drop_beam';
    const hasLeftCant = beam.cantilevers.left > 0.001;
    const hasRightCant = beam.cantilevers.right > 0.001;
    const numSpans = beam.spans.length;

    if (hasLeftCant && beam.supports.length > 0) {
      const firstSupWidth = beam.supports[0].widthAlongBeamM;
      const clearLn = Math.max(0.1, Number((beam.cantilevers.left - firstSupWidth / 2.0).toFixed(3)));
      const divisor = getAciDeflectionDivisor(category, 'cantilever');
      const reqCm = Number(((clearLn * 100.0 / divisor) * fyModifier).toFixed(2));
      checks.push({
        elementId: beam.id,
        elementCategory: category,
        spanLabel: 'Left Cantilever (LC)',
        continuityCase: 'cantilever',
        centerLengthM: beam.cantilevers.left,
        clearLengthLnM: clearLn,
        aciDivisor: divisor,
        fyModifier,
        requiredMinThicknessCm: reqCm,
      });
    }

    for (let i = 0; i < numSpans; i++) {
      const leftSup = beam.supports[i];
      const rightSup = beam.supports[i + 1];
      const leftW = leftSup ? leftSup.widthAlongBeamM : 0.25;
      const rightW = rightSup ? rightSup.widthAlongBeamM : 0.25;
      const centerL = beam.spans[i];
      const clearLn = Math.max(0.2, Number((centerL - leftW / 2.0 - rightW / 2.0).toFixed(3)));

      const continuousLeft = i > 0 || hasLeftCant;
      const continuousRight = i < numSpans - 1 || hasRightCant;

      let continuity: SpanContinuityCase = 'simply_supported';
      if (continuousLeft && continuousRight) {
        continuity = 'both_ends_continuous';
      } else if (continuousLeft || continuousRight) {
        continuity = 'one_end_continuous';
      }

      const divisor = getAciDeflectionDivisor(category, continuity);
      const reqCm = Number(((clearLn * 100.0 / divisor) * fyModifier).toFixed(2));

      checks.push({
        elementId: beam.id,
        elementCategory: category,
        spanLabel: `Span L${i + 1}`,
        continuityCase: continuity,
        centerLengthM: centerL,
        clearLengthLnM: clearLn,
        aciDivisor: divisor,
        fyModifier,
        requiredMinThicknessCm: reqCm,
      });
    }

    if (hasRightCant && beam.supports.length > 0) {
      const lastSupWidth = beam.supports[beam.supports.length - 1].widthAlongBeamM;
      const clearLn = Math.max(0.1, Number((beam.cantilevers.right - lastSupWidth / 2.0).toFixed(3)));
      const divisor = getAciDeflectionDivisor(category, 'cantilever');
      const reqCm = Number(((clearLn * 100.0 / divisor) * fyModifier).toFixed(2));
      checks.push({
        elementId: beam.id,
        elementCategory: category,
        spanLabel: 'Right Cantilever (RC)',
        continuityCase: 'cantilever',
        centerLengthM: beam.cantilevers.right,
        clearLengthLnM: clearLn,
        aciDivisor: divisor,
        fyModifier,
        requiredMinThicknessCm: reqCm,
      });
    }
  }

  let maxRibCm = 0;
  let govRib = '—';
  let maxHiddenCm = 0;
  let govHidden = '—';
  let govHiddenBeamId = '';
  let govHiddenLn = 0;
  let maxDropCm = 0;
  let govDrop = '—';

  for (const c of checks) {
    if (c.elementCategory === 'rib' && c.requiredMinThicknessCm > maxRibCm) {
      maxRibCm = c.requiredMinThicknessCm;
      govRib = `${c.elementId} (${c.spanLabel}, Ln=${c.clearLengthLnM}m)`;
    } else if (c.elementCategory === 'hidden_beam' && c.requiredMinThicknessCm > maxHiddenCm) {
      maxHiddenCm = c.requiredMinThicknessCm;
      govHidden = `${c.elementId} (${c.spanLabel}, Ln=${c.clearLengthLnM}m)`;
      govHiddenBeamId = c.elementId;
      govHiddenLn = c.clearLengthLnM;
    } else if (c.elementCategory === 'drop_beam' && c.requiredMinThicknessCm > maxDropCm) {
      maxDropCm = c.requiredMinThicknessCm;
      govDrop = `${c.elementId} (${c.spanLabel}, Ln=${c.clearLengthLnM}m)`;
    }
  }

  const recommendedUnified = Number(Math.max(maxRibCm, maxHiddenCm).toFixed(2));
  const practicalUnified = Math.max(20, Math.ceil(recommendedUnified / 2.0) * 2);

  // Smart Drop-Beam Optimization Suggestion:
  // If recommendedUnified > 30.0 cm AND governed by a Hidden Beam while slabs & other hidden beams <= 30.0 cm
  let smartOptimization: SmartDropBeamSuggestion | null = null;
  if (recommendedUnified > 30.0 && maxHiddenCm > 30.0 && govHiddenBeamId) {
    let restMax = maxRibCm;
    for (const c of checks) {
      if (c.elementCategory === 'hidden_beam' && c.elementId !== govHiddenBeamId) {
        restMax = Math.max(restMax, c.requiredMinThicknessCm);
      }
    }
    if (restMax <= 30.0) {
      smartOptimization = {
        beamId: govHiddenBeamId,
        governingLnM: govHiddenLn,
        governingReqCm: maxHiddenCm,
        restOfFloorReqCm: Number(restMax.toFixed(1)),
        message: `Optimization Suggestion: Hidden Beam ${govHiddenBeamId} (Ln = ${govHiddenLn.toFixed(2)} m) governs the slab thickness at ${maxHiddenCm.toFixed(1)} cm (> 30 cm), while the rest of the floor requires only ${restMax.toFixed(1)} cm (≤ 30 cm). Converting ${govHiddenBeamId} to a Drop Beam keeps the slab thickness at 30.0 cm.`,
      };
    }
  }

  return {
    fyModifier,
    checks,
    maxRequiredSlabThicknessCm: maxRibCm,
    governingSlabElement: govRib,
    maxRequiredHiddenBeamThicknessCm: maxHiddenCm,
    governingHiddenBeamElement: govHidden,
    recommendedUnifiedSlabAndHiddenCm: recommendedUnified,
    practicalUnifiedThicknessCm: practicalUnified,
    maxRequiredDropBeamDepthCm: maxDropCm,
    governingDropBeamElement: govDrop,
    smartOptimization,
  };
}

// =============================================================================
// 5. TOPOLOGICAL SORTING FOR BEAM DEPENDENCIES
// =============================================================================

export function topologicalSortBeams(beams: StructuralBeamModel[]): {
  orderedBeamIds: string[];
  dependenciesMap: Record<string, string[]>;
  supportedByMap: Record<string, string[]>;
  hasCycle: boolean;
  cycleErrorAr?: string;
} {
  const beamIds = new Set(beams.map((b) => b.id));
  const dependenciesMap: Record<string, string[]> = {};
  const supportedByMap: Record<string, string[]> = {};
  const inDegree: Record<string, number> = {};

  for (const b of beams) {
    dependenciesMap[b.id] = [];
    supportedByMap[b.id] = [];
    inDegree[b.id] = 0;
  }

  for (const b of beams) {
    for (const sup of b.supports) {
      if (sup.kind === 'beam' && beamIds.has(sup.targetId) && sup.targetId !== b.id) {
        if (!dependenciesMap[b.id].includes(sup.targetId)) {
          dependenciesMap[b.id].push(sup.targetId);
          supportedByMap[sup.targetId].push(b.id);
          inDegree[sup.targetId] = (inDegree[sup.targetId] || 0) + 1;
        }
      }
    }
  }

  const queue: string[] = [];
  for (const b of beams) {
    if (inDegree[b.id] === 0) {
      queue.push(b.id);
    }
  }

  const orderedBeamIds: string[] = [];
  while (queue.length > 0) {
    const currentId = queue.shift()!;
    orderedBeamIds.push(currentId);
    for (const carrierId of dependenciesMap[currentId]) {
      inDegree[carrierId] -= 1;
      if (inDegree[carrierId] === 0) {
        queue.push(carrierId);
      }
    }
  }

  if (orderedBeamIds.length !== beams.length) {
    return {
      orderedBeamIds: beams.map((b) => b.id),
      dependenciesMap,
      supportedByMap,
      hasCycle: true,
      cycleErrorAr: 'Structural Warning: Circular beam support loop detected between two beams.',
    };
  }

  return {
    orderedBeamIds,
    dependenciesMap,
    supportedByMap,
    hasCycle: false,
  };
}

// =============================================================================
// 6. CONTINUOUS BEAM ANALYTICAL ENGINE + ACI 318 BEAM DESIGN
// =============================================================================

export function designBeamAci318(
  beam: StructuralBeamModel,
  maxPosMuKnM: number,
  maxFaceNegMuKnM: number,
  maxFaceVuKn: number,
  fcMpa = 20,
  fyMpa = 350
): BeamAciDesignResult {
  const bMm = Math.round(beam.widthM * 1000);
  const hMm = Math.round(beam.depthM * 1000);
  const dMm = Math.max(120, hMm - 45);

  const calcAst = (muKnM: number) => {
    const asMin = Math.max((0.25 * Math.sqrt(fcMpa)) / fyMpa, 1.4 / fyMpa) * bMm * dMm;
    const absMu = Math.abs(muKnM);
    let ast = asMin;
    if (absMu > 0.2) {
      const rn = (absMu * 1e6) / (0.9 * bMm * dMm * dMm);
      const term = Math.max(0.05, 1.0 - (2.0 * rn) / (0.85 * fcMpa));
      const rho = ((0.85 * fcMpa) / fyMpa) * (1.0 - Math.sqrt(term));
      ast = Math.max(asMin, rho * bMm * dMm);
    }
    const barArea16 = 201.06;
    const minBars = bMm >= 350 ? 4 : 2;
    const count = Math.max(minBars, Math.ceil(ast / barArea16));
    return { ast: Number(ast.toFixed(0)), label: `${count} Φ 16 mm` };
  };

  const bot = calcAst(maxPosMuKnM);
  const top = calcAst(maxFaceNegMuKnM);
  const vcKn = (0.17 * Math.sqrt(fcMpa) * bMm * dMm) / 1000.0;
  const phiVcKn = Number((0.75 * vcKn).toFixed(1));
  const stirrupsLabel =
    maxFaceVuKn <= phiVcKn * 1.4
      ? beam.beamKind === 'hidden'
        ? 'Φ 8 @ 150 mm (4-Legs)'
        : 'Φ 8 @ 150 mm (2-Legs)'
      : 'Φ 10 @ 120 mm (4-Legs)';

  return {
    beamId: beam.id,
    bMm,
    hMm,
    dMm,
    bottomAstMm2: bot.ast,
    bottomBarsLabel: bot.label,
    topAstMm2: top.ast,
    topBarsLabel: top.label,
    phiVcKn,
    stirrupsLabel,
    status: maxFaceVuKn <= phiVcKn * 3.0 ? 'SAFE' : 'INCREASE_DEPTH',
  };
}

export function solveContinuousBeamSlopeDeflection(
  beam: StructuralBeamModel,
  fcMpa = 20,
  fyMpa = 350
): SlopeDeflectionResult {
  const NS = beam.spans.length;
  if (NS < 1) {
    return {
      solved: false,
      error: 'Beam must have at least one span.',
      reactions: {},
      supportMoments: [],
      supportCriticalTable: [],
      maxPositiveMoments: [],
      maxAbsShearKn: 0,
      maxAbsMomentKnM: 0,
      maxFaceShearKn: 0,
      maxFaceNegMomentKnM: 0,
      xFull: [],
      vFull: [],
      mFull: [],
      academicReport: '',
    };
  }

  const cLeft = Number(beam.cantilevers.left || 0);
  const cRight = Number(beam.cantilevers.right || 0);
  const L: number[] = [0.0, ...beam.spans.map((s) => Number(s))];

  const spanStarts: number[] = [cLeft];
  for (const sLen of beam.spans) {
    spanStarts.push(spanStarts[spanStarts.length - 1] + Number(sLen));
  }

  let CL_moment = 0.0;
  let CL_force = 0.0;
  let CR_moment = 0.0;
  let CR_force = 0.0;

  const W1: Record<number, { w: number; a: number; c: number }[]> = {};
  const P1: Record<number, { p: number; a: number }[]> = {};
  for (let i = 1; i <= NS; i++) {
    W1[i] = [];
    P1[i] = [];
  }

  const rightStartX = spanStarts[spanStarts.length - 1];

  for (const load of beam.loads) {
    if (load.type === 'dist') {
      const wVal = Number(load.val);
      const dSt = Number(load.x1 ?? 0);
      const dEn = Number(load.x2 ?? 0);

      if (cLeft > 0 && dSt < cLeft) {
        const overlapSt = dSt;
        const overlapEn = Math.min(dEn, cLeft);
        const lenC = overlapEn - overlapSt;
        if (lenC > 0) {
          const fC = wVal * lenC;
          const armC = cLeft - (overlapSt + lenC / 2.0);
          CL_force += fC;
          CL_moment += fC * armC;
        }
      }

      if (cRight > 0 && dEn > rightStartX) {
        const overlapSt = Math.max(dSt, rightStartX);
        const overlapEn = dEn;
        const lenC = overlapEn - overlapSt;
        if (lenC > 0) {
          const fC = wVal * lenC;
          const armC = overlapSt + lenC / 2.0 - rightStartX;
          CR_force += fC;
          CR_moment += fC * armC;
        }
      }

      for (let i = 1; i <= NS; i++) {
        const sSt = spanStarts[i - 1];
        const sEn = spanStarts[i];
        const overlapSt = Math.max(dSt, sSt);
        const overlapEn = Math.min(dEn, sEn);
        if (overlapSt < overlapEn) {
          W1[i].push({
            w: wVal,
            a: overlapSt - sSt,
            c: overlapEn - overlapSt,
          });
        }
      }
    } else if (load.type === 'point') {
      const pVal = Number(load.val);
      const pX = Number(load.x ?? 0);

      if (cLeft > 0 && pX < cLeft) {
        CL_force += pVal;
        CL_moment += pVal * (cLeft - pX);
      }
      if (cRight > 0 && pX > rightStartX) {
        CR_force += pVal;
        CR_moment += pVal * (pX - rightStartX);
      }

      for (let i = 1; i <= NS; i++) {
        const sSt = spanStarts[i - 1];
        const sEn = spanStarts[i];
        const isInside =
          i === NS
            ? pX >= sSt - 1e-9 && pX <= sEn + 1e-9
            : (pX >= sSt - 1e-9 && pX < sEn - 1e-9) || Math.abs(pX - sSt) < 1e-6;
        if (isInside) {
          P1[i].push({
            p: pVal,
            a: pX - sSt,
          });
          break;
        }
      }
    }
  }

  const K2: number[] = new Array(NS + 2).fill(0.0);
  for (let i = 1; i <= NS; i++) {
    K2[i] = 1.0 / L[i];
  }

  const D: number[] = new Array(NS + 3).fill(0.0);
  const E: number[] = new Array(NS + 3).fill(0.0);
  D[1] = 4.0 * K2[1];
  E[1] = 2.0 * K2[1];
  for (let i = 2; i <= NS; i++) {
    D[i] = 4.0 * (K2[i - 1] + K2[i]);
    E[i] = 2.0 * K2[i];
  }
  D[NS + 1] = 4.0 * K2[NS];
  E[NS + 1] = 0.0;

  const FL: number[] = new Array(NS + 2).fill(0.0);
  const FR: number[] = new Array(NS + 2).fill(0.0);

  for (let i = 1; i <= NS; i++) {
    const Ll = L[i];
    for (const seg of W1[i]) {
      const ww = seg.w * seg.c;
      const Aa = seg.a;
      const Cc = seg.c;
      const Ss_val = Aa + Cc / 2.0;
      const Tt = Ll - Ss_val;
      FL[i] +=
        (ww * (Ss_val * (Tt * Tt) + ((Ss_val - 2.0 * Tt) * (Cc * Cc)) / 12.0)) / (Ll * Ll);
      FR[i] +=
        (ww * (Tt * (Ss_val * Ss_val) + ((Tt - 2.0 * Ss_val) * (Cc * Cc)) / 12.0)) / (Ll * Ll);
    }
    for (const pt of P1[i]) {
      const ww = pt.p;
      const Ss_val = pt.a;
      const Tt = Ll - Ss_val;
      FL[i] += (ww * (Ss_val * (Tt * Tt))) / (Ll * Ll);
      FR[i] += (ww * (Tt * (Ss_val * Ss_val))) / (Ll * Ll);
    }
  }

  const F: number[] = new Array(NS + 3).fill(0.0);
  F[1] = CL_moment - FL[1];
  for (let i = 2; i <= NS; i++) {
    F[i] = FR[i - 1] - FL[i];
  }
  F[NS + 1] = FR[NS] - CR_moment;

  const R_rot: number[] = new Array(NS + 3).fill(0.0);
  const d_temp: number[] = new Array(NS + 3).fill(0.0);
  const f_temp: number[] = new Array(NS + 3).fill(0.0);

  d_temp[1] = D[1];
  f_temp[1] = F[1];
  for (let i = 2; i <= NS + 1; i++) {
    if (Math.abs(d_temp[i - 1]) < 1e-12) {
      return {
        solved: false,
        error: 'Singular stiffness matrix',
        reactions: {},
        supportMoments: [],
        supportCriticalTable: [],
        maxPositiveMoments: [],
        maxAbsShearKn: 0,
        maxAbsMomentKnM: 0,
        maxFaceShearKn: 0,
        maxFaceNegMomentKnM: 0,
        xFull: [],
        vFull: [],
        mFull: [],
        academicReport: '',
      };
    }
    const m = E[i - 1] / d_temp[i - 1];
    d_temp[i] = D[i] - m * E[i - 1];
    f_temp[i] = F[i] - m * f_temp[i - 1];
  }

  R_rot[NS + 1] = f_temp[NS + 1] / d_temp[NS + 1];
  for (let i = NS; i >= 1; i--) {
    R_rot[i] = (f_temp[i] - E[i] * R_rot[i + 1]) / d_temp[i];
  }

  const ML: number[] = new Array(NS + 2).fill(0.0);
  const MR: number[] = new Array(NS + 2).fill(0.0);
  const Mus: number[] = new Array(NS + 3).fill(0.0);

  for (let i = 1; i <= NS; i++) {
    ML[i] = (4.0 * R_rot[i] + 2.0 * R_rot[i + 1]) * K2[i] + FL[i];
    MR[i] = (2.0 * R_rot[i] + 4.0 * R_rot[i + 1]) * K2[i] - FR[i];
  }

  Mus[1] = -CL_moment;
  for (let i = 1; i < NS; i++) {
    Mus[i + 1] = MR[i];
  }
  Mus[NS + 1] = -CR_moment;

  const RRR: number[] = new Array(NS + 2).fill(0.0);
  const RRL: number[] = new Array(NS + 2).fill(0.0);
  const RA: number[] = new Array(NS + 3).fill(0.0);

  for (let i = 1; i <= NS; i++) {
    const RRR1 = -(ML[i] + MR[i]) / L[i];
    const RRL1 = (ML[i] + MR[i]) / L[i];
    let RRL2 = 0.0;
    let RRR2 = 0.0;
    let RRR3 = 0.0;
    let RRL3 = 0.0;

    for (const seg of W1[i]) {
      const q_w = seg.w;
      const Dd_w = seg.c;
      const Aa_w = seg.a + Dd_w / 2.0;
      const Bb_w = L[i] - Aa_w;
      RRL2 += (q_w * Dd_w * Bb_w) / L[i];
      RRR2 += (q_w * Dd_w * Aa_w) / L[i];
    }

    for (const pt of P1[i]) {
      const q_p = pt.p;
      const Aa_p = pt.a;
      const Bb_p = L[i] - Aa_p;
      RRR3 += (q_p * Aa_p) / L[i];
      RRL3 += (q_p * Bb_p) / L[i];
    }

    RRR[i] = -(RRR1 + RRR2 + RRR3);
    RRL[i] = RRL1 + RRL2 + RRL3;
  }

  RA[1] = RRL[1] + CL_force;
  for (let i = 1; i < NS; i++) {
    RA[i + 1] = RRL[i + 1] - RRR[i];
  }
  RA[NS + 1] = -RRR[NS] + CR_force;

  const reactions: Record<number, number> = {};
  for (let i = 1; i <= NS + 1; i++) {
    reactions[i] = Number(RA[i].toFixed(3));
  }

  const totalLen = cLeft + beam.spans.reduce((a, b) => a + b, 0) + cRight;
  const numPts = Math.min(Math.max(Math.floor(200 * totalLen) + 1, 300), 2500);
  const xFull: number[] = [];
  const vFull: number[] = [];
  const mFull: number[] = [];

  let maxAbsShearKn = 0;
  let maxAbsMomentKnM = 0;

  for (let idx = 0; idx < numPts; idx++) {
    const xPos = (idx / (numPts - 1)) * totalLen;
    let vVal = 0.0;
    let mVal = 0.0;

    for (let s_i = 0; s_i < spanStarts.length; s_i++) {
      const s_x = spanStarts[s_i];
      if (xPos >= s_x - 1e-9) {
        vVal += RA[s_i + 1];
        mVal += RA[s_i + 1] * (xPos - s_x);
      }
    }

    for (const load of beam.loads) {
      if (load.type === 'point') {
        const lx = Number(load.x ?? 0);
        const lval = Number(load.val);
        if (xPos >= lx - 1e-9) {
          vVal -= lval;
          mVal -= lval * (xPos - lx);
        }
      } else if (load.type === 'dist') {
        const lx1 = Number(load.x1 ?? 0);
        const lx2 = Number(load.x2 ?? 0);
        const lval = Number(load.val);
        if (xPos > lx1) {
          const effLen = Math.min(xPos, lx2) - lx1;
          if (effLen > 0) {
            const fW = lval * effLen;
            vVal -= fW;
            mVal -= fW * (xPos - lx1 - effLen / 2.0);
          }
        }
      }
    }

    xFull.push(Number(xPos.toFixed(4)));
    vFull.push(Number(vVal.toFixed(3)));
    mFull.push(Number(mVal.toFixed(3)));

    if (Math.abs(vVal) > maxAbsShearKn) maxAbsShearKn = Number(Math.abs(vVal).toFixed(2));
    if (Math.abs(mVal) > maxAbsMomentKnM) maxAbsMomentKnM = Number(Math.abs(mVal).toFixed(2));
  }

  // Face-of-Support Critical Forces Table
  const supportCriticalTable: SupportCriticalForceRow[] = spanStarts.map((sx, s_i) => {
    const sup = beam.supports[s_i] || {
      supportIndex: s_i + 1,
      kind: 'column' as SupportKind,
      targetId: `C${s_i + 1}`,
      widthAlongBeamM: 0.25,
    };
    const wSup = sup.widthAlongBeamM || 0.25;
    const xFaceL = Math.max(0, sx - wSup / 2.0);
    const xFaceR = Math.min(totalLen, sx + wSup / 2.0);

    let faceNegM = Mus[s_i + 1] ?? 0;
    let faceV = 0;
    let centerV = 0;

    for (let k = 0; k < xFull.length; k++) {
      const xk = xFull[k];
      if (Math.abs(xk - sx) <= 0.04) {
        centerV = Math.max(centerV, Math.abs(vFull[k]));
      }
      if (Math.abs(xk - xFaceL) <= 0.05 || Math.abs(xk - xFaceR) <= 0.05) {
        faceV = Math.max(faceV, Math.abs(vFull[k]));
        if (mFull[k] < 0) {
          faceNegM = Math.max(faceNegM, mFull[k]); // reduced magnitude at face of support
        }
      }
    }

    return {
      supportIndex: s_i + 1,
      targetId: sup.targetId,
      kind: sup.kind,
      xM: Number(sx.toFixed(2)),
      reactionRuKn: Number((RA[s_i + 1] ?? 0).toFixed(2)),
      centerlineNegMuKnM: Number((Mus[s_i + 1] ?? 0).toFixed(2)),
      faceNegMuKnM: Number(faceNegM.toFixed(2)),
      centerlineVuKn: Number(centerV.toFixed(2)),
      faceVuKn: Number((faceV || centerV).toFixed(2)),
    };
  });

  const maxPositiveMoments: {
    spanIndex: number;
    maxMomentKnM: number;
    xLocalM: number;
    xGlobalM: number;
  }[] = [];

  for (let s_i = 0; s_i < NS; s_i++) {
    const sSt = spanStarts[s_i];
    const sEn = spanStarts[s_i + 1];
    let bestM = -Infinity;
    let bestX = sSt;
    for (let k = 0; k < xFull.length; k++) {
      if (xFull[k] >= sSt && xFull[k] <= sEn) {
        if (mFull[k] > bestM) {
          bestM = mFull[k];
          bestX = xFull[k];
        }
      }
    }
    maxPositiveMoments.push({
      spanIndex: s_i + 1,
      maxMomentKnM: Number((bestM > -Infinity ? bestM : 0).toFixed(2)),
      xLocalM: Number((bestX - sSt).toFixed(2)),
      xGlobalM: Number(bestX.toFixed(2)),
    });
  }

  const maxPosMu = Math.max(0, ...maxPositiveMoments.map((m) => m.maxMomentKnM));
  const maxFaceNegMu = Math.min(0, ...supportCriticalTable.map((s) => s.faceNegMuKnM));
  const maxFaceVu = Math.max(0, ...supportCriticalTable.map((s) => s.faceVuKn));

  const aciDesign = designBeamAci318(beam, maxPosMu, maxFaceNegMu, maxFaceVu, fcMpa, fyMpa);

  const E_mod = 4700 * Math.sqrt(fcMpa);
  const I_val = (beam.widthM * Math.pow(beam.depthM, 3)) / 12.0;
  const reportLines: string[] = [
    '==========================================================================',
    `   XPERT STRUCTURAL DESIGN STUDIO (v1.0.0) - BEAM CALCULATION SHEET       `,
    `              CONTINUOUS BEAM (${beam.id}) - ANALYTICAL SOLUTION           `,
    '==========================================================================',
    `Section: ${beam.beamKind === 'hidden' ? 'Hidden Beam' : 'Drop Beam'} | B = ${beam.widthM.toFixed(2)} m | H = ${beam.depthM.toFixed(2)} m`,
    `Materials: f'c = ${fcMpa} MPa | Fy = ${fyMpa} MPa | E = ${E_mod.toFixed(1)} MPa | I = ${I_val.toFixed(6)} m^4`,
    `Spans Count (NS) = ${NS} | Left Cantilever = ${cLeft.toFixed(2)} m | Right Cantilever = ${cRight.toFixed(2)} m`,
    '--------------------------------------------------------------------------',
    '1. Support Centerline & Face-of-Support Design Forces:',
  ];

  for (const row of supportCriticalTable) {
    reportLines.push(
      `   - Support #${row.supportIndex} [${row.targetId} - ${row.kind === 'column' ? 'Hinge' : 'Roller'}]: R = ${row.reactionRuKn.toFixed(2)} kN | M_center = ${row.centerlineNegMuKnM.toFixed(2)} kN.m | M_face = ${row.faceNegMuKnM.toFixed(2)} kN.m | V_face = ${row.faceVuKn.toFixed(2)} kN`
    );
  }

  reportLines.push('\n2. Maximum Span Positive Moments & ACI 318 Reinforcement:');
  for (const mp of maxPositiveMoments) {
    reportLines.push(
      `   - Span #${mp.spanIndex}: +M_u,max = ${mp.maxMomentKnM.toFixed(2)} kN.m (at x = ${mp.xLocalM.toFixed(2)} m)`
    );
  }
  reportLines.push(
    `   - Bottom Flexural Reinforcement: ${aciDesign.bottomBarsLabel} (As,req = ${aciDesign.bottomAstMm2} mm2)`
  );
  reportLines.push(
    `   - Top Support Reinforcement:     ${aciDesign.topBarsLabel} (As,req = ${aciDesign.topAstMm2} mm2)`
  );
  reportLines.push(
    `   - Shear Stirrups (ACI 318):      ${aciDesign.stirrupsLabel} (phi*Vc = ${aciDesign.phiVcKn} kN)`
  );
  reportLines.push('==========================================================================');

  return {
    solved: true,
    reactions,
    supportMoments: Mus.map((m) => Number(m.toFixed(2))),
    supportCriticalTable,
    maxPositiveMoments,
    maxAbsShearKn,
    maxAbsMomentKnM,
    maxFaceShearKn: maxFaceVu,
    maxFaceNegMomentKnM: maxFaceNegMu,
    xFull,
    vFull,
    mFull,
    academicReport: reportLines.join('\n'),
    aciDesign,
  };
}

// =============================================================================
// 7. SEQUENTIAL FLOOR ANALYSIS & 4-WAY COLUMN FRAMING CONNECTIVITY
// =============================================================================

export interface Column4WayFraming {
  North?: string;
  South?: string;
  East?: string;
  West?: string;
}

export interface FloorSequentialAnalysisOutput {
  orderedBeamIds: string[];
  hasCycle: boolean;
  cycleErrorAr?: string;
  updatedBeams: StructuralBeamModel[];
  beamResults: Record<string, SlopeDeflectionResult>;
  transferredReactionsLog: {
    fromSecondaryBeamId: string;
    toPrimaryBeamId: string;
    atPositionXM: number;
    reactionKn: number;
  }[];
  columnReactionsSummary: {
    columnId: string;
    x: number;
    y: number;
    bM: number;
    hM: number;
    activeInStory: boolean;
    contributingBeams: { beamId: string; reactionKn: number }[];
    framing4Way: Column4WayFraming;
    muxKnM: number;
    muyKnM: number;
    beamReactionsSumKn: number;
    columnSelfWeightKn: number;
    totalFloorLoadKn: number;
  }[];
}

export function runSequentialFloorAnalysis(
  initialBeams: StructuralBeamModel[],
  columns: StructuralColumnModel[],
  storyType: StoryType,
  storyHeightM = 3.0,
  fcMpa = 20,
  fyMpa = 350
): FloorSequentialAnalysisOutput {
  const workingBeams: StructuralBeamModel[] = initialBeams.map((b) => {
    const isTieBeamsMode = storyType === 'tie_beams';
    const filteredLoads = b.loads
      .filter((l) => l.category !== 'transferred_reaction')
      .filter((l) => (isTieBeamsMode ? l.category !== 'slab' : true));

    return {
      ...b,
      beamKind: isTieBeamsMode ? 'drop' : b.beamKind,
      layerName: isTieBeamsMode ? '00-XD-BEAM-DROP' : b.layerName,
      depthM: isTieBeamsMode ? Math.max(0.4, b.depthM) : b.depthM,
      loads: filteredLoads.map((l) => ({ ...l })),
    };
  });

  const beamMap: Record<string, StructuralBeamModel> = {};
  for (const wb of workingBeams) {
    beamMap[wb.id] = wb;
  }

  const topo = topologicalSortBeams(workingBeams);
  const beamResults: Record<string, SlopeDeflectionResult> = {};
  const transferredReactionsLog: FloorSequentialAnalysisOutput['transferredReactionsLog'] = [];

  for (const beamId of topo.orderedBeamIds) {
    const currentBeam = beamMap[beamId];
    if (!currentBeam) continue;

    const res = solveContinuousBeamSlopeDeflection(currentBeam, fcMpa, fyMpa);
    beamResults[beamId] = res;

    if (res.solved) {
      for (const sup of currentBeam.supports) {
        if (sup.kind === 'beam' && beamMap[sup.targetId]) {
          const rVal = res.reactions[sup.supportIndex] ?? 0;
          const posOnCarrier = sup.positionOnSupportingBeamM ?? 2.0;

          beamMap[sup.targetId].loads.push({
            id: `TR_${currentBeam.id}_TO_${sup.targetId}_S${sup.supportIndex}`,
            type: 'point',
            x: posOnCarrier,
            val: Number(rVal.toFixed(2)),
            sourceLabel: `Reaction from ${currentBeam.id}`,
            category: 'transferred_reaction',
          });

          transferredReactionsLog.push({
            fromSecondaryBeamId: currentBeam.id,
            toPrimaryBeamId: sup.targetId,
            atPositionXM: posOnCarrier,
            reactionKn: Number(rVal.toFixed(2)),
          });
        }
      }
    }
  }

  const columnReactionsSummary = columns.map((col) => {
    const contributingBeams: { beamId: string; reactionKn: number }[] = [];
    const framing4Way: Column4WayFraming = {};
    let sumKn = 0;
    let muxKnM = 0;
    let muyKnM = 0;

    if (col.activeInStory) {
      for (const b of workingBeams) {
        const res = beamResults[b.id];
        if (!res || !res.solved) continue;
        const isHoriz =
          Math.abs(b.endCoord.x - b.startCoord.x) >= Math.abs(b.endCoord.y - b.startCoord.y);
        const midX = (b.startCoord.x + b.endCoord.x) / 2;
        const midY = (b.startCoord.y + b.endCoord.y) / 2;

        for (const sup of b.supports) {
          if (sup.kind === 'column' && sup.targetId === col.id) {
            const rVal = res.reactions[sup.supportIndex] ?? 0;
            const mVal = Math.abs(res.supportMoments[sup.supportIndex] ?? 0);
            contributingBeams.push({
              beamId: b.id,
              reactionKn: Number(rVal.toFixed(2)),
            });
            sumKn += rVal;

            const sectionTag = `${b.id} (${Math.round(b.widthM * 100)}x${Math.round(b.depthM * 100)})`;
            if (isHoriz) {
              muyKnM += mVal * 0.35 + 8.0;
              if (midX >= col.x) framing4Way.East = sectionTag;
              if (midX <= col.x) framing4Way.West = sectionTag;
            } else {
              muxKnM += mVal * 0.35 + 6.0;
              if (midY >= col.y) framing4Way.North = sectionTag;
              if (midY <= col.y) framing4Way.South = sectionTag;
            }
          }
        }
      }
    }

    const colSelfWeightKn = col.activeInStory
      ? Number((col.bM * col.hM * storyHeightM * 25.0).toFixed(2))
      : 0;

    return {
      columnId: col.id,
      x: col.x,
      y: col.y,
      bM: col.bM,
      hM: col.hM,
      activeInStory: col.activeInStory,
      contributingBeams,
      framing4Way,
      muxKnM: Number(muxKnM.toFixed(1)),
      muyKnM: Number(muyKnM.toFixed(1)),
      beamReactionsSumKn: Number(sumKn.toFixed(2)),
      columnSelfWeightKn: colSelfWeightKn,
      totalFloorLoadKn: Number((sumKn + colSelfWeightKn).toFixed(2)),
    };
  });

  return {
    orderedBeamIds: topo.orderedBeamIds,
    hasCycle: topo.hasCycle,
    cycleErrorAr: topo.cycleErrorAr,
    updatedBeams: workingBeams,
    beamResults,
    transferredReactionsLog,
    columnReactionsSummary,
  };
}

// =============================================================================
// 8. SPCOLUMN (.CTI) EXPORT, COLUMN P-M DIAGRAM & ASCII DXF GENERATOR
// =============================================================================

export function designColumnAciAndExportSpColumn(
  columnId: string,
  bM: number,
  hM: number,
  totalFactoredPuKn: number,
  muxKnM = 15.0,
  muyKnM = 10.0,
  fcMpa = 25,
  fyMpa = 400
): {
  agMm2: number;
  requiredAstMm2: number;
  usedSteelRatioPct: number;
  chosenBarsLabel: string;
  axialCapacityPhiPnKn: number;
  balancedMomentPhiMbKnM: number;
  pureFlexurePhiM0KnM: number;
  pmCurvePoints: { mKnM: number; pKn: number }[];
  utilizationRatio: number;
  status: 'SAFE' | 'OVERSTRESSED';
  spColumnCtiContent: string;
} {
  const bMm = Math.round(bM * 1000);
  const hMm = Math.round(hM * 1000);
  const agMm2 = bMm * hMm;

  const phi = 0.65;
  const alpha = 0.80;
  const puNewton = totalFactoredPuKn * 1000.0;

  const concreteTerm = 0.85 * fcMpa * agMm2;
  const rawAstMm2 =
    (puNewton / (phi * alpha) - concreteTerm) / (fyMpa - 0.85 * fcMpa);

  const minAstMm2 = 0.01 * agMm2;
  const requiredAstMm2 = Math.max(minAstMm2, rawAstMm2);

  const barArea16 = 201.06;
  const numBars16 = Math.max(6, Math.ceil(requiredAstMm2 / barArea16 / 2) * 2);
  const providedAstMm2 = numBars16 * barArea16;
  const usedSteelRatioPct = Number(((providedAstMm2 / agMm2) * 100).toFixed(2));

  const phiPnNewton =
    phi * alpha * (0.85 * fcMpa * (agMm2 - providedAstMm2) + fyMpa * providedAstMm2);
  const axialCapacityPhiPnKn = Number((phiPnNewton / 1000.0).toFixed(1));
  const balancedMomentPhiMbKnM = Number(
    ((0.65 * (0.22 * fcMpa * bMm * hMm * hMm + fyMpa * providedAstMm2 * 0.35 * hMm)) / 1e6).toFixed(1)
  );
  const pureFlexurePhiM0KnM = Number(
    ((0.90 * fyMpa * providedAstMm2 * 0.40 * hMm) / 1e6).toFixed(1)
  );

  const pmCurvePoints = [
    { mKnM: 0, pKn: axialCapacityPhiPnKn },
    { mKnM: Number((balancedMomentPhiMbKnM * 0.6).toFixed(1)), pKn: Number((axialCapacityPhiPnKn * 0.85).toFixed(1)) },
    { mKnM: balancedMomentPhiMbKnM, pKn: Number((axialCapacityPhiPnKn * 0.42).toFixed(1)) },
    { mKnM: pureFlexurePhiM0KnM, pKn: 0 },
  ];

  const utilizationRatio = Number((totalFactoredPuKn / Math.max(1, axialCapacityPhiPnKn)).toFixed(2));

  const ctiLines = [
    `#spColumn Input File (Generated by Xpert Structural Design Studio v1.0.0)`,
    `[Project]`,
    `Project=Xpert Structural Design Studio`,
    `Column=${columnId}`,
    `Engineer=Eng. Yousef Mohammed Keshlaf`,
    `Code=ACI 318-19`,
    `Units=SI (Metric - mm, MPa, kN, kN-m)`,
    `RunAxis=Biaxial`,
    `[Section]`,
    `Shape=Rectangular`,
    `Width_B_mm=${bMm}`,
    `Depth_H_mm=${hMm}`,
    `Ag_mm2=${agMm2}`,
    `[Material]`,
    `fc_MPa=${fcMpa.toFixed(1)}`,
    `Ec_MPa=${(4700 * Math.sqrt(fcMpa)).toFixed(0)}`,
    `fy_MPa=${fyMpa.toFixed(1)}`,
    `Es_MPa=200000`,
    `[Reinforcement]`,
    `Confinement=Tied (phi=0.65)`,
    `TotalBars=${numBars16}`,
    `BarDiameter_mm=16`,
    `ProvidedAst_mm2=${providedAstMm2.toFixed(1)}`,
    `Rho_pct=${usedSteelRatioPct}`,
    `ClearCover_mm=40`,
    `[FactoredLoads]`,
    `LoadCase_1=${totalFactoredPuKn.toFixed(1)}, ${muxKnM.toFixed(1)}, ${muyKnM.toFixed(1)}`,
  ];

  return {
    agMm2,
    requiredAstMm2: Number(requiredAstMm2.toFixed(0)),
    usedSteelRatioPct,
    chosenBarsLabel: `${numBars16} Φ 16 mm`,
    axialCapacityPhiPnKn,
    balancedMomentPhiMbKnM,
    pureFlexurePhiM0KnM,
    pmCurvePoints,
    utilizationRatio,
    status: utilizationRatio <= 1.0 && usedSteelRatioPct <= 8.0 ? 'SAFE' : 'OVERSTRESSED',
    spColumnCtiContent: ctiLines.join('\n'),
  };
}

export function exportStoryToDxfContent(
  columns: StructuralColumnModel[],
  beams: StructuralBeamModel[]
): string {
  const lines: string[] = [
    '0', 'SECTION', '2', 'HEADER',
    '9', '$INSUNITS', '70', '6',
    '0', 'ENDSEC',
    '0', 'SECTION', '2', 'ENTITIES',
  ];

  for (const col of columns) {
    if (!col.activeInStory) continue;
    const tagX = (col.x + col.bM / 2 + 0.12).toFixed(3);
    const tagY = (col.y + col.hM / 2 + 0.12).toFixed(3);
    lines.push(
      '0', 'TEXT', '8', '00-XD-TAG-COL', '62', '3',
      '10', tagX, '20', tagY, '30', '0.0',
      '40', '0.22', '1', col.id
    );
  }

  for (const b of beams) {
    const isVert = Math.abs(b.endCoord.y - b.startCoord.y) > Math.abs(b.endCoord.x - b.startCoord.x);
    const firstSpan = b.spans[0] || 4.0;
    const tagX = isVert
      ? (b.startCoord.x - 0.24).toFixed(3)
      : (b.startCoord.x + firstSpan * 0.5).toFixed(3);
    const tagY = isVert
      ? (b.startCoord.y + firstSpan * 0.5).toFixed(3)
      : (b.startCoord.y + 0.24).toFixed(3);
    lines.push(
      '0', 'LINE', '8', b.beamKind === 'hidden' ? '00-XD-BEAM-HID' : '00-XD-BEAM-DROP',
      '10', b.startCoord.x.toFixed(3), '20', b.startCoord.y.toFixed(3), '30', '0.0',
      '11', b.endCoord.x.toFixed(3), '21', b.endCoord.y.toFixed(3), '31', '0.0',
      '0', 'TEXT', '8', '00-XD-TAG-BEAM', '62', '30',
      '10', tagX, '20', tagY, '30', '0.0',
      '40', '0.25', '50', isVert ? '90.0' : '0.0', '1', b.id
    );
  }

  lines.push('0', 'ENDSEC', '0', 'EOF');
  return lines.join('\n');
}

function hashCode(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return h;
}
