import { describe, expect, it } from 'vitest';
import {
  flyRoutePoints,
  routePoints,
  segmentDurations,
  splitFlyRouteAtHit,
  splitRouteAtHit,
  toPointsAttr,
} from './route';
import type { CheckResult, EncounterFly, StagePayload } from './types';

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

describe('交会方案：flyRoutePoints / splitFlyRouteAtHit', () => {
  const flyA: EncounterFly = {
    id: 'A',
    width: 1000,
    height: 1000,
    start: { x: 0, y: 3000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 3000 },
  };
  const flyB: EncounterFly = {
    id: 'B',
    width: 1000,
    height: 1000,
    start: { x: 9000, y: 2000 },
    waypoints: [
      { x: 6000, y: 4000 },
      { x: 3000, y: 4000 },
    ],
    end: { x: 0, y: 2000 },
  };

  it('flyRoutePoints 展开各自折线（双方分段数可不同）', () => {
    expect(flyRoutePoints(flyA)).toHaveLength(3);
    expect(flyRoutePoints(flyB)).toHaveLength(4);
    expect(flyRoutePoints(flyB)[1]).toEqual({ x: 6000, y: 4000 });
  });

  it('双方分段数不同时按各自段号切分：A 在第 0 段、B 在第 1 段', () => {
    // t=8/19：A 左下角 (80000/19,3000)（第 0 段），B 左下角 (99000/19,4000)（第 1 段）
    const aHit = { x: 80000 / 19, y: 3000 };
    const bHit = { x: 99000 / 19, y: 4000 };
    const sa = splitFlyRouteAtHit(flyA, 0, aHit);
    const sb = splitFlyRouteAtHit(flyB, 1, bHit);
    expect(sa!.safe).toEqual([{ x: 0, y: 3000 }, aHit]);
    expect(sa!.danger[0]).toEqual(aHit);
    expect(sa!.danger).toContainEqual({ x: 5000, y: 3000 });
    expect(sb!.safe).toEqual([
      { x: 9000, y: 2000 },
      { x: 6000, y: 4000 },
      bHit,
    ]);
    expect(sb!.danger).toEqual([
      bHit,
      { x: 3000, y: 4000 },
      { x: 0, y: 2000 },
    ]);
  });

  it('起始即接触（段号 0、命中点即起点）：safe 折叠重合点', () => {
    const split = splitFlyRouteAtHit(flyA, 0, { x: 0, y: 3000 });
    expect(split!.safe).toEqual([{ x: 0, y: 3000 }]);
    expect(split!.danger[0]).toEqual({ x: 0, y: 3000 });
  });

  it('越界段号返回 null', () => {
    expect(splitFlyRouteAtHit(flyA, 5, { x: 1, y: 1 })).toBeNull();
  });
});

describe('交会方案：segmentDurations 各段相对耗时', () => {
  const flyA: EncounterFly = {
    id: 'A',
    width: 1000,
    height: 1000,
    start: { x: 0, y: 4500 },
    waypoints: [{ x: 4500, y: 4500 }],
    end: { x: 9000, y: 4500 },
  };

  it('未提供 duration_weights 时返回 null（各段等时，不标注）', () => {
    expect(segmentDurations(flyA)).toBeNull();
    expect(segmentDurations({ ...flyA, duration_weights: [] })).toBeNull();
  });

  it('提供权重时返回各段相对耗时与权重总和（总和为精确十进制串）', () => {
    expect(segmentDurations({ ...flyA, duration_weights: [3, 1] })).toEqual({
      weights: [3, 1],
      total: '4',
    });
  });

  it('单段路线接受单元素权重', () => {
    const one: EncounterFly = {
      id: 'B', width: 1000, height: 1000,
      start: { x: 5000, y: 0 }, end: { x: 5000, y: 9000 },
      duration_weights: [5],
    };
    expect(segmentDurations(one)).toEqual({ weights: [5], total: '5' });
  });

  it('长度与段数不符或非正整数时防御性返回 null', () => {
    expect(segmentDurations({ ...flyA, duration_weights: [1, 2, 3] })).toBeNull();
    expect(segmentDurations({ ...flyA, duration_weights: [1, 0] })).toBeNull();
    expect(segmentDurations({ ...flyA, duration_weights: [1, 1.5] })).toBeNull();
  });

  it('十六位权重（超过安全整数）保留精确十进制串，不被浮点舍入', () => {
    // 9007199254740993 = 2^53+1，JSON.parse 会舍成 9007199254740992
    const w = '9007199254740993';
    const d = segmentDurations({ ...flyA, duration_weights: [w, '1'] });
    expect(d).not.toBeNull();
    expect(d!.weights[0]).toBe(w);
    expect(d!.total).toBe('9007199254740994');
  });

  it('三百一十位权重与三百零九位双权重：字符串精确累加，不产生 Infinity', () => {
    const w310 = '1' + '0'.repeat(309); // 10^309，超过 Number.MAX_VALUE，JSON.parse → Infinity
    const d1 = segmentDurations({ ...flyA, duration_weights: [w310, '1'] });
    expect(d1).not.toBeNull();
    expect(d1!.weights[0]).toBe(w310);
    expect(d1!.total).toBe('1' + '0'.repeat(308) + '1'); // 10^309 + 1

    // 两个 309 位权重 5×10^308 各一份，精确总和 = 10^309（310 位）
    const a = '5' + '0'.repeat(308);
    const d2 = segmentDurations({ ...flyA, duration_weights: [a, a] });
    expect(d2).not.toBeNull();
    expect(d2!.weights).toEqual([a, a]);
    expect(d2!.total).toBe('1' + '0'.repeat(309));
    expect(Number.isFinite(Number(d2!.total))).toBe(false); // 确证超出浮点范围但仍精确
  });

  it('安全范围内的十进制串归一化为 number', () => {
    const d = segmentDurations({ ...flyA, duration_weights: ['003', 1] });
    expect(d).toEqual({ weights: [3, 1], total: '4' });
  });
});
