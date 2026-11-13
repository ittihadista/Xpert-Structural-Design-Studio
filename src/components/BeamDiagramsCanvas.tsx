import React, { useState } from 'react';
import type { StructuralBeamModel, SlopeDeflectionResult } from '../engine/structuralEngine';

interface BeamDiagramsCanvasProps {
  beam: StructuralBeamModel;
  result: SlopeDeflectionResult;
}

const LOAD_PALETTE = [
  '#556b2f',
  '#795548',
  '#5f6a72',
  '#8b5e34',
  '#3b5323',
];

export const BeamDiagramsCanvas: React.FC<BeamDiagramsCanvasProps> = ({ beam, result }) => {
  const [hoverX, setHoverX] = useState<number | null>(null);

  const cLeft = beam.cantilevers.left || 0;
  const cRight = beam.cantilevers.right || 0;
  const totalLen = Math.max(0.5, cLeft + beam.spans.reduce((a, b) => a + b, 0) + cRight);

  const supportX: number[] = [cLeft];
  for (const sLen of beam.spans) {
    supportX.push(supportX[supportX.length - 1] + sLen);
  }

  const width = 920;
  const height = 630;
  const padLeft = 72;
  const padRight = 56;
  const plotW = width - padLeft - padRight;

  const xToPx = (xM: number) => padLeft + (xM / totalLen) * plotW;

  const yBeam = 126;
  const yShearZero = 320;
  const shearHalfH = 66;
  const yMomentZero = 510;
  const momentHalfH = 72;

  const maxV = Math.max(1, result.maxAbsShearKn);
  const maxM = Math.max(1, result.maxAbsMomentKnM);

  const vToPx = (vKn: number) => yShearZero - (vKn / maxV) * shearHalfH;
  // Positive Bending Moment (Sagging) plotted downward per structural engineering convention
  const mToPx = (mKnM: number) => yMomentZero + (mKnM / maxM) * momentHalfH;

  let hoverV = 0;
  let hoverM = 0;
  if (hoverX !== null && result.xFull.length > 0) {
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < result.xFull.length; i++) {
      const d = Math.abs(result.xFull[i] - hoverX);
      if (d < bestDist) {
        bestDist = d;
        bestIdx = i;
      }
    }
    hoverV = result.vFull[bestIdx] ?? 0;
    hoverM = result.mFull[bestIdx] ?? 0;
  }

  const shearPoints = result.xFull.map((x, idx) => `${xToPx(x).toFixed(1)},${vToPx(result.vFull[idx]).toFixed(1)}`);
  const shearPolygon =
    result.xFull.length > 1
      ? `${xToPx(0).toFixed(1)},${yShearZero} ` +
        shearPoints.join(' ') +
        ` ${xToPx(totalLen).toFixed(1)},${yShearZero}`
      : '';

  const momentPoints = result.xFull.map((x, idx) => `${xToPx(x).toFixed(1)},${mToPx(result.mFull[idx]).toFixed(1)}`);
  const momentPolygon =
    result.xFull.length > 1
      ? `${xToPx(0).toFixed(1)},${yMomentZero} ` +
        momentPoints.join(' ') +
        ` ${xToPx(totalLen).toFixed(1)},${yMomentZero}`
      : '';

  const hatchXs: number[] = [];
  const stepM = Math.max(totalLen / 42, 0.15);
  for (let xm = 0; xm <= totalLen + 1e-6; xm += stepM) {
    hatchXs.push(Math.min(xm, totalLen));
  }

  const distLoads = beam.loads.filter((l) => l.type === 'dist');
  const pointLoads = beam.loads.filter((l) => l.type === 'point');

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = width / rect.width;
    const svgX = (e.clientX - rect.left) * scaleX;
    const xm = ((svgX - padLeft) / plotW) * totalLen;
    if (xm >= 0 && xm <= totalLen) {
      setHoverX(Number(xm.toFixed(2)));
    } else {
      setHoverX(null);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded p-4 space-y-4">
      {/* Live Readout Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-slate-200">
        <div>
          <h4 className="text-sm font-bold text-slate-900">
            Beam Analysis Diagrams — {beam.id} ({beam.beamKind === 'hidden' ? 'Hidden Beam' : 'Drop Beam'}{' '}
            {Math.round(beam.widthM * 100)}×{Math.round(beam.depthM * 100)} cm)
          </h4>
          <p className="text-xs text-slate-500">
            Hover over diagram to inspect Shear & Moment at any section · Triangle (△) = Column Hinge Support · Double-Circle (△○○) = Supporting Beam Roller
          </p>
        </div>
        <div className="flex items-center gap-3 font-mono text-xs tabular-nums">
          <span className="px-2.5 py-1 bg-slate-100 rounded text-slate-800 font-semibold">
            X: {hoverX !== null ? `${hoverX.toFixed(2)} m` : '— m'}
          </span>
          <span className="px-2.5 py-1 bg-blue-50 text-blue-800 rounded font-semibold">
            V: {hoverX !== null ? `${hoverV.toFixed(2)} kN` : '— kN'}
          </span>
          <span className="px-2.5 py-1 bg-red-50 text-red-800 rounded font-semibold">
            M: {hoverX !== null ? `${hoverM.toFixed(2)} kN·m` : '— kN·m'}
          </span>
        </div>
      </div>

      <svg
        direction="ltr"
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto select-none cursor-crosshair border border-slate-100 rounded"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverX(null)}
        data-testid="beam-analysis-svg"
      >
        {supportX.map((sx, idx) => (
          <line
            key={`drop-sup-${idx}`}
            x1={xToPx(sx)}
            y1={50}
            x2={xToPx(sx)}
            y2={height - 20}
            stroke="#94a3b8"
            strokeWidth="1"
            strokeDasharray="3,3"
          />
        ))}

        {/* 1. BEAM ELEVATION, SUPPORTS (HINGE vs ROLLER), AND LOADS */}
        <text x={padLeft} y={24} textAnchor="start" fontSize="13" fontWeight="bold" fill="#003366">
          1. 1D Analytical Structural Model, Loads & Support Reactions ({beam.id})
        </text>

        {distLoads.map((dl, idx) => {
          const x1 = Math.max(0, dl.x1 ?? 0);
          const x2 = Math.min(totalLen, dl.x2 ?? totalLen);
          const px1 = xToPx(x1);
          const px2 = xToPx(x2);
          const col = LOAD_PALETTE[idx % LOAD_PALETTE.length];
          const boxH = 26 + idx * 14;
          const yTop = yBeam - boxH;
          return (
            <g key={dl.id}>
              <rect
                x={px1}
                y={yTop}
                width={Math.max(2, px2 - px1)}
                height={boxH}
                fill={col}
                fillOpacity={0.22}
                stroke={col}
                strokeWidth="1.5"
              />
              <text
                x={(px1 + px2) / 2}
                y={yTop - 5}
                textAnchor="middle"
                fontSize="10.5"
                fontWeight="bold"
                fill={col}
              >
                w = {dl.val.toFixed(1)} kN/m
              </text>
            </g>
          );
        })}

        {pointLoads.map((pl, idx) => {
          const px = xToPx(pl.x ?? 0);
          const isTransferred = pl.category === 'transferred_reaction';
          const col = isTransferred ? '#b91c1c' : '#15803d';
          return (
            <g key={pl.id || idx}>
              <line x1={px} y1={yBeam - 62} x2={px} y2={yBeam - 6} stroke={col} strokeWidth="2.5" />
              <polygon points={`${px},${yBeam - 2} ${px - 5},${yBeam - 12} ${px + 5},${yBeam - 12}`} fill={col} />
              <rect
                x={px - 65}
                y={yBeam - 84}
                width={130}
                height={18}
                rx={3}
                fill="#ffffff"
                stroke={col}
                strokeWidth="1"
              />
              <text x={px} y={yBeam - 71} textAnchor="middle" fontSize="10" fontWeight="bold" fill={col}>
                P = {pl.val.toFixed(1)} kN {isTransferred ? `(${pl.sourceLabel})` : ''}
              </text>
            </g>
          );
        })}

        <line
          x1={xToPx(0)}
          y1={yBeam}
          x2={xToPx(totalLen)}
          y2={yBeam}
          stroke="#0f172a"
          strokeWidth="4.5"
          strokeLinecap="round"
        />

        {supportX.map((sx, idx) => {
          const px = xToPx(sx);
          const sup = beam.supports[idx];
          const isBeamRoller = sup?.kind === 'beam';
          const supColor = isBeamRoller ? '#d97706' : '#003366';
          const rVal = result.reactions[idx + 1] ?? 0;

          return (
            <g key={`sup-node-${idx}`}>
              <polygon
                points={`${px},${yBeam + 2} ${px - 10},${yBeam + 18} ${px + 10},${yBeam + 18}`}
                fill={supColor}
              />
              {isBeamRoller ? (
                <>
                  <circle cx={px - 5} cy={yBeam + 22} r={3.2} fill="none" stroke={supColor} strokeWidth="1.6" />
                  <circle cx={px + 5} cy={yBeam + 22} r={3.2} fill="none" stroke={supColor} strokeWidth="1.6" />
                  <line x1={px - 12} y1={yBeam + 27} x2={px + 12} y2={yBeam + 27} stroke={supColor} strokeWidth="1.6" />
                </>
              ) : (
                <line x1={px - 12} y1={yBeam + 20} x2={px + 12} y2={yBeam + 20} stroke={supColor} strokeWidth="2" />
              )}

              <text
                x={px}
                y={yBeam + 40}
                textAnchor="middle"
                fontSize="10.5"
                fontWeight="bold"
                fill={supColor}
              >
                {sup ? `${sup.targetId} (${isBeamRoller ? 'Roller' : 'Hinge'})` : `S${idx + 1}`}
              </text>

              <text
                x={px}
                y={yBeam + 55}
                textAnchor="middle"
                fontSize="10"
                fontWeight="bold"
                fill="#15803d"
              >
                R{idx + 1}={rVal.toFixed(1)}kN
              </text>
            </g>
          );
        })}

        {beam.spans.map((sLen, idx) => {
          const midX = supportX[idx] + sLen / 2;
          return (
            <text
              key={`span-lbl-${idx}`}
              x={xToPx(midX)}
              y={yBeam + 15}
              textAnchor="middle"
              fontSize="10.5"
              fontWeight="bold"
              fill="#1e293b"
            >
              L{idx + 1} = {sLen.toFixed(2)}m
            </text>
          );
        })}

        {/* 2. SHEAR FORCE DIAGRAM (SFD - kN) */}
        <text x={padLeft} y={230} textAnchor="start" fontSize="12.5" fontWeight="bold" fill="#1f77b4">
          2. Shear Force Diagram — SFD (kN)
        </text>
        <line x1={padLeft} y1={yShearZero} x2={width - padRight} y2={yShearZero} stroke="#0f172a" strokeWidth="1.3" />
        {shearPolygon && (
          <polygon points={shearPolygon} fill="#1f77b4" fillOpacity={0.18} stroke="#1f77b4" strokeWidth="2" />
        )}
        {result.xFull.length > 1 &&
          hatchXs.map((hx, idx) => {
            const bIdx = Math.min(
              result.xFull.length - 1,
              Math.round((hx / totalLen) * (result.xFull.length - 1))
            );
            const vVal = result.vFull[bIdx] ?? 0;
            return (
              <line
                key={`sh-hatch-${idx}`}
                x1={xToPx(hx)}
                y1={yShearZero}
                x2={xToPx(hx)}
                y2={vToPx(vVal)}
                stroke="#1f77b4"
                strokeWidth="0.8"
                strokeOpacity={0.45}
              />
            );
          })}

        {/* 3. BENDING MOMENT DIAGRAM (BMD - kN.m) */}
        <text x={padLeft} y={422} textAnchor="start" fontSize="12.5" fontWeight="bold" fill="#d62728">
          3. Bending Moment Diagram — BMD (kN·m, Positive Sagging Plotted Downward)
        </text>
        <line x1={padLeft} y1={yMomentZero} x2={width - padRight} y2={yMomentZero} stroke="#0f172a" strokeWidth="1.3" />
        {momentPolygon && (
          <polygon points={momentPolygon} fill="#d62728" fillOpacity={0.18} stroke="#d62728" strokeWidth="2" />
        )}
        {result.xFull.length > 1 &&
          hatchXs.map((hx, idx) => {
            const bIdx = Math.min(
              result.xFull.length - 1,
              Math.round((hx / totalLen) * (result.xFull.length - 1))
            );
            const mVal = result.mFull[bIdx] ?? 0;
            return (
              <line
                key={`bm-hatch-${idx}`}
                x1={xToPx(hx)}
                y1={yMomentZero}
                x2={xToPx(hx)}
                y2={mToPx(mVal)}
                stroke="#d62728"
                strokeWidth="0.8"
                strokeOpacity={0.45}
              />
            );
          })}

        {supportX.map((sx, idx) => {
          const mSup = result.supportMoments[idx + 1] ?? 0;
          if (Math.abs(mSup) < 0.05) return null;
          return (
            <text
              key={`bmd-sup-${idx}`}
              x={xToPx(sx)}
              y={mToPx(mSup) - 7}
              textAnchor="middle"
              fontSize="10"
              fontWeight="bold"
              fill="#b91c1c"
            >
              {mSup.toFixed(2)}
            </text>
          );
        })}

        {result.maxPositiveMoments.map((mp) => {
          if (mp.maxMomentKnM <= 0.05) return null;
          return (
            <g key={`bmd-pos-${mp.spanIndex}`}>
              <circle cx={xToPx(mp.xGlobalM)} cy={mToPx(mp.maxMomentKnM)} r={3.5} fill="#d62728" />
              <text
                x={xToPx(mp.xGlobalM)}
                y={mToPx(mp.maxMomentKnM) + 15}
                textAnchor="middle"
                fontSize="10"
                fontWeight="bold"
                fill="#d62728"
              >
                +{mp.maxMomentKnM.toFixed(2)} kN·m (x={mp.xGlobalM.toFixed(2)}m)
              </text>
            </g>
          );
        })}

        {hoverX !== null && (
          <line
            x1={xToPx(hoverX)}
            y1={45}
            x2={xToPx(hoverX)}
            y2={height - 20}
            stroke="#0f172a"
            strokeWidth="1.2"
            strokeDasharray="4,2"
          />
        )}
      </svg>

      {/* Critical Forces Summary Table at Support Centerlines & Faces of Support */}
      <div className="border border-slate-200 rounded overflow-hidden">
        <div className="bg-slate-100 px-3 py-2 text-xs font-bold text-slate-800 border-b border-slate-200">
          Critical Design Forces at Support Centerlines & Faces of Support ({beam.id})
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono tabular-nums">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600">
              <tr>
                <th className="px-3 py-2">Support Node</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Position X (m)</th>
                <th className="px-3 py-2">Reaction Ru (kN)</th>
                <th className="px-3 py-2">Centerline -Mu (kN·m)</th>
                <th className="px-3 py-2 text-rose-700 font-bold">Face of Support -Mu (kN·m)</th>
                <th className="px-3 py-2 text-blue-700 font-bold">Face of Support Vu (kN)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {result.supportCriticalTable.map((row) => (
                <tr key={row.supportIndex} className="hover:bg-slate-50">
                  <td className="px-3 py-1.5 font-bold text-slate-900">
                    #{row.supportIndex} ({row.targetId})
                  </td>
                  <td className="px-3 py-1.5">
                    {row.kind === 'column' ? 'Column (Hinge △)' : 'Beam (Roller △○○)'}
                  </td>
                  <td className="px-3 py-1.5">{row.xM.toFixed(2)}</td>
                  <td className="px-3 py-1.5 font-semibold text-emerald-700">{row.reactionRuKn.toFixed(2)}</td>
                  <td className="px-3 py-1.5">{row.centerlineNegMuKnM.toFixed(2)}</td>
                  <td className="px-3 py-1.5 font-bold text-rose-700">{row.faceNegMuKnM.toFixed(2)}</td>
                  <td className="px-3 py-1.5 font-bold text-blue-700">{row.faceVuKn.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
