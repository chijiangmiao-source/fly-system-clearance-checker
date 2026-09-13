import { addDecimalInts } from './bigInt';
import { asPositiveInt, type IntValue } from './json';
import type { CheckResult, EncounterFly, StagePayload, StagePoint } from './types';

/** 单套吊景的折线顶点（不依赖 zones/id）。 */
export type FlyRoute = Pick<EncounterFly, 'start' | 'end' | 'waypoints'>;

/** 各段相对耗时：weights 为每段权重，total 为权重总和（占比 = weights[i]/total）。
 *  超大权重以精确十进制字符串保存，total 亦为字符串，渲染时不经 Number。 */
export interface SegmentDurations {
  weights: IntValue[];
  total: string;
}

/**
 * 读取吊景的各段相对耗时；未提供 duration_weights（或长度与段数不符，
 * 服务端会拒绝、此处防御性忽略）时返回 null —— 各段等时，页面不标注。
 * 权重为正整数（number 或精确十进制字符串），总和按十进制字符串精确累加，
 * 避免超大整数被浮点舍入或求和溢出为 Infinity。
 */
export function segmentDurations(
  fly: FlyRoute & { duration_weights?: Array<number | string> },
): SegmentDurations | null {
  const raw = fly.duration_weights;
  if (!raw || raw.length === 0) return null;
  if (raw.length !== flyRoutePoints(fly).length - 1) return null;
  const weights: IntValue[] = [];
  for (const w of raw) {
    const v = asPositiveInt(w);
    if (v === null) return null;
    weights.push(v);
  }
  const total = weights
    .map((w) => (typeof w === 'number' ? String(w) : w))
    .reduce((s, w) => addDecimalInts(s, w), '0');
  return { weights, total };
}

/** 完整折线的顶点：start → 各中途停位 → end。 */
export function routePoints(payload: StagePayload): StagePoint[] {
  return flyRoutePoints(payload.fly);
}

/** 单套吊景完整折线的顶点：start → 各停位 → end。 */
export function flyRoutePoints(fly: FlyRoute): StagePoint[] {
  return [fly.start, ...(fly.waypoints ?? []), fly.end];
}

export interface RouteSplit {
  /** 碰撞前的安全路径折线顶点（含命中点为末点）。 */
  safe: StagePoint[];
  /** 命中后的危险路径折线顶点（以命中点为首点）。 */
  danger: StagePoint[];
  /** 命中段序号（从 0 起）。 */
  segmentIndex: number;
  /** 命中点。 */
  hit: StagePoint;
}

/**
 * 按首次命中位置把一条折线切成绿（起点→命中点）/红（命中点→终点）两部分。
 * 命中点恰在折点上（段内 t=0/1）时折叠重合点。
 */
export function splitFlyRouteAtHit(
  fly: FlyRoute,
  segmentIndex: number,
  hit: StagePoint,
): RouteSplit | null {
  const points = flyRoutePoints(fly);
  if (segmentIndex < 0 || segmentIndex >= points.length - 1) {
    return null;
  }
  const same = (a: StagePoint, b: StagePoint) => a.x === b.x && a.y === b.y;
  const safeTail = points.slice(0, segmentIndex + 1);
  const dangerHead = points.slice(segmentIndex + 1);
  const safe = [
    ...safeTail,
    ...(safeTail.length === 0 || !same(safeTail[safeTail.length - 1], hit) ? [hit] : []),
  ];
  const danger = [
    ...(dangerHead.length === 0 || !same(dangerHead[0], hit) ? [hit] : []),
    ...dangerHead,
  ];
  return { safe, danger, segmentIndex, hit };
}

/**
 * 按首次命中位置把完整折线切成绿（起点→命中点）/红（命中点→终点）两部分。
 * 命中段由 result.segment_index 指定；折点两侧同时命中时 API 已归前段。
 */
export function splitRouteAtHit(payload: StagePayload, result: CheckResult): RouteSplit | null {
  if (!result.collides || result.position == null || result.segment_index == null) {
    return null;
  }
  return splitFlyRouteAtHit(payload.fly, result.segment_index, result.position);
}

/** 把折线顶点数组转为 SVG polyline points 串（舞台坐标 y 向上，需 Y 翻转）。 */
export function toPointsAttr(points: StagePoint[], yFlip: (y: number) => number): string {
  return points.map((p) => `${p.x},${yFlip(p.y)}`).join(' ');
}
