import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { EncounterView } from './components/EncounterView';
import type { EncounterPayload, EncounterResult } from './lib/types';

const STAGE = { width: 10000, height: 10000 };

// 场景 2：A 两段、B 三段，t=8/19 首次角点接触
const MID_PAYLOAD: EncounterPayload = {
  stage: STAGE,
  fly_a: {
    id: 'A',
    width: 1000,
    height: 1000,
    start: { x: 0, y: 3000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 3000 },
  },
  fly_b: {
    id: 'B',
    width: 1000,
    height: 1000,
    start: { x: 9000, y: 2000 },
    waypoints: [
      { x: 6000, y: 4000 },
      { x: 3000, y: 4000 },
    ],
    end: { x: 0, y: 2000 },
  },
};

const MID_RESULT: EncounterResult = {
  collides: true,
  t: 8 / 19,
  t_display: '0.421053',
  t_fraction: '8/19',
  fly_a: {
    id: 'A',
    segment_index: 0,
    segment_t_display: '0.842105',
    position: { x: 80000 / 19, y: 3000 },
    position_display: { x: '4210.526316', y: '3000' },
  },
  fly_b: {
    id: 'B',
    segment_index: 1,
    segment_t_display: '0.263158',
    position: { x: 99000 / 19, y: 4000 },
    position_display: { x: '5210.526316', y: '4000' },
  },
  contact: { x: 99000 / 19, y: 4000 },
  contact_display: { x: '5210.526316', y: '4000' },
};

const SAFE_RESULT: EncounterResult = {
  collides: false,
  t: null,
  t_display: null,
  fly_a: null,
  fly_b: null,
  contact: null,
  contact_display: null,
};

describe('EncounterView 服务端渲染冒烟（无需浏览器）', () => {
  it('中途相撞：同时绘制两条路线、双方接触姿态与接触点', () => {
    const html = renderToStaticMarkup(
      createElement(EncounterView, { payload: MID_PAYLOAD, result: MID_RESULT }),
    );
    // 两条路线（各自安全段/危险段）
    expect(html).toContain('data-testid="route-a"');
    expect(html).toContain('data-testid="route-b"');
    expect(html).toContain('data-testid="path-a-safe"');
    expect(html).toContain('data-testid="path-b-safe"');
    expect(html).toContain('data-testid="path-a-danger"');
    expect(html).toContain('data-testid="path-b-danger"');
    // 双方首次接触姿态
    expect(html).toContain('data-testid="a-contact-pose"');
    expect(html).toContain('data-testid="b-contact-pose"');
    // 接触点与全程时刻
    expect(html).toContain('data-testid="contact-marker"');
    expect(html).toContain('0.421053');
    expect(html).toContain('5210.526316');
    // 双方起终姿态与图例
    expect(html).toContain('data-testid="a-start-pose"');
    expect(html).toContain('b-end-pose');
    expect(html).toContain('data-testid="encounter-legend"');
    expect(html).toContain('吊景 A');
    expect(html).toContain('吊景 B');
  });

  it('安全方案：两条路线均全绿、无接触姿态与接触点', () => {
    const html = renderToStaticMarkup(
      createElement(EncounterView, { payload: MID_PAYLOAD, result: SAFE_RESULT }),
    );
    expect(html).toContain('data-testid="path-a-safe"');
    expect(html).toContain('data-testid="path-b-safe"');
    expect(html).not.toContain('path-a-danger');
    expect(html).not.toContain('path-b-danger');
    expect(html).not.toContain('contact-pose');
    expect(html).not.toContain('data-testid="contact-marker"');
  });

  it('起始即接触：命中点即起点，双方段号 0 姿态绘制在起点', () => {
    const payload: EncounterPayload = {
      stage: STAGE,
      fly_a: {
        id: 'A', width: 1000, height: 1000,
        start: { x: 0, y: 0 }, end: { x: 4000, y: 0 },
      },
      fly_b: {
        id: 'B', width: 1000, height: 1000,
        start: { x: 1000, y: 0 }, end: { x: 5000, y: 0 },
      },
    };
    const result: EncounterResult = {
      collides: true,
      t: 0,
      t_display: '0.000000',
      t_fraction: '0/1',
      fly_a: {
        id: 'A', segment_index: 0, segment_t_display: '0.000000',
        position: { x: 0, y: 0 }, position_display: { x: '0', y: '0' },
      },
      fly_b: {
        id: 'B', segment_index: 0, segment_t_display: '0.000000',
        position: { x: 1000, y: 0 }, position_display: { x: '1000', y: '0' },
      },
      contact: { x: 1000, y: 500 },
      contact_display: { x: '1000', y: '500' },
    };
    const html = renderToStaticMarkup(createElement(EncounterView, { payload, result }));
    expect(html).toContain('data-testid="a-contact-pose"');
    expect(html).toContain('data-testid="b-contact-pose"');
    expect(html).toContain('data-testid="contact-marker"');
    expect(html).toContain('0.000000');
  });

  it('未提供 duration_weights 的方案不绘制各段耗时标注', () => {
    const html = renderToStaticMarkup(
      createElement(EncounterView, { payload: MID_PAYLOAD, result: MID_RESULT }),
    );
    expect(html).not.toContain('seg-duration');
  });

  it('加权方案：在各段旁标出相对耗时与占总时长比例', () => {
    // A 两段权重 [1,3]，B 单段未加权：t=7/18 首次接触，A 在第 1 段
    const payload: EncounterPayload = {
      stage: STAGE,
      fly_a: {
        id: 'A', width: 1000, height: 1000,
        start: { x: 0, y: 4500 },
        waypoints: [{ x: 4500, y: 4500 }],
        end: { x: 9000, y: 4500 },
        duration_weights: [1, 3],
      },
      fly_b: {
        id: 'B', width: 1000, height: 1000,
        start: { x: 5000, y: 0 }, end: { x: 5000, y: 9000 },
      },
    };
    const result: EncounterResult = {
      collides: true,
      t: 7 / 18,
      t_display: '0.388889',
      t_fraction: '7/18',
      fly_a: {
        id: 'A', segment_index: 1, segment_t_display: '0.185185',
        position: { x: 16000 / 3, y: 4500 },
        position_display: { x: '5333.333333', y: '4500' },
      },
      fly_b: {
        id: 'B', segment_index: 0, segment_t_display: '0.388889',
        position: { x: 5000, y: 3500 },
        position_display: { x: '5000', y: '3500' },
      },
      contact: { x: 17000 / 3, y: 4500 },
      contact_display: { x: '5666.666667', y: '4500' },
    };
    const html = renderToStaticMarkup(createElement(EncounterView, { payload, result }));
    // A 的两段各标注相对耗时与占比；B 未提供权重不标注
    expect(html).toContain('data-testid="a-seg-duration-0"');
    expect(html).toContain('段#0 耗时 1（占 1/4）');
    expect(html).toContain('data-testid="a-seg-duration-1"');
    expect(html).toContain('段#1 耗时 3（占 3/4）');
    expect(html).not.toContain('b-seg-duration');
    // 检测结果仍展示双方命中段与接触姿态
    expect(html).toContain('data-testid="a-contact-pose"');
    expect(html).toContain('data-testid="contact-marker"');
  });

  it('双方均加权：两条路线的各段都标注', () => {
    const payload: EncounterPayload = {
      stage: STAGE,
      fly_a: {
        id: 'A', width: 1000, height: 1000,
        start: { x: 0, y: 4500 },
        waypoints: [{ x: 4500, y: 4500 }],
        end: { x: 9000, y: 4500 },
        duration_weights: [3, 1],
      },
      fly_b: {
        id: 'B', width: 1000, height: 1000,
        start: { x: 5000, y: 0 },
        waypoints: [{ x: 5000, y: 4500 }],
        end: { x: 5000, y: 9000 },
        duration_weights: [3, 1],
      },
    };
    const html = renderToStaticMarkup(
      createElement(EncounterView, { payload, result: SAFE_RESULT }),
    );
    expect(html).toContain('data-testid="a-seg-duration-0"');
    expect(html).toContain('data-testid="a-seg-duration-1"');
    expect(html).toContain('data-testid="b-seg-duration-0"');
    expect(html).toContain('data-testid="b-seg-duration-1"');
    expect(html).toContain('段#0 耗时 3（占 3/4）');
    expect(html).toContain('段#1 耗时 1（占 1/4）');
  });
});
