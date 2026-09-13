import { describe, expect, it } from 'vitest';
import { routePoints, splitRouteAtHit, toPointsAttr } from './route';
import type { CheckResult, StagePayload } from './types';

const payload = (waypoints?: Array<{ x: number; y: number }>): StagePayload => ({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 3000 },
    waypoints,
    end: { x: 9000, y: 3000 },
  },
  zones: [],
});

const hitResult = (
  segmentIndex: number,
  position: { x: number; y: number },
): CheckResult => ({
  collides: true,
  t: 0.625,
  t_display: '0.625000',
  zone_id: 'A',
  zone_index: 0,
  edge_index: 2,
  segment_index: segmentIndex,
  segment_t_display: '0.250000',
  position,
  position_display: { x: String(position.x), y: String(position.y) },
});

const SAFE_RESULT: CheckResult = {
  collides: false,
  t: null,
  t_display: null,
  zone_id: null,
  zone_index: null,
  edge_index: null,
  segment_index: null,
  segment_t_display: null,
  position: null,
  position_display: null,
};

describe('routePoints', () => {
  it('无 waypoints 时仅起终点', () => {
    expect(routePoints(payload())).toEqual([
      { x: 0, y: 3000 },
      { x: 9000, y: 3000 },
    ]);
  });

  it('含 waypoints 时按 start → 停位 → end 排列', () => {
    const pts = routePoints(payload([{ x: 5000, y: 3000 }]));
    expect(pts).toEqual([
      { x: 0, y: 3000 },
      { x: 5000, y: 3000 },
      { x: 9000, y: 3000 },
    ]);
  });
});

describe('splitRouteAtHit', () => {
  it('无碰撞返回 null', () => {
    expect(splitRouteAtHit(payload([{ x: 5000, y: 3000 }]), SAFE_RESULT)).toBeNull();
  });

  it('第二段命中：安全折线到命中点，危险折线从命中点出发', () => {
    const p = payload([{ x: 5000, y: 3000 }]);
    const split = splitRouteAtHit(p, hitResult(1, { x: 6000, y: 3000 }));
    expect(split).not.toBeNull();
    expect(split!.segmentIndex).toBe(1);
    expect(split!.hit).toEqual({ x: 6000, y: 3000 });
    expect(split!.safe).toEqual([
      { x: 0, y: 3000 },
      { x: 5000, y: 3000 },
      { x: 6000, y: 3000 },
    ]);
    expect(split!.danger).toEqual([
      { x: 6000, y: 3000 },
      { x: 9000, y: 3000 },
    ]);
  });

  it('第一段命中：安全折线不含停位，危险折线经过全部后续折点', () => {
    const p = payload([
      { x: 5000, y: 3000 },
      { x: 7000, y: 6000 },
    ]);
    const split = splitRouteAtHit(p, hitResult(0, { x: 3000, y: 3000 }));
    expect(split!.safe).toEqual([
      { x: 0, y: 3000 },
      { x: 3000, y: 3000 },
    ]);
    expect(split!.danger).toEqual([
      { x: 3000, y: 3000 },
      { x: 5000, y: 3000 },
      { x: 7000, y: 6000 },
      { x: 9000, y: 3000 },
    ]);
  });

  it('折点命中归前段（segment_index 指向前一段）', () => {
    const p = payload([{ x: 5000, y: 3000 }]);
    const split = splitRouteAtHit(p, hitResult(0, { x: 5000, y: 3000 }));
    expect(split!.safe).toEqual([
      { x: 0, y: 3000 },
      { x: 5000, y: 3000 },
    ]);
    expect(split!.danger[0]).toEqual({ x: 5000, y: 3000 });
  });

  it('单段请求兼容：命中点把直线分两段', () => {
    const split = splitRouteAtHit(payload(), hitResult(0, { x: 3000, y: 3000 }));
    expect(split!.safe).toEqual([
      { x: 0, y: 3000 },
      { x: 3000, y: 3000 },
    ]);
    expect(split!.danger).toEqual([
      { x: 3000, y: 3000 },
      { x: 9000, y: 3000 },
    ]);
  });
});

describe('toPointsAttr', () => {
  it('应用 y 翻转并拼接坐标串', () => {
    const attr = toPointsAttr(
      [
        { x: 0, y: 0 },
        { x: 100, y: 250 },
      ],
      (y) => 10000 - y,
    );
    expect(attr).toBe('0,10000 100,9750');
  });
});
