import { formatMm } from '../lib/format';
import { flyRoutePoints, splitFlyRouteAtHit, toPointsAttr } from '../lib/route';
import { StageCanvas, useStageCanvas } from './StageCanvas';
import type { EncounterPayload, EncounterResult, FlyPose } from '../lib/types';

interface Props {
  payload: EncounterPayload;
  result: EncounterResult;
}

const FLY_STYLE = {
  a: { route: '#2980b9', pose: 'rgba(41, 128, 185, 0.12)', label: '#2980b9' },
  b: { route: '#8e44ad', pose: 'rgba(142, 68, 173, 0.12)', label: '#8e44ad' },
} as const;

export function EncounterView({ payload, result }: Props) {
  return (
    <StageCanvas testid="encounter-view">
      <EncounterScene payload={payload} result={result} />
    </StageCanvas>
  );
}

function FlyLayer({
  fly,
  pose,
  kind,
  collides,
}: {
  fly: EncounterPayload['fly_a'];
  pose: FlyPose | null;
  kind: 'a' | 'b';
  collides: boolean;
}) {
  const { view, Y } = useStageCanvas();
  const style = FLY_STYLE[kind];
  const fontSmall = view.w * 0.013;
  const strokeW = view.w * 0.0024;
  const hit = pose?.position ?? null;
  const split =
    collides && pose && hit
      ? splitFlyRouteAtHit(fly, pose.segment_index, hit)
      : null;

  return (
    <g data-testid={`route-${kind}`}>
      {/* 路线：无碰撞全绿；有冲突时接触点前实色、接触点后虚线 */}
      {split ? (
        <>
          <polyline
            points={toPointsAttr(split.safe, Y)}
            fill="none"
            stroke={style.route}
            strokeWidth={strokeW}
            data-testid={`path-${kind}-safe`}
          />
          <polyline
            points={toPointsAttr(split.danger, Y)}
            fill="none"
            stroke={style.route}
            strokeWidth={strokeW}
            strokeDasharray={`${view.w * 0.008} ${view.w * 0.006}`}
            opacity={0.55}
            data-testid={`path-${kind}-danger`}
          />
        </>
      ) : (
        <polyline
          points={toPointsAttr(flyRoutePoints(fly), Y)}
          fill="none"
          stroke="#27ae60"
          strokeWidth={strokeW}
          data-testid={`path-${kind}-safe`}
        />
      )}

      {/* 中途停位 */}
      {(fly.waypoints ?? []).map((wp, i) => (
        <g key={i} data-testid={`${kind}-waypoint-pose-${i}`}>
          <rect
            x={wp.x}
            y={Y(wp.y + fly.height)}
            width={fly.width}
            height={fly.height}
            fill={style.pose}
            stroke={style.route}
            strokeWidth={view.w * 0.0014}
            strokeDasharray={`${view.w * 0.005} ${view.w * 0.004}`}
          />
          <circle cx={wp.x} cy={Y(wp.y)} r={view.w * 0.0028} fill={style.route} />
        </g>
      ))}

      {/* 起终姿态 */}
      <g data-testid={`${kind}-start-pose`}>
        <rect
          x={fly.start.x}
          y={Y(fly.start.y + fly.height)}
          width={fly.width}
          height={fly.height}
          fill={style.pose}
          stroke={style.route}
          strokeWidth={view.w * 0.0016}
        />
        <text x={fly.start.x} y={Y(fly.start.y + fly.height) - fontSmall * 0.4} fontSize={fontSmall} fill={style.label}>
          {fly.id} 起点 ({formatMm(fly.start.x)}, {formatMm(fly.start.y)})
        </text>
      </g>
      <g data-testid={`${kind}-end-pose`}>
        <rect
          x={fly.end.x}
          y={Y(fly.end.y + fly.height)}
          width={fly.width}
          height={fly.height}
          fill={style.pose}
          stroke={style.route}
          strokeWidth={view.w * 0.0016}
          strokeDasharray={`${view.w * 0.006} ${view.w * 0.004}`}
        />
        <text x={fly.end.x} y={Y(fly.end.y + fly.height) - fontSmall * 0.4} fontSize={fontSmall} fill={style.label}>
          {fly.id} 终点
        </text>
      </g>

      {/* 首次接触姿态 */}
      {collides && pose && hit && (
        <g data-testid={`${kind}-contact-pose`}>
          <rect
            x={hit.x}
            y={Y(hit.y + fly.height)}
            width={fly.width}
            height={fly.height}
            fill={kind === 'a' ? 'rgba(231, 76, 60, 0.18)' : 'rgba(243, 156, 18, 0.18)'}
            stroke={kind === 'a' ? '#e74c3c' : '#f39c12'}
            strokeWidth={view.w * 0.0024}
          />
        </g>
      )}
    </g>
  );
}

function EncounterScene({ payload, result }: Props) {
  const { view, Y } = useStageCanvas();
  const font = view.w * 0.016;
  const collides =
    result.collides &&
    result.contact != null &&
    result.fly_a != null &&
    result.fly_b != null;
  const contact = result.contact ?? { x: 0, y: 0 };

  return (
    <>
      <FlyLayer fly={payload.fly_a} pose={result.fly_a} kind="a" collides={collides} />
      <FlyLayer fly={payload.fly_b} pose={result.fly_b} kind="b" collides={collides} />

      {/* 接触点标记 */}
      {collides && (
        <g data-testid="contact-marker">
          <circle cx={contact.x} cy={Y(contact.y)} r={view.w * 0.005} fill="#c0392b" stroke="#fff" strokeWidth={view.w * 0.0012} />
          <text
            x={contact.x}
            y={Y(contact.y) - view.w * 0.008}
            fontSize={font}
            fill="#c0392b"
            textAnchor="middle"
          >
            首次接触 全程 t={result.t_display}（{result.contact_display?.x}, {result.contact_display?.y}）mm
          </text>
        </g>
      )}

      {/* 图例 */}
      <g data-testid="encounter-legend">
        <rect x={120} y={Y(9850)} width={view.w * 0.05} height={view.w * 0.012} fill={FLY_STYLE.a.route} />
        <text x={120 + view.w * 0.06} y={Y(9850) + font} fontSize={font * 0.8} fill="#2980b9">
          吊景 {payload.fly_a.id}
        </text>
        <rect x={120 + view.w * 0.22} y={Y(9850)} width={view.w * 0.05} height={view.w * 0.012} fill={FLY_STYLE.b.route} />
        <text x={120 + view.w * 0.28} y={Y(9850) + font} fontSize={font * 0.8} fill="#8e44ad">
          吊景 {payload.fly_b.id}
        </text>
      </g>
    </>
  );
}
