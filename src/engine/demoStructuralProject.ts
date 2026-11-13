import type {
  ProjectMasterConfig,
  StructuralBeamModel,
  StructuralColumnModel,
  SlabPanelModel,
} from './structuralEngine';

export const DEFAULT_MASTER_CONFIG: ProjectMasterConfig = {
  projectName: 'Villa Al Yasmin',
  rootDirectory: 'C:\\XpertStudio_Projects',
  upperStoriesCount: 2,
  hasBasement: false,
  basementHeightM: 3.0,
  hasTypicalFloor: true,
  typicalFloorCount: 2,
  includePenthouse: false,
  slabThicknessCm: 30,       // Default 30 cm -> automatic 20 cm hollow block
  ribWidthCm: 15,            // Default 15 cm rib width
  hiddenBeamMinWidthCm: 30,  // Default 30 cm (0.30 m)
  dropBeamWidthCm: 20,       // Default 20 cm (0.20 m)
  dropBeamMinDepthCm: 40,    // Default 40 cm (0.40 m)
  wallWidthCm: 20,           // Default 20 cm
  storyHeightM: 3.2,         // Ground Floor Height (Mandatory Start = 3.20 m)
  upperStoryHeightM: 3.0,    // Upper Floor Height = 3.00 m
  fcMpa: 20,                 // Default 20 MPa
  fyMpa: 350,                // Default 350 MPa (Range up to 1000 MPa)
  finishLoadKnM2: 2.0,       // Default 2.0 kN/m²
  liveLoadKnM2: 2.0,         // Default 2.0 kN/m²
  soilBearingCapacityKnM2: 150, // Default 150 kN/m² (Range up to 2000 kN/m²)
  foundationDepthM: 1.5,     // Excavation / Foundation Depth = 1.50 m
};

export const INITIAL_COLUMNS: StructuralColumnModel[] = [
  { id: 'C1', x: 0.0, y: 8.5, bM: 0.25, hM: 0.50, activeInStory: true },
  { id: 'C2', x: 5.2, y: 8.5, bM: 0.25, hM: 0.60, activeInStory: true },
  { id: 'C3', x: 10.0, y: 8.5, bM: 0.25, hM: 0.50, activeInStory: true },
  { id: 'C4', x: 0.0, y: 4.2, bM: 0.25, hM: 0.50, activeInStory: true },
  { id: 'C5', x: 5.2, y: 4.2, bM: 0.30, hM: 0.60, activeInStory: true },
  { id: 'C6', x: 10.0, y: 4.2, bM: 0.25, hM: 0.50, activeInStory: true },
  { id: 'C7', x: 0.0, y: 0.0, bM: 0.25, hM: 0.50, activeInStory: true },
  { id: 'C8', x: 5.2, y: 0.0, bM: 0.25, hM: 0.60, activeInStory: true },
  { id: 'C9', x: 10.0, y: 0.0, bM: 0.25, hM: 0.50, activeInStory: true },
];

export const INITIAL_BEAMS: StructuralBeamModel[] = [
  {
    id: 'B1',
    beamKind: 'drop',
    layerName: '00-XD-BEAM-DROP',
    widthM: 0.20,
    depthM: 0.50,
    cantilevers: { left: 0.0, right: 1.4 },
    spans: [5.2, 4.8],
    supports: [
      { supportIndex: 1, kind: 'column', targetId: 'C1', widthAlongBeamM: 0.25 },
      { supportIndex: 2, kind: 'column', targetId: 'C2', widthAlongBeamM: 0.25 },
      { supportIndex: 3, kind: 'column', targetId: 'C3', widthAlongBeamM: 0.25 },
    ],
    loads: [
      {
        id: 'B1_L1',
        type: 'dist',
        x1: 0,
        x2: 11.4,
        val: 12.5,
        sourceLabel: 'Beam Self-Weight + Exterior Wall (20 cm)',
        category: 'wall',
      },
      {
        id: 'B1_L2',
        type: 'dist',
        x1: 0,
        x2: 10.0,
        val: 18.4,
        sourceLabel: 'Hollow-Block Slab S1 Rib Reaction',
        category: 'slab',
      },
    ],
    startCoord: { x: 0.0, y: 8.5 },
    endCoord: { x: 11.4, y: 8.5 },
  },
  {
    id: 'B2',
    beamKind: 'hidden',
    layerName: '00-XD-BEAM-HID',
    widthM: 0.70,
    depthM: 0.30,
    cantilevers: { left: 0.0, right: 1.4 },
    spans: [5.2, 4.8],
    supports: [
      { supportIndex: 1, kind: 'column', targetId: 'C4', widthAlongBeamM: 0.25 },
      { supportIndex: 2, kind: 'column', targetId: 'C5', widthAlongBeamM: 0.30 },
      { supportIndex: 3, kind: 'column', targetId: 'C6', widthAlongBeamM: 0.25 },
    ],
    loads: [
      {
        id: 'B2_L1',
        type: 'dist',
        x1: 0,
        x2: 11.4,
        val: 5.25,
        sourceLabel: 'Hidden Beam Self-Weight (0.70 x 0.30 m)',
        category: 'self_weight',
      },
      {
        id: 'B2_L2',
        type: 'dist',
        x1: 0,
        x2: 11.4,
        val: 34.8,
        sourceLabel: 'Tributary Load from Slabs S1 + S2',
        category: 'slab',
      },
    ],
    startCoord: { x: 0.0, y: 4.2 },
    endCoord: { x: 11.4, y: 4.2 },
  },
  {
    id: 'B3',
    beamKind: 'drop',
    layerName: '00-XD-BEAM-DROP',
    widthM: 0.20,
    depthM: 0.50,
    cantilevers: { left: 0.0, right: 0.0 },
    spans: [5.2, 4.8],
    supports: [
      { supportIndex: 1, kind: 'column', targetId: 'C7', widthAlongBeamM: 0.25 },
      { supportIndex: 2, kind: 'column', targetId: 'C8', widthAlongBeamM: 0.25 },
      { supportIndex: 3, kind: 'column', targetId: 'C9', widthAlongBeamM: 0.25 },
    ],
    loads: [
      {
        id: 'B3_L1',
        type: 'dist',
        x1: 0,
        x2: 10.0,
        val: 12.5,
        sourceLabel: 'Beam Self-Weight + Facade Wall (20 cm)',
        category: 'wall',
      },
      {
        id: 'B3_L2',
        type: 'dist',
        x1: 0,
        x2: 10.0,
        val: 17.6,
        sourceLabel: 'Hollow-Block Slab S2 Rib Reaction',
        category: 'slab',
      },
    ],
    startCoord: { x: 0.0, y: 0.0 },
    endCoord: { x: 10.0, y: 0.0 },
  },
  {
    id: 'B4',
    beamKind: 'drop',
    layerName: '00-XD-BEAM-DROP',
    widthM: 0.20,
    depthM: 0.45,
    cantilevers: { left: 0.0, right: 0.0 },
    spans: [4.2, 4.3],
    supports: [
      { supportIndex: 1, kind: 'column', targetId: 'C8', widthAlongBeamM: 0.60 },
      { supportIndex: 2, kind: 'column', targetId: 'C5', widthAlongBeamM: 0.60 },
      { supportIndex: 3, kind: 'column', targetId: 'C2', widthAlongBeamM: 0.60 },
    ],
    loads: [
      {
        id: 'B4_L1',
        type: 'dist',
        x1: 0,
        x2: 8.5,
        val: 11.8,
        sourceLabel: 'Beam Self-Weight + Partition Wall (20 cm)',
        category: 'wall',
      },
    ],
    startCoord: { x: 5.2, y: 0.0 },
    endCoord: { x: 5.2, y: 8.5 },
  },
  {
    id: 'B5',
    beamKind: 'hidden',
    layerName: '00-XD-BEAM-HID',
    widthM: 0.40,
    depthM: 0.30,
    cantilevers: { left: 0.0, right: 0.0 },
    spans: [4.3],
    supports: [
      {
        supportIndex: 1,
        kind: 'beam',
        targetId: 'B2',
        widthAlongBeamM: 0.70,
        positionOnSupportingBeamM: 7.6,
      },
      {
        supportIndex: 2,
        kind: 'beam',
        targetId: 'B1',
        widthAlongBeamM: 0.20,
        positionOnSupportingBeamM: 7.6,
      },
    ],
    loads: [
      {
        id: 'B5_L1',
        type: 'dist',
        x1: 0,
        x2: 4.3,
        val: 16.5,
        sourceLabel: 'Trimming Beam Around Shaft OP1 + Interrupted Ribs',
        category: 'slab',
      },
    ],
    startCoord: { x: 7.6, y: 4.2 },
    endCoord: { x: 7.6, y: 8.5 },
  },
];

export const INITIAL_SLABS: SlabPanelModel[] = [
  {
    id: 'S1',
    ribDirectionDeg: 90,
    axisSpanCenterM: 4.3,
    leftSupportBeamId: 'B2',
    rightSupportBeamId: 'B1',
    leftSupportWidthM: 0.70,
    rightSupportWidthM: 0.20,
    isCantileverSlab: false,
    connectedToCantilever: true,
    areaM2: 43.0,
  },
  {
    id: 'S2',
    ribDirectionDeg: 90,
    axisSpanCenterM: 4.2,
    leftSupportBeamId: 'B3',
    rightSupportBeamId: 'B2',
    leftSupportWidthM: 0.20,
    rightSupportWidthM: 0.70,
    isCantileverSlab: false,
    connectedToCantilever: false,
    areaM2: 42.0,
  },
  {
    id: 'S3_Cantilever',
    ribDirectionDeg: 0,
    axisSpanCenterM: 1.4,
    leftSupportBeamId: 'C3-C6',
    rightSupportBeamId: 'FREE',
    leftSupportWidthM: 0.25,
    rightSupportWidthM: 0.0,
    isCantileverSlab: true,
    connectedToCantilever: false,
    areaM2: 6.02,
  },
];

export const VERSION_CHANGELOG_LIST = [
  {
    version: 'v1.0.0-studio-foundation',
    date: '2026-11-13',
    title: 'Xpert Structural Design Studio — All-in-One Desktop & Web Structural Suite (Zero-Ribbon Classic Studio)',
    changes: [
      'Re-architected application into Xpert Structural Design Studio (v1.0.0) with a Modal New Project Dialog that closes on OK and opens the main studio directly on 02_Ground_Floor.',
      'Replaced external AutoCAD plugin dependency with a built-in 2D Interactive Structural CAD Modeler featuring Classic Menu Bar, Classic Top & Left Toolbars (Zero Ribbon), Architectural DXF Underlay, and live 2-way .DXF + .JSON synchronization.',
      'Implemented Color-Coded Non-Overlapping CAD Tagging: Bright Green (ACI Color 3) Column tags placed outside top-right column corners, and Bright Orange (ACI Color 30) Beam tags placed parallel to beams at the midpoint of the first clear span.',
      'Added Automatic Background ACI 318 Thickness Evaluation per story with Read-Only Calculated Thickness vs Editable Adopted Thickness (30 cm default) and Smart Drop-Beam Optimization Suggestion when a Hidden Beam governs > 30 cm.',
      'Built 1-Click Analyze All Beams (F5) with All-Beams Master Summary Table, Interactive Beam Inspector (Hinge △ vs Roller △○○, SFD, BMD, Face-of-Support forces), 4-Way Column Framing Connectivity, P-M Interaction Diagrams, and Printable Master Calculation Report.',
    ],
  },
];
