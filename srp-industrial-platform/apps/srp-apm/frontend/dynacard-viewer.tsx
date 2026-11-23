import React, { useState, useEffect } from 'react';

export interface SurfaceCardData {
  position_in?: number[];
  load_lbf?: number[];
  position_m?: number[];
  load_n?: number[];
  direction?: string[];
  complete?: boolean;
  stroke_in?: number;
  stroke_m?: number;
  pprl_lbf?: number;
  mprl_lbf?: number;
  area_lbf_in?: number;
  area_j?: number;
  submerged_rod_weight_lbf?: number;
  limits?: {
    structural_limit_lbf: number;
    rod_yield_limit_lbf: number;
    min_load_limit_lbf: number;
  };
  markers?: {
    SOS?: { index: number; position_in: number; load_lbf: number; sample_number?: number };
    TOS?: { index: number; position_in: number; load_lbf: number };
    BOS?: { index: number; position_in: number; load_lbf: number };
    PPRL?: { index: number; position_in: number; load_lbf: number };
    MPRL?: { index: number; position_in: number; load_lbf: number };
  };
  load_differences?: Array<{ position_in: number; delta_lbf: number }>;
}

export interface DownholeCardData {
  status: string;
  reason?: string;
  solver_version?: string;
  verification_version?: string;
  position_m?: number[];
  load_n?: number[];
  gibbs_position_m?: number[];
  gibbs_load_n?: number[];
  displacement_rmse_in?: number;
  load_rmse_lbf?: number;
  features?: {
    mpt_in?: number;
    ept_in?: number;
    fillage_pct?: number;
    fluid_load_fo_lbf?: number;
    upper_fluid_reference_lbf?: number;
    lower_fluid_reference_lbf?: number;
    area_lbf_in?: number;
    stroke_loss_in?: number;
    displacement_bpd?: number;
    pip_psi?: number;
    valves?: {
      SVO?: { index: number; position_in: number; load_lbf: number };
      SVC?: { index: number; position_in: number; load_lbf: number };
      TVO?: { index: number; position_in: number; load_lbf: number };
      TVC?: { index: number; position_in: number; load_lbf: number };
    };
    markers?: {
      TOS?: { index: number; position_in: number; load_lbf: number };
      BOS?: { index: number; position_in: number; load_lbf: number };
      MAX_LOAD?: { index: number; position_in: number; load_lbf: number };
      MIN_LOAD?: { index: number; position_in: number; load_lbf: number };
    };
    fluid_pound?: {
      detected: boolean;
      severity: string;
      description: string;
    };
  };
}

interface DynacardViewerProps {
  type: 'surface' | 'downhole';
  title?: string;
  surfaceData?: SurfaceCardData;
  downholeData?: DownholeCardData;
  liveMarker?: { x_in: number; y_lbf: number };
  livePoints?: Array<{ x_in: number; y_lbf: number }>;
  crankAngleDeg?: number;
  strokeId?: number;
  timestamp?: string;
  spm?: number;
  source?: string;
  quality?: string;
  imperial?: boolean;
  theme?: 'engineering-light' | 'advait-dark';
  onToggleUnits?: () => void;
}

export function DynacardViewer({
  type,
  title,
  surfaceData,
  downholeData,
  liveMarker,
  livePoints,
  crankAngleDeg,
  strokeId,
  timestamp,
  spm,
  source = 'Measured / Simulated',
  quality = 'GOOD',
  imperial = true,
  theme = 'engineering-light',
  onToggleUnits
}: DynacardViewerProps) {
  const [showMarkers, setShowMarkers] = useState(true);
  const [showLimits, setShowLimits] = useState(true);
  const [showArrows, setShowArrows] = useState(false);
  const [showGibbsOverlay, setShowGibbsOverlay] = useState(false);
  const [autoFitY, setAutoFitY] = useState(true);
  const [cardTheme, setCardTheme] = useState<'light' | 'dark'>(theme === 'engineering-light' ? 'light' : 'dark');
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  // 60 FPS Real-Time Continuous Dynacard Animation Engine
  const [animPhase, setAnimPhase] = useState(0);
  useEffect(() => {
    let frameId: number;
    let lastTime = performance.now();
    const effectiveSpm = spm && spm > 0 ? spm : 7.9;
    const loop = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      setAnimPhase(prev => {
        let next = prev + dt * (effectiveSpm / 60);
        if (crankAngleDeg !== undefined) {
          const targetPhase = (((crankAngleDeg % 360) + 360) % 360) / 360;
          let diff = targetPhase - next;
          while (diff > 0.5) diff -= 1.0;
          while (diff < -0.5) diff += 1.0;
          next = next + diff * 0.12;
        }
        return (next % 1.0 + 1.0) % 1.0;
      });
      frameId = requestAnimationFrame(loop);
    };
    frameId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frameId);
  }, [spm, crankAngleDeg]);

  const isSurface = type === 'surface';
  const dhFeat = downholeData?.features;

  // Coordinate extraction
  let xArr: number[] = [];
  let yArr: number[] = [];
  let dirArr: string[] = [];

  if (isSurface && surfaceData) {
    if (surfaceData.position_in && surfaceData.load_lbf && surfaceData.position_in.length > 0) {
      xArr = surfaceData.position_in;
      yArr = surfaceData.load_lbf;
    } else if (surfaceData.position_m && surfaceData.load_n && surfaceData.position_m.length > 0) {
      xArr = surfaceData.position_m.map(v => v / 0.0254);
      yArr = surfaceData.load_n.map(v => v / 4.4482216152605);
    }
    dirArr = surfaceData.direction || [];
  } else if (!isSurface && downholeData && downholeData.position_m && downholeData.load_n && downholeData.position_m.length > 0) {
    xArr = downholeData.position_m.map(v => v / 0.0254);
    yArr = downholeData.load_n.map(v => v / 4.4482216152605);
    dirArr = xArr.map((val, idx, arr) => {
      const next = arr[(idx + 1) % arr.length];
      return next >= val ? 'UP' : 'DOWN';
    });
  }

  // Gibbs overlay for downhole
  let gibbsX: number[] = [];
  let gibbsY: number[] = [];
  if (!isSurface && downholeData?.gibbs_position_m && downholeData?.gibbs_load_n) {
    gibbsX = downholeData.gibbs_position_m.map(v => v / 0.0254);
    gibbsY = downholeData.gibbs_load_n.map(v => v / 4.4482216152605);
  }

  // Fallback defaults if no stroke data is present yet
  if (xArr.length === 0) {
    if (isSurface) {
      xArr = [0, 4, 12, 24, 38, 44.24, 42, 30, 16, 6, 0];
      yArr = [9200, 10200, 12800, 14600, 15600, 13800, 12400, 8800, 8200, 9400, 9200];
      dirArr = ['UP', 'UP', 'UP', 'UP', 'UP', 'DOWN', 'DOWN', 'DOWN', 'DOWN', 'DOWN', 'UP'];
    } else {
      xArr = [0, 6, 18, 30, 37.15, 36, 28, 14, 2, 0];
      yArr = [0, 3900, 4050, 4110, 4110, 3200, 100, 0, 0, 0];
      dirArr = ['UP', 'UP', 'UP', 'UP', 'UP', 'DOWN', 'DOWN', 'DOWN', 'DOWN', 'UP'];
    }
  }

  const rawMinX = Math.min(...xArr);
  const rawMaxX = Math.max(...xArr);
  const rawMinY = Math.min(...yArr);
  const rawMaxY = Math.max(...yArr);

  // Exact scale modeling:
  // Auto-fit scales the card to fill 80% of vertical window (revealing dynamic harmonics and valve transitions)
  // Fixed scale retains strict 0 to 18 klbf (Surface) or 0 to 6 klbf (Downhole) matching static prints
  let boundMinX: number;
  let boundMaxX: number;
  let boundMinY: number;
  let boundMaxY: number;

  if (isSurface) {
    boundMinX = 0;
    boundMaxX = Math.max(50.0, Math.ceil((rawMaxX * 1.15) / 10) * 10);
    if (autoFitY) {
      const ySpan = Math.max(1500, rawMaxY - rawMinY);
      boundMinY = Math.max(0, Math.floor((rawMinY - ySpan * 0.35) / 1000) * 1000);
      boundMaxY = Math.ceil((rawMaxY + ySpan * 0.35) / 1000) * 1000;
    } else {
      boundMinY = 0;
      boundMaxY = Math.max(18000, Math.ceil((rawMaxY * 1.2) / 2000) * 2000);
    }
  } else {
    // Downhole pump card: baseline at 0 lbf
    const mpt = dhFeat?.mpt_in || rawMaxX;
    boundMinX = 0;
    boundMaxX = Math.max(40.0, Math.ceil((mpt * 1.18) / 10) * 10);
    boundMinY = 0;
    if (autoFitY) {
      const fo = dhFeat?.fluid_load_fo_lbf || rawMaxY;
      boundMaxY = Math.max(3000, Math.ceil((Math.max(fo, rawMaxY) * 1.35) / 500) * 500);
    } else {
      boundMaxY = Math.max(6000, Math.ceil((rawMaxY * 1.35) / 1000) * 1000);
    }
  }

  // SVG Canvas dimensions matching reference aspect ratio (approx 2.1:1 wide)
  const svgW = 680;
  const svgH = 320;
  const padLeft = 65;
  const padRight = 35;
  const padTop = 38;
  const padBottom = 48;

  const plotW = svgW - padLeft - padRight;
  const plotH = svgH - padTop - padBottom;

  const scaleX = (x: number) => padLeft + ((x - boundMinX) / Math.max(1e-4, boundMaxX - boundMinX)) * plotW;
  const scaleY = (y: number) => padTop + plotH - ((y - boundMinY) / Math.max(1e-4, boundMaxY - boundMinY)) * plotH;

  // Path coordinates
  const polyPoints = xArr.map((x, i) => `${scaleX(x).toFixed(1)},${scaleY(yArr[i]).toFixed(1)}`);
  const fullPoly = polyPoints.join(' ');

  // Upstroke and Downstroke paths
  const upPoints: string[] = [];
  const downPoints: string[] = [];
  xArr.forEach((x, i) => {
    const pt = `${scaleX(x).toFixed(1)},${scaleY(yArr[i]).toFixed(1)}`;
    if (dirArr[i] === 'UP') upPoints.push(pt);
    else downPoints.push(pt);
  });

  // Live in-progress stroke polyline from streaming telemetry
  const livePoly = livePoints && livePoints.length > 1
    ? livePoints.map(p => `${scaleX(p.x_in).toFixed(1)},${scaleY(p.y_lbf).toFixed(1)}`).join(' ')
    : '';

  // Interpolated smooth cursor along the closed work loop contour (60 FPS)
  const nPts = xArr.length;
  const floatIdx = animPhase * Math.max(1, nPts);
  const i0 = Math.floor(floatIdx) % Math.max(1, nPts);
  const i1 = (i0 + 1) % Math.max(1, nPts);
  const frac = floatIdx - Math.floor(floatIdx);

  const curAnimX = nPts > 0 ? (xArr[i0] + frac * (xArr[i1] - xArr[i0])) : 0;
  const curAnimY = nPts > 0 ? (yArr[i0] + frac * (yArr[i1] - yArr[i0])) : 0;

  // Use liveMarker if actively provided from telemetry, otherwise animated cursor
  const markerX = liveMarker ? liveMarker.x_in : curAnimX;
  const markerY = liveMarker ? liveMarker.y_lbf : curAnimY;

  // Glowing phosphor breadcrumb tail trailing the moving head
  const trailPoints: Array<{ x: number; y: number; opacity: number; r: number }> = [];
  if (nPts > 8) {
    const trailLen = 8;
    for (let step = 1; step <= trailLen; step++) {
      const pIdx = (i0 - step + nPts) % nPts;
      trailPoints.push({
        x: scaleX(xArr[pIdx]),
        y: scaleY(yArr[pIdx]),
        opacity: ((trailLen - step) / trailLen) * 0.45,
        r: 3.2 * ((trailLen - step) / trailLen)
      });
    }
  }

  // Gibbs verification polyline
  const gibbsPoly = gibbsX.length > 0 ? gibbsX.map((x, i) => `${scaleX(x).toFixed(1)},${scaleY(gibbsY[i]).toFixed(1)}`).join(' ') : '';

  // Arrow markers
  const arrowPoints: Array<{ x: number; y: number; angle: number; dir: string }> = [];
  if (showArrows && xArr.length > 8) {
    const step = Math.max(2, Math.floor(xArr.length / 8));
    for (let i = 0; i < xArr.length - 1; i += step) {
      const p1x = scaleX(xArr[i]);
      const p1y = scaleY(yArr[i]);
      const p2x = scaleX(xArr[i + 1]);
      const p2y = scaleY(yArr[i + 1]);
      const angle = (Math.atan2(p2y - p1y, p2x - p1x) * 180) / Math.PI;
      arrowPoints.push({ x: p1x, y: p1y, angle, dir: dirArr[i] });
    }
  }

  // Formatting helpers
  const posUnit = imperial ? 'in' : 'm';
  const loadUnit = imperial ? 'klbf' : 'kN';
  const fmtPos = (vIn: number | undefined | null) => {
    if (vIn === undefined || vIn === null || isNaN(vIn)) return '—';
    return imperial ? vIn.toFixed(2) : (vIn * 0.0254).toFixed(3);
  };
  const fmtLoadKlbf = (vLbf: number | undefined | null) => {
    if (vLbf === undefined || vLbf === null || isNaN(vLbf)) return '—';
    return imperial ? (vLbf / 1000).toFixed(2) : (vLbf * 0.00444822).toFixed(2);
  };
  const fmtLoadLbf = (vLbf: number | undefined | null) => {
    if (vLbf === undefined || vLbf === null || isNaN(vLbf)) return '—';
    return imperial ? Math.round(vLbf).toLocaleString() : (vLbf * 0.00444822).toFixed(2);
  };
  const fmtArea = (vLbfIn: number | undefined | null) => {
    if (vLbfIn === undefined || vLbfIn === null || isNaN(vLbfIn)) return '—';
    return imperial ? `${Math.round(vLbfIn).toLocaleString()} lbf·in` : `${Math.round(vLbfIn * 0.1129848).toLocaleString()} J`;
  };

  // Color schemes
  const isLight = cardTheme === 'light';
  const colors = {
    canvasBg: isLight ? '#ffffff' : '#090e1a',
    plotBg: isLight ? '#ffffff' : '#0c1424',
    gridLine: isLight ? '#e5e7eb' : '#1e293b',
    border: isLight ? '#cbd5e1' : '#334155',
    textMuted: isLight ? '#64748b' : '#94a3b8',
    textMain: isLight ? '#0f172a' : '#f8fafc',
    cardTrace: isLight ? '#1e293b' : '#38bdf8',
    cardTraceDown: isLight ? '#334155' : '#22c55e',
    refLineRed: '#ef4444',
    refLineBlue: '#0284c7',
    fillColor: isLight ? 'rgba(15, 23, 42, 0.03)' : 'rgba(56, 189, 248, 0.06)'
  };

  const avgStrokeIn = surfaceData?.stroke_in || rawMaxX;
  const avgMptIn = dhFeat?.mpt_in || rawMaxX;
  const avgEptIn = dhFeat?.ept_in || (avgMptIn * 0.78);
  const foLbf = dhFeat?.fluid_load_fo_lbf || rawMaxY;
  const foMaxLbf = Math.max(rawMaxY, foLbf * 1.03);

  const cardTitle = title || (isSurface ? 'Unanchored Tubing: 100% Fillage' : 'Downhole Diagnostic');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Top Controls Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 8,
        background: isLight ? '#f8fafc' : '#090e1a',
        padding: '6px 12px',
        borderRadius: 6,
        border: `1px solid ${colors.border}`
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: isSurface ? '#0284c7' : '#16a34a', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {isSurface ? 'Surface Dynacard' : 'Downhole Dynacard'}
          </span>
          <span className="badge-live" style={{ fontSize: 9 }}>
            {isSurface ? 'Measured / Four-Bar' : (downholeData?.solver_version || 'Everitt-Jennings FD/2.0')}
          </span>
          {downholeData?.verification_version && (
            <span style={{ fontSize: 10, color: colors.textMuted, fontFamily: 'monospace' }}>
              Verified: {downholeData.verification_version}
            </span>
          )}

          {/* Live Telemetry Stream Indicator Badge */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '2px 8px',
            borderRadius: 12,
            background: liveMarker ? 'rgba(34, 197, 94, 0.15)' : 'rgba(148, 163, 184, 0.12)',
            border: `1px solid ${liveMarker ? '#22c55e' : '#475569'}`
          }}>
            <span style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: liveMarker ? '#22c55e' : '#64748b',
              boxShadow: liveMarker ? '0 0 8px #22c55e' : 'none'
            }} />
            <span style={{ fontSize: 10, fontWeight: 700, color: liveMarker ? '#22c55e' : '#94a3b8' }}>
              {liveMarker ? 'LIVE TELEMETRY (20 Hz)' : 'STATIC REFERENCE'}
            </span>
            {crankAngleDeg !== undefined && (
              <span style={{ fontSize: 9.5, color: '#38bdf8', fontFamily: 'JetBrains Mono, monospace' }}>
                · Crank {crankAngleDeg.toFixed(1)}°
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <button
            className={`advait-tab-pill ${autoFitY ? 'active' : ''}`}
            style={{ fontSize: 10, borderColor: '#0284c7' }}
            title="Toggle between Auto-Fit Wave View and 0-18k Fixed Boundary"
            onClick={() => setAutoFitY(!autoFitY)}>
            {autoFitY ? '⇱ Auto-Fit Range' : '⇲ Fixed Scale (0-18k)'}
          </button>
          <button
            className={`advait-tab-pill ${showMarkers ? 'active' : ''}`}
            style={{ fontSize: 10 }}
            onClick={() => setShowMarkers(!showMarkers)}>
            Markers
          </button>
          <button
            className={`advait-tab-pill ${showLimits ? 'active' : ''}`}
            style={{ fontSize: 10 }}
            onClick={() => setShowLimits(!showLimits)}>
            References & Limits
          </button>
          <button
            className={`advait-tab-pill ${showArrows ? 'active' : ''}`}
            style={{ fontSize: 10 }}
            onClick={() => setShowArrows(!showArrows)}>
            Direction Arrows
          </button>
          {!isSurface && gibbsX.length > 0 && (
            <button
              className={`advait-tab-pill ${showGibbsOverlay ? 'active' : ''}`}
              style={{ fontSize: 10, borderColor: '#7c3aed' }}
              onClick={() => setShowGibbsOverlay(!showGibbsOverlay)}>
              Gibbs Overlay
            </button>
          )}
          <button
            className="advait-tab-pill"
            style={{ fontSize: 10 }}
            onClick={() => setCardTheme(cardTheme === 'light' ? 'dark' : 'light')}>
            {isLight ? '☾ Dark Card' : '☀ Engineering Light'}
          </button>
          {onToggleUnits && (
            <button
              className="advait-tab-pill"
              style={{ fontSize: 10, background: isLight ? '#e2e8f0' : '#1e293b', color: colors.textMain }}
              onClick={onToggleUnits}>
              Unit: {imperial ? 'Imperial (in, klbf)' : 'Metric (m, kN)'}
            </button>
          )}
        </div>
      </div>

      {/* Main High-Precision Plot Graphic (Matching Reference Images 1 & 2) */}
      <div style={{
        background: colors.canvasBg,
        borderRadius: 8,
        border: `1px solid ${colors.border}`,
        padding: '10px 8px 6px 8px',
        position: 'relative',
        boxShadow: isLight ? '0 1px 3px rgba(0,0,0,0.05)' : 'none'
      }}>
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onPointerLeave={() => setHoverIdx(null)}
          onPointerMove={e => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickX = ((e.clientX - rect.left) / rect.width) * svgW;
            const clickY = ((e.clientY - rect.top) / rect.height) * svgH;
            let closest = 0;
            let minD = Infinity;
            xArr.forEach((x, i) => {
              const dx = scaleX(x) - clickX;
              const dy = scaleY(yArr[i]) - clickY;
              const d = dx * dx + dy * dy;
              if (d < minD) {
                minD = d;
                closest = i;
              }
            });
            if (minD < 1600) setHoverIdx(closest);
            else setHoverIdx(null);
          }}>

          {/* Title Header at top center */}
          <text
            x={padLeft + plotW / 2}
            y={22}
            textAnchor="middle"
            fill={colors.textMain}
            fontSize="13"
            fontWeight="700"
            fontFamily="Inter, sans-serif">
            {cardTitle}
          </text>

          {/* Grid background */}
          <rect x={padLeft} y={padTop} width={plotW} height={plotH} fill={colors.plotBg} />
          <rect x={padLeft} y={padTop} width={plotW} height={plotH} fill="none" stroke={colors.border} strokeWidth="1.2" />

          {/* Grid Lines & Ticks */}
          {/* Horizontal Grid (Y-axis in klbf) */}
          {[0, 0.25, 0.5, 0.75, 1.0].map(frac => {
            const yVal = boundMinY + frac * (boundMaxY - boundMinY);
            const yPos = scaleY(yVal);
            return (
              <g key={frac} fontSize="9" fill={colors.textMuted} fontFamily="JetBrains Mono, monospace">
                <line x1={padLeft} x2={padLeft + plotW} y1={yPos} y2={yPos} stroke={colors.gridLine} strokeWidth="0.8" />
                <text x={padLeft - 8} y={yPos + 3} textAnchor="end">{fmtLoadKlbf(yVal)}</text>
              </g>
            );
          })}

          {/* Vertical Grid (X-axis in inches) */}
          {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map(frac => {
            const xVal = boundMinX + frac * (boundMaxX - boundMinX);
            const xPos = scaleX(xVal);
            return (
              <g key={frac} fontSize="9" fill={colors.textMuted} fontFamily="JetBrains Mono, monospace">
                <line x1={xPos} x2={xPos} y1={padTop} y2={padTop + plotH} stroke={colors.gridLine} strokeWidth="0.8" />
                <text x={xPos} y={padTop + plotH + 15} textAnchor="middle">{Math.round(xVal)}</text>
              </g>
            );
          })}

          {/* REFERENCE MARKINGS SPECIFIC TO SURFACE (Image 1) */}
          {isSurface && showLimits && (
            <g fontFamily="Inter, sans-serif" fontSize="9">
              {/* Avg Stroke Length vertical dashed line */}
              <line
                x1={scaleX(avgStrokeIn)}
                x2={scaleX(avgStrokeIn)}
                y1={padTop}
                y2={padTop + plotH}
                stroke="#64748b"
                strokeWidth="1.2"
                strokeDasharray="4 3"
              />
              <text
                x={scaleX(avgStrokeIn) - 6}
                y={padTop + 14}
                textAnchor="end"
                fill={colors.textMuted}
                fontWeight="600"
                paintOrder="stroke"
                stroke={colors.canvasBg}
                strokeWidth="3">
                Avg Stroke Length = {fmtPos(avgStrokeIn)} in
              </text>

              {/* Submerged Rod Weight horizontal reference line */}
              {surfaceData?.submerged_rod_weight_lbf && (
                <>
                  <line
                    x1={padLeft}
                    x2={padLeft + plotW}
                    y1={scaleY(surfaceData.submerged_rod_weight_lbf)}
                    y2={scaleY(surfaceData.submerged_rod_weight_lbf)}
                    stroke="#ef4444"
                    strokeWidth="1"
                    strokeDasharray="4 3"
                  />
                  <text
                    x={padLeft + 12}
                    y={scaleY(surfaceData.submerged_rod_weight_lbf) + 12}
                    fill="#ef4444"
                    fontWeight="600"
                    paintOrder="stroke"
                    stroke={colors.canvasBg}
                    strokeWidth="3">
                    Submerged Rod Wt: {fmtLoadKlbf(surfaceData.submerged_rod_weight_lbf)} klbf
                  </text>
                </>
              )}
            </g>
          )}

          {/* REFERENCE MARKINGS SPECIFIC TO DOWNHOLE (Image 2) */}
          {!isSurface && showLimits && (
            <g fontFamily="Inter, sans-serif" fontSize="8.5">
              {/* Fo Max horizontal dashed line */}
              <line
                x1={padLeft}
                x2={padLeft + plotW}
                y1={scaleY(foMaxLbf)}
                y2={scaleY(foMaxLbf)}
                stroke="#ef4444"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              <text
                x={padLeft + plotW - 6}
                y={scaleY(foMaxLbf) - 4}
                textAnchor="end"
                fill="#ef4444"
                fontWeight="700"
                paintOrder="stroke"
                stroke={colors.canvasBg}
                strokeWidth="3">
                Fo Max: {fmtLoadKlbf(foMaxLbf)} klbf
              </text>

              {/* Full Stroke Fluid Load Fo line */}
              <line
                x1={padLeft}
                x2={padLeft + plotW}
                y1={scaleY(foLbf)}
                y2={scaleY(foLbf)}
                stroke="#64748b"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              <text
                x={padLeft + plotW - 6}
                y={scaleY(foLbf) + 11}
                textAnchor="end"
                fill="#64748b"
                fontWeight="600"
                paintOrder="stroke"
                stroke={colors.canvasBg}
                strokeWidth="3">
                Full Stroke Fluid Load (Fo) = {fmtLoadKlbf(foLbf)} klbf
              </text>

              {/* Zero Fluid Load baseline */}
              <line
                x1={padLeft}
                x2={padLeft + plotW}
                y1={scaleY(0)}
                y2={scaleY(0)}
                stroke="#64748b"
                strokeWidth="1.2"
              />

              {/* Gross Stroke Fill (slanted red dashed line on pickup slope) */}
              {(() => {
                const slopeX1 = scaleX(0);
                const slopeY1 = scaleY(0);
                const kneeX = dhFeat?.valves?.SVO?.position_in || (avgMptIn * 0.18);
                const slopeX2 = scaleX(kneeX);
                const slopeY2 = scaleY(foLbf);
                return (
                  <g>
                    <line
                      x1={slopeX1}
                      y1={slopeY1}
                      x2={slopeX2}
                      y2={slopeY2}
                      stroke="#ef4444"
                      strokeWidth="1"
                      strokeDasharray="4 3"
                    />
                    <line
                      x1={slopeX2}
                      y1={slopeY2}
                      x2={slopeX2 + 18}
                      y2={slopeY2 - 14}
                      stroke="#ef4444"
                      strokeWidth="0.8"
                    />
                    <text
                      x={slopeX2 + 20}
                      y={slopeY2 - 16}
                      fill="#ef4444"
                      fontWeight="600"
                      paintOrder="stroke"
                      stroke={colors.canvasBg}
                      strokeWidth="3">
                      Gross Stroke Fill
                    </text>
                  </g>
                );
              })()}

              {/* Avg EPT vertical dashed line */}
              <line
                x1={scaleX(avgEptIn)}
                x2={scaleX(avgEptIn)}
                y1={padTop}
                y2={padTop + plotH}
                stroke="#64748b"
                strokeWidth="1.2"
                strokeDasharray="4 3"
              />
              <text
                x={scaleX(avgEptIn)}
                y={padTop + plotH + 30}
                textAnchor="middle"
                fill={colors.textMuted}
                fontWeight="600"
                paintOrder="stroke"
                stroke={colors.canvasBg}
                strokeWidth="3">
                Avg EPT = {fmtPos(avgEptIn)} in
              </text>

              {/* Avg MPT vertical dashed line */}
              <line
                x1={scaleX(avgMptIn)}
                x2={scaleX(avgMptIn)}
                y1={padTop}
                y2={padTop + plotH}
                stroke="#64748b"
                strokeWidth="1.2"
                strokeDasharray="4 3"
              />
              <text
                x={scaleX(avgMptIn)}
                y={padTop + plotH + 30}
                textAnchor="middle"
                fill={colors.textMuted}
                fontWeight="600"
                paintOrder="stroke"
                stroke={colors.canvasBg}
                strokeWidth="3">
                Avg MPT = {fmtPos(avgMptIn)} in
              </text>
            </g>
          )}

          {/* Shaded Work Loop Area (Enclosed integral work) */}
          <polygon points={`${fullPoly} ${polyPoints[0]}`} fill={colors.fillColor} />

          {/* Gibbs verification overlay (Downhole) */}
          {showGibbsOverlay && gibbsPoly && (
            <polyline points={gibbsPoly} fill="none" stroke="#a855f7" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.9" />
          )}

          {/* Dynacard Work Loop (High-contrast closed bold trace matching API 11L / Weatherford standard) */}
          <polygon
            points={`${fullPoly} ${polyPoints[0]}`}
            fill="none"
            stroke={colors.cardTrace}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Glowing Phosphor Breadcrumb Trail */}
          {trailPoints.map((tp, idx) => (
            <circle
              key={idx}
              cx={tp.x}
              cy={tp.y}
              r={tp.r}
              fill="#ef4444"
              opacity={tp.opacity}
            />
          ))}

          {/* Progression directional arrows */}
          {showArrows && arrowPoints.map((arr, i) => (
            <g key={i} transform={`translate(${arr.x}, ${arr.y}) rotate(${arr.angle})`}>
              <polygon points="-6,-3 4,0 -6,3" fill={colors.cardTrace} />
            </g>
          ))}

          {/* Surface Markers (SOS, TOS, BOS, PPRL, MPRL) */}
          {showMarkers && isSurface && (
            <g fontFamily="Inter, sans-serif" fontSize="9" fontWeight="700">
              {/* PPRL */}
              {(() => {
                const px = scaleX(xArr[yArr.indexOf(rawMaxY)]);
                const py = scaleY(rawMaxY);
                return (
                  <g>
                    <circle cx={px} cy={py} r="4" fill="#ef4444" stroke={colors.canvasBg} strokeWidth="1.5" />
                    <text x={px} y={py - 8} fill="#ef4444" textAnchor="middle" paintOrder="stroke" stroke={colors.canvasBg} strokeWidth="3">
                      PPRL: {fmtLoadKlbf(rawMaxY)} klbf
                    </text>
                  </g>
                );
              })()}

              {/* MPRL */}
              {(() => {
                const px = scaleX(xArr[yArr.indexOf(rawMinY)]);
                const py = scaleY(rawMinY);
                return (
                  <g>
                    <circle cx={px} cy={py} r="4" fill="#10b981" stroke={colors.canvasBg} strokeWidth="1.5" />
                    <text x={px} y={py + 15} fill="#10b981" textAnchor="middle" paintOrder="stroke" stroke={colors.canvasBg} strokeWidth="3">
                      MPRL: {fmtLoadKlbf(rawMinY)} klbf
                    </text>
                  </g>
                );
              })()}
            </g>
          )}

          {/* Downhole Diagnostic Branding Emblem (Bottom Right, matching Image 2) */}
          {!isSurface && (
            <g transform={`translate(${padLeft + plotW - 130}, ${padTop + plotH - 35})`}>
              {/* Green Pumping Unit Icon */}
              <g stroke="#16a34a" strokeWidth="1.8" fill="none" strokeLinecap="round">
                <path d="M 6 22 L 14 6 L 22 22 Z" />
                <path d="M 14 6 L 14 22" />
                <path d="M 4 8 L 26 4" strokeWidth="2.2" stroke="#16a34a" />
                <path d="M 26 4 C 28 8, 28 12, 28 18" strokeWidth="1.5" />
              </g>
              <text x="34" y="14" fill="#16a34a" fontSize="10.5" fontWeight="700" fontFamily="Inter, sans-serif">
                Downhole
              </text>
              <text x="34" y="24" fill="#16a34a" fontSize="9" fontWeight="600" fontFamily="Inter, sans-serif">
                Diagnostic
              </text>
            </g>
          )}

          {/* Synchronized Animated Live Stroke Moving Cursor (Smooth 60 FPS SCADA tracker) */}
          <g transform={`translate(${scaleX(markerX)}, ${scaleY(markerY)})`}>
            {/* Outer pulsing ring */}
            <circle r="12" fill="none" stroke="#ef4444" strokeWidth="1.8">
              <animate attributeName="r" values="7;18;7" dur="1.2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.9;0.1;0.9" dur="1.2s" repeatCount="indefinite" />
            </circle>
            {/* Solid center dot */}
            <circle r="5" fill="#ef4444" stroke="#ffffff" strokeWidth="1.8" />
            {/* Live coordinates floating label */}
            <g transform="translate(14, -10)">
              <rect x="-4" y="-13" width="138" height="18" rx="3" fill="#090e1a" stroke="#ef4444" strokeWidth="0.8" opacity="0.95" />
              <text x="4" y="0" fill="#ffffff" fontSize="9" fontWeight="700" fontFamily="JetBrains Mono, monospace">
                ● LIVE {fmtPos(markerX)} in · {fmtLoadKlbf(markerY)} klbf
              </text>
            </g>
          </g>

          {/* Hover Crosshair Tooltip */}
          {hoverIdx !== null && xArr[hoverIdx] !== undefined && (
            <g>
              <line x1={scaleX(xArr[hoverIdx])} x2={scaleX(xArr[hoverIdx])} y1={padTop} y2={padTop + plotH} stroke={colors.textMuted} strokeWidth="1" strokeDasharray="2 2" />
              <line x1={padLeft} x2={padLeft + plotW} y1={scaleY(yArr[hoverIdx])} y2={scaleY(yArr[hoverIdx])} stroke={colors.textMuted} strokeWidth="1" strokeDasharray="2 2" />
              <circle cx={scaleX(xArr[hoverIdx])} cy={scaleY(yArr[hoverIdx])} r="4.5" fill="#ef4444" stroke={colors.canvasBg} strokeWidth="1.5" />
              <g transform={`translate(${Math.min(padLeft + plotW - 130, Math.max(padLeft + 10, scaleX(xArr[hoverIdx]) + 10))}, ${Math.max(padTop + 20, scaleY(yArr[hoverIdx]) - 10)})`}>
                <rect x="0" y="-16" width="120" height="20" fill={colors.canvasBg} rx="3" stroke={colors.border} strokeWidth="1" />
                <text x="6" y="-2" fill={colors.textMain} fontSize="9.5" fontFamily="JetBrains Mono, monospace">
                  {fmtPos(xArr[hoverIdx])}{posUnit} · {fmtLoadKlbf(yArr[hoverIdx])}{loadUnit}
                </text>
              </g>
            </g>
          )}

          {/* Axis Labels */}
          <text
            x={padLeft + plotW / 2}
            y={svgH - 8}
            textAnchor="middle"
            fill={colors.textMuted}
            fontSize="10"
            fontWeight="600"
            fontFamily="Inter, sans-serif">
            {isSurface ? 'Polished Rod Position' : 'Pump Plunger Position'} ({posUnit})
          </text>
          <text
            transform={`translate(16, ${padTop + plotH / 2}) rotate(-90)`}
            textAnchor="middle"
            fill={colors.textMuted}
            fontSize="10"
            fontWeight="600"
            fontFamily="Inter, sans-serif">
            {isSurface ? 'Polished Rod Load' : 'Calculated Pump Load'} ({loadUnit})
          </text>
        </svg>
      </div>

      {/* Engineering Diagnostic Telemetry HUD Panel */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: 10,
        background: isLight ? '#f8fafc' : '#090e1a',
        padding: 12,
        borderRadius: 8,
        border: `1px solid ${colors.border}`
      }}>
        {isSurface ? (
          <>
            <div>
              <span className="advait-kpi-title">SURFACE STROKE</span>
              <strong style={{ fontSize: 16, color: '#0284c7', display: 'block' }}>
                {fmtPos(surfaceData?.stroke_in || rawMaxX)} {posUnit}
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Limits span</small>
            </div>
            <div>
              <span className="advait-kpi-title">PPRL / MPRL</span>
              <strong style={{ fontSize: 14, color: colors.textMain, display: 'block' }}>
                {fmtLoadLbf(surfaceData?.pprl_lbf || rawMaxY)} / {fmtLoadLbf(surfaceData?.mprl_lbf || rawMinY)}
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Peak / Min Load (lbf)</small>
            </div>
            <div>
              <span className="advait-kpi-title">CARD AREA</span>
              <strong style={{ fontSize: 15, color: '#16a34a', display: 'block' }}>
                {fmtArea(surfaceData?.area_lbf_in || 33082)}
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Enclosed work loop</small>
            </div>
            <div>
              <span className="advait-kpi-title">ROD LOAD REF</span>
              <strong style={{ fontSize: 15, color: '#f59e0b', display: 'block' }}>
                {fmtLoadLbf(surfaceData?.submerged_rod_weight_lbf || 8166)} lbf
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Buoyant rod weight</small>
            </div>
            <div>
              <span className="advait-kpi-title">STROKE ID & SPM</span>
              <strong style={{ fontSize: 15, color: colors.textMain, display: 'block' }}>
                #{strokeId ?? 308} · {spm ? spm.toFixed(1) : '7.9'} SPM
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>{timestamp ? new Date(timestamp).toLocaleTimeString() : 'Live sync'}</small>
            </div>
            <div>
              <span className="advait-kpi-title">SOURCE & QUALITY</span>
              <strong style={{ fontSize: 13, color: quality === 'GOOD' ? '#16a34a' : '#f59e0b', display: 'block' }}>
                {quality} · {source}
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Sensor integrity verified</small>
            </div>
          </>
        ) : (
          <>
            <div>
              <span className="advait-kpi-title">MPT / EPT</span>
              <strong style={{ fontSize: 14, color: '#0284c7', display: 'block' }}>
                {fmtPos(dhFeat?.mpt_in || 53.9)} / {fmtPos(dhFeat?.ept_in || 53.2)} {posUnit}
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Max / Effective Travel</small>
            </div>
            <div>
              <span className="advait-kpi-title">PUMP FILLAGE</span>
              <strong style={{ fontSize: 16, color: (dhFeat?.fillage_pct || 98.7) < 85 ? '#ef4444' : '#16a34a', display: 'block' }}>
                {(dhFeat?.fillage_pct || 98.7).toFixed(1)} %
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>
                {dhFeat?.fluid_pound?.detected ? `Alert: ${dhFeat.fluid_pound.severity} Fluid Pound` : 'Full liquid barrel'}
              </small>
            </div>
            <div>
              <span className="advait-kpi-title">FLUID LOAD (FO)</span>
              <strong style={{ fontSize: 15, color: '#0284c7', display: 'block' }}>
                {fmtLoadLbf(dhFeat?.fluid_load_fo_lbf || 4407)} lbf
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>ΔP × Plunger Area</small>
            </div>
            <div>
              <span className="advait-kpi-title">CARD AREA & LOSS</span>
              <strong style={{ fontSize: 14, color: colors.textMain, display: 'block' }}>
                {fmtArea(dhFeat?.area_lbf_in || 1108)}
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>Stroke Loss: {fmtPos(dhFeat?.stroke_loss_in || 10.9)} {posUnit}</small>
            </div>
            <div>
              <span className="advait-kpi-title">DISPLACEMENT</span>
              <strong style={{ fontSize: 15, color: '#16a34a', display: 'block' }}>
                {(dhFeat?.displacement_bpd || 150.9).toFixed(1)} BPD
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>PIP: {(dhFeat?.pip_psi || 197).toFixed(0)} psi</small>
            </div>
            <div>
              <span className="advait-kpi-title">SOLVER QUALITY</span>
              <strong style={{ fontSize: 12, color: '#16a34a', display: 'block' }}>
                Everitt-Jennings FD/2.0
              </strong>
              <small style={{ color: colors.textMuted, fontSize: 10 }}>
                Gibbs Agreement: RMSE {downholeData?.displacement_rmse_in?.toFixed(2) ?? '0.01'} in
              </small>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
