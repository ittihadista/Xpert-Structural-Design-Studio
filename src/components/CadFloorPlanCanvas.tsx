import React, { useState } from 'react';
import type {
  StructuralBeamModel,
  StructuralColumnModel,
  SlabPanelModel,
  StoryType,
} from '../engine/structuralEngine';

export type CadToolMode =
  | 'SELECT'
  | 'ADD_COLUMN'
  | 'DRAW_HIDDEN_BEAM'
  | 'DRAW_DROP_BEAM'
  | 'DISCONTINUE_COL'
  | 'TOGGLE_RIB';

interface CadFloorPlanCanvasProps {
  columns: StructuralColumnModel[];
  beams: StructuralBeamModel[];
  slabs: SlabPanelModel[];
  selectedBeamId: string;
  onSelectBeam: (beamId: string) => void;
  onToggleColumnContinuity?: (columnId: string) => void;
  onAddColumnAt?: (xM: number, yM: number) => void;
  onAddBeamBetweenColumns?: (colStartId: string, colEndId: string, kind: 'hidden' | 'drop') => void;
  onToggleSlabRibDirection?: (slabId: string) => void;
  onExportDxf?: () => void;
  storyType: StoryType;
  storyLabel: string;
}

export const CadFloorPlanCanvas: React.FC<CadFloorPlanCanvasProps> = ({
  columns,
  beams,
  slabs,
  selectedBeamId,
  onSelectBeam,
  onToggleColumnContinuity,
  onAddColumnAt,
  onAddBeamBetweenColumns,
  onToggleSlabRibDirection,
  onExportDxf,
  storyType,
  storyLabel,
}) => {
  const [activeTool, setActiveTool] = useState<CadToolMode>('SELECT');
  const [showArchUnderlay, setShowArchUnderlay] = useState<boolean>(true);
  const [orthoEnabled, setOrthoEnabled] = useState<boolean>(true);
  const [osnapEnabled, setOsnapEnabled] = useState<boolean>(true);
  const [pendingStartColId, setPendingStartColId] = useState<string | null>(null);
  const [cursorWorld, setCursorWorld] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const isTieBeams = storyType === 'tie_beams';
  const isGround = storyType === 'ground';

  const svgW = 840;
  const svgH = 510;
  const scale = 44;
  const offsetX = 110;
  const offsetY = 455;

  const toX = (xm: number) => offsetX + xm * scale;
  const toY = (ym: number) => offsetY - ym * scale;
  const toWorldX = (px: number) => Number(((px - offsetX) / scale).toFixed(2));
  const toWorldY = (py: number) => Number(((offsetY - py) / scale).toFixed(2));

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (svgW / rect.width);
    const sy = (e.clientY - rect.top) * (svgH / rect.height);
    setCursorWorld({ x: toWorldX(sx), y: toWorldY(sy) });
  };

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (activeTool === 'ADD_COLUMN' && onAddColumnAt) {
      const rect = e.currentTarget.getBoundingClientRect();
      const sx = (e.clientX - rect.left) * (svgW / rect.width);
      const sy = (e.clientY - rect.top) * (svgH / rect.height);
      const xm = Math.max(0, Math.min(11.5, toWorldX(sx)));
      const ym = Math.max(0, Math.min(9.0, toWorldY(sy)));
      onAddColumnAt(xm, ym);
      setActiveTool('SELECT');
    }
  };

  const handleColumnClick = (e: React.MouseEvent, colId: string) => {
    e.stopPropagation();
    if (activeTool === 'DRAW_HIDDEN_BEAM' || activeTool === 'DRAW_DROP_BEAM') {
      if (!pendingStartColId) {
        setPendingStartColId(colId);
      } else if (pendingStartColId !== colId && onAddBeamBetweenColumns) {
        onAddBeamBetweenColumns(
          pendingStartColId,
          colId,
          activeTool === 'DRAW_HIDDEN_BEAM' ? 'hidden' : 'drop'
        );
        setPendingStartColId(null);
        setActiveTool('SELECT');
      }
      return;
    }

    if ((activeTool === 'DISCONTINUE_COL' || !isGround) && onToggleColumnContinuity && !isGround) {
      onToggleColumnContinuity(colId);
    }
  };

  return (
    <div className="bg-slate-900 text-slate-100 rounded border border-slate-800 flex flex-col">
      {/* Studio CAD Top Status Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-2 bg-slate-950 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-bold text-slate-100">2D Structural CAD Studio — {storyLabel}</span>
          <span className="text-slate-500">|</span>
          <span className="font-mono text-emerald-400">
            Tool: {activeTool}
            {pendingStartColId ? ` (Start: ${pendingStartColId} → Click Target Column)` : ''}
          </span>
        </div>

        {/* CAD Layer & Tag Color Legend */}
        <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
          <span className="text-red-400">■ 00-XD-COL</span>
          <span className="text-green-400 font-bold">C# Tag (Green Outside Corner)</span>
          <span className="text-emerald-400">━ Drop Beam (0.20m)</span>
          {!isTieBeams && <span className="text-yellow-400">┅ Hidden Beam (≥0.30m)</span>}
          <span className="text-orange-400 font-bold">B# Tag (Orange Mid-Clear-Span)</span>
        </div>
      </div>

      {/* Main Studio Area: Left Vertical Classic CAD Toolbar + Right Interactive Canvas */}
      <div className="flex flex-1 min-h-[480px]">
        {/* Left Vertical Classic CAD Toolbar (No Ribbon!) */}
        <div className="w-44 bg-slate-950 border-r border-slate-800 p-2 flex flex-col gap-1.5 shrink-0">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1 pb-1 border-b border-slate-800">
            CAD Drawing Tools
          </div>

          <button
            type="button"
            onClick={() => {
              setActiveTool('SELECT');
              setPendingStartColId(null);
            }}
            className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
              activeTool === 'SELECT'
                ? 'bg-sky-600 text-white font-semibold'
                : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
            }`}
          >
            1. Select / Inspect
          </button>

          <button
            type="button"
            onClick={() => setShowArchUnderlay((v) => !v)}
            className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
              showArchUnderlay
                ? 'bg-slate-800 text-cyan-300 border border-cyan-800'
                : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
            }`}
          >
            2. Arch .DXF Underlay ({showArchUnderlay ? 'ON' : 'OFF'})
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTool('ADD_COLUMN');
              setPendingStartColId(null);
            }}
            className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
              activeTool === 'ADD_COLUMN'
                ? 'bg-emerald-600 text-white font-semibold'
                : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
            }`}
          >
            3. + Draw Column (C#)
          </button>

          {!isGround && (
            <button
              type="button"
              onClick={() => setActiveTool('DISCONTINUE_COL')}
              className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
                activeTool === 'DISCONTINUE_COL'
                  ? 'bg-rose-600 text-white font-semibold'
                  : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
              }`}
            >
              4. Discontinue Column
            </button>
          )}

          {!isTieBeams && (
            <button
              type="button"
              onClick={() => {
                setActiveTool('DRAW_HIDDEN_BEAM');
                setPendingStartColId(null);
              }}
              className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
                activeTool === 'DRAW_HIDDEN_BEAM'
                  ? 'bg-amber-600 text-white font-semibold'
                  : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
              }`}
            >
              5. + Hidden Beam (B#)
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              setActiveTool('DRAW_DROP_BEAM');
              setPendingStartColId(null);
            }}
            className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
              activeTool === 'DRAW_DROP_BEAM'
                ? 'bg-emerald-700 text-white font-semibold'
                : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
            }`}
          >
            6. + Drop Beam (B#)
          </button>

          {!isTieBeams && (
            <button
              type="button"
              onClick={() => setActiveTool('TOGGLE_RIB')}
              className={`text-left px-2.5 py-1.5 rounded text-xs font-medium transition ${
                activeTool === 'TOGGLE_RIB'
                  ? 'bg-yellow-600 text-white font-semibold'
                  : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
              }`}
            >
              7. Flip Rib Direction
            </button>
          )}

          <div className="mt-auto pt-2 border-t border-slate-800 flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
              <button
                type="button"
                onClick={() => setOsnapEnabled((v) => !v)}
                className={osnapEnabled ? 'text-emerald-400 font-bold' : 'text-slate-500'}
              >
                OSNAP:{osnapEnabled ? 'ON' : 'OFF'}
              </button>
              <button
                type="button"
                onClick={() => setOrthoEnabled((v) => !v)}
                className={orthoEnabled ? 'text-sky-400 font-bold' : 'text-slate-500'}
              >
                ORTHO:{orthoEnabled ? 'ON' : 'OFF'}
              </button>
            </div>

            {onExportDxf && (
              <button
                type="button"
                onClick={onExportDxf}
                className="w-full px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold text-center transition"
              >
                Save Story (.DXF)
              </button>
            )}
          </div>
        </div>

        {/* Interactive Dark CAD Canvas */}
        <div className="flex-1 bg-[#0D1117] p-2 flex flex-col justify-between">
          <svg
            direction="ltr"
            viewBox={`0 0 ${svgW} ${svgH}`}
            onMouseMove={handleSvgMouseMove}
            onClick={handleSvgClick}
            className="w-full h-auto bg-[#0D1117] rounded border border-slate-800 select-none cursor-crosshair"
            data-testid="cad-floorplan-svg"
          >
            {/* Architectural Reference Underlay Grid & Walls */}
            {showArchUnderlay &&
              [0, 5.2, 10.0].map((gx, i) => (
                <g key={`grid-v-${i}`}>
                  <line
                    x1={toX(gx)}
                    y1={25}
                    x2={toX(gx)}
                    y2={svgH - 20}
                    stroke="#1e293b"
                    strokeWidth="1"
                    strokeDasharray="6,4"
                  />
                  <circle cx={toX(gx)} cy={16} r={10} fill="#0f172a" stroke="#475569" strokeWidth="1" />
                  <text x={toX(gx)} y={20} textAnchor="middle" fontSize="10" fill="#94a3b8" fontWeight="bold">
                    {i + 1}
                  </text>
                </g>
              ))}

            {showArchUnderlay &&
              [0, 4.2, 8.5].map((gy, i) => {
                const labels = ['A', 'B', 'C'];
                return (
                  <g key={`grid-h-${i}`}>
                    <line
                      x1={35}
                      y1={toY(gy)}
                      x2={svgW - 20}
                      y2={toY(gy)}
                      stroke="#1e293b"
                      strokeWidth="1"
                      strokeDasharray="6,4"
                    />
                    <circle cx={20} cy={toY(gy)} r={10} fill="#0f172a" stroke="#475569" strokeWidth="1" />
                    <text x={20} y={toY(gy) + 4} textAnchor="middle" fontSize="10" fill="#94a3b8" fontWeight="bold">
                      {labels[i]}
                    </text>
                  </g>
                );
              })}

            {/* Outer Slab Boundary (00-XD-EDGE in Cyan) */}
            {!isTieBeams && (
              <polygon
                points={`${toX(-0.12)},${toY(8.62)} ${toX(11.4)},${toY(8.62)} ${toX(11.4)},${toY(4.08)} ${toX(10.12)},${toY(4.08)} ${toX(10.12)},${toY(-0.12)} ${toX(-0.12)},${toY(-0.12)}`}
                fill="#0f172a"
                fillOpacity={0.35}
                stroke="#06b6d4"
                strokeWidth="1.6"
              />
            )}

            {/* Opening / Shaft OP1 (00-XD-OPEN in Magenta) */}
            {!isTieBeams && (
              <g>
                <rect
                  x={toX(7.6)}
                  y={toY(8.5)}
                  width={(10.0 - 7.6) * scale}
                  height={(8.5 - 4.2) * scale}
                  fill="#1e1b4b"
                  fillOpacity={0.45}
                  stroke="#e879f9"
                  strokeWidth="1.5"
                />
                <line x1={toX(7.6)} y1={toY(8.5)} x2={toX(10.0)} y2={toY(4.2)} stroke="#e879f9" strokeWidth="1" />
                <line x1={toX(10.0)} y1={toY(8.5)} x2={toX(7.6)} y2={toY(4.2)} stroke="#e879f9" strokeWidth="1" />
                <text x={toX(8.8)} y={toY(6.35)} textAnchor="middle" fontSize="10" fill="#f0abfc" fontWeight="bold">
                  OP1 (Shaft)
                </text>
              </g>
            )}

            {/* One-Way Hollow-Block Rib Indicators (00-XD-SLAB) */}
            {!isTieBeams &&
              slabs.map((s, idx) => {
                const cx = idx === 0 ? 2.4 : idx === 1 ? 2.4 : 10.7;
                const cy = idx === 0 ? 6.35 : idx === 1 ? 2.1 : 6.35;
                const isVert = s.ribDirectionDeg === 90;
                return (
                  <g
                    key={s.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onToggleSlabRibDirection) onToggleSlabRibDirection(s.id);
                    }}
                    className="cursor-pointer"
                  >
                    {isVert ? (
                      <line
                        x1={toX(cx)}
                        y1={toY(cy - 1.0)}
                        x2={toX(cx)}
                        y2={toY(cy + 1.0)}
                        stroke="#facc15"
                        strokeWidth="2"
                      />
                    ) : (
                      <line
                        x1={toX(cx - 0.55)}
                        y1={toY(cy)}
                        x2={toX(cx + 0.55)}
                        y2={toY(cy)}
                        stroke="#facc15"
                        strokeWidth="2"
                      />
                    )}
                    <text
                      x={isVert ? toX(cx) + 8 : toX(cx)}
                      y={isVert ? toY(cy) : toY(cy) - 10}
                      textAnchor={isVert ? 'start' : 'middle'}
                      fontSize="9.5"
                      fill="#fde047"
                      fontWeight="bold"
                    >
                      {s.id} ({isVert ? '90° Y-Ribs' : '0° X-Ribs'})
                    </text>
                  </g>
                );
              })}

            {/* Beams (00-XD-BEAM-HID & 00-XD-BEAM-DROP) + Bright Orange Non-Overlapping Clear-Span Tags */}
            {beams.map((b) => {
              const isSelected = b.id === selectedBeamId;
              const isHidden = !isTieBeams && b.beamKind === 'hidden';
              const strokeColor = isSelected ? '#38bdf8' : isHidden ? '#eab308' : '#10b981';
              const strokeW = isHidden ? Math.max(7, b.widthM * scale * 0.42) : 4.5;

              const x1 = toX(b.startCoord.x);
              const y1 = toY(b.startCoord.y);
              const x2 = toX(b.endCoord.x);
              const y2 = toY(b.endCoord.y);

              const isVertical = Math.abs(b.endCoord.y - b.startCoord.y) > Math.abs(b.endCoord.x - b.startCoord.x);
              const firstSpanLen = b.spans[0] || 4.2;

              // Place Beam Tag B# at the midpoint of the FIRST CLEAR SPAN (strictly between columns, never on C2/C5!)
              const tagWorldX = isVertical
                ? b.startCoord.x - 0.35
                : b.startCoord.x + firstSpanLen * 0.5;
              const tagWorldY = isVertical
                ? b.startCoord.y + firstSpanLen * 0.5
                : b.startCoord.y + 0.32;

              const tagPxX = toX(tagWorldX);
              const tagPxY = toY(tagWorldY);

              return (
                <g
                  key={b.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectBeam(b.id);
                  }}
                  className="cursor-pointer"
                >
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={strokeColor}
                    strokeWidth={strokeW}
                    strokeDasharray={isHidden ? '8,4' : undefined}
                    strokeOpacity={isSelected ? 1.0 : 0.85}
                  />
                  {/* Non-overlapping Bright Orange Beam Tag (#FB923C) at First Clear-Span Midpoint */}
                  <rect
                    x={tagPxX - 34}
                    y={tagPxY - 10}
                    width={68}
                    height={18}
                    rx={3}
                    fill={isSelected ? '#0284c7' : '#1e1b18'}
                    stroke="#fb923c"
                    strokeWidth="1.3"
                  />
                  <text
                    x={tagPxX}
                    y={tagPxY + 3}
                    textAnchor="middle"
                    fontSize="10"
                    fontWeight="bold"
                    fill="#fb923c"
                  >
                    {b.id} ({isHidden ? 'Hid' : 'Drop'})
                  </text>
                </g>
              );
            })}

            {/* Columns (00-XD-COL) + Bright Green Tags (#4ADE80) Placed OUTSIDE Top-Right Corner */}
            {columns.map((c) => {
              const cx = toX(c.x);
              const cy = toY(c.y);
              const wPx = Math.max(12, c.bM * scale);
              const hPx = Math.max(16, c.hM * scale);
              const isStartPending = pendingStartColId === c.id;

              return (
                <g
                  key={c.id}
                  onClick={(e) => handleColumnClick(e, c.id)}
                  className="cursor-pointer"
                >
                  <rect
                    x={cx - wPx / 2}
                    y={cy - hPx / 2}
                    width={wPx}
                    height={hPx}
                    fill={c.activeInStory ? '#dc2626' : '#334155'}
                    fillOpacity={0.85}
                    stroke={isStartPending ? '#facc15' : c.activeInStory ? '#fca5a5' : '#64748b'}
                    strokeWidth={isStartPending ? '2.5' : '1.6'}
                  />
                  {/* Column Tag C# in Bright Green (#4ADE80) strictly outside the top-right corner */}
                  <text
                    x={cx + wPx / 2 + 6}
                    y={cy - hPx / 2 - 4}
                    fontSize="11"
                    fontWeight="bold"
                    fill={c.activeInStory ? '#4ade80' : '#94a3b8'}
                  >
                    {c.id}
                    {!c.activeInStory ? ' (Stopped)' : ''}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Bottom CAD Coordinate & OSNAP Readout Bar */}
          <div className="flex items-center justify-between px-2 pt-1.5 text-[11px] font-mono text-slate-400">
            <span>
              Cursor WCS: X = {cursorWorld.x.toFixed(2)} m , Y = {cursorWorld.y.toFixed(2)} m , Z = 0.00 m ($INSUNITS = 6 Meters)
            </span>
            <span>
              Columns: {columns.filter((c) => c.activeInStory).length} Active | Beams: {beams.length} | Click any beam to inspect diagrams
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
