import { formatMm, formatTick } from '../lib/format';
import { routePoints, splitRouteAtHit, toPointsAttr } from '../lib/route';
import { StageCanvas, useStageCanvas } from './StageCanvas';
import type { CheckResult, StagePayload } from '../lib/types';

interface Props {
  payload: StagePayload;
  result: CheckResult;
}

export function StageView({ payload, result }: Props) {
  return (
    <StageCanvas>
      <StageScene payload={payload} result={result} />
    </StageCanvas>
  );
}

function StageScene({ payload, result }: Props) {
  const { view, Y } = useStageCanvas();
  const { fly } = payload;
  const waypoints = fly.waypoints ?? [];
  const collides = result.collides && result.position != null;
  const cx = result.position?.x ?? 0;
  const cy = result.position?.y ?? 0;
  const split = splitRouteAtHit(payload, result);
  const responsibleZone =
    collides && result.zone_index != null ? payload.zones[result.zone_index] : undefined;
  const edgeIndex = result.edge_index ?? -1;
  const edgeA = responsibleZone?.vertices[edgeIndex];
  const edgeB = responsibleZone?.vertices[(edgeIndex + 1) % responsibleZone.vertices.length];

  const font = view.w * 0.016;
  const fontSmall = view.w * 0.013;
  const strokeW = view.w * 0.0022;

  return (
    <>
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
            {/* 选填启用窗口：在禁入区旁标注生效区间（刻度换算到 t 轴） */}
            {z.active_window && (
              <text
                x={cxp}
                y={Y(cyp) + font * 1.25}
                fontSize={fontSmall}
                fill="#c0392b"
                textAnchor="middle"
                data-testid={`zone-window-${z.id}`}
              >
                生效 [{formatTick(z.active_window.start_tick)},{' '}
                {formatTick(z.active_window.end_tick)}]
              </text>
            )}
          </g>
        );
      })}

      {/* 完整折线路径：无碰撞全绿；有碰撞则起点→命中点绿、命中点→终点红 */}
      {split ? (
        <g>
          <polyline
            points={toPointsAttr(split.safe, Y)}
            fill="none"
            stroke="#27ae60"
            strokeWidth={strokeW}
            data-testid="path-safe"
          />
          <polyline
            points={toPointsAttr(split.danger, Y)}
            fill="none"
            stroke="#e74c3c"
            strokeWidth={strokeW}
            strokeDasharray={`${view.w * 0.008} ${view.w * 0.006}`}
            data-testid="path-danger"
          />
        </g>
      ) : (
        <polyline
          points={toPointsAttr(routePoints(payload), Y)}
          fill="none"
          stroke="#27ae60"
          strokeWidth={strokeW}
          data-testid="path-safe"
        />
      )}

      {/* 中途停位姿态 */}
      {waypoints.map((wp, i) => (
        <g key={i} data-testid={`waypoint-pose-${i}`}>
          <rect
            x={wp.x}
            y={Y(wp.y + fly.height)}
            width={fly.width}
            height={fly.height}
            fill="rgba(142, 68, 173, 0.08)"
            stroke="#8e44ad"
            strokeWidth={view.w * 0.0016}
            strokeDasharray={`${view.w * 0.006} ${view.w * 0.004}`}
          />
          <circle cx={wp.x} cy={Y(wp.y)} r={view.w * 0.0032} fill="#8e44ad" />
          <text
            x={wp.x}
            y={Y(wp.y + fly.height) - fontSmall * 0.4}
            fontSize={fontSmall}
            fill="#8e44ad"
          >
            停位 {i + 1} ({formatMm(wp.x)}, {formatMm(wp.y)}) mm
          </text>
        </g>
      ))}

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
            首次碰撞：第 {(result.segment_index ?? 0) + 1} 段 · 段内 t=
            {result.segment_t_display} · 全程 t={result.t_display} ({result.position_display?.x},{' '}
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
    </>
  );
}
