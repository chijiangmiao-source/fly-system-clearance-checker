import { useEffect, useRef, useState } from 'react';
import { formatMm } from '../lib/format';
import type { CheckResult, StagePayload } from '../lib/types';

const STAGE = 10000;
const Y = (y: number) => STAGE - y; // 舞台坐标 y 向上 → SVG y 向下

interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

const INITIAL_VIEW: ViewBox = { x: -600, y: -600, w: 11200, h: 11200 };

interface Props {
  payload: StagePayload;
  result: CheckResult;
}

export function StageView({ payload, result }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<ViewBox>(INITIAL_VIEW);
  const drag = useRef<{ px: number; py: number } | null>(null);

  const { fly } = payload;
  const collides = result.collides && result.position != null;
  const cx = result.position?.x ?? 0;
  const cy = result.position?.y ?? 0;
  const responsibleZone =
    collides && result.zone_index != null ? payload.zones[result.zone_index] : undefined;
  const edgeIndex = result.edge_index ?? -1;
  const edgeA = responsibleZone?.vertices[edgeIndex];
  const edgeB = responsibleZone?.vertices[(edgeIndex + 1) % responsibleZone.vertices.length];

  // 滚轮缩放需要非 passive 监听
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const fx = (e.clientX - rect.left) / rect.width;
      const fy = (e.clientY - rect.top) / rect.height;
      const scale = e.deltaY < 0 ? 0.8 : 1.25;
      setView((v) => {
        const w = Math.min(60000, Math.max(200, v.w * scale));
        const h = Math.min(60000, Math.max(200, v.h * scale));
        return { x: v.x + fx * (v.w - w), y: v.y + fy * (v.h - h), w, h };
      });
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, []);

  const zoomBy = (scale: number) =>
    setView((v) => {
      const w = Math.min(60000, Math.max(200, v.w * scale));
      const h = Math.min(60000, Math.max(200, v.h * scale));
      return { x: v.x + (v.w - w) / 2, y: v.y + (v.h - h) / 2, w, h };
    });

  const font = view.w * 0.016;
  const fontSmall = view.w * 0.013;

  return (
    <div className="stage-view-wrap">
      <div className="view-toolbar">
        <button data-testid="zoom-in" onClick={() => zoomBy(0.8)}>
          放大
        </button>
        <button data-testid="zoom-out" onClick={() => zoomBy(1.25)}>
          缩小
        </button>
        <button data-testid="zoom-reset" onClick={() => setView(INITIAL_VIEW)}>
          重置视图
        </button>
        <span className="hint">滚轮缩放 · 拖拽平移 · 坐标单位 mm</span>
      </div>
      <svg
        ref={svgRef}
        data-testid="stage-view"
        className="stage-view"
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        onPointerDown={(e) => {
          drag.current = { px: e.clientX, py: e.clientY };
          (e.target as Element).setPointerCapture?.(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!drag.current || !svgRef.current) return;
          const rect = svgRef.current.getBoundingClientRect();
          const dx = ((e.clientX - drag.current.px) / rect.width) * view.w;
          const dy = ((e.clientY - drag.current.py) / rect.height) * view.h;
          drag.current = { px: e.clientX, py: e.clientY };
          setView((v) => ({ ...v, x: v.x - dx, y: v.y - dy }));
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerLeave={() => (drag.current = null)}
      >
        {/* 台口 */}
        <rect
          x={0}
          y={0}
          width={STAGE}
          height={STAGE}
          fill="#fbfcfe"
          stroke="#33475b"
          strokeWidth={view.w * 0.0012}
          data-testid="stage-boundary"
        />
        <text x={120} y={Y(STAGE - 120)} fontSize={font} fill="#33475b">
          台口 10000 × 10000 mm
        </text>

        {/* 禁入区 */}
        {payload.zones.map((z, zi) => {
          const pts = z.vertices.map((v) => `${v.x},${Y(v.y)}`).join(' ');
          const cxp = z.vertices.reduce((s, v) => s + v.x, 0) / z.vertices.length;
          const cyp = z.vertices.reduce((s, v) => s + v.y, 0) / z.vertices.length;
          return (
            <g key={zi}>
              <polygon
                points={pts}
                fill="rgba(231, 76, 60, 0.16)"
                stroke="#c0392b"
                strokeWidth={view.w * 0.0012}
                data-testid={`zone-${z.id}`}
              />
              <text x={cxp} y={Y(cyp)} fontSize={font} fill="#c0392b" textAnchor="middle">
                禁入区 {z.id}
              </text>
            </g>
          );
        })}

        {/* 完整路径：无碰撞全绿；有碰撞则起点→碰撞点绿、碰撞点→终点红 */}
        {collides ? (
          <g>
            <line
              x1={fly.start.x}
              y1={Y(fly.start.y)}
              x2={cx}
              y2={Y(cy)}
              stroke="#27ae60"
              strokeWidth={view.w * 0.0022}
              data-testid="path-safe"
            />
            <line
              x1={cx}
              y1={Y(cy)}
              x2={fly.end.x}
              y2={Y(fly.end.y)}
              stroke="#e74c3c"
              strokeWidth={view.w * 0.0022}
              strokeDasharray={`${view.w * 0.008} ${view.w * 0.006}`}
              data-testid="path-danger"
            />
          </g>
        ) : (
          <line
            x1={fly.start.x}
            y1={Y(fly.start.y)}
            x2={fly.end.x}
            y2={Y(fly.end.y)}
            stroke="#27ae60"
            strokeWidth={view.w * 0.0022}
            data-testid="path-safe"
          />
        )}

        {/* 起终姿态 */}
        <g data-testid="start-pose">
          <rect
            x={fly.start.x}
            y={Y(fly.start.y + fly.height)}
            width={fly.width}
            height={fly.height}
            fill="rgba(41, 128, 185, 0.10)"
            stroke="#2980b9"
            strokeWidth={view.w * 0.0016}
            strokeDasharray={`${view.w * 0.006} ${view.w * 0.004}`}
          />
          <text x={fly.start.x} y={Y(fly.start.y + fly.height) - fontSmall * 0.4} fontSize={fontSmall} fill="#2980b9">
            起点 ({formatMm(fly.start.x)}, {formatMm(fly.start.y)}) mm
          </text>
        </g>
        <g data-testid="end-pose">
          <rect
            x={fly.end.x}
            y={Y(fly.end.y + fly.height)}
            width={fly.width}
            height={fly.height}
            fill="rgba(127, 140, 141, 0.10)"
            stroke="#7f8c8d"
            strokeWidth={view.w * 0.0016}
            strokeDasharray={`${view.w * 0.006} ${view.w * 0.004}`}
          />
          <text x={fly.end.x} y={Y(fly.end.y + fly.height) - fontSmall * 0.4} fontSize={fontSmall} fill="#5d6d7e">
            终点 ({formatMm(fly.end.x)}, {formatMm(fly.end.y)}) mm
          </text>
        </g>

        {/* 首次碰撞姿态 */}
        {collides && (
          <g data-testid="collision-pose">
            <rect
              x={cx}
              y={Y(cy + fly.height)}
              width={fly.width}
              height={fly.height}
              fill="rgba(231, 76, 60, 0.22)"
              stroke="#e74c3c"
              strokeWidth={view.w * 0.0024}
            />
            <circle cx={cx} cy={Y(cy)} r={view.w * 0.004} fill="#e74c3c" />
            <text x={cx} y={Y(cy) + font * 1.2} fontSize={font} fill="#e74c3c">
              首次碰撞 t={result.t_display} ({result.position_display?.x},{' '}
              {result.position_display?.y}) mm
            </text>
          </g>
        )}

        {/* 责任边 */}
        {collides && edgeA && edgeB && (
          <g data-testid="responsible-edge">
            <line
              x1={edgeA.x}
              y1={Y(edgeA.y)}
              x2={edgeB.x}
              y2={Y(edgeB.y)}
              stroke="#f39c12"
              strokeWidth={view.w * 0.005}
              strokeLinecap="round"
            />
            <text
              x={(edgeA.x + edgeB.x) / 2}
              y={Y((edgeA.y + edgeB.y) / 2) - fontSmall * 0.5}
              fontSize={font}
              fill="#d68910"
              textAnchor="middle"
            >
              责任边 #{edgeIndex}（禁入区 {result.zone_id}）
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}
